// 今日の一戦を ntfy に知らせる（タップすると 𝕏 の投稿画面が開く）。GitHub Actions から毎朝動かす
//   組み合わせはページと同じ計算で決めたいので、実際のページをブラウザで開いて、ページの todayPair() を呼ぶ
//   環境変数: SITE（既定 https://hyakkakenten.com）, NTFY_TOPIC, CHROME（省略時はインストール済みの Chrome）
//   ページに「今日の一戦」がまだないとき（公開前）は、何もしない
import { chromium } from 'playwright-core';

const SITE = process.env.SITE || 'https://hyakkakenten.com';
const NTFY = process.env.NTFY_TOPIC;
const DISC = '※Wikipediaの記述をもとにした架空の試合です。実在の国・団体・人物の優劣を示すものではありません';

const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : { channel: 'chrome' });
const page = await browser.newPage();
await page.goto(SITE + '/', { waitUntil: 'domcontentloaded' });
// 「今日の一戦」の枠は、組み合わせが決まる前から「準備中」として出ているので、枠ではなく組み合わせ（TD）が決まるのを待つ
if (!(await page.$('#today'))) { console.log('このページには「今日の一戦」がありません（公開前？）。何もしません'); await browser.close(); process.exit(0); }
const ok = await page.waitForFunction(() => typeof TD !== 'undefined' && TD && TD.day, null, { timeout: 60000 }).then(() => true).catch(() => false);
if (!ok) { console.error('今日の一戦の組み合わせが決まりませんでした（ページの読み込みに失敗？）'); await browser.close(); process.exit(1); }
const td = await page.evaluate(() => ({ day: TD.day, a: F[TD.a][0], b: F[TD.b][0] }));
await browser.close();

const md = d => (+d.slice(5, 7)) + '月' + (+d.slice(8, 10)) + '日';
const url = SITE + '/?today=1';
const xlen = s => [...s].reduce((n, c) => n + (c.codePointAt(0) < 0x1100 ? 1 : 2), 0);   // Xの文字数の数え方（URLは別に23）
let lines = [`【百科拳典 今日の一戦 ${md(td.day)}】`, `${td.a} vs ${td.b}`, '人気の記事に、ランダムに選ばれた記事が挑む。どっちが勝つ？ 予想してから観戦しよう', '#百科拳典', DISC];
if (xlen(lines.join('\n')) > 280 - 24) lines.splice(2, 1);   // 長すぎるときは、説明の行を削る
const text = lines.join('\n');
console.log(text);
if (!NTFY) { console.log('NTFY_TOPIC がないので、通知は送りません'); process.exit(0); }
const intent = 'https://x.com/intent/post?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(url);
const r = await fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
  topic: NTFY, title: `今日の一戦：${td.a} vs ${td.b}`, message: text + '\n\nタップするとXの投稿画面が開きます', tags: ['crossed_swords'],
  click: intent, actions: [{ action: 'view', label: 'Xで投稿', url: intent, clear: true }, { action: 'view', label: 'ページを見る', url }] }) });
console.log('通知', r.status);
