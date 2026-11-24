// 百科拳典 王座戦API（Cloudflare Workers + D1）
//   GET  /api/throne            … いまの王者・最近の挑戦
//   GET  /api/hall              … 王者の殿堂：全部の王者と記録（王者キラー・最も挑まれた王者）
//   POST /api/challenge         … {title, name} で王者に挑む。勝敗はサーバーで計算し直して決める
//   POST /api/report            … {reason, a, b, target, fact?, fix?, text?, url?} 利用者からの報告（数字や事実の誤り・内容が不適切）
//   GET  /api/holds             … 報告を受けて、確かめるまで今日の一戦とランダムに出さない記事
//   POST /api/visit             … {client, ref, mob, fresh} ページを開いたブラウザを1日1回数える（どこから来たか・スマホか・初めてか）
//   POST /api/plays             … {n, k:{t,m,f,d}, client} 自由対戦などの対戦数（ブラウザでまとめて数えたもの）を足す。k は遊び方ごとの内訳
//   GET  /og/c/番号.jpg          … 王座戦の試合ごとの共有画像
//   GET  /api/og/pending        … 画像がまだない挑戦の一覧（管理用。GitHub Actions が使う）
//   GET  /api/throne/day?d=日付  … その日の王座戦のまとめ（交代の回数・挑戦の数・いちばん防衛した王者・いまの王者）
//   PUT  /api/og/番号            … 作った画像を預ける（管理用）
//   GET  /og/t/日付.jpg          … 今日の一戦の共有画像（毎日0時すぎに GitHub Actions が作る）
//   PUT  /api/og/today/日付?a=&b= … 今日の一戦の共有画像を預ける（管理用）
//   POST /api/admin/hide        … {id} 不適切な名前を非表示にする（ヘッダー Authorization: Bearer ADMIN_TOKEN）
//   POST /api/admin/cleanup     … 毎晩の片付けを手で動かす（同じく ADMIN_TOKEN）
//   GET  /sitemap.xml           … 検索エンジン向けの一覧（トップ・王座戦の試合の記録・仲間さがしの一門・県の応援の入口）。1日覚えておく
//   GET  / （?c=番号 / ?a=記事&b=記事） … ゲームの画面。共有カード（OGP）の文字だけ、その試合用に書き換えて返す
//   それ以外（data/ や画像）は静的ファイルとしてそのまま配る（Workerを通らないので無料枠を使わない）
import * as E from './engine.mjs';

const SEED = '東京タワー';                 // 王者がいないときの初代
const MAX_NAME = 16;
const LIMIT_10MIN = 10, LIMIT_DAY = 100;   // ブラウザ1つあたりの挑戦回数
const IP_10MIN = 60, IP_DAY = 500;         // 同じ回線（IPアドレス）全体の上限。携帯回線などは大勢で共有されるので緩めにする
// 名前の禁止語（部分一致。表記ゆれを減らすため、比べる前に正規化する）
const NG = ['死ね', 'しね', '殺す', 'ころす', 'きちがい', 'キチガイ', 'ガイジ', 'がいじ', '障害者', 'ちんこ', 'ちんぽ', 'まんこ', 'おまんこ', 'セックス', 'sex', 'fuck', 'shit', 'nigger', 'nigga', 'faggot', 'rape', 'レイプ', '強姦', '朝鮮人',  'シナ人', '支那', '部落', '在日', 'hitler', 'ヒトラー', 'http', 'www.', '.com', '.jp'];

let META = null, METAAT = 0;
// 記事データは、同じWorkerが配っている静的ファイルから直接読む（無ければ DATA_BASE のURLから）
const ABASE = 'https://assets.local/data/';
const dataBase = env => env.ASSETS ? ABASE : env.DATA_BASE;
const dfetch = (env, u) => env.ASSETS ? env.ASSETS.fetch(u) : fetch(u);
async function meta(env) {
  if (META && Date.now() - METAAT < 600000) return META;
  const [m, ex] = await Promise.all([
    dfetch(env, dataBase(env) + 'meta.json?t=' + Date.now()).then(r => r.json()),
    dfetch(env, dataBase(env) + 'exclude.json?t=' + Date.now()).then(r => r.ok ? r.json() : []).catch(() => []),
  ]);
  META = m; METAAT = Date.now();
  E.setup({ base: dataBase(env), fetch: u => dfetch(env, u), nb: m.nb, ver: m.build || m.asof, excl: ex });
  return m;
}

const now = () => new Date().toISOString();
function cors(env, req) {
  const o = req.headers.get('Origin') || '';
  const ok = (env.ALLOWED_ORIGINS || '').split(',').map(x => x.trim()).filter(Boolean);
  return { 'Access-Control-Allow-Origin': ok.includes(o) ? o : ok[0] || '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type,Authorization', 'Vary': 'Origin' };
}
const json = (env, req, body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...cors(env, req) } });

function cleanName(n) {
  n = String(n || '').normalize('NFKC').replace(/[\u0000-\u001f\u007f<>]/g, '').replace(/\s+/g, ' ').trim().slice(0, MAX_NAME);
  if (!n) return { name: '名無しの挑戦者' };
  const low = n.toLowerCase().replace(/[\s._\-・]/g, '');
  const kata = low.replace(/[ぁ-ゖ]/g, c => String.fromCharCode(c.charCodeAt(0) + 0x60));
  if (NG.some(w => { const x = w.toLowerCase(); return low.includes(x) || kata.includes(x.replace(/[ぁ-ゖ]/g, c => String.fromCharCode(c.charCodeAt(0) + 0x60))); })) return { error: 'その名前は使えません。別の名前にしてください。' };
  return { name: n };
}
async function ipHash(env, req) {
  const ip = req.headers.get('CF-Connecting-IP') || 'local';
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode((env.IP_SALT || 'dev') + '|' + ip));
  return [...new Uint8Array(d)].slice(0, 12).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function current(env) {
  let c = await env.DB.prepare('SELECT * FROM reigns WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1').first();
  if (!c) {   // 初代王者を置く
    await meta(env); const i = await E.loadOne(SEED); const inf = i >= 0 ? E.info(i) : { title: SEED, name: SEED };
    await env.DB.prepare('INSERT INTO reigns (title, display, holder, started_at, defenses) VALUES (?,?,?,?,0)').bind(inf.title, inf.name, '初代', now()).run();
    c = await env.DB.prepare('SELECT * FROM reigns WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1').first();
  }
  return c;
}

// 王座戦の情報は、データベースで集計した結果を15秒だけ使い回す（大勢が見ても集計は15秒に1回。挑戦があったら捨てる）
const TH_KEY = 'https://hyakkakenten.com/__cache/throne';
async function throne(env, req, ctx) {
  try { const hit = await caches.default.match(TH_KEY); if (hit) return json(env, req, await hit.json()); } catch (_) {}
  const body = await throneBody(env);
  try { const put = caches.default.put(TH_KEY, new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=15' } })); if (ctx) ctx.waitUntil(put); } catch (_) {}
  return json(env, req, body);
}
async function throneBody(env) {
  const c = await current(env);
  const [recent] = await env.DB.batch([
    env.DB.prepare('SELECT c.id, c.reign_id, c.display, c.title, c.name, c.result, c.how, c.at, r.display AS cdisplay FROM challenges c JOIN reigns r ON r.id = c.reign_id ORDER BY c.id DESC LIMIT 15'),
  ]);
  const [pl, ch] = await env.DB.batch([
    env.DB.prepare("SELECT n FROM stats WHERE k = 'plays'"),
    env.DB.prepare('SELECT COALESCE(MAX(id), 0) AS n FROM challenges'),   // 挑戦の数。記録は消さないので、いちばん新しい番号＝数（COUNT は全部の行を読むので使わない）
  ]);
  return { champ: c, reignNo: c.id, recent: recent.results,   // 最長防衛・歴代王者は /api/hall（王者の殿堂）へ移した
    count: { plays: (pl.results[0] || {}).n || 0, throne: (ch.results[0] || {}).n || 0 } };
}

// 王者の殿堂：全部の王者（殿堂入り・最長在位はページ側で計算）と、集計が要る記録。60秒だけ使い回す（挑戦があったら捨てる）
const HALL_KEY = 'https://hyakkakenten.com/__cache/hall';
async function hall(env, req, ctx) {
  try { const hit = await caches.default.match(HALL_KEY); if (hit) return json(env, req, await hit.json()); } catch (_) {}
  await current(env);
  const [reigns, killer, most] = await env.DB.batch([
    env.DB.prepare("SELECT id, display, title, holder, started_at, ended_at, defenses, ended_by, (SELECT c.id FROM challenges c WHERE c.result = 'win' AND c.title = reigns.title AND c.reign_id < reigns.id ORDER BY c.id DESC LIMIT 1) AS cid, (SELECT c.id FROM challenges c WHERE c.reign_id = reigns.id AND c.result = 'win' ORDER BY c.id LIMIT 1) AS lostcid FROM reigns ORDER BY id DESC LIMIT 2000"),
    env.DB.prepare("SELECT title, MAX(display) AS display, COUNT(*) AS n FROM challenges WHERE result = 'win' GROUP BY title ORDER BY n DESC, MIN(id) ASC LIMIT 3"),
    env.DB.prepare("SELECT r.id, r.display, r.title, COUNT(*) AS n FROM challenges c JOIN reigns r ON r.id = c.reign_id WHERE c.result != 'late' GROUP BY r.id ORDER BY n DESC, r.id ASC LIMIT 3"),
  ]);
  const body = { reigns: reigns.results, killer: killer.results, most: most.results, now: now() };
  try { const put = caches.default.put(HALL_KEY, new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=60' } })); if (ctx) ctx.waitUntil(put); } catch (_) {}
  return json(env, req, body);
}

async function challenge(env, req, ctx) {
  let body; try { body = await req.json(); } catch (_) { return json(env, req, { error: '送信内容を読めませんでした' }, 400); }
  const title = String(body.title || '').trim().slice(0, 200);
  if (!title) return json(env, req, { error: '挑戦する記事名を入れてください' }, 400);
  const nm = cleanName(body.name); if (nm.error) return json(env, req, { error: nm.error }, 400);
  const ih = await ipHash(env, req);
  // ブラウザごとの番号（ページが端末に保存している乱数）。無い・形が違うときは回線単位の厳しい上限だけで数える
  const cl = /^[a-z0-9]{16,40}$/.test(String(body.client || '')) ? await ipHash(env, { headers: { get: () => 'client:' + body.client } }) : null;
  const t10 = new Date(Date.now() - 600000).toISOString(), t24 = new Date(Date.now() - 86400000).toISOString();
  const cnt = async (col, v) => env.DB.prepare('SELECT SUM(CASE WHEN at > ? THEN 1 ELSE 0 END) AS m10, COUNT(*) AS d FROM challenges WHERE ' + col + ' = ? AND at > ?').bind(t10, v, t24).first();
  const byIp = await cnt('iphash', ih);
  if (cl) {
    const byCl = await cnt('client', cl);
    if ((byCl.m10 || 0) >= LIMIT_10MIN) return json(env, req, { error: '挑戦が続いています。10分ほど待ってから、また挑んでください。' }, 429);
    if ((byCl.d || 0) >= LIMIT_DAY) return json(env, req, { error: '今日の挑戦回数の上限に達しました。また明日どうぞ。' }, 429);
    if ((byIp.m10 || 0) >= IP_10MIN || (byIp.d || 0) >= IP_DAY) return json(env, req, { error: 'この回線からの挑戦が集中しています。しばらく待ってから挑んでください。' }, 429);
  } else {
    if ((byIp.m10 || 0) >= LIMIT_10MIN) return json(env, req, { error: '挑戦が続いています。10分ほど待ってから、また挑んでください。' }, 429);
    if ((byIp.d || 0) >= LIMIT_DAY) return json(env, req, { error: '今日の挑戦回数の上限に達しました。また明日どうぞ。' }, 429);
  }

  await meta(env);
  const c = await current(env);
  // 挑戦者が「どの王者に挑むつもりか」を送ってきた場合、すでに入れ替わっていたら勝負せずに知らせる（記録もしない）
  const want = parseInt(body.reign, 10);
  if (want && want !== c.id) return json(env, req, { error: '王者が「' + c.display + '」に変わりました。もう一度「挑戦する」を押すと、' + c.display + 'に挑みます。', changed: true, champ: { id: c.id, title: c.title, display: c.display, defenses: c.defenses } }, 409);
  const bi = await E.loadOne(title);
  if (bi < 0) return json(env, req, { error: '「' + title + '」は収録していません' }, 404);
  const B = E.info(bi);
  if (B.blocked) return json(env, req, { error: '「' + B.name + '」は確認中のため挑戦できません' }, 400);
  if (B.title === c.title) return json(env, req, { error: 'それはいまの王者です' }, 400);
  // 同じ組み合わせの王座戦は一度きり（どちらが王者だったかは問わない）。勝敗は記事のデータで決まり、何度やっても同じなので、
  // 三すくみの記事を順に出して王座を回し続けることもできなくなる
  const met = await env.DB.prepare(`SELECT c.id, c.result, c.title, c.display, r.title AS ctitle, r.display AS cdisplay FROM challenges c JOIN reigns r ON r.id = c.reign_id
      WHERE (c.title = ? AND r.title = ?) OR (c.title = ? AND r.title = ?) ORDER BY c.id DESC LIMIT 1`).bind(B.title, c.title, c.title, B.title).first();
  if (met) {
    const w = met.result === 'draw' ? null : (met.result === 'win' || met.result === 'late') ? met.display : met.cdisplay;
    return json(env, req, { error: '「' + B.name + '」と「' + c.display + '」は、すでに王座戦で戦っています（' + (w ? w + 'の勝ち' : '引き分け') + '）。結果は何度やっても同じなので、別の記事で挑んでください。', known: { id: met.id, result: met.result } }, 409);
  }

  const ai = await E.loadOne(c.title);
  let v, result;
  if (ai < 0 || E.info(ai).blocked) { v = { w: B.title, kind: '不戦勝', how: '王者が収録から外れていたため不戦勝' }; }
  else v = E.verdict(ai, bi);
  result = v.w === B.title ? 'win' : v.w === null ? 'draw' : 'lose';
  const t = now();
  const ins = await env.DB.prepare('INSERT OR IGNORE INTO challenges (reign_id, title, display, name, result, how, at, iphash, client) VALUES (?,?,?,?,?,?,?,?,?)')
    .bind(c.id, B.title, B.name, nm.name, result, v.how, t, ih, cl).run();
  if (!ins.meta.changes) {   // ほぼ同時に、別の人が同じ記事で同じ王者に挑んでいた（同じ組み合わせは1回まで）
    const same = await env.DB.prepare('SELECT id FROM challenges WHERE reign_id = ? AND title = ?').bind(c.id, B.title).first();
    return json(env, req, { error: '同じ記事での挑戦が、ほぼ同時に別の人から届いていました。結果は同じなので、その試合を見てください。', known: same ? { id: same.id } : null }, 409);
  }
  let newReign = null, gone = false;   // gone：勝敗を決めているあいだに、王者が別の挑戦者に倒されていた
  if (result === 'win') {
    const up = await env.DB.prepare('UPDATE reigns SET ended_at = ?, ended_by = ? WHERE id = ? AND ended_at IS NULL').bind(t, B.name, c.id).run();
    if (up.meta.changes) {
      await env.DB.prepare('INSERT INTO reigns (title, display, holder, started_at, defenses) VALUES (?,?,?,?,0)').bind(B.title, B.name, nm.name, t).run();
      newReign = true;
    } else {   // ほぼ同時に別の人が王者を倒していた：記録も「ひと足遅れ」に直す
      result = 'late'; await env.DB.prepare("UPDATE challenges SET result = 'late' WHERE id = ?").bind(ins.meta.last_row_id).run();
    }
  } else {
    const df = await env.DB.prepare('UPDATE reigns SET defenses = defenses + 1 WHERE id = ? AND ended_at IS NULL').bind(c.id).run();
    if (!df.meta.changes) gone = true;   // 防衛には数えない（記録は「元王者に負けた・引き分けた」として残る）
  }
  try { await caches.default.delete(TH_KEY); await caches.default.delete(HALL_KEY); } catch (_) {}   // 使い回している王座戦の情報を捨てる（すぐ新しい結果が見えるように）
  if (ctx) ctx.waitUntil(askImage(env, { id: ins.meta.last_row_id }));   // 共有画像を作ってもらう（失敗しても挑戦には影響しない。1時間ごとの定期実行でも拾う）
  const after = await env.DB.prepare('SELECT defenses FROM reigns WHERE id = ?').bind(c.id).first();   // 同時の挑戦があっても、実際の防衛回数を返す
  let nowC = null;   // ひと足遅れ・王者がもう倒されていたとき：いまの王者を知らせる（そのまま挑み直せるように）
  if (result === 'late' || gone) { const n = await current(env); nowC = { id: n.id, title: n.title, display: n.display, holder: n.holder }; }
  return json(env, req, { id: ins.meta.last_row_id, reignNo: c.id, result, gone, now: nowC, newChamp: !!newReign, champ: { id: c.id, title: c.title, display: c.display, defenses: after ? after.defenses : c.defenses }, challenger: { title: B.title, display: B.name }, how: v.how, kind: v.kind, name: nm.name });
}

// 1つの挑戦の記録（共有URL ?c=番号 で、その試合を再生するため）
async function getChallenge(env, req, id) {
  const x = await env.DB.prepare('SELECT c.id, c.reign_id, c.title, c.display, c.name, c.result, c.how, c.at, r.title AS ctitle, r.display AS cdisplay FROM challenges c JOIN reigns r ON r.id = c.reign_id WHERE c.id = ?').bind(id).first();
  if (!x) return json(env, req, { error: 'その挑戦の記録はありません' }, 404);
  const d = await env.DB.prepare("SELECT COUNT(*) AS n FROM challenges WHERE reign_id = ? AND id <= ? AND result IN ('lose','draw')").bind(x.reign_id, x.id).first();
  return json(env, req, { id: x.id, reignNo: x.reign_id, result: x.result, how: x.how, at: x.at, name: x.name,
    champ: { title: x.ctitle, display: x.cdisplay, defenses: d.n }, challenger: { title: x.title, display: x.display } });
}

// 自由対戦の対戦数を足す。誰でも送れるので、1回に送れる数と回数に上限を付けて、極端な水増しだけ防ぐ
const PLAYS_MAX = 30;                       // 1回に送れる対戦数
const PLAYS_CL_10MIN = 120, PLAYS_IP_10MIN = 1200;   // 10分あたりに足せる対戦数（ブラウザ1つ／同じ回線全体）
async function plays(env, req) {
  let body; try { body = JSON.parse(await req.text()); } catch (_) { return json(env, req, { error: 'bad' }, 400); }
  const n = Math.min(PLAYS_MAX, Math.floor(Number(body.n)));
  if (!(n >= 1)) return json(env, req, { error: 'bad' }, 400);
  const ih = await ipHash(env, req);
  const cl = /^[a-z0-9]{16,40}$/.test(String(body.client || '')) ? await ipHash(env, { headers: { get: () => 'client:' + body.client } }) : null;
  const t10 = new Date(Date.now() - 600000).toISOString();
  const [a, b] = await env.DB.batch([
    cl ? env.DB.prepare('SELECT COALESCE(SUM(n), 0) AS s FROM plays WHERE client = ? AND at > ?').bind(cl, t10)
       : env.DB.prepare('SELECT COALESCE(SUM(n), 0) AS s FROM plays WHERE iphash = ? AND client IS NULL AND at > ?').bind(ih, t10),   // 番号なしは回線ごとに厳しく
    env.DB.prepare('SELECT COALESCE(SUM(n), 0) AS s FROM plays WHERE iphash = ? AND at > ?').bind(ih, t10),
  ]);
  const room = Math.min((cl ? PLAYS_CL_10MIN : PLAYS_MAX) - a.results[0].s, PLAYS_IP_10MIN - b.results[0].s);
  const add = Math.min(n, room);
  if (add <= 0) return json(env, req, { ok: false });
  // 遊び方ごとの内訳（今日の一戦 t・あなたの代表戦 m・仲間図鑑から f・百科ダンジョン d。残りが自由対戦）。合わせて add を超えないように
  const kk = body.k && typeof body.k === 'object' ? body.k : {}; let left = add; const K = {};
  for (const x of ['t', 'm', 'f', 'd']) { const v = Math.min(left, Math.max(0, Math.floor(Number(kk[x]) || 0))); K[x] = v; left -= v; }
  const st = env.DB.prepare("INSERT INTO stats (k, n) VALUES ('plays', ?) ON CONFLICT(k) DO UPDATE SET n = n + excluded.n").bind(add);
  try { await env.DB.batch([env.DB.prepare('INSERT INTO plays (n, at, iphash, client, kt, km, kf, kd) VALUES (?,?,?,?,?,?,?,?)').bind(add, now(), ih, cl, K.t, K.m, K.f, K.d), st]); }
  catch (_) { try { await env.DB.batch([env.DB.prepare('INSERT INTO plays (n, at, iphash, client, kt, km, kf) VALUES (?,?,?,?,?,?,?)').bind(add, now(), ih, cl, K.t, K.m, K.f), st]); }   // ダンジョンの列がまだないとき
  catch (_) { await env.DB.batch([env.DB.prepare('INSERT INTO plays (n, at, iphash, client) VALUES (?,?,?,?)').bind(add, now(), ih, cl), st]); } }   // 内訳の列がまだないとき
  try { await prefCount(env, req, body.r, add); } catch (_) {}   // 県対抗（表がまだないときなどは数えずに進む）
  { const dev = body.mob ? 'm' : 'd', src = ['mugen', 'x', 'search', 'direct', 'other'].includes(body.s) ? body.s : 'other';
    for (const x of ['t', 'm', 'f', 'd']) if (K[x]) evPoint(env, 'play', x, dev, src, '', '', K[x]);
    if (left > 0) evPoint(env, 'play', 'free', dev, src, '', '', left);
    for (const r of (Array.isArray(body.rs) ? body.rs : []).slice(0, 4)) if ([1, 2, 4, 10].includes(r)) evPoint(env, 'reach', r, dev, src, '', '', 1); }
  return json(env, req, { ok: true, added: add });
}

// 都道府県の応援：県対抗の集計
//   ブラウザは対戦数と一緒に、試合結果 [勝った記事, 負けた記事, 応援した県] を送ってくる（受け付けた対戦数まで）
//   記事を県に読み替える対応表は data/pref/map/NN.json（記事名のハッシュで64個に分けたもの。tools/pref_roster.py が作る）。要る分だけ読み、1時間覚えておく
//   月ごと（日本時間）に県の勝ち・負け・応援の数を足す
const PREFS = '北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県'.split(' ');
function prefShard(t) { let h = 2166136261; for (const ch of t) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619) >>> 0; } return h % 64; }   // FNV-1a（tools/pref_roster.py と同じ）
const PMAP = new Map();   // 番号 → { t: 読んだ時刻, m: 対応表 }
async function prefOf(env, req, t) {
  if (!t) return [];
  const k = prefShard(t); let e = PMAP.get(k);
  if (!e || Date.now() - e.t > 3600e3) {
    const r = await env.ASSETS.fetch(new Request(new URL('/data/pref/map/' + String(k).padStart(2, '0') + '.json', req.url)));
    e = { t: Date.now(), m: r.ok ? await r.json() : {} }; PMAP.set(k, e);
  }
  return (e.m[t] || []).map(i => PREFS[i]).filter(Boolean);
}
const prefDay = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
// 効果を測る：県ごと・日ごとの数（k = in：?pref=県名 のURLから来た、sh：応援試合の結果を共有した、pb：応援試合）
const prefEvStmt = (env, d, p, k, n) => env.DB.prepare('INSERT INTO pref_ev (day, pref, k, n) VALUES (?,?,?,?) ON CONFLICT(day, pref, k) DO UPDATE SET n = n + excluded.n').bind(d, p, k, n);
async function prefEvApi(env, req) {
  let b; try { b = JSON.parse(await req.text()); } catch (_) { return json(env, req, { error: 'bad' }, 400); }
  if (!['in', 'sh'].includes(b.k) || !PREFS.includes(b.p)) return json(env, req, { error: 'bad' }, 400);
  try { await prefEvStmt(env, prefDay(), b.p, b.k, 1).run(); } catch (_) {}
  return json(env, req, { ok: true });
}
const prefMonth = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 7);
async function prefCount(env, req, rs, add) {
  if (!Array.isArray(rs) || !rs.length || !env.ASSETS) return;
  const W = new Map(), inc = (p, k) => { const o = W.get(p) || { w: 0, l: 0, c: 0 }; o[k]++; W.set(p, o); };
  for (const x of rs.slice(0, add)) {
    if (!Array.isArray(x)) continue; const [w, l, c] = x.map(v => String(v || '').slice(0, 200));
    const pw = new Set(await prefOf(env, req, w)), pl = new Set(await prefOf(env, req, l));
    for (const p of pw) if (!pl.has(p)) inc(p, 'w');   // 同じ県の記事どうしの試合は数えない
    for (const p of pl) if (!pw.has(p)) inc(p, 'l');
    if (c && PREFS.includes(c)) inc(c, 'c');
  }
  try { const d = prefDay(), C = [...W].filter(([, o]) => o.c); if (C.length) await env.DB.batch(C.map(([p, o]) => prefEvStmt(env, d, p, 'pb', o.c))); } catch (_) {}   // 効果を測る：日ごとの応援試合の数
  if (!W.size) return;
  const m = prefMonth();
  await env.DB.batch([...W].map(([p, o]) => env.DB.prepare('INSERT INTO pref_month (month, pref, w, l, c) VALUES (?,?,?,?,?) ON CONFLICT(month, pref) DO UPDATE SET w = w + excluded.w, l = l + excluded.l, c = c + excluded.c').bind(m, p, o.w, o.l, o.c)));
}
async function prefBoardApi(env, req) {
  const m = prefMonth();
  let rows = [];
  try { rows = (await env.DB.prepare('SELECT pref AS p, w, l, c FROM pref_month WHERE month = ?').bind(m).all()).results || []; } catch (_) {}
  const res = json(env, req, { m, rows }); res.headers.set('Cache-Control', 'public, max-age=30'); return res;
}

// ページを開いたブラウザを数える。ブラウザごとの乱数番号を変換したもの（plays の client と同じ）で、同じ日の2回目からは数えない
//   Cloudflare Web Analytics は iPhone の Safari などで数え漏れるので、ゲームの側でも数える。Cookie・個人を表す情報は使わない
// ---------- 遊ばれ方の記録（Workers Analytics Engine） ----------
// 誰のものかを結び付けられる値（ブラウザの番号・IPアドレス）は書かない。3か月で自動的に消える。長く見る数字は、毎晩、日ごとの合計にしてデータベースに写す
//   blob1 種類（btn・visit・play・reach）、blob2 名前、blob3 スマホ m／パソコン d、blob4 来た元の種類、blob5・blob6 種類ごとの補足、double1 回数
function evPoint(env, type, key, dev, src, x1, x2, n) {
  if (!env.EV) return;
  try { env.EV.writeDataPoint({ indexes: [type], blobs: [type, String(key), dev, src, String(x1 || ''), String(x2 || '')], doubles: [n] }); } catch (_) {}
}
const srcOf = h => !h ? 'direct' : /freegame-mugen\.jp$/.test(h) ? 'mugen' : /(^|\.)(t\.co|x\.com|twitter\.com)$/.test(h) ? 'x' : /(google|bing|yahoo|duckduckgo)\./.test(h) ? 'search' : 'other';
// ---------- ボタンが押された回数 ----------
// ページの中でためた回数を、まとめて受け取る。誰が押したかは受け取らない（番号もIPも書かない）。書き先は Workers Analytics Engine（3か月で自動的に消える）
async function events(env, req) {
  if (!env.EV) return json(env, req, { ok: true });
  let b; try { b = JSON.parse(await req.text()); } catch (_) { return json(env, req, { error: 'bad' }, 400); }
  const e = b && typeof b.e === 'object' && b.e ? b.e : {};
  const dev = b.m ? 'm' : 'd', src = ['mugen', 'x', 'search', 'direct', 'other'].includes(b.s) ? b.s : 'other';
  let k = 0;
  for (const [name, c] of Object.entries(e)) {
    if (k >= 60) break;
    const n = Math.min(200, Math.max(0, Math.floor(Number(c) || 0)));
    if (!n || !/^[a-z0-9_.:\/-]{1,48}$/.test(name)) continue;
    evPoint(env, 'btn', name, dev, src, '', '', n); k++;
  }
  return json(env, req, { ok: true });
}
async function visit(env, req) {
  // 1日1回、ブラウザが送ってくる。ブラウザの番号は受け取っても使わない（古いページから届く分）
  let body; try { body = JSON.parse(await req.text()); } catch (_) { return json(env, req, { error: 'bad' }, 400); }
  const ref = /^[a-z0-9.-]{1,80}$/.test(String(body.ref || '')) ? String(body.ref) : '';   // 来た元のサイトの名前だけ（URLの残りは受け取らない）
  const land = ['top', 'today', 'pref', 'battle', 'c', 'hall', 'other'].includes(body.land) ? body.land : 'other';   // どこから入ったか
  const ret = ['new', 'd1', 'w', 'long'].includes(body.ret) ? body.ret : body.fresh ? 'new' : 'long';   // 初めて／前日も来た／1週間以内／久しぶり
  evPoint(env, 'visit', ret, body.mob ? 'm' : 'd', srcOf(ref), land, ref, 1);
  return json(env, req, { ok: true });
}

// ---------- 王座戦の共有画像 ----------
const isAdmin = (env, req) => !!env.ADMIN_TOKEN && req.headers.get('Authorization') === 'Bearer ' + env.ADMIN_TOKEN;
async function askImage(env, info) {
  if (!env.GH_DISPATCH_TOKEN) return null;
  try {
    const r = await fetch('https://api.github.com/repos/' + (env.GH_REPO || 'y-krn/hyakka-kenten') + '/dispatches', { method: 'POST',
      headers: { 'Authorization': 'Bearer ' + env.GH_DISPATCH_TOKEN, 'Accept': 'application/vnd.github+json', 'User-Agent': 'hyakka-kenten (https://github.com/y-krn)', 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: 'og', client_payload: { ...(info || {}), sent: now() } }) });
    return r.status;
  } catch (e) { return String(e); }
}
async function ogPending(env, req) {
  if (!isAdmin(env, req)) return json(env, req, { error: 'forbidden' }, 403);
  // 画像待ちを探すのは、いちばん新しい画像の50件前から先だけ（毎回すべての記録を読むと、読み取り行数が記録の数に比例して増えるため）
  const q = new URL(req.url).searchParams, all = q.get('all') === '1', before = parseInt(q.get('before'), 10) || 1e9;   // all=1 … 作り直し用に、画像のあるものも含めて古い順にたどる
  const r = await env.DB.prepare(`SELECT c.id, c.reign_id, c.title, c.display, c.result, c.how, c.at, r.title AS ctitle, r.display AS cdisplay, r.started_at AS since,
      (SELECT COUNT(*) FROM challenges d WHERE d.reign_id = c.reign_id AND d.id <= c.id AND d.result IN ('lose','draw')) AS defenses
    FROM challenges c JOIN reigns r ON r.id = c.reign_id LEFT JOIN ogimg o ON o.id = c.id
    WHERE ${all ? 'c.id < ?' : 'o.id IS NULL AND c.id > (SELECT COALESCE(MAX(id), 0) FROM ogimg) - 50'} ORDER BY c.id DESC LIMIT 30`).bind(...(all ? [before] : [])).all();
  return json(env, req, { items: r.results.map(x => ({ id: x.id, reignNo: x.reign_id, result: x.result, how: x.how, at: x.at, since: x.since, defenses: x.defenses,
    ch: { title: x.title, name: x.display }, cp: { title: x.ctitle, name: x.cdisplay } })) });
}
// その日（日本時間）の王座戦のまとめ。夜のまとめ通知（GitHub Actions）が使う。名前などは出さない
async function throneDay(env, req) {
  const d0 = new URL(req.url).searchParams.get('d') || '', day = /^\d{4}-\d\d-\d\d$/.test(d0) ? d0 : new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const [a, b, c, w] = await env.DB.batch([
    env.DB.prepare("SELECT COUNT(*) AS n FROM reigns WHERE date(started_at, '+9 hours') = ? AND holder <> '初代'").bind(day),
    env.DB.prepare("SELECT COUNT(*) AS n FROM challenges WHERE date(at, '+9 hours') = ? AND result <> 'late'").bind(day),
    env.DB.prepare("SELECT display, defenses FROM reigns WHERE date(started_at, '+9 hours') = ? OR date(ended_at, '+9 hours') = ? OR (ended_at IS NULL AND date(started_at, '+9 hours') <= ?) ORDER BY defenses DESC, id LIMIT 1").bind(day, day, day),
    env.DB.prepare("SELECT id FROM challenges WHERE result = 'win' ORDER BY id DESC LIMIT 1")]);
  const cur = await current(env);
  return json(env, req, { day, changes: a.results[0].n, challenges: b.results[0].n, best: c.results[0] || null, lastWin: w.results[0] ? w.results[0].id : null,
    champ: { reignNo: cur.id, display: cur.display, defenses: cur.defenses } });
}
async function ogPut(env, req, id) {
  if (!isAdmin(env, req)) return json(env, req, { error: 'forbidden' }, 403);
  const b = new Uint8Array(await req.arrayBuffer());
  if (b.length < 1000 || b.length > 1500000 || b[0] !== 0xff || b[1] !== 0xd8) return json(env, req, { error: 'JPEG（1.5MBまで）を送ってください' }, 400);
  const ok = await env.DB.prepare('SELECT id FROM challenges WHERE id = ?').bind(id).first();
  if (!ok) return json(env, req, { error: 'その挑戦の記録はありません' }, 404);
  await env.DB.prepare('INSERT INTO ogimg (id, img, at) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET img = excluded.img, at = excluded.at').bind(id, b, now()).run();
  return json(env, req, { ok: true, bytes: b.length });
}
// 今日の一戦の共有画像（表 today_og。日付ごとに1枚。結果は載せない）
async function todayOgPut(env, req, day) {
  if (!isAdmin(env, req)) return json(env, req, { error: 'forbidden' }, 403);
  const q = new URL(req.url).searchParams, a = (q.get('a') || '').slice(0, 200), b = (q.get('b') || '').slice(0, 200);
  const img = new Uint8Array(await req.arrayBuffer());
  if (!a || !b || img.length < 1000 || img.length > 1500000 || img[0] !== 0xff || img[1] !== 0xd8) return json(env, req, { error: 'a・b と JPEG（1.5MBまで）を送ってください' }, 400);
  await env.DB.prepare('INSERT INTO today_og (day, a, b, img, at) VALUES (?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET a = excluded.a, b = excluded.b, img = excluded.img, at = excluded.at').bind(day, a, b, img, now()).run();
  return json(env, req, { ok: true, bytes: img.length });
}
async function todayOgGet(req, env, ctx, day) {
  const v = new URL(req.url).searchParams.get('v') || '';
  const cache = caches.default, key = new Request(SITE + '/og/t/' + day + '.jpg?v=' + encodeURIComponent(v));
  const hit = await cache.match(key); if (hit) return hit;
  let x = null; try { x = await env.DB.prepare('SELECT img FROM today_og WHERE day = ?').bind(day).first(); } catch (_) {}
  if (!x) return Response.redirect(SITE + '/og.png', 302);
  const res = new Response(new Uint8Array(x.img), { headers: { 'Content-Type': 'image/jpeg', 'Cache-Control': 'public, max-age=86400' } });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}
async function ogGet(req, env, ctx, id) {
  const v = new URL(req.url).searchParams.get('v') || '';
  const cache = caches.default, key = new Request(SITE + '/og/c/' + id + '.jpg?v=' + encodeURIComponent(v));
  const hit = await cache.match(key); if (hit) return hit;
  const x = await env.DB.prepare('SELECT img FROM ogimg WHERE id = ?').bind(id).first();
  if (!x) return Response.redirect(SITE + '/og.png', 302);
  const res = new Response(new Uint8Array(x.img), { headers: { 'Content-Type': 'image/jpeg', 'Cache-Control': 'public, max-age=86400' } });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

async function hide(env, req) {
  if (!env.ADMIN_TOKEN || req.headers.get('Authorization') !== 'Bearer ' + env.ADMIN_TOKEN) return json(env, req, { error: 'forbidden' }, 403);
  const b = await req.json();
  if (b.challenge) await env.DB.prepare("UPDATE challenges SET name = '（非表示）' WHERE id = ?").bind(b.challenge).run();
  if (b.reign) await env.DB.prepare("UPDATE reigns SET holder = '（非表示）' WHERE id = ?").bind(b.reign).run();
  return json(env, req, { ok: true });
}

// ---------- ゲームの画面：共有カード（OGP）を試合ごとに ----------
const SITE = 'https://hyakkakenten.com';
const RESULT_TXT = {
  win: x => `${x.display}が王者${x.cdisplay}を倒し、新王者に。`,
  late: x => `${x.display}が${x.cdisplay}に勝利。ただし王座はひと足先に別の記事へ。`,
  lose: x => `王者${x.cdisplay}が${x.display}を退け、防衛。`,
  draw: x => `${x.display}と王者${x.cdisplay}は引き分け。王者の防衛。`,
};
// 収録されている記事名か（作り話の記事名を共有カードに載せないため）。記事名だけの索引を見る
function fnv(t) { let h = 0x811c9dc5; for (let i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; } return h; }
async function known(env, t) {
  if (!t || t.length > 200) return false;
  const m = await meta(env), r = await dfetch(env, dataBase(env) + 't/' + (fnv(t) % m.nb) + '.json.gz?v=' + (m.build || m.asof));
  if (!r.ok) return false;
  const list = JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text());
  return list.includes(t);
}
// 仲間図鑑の一門（data/fam/ を読む）
const FAMK = { p: n => n + 'の一門', c: n => n + 'が生んだもの', o: n => n + 'から名前をもらったもの', s: n => /シリーズ$/.test(n) ? n : n + 'シリーズ', w: n => n + 'が戦った戦い' };
let FAMNB = 0;
async function famGet(env, key) {
  if (!FAMNB) { const r = await dfetch(env, dataBase(env) + 'fam/featured.json'); FAMNB = r.ok ? ((await r.json()).nb || 512) : 512; }
  const m = await meta(env), r = await dfetch(env, dataBase(env) + 'fam/' + (fnv(key) % FAMNB) + '.json.gz?v=' + (m.build || m.asof));
  if (!r.ok) return null;
  return JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text())[key] || null;
}
let PCARD = null;   // data/pref/card.json（県ごとの、種類ごとの1位の代表）。1時間覚えておく
async function prefCard(env, u) {
  if (PCARD && Date.now() - PCARD.t < 3600e3) return PCARD.c;
  const r = await env.ASSETS.fetch(new Request(new URL('/data/pref/card.json', u)));
  PCARD = { t: Date.now(), c: r.ok ? await r.json() : {} }; return PCARD.c;
}
async function cardFor(env, u) {
  const q = u.searchParams, clip = (t, n) => { t = String(t || '').trim(); return t.length > n ? t.slice(0, n) + '…' : t; };
  const c = q.get('c');
  if (c && /^\d{1,9}$/.test(c)) {
    const x = await env.DB.prepare('SELECT c.display, c.result, c.how, r.display AS cdisplay, (SELECT o.at FROM ogimg o WHERE o.id = c.id) AS img FROM challenges c JOIN reigns r ON r.id = c.reign_id WHERE c.id = ?').bind(+c).first();
    if (x) return { image: x.img ? SITE + '/og/c/' + c + '.jpg?v=' + Date.parse(x.img) : null, title: `${clip(x.display, 40)} vs ${clip(x.cdisplay, 40)} ― 百科拳典 王座戦`, desc: (RESULT_TXT[x.result] || (() => ''))(x) + (x.how ? `（${x.how}）` : '') + ' 試合の一部始終はこちら。', url: SITE + '/?c=' + c };
  }
  if (q.has('today')) {   // 今日の一戦（?today=1&d=日付。d がなければ今日）
    const jst = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10), d0 = q.get('d'), day = /^\d{4}-\d\d-\d\d$/.test(d0 || '') ? d0 : jst;
    let x = null; try { x = await env.DB.prepare('SELECT a, b, at FROM today_og WHERE day = ?').bind(day).first(); } catch (_) {}
    const md = (+day.slice(5, 7)) + '月' + (+day.slice(8, 10)) + '日';
    if (x) return { title: `今日の一戦 ${md}：${clip(x.a, 30)} vs ${clip(x.b, 30)} ― 百科拳典`, url: SITE + '/?today=1&d=' + day, image: SITE + '/og/t/' + day + '.jpg?v=' + Date.parse(x.at),
      desc: '人気の記事に、ランダムに選ばれた記事が挑む。どっちが勝つ？ 予想してから観戦しよう。' };
  }
  const fk = q.get('fam');
  if (fk && /^[pcosw]Q\d{1,12}$/.test(fk)) {   // 仲間図鑑の一門
    const g = await famGet(env, fk);
    if (g) { const top = g.m.slice(0, 5).map(m => m[1]);
      return { title: `${FAMK[g.k](g.n)} ${g.c}記事 ― 百科拳典 仲間さがし`, url: SITE + '/?fam=' + fk,
        desc: top.join('、') + (g.c > top.length ? `…ほか${g.c - top.length}記事。` : '。') + 'Wikipediaのつながりから集めた仲間たち。' }; }
  }
  const pf = q.get('pref');
  if (pf && PREFS.includes(pf)) {   // 都道府県を応援の入口：県ごとの共有画像と、種類ごとの1位の代表
    const c = await prefCard(env, u), r = c[pf] || {}, reps = ['人物', '名所', '自然', '名物・文化'].map(k => r[k]).filter(Boolean).map(t => t.replace(/\s*\(.*\)$/, ''));
    return { title: `${pf}を応援しよう ― 百科拳典 都道府県を応援`, url: SITE + '/?pref=' + encodeURIComponent(pf),
      image: SITE + '/data/pref/og/' + String(PREFS.indexOf(pf)).padStart(2, '0') + '.jpg',
      desc: (reps.length ? `${pf}の代表は${reps.join('、')}など。` : '') + 'ゆかりのある県の記事が、ほかの県の記事と戦う。今月の県対抗で、あなたの県は何位？' };
  }
  const a = q.get('a'), b = q.get('b');
  if (a && b && a !== b && (await Promise.all([known(env, a), known(env, b)])).every(Boolean)) return { title: `${clip(a, 40)} vs ${clip(b, 40)} ― 百科拳典`, desc: 'Wikipediaの記事どうしが、事実だけで殴り合う。勝ったのはどちらか。', url: SITE + '/?a=' + encodeURIComponent(a) + '&b=' + encodeURIComponent(b) };
  return null;
}
// 検索エンジン向けのサイトマップ。中身のあるページ（共有カードの文字を書き換えているページ）だけを並べる
async function sitemap(req, env, ctx) {
  const cache = caches.default, key = new Request(SITE + '/sitemap.xml?d=' + new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10));
  const hit = await cache.match(key); if (hit) return hit;
  const esc = t => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const urls = [[SITE + '/', null, 'daily', '1.0']];
  try {   // 王座戦の試合の記録（新しい順）
    const r = await env.DB.prepare('SELECT id, at FROM challenges ORDER BY id DESC LIMIT 5000').all();
    for (const x of r.results) urls.push([SITE + '/?c=' + x.id, String(x.at || '').slice(0, 10), null, '0.5']);
  } catch (_) {}
  try {   // 仲間さがしの一門（目立つものの一覧）
    const r = await env.ASSETS.fetch(new Request(new URL('/data/fam/featured.json', req.url)));
    if (r.ok) for (const g of ((await r.json()).featured || [])) if (/^[pcosw]Q\d{1,12}$/.test(g[0])) urls.push([SITE + '/?fam=' + g[0], null, 'monthly', '0.4']);
  } catch (_) {}
  if (typeof PREFS !== 'undefined') for (const p of PREFS) urls.push([SITE + '/?pref=' + encodeURIComponent(p), null, 'weekly', '0.6']);   // 都道府県の応援の入口
  const body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    urls.map(([l, m, c, p]) => `  <url><loc>${esc(l)}</loc>${m ? `<lastmod>${m}</lastmod>` : ''}${c ? `<changefreq>${c}</changefreq>` : ''}<priority>${p}</priority></url>`).join('\n') + '\n</urlset>\n';
  const res = new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8', 'Cache-Control': 'public, max-age=3600' } });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}
async function page(req, env, u) {
  const res0 = await env.ASSETS.fetch(new Request(new URL('/', u), req));
  // 数えない印（?nostat=1）で開いたときは、最初のHTMLから manifest を ?nostat=1 で開くものに替える（iPhone のホーム画面のWebアプリにも印が付くように）
  const res = u.searchParams.get('nostat') === '1' ? new HTMLRewriter().on('link[rel="manifest"]', { element(e) { e.setAttribute('href', 'manifest-nostat.webmanifest'); } }).transform(res0) : res0;
  let card = null; try { card = await cardFor(env, u); } catch (_) {}
  if (u.hostname !== 'hyakkakenten.com') { const h = new Headers(res.headers); h.set('X-Robots-Tag', 'noindex'); return new Response(res.body, { status: res.status, headers: h }); }   // 試作版は検索に載せない
  if (!card || !res.ok) return res;
  const set = v => ({ element(e) { e.setAttribute('content', v); } });
  return new HTMLRewriter()
    .on('title', { element(e) { e.setInnerContent(card.title); } })
    .on('meta[property="og:title"]', set(card.title))
    .on('meta[property="og:description"]', set(card.desc))
    .on('meta[name="description"]', set(card.desc))
    .on('meta[property="og:url"]', set(card.url))
    .on('link[rel="canonical"]', { element(e) { if (card.url && !u.searchParams.has('today')) e.setAttribute('href', card.url); } })
    .on('meta[property="og:image"]', set(card.image || SITE + '/og.png'))
    .on('meta[name="twitter:card"]', set(card.image ? 'summary_large_image' : 'summary'))
    .transform(res);
}

// 利用者からの報告（数字や事実の誤り・内容が不適切）。GitHubのアカウントがなくても送れる。名前やメールアドレスは集めない
//   いたずら・連続送信の対策：同じ回線・同じブラウザごとの回数の上限、同じ人の同じ報告は1回だけ、全体の1日の上限、
//   画面を開いてすぐの送信（機械的な送信）と、人には見えない欄が埋まった送信（ロボット）は受け付けない、ほかのサイトからの送信は受け付けない
//   管理者の手間を減らす：
//     - 「内容が不適切」だけ、すぐスマホに知らせる。数字や事実の誤りは急がないので、週1回のアクセスレポートにまとめる
//     - 同じもの（同じ記事の同じ事実、同じ記事への不適切の報告）は1つにまとめて数える。通知は最初の1回と、記事を一時的に外したときだけ
//     - 違う回線の2人以上から「内容が不適切」と知らされた記事は、確かめるまで今日の一戦とランダムに出さない（/api/holds）。
//       確かめたら status を 'ok'（問題なし）か 'done'（対応した）にすると、元に戻る
const REP = { perIp10m: 3, perIpDay: 10, perClientDay: 10, allDay: 100, notifyDay: 30, holdBy: 2 };
const REASON = { fact: '数字や事実が違う', dis: '差別的・攻撃的', subj: '扱いがふさわしくない題材', other: 'その他' };
const HOLDS_KEY = 'https://hyakkakenten.com/__cache/holds';
async function repTable(env) {
  await env.DB.prepare('CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, iphash TEXT NOT NULL, client TEXT, kind TEXT NOT NULL, a TEXT, b TEXT, target TEXT, text TEXT, url TEXT, status TEXT NOT NULL DEFAULT \'new\', reason TEXT, title TEXT, fk TEXT, fv TEXT, fix TEXT, rkey TEXT)').run();
  try { await env.DB.prepare('SELECT rkey FROM reports LIMIT 0').run(); }
  catch (_) { for (const c of ['reason', 'title', 'fk', 'fv', 'fix', 'rkey']) { try { await env.DB.prepare('ALTER TABLE reports ADD COLUMN ' + c + ' TEXT').run(); } catch (_) {} } }   // 先に作った表に、あとから足した列
  // 索引：回数の上限を数えるたびに表全体を読まないように（D1の無料枠は「読んだ行数」で数える）
  await env.DB.batch(['CREATE INDEX IF NOT EXISTS rep_key ON reports(rkey, status)', 'CREATE INDEX IF NOT EXISTS rep_at ON reports(at)',
    'CREATE INDEX IF NOT EXISTS rep_cl ON reports(client, at)', 'CREATE INDEX IF NOT EXISTS rep_hold ON reports(kind, status, title)'].map(q => env.DB.prepare(q)));
}
async function report(env, req, ctx) {
  const origin = req.headers.get('Origin') || '';
  if (origin && !/^https:\/\/(hyakkakenten\.com|preview-hyakka-kenten-api\.y-krn\.workers\.dev)$/.test(origin) && !/^http:\/\/localhost(:\d+)?$/.test(origin)) return json(env, req, { error: 'forbidden' }, 403);
  let b; try { b = JSON.parse(await req.text()); } catch (_) { return json(env, req, { error: 'bad' }, 400); }
  if (b.hp) return json(env, req, { ok: true });                       // 人には見えない欄が埋まっている：受け付けたふりをして捨てる
  if (!(Number(b.ms) >= 800)) return json(env, req, { error: '少し時間をおいてから送ってください' }, 400);   // 開いて1秒足らずの送信
  const reason = REASON[b.reason] ? b.reason : b.kind === 'num' ? 'fact' : b.kind === 'bad' ? 'other' : null;
  const kind = reason === 'fact' ? 'num' : 'bad';
  const target = ['a', 'b', 'text'].includes(b.target) ? b.target : null;
  const clean = (x, n) => String(x || '').normalize('NFKC').replace(/[\u0000-\u0009\u000b-\u001f\u007f]/g, '').trim().slice(0, n);
  const a = clean(b.a, 200), bb = clean(b.b, 200), text = clean(b.text, 200), url = clean(b.url, 300), fix = clean(b.fix, 60);
  const fc = b.fact && typeof b.fact === 'object' ? b.fact : {};
  const fk = clean(fc.k, 40), fv = clean(fc.v, 120);
  if (!reason || !target || !a || !bb) return json(env, req, { error: 'bad' }, 400);
  const title = target === 'a' ? a : target === 'b' ? bb : '';
  if (kind === 'num' && !fv && text.length < 2) return json(env, req, { error: 'どこが違うか、ひとこと書いてください' }, 400);
  if (url && !/^https?:\/\/[^\s]+$/.test(url)) return json(env, req, { error: '出典のURLは https:// から書いてください' }, 400);
  // まとめる単位：数字や事実は「記事＋項目」、不適切は「記事」（実況の文面は「対戦」）
  const rkey = kind === 'num' ? (fv ? 'n|' + title + '|' + fk + '|' + fv : 'n|' + a + '|' + bb + '|' + target + '|' + text.slice(0, 40))
    : target === 'text' ? 'b|text|' + a + '|' + bb : 'b|' + title;
  await repTable(env);
  const ih = await ipHash(env, req);
  const cl = /^[a-z0-9]{16,40}$/.test(String(b.client || '')) ? await ipHash(env, { headers: { get: () => 'client:' + b.client } }) : null;
  const t10 = new Date(Date.now() - 600000).toISOString(), t1d = new Date(Date.now() - 86400000).toISOString();
  const [q1, q2, q3, q4, q5, q6] = await env.DB.batch([
    env.DB.prepare('SELECT COUNT(*) AS n FROM reports WHERE iphash = ? AND at > ?').bind(ih, t10),
    env.DB.prepare('SELECT COUNT(*) AS n FROM reports WHERE iphash = ? AND at > ?').bind(ih, t1d),
    env.DB.prepare('SELECT COUNT(*) AS n FROM reports WHERE client = ? AND at > ?').bind(cl || '-', t1d),
    env.DB.prepare('SELECT COUNT(*) AS n FROM reports WHERE at > ?').bind(t1d),
    env.DB.prepare("SELECT COUNT(*) AS n FROM reports WHERE (iphash = ? OR client = ?) AND rkey = ? AND status = 'new'").bind(ih, cl || '-', rkey),
    env.DB.prepare("SELECT COUNT(DISTINCT iphash) AS n FROM reports WHERE rkey = ? AND status = 'new'").bind(rkey),
  ]);
  const n = r => r.results[0].n;
  if (n(q5) > 0) return json(env, req, { ok: true, dup: true });   // 同じ人の同じ報告は1回だけ（2回目以降は受け付けたことにして記録しない）
  if (n(q1) >= REP.perIp10m || n(q2) >= REP.perIpDay || n(q3) >= REP.perClientDay) return json(env, req, { error: '短い時間にたくさん送られたため、いまは受け付けられません。時間をおいてください' }, 429);
  if (n(q4) >= REP.allDay) return json(env, req, { error: 'きょうは報告が多いため、受け付けを止めています。明日もう一度お願いします' }, 429);
  await env.DB.prepare('INSERT INTO reports (at, iphash, client, kind, a, b, target, text, url, reason, title, fk, fv, fix, rkey) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)')
    .bind(now(), ih, cl, kind, a, bb, target, text, url, reason, title, fk, fv, fix, rkey).run();
  const people = n(q6) + 1;   // この報告を入れた人数（違う回線の数）
  const held = kind === 'bad' && title && people === REP.holdBy;
  if (held) { try { await caches.default.delete(HOLDS_KEY); } catch (_) {} }
  if (kind === 'bad' && (people === 1 || held) && env.NTFY_TOPIC && n(q4) < REP.notifyDay) {   // 管理者のスマホに届ける：最初の1回と、一時的に外したときだけ
    const who = target === 'text' ? '実況の文面（' + a + ' 対 ' + bb + '）' : title;
    const page = SITE + '/?a=' + encodeURIComponent(a) + '&b=' + encodeURIComponent(bb);
    const p = fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      topic: env.NTFY_TOPIC, title: (held ? '一時的に外しました：' : '内容の報告：') + who, tags: [held ? 'no_entry' : 'warning'], click: page,
      message: (held ? `違う回線の${people}人から報告があったため、今日の一戦とランダムに出さないようにしました（検索では選べます）。確かめて、問題がなければ戻してください\n` : '')
        + `理由：${REASON[reason]}\n対戦：${a} 対 ${bb}${text ? '\nひとことあり（管理画面で見る）' : ''}` }) }).catch(() => {});   // 利用者が書いた文は、外部の通知サービスに送らない
    if (ctx) ctx.waitUntil(p); else await p;
  }
  return json(env, req, { ok: true });
}
// 一時的に外している記事（今日の一戦とランダムに出さない）。ページが読み込みのたびに聞くので、5分だけ使い回す
async function holds(env, req, ctx) {
  try { const hit = await caches.default.match(HOLDS_KEY); if (hit) return json(env, req, await hit.json()); } catch (_) {}
  let titles = [];
  try { titles = (await env.DB.prepare("SELECT title FROM reports WHERE kind = 'bad' AND status = 'new' AND title <> '' GROUP BY title HAVING COUNT(DISTINCT iphash) >= ?").bind(REP.holdBy).all()).results.map(r => r.title); } catch (_) {}
  const body = { titles };
  try { const put = caches.default.put(HOLDS_KEY, new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300' } })); if (ctx) ctx.waitUntil(put); } catch (_) {}
  return json(env, req, body);
}

// ---------- 毎晩の片付け（必要な分だけ残す） ----------
//   ・対戦数の1件ずつの記録（回数の上限を数えるためだけのもの）：25時間で消す
//   ・王座戦の挑戦に付けた、変換したIPとブラウザの番号：25時間で消す（10分・1日の挑戦回数の上限にだけ使う。記事・名前・結果・日時は残す）
//   ・報告に付けた、変換したIPとブラウザの番号：30日で消す（同じ記事に違う人から報告が重なったかを数えるのに使う）
//   ・報告そのもの：対応が終わってから1年で消す
async function cleanup(env) {
  const ago = h => new Date(Date.now() - h * 3600000).toISOString();
  const r = await env.DB.batch([
    env.DB.prepare('DELETE FROM plays WHERE at < ?').bind(ago(25)),
    env.DB.prepare("UPDATE challenges SET iphash = '', client = NULL WHERE at < ? AND (iphash <> '' OR client IS NOT NULL)").bind(ago(25)),
    env.DB.prepare("UPDATE reports SET iphash = '', client = NULL WHERE at < ? AND (iphash <> '' OR client IS NOT NULL)").bind(ago(24 * 30)),
    env.DB.prepare("DELETE FROM reports WHERE status <> 'new' AND at < ?").bind(ago(24 * 365)),
  ]);
  return r.map(x => x.meta && x.meta.changes || 0);
}
export default {
  async scheduled(ev, env, ctx) { ctx.waitUntil(cleanup(env)); },   // 毎晩の片付け（wrangler.toml の triggers）
  async fetch(req, env, ctx) {
    const u = new URL(req.url);
    if (u.hostname === 'www.hyakkakenten.com') return Response.redirect(SITE + u.pathname + u.search, 301);
    if (u.hostname === 'hyakka-kenten-api.y-krn.workers.dev') return Response.redirect(SITE + u.pathname + u.search, 301);   // 古いアドレス（試作版のプレビュー用URLは別の名前なので対象外）
    if (req.method === 'OPTIONS') return new Response(null, { headers: cors(env, req) });
    if (env.ASSETS && (u.pathname === '/' || u.pathname === '/index.html') && (req.method === 'GET' || req.method === 'HEAD')) return page(req, env, u);
    if (env.ASSETS && u.pathname === '/sitemap.xml' && (req.method === 'GET' || req.method === 'HEAD')) return sitemap(req, env, ctx);
    const og = u.pathname.match(/^\/og\/c\/(\d{1,9})\.jpg$/); if (og && req.method === 'GET') return ogGet(req, env, ctx, +og[1]);
    const ot = u.pathname.match(/^\/og\/t\/(\d{4}-\d\d-\d\d)\.jpg$/); if (ot && req.method === 'GET') return todayOgGet(req, env, ctx, ot[1]);
    if (env.ASSETS && !u.pathname.startsWith('/api/')) return env.ASSETS.fetch(req);
    try {
      if (u.pathname === '/api/throne' && req.method === 'GET') return await throne(env, req, ctx);
      if (u.pathname === '/api/throne/day' && req.method === 'GET') return await throneDay(env, req);
      if (u.pathname === '/api/hall' && req.method === 'GET') return await hall(env, req, ctx);
      if (u.pathname === '/api/challenge' && req.method === 'POST') return await challenge(env, req, ctx);
      if (u.pathname === '/api/og/pending' && req.method === 'GET') return await ogPending(env, req);
      if (u.pathname === '/api/og/ask' && req.method === 'POST') return isAdmin(env, req) ? json(env, req, { status: await askImage(env, { id: 'test' }) }) : json(env, req, { error: 'forbidden' }, 403);
      const op = u.pathname.match(/^\/api\/og\/(\d{1,9})$/); if (op && req.method === 'PUT') return await ogPut(env, req, +op[1]);
      const tp = u.pathname.match(/^\/api\/og\/today\/(\d{4}-\d\d-\d\d)$/); if (tp && req.method === 'PUT') return await todayOgPut(env, req, tp[1]);
      if (u.pathname === '/api/plays' && req.method === 'POST') return await plays(env, req);
      if (u.pathname === '/api/ev' && req.method === 'POST') return await events(env, req);
      if (u.pathname === '/api/pref/ev' && req.method === 'POST') return await prefEvApi(env, req);
      if (u.pathname === '/api/pref' && req.method === 'GET') return await prefBoardApi(env, req);
      if (u.pathname === '/api/visit' && req.method === 'POST') return await visit(env, req);
      if (u.pathname === '/api/report' && req.method === 'POST') return await report(env, req, ctx);
      if (u.pathname === '/api/holds' && req.method === 'GET') return await holds(env, req, ctx);
      if (u.pathname === '/api/admin/hide' && req.method === 'POST') return await hide(env, req);
      if (u.pathname === '/api/admin/cleanup' && req.method === 'POST') { if (!isAdmin(env, req)) return json(env, req, { error: 'forbidden' }, 403); return json(env, req, { ok: true, changes: await cleanup(env) }); }   // 片付けを手で動かす（確かめる用）
      const m = u.pathname.match(/^\/api\/challenge\/(\d{1,9})$/); if (m && req.method === 'GET') return await getChallenge(env, req, +m[1]);
      return json(env, req, { error: 'not found' }, 404);
    } catch (e) {
      return json(env, req, { error: 'サーバーでエラーが起きました', detail: String(e && e.message || e).slice(0, 200) }, 500);
    }
  },
};
