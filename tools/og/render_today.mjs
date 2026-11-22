// 今日の一戦の共有画像を作って、サーバーに預ける（GitHub Actions から毎日0時すぎに動かす）
//   組み合わせはページと同じ計算で決めたいので、実際のページをブラウザで開いて、ページの TD（今日の一戦）を読む
//   環境変数: SITE（既定 https://hyakkakenten.com）, ADMIN_TOKEN, CHROME（省略時はインストール済みの Chrome）
//   ページに「今日の一戦」がまだないときは、何もしない
import { chromium } from 'playwright-core';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const SITE = process.env.SITE || 'https://hyakkakenten.com';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : { channel: 'chrome' });
const page = await browser.newPage();
await page.goto(SITE + '/?nostat=1', { waitUntil: 'domcontentloaded' });
if (!(await page.$('#today'))) { console.log('このページには「今日の一戦」がありません。何もしません'); await browser.close(); process.exit(0); }
const ok = await page.waitForFunction(() => typeof TD !== 'undefined' && TD && TD.day, null, { timeout: 60000 }).then(() => true).catch(() => false);
if (!ok) { console.error('今日の一戦の組み合わせが決まりませんでした（ページの読み込みに失敗？）'); await browser.close(); process.exit(1); }
// 記事の短い説明（「日本のプロ野球選手」など）は、ページの今日の一戦の枠に出ているものを使う（読み込みを少し待つ）
await page.waitForFunction(() => [...document.querySelectorAll('#today b')].filter(b => b.nextElementSibling && b.nextElementSibling.tagName === 'A' && b.nextElementSibling.textContent.trim()).length >= 2, null, { timeout: 15000 }).catch(() => {});
const M = await page.evaluate(() => {
  const qs = [...document.querySelectorAll('#today b')].map(b => b.nextElementSibling && b.nextElementSibling.tagName === 'A' ? b.nextElementSibling.textContent.trim() : '');
  const mv = (x, y) => { try { return [...new Set(pickMoves(x, y).map(m => m[8] || m[1]))]; } catch (_) { return []; } };
  const one = (x, y, q) => ({ name: F[x][0], title: F[x][1], q: q || '', mv: mv(x, y) });
  return { day: TD.day, a: one(TD.a, TD.b, qs[0]), b: one(TD.b, TD.a, qs[1]) };
});
console.log(M.day, M.a.name, 'vs', M.b.name, M.a.mv.join('・'), '/', M.b.mv.join('・'));
const card = await browser.newPage({ viewport: { width: 1200, height: 630 } });
await card.goto('file://' + path.join(HERE, 'today.html'));
await card.evaluate(x => window.draw(x), M);
await card.waitForSelector('body[data-ready]'); await card.waitForTimeout(150);
const img = await card.screenshot({ type: 'jpeg', quality: 88 });
await browser.close();
if (process.env.OUT) { (await import('node:fs')).writeFileSync(process.env.OUT, img); console.log('保存', process.env.OUT); }
if (!process.env.ADMIN_TOKEN) { console.log('ADMIN_TOKEN がないので、預けません'); process.exit(0); }
const q = new URLSearchParams({ a: M.a.name, b: M.b.name });
const r = await fetch(SITE + '/api/og/today/' + M.day + '?' + q, { method: 'PUT', headers: { Authorization: 'Bearer ' + process.env.ADMIN_TOKEN, 'Content-Type': 'image/jpeg' }, body: img });
console.log('預けた', r.status, img.length + 'B', await r.text());
if (!r.ok) process.exit(1);
