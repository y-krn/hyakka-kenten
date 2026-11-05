// 週1回のアクセスレポート
//   ゲームの記録（D1）と、Cloudflare Web Analytics の訪問数を、先週と比べてまとめる。
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
const one = async (sql, p) => (await q(sql, p))[0] || {};
const PLAYS = 'SELECT COALESCE(SUM(n),0) AS n, COUNT(DISTINCT COALESCE(client, iphash)) AS u FROM plays WHERE at >= ? AND at < ?';
const CH = "SELECT COUNT(*) AS n, COUNT(DISTINCT COALESCE(client, iphash)) AS u, COALESCE(SUM(result = 'win'),0) AS w FROM challenges WHERE at >= ? AND at < ? AND result <> 'late'";
const [pw, pp, cw, cp, champ, changes, topCh, daily, tot] = await Promise.all([
  one(PLAYS, W), one(PLAYS, P), one(CH, W), one(CH, P),
  one('SELECT id, display, holder, defenses, started_at FROM reigns WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1'),
  q('SELECT id, display, holder, ended_by FROM reigns WHERE started_at >= ? AND started_at < ? ORDER BY id', W),
  q("SELECT display, COUNT(*) AS n FROM challenges WHERE at >= ? AND at < ? AND result <> 'late' GROUP BY title ORDER BY n DESC, MIN(id) LIMIT 5", W),
  q("SELECT date(datetime(at, '+9 hours')) AS d, SUM(n) AS n FROM plays WHERE at >= ? AND at < ? GROUP BY d ORDER BY d", W),
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
L.push(`- 対戦（王座戦以外）  ${n(pw.n)}戦 ${diff(pw.n, pp.n)}、遊んだブラウザ ${n(pw.u)} ${diff(pw.u, pp.u)}`);
// 遊び方ごとの内訳（2026年11月5日から数えている。内訳の列がまだなければ出さない）
try {
  const KQ = "SELECT COALESCE(SUM(kt),0) AS t, COALESCE(SUM(km),0) AS m, COALESCE(SUM(kf),0) AS f, COUNT(DISTINCT CASE WHEN kt > 0 THEN COALESCE(client, iphash) END) AS tu, COUNT(DISTINCT CASE WHEN km > 0 THEN COALESCE(client, iphash) END) AS mu, COUNT(DISTINCT CASE WHEN kf > 0 THEN COALESCE(client, iphash) END) AS fu FROM plays WHERE at >= ? AND at < ?";
  const [kw, kp] = await Promise.all([one(KQ, W), one(KQ, P)]);
  const free = pw.n - kw.t - kw.m - kw.f, freeP = pp.n - kp.t - kp.m - kp.f;
  L.push(`  - 今日の一戦 ${n(kw.t)}戦 ${diff(kw.t, kp.t)}（${n(kw.tu)}ブラウザ）`, `  - あなたの代表戦 ${n(kw.m)}戦 ${diff(kw.m, kp.m)}（${n(kw.mu)}ブラウザ）`, `  - 仲間図鑑から ${n(kw.f)}戦 ${diff(kw.f, kp.f)}（${n(kw.fu)}ブラウザ）`, `  - 自由対戦 ${n(free)}戦 ${diff(free, freeP)}`);
  if (start < new Date('2026-11-12T15:00:00Z')) L.push('  - ※内訳は11月5日夜から数え始めたので、この週と前の週の比べは参考になりません');
  globalThis.KW = kw;
} catch (_) {}
L.push(`- 王座戦の挑戦 ${n(cw.n)}回 ${diff(cw.n, cp.n)}、挑んだブラウザ ${n(cw.u)}、王座奪取 ${n(cw.w)}回`);
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
    if (r.kind === 'num') L.push(`- 数字：${who}｜${r.fk || '—'}｜${r.fv || '—'} → ${r.fix || '（正しい値の記入なし）'}${ppl}${r.url ? ' 出典：' + r.url : ''}${r.text ? ' ひとこと：' + r.text : ''}`);
    else L.push(`- 内容：${who}｜${RS[r.reason] || 'その他'}${ppl}${r.people >= 2 && r.target !== 'text' ? '｜一時的に外し中' : ''}${r.text ? ' ひとこと：' + r.text : ''}`);
  }
  L.push('', '直すときは「報告を反映して」と頼めば、出典を確かめて訂正表（data/fix.json）に足します。問題がなかったものは status を ok に');
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
