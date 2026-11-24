// Workers Analytics Engine の記録（3か月で消える）を、日ごとの合計にしてデータベース（D1）に写すための SQL を作る
//   誰のものかを結び付けられる値は、もともと記録にない。直近 DAYS 日分を毎回作り直す（同じ日を何度写しても同じ結果になる）
//   環境変数: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, DATASET（hyakka_ev／hyakka_ev_preview）, DAYS（既定 14）, OUT（SQL を書くファイル）
import { writeFileSync } from 'node:fs';
const { CLOUDFLARE_API_TOKEN: TOKEN, CLOUDFLARE_ACCOUNT_ID: ACC, DATASET = 'hyakka_ev', DAYS = '14', OUT = 'rollup.sql' } = process.env;
if (!/^[a-z_]+$/.test(DATASET) || !/^\d{1,2}$/.test(DAYS)) throw new Error('DATASET か DAYS がおかしい');
const sql = async q => {
  const r = await fetch(`https://api.cloudflare.com/client/v4/accounts/${ACC}/analytics_engine/sql`, { method: 'POST', headers: { Authorization: 'Bearer ' + TOKEN }, body: q });
  const t = await r.text(); if (!r.ok) throw new Error('Analytics Engine の読み出しに失敗: ' + t.slice(0, 300));
  return JSON.parse(t).data || [];
};
// 日本時間の日付ごとに分ける
const DAY = "toStartOfInterval(timestamp + INTERVAL '9' HOUR, INTERVAL '1' DAY)";
const base = `FROM ${DATASET} WHERE timestamp > NOW() - INTERVAL '${DAYS}' DAY`;
const rows = [
  ...(await sql(`SELECT ${DAY} AS d, blob1 AS ev, blob2 AS k, blob3 AS dev, blob4 AS src, blob5 AS x, SUM(_sample_interval * double1) AS n ${base} AND blob1 = 'visit' GROUP BY d, ev, k, dev, src, x FORMAT JSON`)),
  ...(await sql(`SELECT ${DAY} AS d, 'ref' AS ev, blob6 AS k, blob3 AS dev, blob4 AS src, '' AS x, SUM(_sample_interval * double1) AS n ${base} AND blob1 = 'visit' AND blob6 <> '' GROUP BY d, k, dev, src FORMAT JSON`)),
  ...(await sql(`SELECT ${DAY} AS d, blob1 AS ev, blob2 AS k, blob3 AS dev, blob4 AS src, '' AS x, SUM(_sample_interval * double1) AS n ${base} AND blob1 IN ('play', 'reach', 'btn') GROUP BY d, ev, k, dev, src FORMAT JSON`)),
];
const q = v => "'" + String(v ?? '').replace(/'/g, "''").slice(0, 80) + "'";
const days = new Set(), L = [];
for (const r of rows) {
  const day = String(r.d).slice(0, 10); if (!/^\d{4}-\d\d-\d\d$/.test(day)) continue; days.add(day);
  L.push(`INSERT INTO daily_stats (day, ev, k, dev, src, x, n) VALUES (${q(day)}, ${q(r.ev)}, ${q(r.k)}, ${q(r.dev)}, ${q(r.src)}, ${q(r.x)}, ${Math.round(Number(r.n) || 0)});`);
}
// 写す日の分を消してから入れ直す（数え直した結果で置き換える）。ただし、移す前の記録から作った日（Analytics Engine に記録がない日）は消さない
const del = [...days].sort().map(d => `DELETE FROM daily_stats WHERE day = ${q(d)};`);
writeFileSync(OUT, [...del, ...L].join('\n') + '\n');
console.log(`日数 ${days.size}（${[...days].sort().join(', ')}）、行数 ${L.length}`);
