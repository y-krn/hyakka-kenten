// 「この辺が舞台の作品」の索引を作る（日本語版Wikipediaの「○○を舞台とした作品」カテゴリから）
//   Category:日本を舞台とした作品 から下へたどり、「○○を舞台とした…」の○○を舞台の土地とみなす
//   土地の名前は Wikipedia の記事名にそろえる（転送をたどる。例：東京都港区 → 港区 (東京都)）
//   data/st/p/<番号>.json.gz … 土地（記事名）ごとに、そこが舞台の作品（よく読まれている順）。番号は記事名のFNVハッシュ % NB
//   data/st/geo.json.gz      … 市区町村・都道府県でない土地（湘南・浅草・下北沢など）のうち、記事に位置があるもの [記事名, 緯度, 経度]
//   data/st/meta.json        … { nb }
//   市区町村・都道府県は、ページ側で現在地の所在地（Wikidata P131）をたどって引く。それ以外の土地は、位置から近いものを引く
//   収録していない記事・確認中の記事は入れない。「警視庁」「江戸」「○○時代」「日本各地」など、場所として拾えない舞台は外す
//   使い方: node tools/build_stage.mjs   （Wikipedia に問い合わせるので、ワークフロー「舞台の索引を作る」で動かす）
import { readFileSync, readdirSync, writeFileSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import { gunzipSync, gzipSync } from 'node:zlib';
const UA = 'hyakka-kenten-build (+https://github.com/y-krn/hyakka-kenten)';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const NB = 64;
const fnv = s => { let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; } return h >>> 0; };   // ページ側の fnv と同じ
// 収録データ（確認中は除く。対戦に戻した記事 data/unhold.json は入れる）
const U = existsSync('data/unhold.json') ? JSON.parse(readFileSync('data/unhold.json', 'utf8')) : {};
const key = why => String(why).replace(/（[^（）]*年[^（）]*）$/, '');
const IN = new Map();
for (const f of readdirSync('data/a')) { const B = JSON.parse(gunzipSync(readFileSync('data/a/' + f)));
  for (const [t, r] of Object.entries(B)) {
    if (r.hold && !((U['記事'] || {})[t] || (U['理由'] || {})[key(r.hold)])) continue;
    const m = (r.ext || []).find(e => e[0] === '_m'); IN.set(t, m ? m[5] || 0 : 0); } }
console.log('収録', IN.size);
async function api(p) { for (let tr = 0; tr < 6; tr++) { try { const j = await (await fetch('https://ja.wikipedia.org/w/api.php?' + new URLSearchParams({ format: 'json', ...p }), { headers: { 'User-Agent': UA } })).json(); if (!j.error) return j; } catch (_) {} await sleep(3000 * (tr + 1)); } throw new Error('Wikipedia に問い合わせられない'); }
async function members(cat) { const out = []; let cont = {};
  do { const j = await api({ action: 'query', list: 'categorymembers', cmtitle: cat, cmlimit: 'max', cmnamespace: '0|14', ...cont }); out.push(...((j.query || {}).categorymembers || [])); cont = j.continue || null; await sleep(80); } while (cont);
  return out; }
// 1. カテゴリをたどる
const ROOT = 'Category:日本を舞台とした作品';
const NOPLACE = /^(日本|日本各地|警視庁|江戸|幕末|京都|大阪|関東地方|関西地方|近畿地方|東北地方|九州|九州地方|四国|四国地方|中国地方|北陸地方|中部地方|東海地方|甲信越地方|北海道地方|山陰地方|山陽地方|南関東|北関東|首都圏|.*時代.*|.*の日本|.*期|.*戦争|.*の歴史|.*の学校|.*大学)$/;
const seen = new Set([ROOT]), RAW = new Map();   // 土地の名前 → Set(作品)
const q = [[ROOT, 0]];
while (q.length) { const [cat, d] = q.shift(); const m = await members(cat);
  const pm = cat.replace(/^Category:/, '').match(/^(.+?)を舞台とした/); const place = pm && !NOPLACE.test(pm[1]) ? pm[1] : null;
  for (const x of m) { if (x.ns === 14) { if (!seen.has(x.title) && d < 6) { seen.add(x.title); q.push([x.title, d + 1]); } }
    else if (place && IN.has(x.title)) (RAW.get(place) || RAW.set(place, new Set()).get(place)).add(x.title); } }
console.log('カテゴリ', seen.size, '土地', RAW.size);
// 2. 土地の名前を記事名にそろえ、位置を取る
const ALIAS = { '東京': '東京都' };
const names = [...RAW.keys()]; const NORM = {}, COORD = {};
for (let i = 0; i < names.length; i += 50) { const part = names.slice(i, i + 50).map(n => ALIAS[n] || n);
  const j = await api({ action: 'query', titles: part.join('|'), redirects: 1, prop: 'coordinates|pageprops', ppprop: 'disambiguation', colimit: 'max' });
  const qq = j.query || {}; const mp = {}; for (const r of [...(qq.normalized || []), ...(qq.redirects || [])]) mp[r.from] = r.to;
  const pages = Object.values(qq.pages || {});
  for (const [k, n] of names.slice(i, i + 50).entries()) { let t = part[k]; for (let s = 0; s < 3 && mp[t]; s++) t = mp[t];
    const pg = pages.find(p => p.title === t); if (!pg || pg.missing !== undefined || (pg.pageprops && pg.pageprops.disambiguation !== undefined)) continue;
    NORM[n] = t; if (pg.coordinates && pg.coordinates[0]) COORD[t] = [+pg.coordinates[0].lat.toFixed(4), +pg.coordinates[0].lon.toFixed(4)]; }
  await sleep(100); }
const PREF = new Set('北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県'.split(' '));
const ADMIN = t => PREF.has(t) || /[市区町村郡]( \([^()]+\))?$/.test(t);
// 3. 索引にする
const P = {}; let nw = 0;
for (const [n, s] of RAW) { const t = NORM[n]; if (!t) continue; if (!ADMIN(t) && !COORD[t]) continue;   // 市区町村・都道府県でもなく位置もない土地は引けない
  const set = P[t] || (P[t] = new Set()); for (const w of s) if (w !== t) set.add(w); }
const W = new Set(); for (const s of Object.values(P)) for (const w of s) W.add(w);
rmSync('data/st', { recursive: true, force: true }); mkdirSync('data/st/p', { recursive: true });
const SH = Array.from({ length: NB }, () => ({}));
for (const [t, s] of Object.entries(P)) { if (!s.size) continue; SH[fnv(t) % NB][t] = [...s].sort((a, b) => IN.get(b) - IN.get(a)); }
SH.forEach((o, i) => writeFileSync(`data/st/p/${i}.json.gz`, gzipSync(JSON.stringify(o))));
const GEO = Object.keys(P).filter(t => P[t].size && !ADMIN(t) && COORD[t]).map(t => [t, ...COORD[t]]);
writeFileSync('data/st/geo.json.gz', gzipSync(JSON.stringify(GEO)));
writeFileSync('data/st/meta.json', JSON.stringify({ nb: NB }));
console.log('索引の土地', Object.values(P).filter(s => s.size).length, '（位置で引く土地', GEO.length, '）作品', W.size);
for (const t of ['湘南', '神奈川県', '浅草', '葛飾区', '沼津市', '下北沢', '静岡市', '鎌倉市']) console.log(t, P[t] ? [...P[t]].length : '-', P[t] ? [...P[t]].slice(0, 5).join('、') : '', COORD[t] || '');
