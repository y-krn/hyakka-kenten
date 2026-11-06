// 「主要作品」（Wikidata の P800）の並べ直し：作品の記事がよく読まれている順に、先頭の2件を選び直す
//   収録データには、作品の先頭2件（Wikidata の登録順）しか入っていない。登録順は有名な順ではないので、
//   よく知られた作品が後ろに隠れることがある（例：井上陽水の「少年時代」は4件目）
//   1. 作品が3件以上ある記事は、Wikidata から作品の全件と日本語の名前・説明を取り寄せる
//   2. 作品の記事の閲覧数（収録データにあるもの。ないものは 0）の多い順に並べ、同じなら登録順
//   3. 先頭2件がいまと違う記事だけを「WK」で始まる行に出す（tools/fixa_build.py に渡すと、自動の訂正表に入る）
import { readFileSync, readdirSync, appendFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
const UA = 'hyakka-kenten-works (+https://github.com/y-krn)';
let FAIL = 0;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const PV = {}; const L = [];
for (const f of readdirSync('data/a')) { const B = JSON.parse(gunzipSync(readFileSync('data/a/' + f)));
  for (const [t, r] of Object.entries(B)) { const m = (r.ext || []).find(e => e[0] === '_m'); PV[r.f[2]] = m ? m[5] || 0 : 0;
    const p = (r.ext || []).find(e => e[0] === 'P800'); if (p) L.push({ t, q: r.f[2], n: p[1], it: p[2] }); } }
async function api(params) {
  const u = 'https://www.wikidata.org/w/api.php?' + new URLSearchParams({ format: 'json', ...params });
  for (let tr = 0; tr < 5; tr++) { let why = '';
    try { const res = await fetch(u, { headers: { 'User-Agent': UA, 'Api-User-Agent': UA } }); const tx = await res.text();
      try { const j = JSON.parse(tx); if (!j.error) return j; why = res.status + ' ' + JSON.stringify(j.error).slice(0, 200); } catch (_) { why = res.status + ' ' + tx.slice(0, 200); } }
    catch (e) { why = String(e).slice(0, 200); }
    if (FAIL++ < 10) console.log('失敗', tr, why);   // 失敗の理由を最初の10回だけ出す
    await sleep(5000 * (tr + 1)); }
  return null;
}
// 1. 作品が3件以上ある記事：作品の全件
const many = L.filter(x => x.n > 2).slice(0, +(process.env.N || 1e9)); const full = {};
console.log('作品が3件以上', many.length);
for (let i = 0; i < many.length; i += 25) {
  if (i % 500 === 0) console.log('作品の全件', i, '/', many.length);
  const d = await api({ action: 'wbgetentities', props: 'claims', ids: many.slice(i, i + 25).map(x => x.q).join('|') });
  if (d) for (const [q, e] of Object.entries(d.entities || {})) full[q] = (((e.claims || {}).P800) || []).filter(c => c.rank !== 'deprecated').map(c => c.mainsnak.datavalue && c.mainsnak.datavalue.value.id).filter(Boolean);
  await sleep(500);
}
// 作品の日本語の名前と説明（まだ知らないものだけ）
const known = {}; for (const x of L) for (const [lab, desc, q] of x.it) known[q] = [lab, desc || '', q];
const need = [...new Set(Object.values(full).flat())].filter(q => !known[q]); console.log('名前を取り寄せる作品', need.length);
for (let i = 0; i < need.length; i += 50) {
  const d = await api({ action: 'wbgetentities', props: 'labels|descriptions', languages: 'ja', ids: need.slice(i, i + 50).join('|') });
  if (d) for (const [q, e] of Object.entries(d.entities || {})) { const lab = e.labels && e.labels.ja && e.labels.ja.value; if (lab) known[q] = [lab, (e.descriptions && e.descriptions.ja && e.descriptions.ja.value) || '', q]; }
  await sleep(500);
}
// 2・3. 並べ直して、先頭2件が変わるものだけ出す（日本語の名前がない作品は使わない）
let changed = 0;
for (const x of L) {
  const ids = x.n > 2 && full[x.q] ? full[x.q] : x.it.map(w => w[2]);
  const ws = ids.map((q, k) => ({ q, k, pv: PV[q] || 0 })).filter(w => known[w.q]).sort((a, b) => b.pv - a.pv || a.k - b.k).map(w => known[w.q]).filter((w, i, a) => a.findIndex(v => v[0] === w[0]) === i).slice(0, 2);   // 同じ名前の作品（番組の別の版など）は1つだけ
  if (!ws.length || ws.map(w => w[2]).join() === x.it.map(w => w[2]).join()) continue;
  changed++; console.log('WK\t' + JSON.stringify({ t: x.t, it: ws }));
}
const M = `# 主要作品の並べ直し：主要作品のある ${L.length} 記事のうち、${changed} 記事で先頭の2件が変わる（作品が3件以上：${many.length} 記事）`;
console.log(M); if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, M + '\n');
