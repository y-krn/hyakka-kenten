// 無料枠の見張り：Cloudflare の今日（UTC。無料枠はUTCの0時に戻る）の使用量を読み、多すぎたら ntfy に知らせる。読むだけで何も変えない
//   見るもの：Workers のリクエスト数（無料枠 1日10万）、D1 の読んだ行数（1日500万）・書いた行数（1日10万）
//   使うもの：CLOUDFLARE_API_TOKEN（アカウントの解析を読む権限）、CLOUDFLARE_ACCOUNT_ID、NTFY_TOPIC
const T = process.env.CLOUDFLARE_API_TOKEN, A = process.env.CLOUDFLARE_ACCOUNT_ID, NTFY = process.env.NTFY_TOPIC;
const LIMIT = { req: 100000, read: 5000000, write: 100000 }, WARN = +(process.env.WARN || 0.5);   // 無料枠の半分を超えたら知らせる
const day = new Date().toISOString().slice(0, 10);
const gql = async q => { const r = await fetch('https://api.cloudflare.com/client/v4/graphql', { method: 'POST', headers: { Authorization: 'Bearer ' + T, 'Content-Type': 'application/json' }, body: JSON.stringify({ query: q }) }); const j = await r.json(); if (j.errors && j.errors.length) console.log('ERR', JSON.stringify(j.errors).slice(0, 600)); return j.data; };
const d = await gql(`query{viewer{accounts(filter:{accountTag:"${A}"}){
  w:workersInvocationsAdaptive(limit:50,filter:{date_geq:"${day}",date_leq:"${day}"}){sum{requests errors} dimensions{scriptName}}
  d:d1AnalyticsAdaptiveGroups(limit:50,filter:{date_geq:"${day}",date_leq:"${day}"}){sum{rowsRead rowsWritten readQueries writeQueries} dimensions{databaseId}}}}}`);
const a = d && d.viewer && d.viewer.accounts[0];
if (!a) { console.log('読めませんでした'); process.exit(1); }
const sum = (L, f) => (L || []).reduce((n, x) => n + (x.sum[f] || 0), 0);
const u = { req: sum(a.w, 'requests'), read: sum(a.d, 'rowsRead'), write: sum(a.d, 'rowsWritten') };
const pct = k => Math.round(u[k] / LIMIT[k] * 100);
console.log('CHJSON' + JSON.stringify({ day, ...u, pct: { req: pct('req'), read: pct('read'), write: pct('write') }, workers: (a.w || []).map(x => [x.dimensions.scriptName, x.sum.requests, x.sum.errors]) }));
const over = Object.keys(LIMIT).filter(k => u[k] >= LIMIT[k] * WARN);
if (over.length && NTFY) {
  const lab = { req: 'Workersのリクエスト', read: 'D1の読んだ行数', write: 'D1の書いた行数' };
  await fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic: NTFY, title: '百科拳典：無料枠の使用が多い', priority: 4, tags: ['warning'],
    message: over.map(k => `${lab[k]}：${u[k].toLocaleString('ja-JP')}（無料枠の${pct(k)}%）`).join('\n') + '\n（UTC ' + day + '。日本時間9時に戻ります。連打の可能性があれば Cloudflare のダッシュボードで確かめてください）' }) });
  console.log('知らせました', over.join(','));
}
