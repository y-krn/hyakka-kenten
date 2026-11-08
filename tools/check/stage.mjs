// 調査用：「作品の舞台」（Wikidata P840）で拾える作品がどれくらいあるかを数える
//   舞台に座標があれば「近くで探す」で見つけられる。座標がなくても、日本の市区町村なら「ゆかりの人」と同じ形で出せる
//   収録している作品（data/a にあり、確認中でない）だけを数える。手元では Wikidata に届かないので、調査ワークフローで動かす
import { readFileSync, readdirSync, appendFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
const UA = 'hyakka-kenten-check (+https://github.com/y-krn)';
const IN = new Map();
for (const f of readdirSync('data/a')) { const B = JSON.parse(gunzipSync(readFileSync('data/a/' + f)));
  for (const [t, r] of Object.entries(B)) { if (r.hold) continue; const m = (r.ext || []).find(e => e[0] === '_m'); IN.set(t, m ? m[5] || 0 : 0); } }
console.log('収録', IN.size);
const Q = `SELECT ?w ?wt ?p WHERE { ?w wdt:P840 ?p. ?wa schema:about ?w; schema:isPartOf <https://ja.wikipedia.org/>; schema:name ?wt. }`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
let rows = null;
for (let tr = 0; tr < 4 && !rows; tr++) {
  try { const r = await fetch('https://query.wikidata.org/sparql', { method: 'POST', headers: { 'User-Agent': UA, Accept: 'application/sparql-results+json', 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ query: Q }) });
    const tx = await r.text(); rows = JSON.parse(tx).results.bindings; } catch (e) { console.log('失敗', tr, String(e).slice(0, 200)); await sleep(20000); } }
if (!rows) process.exit(1);
rows = rows.filter(b => IN.has(b.wt.value));
// 舞台の場所の情報（日本語版の記事名・座標・国・種類）は wbgetentities で50件ずつ
const PL = {}; const ids = [...new Set(rows.map(b => b.p.value.split('/').pop()))]; console.log('舞台の場所', ids.length);
const vals = (c, p) => ((c[p] || []).filter(s => s.rank !== 'deprecated').map(s => s.mainsnak.datavalue && s.mainsnak.datavalue.value).filter(Boolean));
for (let i = 0; i < ids.length; i += 50) { const part = ids.slice(i, i + 50);
  for (let tr = 0; tr < 5; tr++) { try { const d = await (await fetch('https://www.wikidata.org/w/api.php?' + new URLSearchParams({ format: 'json', action: 'wbgetentities', ids: part.join('|'), props: 'claims|sitelinks', sitefilter: 'jawiki' }), { headers: { 'User-Agent': UA } })).json();
      for (const [q, e] of Object.entries(d.entities || {})) { const c = e.claims || {};
        PL[q] = { pt: e.sitelinks && e.sitelinks.jawiki ? e.sitelinks.jawiki.title : q, coord: vals(c, 'P625').length > 0, cs: vals(c, 'P17').map(v => v.id), ks: vals(c, 'P31').map(v => v.id) }; } break; }
    catch (e) { await sleep(5000 * (tr + 1)); } }
  await sleep(200); }
rows = rows.map(b => { const q = b.p.value.split('/').pop(), x = PL[q] || { pt: q, coord: false, cs: [], ks: [] };
  return { wt: b.wt, p: b.p, pt: { value: x.pt }, coord: x.coord || undefined, cs: { value: x.cs.join(',') }, ks: { value: x.ks.join(',') } }; });
console.log('舞台の行', rows.length);
const MUNI = new Set(['Q494721', 'Q1059478', 'Q4174776', 'Q5327704', 'Q1137833', 'Q1196035', 'Q1749269', 'Q134390', 'Q15710360']);
const PREF = new Set(['Q50337']);
const W = new Map(); const CLS = {};   // 作品 → {pv, places:[{pt, kind}]}
for (const b of rows) { const wt = b.wt.value; if (!IN.has(wt)) continue;
  const pid = b.p.value.split('/').pop(), cs = (b.cs.value || '').split(',').filter(Boolean), ks = (b.ks.value || '').split(',').filter(Boolean);
  const jp = cs.includes('Q17') || pid === 'Q17';
  let kind = pid === 'Q17' ? '日本全体' : !jp ? (cs.length ? '海外' : (b.coord ? '海外' : '国なし（架空など）')) : ks.some(k => PREF.has(k)) ? '都道府県' : b.coord ? '日本・座標あり' : ks.some(k => MUNI.has(k)) ? '日本・市区町村（座標なし）' : '日本・その他';
  if (jp && pid !== 'Q17') for (const k of ks) CLS[k] = (CLS[k] || 0) + 1;
  const x = W.get(wt) || { pv: IN.get(wt), pl: [] }; x.pl.push({ pt: b.pt ? b.pt.value : pid, kind }); W.set(wt, x); }
const best = x => ['日本・座標あり', '日本・市区町村（座標なし）', '都道府県', '日本・その他', '日本全体', '海外', '国なし（架空など）'].find(k => x.pl.some(p => p.kind === k));
const by = {}; for (const [t, x] of W) (by[best(x)] ||= []).push([t, x]);
const out = [`# 作品の舞台：舞台が書かれた収録作品 ${W.size}`, '', 'いちばん拾いやすい舞台で分けた数と、閲覧数の多い例：', ''];
for (const k of ['日本・座標あり', '日本・市区町村（座標なし）', '都道府県', '日本・その他', '日本全体', '海外', '国なし（架空など）']) { const a = (by[k] || []).sort((p, q) => q[1].pv - p[1].pv);
  out.push(`- **${k}**（${a.length}）：` + a.slice(0, 15).map(([t, x]) => `${t}〔${x.pl.filter(p => p.kind === k).map(p => p.pt).slice(0, 2).join('・')}〕`).join('、')); }
const look = ['SLAM DUNK', 'スラムダンク', 'らき☆すた', '君の名は。', 'ガールズ&パンツァー', 'となりのトトロ', '千と千尋の神隠し', 'ちびまる子ちゃん', 'こちら葛飾区亀有公園前派出所', 'ラブライブ!サンシャイン!!', '男はつらいよ', '坊っちゃん', '伊豆の踊子', 'ONE PIECE', '名探偵コナン'];
out.push('', '## 気になる作品', ...look.map(t => `- ${t}：` + (W.has(t) ? W.get(t).pl.map(p => `${p.pt}（${p.kind}）`).join('、') : IN.has(t) ? '収録あり・舞台なし' : '収録なし')));
out.push('', '## 日本の舞台の種類（P31 の上位）', Object.entries(CLS).sort((a, b) => b[1] - a[1]).slice(0, 25).map(([k, n]) => `${k}:${n}`).join('、'));
console.log(out.join('\n')); if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, out.join('\n') + '\n');
