// 数字の選び直し：Wikidata に同じ数字（人口・面積など）が複数あるとき、いちばん新しい時点の値を使う
//   収録データは、複数の値のうち最大のものを使っていた（例：人口がいちばん多かった年の値）。
//   値に「時点」（P585）が付いているものがあれば、いちばん新しい時点の値に選び直す（同じ時点が複数なら大きいほう）。
//   使うのは人口と面積で、時点が2000年以降のものだけ（tools/fixa_build.py で絞る）。昔の国の人口や記録の体重などは、最大の値のほうがふさわしい
//   時点の付いた値がなければ、いままでどおり最大の値。「優先」の印が付いた値があれば、その中から選ぶ（いままでと同じ）
//   収録の値と違う記事だけを「LT」で始まる行に出す（tools/fixa_build.py に渡すと、自動の訂正表に入る）
//   OFFSET / N で範囲を区切れる（数字のある記事を題名の順に並べたときの位置）
import { readFileSync, readdirSync, appendFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
const UA = 'hyakka-kenten-latest (+https://github.com/y-krn)';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const LEN = { Q11573: 1, Q828224: 1000, Q174728: 0.01, Q174789: 0.001, Q3710: 0.3048, Q218593: 0.0254, Q253276: 1609.344 };
const CONV = { P2067: { Q11570: 1, Q41803: 0.001, Q191118: 1000, Q100995: 0.45359, Q180892: 1.989e30, Q651336: 1.898e27 }, P1082: { '1': 1, Q199: 1 }, P2046: { Q712226: 1, Q25343: 1e-6, Q35852: 0.01, Q706688: 3.3058e-6, Q232291: 2.59 }, P2044: LEN, P2048: LEN, P2043: LEN, P4511: LEN, P2052: { Q180154: 1, Q182429: 3.6, Q211256: 1.609344, Q128822: 1.852 } };
const KP = { h: ['P2048', 1], m: ['P2067', 1], e: ['P2044', 1], a: ['P2046', 1], p: ['P1082', 1], l: ['P2043', 1000], d: ['P4511', 1], s: ['P2052', 1] };
// tools/gen_v2.js の qty と同じ選び方（新しい時点の値を優先）
function qty(c, p) {
  const a = (c[p] || []).filter(s => s.rank !== 'deprecated'); const pr = a.filter(s => s.rank === 'preferred');
  let best = null, bt = null, dated = null;
  for (const s of (pr.length ? pr : a)) { const v = s.mainsnak.datavalue && s.mainsnak.datavalue.value; if (!v || v.amount === undefined) continue;
    const f = CONV[p][(v.unit || '1').split('/').pop()]; if (f === undefined) continue; const x = parseFloat(v.amount) * f;
    const q = s.qualifiers && s.qualifiers.P585 && s.qualifiers.P585[0] && s.qualifiers.P585[0].datavalue; const t = q ? q.value.time : null;
    if (t) { if (dated === null || t > bt || (t === bt && x > dated)) { dated = x; bt = t; } }
    if (best === null || x > best) best = x; }
  return dated !== null ? [dated, bt.slice(1, 11)] : best !== null ? [best, ''] : null;
}
let L = [];
for (const f of readdirSync('data/a')) { const B = JSON.parse(gunzipSync(readFileSync('data/a/' + f)));
  for (const [t, r] of Object.entries(B)) if (r.qt && Object.keys(r.qt).length) L.push({ t, q: r.f[2], qt: r.qt }); }
L.sort((x, y) => x.t < y.t ? -1 : 1); const all = L.length;
L = L.slice(+(process.env.OFFSET || 0), +(process.env.OFFSET || 0) + +(process.env.N || 1e9));
console.log('数字のある記事', all, 'のうち', L.length);
let FAIL = 0;
async function api(params) {
  const u = 'https://www.wikidata.org/w/api.php?' + new URLSearchParams({ format: 'json', ...params });
  for (let tr = 0; tr < 5; tr++) { let why = '';
    try { const res = await fetch(u, { headers: { 'User-Agent': UA, 'Api-User-Agent': UA } }); const tx = await res.text();
      try { const j = JSON.parse(tx); if (!j.error) return j; why = res.status + ' ' + JSON.stringify(j.error).slice(0, 200); } catch (_) { why = res.status + ' ' + tx.slice(0, 200); } }
    catch (e) { why = String(e).slice(0, 200); }
    if (FAIL++ < 10) console.log('失敗', tr, why);
    await sleep(5000 * (tr + 1)); }
  return null;
}
let changed = 0, miss = 0;
for (let i = 0; i < L.length; i += 25) {
  if (i % 2000 === 0) console.log('進み具合', i, '/', L.length);
  const part = L.slice(i, i + 25);
  const d = await api({ action: 'wbgetentities', props: 'claims', ids: part.map(x => x.q).join('|') });
  if (!d) { miss += part.length; continue; }
  for (const x of part) { const e = d.entities && d.entities[x.q]; if (!e || !e.claims) { miss++; continue; }
    for (const [k, old] of Object.entries(x.qt)) { const r = qty(e.claims, KP[k][0]); if (!r) continue;
      const nv = +(r[0] / KP[k][1]).toPrecision(6);
      if (Math.abs(nv - old) / Math.max(Math.abs(old), 1e-12) > 0.001) { changed++; console.log('LT\t' + JSON.stringify({ t: x.t, k, old, lt: nv, at: r[1] })); } } }
  await sleep(300);
}
const M = `# 数字の選び直し：${L.length} 記事を調べて、${changed} 項目で値が変わる（取り寄せられなかった記事：${miss}）`;
console.log(M); if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, M + '\n');
