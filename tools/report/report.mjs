// 週1回のアクセスレポート
//   ゲームの記録（D1）と、Cloudflare Web Analytics の訪問数を、先週と比べてまとめる。
//   遊ばれ方は日ごとの合計（daily_stats。誰のものかは持たない）から読む。実行結果のページは誰でも見られるので、報告のひとことと出典は出さない
//   結果は GitHub Actions の実行結果ページ（Summary）に書き、ntfy に短い通知を送る。
// 必要な環境変数: CF_TOKEN, CF_ACCOUNT, D1_ID
// 任意: NTFY_TOPIC（通知先）, RUN_URL（通知をタップしたときに開くページ）, GITHUB_STEP_SUMMARY
import { appendFileSync } from 'node:fs';

const { CF_TOKEN, CF_ACCOUNT, D1_ID, NTFY_TOPIC, RUN_URL, GITHUB_STEP_SUMMARY } = process.env;
const RUM_TOKEN = '92aaad9660e1433f8d518c17a8ac2512';   // ページに埋め込んでいる Web Analytics の番号（公開されているもの）
const API = 'https://api.cloudflare.com/client/v4';
const H = { Authorization: 'Bearer ' + CF_TOKEN, 'Content-Type': 'application/json', 'User-Agent': 'hyakka-kenten-report (+https://github.com/y-krn)' };

// ---------- 期間：日本時間で「きょうの0時」までの7日間と、その前の7日間 ----------
const DAY = 864e5, JST = 9 * 36e5;
const end = new Date(Math.floor((Date.now() + JST) / DAY) * DAY - JST);
const start = new Date(end - 7 * DAY), pstart = new Date(start - 7 * DAY);
const iso = d => d.toISOString();
const md = d => { const j = new Date(+d + JST); return (j.getUTCMonth() + 1) + '/' + j.getUTCDate(); };
const range = md(start) + '〜' + md(new Date(end - DAY));

// ---------- D1 ----------
async function q(sql, params = []) {
  const r = await fetch(`${API}/accounts/${CF_ACCOUNT}/d1/database/${D1_ID}/query`, { method: 'POST', headers: H, body: JSON.stringify({ sql, params }) });
  const j = await r.json(); if (!j.success) throw new Error('D1: ' + JSON.stringify(j.errors));
  return j.result[0].results;
}
const W = [iso(start), iso(end)], P = [iso(pstart), iso(start)];
const jd = d => new Date(+d + JST).toISOString().slice(0, 10), DW = [jd(start), jd(end)], DP = [jd(pstart), jd(start)];   // 日ごとの合計は日本時間の日付
const one = async (sql, p) => (await q(sql, p))[0] || {};
const PLAYS = "SELECT COALESCE(SUM(CASE WHEN ev = 'play' THEN n END), 0) AS n, COALESCE(SUM(CASE WHEN ev = 'reach' AND k = '1' THEN n END), 0) AS u FROM daily_stats WHERE day >= ? AND day < ?";   // u：その日に1戦以上遊んだブラウザの、日ごとの延べ
const CH = "SELECT COUNT(*) AS n, COALESCE(SUM(result = 'win'),0) AS w FROM challenges WHERE at >= ? AND at < ? AND result <> 'late'";
const [pw, pp, cw, cp, champ, changes, topCh, daily, tot] = await Promise.all([
  one(PLAYS, DW), one(PLAYS, DP), one(CH, W), one(CH, P),
  one('SELECT id, display, holder, defenses, started_at FROM reigns WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1'),
  q('SELECT id, display, holder, ended_by FROM reigns WHERE started_at >= ? AND started_at < ? ORDER BY id', W),
  q("SELECT display, COUNT(*) AS n FROM challenges WHERE at >= ? AND at < ? AND result <> 'late' GROUP BY title ORDER BY n DESC, MIN(id) LIMIT 5", W),
  q("SELECT day AS d, SUM(n) AS n FROM daily_stats WHERE ev = 'play' AND day >= ? AND day < ? GROUP BY day ORDER BY day", DW),
  one("SELECT (SELECT n FROM stats WHERE k = 'plays') AS plays, (SELECT COUNT(*) FROM challenges WHERE result <> 'late') AS ch, (SELECT COUNT(*) FROM reigns) AS reigns"),
]);

// ---------- Web Analytics（権限がなければ、その旨だけ書いて続ける） ----------
let rum = null, rumNote = '';
try {
  const s = await fetch(`${API}/accounts/${CF_ACCOUNT}/rum/site_info/list?per_page=50`, { headers: H }).then(r => r.json());
  if (!s.success) throw new Error((s.errors || []).map(e => e.message).join(' / ') || 'site list');
  const site = (s.result || []).find(x => x.site_token === RUM_TOKEN || x.site_tag === RUM_TOKEN);
  if (!site) throw new Error('サイトが見つかりません');
  const f = (a, b) => `{siteTag: "${site.site_tag}", datetime_geq: "${a}", datetime_lt: "${b}", bot: 0}`;
  const g = (name, fl, dim, lim, ord = 'sum_visits_DESC') => `${name}: rumPageloadEventsAdaptiveGroups(limit: ${lim}, filter: ${fl}${ord ? ', orderBy: [' + ord + ']' : ''}) { count sum { visits }${dim ? ' dimensions { ' + dim + ' }' : ''} }`;
  const fw = f(iso(start), iso(end)), fp = f(iso(pstart), iso(start));
  const query = `{ viewer { accounts(filter: {accountTag: "${CF_ACCOUNT}"}) {
    ${g('tw', fw, '', 1, '')} ${g('tp', fp, '', 1, '')}
    ${g('ctry', fw, 'countryName', 6)} ${g('ref', fw, 'refererHost', 8)} ${g('path', fw, 'requestPath', 5)} ${g('dev', fw, 'deviceType', 4)} } } }`;
  const j = await fetch(API + '/graphql', { method: 'POST', headers: H, body: JSON.stringify({ query }) }).then(r => r.json());
  if (j.errors && j.errors.length) throw new Error(j.errors.map(e => e.message).join(' / '));
  rum = j.data.viewer.accounts[0];
} catch (e) { rumNote = String(e.message || e); }

// ---------- まとめる ----------
const n = x => Number(x || 0).toLocaleString('ja-JP');
const diff = (a, b) => { a = +a || 0; b = +b || 0; if (!b) return a ? '（先週 0）' : ''; const p = Math.round((a - b) / b * 100); return `（先週 ${n(b)}、${p >= 0 ? '+' : ''}${p}%）`; };
const v = o => o && o[0] ? { visits: o[0].sum.visits, views: o[0].count } : { visits: 0, views: 0 };
const who = h => h && h !== '名無しの挑戦者' ? `（${h}）` : '';   // 名前を入れずに挑んだ人は書かない
const CTRY = { JP: '日本', US: 'アメリカ', CN: '中国', FR: 'フランス', NL: 'オランダ', IE: 'アイルランド', DE: 'ドイツ', GB: 'イギリス', SG: 'シンガポール', KR: '韓国', TW: '台湾', HK: '香港', CA: 'カナダ', IN: 'インド', AU: 'オーストラリア' };
const L = [];
L.push(`# 百科拳典 週間レポート ${range}`, '');
L.push('## 訪問（Cloudflare Web Analytics）');
if (rum) {
  const a = v(rum.tw), b = v(rum.tp);
  L.push(`- 訪問 ${n(a.visits)} ${diff(a.visits, b.visits)}`, `- ページ表示 ${n(a.views)} ${diff(a.views, b.views)}`);
  const list = (title, rows, key, fmt = x => x || '（不明）') => { if (rows.length) L.push(`- ${title}：` + rows.map(r => `${fmt(r.dimensions[key])} ${n(r.sum.visits)}`).join('、')); };
  list('国・地域', rum.ctry, 'countryName', x => CTRY[x] || x || '（不明）');
  list('どこから来たか', rum.ref, 'refererHost', x => x || '直接・不明');
  list('よく開かれたページ', rum.path, 'requestPath');
  list('端末', rum.dev, 'deviceType');
} else L.push(`- 取得できませんでした：${rumNote}`, '  - APIトークンに「Account Analytics：読み取り」の権限があるか確認してください');
L.push('', '## 遊ばれ方（ゲームの記録）');
L.push(`- 対戦（王座戦以外）  ${n(pw.n)}戦 ${diff(pw.n, pp.n)}、遊んだブラウザ（日ごとの延べ） ${n(pw.u)} ${diff(pw.u, pp.u)}`);
// 遊び方ごとの内訳（日ごとの合計から）
try {
  const KQ = "SELECT " + ['t', 'm', 'f', 'd'].map(x => `COALESCE(SUM(CASE WHEN k = '${x}' THEN n END), 0) AS ${x}`).join(', ') + " FROM daily_stats WHERE ev = 'play' AND day >= ? AND day < ?";
  const [kw, kp] = await Promise.all([one(KQ, DW), one(KQ, DP)]);
  L.push(`  - 今日の一戦 ${n(kw.t)}戦 ${diff(kw.t, kp.t)}`, `  - あなたの代表戦 ${n(kw.m)}戦 ${diff(kw.m, kp.m)}`, `  - 仲間さがしから ${n(kw.f)}戦 ${diff(kw.f, kp.f)}`, `  - 百科ダンジョン ${n(kw.d)}戦 ${diff(kw.d, kp.d)}`,
    `  - 自由対戦 ${n(pw.n - kw.t - kw.m - kw.f - kw.d)}戦 ${diff(pw.n - kw.t - kw.m - kw.f - kw.d, pp.n - kp.t - kp.m - kp.f - kp.d)}`);
  globalThis.KW = kw;
} catch (_) {}
// ---------- 開いた人から遊んだ人まで（日ごとの合計から。同じ人が2日来れば2と数える） ----------
try {
  const VQ = "SELECT COALESCE(SUM(n), 0) AS v, COALESCE(SUM(CASE WHEN k = 'new' THEN n END), 0) AS nw, COALESCE(SUM(CASE WHEN k IN ('d1', 'w') THEN n END), 0) AS rt, COALESCE(SUM(CASE WHEN dev = 'm' THEN n END), 0) AS mb FROM daily_stats WHERE ev = 'visit' AND day >= ? AND day < ?";
  const RQ = "SELECT " + ['1', '2', '4', '10'].map(x => `COALESCE(SUM(CASE WHEN k = '${x}' THEN n END), 0) AS p${x}`).join(', ') + " FROM daily_stats WHERE ev = 'reach' AND day >= ? AND day < ?";
  const [vw, vp, fw, refs] = await Promise.all([one(VQ, DW), one(VQ, DP), one(RQ, DW),
    q("SELECT k AS ref, SUM(n) AS u FROM daily_stats WHERE ev = 'ref' AND day >= ? AND day < ? GROUP BY k ORDER BY u DESC LIMIT 6", DW)]);
  if (vw.v) {
    const pc = x => Math.round(x / vw.v * 100);
    L.push(`- 開いたブラウザ（日ごとの延べ） ${n(vw.v)} ${diff(vw.v, vp.v)}（初めて ${n(vw.nw)}・1週間以内にまた来た ${n(vw.rt)}・スマホ ${n(vw.mb)}）`);
    L.push(`  - その日に1戦以上 ${n(fw.p1)}（${pc(fw.p1)}%）、2戦以上 ${n(fw.p2)}（${pc(fw.p2)}%）、4戦以上 ${n(fw.p4)}（${pc(fw.p4)}%）、10戦以上 ${n(fw.p10)}（${pc(fw.p10)}%）`);
    L.push('  - 来た元：' + (refs.length ? refs.map(r => `${r.ref} ${n(r.u)}`).join('、') + '、ほかは直接・不明' : '直接・不明のみ'));
  }
} catch (_) {}
// ---------- 都道府県の応援（2026年11月21日から数えている。表がまだなければ出さない） ----------
try {
  const jd = d => new Date(+d + JST).toISOString().slice(0, 10), DW = [jd(start), jd(end)], DP = [jd(pstart), jd(start)];
  const EQ = "SELECT COALESCE(SUM(CASE WHEN k = 'pb' THEN n END), 0) AS pb, COALESCE(SUM(CASE WHEN k = 'in' THEN n END), 0) AS i, COALESCE(SUM(CASE WHEN k = 'sh' THEN n END), 0) AS sh FROM pref_ev WHERE day >= ? AND day < ?";
  const [ew, ep, top] = await Promise.all([one(EQ, DW), one(EQ, DP),
    q("SELECT pref, SUM(CASE WHEN k = 'pb' THEN n ELSE 0 END) AS pb, SUM(CASE WHEN k = 'in' THEN n ELSE 0 END) AS i, SUM(CASE WHEN k = 'sh' THEN n ELSE 0 END) AS sh FROM pref_ev WHERE day >= ? AND day < ? GROUP BY pref ORDER BY pb + i DESC LIMIT 5", DW)]);
  if (ew.pb || ew.i || ew.sh) {
    L.push(`- 都道府県の応援：応援試合 ${n(ew.pb)}戦 ${diff(ew.pb, ep.pb)}、結果の共有 ${n(ew.sh)}回 ${diff(ew.sh, ep.sh)}、共有されたURLから来た ${n(ew.i)}人 ${diff(ew.i, ep.i)}`);
    L.push('  - よく応援された県：' + top.map(r => `${r.pref}（応援${n(r.pb)}・共有${n(r.sh)}・来た${n(r.i)}）`).join('、'));
  }
} catch (_) {}
L.push(`- 王座戦の挑戦 ${n(cw.n)}回 ${diff(cw.n, cp.n)}、王座奪取 ${n(cw.w)}回`);
if (daily.length) L.push('- 日別の対戦（王座戦以外）：' + daily.map(r => `${+r.d.slice(5, 7)}/${+r.d.slice(8)} ${n(r.n)}`).join('、'));
if (topCh.length) L.push('- よく挑まれた記事：' + topCh.map(r => `${r.display} ${r.n}回`).join('、'));
L.push('', '## 王座');
if (changes.length) L.push(`- 今週の王座交代 ${changes.length}回：` + changes.map(r => r.display + who(r.holder)).join(' → '));
else L.push('- 今週の王座交代はありませんでした');
if (champ.id) L.push(`- いまの王者：${champ.display}${who(champ.holder)} 防衛${champ.defenses}回、${md(new Date(champ.started_at))}から`);
// ---------- 未対応の報告（数字や事実の誤りは、ここにまとめて載せる。不適切の報告は届いたときにも通知済み） ----------
let reps = null;
try {
  reps = await q("SELECT kind, reason, title, a, b, target, fk, fv, GROUP_CONCAT(DISTINCT NULLIF(fix, '')) AS fix, GROUP_CONCAT(DISTINCT NULLIF(url, '')) AS url, GROUP_CONCAT(DISTINCT NULLIF(text, '')) AS text, COUNT(DISTINCT iphash) AS people, MIN(at) AS first FROM reports WHERE status = 'new' GROUP BY rkey ORDER BY kind DESC, people DESC, first");
} catch (_) {}   // 報告の表がまだない
const RS = { fact: '数字や事実', dis: '差別的・攻撃的', subj: '扱いがふさわしくない題材', other: 'その他' };
if (reps && reps.length) {
  L.push('', `## 未対応の報告 ${reps.length}件`);
  for (const r of reps) {
    const who = r.target === 'text' ? `実況の文面（${r.a} 対 ${r.b}）` : r.title || r.a;
    const ppl = r.people > 1 ? `（${r.people}人）` : '';
    if (r.kind === 'num') L.push(`- 数字：${who}｜${r.fk || '—'}｜${r.fv || '—'} → ${r.fix || '（正しい値の記入なし）'}${ppl}${r.url ? '｜出典あり' : ''}${r.text ? '｜ひとことあり' : ''}`);
    else L.push(`- 内容：${who}｜${RS[r.reason] || 'その他'}${ppl}${r.people >= 2 && r.target !== 'text' ? '｜一時的に外し中' : ''}${r.text ? '｜ひとことあり' : ''}`);
  }
  L.push('', '出典・ひとことは、Cloudflare の管理画面の D1（hyakka-kenten）のコンソールで見られます（ここは誰でも見られるので出しません）。', '直すときは「報告を反映して」と頼めば、出典を確かめて訂正表（data/fix.json）に足します。問題がなかったものは status を ok に');
}
L.push('', `累計：対戦（王座戦以外） ${n(tot.plays)}戦・王座戦 ${n(tot.ch)}回・歴代王者 ${n(tot.reigns)}代`);
const md_ = L.join('\n');
console.log(md_);
if (GITHUB_STEP_SUMMARY) appendFileSync(GITHUB_STEP_SUMMARY, md_ + '\n');

// ---------- 通知（短く） ----------
if (NTFY_TOPIC) {
  const a = rum ? v(rum.tw) : null, b = rum ? v(rum.tp) : null;
  const msg = [
    a ? `訪問 ${n(a.visits)} ${diff(a.visits, b.visits)}` : '訪問数は取得できませんでした',
    `対戦 ${n(pw.n)}戦 ${diff(pw.n, pp.n)}` + (globalThis.KW ? `（今日の一戦 ${n(KW.t)}・代表戦 ${n(KW.m)}）` : ''),
    `王座戦 ${n(cw.n)}回・王座交代 ${changes.length}回`,
    champ.id ? `王者：${champ.display}（防衛${champ.defenses}回）` : '',
    reps && reps.length ? `未対応の報告 ${reps.length}件` : '',
  ].filter(Boolean).join('\n') + (RUN_URL ? '\n\nタップすると詳しいレポートが開きます' : '');
  const r = await fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
    topic: NTFY_TOPIC, title: `百科拳典 週間レポート ${range}`, message: msg, tags: ['bar_chart'], ...(RUN_URL ? { click: RUN_URL } : {}) }) });
  console.log('通知', r.status);
}
