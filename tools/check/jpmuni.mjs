// 調査用：日本の都道府県・市区町村の人口と面積を、日本語版の記事が表示している値と突き合わせる（照合だけ。何も書き換えない）
//   市区町村の記事の情報欄は、数字を「Template:自治体人口/〇〇県」「Template:自治体面積/〇〇県」から引いて表示している
//   （記事のウィキテキストには数字が書かれていないので、ふつうの照合では「日本語版に数字なし」になる）
//   このテンプレート（47都道府県×2）を直接読んで、収録の数字と比べる。結果は numcheck.mjs と同じ形で「NC」で始まる行に出す
import { readFileSync, readdirSync, appendFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
process.env.NUMCHECK_LIB = '1';
const { judge } = await import('./numcheck.mjs');
const UA = 'hyakka-kenten-numcheck (+https://github.com/y-krn)';
const PREF = '北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県'.split(' ');
const sleep = ms => new Promise(r => setTimeout(r, ms));
// テンプレートを読む（20ページずつ）
const pages = PREF.flatMap(p => [`Template:自治体人口/${p}`, `Template:自治体面積/${p}`]); const WT = {};
for (let i = 0; i < pages.length; i += 20) {
  const u = 'https://ja.wikipedia.org/w/api.php?' + new URLSearchParams({ action: 'query', format: 'json', formatversion: 2, prop: 'revisions', rvprop: 'content', rvslots: 'main', maxlag: 5, titles: pages.slice(i, i + 20).join('|') });
  let d = null; for (let tr = 0; tr < 5 && !d; tr++) { try { const j = await (await fetch(u, { headers: { 'Api-User-Agent': UA, 'User-Agent': UA } })).json(); if (j.error) { await sleep(5000); continue; } d = j; } catch (_) { await sleep(5000); } }
  if (!d) { console.error('取得できなかった', pages.slice(i, i + 20).join('、')); continue; }
  for (const p of d.query.pages) WT[p.title] = p.revisions ? p.revisions[0].slots.main.content : '';
  await sleep(1000);
}
// 「| 名前 = 数字」を拾う。T[名前] = [{pref, p, a}]（同じ名前の町村が別の都道府県にあることがある）
const T = {}; let date = '';
for (const pf of PREF) for (const [kind, k] of [['人口', 'p'], ['面積', 'a']]) {
  const w = WT[`Template:自治体${kind}/${pf}`] || '';
  if (k === 'p') { const m = w.match(/\|\s*date\s*=\s*([^\n|]+)/); if (m && !date) date = m[1].trim(); }
  for (const m of w.matchAll(/^\s*\|\s*([^=|#\n]+?)\s*=\s*([\d,.]+)\s*$/gm)) {
    const name = m[1].trim(), v = parseFloat(m[2].replace(/,/g, '')); if (!isFinite(v)) continue;
    const L = (T[name] ||= []); let e = L.find(x => x.pref === pf); if (!e) L.push(e = { pref: pf }); e[k] = v;
  }
}
console.log('テンプレートの項目', Object.keys(T).length, '人口の時点', date);
// 収録記事のうち、名前（「 (〇〇県)」などを除いたもの）がテンプレートにあるもの
const res = [];
for (const f of readdirSync('data/a')) { const B = JSON.parse(gunzipSync(readFileSync('data/a/' + f)));
  for (const [t, r] of Object.entries(B)) { if (!r.qt || !(r.qt.p > 0 || r.qt.a > 0)) continue;
    const m = t.match(/^(.+?)(?:\s*\((.+?)\))?$/); const base = m[1], hint = m[2] || '';
    // 政令市の区は「大阪市北区」のように市の名前つきでテンプレートにある（「北区 (大阪市)」→「大阪市北区」）
    const L = hint && T[hint + base] ? T[hint + base] : T[base]; if (!L) continue;
    // どの都道府県のものか：題名の括弧（「川西町 (奈良県)」）。括弧があるのに合う都道府県がないもの（別の市の区など）は使わない
    //   括弧がなく1つだけならそれ。複数あって決められないものは、面積がいちばん近いもの（2割以内）
    let e = hint && T[hint + base] ? L[0] : hint ? L.find(x => hint.includes(x.pref)) : (L.length === 1 ? L[0] : null);
    if (hint && !e) continue;
    if (!e && r.qt.a > 0) { const c = L.filter(x => x.a > 0).sort((x, y) => Math.abs(x.a - r.qt.a) - Math.abs(y.a - r.qt.a))[0]; if (c && Math.abs(c.a - r.qt.a) / r.qt.a <= 0.2) e = c; }
    if (!e) continue;
    const p = (r.ext || []).find(x => x[0] === '_m'); const pv = p ? p[5] : 0;
    for (const k of ['p', 'a']) { const wd = r.qt[k], jp = e[k]; if (!(wd > 0) || !(jp > 0)) continue;
      const [st, diff] = judge(k, wd, jp);
      res.push({ t, pv, k, wd, jp, st, diff: +diff.toFixed(4), field: `Template:自治体${k === 'p' ? '人口' : '面積'}/${e.pref}`, raw: `${base} = ${jp}${k === 'p' && date ? '（' + date + '）' : ''}` }); }
  } }
for (const r of res) console.log('NC\t' + JSON.stringify(r));
const cnt = {}; for (const r of res) { const key = r.k + ':' + r.st; cnt[key] = (cnt[key] || 0) + 1; }
const M = [`# 日本の自治体の人口・面積の照合（${res.length} 項目、人口は${date}時点）`, '', '```', JSON.stringify(cnt, null, 1), '```'];
console.log(M.join('\n')); if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, M.join('\n') + '\n');
