// 調査用：届いている報告を一覧にする（読むだけ。回線やブラウザの番号は出さない）
// 実行結果のページは誰でも見られる（公開リポジトリ）ので、利用者が自由に書いた「ひとこと」と「出典URL」は出さない。
// その2つは、Cloudflare の管理画面（D1 → hyakka-kenten → コンソール）で、下に出す問い合わせを実行して読む
//   環境変数: CF_TOKEN, CF_ACCOUNT, D1_ID
import { appendFileSync } from 'node:fs';
const { CF_TOKEN, CF_ACCOUNT, D1_ID, GITHUB_STEP_SUMMARY } = process.env;
const r = await fetch(`https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT}/d1/database/${D1_ID}/query`, { method: 'POST',
  headers: { Authorization: 'Bearer ' + CF_TOKEN, 'Content-Type': 'application/json' },
  body: JSON.stringify({ sql: "SELECT id, datetime(at, '+9 hours') AS at, kind, reason, a, b, target, title, fk, fv, fix, url, text, status, rkey, (SELECT COUNT(DISTINCT iphash) FROM reports r2 WHERE r2.rkey = reports.rkey AND r2.status = 'new') AS people FROM reports ORDER BY id" }) });
const j = await r.json(); if (!j.success) { console.error(JSON.stringify(j.errors)); process.exit(1); }
const rows = j.result[0].results;
const L = ['# 届いている報告 ' + rows.length + '件', '', '| id | 日時 | 種類 | 理由 | 対戦 | 対象 | 項目 | いまの値 | 正しい値 | 出典・ひとこと | 人数 | 状態 |', '|---|---|---|---|---|---|---|---|---|---|---|---|'];
const c = x => String(x ?? '').replace(/\|/g, '／').replace(/\n/g, ' ');
for (const x of rows) L.push(`| ${x.id} | ${c(x.at)} | ${c(x.kind)} | ${c(x.reason)} | ${c(x.a)} 対 ${c(x.b)} | ${c(x.target === 'text' ? '実況の文面' : x.title || x.target)} | ${c(x.fk)} | ${c(x.fv)} | ${c(String(x.fix ?? '').slice(0, 40))} | ${x.url || x.text ? 'あり（管理画面で見る）' : ''} | ${c(x.people)} | ${c(x.status)} |`);
L.push('', '出典・ひとことを読むには、Cloudflare の管理画面の D1（hyakka-kenten）のコンソールで次を実行：', '', '`SELECT id, url, text FROM reports WHERE url IS NOT NULL OR text IS NOT NULL ORDER BY id DESC LIMIT 50`');
console.log(L.join('\n')); if (GITHUB_STEP_SUMMARY) appendFileSync(GITHUB_STEP_SUMMARY, L.join('\n') + '\n');
