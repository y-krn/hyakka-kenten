// 百科拳典 王座戦API（Cloudflare Workers + D1）
//   GET  /api/throne            … いまの王者・最近の挑戦・歴代王者・最長防衛
//   POST /api/challenge         … {title, name} で王者に挑む。勝敗はサーバーで計算し直して決める
//   POST /api/admin/hide        … {id} 不適切な名前を非表示にする（ヘッダー Authorization: Bearer ADMIN_TOKEN）
import * as E from './engine.mjs';

const SEED = '東京タワー';                 // 王者がいないときの初代
const MAX_NAME = 16;
const LIMIT_10MIN = 10, LIMIT_DAY = 100;   // 1人あたりの挑戦回数
// 名前の禁止語（部分一致。表記ゆれを減らすため、比べる前に正規化する）
const NG = ['死ね', 'しね', '殺す', 'ころす', 'きちがい', 'キチガイ', 'ガイジ', 'がいじ', '障害者', 'ちんこ', 'ちんぽ', 'まんこ', 'おまんこ', 'セックス', 'sex', 'fuck', 'shit', 'nigger', 'nigga', 'faggot', 'rape', 'レイプ', '強姦', '朝鮮人',  'シナ人', '支那', '部落', '在日', 'hitler', 'ヒトラー', 'http', 'www.', '.com', '.jp'];

let META = null, METAAT = 0;
async function meta(env) {
  if (META && Date.now() - METAAT < 600000) return META;
  const [m, ex] = await Promise.all([
    fetch(env.DATA_BASE + 'meta.json?t=' + Date.now()).then(r => r.json()),
    fetch(env.DATA_BASE + 'exclude.json?t=' + Date.now()).then(r => r.ok ? r.json() : []).catch(() => []),
  ]);
  META = m; METAAT = Date.now();
  E.setup({ base: env.DATA_BASE, nb: m.nb, ver: m.build || m.asof, excl: ex });
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
    env.DB.prepare('SELECT id, reign_id, display, title, name, result, how, at FROM challenges ORDER BY id DESC LIMIT 15'),
    env.DB.prepare('SELECT id, display, title, holder, started_at, ended_at, defenses FROM reigns ORDER BY defenses DESC, id ASC LIMIT 10'),
    env.DB.prepare('SELECT id, display, title, holder, started_at, ended_at, defenses, ended_by FROM reigns ORDER BY id DESC LIMIT 10'),
  ]);
  const cnt = await env.DB.prepare('SELECT COUNT(*) AS n FROM reigns').first();
  return json(env, req, { champ: c, reignNo: cnt.n, recent: recent.results, best: best.results, history: hist.results });
}

async function challenge(env, req) {
  let body; try { body = await req.json(); } catch (_) { return json(env, req, { error: '送信内容を読めませんでした' }, 400); }
  const title = String(body.title || '').trim().slice(0, 200);
  if (!title) return json(env, req, { error: '挑戦する記事名を入れてください' }, 400);
  const nm = cleanName(body.name); if (nm.error) return json(env, req, { error: nm.error }, 400);
  const ih = await ipHash(env, req);
  const lim = await env.DB.prepare("SELECT SUM(CASE WHEN at > ? THEN 1 ELSE 0 END) AS m10, COUNT(*) AS d FROM challenges WHERE iphash = ? AND at > ?")
    .bind(new Date(Date.now() - 600000).toISOString(), ih, new Date(Date.now() - 86400000).toISOString()).first();
  if ((lim.m10 || 0) >= LIMIT_10MIN) return json(env, req, { error: '挑戦が続いています。10分ほど待ってから、また挑んでください。' }, 429);
  if ((lim.d || 0) >= LIMIT_DAY) return json(env, req, { error: '今日の挑戦回数の上限に達しました。また明日どうぞ。' }, 429);

  await meta(env);
  const c = await current(env);
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
  const ins = await env.DB.prepare('INSERT OR IGNORE INTO challenges (reign_id, title, display, name, result, how, at, iphash) VALUES (?,?,?,?,?,?,?,?)')
    .bind(c.id, B.title, B.name, nm.name, result, v.how, t, ih).run();
  if (!ins.meta.changes) return json(env, req, { error: 'ちょうど同じ挑戦が受け付けられました。少し待ってから見直してください。' }, 409);
  let newReign = null;
  if (result === 'win') {
    const up = await env.DB.prepare('UPDATE reigns SET ended_at = ?, ended_by = ? WHERE id = ? AND ended_at IS NULL').bind(t, B.name, c.id).run();
    if (up.meta.changes) {
      await env.DB.prepare('INSERT INTO reigns (title, display, holder, started_at, defenses) VALUES (?,?,?,?,0)').bind(B.title, B.name, nm.name, t).run();
      newReign = true;
    } else { result = 'late'; }   // ほぼ同時に別の人が王者を倒していた
  } else {
    await env.DB.prepare('UPDATE reigns SET defenses = defenses + 1 WHERE id = ? AND ended_at IS NULL').bind(c.id).run();
  }
  return json(env, req, { result, newChamp: !!newReign, champ: { title: c.title, display: c.display, defenses: c.defenses + (result === 'win' || result === 'late' ? 0 : 1) }, challenger: { title: B.title, display: B.name }, how: v.how, kind: v.kind, name: nm.name });
}

async function hide(env, req) {
  if (!env.ADMIN_TOKEN || req.headers.get('Authorization') !== 'Bearer ' + env.ADMIN_TOKEN) return json(env, req, { error: 'forbidden' }, 403);
  const b = await req.json();
  if (b.challenge) await env.DB.prepare("UPDATE challenges SET name = '（非表示）' WHERE id = ?").bind(b.challenge).run();
  if (b.reign) await env.DB.prepare("UPDATE reigns SET holder = '（非表示）' WHERE id = ?").bind(b.reign).run();
  return json(env, req, { ok: true });
}

export default {
  async fetch(req, env) {
    const u = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { headers: cors(env, req) });
    try {
      if (u.pathname === '/api/throne' && req.method === 'GET') return await throne(env, req);
      if (u.pathname === '/api/challenge' && req.method === 'POST') return await challenge(env, req);
      if (u.pathname === '/api/admin/hide' && req.method === 'POST') return await hide(env, req);
      return json(env, req, { error: 'not found' }, 404);
    } catch (e) {
      return json(env, req, { error: 'サーバーでエラーが起きました', detail: String(e && e.message || e).slice(0, 200) }, 500);
    }
  },
};
