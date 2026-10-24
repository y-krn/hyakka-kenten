// 記事を指定して追加する（1）：WikipediaとWikidataから、指定した記事の材料を集める
// node fetch_one.js <workdir> 記事名1 記事名2 ...   または   node fetch_one.js <workdir> @titles.json
//   workdir/cirrus.jsonl … 検索用データ（ダンプと同じ形）
//   workdir/ents.jsonl   … Wikidataの項目（記事本体・関連項目・分類を6段まで）
//   workdir/aux_type.jsonl / aux_works.jsonl … 種類ごとの項目数・人物の作品数
//   workdir/titles.json  … {入力した名前: 正式な記事名 or null}
'use strict';
const fs = require('fs'), path = require('path');
const W = require('../wm_vm.js');
const DIR = process.argv[2];
// 記事名は引数で並べるか、「@ファイル名」でJSONの配列を渡す（空白や記号を含む記事名でも安全）
const IN = ((process.argv[3] || '').startsWith('@') ? JSON.parse(fs.readFileSync(process.argv[3].slice(1), 'utf8')) : process.argv.slice(3)).map(s => String(s).trim()).filter(Boolean);
fs.mkdirSync(DIR, { recursive: true });
const idv = s => s && s.mainsnak && s.mainsnak.datavalue && s.mainsnak.datavalue.value && s.mainsnak.datavalue.value.id;
const ids = (e, p) => ((e && e.c && e.c[p]) || []).map(idv).filter(Boolean);
const ENTS = {};
async function fetchEnts(list, mode) {   // mode: main（サイトリンク込み）/ full / lab（名前と説明だけ）
  const need = [...new Set(list)].filter(q => /^Q\d+$/.test(q) && !(ENTS[q] && (mode === 'lab' || Object.keys(ENTS[q].c || {}).length || ENTS[q]._full)));
  for (let i = 0; i < need.length; i += 50) {
    const part = need.slice(i, i + 50);
    const props = mode === 'lab' ? 'labels|descriptions' : 'claims|labels|descriptions' + (mode === 'main' ? '|sitelinks' : '');
    const j = await W.getJ('https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=' + props + '&languages=ja|en&ids=' + part.join('|'));
    Object.values(j.entities || {}).forEach(e => { if (e.id && !e.missing) { const t = W.trim(e); if (mode !== 'lab') t._full = 1; if (!ENTS[e.id] || mode !== 'lab') ENTS[e.id] = t; } });
  }
}
(async () => {
  // 1. Wikipedia：転送を解決し、検索用データ（cirrusdoc）を取る
  const titles = {}; const docs = [];
  for (let i = 0; i < IN.length; i += 20) {
    const part = IN.slice(i, i + 20);
    const j = await W.getJ('https://ja.wikipedia.org/w/api.php?action=query&format=json&prop=cirrusdoc&redirects=1&titles=' + encodeURIComponent(part.join('|')));
    const map = {}; (j.query.normalized || []).forEach(n => map[n.from] = n.to); (j.query.redirects || []).forEach(n => map[n.from] = n.to);
    const res = t => { let x = t; for (let k = 0; k < 4 && map[x]; k++) x = map[x]; return x; };
    const pages = {}; Object.values(j.query.pages || {}).forEach(p => pages[p.title] = p);
    for (const t of part) {
      const p = pages[res(t)];
      if (!p || p.missing !== undefined || !(p.cirrusdoc && p.cirrusdoc[0])) { titles[t] = null; continue; }
      const s = p.cirrusdoc[0].source;
      (s.coordinates || []).forEach(c => { if ('primary' in c) c.primary = true; });   // APIでは空文字で返るので、ダンプと同じ true にそろえる
      titles[t] = s.title; docs.push(s);
    }
  }
  fs.writeFileSync(path.join(DIR, 'cirrus.jsonl'), docs.map(d => JSON.stringify(d)).join('\n') + (docs.length ? '\n' : ''));
  fs.writeFileSync(path.join(DIR, 'titles.json'), JSON.stringify(titles));
  const MAIN = docs.filter(d => d.wikibase_item && String(d.namespace) === '0').map(d => d.wikibase_item);
  // 2. Wikidata：本体 → 関連項目 → その上位クラス → 分類を6段
  await fetchEnts(MAIN, 'main');
  const NEEDP = ['P31','P279','P138','P61','P112','P170','P50','P131','P276','P137','P176','P127','P749','P449','P179','P361','P1433','P106'];
  const NEED = new Set(W.linkedOf(MAIN, ENTS, NEEDP)); const all = W.linkedOf(MAIN, ENTS);
  await fetchEnts(all.filter(q => NEED.has(q)), 'full');
  await fetchEnts(all.filter(q => !NEED.has(q)), 'lab');
  const L1 = W.linkedOf(MAIN, ENTS); await fetchEnts(W.linkedOf(L1, ENTS, ['P279']), 'full');
  let fr = new Set(MAIN.flatMap(q => ids(ENTS[q], 'P31')));
  for (let d = 0; d < 6 && fr.size; d++) { await fetchEnts([...fr], 'full'); const nx = new Set(); fr.forEach(q => ids(ENTS[q], 'P279').forEach(x => nx.add(x))); fr = nx; }
  // 因縁の相手を探すため、関係の先にある項目の日本語版の記事名も取る
  const RELP = ['P1889','P138','P155','P156','P1365','P1366','P22','P25','P40','P3373','P26','P1066','P802','P737','P144','P4969','P47','P190','P460','P170','P50','P86','P57','P61','P84','P112','P1327','P1346'];
  const relT = [...new Set(MAIN.flatMap(q => RELP.flatMap(p => ids(ENTS[q], p))))];
  const jt = {};
  for (let i = 0; i < relT.length; i += 50) {
    const j = await W.getJ('https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=sitelinks&sitefilter=jawiki&ids=' + relT.slice(i, i + 50).join('|'));
    Object.values(j.entities || {}).forEach(e => { if (e.sitelinks && e.sitelinks.jawiki) jt[e.id] = e.sitelinks.jawiki.title; });
  }
  fs.writeFileSync(path.join(DIR, 'reltitles.json'), JSON.stringify(jt));
  fs.writeFileSync(path.join(DIR, 'ents.jsonl'), Object.values(ENTS).map(e => { const x = { ...e }; delete x._full; return JSON.stringify(x); }).join('\n') + '\n');
  // 3. 種類ごとの項目数（人物以外）と、人物の作品数
  const T = [], P = [];
  for (const q of MAIN) {
    const isP = ids(ENTS[q], 'P31').includes('Q5');
    if (!isP) { const r = await W.search('haswbstatement:P31=' + q, 1); T.push([q, r.n]); continue; }
    const w = await W.search('haswbstatement:"P50=' + q + '|P170=' + q + '|P86=' + q + '|P57=' + q + '|P175=' + q + '|P161=' + q + '|P725=' + q + '"', 50);
    const occ = ids(ENTS[q], 'P106').map(x => ENTS[x] ? ((ENTS[x].l.ja || '') + ' ' + (ENTS[x].l.en || '')).toLowerCase() : '').join(' ');
    let m = []; if (/武将|軍人|大名|武士|軍事|司令|将軍|military|soldier|samurai|general|daimyo/.test(occ)) m = (await W.search('haswbstatement:P710=' + q, 50)).ids;
    P.push([q, w.n, w.ids, m]);
  }
  fs.writeFileSync(path.join(DIR, 'aux_type.jsonl'), T.map(x => JSON.stringify(x)).join('\n') + '\n');
  fs.writeFileSync(path.join(DIR, 'aux_works.jsonl'), P.map(x => JSON.stringify(x)).join('\n') + '\n');
  console.log(JSON.stringify({ input: IN.length, found: docs.length, ents: Object.keys(ENTS).length, req: W.stats().nreq }));
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
