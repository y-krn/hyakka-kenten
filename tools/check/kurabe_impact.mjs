// 調査：「比べ合い」のきっかけから「生まれた年」「肩書きの数」を外したとき、王座戦の過去の試合のうち結果が変わるものを数える
//   いまのエンジンと、条件だけ変えたエンジンの両方で、記録済みの挑戦をすべて計算し直して比べる
//   使い方: node tools/check/kurabe_impact.mjs（GitHub Actions の「調査」から動かす）
import fs from 'node:fs'; import path from 'node:path'; import { fileURLToPath, pathToFileURL } from 'node:url';
const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const SITE = process.env.SITE || 'https://hyakkakenten.com';
const src = fs.readFileSync(path.join(ROOT, 'worker/src/engine.mjs'), 'utf8');
const A = 'nReal=R.filter(x=>!METAD.includes(x.k)).length';
if (!src.includes(A)) throw new Error('比べ合いの条件の場所が見つかりません');
const tmp = fs.mkdtempSync(path.join(process.env.RUNNER_TEMP || '/tmp', 'kb-'));
const exp = s => s.replace('export {setup, loadOne, verdict, info};', 'export {setup, loadOne, verdict, info, analyze};');
fs.writeFileSync(path.join(tmp, 'now.mjs'), exp(src));
fs.writeFileSync(path.join(tmp, 'new.mjs'), exp(src.replace(A, "nReal=R.filter(x=>!METAD.includes(x.k)&&x.k!=='yr'&&x.k!=='P106').length")));
const meta = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/meta.json')));
const fetchLocal = async u => new Response(fs.readFileSync(path.join(ROOT, 'data', u.replace('file:///data/', '').split('?')[0])));
const E = {};
for (const k of ['now', 'new']) { E[k] = await import(pathToFileURL(path.join(tmp, k + '.mjs'))); E[k].setup({ base: 'file:///data/', fetch: fetchLocal, nb: meta.nb, ver: meta.build }); }

// 記録済みの挑戦を、公開されている API から1件ずつ読む
const th = await fetch(SITE + '/api/throne').then(r => r.json());
const maxId = Math.max(...(th.recent || []).map(x => x.id));
const rows = [];
for (let id = 1; id <= maxId; id++) { const r = await fetch(SITE + '/api/challenge/' + id); if (r.ok) rows.push(await r.json()); }
const out = []; let same = 0, chType = 0, chWin = 0, skip = 0; const flips = [];
for (const x of rows) {
  const res = {};
  for (const k of ['now', 'new']) { const a = await E[k].loadOne(x.challenger.title), b = await E[k].loadOne(x.champ.title); if (a < 0 || b < 0) { res[k] = null; continue; }
    const an = E[k].analyze(a, b, true); const v = E[k].verdict(a, b); res[k] = { w: v.w, type: an.type || v.type }; }
  if (!res.now || !res.new) { skip++; continue; }
  const winNow = res.now.w === x.challenger.title ? 'win' : res.now.w === x.champ.title ? 'lose' : 'draw';
  const winNew = res.new.w === x.challenger.title ? 'win' : res.new.w === x.champ.title ? 'lose' : 'draw';
  if (res.now.type !== res.new.type) chType++;
  if (winNow !== winNew) { chWin++; flips.push({ id: x.id, reign: x.reignNo, ch: x.challenger.display, cp: x.champ.display, rec: x.result, now: winNow, nw: winNew, t0: res.now.type, t1: res.new.type }); } else same++;
}
const L = [];
L.push(`# 比べ合いの条件を変えたときの、王座戦への影響`, '', `記録済みの挑戦 ${rows.length}件（計算できなかったもの ${skip}件）`, '',
  `- 試合の型が変わる：${chType}件`, `- 勝敗が変わる：${chWin}件`, `- 勝敗は変わらない：${same}件`, '');
if (flips.length) { L.push('| 挑戦 | 第何代の王者 | 挑戦者 | 王者 | 記録 | 今の計算 | 変更後 | 型（今→後） |', '|---|---|---|---|---|---|---|---|');
  for (const f of flips) L.push(`| #${f.id} | ${f.reign} | ${f.ch} | ${f.cp} | ${f.rec} | ${f.now} | ${f.nw} | ${f.t0}→${f.t1} |`); }
const md = L.join('\n'); console.log(md);
if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, md + '\n');
