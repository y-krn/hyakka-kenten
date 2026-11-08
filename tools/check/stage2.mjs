// 調査用：日本語版Wikipediaの「○○を舞台とした作品」カテゴリで、拾える作品がどれくらいあるかを数える
//   Wikidata の「作品の舞台」は日本の作品に少ないので、カテゴリのほうを調べる
//   Category:日本を舞台とした作品 から下へたどり、「○○を舞台とした…」の○○を舞台の土地とみなす
import { readFileSync, readdirSync, appendFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
const UA = 'hyakka-kenten-check (+https://github.com/y-krn)';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const IN = new Map();
for (const f of readdirSync('data/a')) { const B = JSON.parse(gunzipSync(readFileSync('data/a/' + f)));
  for (const [t, r] of Object.entries(B)) { if (r.hold) continue; const m = (r.ext || []).find(e => e[0] === '_m'); IN.set(t, m ? m[5] || 0 : 0); } }
async function api(p) { for (let tr = 0; tr < 5; tr++) { try { const j = await (await fetch('https://ja.wikipedia.org/w/api.php?' + new URLSearchParams({ format: 'json', ...p }), { headers: { 'User-Agent': UA } })).json(); if (!j.error) return j; } catch (_) {} await sleep(3000 * (tr + 1)); } return {}; }
async function members(cat) { const out = []; let cont = {};
  do { const j = await api({ action: 'query', list: 'categorymembers', cmtitle: cat, cmlimit: 'max', cmnamespace: '0|14', ...cont }); out.push(...((j.query || {}).categorymembers || [])); cont = j.continue || null; await sleep(100); } while (cont);
  return out; }
const ROOT = 'Category:日本を舞台とした作品', DEPTH = +(process.env.N || 6);
const seen = new Set([ROOT]), WORK = new Map(), PLACE = {};   // 作品 → Set(土地)、土地 → カテゴリ数
let q = [[ROOT, 0]];
while (q.length) { const [cat, d] = q.shift(); const m = await members(cat);
  const pm = cat.replace(/^Category:/, '').match(/^(.+?)を舞台とした/); const place = pm ? pm[1] : null;
  if (place) PLACE[place] = (PLACE[place] || 0) + 1;
  for (const x of m) { if (x.ns === 14) { if (!seen.has(x.title) && d < DEPTH) { seen.add(x.title); q.push([x.title, d + 1]); } }
    else if (place && IN.has(x.title)) { (WORK.get(x.title) || WORK.set(x.title, new Set()).get(x.title)).add(place); } } }
console.log('カテゴリ', seen.size, '作品', WORK.size);
// 土地の細かさ：都道府県・「日本」「東京」などの広い名前と、それより細かい土地に分ける
const PREF = new Set('北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県 東京 京都 大阪'.split(' '));
const WIDE = /^(日本|関東地方|関西地方|近畿地方|東北地方|九州|四国|中国地方|北陸地方|中部地方|東海地方|北海道地方|.*時代|.*の歴史)$/;
const kind = p => WIDE.test(p) ? '広い地域・時代' : PREF.has(p) ? '都道府県' : '市区町村・それより細かい土地';
const by = {}; for (const [t, s] of WORK) { const ks = [...s].map(kind); const k = ['市区町村・それより細かい土地', '都道府県', '広い地域・時代'].find(x => ks.includes(x)); (by[k] ||= []).push([t, [...s].filter(p => kind(p) === k)]); }
const out = [`# 「○○を舞台とした作品」カテゴリ：収録作品 ${WORK.size}（たどったカテゴリ ${seen.size}）`, ''];
for (const k of ['市区町村・それより細かい土地', '都道府県', '広い地域・時代']) { const a = (by[k] || []).sort((x, y) => IN.get(y[0]) - IN.get(x[0]));
  out.push(`- **${k}**（${a.length}）：` + a.slice(0, 25).map(([t, p]) => `${t}〔${p.slice(0, 2).join('・')}〕`).join('、')); }
const look = ['SLAM DUNK', 'らき☆すた', 'こちら葛飾区亀有公園前派出所', 'ラブライブ!サンシャイン!!', '男はつらいよ', '伊豆の踊子', 'ちびまる子ちゃん', '名探偵コナン', '君の名は。', 'クレヨンしんちゃん', 'ぼっち・ざ・ろっく!', '涼宮ハルヒの憂鬱', 'けいおん!', 'あの日見た花の名前を僕達はまだ知らない。', 'ゆるキャン△', '鎌倉殿の13人', 'ハイキュー!!', '呪術廻戦', '東京リベンジャーズ', '孤独のグルメ'];
out.push('', '## 気になる作品', ...look.map(t => `- ${t}：` + (WORK.has(t) ? [...WORK.get(t)].join('、') : IN.has(t) ? '収録あり・カテゴリなし' : '収録なし')));
out.push('', '## 作品の多い土地（細かい土地）', Object.entries([...WORK.values()].flatMap(s => [...s]).filter(p => kind(p) === '市区町村・それより細かい土地').reduce((o, p) => (o[p] = (o[p] || 0) + 1, o), {})).sort((a, b) => b[1] - a[1]).slice(0, 40).map(([p, n]) => `${p}:${n}`).join('、'));
console.log(out.join('\n')); if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, out.join('\n') + '\n');
