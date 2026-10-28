// 王座戦の共有画像を作って、サーバーに預ける（GitHub Actions から動かす）
//   環境変数: SITE（既定 https://hyakkakenten.com）, ADMIN_TOKEN, CHROME（使うブラウザ。省略時はインストール済みの Chrome）
import { chromium } from 'playwright-core';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const SITE = process.env.SITE || 'https://hyakkakenten.com';
const AUTH = { Authorization: 'Bearer ' + process.env.ADMIN_TOKEN };
const HERE = path.dirname(fileURLToPath(import.meta.url));

const fnv = s => { let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; } return h; };
const pend = await fetch(SITE + '/api/og/pending', { headers: AUTH }).then(r => r.json());
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
let done = 0;
for (const m of pend.items.reverse()) {
  m.ch.st = await stats(m.ch.title); m.cp.st = await stats(m.cp.title);
  await page.evaluate(x => { delete document.body.dataset.ready; window.draw(x); }, m);
  await page.waitForSelector('body[data-ready]'); await page.waitForTimeout(150);
  const img = await page.screenshot({ type: 'jpeg', quality: 88 });
  const r = await fetch(SITE + '/api/og/' + m.id, { method: 'PUT', headers: { ...AUTH, 'Content-Type': 'image/jpeg' }, body: img });
  console.log(m.id, m.ch.name, 'vs', m.cp.name, r.status, img.length + 'B'); if (r.ok) done++;
}
await browser.close();
console.log(`${done}/${pend.items.length} 枚を預けました`);
