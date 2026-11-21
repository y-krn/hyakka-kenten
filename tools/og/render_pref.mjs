// 都道府県を応援の共有画像を47枚作る：node render_pref.mjs <roster.json> <出力フォルダ>
//   出力は NN.jpg（NN は都道府県の並びの番号 00〜46。北海道が00）
import { chromium } from 'playwright-core';
import fs from 'node:fs'; import path from 'node:path'; import { fileURLToPath, pathToFileURL } from 'node:url';
const PREFS = '北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県'.split(' ');
const [, , rosterPath, outDir] = process.argv; const R = JSON.parse(fs.readFileSync(rosterPath, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });
const here = path.dirname(fileURLToPath(import.meta.url));
const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : { channel: 'chrome' }); const p = await b.newPage({ viewport: { width: 1200, height: 630 } });   // Actions では入っている Chrome を使う
for (const [i, P] of PREFS.entries()) {
  await p.goto(pathToFileURL(path.join(here, 'pref.html')).href);
  await p.evaluate(([P, r]) => window.draw(P, r), [P, R[P] || {}]);
  await p.waitForSelector('body[data-ready]');
  await p.screenshot({ path: path.join(outDir, String(i).padStart(2, '0') + '.jpg'), type: 'jpeg', quality: 82, clip: { x: 0, y: 0, width: 1200, height: 630 } });
}
await b.close();
