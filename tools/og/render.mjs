// 王座戦の共有画像を作って、サーバーに預ける（GitHub Actions から動かす）
//   環境変数: SITE（既定 https://hyakkakenten.com）, ADMIN_TOKEN, CHROME（使うブラウザ。省略時はインストール済みの Chrome）
//            NTFY_TOPIC（任意。王座交代・節目の防衛のとき、Xの投稿画面を開く通知を ntfy に送る）
//            NOTIFY_TEST（任意。1 なら画像は作らず、いちばん新しい王座交代の通知を試しに送る）
import { chromium } from 'playwright-core';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const SITE = process.env.SITE || 'https://hyakkakenten.com';
const AUTH = { Authorization: 'Bearer ' + process.env.ADMIN_TOKEN };
const HERE = path.dirname(fileURLToPath(import.meta.url));

const fnv = s => { let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; } return h; };
// ---------- ntfy への通知（Xの投稿画面を開くリンク付き） ----------
const NTFY = process.env.NTFY_TOPIC;
function postText(m) {
  const url = SITE + '/?c=' + m.id;
  if (m.result === 'win') return { title: `王座交代：第${m.reignNo + 1}代王者 ${m.ch.name}`, url,
    text: `【王座交代】${m.ch.name}が王者${m.cp.name}を下し、第${m.reignNo + 1}代王者に。（${m.how}）\n${m.cp.name}は防衛${m.defenses}回で陥落。\n#百科拳典` };
  if (m.result === 'lose' && m.defenses > 0 && m.defenses % 5 === 0) return { title: `${m.cp.name}、${m.defenses}度目の防衛`, url,
    text: `【防衛${m.defenses}回】王者${m.cp.name}、${m.ch.name}を退けて${m.defenses}度目の防衛。（${m.how}）\n#百科拳典` };
  return null;
}
async function notify(m) {
  const p = NTFY && postText(m); if (!p) return;
  const intent = 'https://x.com/intent/post?text=' + encodeURIComponent(p.text) + '&url=' + encodeURIComponent(p.url);
  const r = await fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
    topic: NTFY, title: p.title, message: p.text + '\n\nタップするとXの投稿画面が開きます', tags: ['crown'],
    click: intent, attach: SITE + '/og/c/' + m.id + '.jpg', filename: 'hyakkakenten-' + m.id + '.jpg',
    actions: [{ action: 'view', label: 'Xで投稿', url: intent, clear: true }, { action: 'view', label: '試合を見る', url: p.url }] }) });
  console.log('  通知', r.status);
}

const pending = () => fetch(SITE + '/api/og/pending', { headers: AUTH }).then(r => r.json());
if (process.env.NOTIFY_TEST === '1') {   // 通知の試し送り：いちばん新しい王座交代を使う
  const t = await fetch(SITE + '/api/throne').then(r => r.json());
  const last = t.recent.find(x => x.result === 'win'); if (!last) { console.log('王座交代の記録がありません'); process.exit(0); }
  const x = await fetch(SITE + '/api/challenge/' + last.id).then(r => r.json());
  await notify({ id: x.id, reignNo: x.reignNo, result: 'win', how: x.how, defenses: x.champ.defenses, ch: { name: x.challenger.display }, cp: { name: x.champ.display } });
  process.exit(0);
}
let pend = await pending();
if (!pend.items) { console.error('一覧を取れませんでした', pend); process.exit(1); }
if (!pend.items.length) { console.log('作る画像はありません'); process.exit(0); }

const meta = await fetch(SITE + '/data/meta.json').then(r => r.json());
const buckets = {};
async function stats(title) {   // 記事の能力値（HP・攻撃・防御・速さ）。収録から外れていれば null
  const k = fnv(title) % meta.nb;
  if (!buckets[k]) { const r = await fetch(`${SITE}/data/a/${k}.json.gz?v=${meta.build || meta.asof}`); buckets[k] = r.ok ? JSON.parse(gunzipSync(Buffer.from(await r.arrayBuffer())).toString()) : {}; }
  const rec = buckets[k][title]; return rec ? rec.f[3] : null;
}

const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : { channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
await page.goto('file://' + path.join(HERE, 'card.html'));
let done = 0, total = 0;
for (let round = 0; round < 20 && pend.items && pend.items.length; round++, pend = await pending()) {   // 一覧は30件ずつ。なくなるまで繰り返す
 total += pend.items.length; let ok = 0;
 for (const m of pend.items.reverse()) {
  m.ch.st = await stats(m.ch.title); m.cp.st = await stats(m.cp.title);
  await page.evaluate(x => { delete document.body.dataset.ready; window.draw(x); }, m);
  await page.waitForSelector('body[data-ready]'); await page.waitForTimeout(150);
  const img = await page.screenshot({ type: 'jpeg', quality: 88 });
  const r = await fetch(SITE + '/api/og/' + m.id, { method: 'PUT', headers: { ...AUTH, 'Content-Type': 'image/jpeg' }, body: img });
  console.log(m.id, m.ch.name, 'vs', m.cp.name, r.status, img.length + 'B'); if (r.ok) { done++; ok++; await notify(m).catch(e => console.log('  通知に失敗', String(e))); }
 }
 if (!ok) break;   // 1枚も預けられなかったら、同じものを繰り返さない
}
await browser.close();
console.log(`${done}/${total} 枚を預けました`);
