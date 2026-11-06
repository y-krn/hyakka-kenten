// 調査用：「確認中」（保留）の記事を、保留の理由ごとにまとめて一覧にする（data/unhold.json で戻す記事を決めるため）
//   理由は年の括弧を除いてまとめる（unhold.json の「理由」に書く形と同じ）。理由ごとに、記事数と、閲覧数の多い記事を出す
//   手元でも動く：node tools/check/holds.mjs [理由ごとに出す記事数（既定 8）]
import { readFileSync, readdirSync, existsSync, appendFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
const K = +(process.argv[2] || 8);
const U = existsSync('data/unhold.json') ? JSON.parse(readFileSync('data/unhold.json', 'utf8')) : {};
const key = why => String(why).replace(/（[^（）]*年[^（）]*）$/, '');
const G = {}; let n = 0, back = 0;
for (const f of readdirSync('data/a')) { const B = JSON.parse(gunzipSync(readFileSync('data/a/' + f)));
  for (const [t, r] of Object.entries(B)) { if (!r.hold) continue; n++;
    if ((U['記事'] || {})[t] || (U['理由'] || {})[key(r.hold)]) { back++; continue; }
    const m = (r.ext || []).find(e => e[0] === '_m'); (G[key(r.hold)] ||= []).push([t, m ? m[5] || 0 : 0]); } }
const L = Object.entries(G).sort((a, b) => b[1].length - a[1].length);
const out = [`# 確認中の記事：${n} 記事（うち対戦に戻した記事 ${back}）、理由 ${L.length} 種類`, ''];
for (const [why, a] of L) { a.sort((x, y) => y[1] - x[1]);
  out.push(`- ${why}（${a.length}）：` + a.slice(0, K).map(([t, pv]) => `${t}（${pv >= 1e4 ? Math.round(pv / 1e4) + '万' : pv}）`).join('、')); }
console.log(out.join('\n')); if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, out.join('\n') + '\n');
