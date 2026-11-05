// 調査用：2段書きの情報欄の点検
//   自動の訂正表（data/fixa）で日本語版に合わせた数字のうち、Wikidata と2倍以上違うものについて、
//   日本語版の情報欄の「同じ種類の別の段」（市街地・都市圏・陸地面積・車体長など）に Wikidata とほぼ同じ値があるかを調べる
//   あれば「1段目が誤りか、定義の違い」の候補として出す（照合だけ。何も書き換えない）。結果は Summary と「TT」で始まる行
import { readFileSync, readdirSync, appendFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
process.env.NUMCHECK_LIB = '1';
const { readNum, params } = await import('./numcheck.mjs');
const UA = 'hyakka-kenten-numcheck (+https://github.com/y-krn)';
const LAB = { e: '標高', h: '高さ', m: '重さ', a: '面積', p: '人口', l: '長さ', d: '深さ', s: '速さ' };
const KEY = Object.fromEntries(Object.entries(LAB).map(([k, v]) => [v, k]));
const FAM = { a: /面積|area/i, p: /人口|population/i, l: /全長|延長|長さ|length|距離/i, h: /高さ|全高|height|身長/i, s: /速度|速力|speed/i, e: /標高|elevation/i, m: /重量|質量|weight|mass|体重/i, d: /深/ };
const NOT = /順位|大きさ|密度|率|統計年|時点|備考|年|rank|density|note|footnote|ref|ft|mi|sq|imperial|dunam|acre|_as_of|date/i;
const DEF = { a: 'km2', p: '', l: 'km?', h: 'm', s: 'km/h?', e: 'm', m: 'kg?', d: 'm' };
// 候補：fixa の値と、収録の値（Wikidata）
const FA = {}; for (const f of readdirSync('data/fixa')) Object.assign(FA, JSON.parse(readFileSync('data/fixa/' + f, 'utf8')));
const meta = JSON.parse(readFileSync('data/meta.json')); const NB = meta.nb;
const fnv = t => { let h = 0x811c9dc5; for (let k = 0; k < t.length; k++) { h ^= t.charCodeAt(k); h = Math.imul(h, 0x01000193) >>> 0; } return h >>> 0; };
const byB = {}; for (const t of Object.keys(FA)) (byB[fnv(t) % NB] ||= []).push(t);
const QT = {}; for (const [b, ts] of Object.entries(byB)) { const B = JSON.parse(gunzipSync(readFileSync(`data/a/${b}.json.gz`))); for (const t of ts) QT[t] = (B[t] && B[t].qt) || {}; }   // 区画ごとに1回だけ読む（全部を覚えておくとメモリが足りない）
const C = [];
for (const [t, o] of Object.entries(FA)) for (const [lab, jp] of Object.entries(o)) { const k = KEY[lab]; const wd = QT[t][k]; if (!(wd > 0 && jp > 0)) continue; const ratio = Math.max(wd / jp, jp / wd); if (ratio >= 2) C.push({ t, k, wd, jp, ratio }); }
console.log('候補', C.length);
const titles = [...new Set(C.map(c => c.t))]; const WT = {}; const sleep = ms => new Promise(r => setTimeout(r, ms));
for (let i = 0; i < titles.length; i += 20) {
  const u = 'https://ja.wikipedia.org/w/api.php?' + new URLSearchParams({ action: 'query', format: 'json', formatversion: 2, prop: 'revisions', rvprop: 'content', rvslots: 'main', rvsection: 0, redirects: 1, maxlag: 5, titles: titles.slice(i, i + 20).join('|') });
  let d = null; for (let tr = 0; tr < 5 && !d; tr++) { try { const j = await (await fetch(u, { headers: { 'Api-User-Agent': UA, 'User-Agent': UA } })).json(); if (j.error) { await sleep(5000); continue; } d = j; } catch (_) { await sleep(5000); } }
  if (!d) continue;
  const back = {}; for (const x of [...(d.query.normalized || []), ...(d.query.redirects || [])]) back[x.to] = back[x.from] || x.from;
  for (const p of d.query.pages) WT[back[p.title] || p.title] = p.revisions ? p.revisions[0].slots.main.content : '';
  await sleep(1000);
}
const out = [];
for (const c of C) {
  const P = params(WT[c.t] || '').filter(([n]) => FAM[c.k].test(n) && !NOT.test(n));
  const vals = P.map(([n, v]) => { const r = readNum(v, c.k, n.includes('ha') ? 'ha' : DEF[c.k]); return r && !r.unsure ? { n, v: r.n, raw: r.raw } : null; }).filter(Boolean);
  const hit = vals.find(x => Math.abs(x.v - c.wd) / c.wd <= 0.05 && Math.abs(x.v - c.jp) / c.jp > 0.05);
  const r = { ...c, ratio: +c.ratio.toFixed(2), rows: vals.map(x => `${x.n}=${+x.v.toPrecision(6)}`).join(' ／ '), other: hit ? `${hit.n}=${hit.raw}` : null };
  out.push(r); console.log('TT\t' + JSON.stringify(r));
}
const H = out.filter(r => r.other);
const c = s => String(s ?? '').replace(/\|/g, '／');
const M = [`# 2段書きの情報欄の点検（候補 ${C.length} 項目・${titles.length} 記事）`, '', `## 別の段に Wikidata とほぼ同じ値があるもの ${H.length}件`, '', '| 記事 | 項目 | 使っている値（日本語版1段目） | Wikidata | 別の段 |', '|---|---|---|---|---|'];
for (const r of H) M.push(`| ${c(r.t)} | ${LAB[r.k]} | ${r.jp} | ${r.wd} | ${c(r.other)} |`);
if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, M.join('\n') + '\n');
console.log(M.slice(0, 4).join('\n'));
