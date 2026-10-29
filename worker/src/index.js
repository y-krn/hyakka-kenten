// 百科拳典 王座戦API（Cloudflare Workers + D1）
//   GET  /api/throne            … いまの王者・最近の挑戦・歴代王者・最長防衛
//   POST /api/challenge         … {title, name} で王者に挑む。勝敗はサーバーで計算し直して決める
//   POST /api/plays             … {n, client} 自由対戦の対戦数（ブラウザでまとめて数えたもの）を足す
//   GET  /og/c/番号.jpg          … 王座戦の試合ごとの共有画像
//   GET  /api/og/pending        … 画像がまだない挑戦の一覧（管理用。GitHub Actions が使う）
//   PUT  /api/og/番号            … 作った画像を預ける（管理用）
//   POST /api/admin/hide        … {id} 不適切な名前を非表示にする（ヘッダー Authorization: Bearer ADMIN_TOKEN）
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

async function throne(env, req) {
  const c = await current(env);
  const [recent, best, hist] = await env.DB.batch([
    env.DB.prepare('SELECT c.id, c.reign_id, c.display, c.title, c.name, c.result, c.how, c.at, r.display AS cdisplay FROM challenges c JOIN reigns r ON r.id = c.reign_id ORDER BY c.id DESC LIMIT 15'),
    env.DB.prepare("SELECT id, display, title, holder, started_at, ended_at, defenses, (SELECT c.id FROM challenges c WHERE c.result = 'win' AND c.title = reigns.title AND c.reign_id < reigns.id ORDER BY c.id DESC LIMIT 1) AS cid FROM reigns ORDER BY defenses DESC, id ASC LIMIT 10"),
    env.DB.prepare("SELECT id, display, title, holder, started_at, ended_at, defenses, ended_by, (SELECT c.id FROM challenges c WHERE c.result = 'win' AND c.title = reigns.title AND c.reign_id < reigns.id ORDER BY c.id DESC LIMIT 1) AS cid, (SELECT c.id FROM challenges c WHERE c.reign_id = reigns.id AND c.result = 'win' ORDER BY c.id LIMIT 1) AS lostcid FROM reigns ORDER BY id DESC LIMIT 10"),
  ]);
  const [pl, ch] = await env.DB.batch([
    env.DB.prepare("SELECT n FROM stats WHERE k = 'plays'"),
    env.DB.prepare('SELECT COUNT(*) AS n FROM challenges'),
  ]);
  return json(env, req, { champ: c, reignNo: c.id, recent: recent.results, best: best.results, history: hist.results,
    count: { plays: (pl.results[0] || {}).n || 0, throne: (ch.results[0] || {}).n || 0 } });
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
  const tried = await env.DB.prepare('SELECT result, how FROM challenges WHERE reign_id = ? AND title = ?').bind(c.id, B.title).first();
  if (tried) return json(env, req, { error: '「' + B.name + '」はすでにこの王者に挑んで' + (tried.result === 'draw' ? '引き分けました' : '敗れています') + '。結果は何度やっても同じです。別の記事で挑んでください。', known: tried }, 409);

  const ai = await E.loadOne(c.title);
  let v, result;
  if (ai < 0 || E.info(ai).blocked) { v = { w: B.title, kind: '不戦勝', how: '王者が収録から外れていたため不戦勝' }; }
  else v = E.verdict(ai, bi);
  result = v.w === B.title ? 'win' : v.w === null ? 'draw' : 'lose';
  const t = now();
  const ins = await env.DB.prepare('INSERT OR IGNORE INTO challenges (reign_id, title, display, name, result, how, at, iphash, client) VALUES (?,?,?,?,?,?,?,?,?)')
    .bind(c.id, B.title, B.name, nm.name, result, v.how, t, ih, cl).run();
  if (!ins.meta.changes) return json(env, req, { error: 'ちょうど同じ挑戦が受け付けられました。少し待ってから見直してください。' }, 409);
  let newReign = null;
  if (result === 'win') {
    const up = await env.DB.prepare('UPDATE reigns SET ended_at = ?, ended_by = ? WHERE id = ? AND ended_at IS NULL').bind(t, B.name, c.id).run();
    if (up.meta.changes) {
      await env.DB.prepare('INSERT INTO reigns (title, display, holder, started_at, defenses) VALUES (?,?,?,?,0)').bind(B.title, B.name, nm.name, t).run();
      newReign = true;
    } else {   // ほぼ同時に別の人が王者を倒していた：記録も「ひと足遅れ」に直す
      result = 'late'; await env.DB.prepare("UPDATE challenges SET result = 'late' WHERE id = ?").bind(ins.meta.last_row_id).run();
    }
  } else {
    await env.DB.prepare('UPDATE reigns SET defenses = defenses + 1 WHERE id = ? AND ended_at IS NULL').bind(c.id).run();
  }
  if (ctx) ctx.waitUntil(askImage(env, { id: ins.meta.last_row_id }));   // 共有画像を作ってもらう（失敗しても挑戦には影響しない。1時間ごとの定期実行でも拾う）
  const after = await env.DB.prepare('SELECT defenses FROM reigns WHERE id = ?').bind(c.id).first();   // 同時の挑戦があっても、実際の防衛回数を返す
  return json(env, req, { id: ins.meta.last_row_id, reignNo: c.id, result, newChamp: !!newReign, champ: { id: c.id, title: c.title, display: c.display, defenses: after ? after.defenses : c.defenses }, challenger: { title: B.title, display: B.name }, how: v.how, kind: v.kind, name: nm.name });
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
  await env.DB.batch([
    env.DB.prepare('INSERT INTO plays (n, at, iphash, client) VALUES (?,?,?,?)').bind(add, now(), ih, cl),
    env.DB.prepare("INSERT INTO stats (k, n) VALUES ('plays', ?) ON CONFLICT(k) DO UPDATE SET n = n + excluded.n").bind(add),
  ]);
  return json(env, req, { ok: true, added: add });
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
  const r = await env.DB.prepare(`SELECT c.id, c.reign_id, c.title, c.display, c.result, c.how, c.at, r.title AS ctitle, r.display AS cdisplay,
      (SELECT COUNT(*) FROM challenges d WHERE d.reign_id = c.reign_id AND d.id <= c.id AND d.result IN ('lose','draw')) AS defenses
    FROM challenges c JOIN reigns r ON r.id = c.reign_id LEFT JOIN ogimg o ON o.id = c.id WHERE o.id IS NULL ORDER BY c.id DESC LIMIT 30`).all();
  return json(env, req, { items: r.results.map(x => ({ id: x.id, reignNo: x.reign_id, result: x.result, how: x.how, at: x.at, defenses: x.defenses,
    ch: { title: x.title, name: x.display }, cp: { title: x.ctitle, name: x.cdisplay } })) });
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
async function ogGet(req, env, ctx, id) {
  const cache = caches.default, key = new Request(new URL('/og/c/' + id + '.jpg', SITE).toString());
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
async function cardFor(env, u) {
  const q = u.searchParams, clip = (t, n) => { t = String(t || '').trim(); return t.length > n ? t.slice(0, n) + '…' : t; };
  const c = q.get('c');
  if (c && /^\d{1,9}$/.test(c)) {
    const x = await env.DB.prepare('SELECT c.display, c.result, c.how, r.display AS cdisplay, (SELECT 1 FROM ogimg o WHERE o.id = c.id) AS img FROM challenges c JOIN reigns r ON r.id = c.reign_id WHERE c.id = ?').bind(+c).first();
    if (x) return { image: x.img ? SITE + '/og/c/' + c + '.jpg' : null, title: `${clip(x.display, 40)} vs ${clip(x.cdisplay, 40)} ― 百科拳典 王座戦`, desc: (RESULT_TXT[x.result] || (() => ''))(x) + (x.how ? `（${x.how}）` : '') + ' 試合の一部始終はこちら。', url: SITE + '/?c=' + c };
  }
  const a = q.get('a'), b = q.get('b');
  if (a && b && a !== b && (await Promise.all([known(env, a), known(env, b)])).every(Boolean)) return { title: `${clip(a, 40)} vs ${clip(b, 40)} ― 百科拳典`, desc: 'Wikipediaの記事どうしが、事実だけで殴り合う。勝ったのはどちらか。', url: SITE + '/?a=' + encodeURIComponent(a) + '&b=' + encodeURIComponent(b) };
  return null;
}
async function page(req, env, u) {
  const res = await env.ASSETS.fetch(new Request(new URL('/', u), req));
  let card = null; try { card = await cardFor(env, u); } catch (_) {}
  if (!card || !res.ok) return res;
  const set = v => ({ element(e) { e.setAttribute('content', v); } });
  return new HTMLRewriter()
    .on('title', { element(e) { e.setInnerContent(card.title); } })
    .on('meta[property="og:title"]', set(card.title))
    .on('meta[property="og:description"]', set(card.desc))
    .on('meta[name="description"]', set(card.desc))
    .on('meta[property="og:url"]', set(card.url))
    .on('meta[property="og:image"]', set(card.image || SITE + '/og.png'))
    .on('meta[name="twitter:card"]', set(card.image ? 'summary_large_image' : 'summary'))
    .transform(res);
}

export default {
  async fetch(req, env, ctx) {
    const u = new URL(req.url);
    if (u.hostname === 'www.hyakkakenten.com') return Response.redirect(SITE + u.pathname + u.search, 301);
    if (req.method === 'OPTIONS') return new Response(null, { headers: cors(env, req) });
    if (env.ASSETS && (u.pathname === '/' || u.pathname === '/index.html') && (req.method === 'GET' || req.method === 'HEAD')) return page(req, env, u);
    const og = u.pathname.match(/^\/og\/c\/(\d{1,9})\.jpg$/); if (og && req.method === 'GET') return ogGet(req, env, ctx, +og[1]);
    if (env.ASSETS && !u.pathname.startsWith('/api/')) return env.ASSETS.fetch(req);
    try {
      if (u.pathname === '/api/throne' && req.method === 'GET') return await throne(env, req);
      if (u.pathname === '/api/challenge' && req.method === 'POST') return await challenge(env, req, ctx);
      if (u.pathname === '/api/og/pending' && req.method === 'GET') return await ogPending(env, req);
      if (u.pathname === '/api/og/ask' && req.method === 'POST') return isAdmin(env, req) ? json(env, req, { status: await askImage(env, { id: 'test' }) }) : json(env, req, { error: 'forbidden' }, 403);
      const op = u.pathname.match(/^\/api\/og\/(\d{1,9})$/); if (op && req.method === 'PUT') return await ogPut(env, req, +op[1]);
      if (u.pathname === '/api/plays' && req.method === 'POST') return await plays(env, req);
      if (u.pathname === '/api/admin/hide' && req.method === 'POST') return await hide(env, req);
      const m = u.pathname.match(/^\/api\/challenge\/(\d{1,9})$/); if (m && req.method === 'GET') return await getChallenge(env, req, +m[1]);
      return json(env, req, { error: 'not found' }, 404);
    } catch (e) {
      return json(env, req, { error: 'サーバーでエラーが起きました', detail: String(e && e.message || e).slice(0, 200) }, 500);
    }
  },
};
