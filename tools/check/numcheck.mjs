// 調査用：収録している数字（Wikidata）と、日本語版Wikipediaの記事の情報欄の数字を突き合わせる（照合だけ。何も書き換えない）
//   よく読まれている順に N 記事（環境変数 N、既定 2000）。結果は実行結果ページ（Summary）と numcheck.json に出す
//   Wikipedia への問い合わせは、1回に20記事ずつ、順番に（同時に投げない）。Api-User-Agent に連絡先を入れる
import { readFileSync, readdirSync, writeFileSync, appendFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const N = +(process.env.N || 2000), OUT = process.env.OUT || 'numcheck.json';
const UA = 'hyakka-kenten-numcheck (+https://github.com/y-krn)';
const LAB = { e: '標高', h: '高さ', m: '重さ', a: '面積', p: '人口', l: '長さ', d: '深さ', s: '速さ' };

// ---------- 情報欄から数字を読む ----------
// 項目名（情報欄の引数名）ごとに、どの数字か・既定の単位を決める。上にあるものほど優先
const FIELDS = {
  e: [[/^(標高|標高\s*m|標高\(メートル\)|elevation|elevation_m|最高標高|最高地点標高)$/i, 'm']],
  a: [[/^(面積|総面積|面積値|面積\s*km2|総面積\(平方キロ\)|area|area_km2|area_total_km2|陸地面積)$/i, 'km2'], [/^(面積\s*ha|敷地面積\s*ha)$/i, 'ha']],
  p: [[/^(人口|総人口|人口値|population|population_total)$/i, '']],
  h: [[/^(身長)$/, 'cm?'], [/^(高さ|全高|height|高さ\s*m|塔高|構造物高)$/i, 'm']],
  m: [[/^(体重)$/, 'kg'], [/^(重量|質量|weight|mass|全備重量|自重|空虚重量|打ち上げ時質量|機体質量)$/i, 'kg?']],
  l: [[/^(全長|延長|長さ|length|路線距離|総延長|流路延長|幹川流路延長|全長\s*km|総距離)$/i, 'km?']],
  d: [[/^(最大水深|最大深度|max-depth|max_depth|最深部)$/i, 'm']],
  s: [[/^(最高速度|最大速度|最大速力|速度|速力|最高運転速度|speed|max_speed|最高速)$/i, 'km/h?']],
};
// 中身の整理：注釈・コメント・タグを消し、変換テンプレートは元の数字と単位にする
function clean(v) {
  return v.replace(/<!--[\s\S]*?-->/g, '').replace(/<ref[^>]*\/>/g, '').replace(/<ref[^>]*>[\s\S]*?<\/ref>/g, '')
    .replace(/\{\{\s*(?:convert|convert2|cvt)\s*\|\s*([\d.,]+)\s*\|\s*([^|}]+)[^}]*\}\}/gi, '$1 $2')
    .replace(/\{\{\s*val\s*\|\s*([\d.,]+)((?:\|[^}]*)?)\}\}/gi, (_, n, rest) => { const u = (rest.match(/\|\s*ul?\s*=\s*([^|}]+)/) || [])[1] || ''; return n + ' ' + u; })
    .replace(/\{\{\s*e\s*\|\s*(-?\d+)\s*\}\}/gi, 'e$1')
    .replace(/\{\{\s*(?:R|efn|efn2|Sfn|refnest|要出典)[^}]*\}\}/gi, '').replace(/\{\{sup\|2\}\}/gi, '2')
    .replace(/<sup>2<\/sup>/gi, '2').replace(/<small>([\d]+)<\/small>/gi, '$1').replace(/<[^>]+>/g, ' ')
    .replace(/\[\[(?:[^|\]]*\|)?([^\]]*)\]\]/g, '$1').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
}
// 「数字＋単位」を1つ読んで、収録の単位（m・km・km²・kg・人・km/h）にそろえる
const KNOT = 1.852;
function readNum(raw, key, def) {
  const v = clean(raw);
  if (/^(約|およそ)?\s*$/.test(v)) return null;
  const un = why => ({ unsure: why, raw: v.slice(0, 80) });
  if (/^\{\{|\{\{(?!\s*0)/.test(v)) return un('テンプレートで書かれている');
  if (/☉|M_?sun|太陽質量|地球質量/.test(v)) return un('天体の単位');
  // 「1億2281万1000」のような書き方
  const jp = v.match(/^\D{0,4}?(\d[\d,]*(?:\.\d+)?)\s*億\s*(?:(\d[\d,]*)\s*万)?\s*(\d[\d,]*)?|^\D{0,4}?(\d[\d,]*(?:\.\d+)?)\s*万\s*(\d[\d,]*)?/);
  if (jp) { const f = x => +(String(x || '0').replace(/,/g, '')); const n = jp[1] !== undefined ? f(jp[1]) * 1e8 + f(jp[2]) * 1e4 + f(jp[3]) : f(jp[4]) * 1e4 + f(jp[5]); return { n, raw: v.slice(0, 80) }; }
  // 範囲（「45 - 55 km/h」）や、区間ごとに複数の数字が並ぶもの（路線の距離など）は、どれと比べるか決められない
  if (/\d\s*[-–〜~]\s*\d/.test(v.replace(/\d{4}年\s*[-–〜~]\s*\d{4}年/g, ''))) return un('範囲で書かれている');
  const units = v.match(/\d[\d,.]*\s*(km|m|mm|kg|t|トン|ha|km2|人|ft|kn|ノット)(?![a-z])/gi) || [];
  if (units.length >= 2 && !/[（(]約?\s*[\d,.]+\s*(km\/h|m|ft|km)/.test(v)) return un('数字が複数ある');
  const mm = v.match(/(-?\d[\d,]*(?:\.\d+)?)\s*(万|億)?\s*([a-zA-Zµ²/]+|メートル|キロメートル|平方キロメートル|ヘクタール|トン|キログラム|グラム|ノット|人|フィート)?/);
  if (!mm) return null;
  let n = parseFloat(mm[1].replace(/,/g, '')); if (!isFinite(n)) return null;
  { const ex = v.slice(mm.index + mm[0].length - (mm[3] || '').length - 0).match(/^\s*e(-?\d+)/); if (ex) n *= 10 ** +ex[1]; }
  if (mm[2] === '万') n *= 1e4; if (mm[2] === '億') n *= 1e8;
  let u = (mm[3] || '').toLowerCase();
  const U = { メートル: 'm', キロメートル: 'km', 平方キロメートル: 'km2', ヘクタール: 'ha', トン: 't', キログラム: 'kg', グラム: 'g', ノット: 'kn', フィート: 'ft', 'km²': 'km2', 'km^2': 'km2', knot: 'kn', knots: 'kn', lt: 't', 'km/h': 'km/h', mph: 'mph' };
  u = U[u] || u;
  const d = def.replace('?', '');
  if (!u || u === '人') u = d;
  const conv = {
    e: { m: 1, ft: 0.3048 }, d: { m: 1, ft: 0.3048 },
    h: { m: 1, cm: 0.01, mm: 0.001, ft: 0.3048 },
    a: { km2: 1, ha: 0.01, m2: 1e-6, km: 1 /* km<sup>2</sup> の 2 が落ちたもの */ },
    p: { '': 1 },
    m: { kg: 1, t: 1000, g: 0.001, lb: 0.4536 },
    l: { km: 1, m: 0.001, mm: 1e-6, ft: 0.0003048, mi: 1.609 },
    s: { 'km/h': 1, kn: KNOT, mph: 1.609, 'm/s': 3.6 },
  }[key];
  // 単位が分からないときは、既定の単位とみなす（身長は値の大きさで cm か m かを決める）
  if (key === 'h' && def === 'cm?' && !conv[u]) u = n > 3 ? 'cm' : 'm';
  if (!mm[3] && (key === 'h' && def !== 'cm?' || key === 'l')) return un('単位が書かれていない');
  if (!(u in conv)) { if (def.endsWith('?') || !u) u = d; else return null; }
  if (!(u in conv)) return null;
  return { n: n * conv[u], raw: v.slice(0, 80) };
}
// 記事の冒頭（節0）の、最初の情報欄の引数を拾う
function params(wt) {
  const out = []; for (const line of wt.split('\n')) { const m = line.match(/^\s*\|\s*([^=|]+?)\s*=\s*(.*)$/); if (m) out.push([m[1].trim(), m[2]]); } return out;
}
function infobox(wt, qt) {
  const P = params(wt), got = {};
  for (const k of Object.keys(qt)) {
    for (const [re, def] of FIELDS[k] || []) {
      const hit = P.find(([name]) => re.test(name)); if (!hit) continue;
      const r = readNum(hit[1], k, def); if (r) { got[k] = { ...r, field: hit[0] }; break; }
    }
  }
  return got;
}
// 比べ方：一致（0.5%以内か、四捨五入の違い）・小さな差（5%以内。人口は調査年の違いが多いので15%以内）・食い違い
function judge(k, wd, jp) {
  const diff = Math.abs(wd - jp) / Math.max(Math.abs(wd), Math.abs(jp), 1e-9);
  if (diff <= 0.005 || Math.abs(wd - jp) < (k === 'p' ? 1 : 0.51 * (k === 'a' ? 0.01 : k === 'l' ? 0.001 : 1))) return ['一致', diff];
  if (diff <= (k === 'p' ? 0.15 : 0.05)) return ['小さな差', diff];
  return ['食い違い', diff];
}
export { clean, readNum, infobox, judge };

// ---------- 本体 ----------
if (process.argv[1] && process.argv[1].endsWith('numcheck.mjs') && !process.env.NUMCHECK_LIB) {
  const fnvDir = 'data/a'; const L = [];
  for (const f of readdirSync(fnvDir)) { const b = JSON.parse(gunzipSync(readFileSync(fnvDir + '/' + f)));
    for (const [t, r] of Object.entries(b)) { if (!r.qt) continue; const q = {}; for (const k of Object.keys(LAB)) if (r.qt[k] != null) q[k] = r.qt[k]; if (!Object.keys(q).length) continue;
      const p = (r.ext || []).find(e => e[0] === '_m'); L.push({ t, pv: p ? p[5] : 0, q }); } }
  L.sort((a, b) => b.pv - a.pv); const T = L.slice(0, N);
  const FIX = JSON.parse(readFileSync('data/fix.json', 'utf8'));
  const res = []; const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < T.length; i += 20) {
    const chunk = T.slice(i, i + 20);
    const u = 'https://ja.wikipedia.org/w/api.php?' + new URLSearchParams({ action: 'query', format: 'json', formatversion: 2, prop: 'revisions', rvprop: 'content', rvslots: 'main', rvsection: 0, redirects: 1, maxlag: 5, titles: chunk.map(x => x.t).join('|') });
    let d = null;
    for (let tr = 0; tr < 5 && !d; tr++) { try { const r = await fetch(u, { headers: { 'Api-User-Agent': UA, 'User-Agent': UA } }); const j = await r.json(); if (j.error) { await sleep(5000 * (tr + 1)); continue; } d = j; } catch (_) { await sleep(5000 * (tr + 1)); } }
    if (!d) { console.error('取得できなかった', chunk.map(x => x.t).join('、')); continue; }
    const back = {}; for (const x of [...(d.query.normalized || []), ...(d.query.redirects || [])]) back[x.to] = back[x.from] || x.from;
    const wt = {}; for (const p of d.query.pages) wt[back[p.title] || p.title] = p.revisions ? p.revisions[0].slots.main.content : '';
    for (const x of chunk) {
      const got = infobox(wt[x.t] || '', x.q);
      for (const [k, v] of Object.entries(x.q)) {
        const g = got[k]; const fixed = FIX[x.t] && LAB[k] in FIX[x.t];
        if (!g) { res.push({ t: x.t, pv: x.pv, k, wd: v, st: '日本語版に数字なし', fixed }); continue; }
        if (g.unsure) { res.push({ t: x.t, pv: x.pv, k, wd: v, st: '読み取り不確か', why: g.unsure, field: g.field, raw: g.raw, fixed }); continue; }
        const lr = Math.log10(Math.abs(v / g.n)); if (Math.abs(lr) >= 1.9 && Math.abs(lr - Math.round(lr)) < 0.02) { res.push({ t: x.t, pv: x.pv, k, wd: v, jp: g.n, st: '読み取り不確か', why: '10の何乗倍のずれ（単位の読み違いの疑い）', field: g.field, raw: g.raw, fixed }); continue; }
        const [st, diff] = judge(k, v, g.n); res.push({ t: x.t, pv: x.pv, k, wd: v, jp: +g.n.toPrecision(8), st, diff: +diff.toFixed(4), field: g.field, raw: g.raw, fixed });
      }
    }
    if (i % 200 === 0) console.log(i + chunk.length, '/', T.length);
    await sleep(1000);
  }
  writeFileSync(OUT, JSON.stringify(res, null, 1));
  const cnt = {}; for (const r of res) { cnt[r.k] = cnt[r.k] || {}; cnt[r.k][r.st] = (cnt[r.k][r.st] || 0) + 1; }
  const sts = ['一致', '小さな差', '食い違い', '読み取り不確か', '日本語版に数字なし'];
  const M = [`# 数字の照合（よく読まれている順に ${T.length} 記事・${res.length} 項目）`, '', '| 項目 | ' + sts.join(' | ') + ' |', '|---|' + sts.map(() => '---|').join('')];
  for (const k of Object.keys(LAB)) if (cnt[k]) M.push(`| ${LAB[k]} | ` + sts.map(s => cnt[k][s] || 0).join(' | ') + ' |');
  const bad = res.filter(r => r.st === '食い違い').sort((a, b) => b.pv - a.pv);
  M.push('', `## 食い違い ${bad.length}件（よく読まれている順）`, '', '| 記事 | 項目 | Wikidata | 日本語版 | 差 | 情報欄の書き方 |', '|---|---|---|---|---|---|');
  const c = s => String(s ?? '').replace(/\|/g, '／');
  for (const r of bad) M.push(`| ${c(r.t)}${r.fixed ? '（訂正表あり）' : ''} | ${LAB[r.k]} | ${r.wd} | ${r.jp} | ${Math.round(r.diff * 100)}% | ${c(r.field)} = ${c(r.raw)} |`);
  const md = M.join('\n'); console.log(md.slice(0, 5000));
  if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, md + '\n');
}
