# 試作の page.html から、公開用（記事データを必要なときだけ読む版）の index.html を作る
# python3 mk_site.py <page.html> <out/index.html>
import sys, re, os
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()
def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    assert n == cnt, (n, a[:80])
    s = s.replace(a, b)
def rep_span(start, end, b):
    """start から end（end を含む）までを置き換える"""
    global s
    i = s.index(start); j = s.index(end, i) + len(end)
    s = s[:i] + b + s[j:]

REPO = 'https://github.com/y-krn/hyakka-kenten'

# ---- 1. データの入れ物：最初は空で、記事を読み込むたびに足す ----
rep("const DATA=/*__DATA__*/null;\nconst F=DATA.F, RV=DATA.RV, N=F.length;\nconst NAMES=F.map(f=>f[0]);\ntry{ document.getElementById('eyebrow').textContent='ひゃっかけんてん ／ 試作 ／ '+N+'記事収録'; }catch(_){}\n",
"""/* ---------- 記事データ：必要になった記事だけを読み込む ---------- */
const F=[], RV={}; let VER='', N=0, NB=4096, POPULAR=[], EXCL=new Set();
const fnv=t=>{ let h=0x811c9dc5; for(let k=0;k<t.length;k++){ h^=t.charCodeAt(k); h=Math.imul(h,0x01000193)>>>0; } return h>>>0; };
const BUCKET={};   // 読み込んだ振り分けファイル {番号: {記事名: レコード}}
const TIX={};      // 記事名 → 番号
// 振り分けファイルは gzip のまま置いてあるので、ブラウザで展開して読む
async function bucket(k){ if(!BUCKET[k]) BUCKET[k]=fetch('data/a/'+k+'.json.gz?v='+VER).then(async r=>{ if(!r.ok) throw new Error(r.status);
    const ds=new DecompressionStream('gzip'); return JSON.parse(await new Response(r.body.pipeThrough(ds)).text()); }).catch(e=>{ delete BUCKET[k]; throw e; }); return BUCKET[k]; }
async function loadTitle(t){ t=String(t||'').trim(); if(!t) return -1; if(TIX[t]!==undefined) return TIX[t];
  const b=await bucket(fnv(t)%NB); const rec=b[t]; if(!rec) return -1; return register(rec); }
""")
rep("const EX=DATA.EX||{}, QT=DATA.QT||{};", "const EX={}, QT={};")
rep("const EXT=DATA.EXT||{};", "const EXT={};")
rep("const WP=DATA.WP||{};", "const WP={};")
rep("const GEN=DATA.GEN||{};", "const GEN={};")
rep("const CL=DATA.CL||{};", "const CL={};")
# META/CNT/POOL を記事ごとに作る関数へ
rep("const META=[], CNT=[];\nF.forEach((f,i)=>{ META[i]=null; CNT[i]={};\n  for(const e of (EXT[i]||[])){ if(e[0]==='_m'){ META[i]={sl:e[1],ch:Math.round(e[2]/3),lh:e[3],lhp:e[4],pv:e[5]}; continue; } CNT[i][e[0]]=e[1]; } });",
"const META=[], CNT=[];\nfunction prepMeta(i){ META[i]=null; CNT[i]={};\n  for(const e of (EXT[i]||[])){ if(e[0]==='_m'){ META[i]={sl:e[1],ch:Math.round(e[2]/3),lh:e[3],lhp:e[4],pv:e[5]}; continue; } CNT[i][e[0]]=e[1]; } }")
rep("const POOL=F.map((f,i)=>{ const out=[...f[7]];", "const POOL=[];\nfunction makePool(i){ const f=F[i]; const out=[...f[7]];")
i = s.index("function makePool(i)"); j = s.index("  return out; });", i)
s = s[:j] + "  return out; }" + s[j + len("  return out; });"):]
# 登録：記事レコードを番号に割り当て、技の候補まで作る
rep("const HOLD=DATA.HOLD||{};", "const HOLD={};")
rep("const QIX={}; F.forEach((f,i)=>QIX[f[2]]=i);", """const QIX={};
function register(rec){ const t=rec.f[1]; /* 振り分けは正式な記事名で（表示名は同名の別記事と重なることがある） */ if(TIX[t]!==undefined) return TIX[t]; const i=F.length;
  F.push(rec.f); TIX[t]=i; QIX[rec.f[2]]=i; EXT[i]=rec.ext||[]; if(rec.qt) QT[i]=rec.qt; if(rec.wp) WP[i]=rec.wp; if(rec.gen) GEN[i]=rec.gen; if(rec.hold) HOLD[i]=rec.hold;
  for(const [q,txt] of Object.entries(rec.rv||{})){ const j=QIX[q]; if(j!==undefined&&j!==i) RV[Math.min(i,j)+','+Math.max(i,j)]=txt; }
  prepMeta(i); POOL[i]=makePool(i); if(rec.hold||EXCL.has(t)) BLOCK.add(i); return i; }""")

# ---- 2. 保留・通報：確認画面はなくし、保留と除外リストの記事は選べないだけにする ----
rep_span("let DEC={}, REPS=[], isAdmin=false, dbRef=null;", "}catch(_){} })();",
"""const BLOCK=new Set();
function setCount(){ try{ document.getElementById('eyebrow').textContent='ひゃっかけんてん ／ '+N.toLocaleString('ja-JP')+'記事収録'; }catch(_){} }""")

# ---- 3. 選手選び：記事名で読み込む。候補は人気記事＋Wikipediaの検索候補 ----
rep("const rnd=(ex)=>{ let i; do{ i=Math.floor(Math.random()*N); }while(ex.includes(i)||BLOCK.has(i)); return i; };",
"""// ランダム：半分は人気記事から、半分は全記事から（振り分けファイルを1つ引いて、その中から選ぶ）
async function rnd(ex){ for(let k=0;k<12;k++){ let t;
    if(Math.random()<0.5&&POPULAR.length) t=POPULAR[Math.floor(Math.random()*POPULAR.length)];
    else { const b=await bucket(Math.floor(Math.random()*NB)); const ks=Object.keys(b); if(!ks.length) continue; t=ks[Math.floor(Math.random()*ks.length)]; }
    const i=await loadTitle(t); if(i>=0&&!ex.includes(i)&&!BLOCK.has(i)) return i; }
  return ex.includes(0)?1:0; }""")
rep("""<input id="in${side}" list="names" placeholder="記事名を入力（例：富士山）" value="${i===null?'':esc(F[i][0])}" aria-label="${side===0?'青コーナー':'赤コーナー'}の記事">""",
    """<input id="in${side}" list="names${side}" placeholder="記事名を入力（例：富士山）" value="${i===null?'':esc(F[i][0])}" aria-label="${side===0?'青コーナー':'赤コーナー'}の記事" autocomplete="off"><datalist id="names${side}"></datalist>""")
rep("${i===null?'<div class=\"empty\">'+N+'記事から選べます。候補は入力すると出てきます。</div>':fighterCard(i)}`;",
    "${i===null?'<div class=\"empty\">'+N.toLocaleString('ja-JP')+'記事から選べます。日本語版Wikipediaの記事名を入れてください。</div>':fighterCard(i)}`;")
rep("""  el.querySelector('input').addEventListener('change',e=>{ const k=NAMES.indexOf(e.target.value.trim()); if(k>=0&&BLOCK.has(k)){ e.target.value=''; e.target.placeholder='「'+NAMES[k]+'」は確認中のため選べません'; return; } if(k>=0){ sel[side]=k; streak={idx:null,n:0}; renderPick(side); updateFight(); } });
  el.querySelector('[data-rnd]').onclick=()=>{ sel[side]=rnd([sel[1-side]]); streak={idx:null,n:0}; renderPick(side); updateFight(); };""",
"""  const inp=el.querySelector('input'), dl=el.querySelector('datalist'); let tm=null, seq=0;
  inp.addEventListener('input',()=>{ clearTimeout(tm); const v=inp.value.trim(); if(!v) return; tm=setTimeout(async()=>{ const my=++seq;
    try{ const r=await fetch('https://ja.wikipedia.org/w/api.php?action=opensearch&format=json&origin=*&namespace=0&redirects=resolve&limit=10&search='+encodeURIComponent(v)); const j=await r.json(); if(my!==seq) return;
      dl.innerHTML=(j[1]||[]).map(n=>`<option value="${esc(n)}"></option>`).join(''); }catch(_){} },250); });
  inp.addEventListener('change',async e=>{ const v=e.target.value.trim(); if(!v) return; const note=el.querySelector('.empty');
    if(note) note.textContent='「'+v+'」を探しています…';
    let k=-1; try{ k=await loadTitle(v); }catch(_){ if(note) note.textContent='読み込めませんでした。通信状態を確かめて、もう一度入れてください。'; return; }
    if(k<0){ e.target.value=''; e.target.placeholder='「'+v+'」は収録していません'; if(note) note.textContent='「'+v+'」は収録していません。記事名が正確か確かめてください。一覧・曖昧さ回避のページや、事件・事故・災害など扱わない題材は入っていません。'; return; }
    if(BLOCK.has(k)){ e.target.value=''; e.target.placeholder='「'+v+'」は確認中のため選べません'; if(note) note.textContent='「'+v+'」は内容を確認中のため、いまは選べません。'; return; }
    sel[side]=k; streak={idx:null,n:0}; renderPick(side); updateFight(); });
  el.querySelector('[data-rnd]').onclick=async()=>{ sel[side]=await rnd([sel[1-side]]); streak={idx:null,n:0}; renderPick(side); updateFight(); };""")
rep("$('#omakase').onclick=()=>{ sel[0]=rnd([]); sel[1]=rnd([sel[0]]);", "$('#omakase').onclick=async()=>{ sel[0]=await rnd([]); sel[1]=await rnd([sel[0]]);")
rep("if($('#cont')) $('#cont').onclick=()=>{ const keep=w; const side=keep===ai?0:1; sel[side]=keep; sel[1-side]=rnd([keep]);",
    "if($('#cont')) $('#cont').onclick=async()=>{ const keep=w; const side=keep===ai?0:1; sel[side]=keep; sel[1-side]=await rnd([keep]);")
rep("$('#again').onclick=()=>{ streak={idx:null,n:0}; sel[0]=rnd([]); sel[1]=rnd([sel[0]]);",
    "$('#again').onclick=async()=>{ streak={idx:null,n:0}; sel[0]=await rnd([]); sel[1]=await rnd([sel[0]]);")

# ---- 4. 通報：GitHubのIssueを、記事名と理由が入った状態で開く ----
i = s.index("  document.querySelectorAll('[data-rep]').forEach(btn=>btn.onclick=async()=>{"); j = s.index("document.querySelectorAll('[data-rep]').forEach(x=>x.disabled=false); } });", i)
j += len("document.querySelectorAll('[data-rep]').forEach(x=>x.disabled=false); } });")
s = s[:i] + """  document.querySelectorAll('[data-rep]').forEach(btn=>btn.onclick=()=>{ const kind=btn.dataset.rep;
    const tgt=kind==='a'?F[ai][0]:kind==='b'?F[bi][0]:F[ai][0]+' 対 '+F[bi][0];
    const title=(kind==='text'?'【文面】':'【記事】')+tgt;
    const body='対戦：'+F[ai][0]+' 対 '+F[bi][0]+'\\n対象：'+(kind==='text'?'実況の文面':tgt+'の記事')+'\\n\\n気になった点（任意）：\\n';
    window.open('""" + REPO + """/issues/new?labels=report&title='+encodeURIComponent(title)+'&body='+encodeURIComponent(body),'_blank','noopener');
    $('#repmsg').textContent='GitHubの報告ページを開きました（GitHubのアカウントが必要です）。確認して、必要なら収録から外します。'; });""" + s[j:]

# ---- 5. 初期表示 ----
rep("""sel=[NAMES.indexOf('東京タワー'),NAMES.indexOf('エッフェル塔')]; if(sel[0]<0||sel[1]<0||BLOCK.has(sel[0])||BLOCK.has(sel[1])){ sel[0]=rnd([]); sel[1]=rnd([sel[0]]); }
renderPick(0); renderPick(1); updateFight(); renderRec(); recompute();""",
"""renderRec();
(async()=>{ try{
  const [m,ex]=await Promise.all([fetch('data/meta.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.json()), fetch('data/exclude.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():[]).catch(()=>[])]);
  N=m.n-(m.hold||0); NB=m.nb; VER=m.build||m.asof; POPULAR=m.popular||[]; EXCL=new Set(ex); setCount();
  sel=[await loadTitle('東京タワー'),await loadTitle('エッフェル塔')];
  if(sel[0]<0||sel[1]<0||BLOCK.has(sel[0])||BLOCK.has(sel[1])){ sel[0]=await rnd([]); sel[1]=await rnd([sel[0]]); }
}catch(e){ $('#pickA').innerHTML='<div class="empty">記事データを読み込めませんでした。ページを再読み込みしてください。</div>'; return; }
  renderPick(0); renderPick(1); updateFight(); })();""")


# ---- 6. 結果を記事の読み込み順に左右されないようにする（番号ではなくQIDで順序・乱数を決める） ----
rep("const rival=(i,j)=>RV[Math.min(i,j)+','+Math.max(i,j)]||null;",
    "const rival=(i,j)=>RV[Math.min(i,j)+','+Math.max(i,j)]||null;\nconst QN=i=>+String(F[i][2]).slice(1), lt=(i,j)=>QN(i)<QN(j)||(QN(i)===QN(j)&&i<j), QK=(i,j)=>lt(i,j)?F[i][2]+'/'+F[j][2]:F[j][2]+'/'+F[i][2];")
rep("hash(Math.min(i,j)+'/'+Math.max(i,j)+'/'+i+c.m[1])", "hash(QK(i,j)+'/'+F[i][2]+c.m[1])")
rep("hash('kb'+Math.min(ai,bi)+'/'+Math.max(ai,bi))", "hash('kb'+QK(ai,bi))")
rep("  if(ai<bi) return simulate(ai,bi,opt);", "  if(lt(ai,bi)) return simulate(ai,bi,opt);")
rep("const K0=ai+'/'+bi;", "const K0=F[ai][2]+'/'+F[bi][2];")
# 分類（同じ種類どうしの比べ合いに使う）
rep("prepMeta(i); POOL[i]=makePool(i);", "CL[i]=rec.p?['Q5','ヒト']:(rec.gen&&rec.gen.c?[rec.gen.c,rec.gen.c]:undefined); prepMeta(i); POOL[i]=makePool(i);")


# ---- 7. 単独のページとして公開するための頭の部分 ----
rep('<title>百科拳典</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n',
"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>百科拳典（ひゃっかけんてん）</title>
<meta name="description" content="Wikipediaの記事が、事実だけで殴り合う。日本語版Wikipediaの約140万記事から2つ選ぶと、WikidataとWikipediaに載っている事実だけで真面目に戦います。">
<meta property="og:title" content="百科拳典（ひゃっかけんてん）">
<meta property="og:description" content="Wikipediaの記事が、事実だけで殴り合う。">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
""")
rep('</style>\n', '</style>\n</head>\n<body>\n', 1)
s = s.rstrip() + '\n</body>\n</html>\n'


# ---- 8. 王座戦：いまの王者に挑み、勝てば王座を奪う（勝敗はサーバーが計算し直して決める） ----
API = os.environ.get('HK_API', '')
rep('.card{background:var(--paper);border:1px solid var(--line);border-radius:6px}',
""".card{background:var(--paper);border:1px solid var(--line);border-radius:6px}
#throne{padding:16px;display:flex;flex-direction:column;gap:12px;border-top:4px solid var(--hl)}
#throne .crown{font-size:12px;letter-spacing:.12em;color:var(--muted)}
#throne .champ{font-family:var(--f-display);font-weight:400;font-size:clamp(22px,5vw,30px);line-height:1.2;overflow-wrap:anywhere}
#throne .champ a{font-family:var(--f-body);font-size:12px;margin-left:8px}
#throne .meta{font-size:13px;color:var(--muted)}
#throne .meta b{color:var(--ink)}
#throne form{display:flex;flex-wrap:wrap;gap:8px;align-items:stretch}
#throne input{flex:1 1 200px;min-width:0;font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:4px;background:var(--bg);color:var(--ink)}
#throne input.nm{flex:0 1 150px}
#throne .msg{font-size:14px;min-height:1.4em}
#throne .msg.win{font-weight:700;color:var(--ok)}
#throne .msg.err{color:var(--b)}
#throne details{border-top:1px solid var(--line);padding-top:8px}
#throne summary{cursor:pointer;font-size:13px;color:var(--muted)}
#throne ol{margin:8px 0 0;padding-left:1.4em;font-size:13px;display:flex;flex-direction:column;gap:4px}
#throne ol .who{color:var(--muted)}
#throne .r-win{color:var(--ok);font-weight:700}
""")
rep('  <section id="setup" class="card"', """  <section id="throne" class="card" hidden aria-live="polite"></section>

  <section id="setup" class="card\"""")
rep("renderRec();\n(async()=>{ try{", """/* ---------- 王座戦 ---------- */
const API=""" + ("(location.hostname.endsWith('github.io')?'https://hyakka-kenten-api.y-krn.workers.dev':location.origin)" if API=='same' else "'"+API+"'") + """;
let THRONE=null;
const dt=s=>{ try{ const d=new Date(s); return (d.getMonth()+1)+'/'+d.getDate()+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0'); }catch(_){ return ''; } };
const RES={win:'<span class="r-win">王座奪取</span>',lose:'防衛',draw:'引き分け（防衛）',late:'ひと足遅れ'};
function renderThrone(d,msg){ const el=$('#throne'); if(!d){ el.hidden=true; return; } THRONE=d; const c=d.champ; el.hidden=false;
  let nm=''; try{ nm=localStorage.getItem('hk-name')||''; }catch(_){}
  el.innerHTML=`<div class="crown">王座戦 ／ 第${d.reignNo}代王者</div>
  <div class="champ">${esc(c.display)}<a href="https://ja.wikipedia.org/wiki/${encodeURIComponent(c.title)}" target="_blank" rel="noopener">記事 ↗</a></div>
  <div class="meta">防衛 <b>${c.defenses}</b>回 ／ 王座を取った人：<b>${esc(c.holder)}</b> ／ ${esc(dt(c.started_at))}から在位</div>
  <div class="meta">この王者を倒せる記事を、約140万記事の中から探してください。勝てば王座はあなたの記事のもの。結果は何度やっても同じなので、一度王座戦で戦った組み合わせは、もう戦えません。</div>
  <form id="chf"><input id="chT" list="chL" placeholder="挑戦する記事名" autocomplete="off" aria-label="挑戦する記事名"><datalist id="chL"></datalist>
    <input id="chN" class="nm" maxlength="16" placeholder="名前（任意）" value="${esc(nm)}" aria-label="名前"><button type="submit" class="btn">挑戦する</button></form>
  <div class="msg" id="chM">${msg||''}</div>
  <details><summary>最近の挑戦</summary><ol>${d.recent.map(x=>`<li>${esc(x.display)} <span class="who">（${esc(x.name)}・${esc(dt(x.at))}）</span> … ${RES[x.result]||''}</li>`).join('')||'<li>まだ挑戦はありません</li>'}</ol></details>
  <details><summary>最長防衛ランキング</summary><ol>${d.best.map(x=>`<li><b>${esc(x.display)}</b> 防衛${x.defenses}回 <span class="who">（${esc(x.holder)}${x.ended_at?'':'・在位中'}）</span></li>`).join('')}</ol></details>
  <details><summary>歴代王者</summary><ol reversed>${d.history.map(x=>`<li><b>${esc(x.display)}</b> 防衛${x.defenses}回 <span class="who">（${esc(x.holder)}・${esc(dt(x.started_at))}〜${x.ended_by?'、'+esc(x.ended_by)+'に敗れる':'在位中'}）</span></li>`).join('')}</ol></details>`;
  const inp=$('#chT'), dl=$('#chL'); let tm=null, sq=0;
  inp.addEventListener('input',()=>{ clearTimeout(tm); const v=inp.value.trim(); if(!v) return; tm=setTimeout(async()=>{ const my=++sq;
    try{ const j=await fetch('https://ja.wikipedia.org/w/api.php?action=opensearch&format=json&origin=*&namespace=0&redirects=resolve&limit=10&search='+encodeURIComponent(v)).then(r=>r.json()); if(my!==sq) return;
      dl.innerHTML=(j[1]||[]).map(n=>`<option value="${esc(n)}"></option>`).join(''); }catch(_){} },250); });
  $('#chf').onsubmit=e=>{ e.preventDefault(); doChallenge(); }; }
async function loadThrone(msg){ if(!API) return; try{ const d=await fetch(API+'/api/throne').then(r=>r.json()); if(d&&d.champ) renderThrone(d,msg); }catch(_){} }
async function doChallenge(){ const t=$('#chT').value.trim(), name=$('#chN').value.trim(), m=$('#chM'), btn=$('#chf button');
  if(!t){ m.className='msg err'; m.textContent='挑戦する記事名を入れてください'; return; }
  try{ localStorage.setItem('hk-name',name); }catch(_){}
  btn.disabled=true; m.className='msg'; m.textContent='「'+t+'」で挑戦しています…';
  let d; try{ const r=await fetch(API+'/api/challenge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:t,name})}); d=await r.json(); }
  catch(_){ btn.disabled=false; m.className='msg err'; m.textContent='送れませんでした。通信状態を確かめてください。'; return; }
  btn.disabled=false;
  if(d.error){ m.className='msg err'; m.textContent=d.error; return; }
  const msg=d.result==='win'?`<span class="msg win">${esc(d.challenger.display)}が${esc(d.champ.display)}を倒し、新王者になりました！（${esc(d.how||'')}）</span>`:
    d.result==='late'?`${esc(d.challenger.display)}は勝ちましたが、ひと足先に別の挑戦者が王者を倒していました。新しい王者に挑み直してください。`:
    d.result==='draw'?`${esc(d.challenger.display)}は引き分け。王者${esc(d.champ.display)}の防衛です。`:`${esc(d.champ.display)}の防衛（${d.champ.defenses}回目）。${esc(d.challenger.display)}は敗れました。`;
  // 対戦の中身をリングで見せる（同じ計算なので、サーバーと同じ結果になる）
  try{ const a=await loadTitle(d.challenger.title), b=await loadTitle(d.champ.title); if(a>=0&&b>=0){ sel=[a,b]; streak={idx:null,n:0}; renderPick(0); renderPick(1); updateFight(); startBattle(); } }catch(_){}
  await loadThrone(msg); }

renderRec();
(async()=>{ try{""")
rep("  renderPick(0); renderPick(1); updateFight(); })();", "  renderPick(0); renderPick(1); updateFight(); loadThrone(); })();")


# ---- 9. スマホ：入力欄に触れたときの自動拡大と、横方向のぐらつきを防ぐ ----
rep('</style>\n</head>', """html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
html,body{overflow-x:clip;max-width:100%}
input,select,textarea{font-size:16px!important}   /* iPhoneは16px未満の入力欄に触れると画面を拡大し、横にずれる */
</style>
</head>""")


# ---- 10. 対戦カード：技の一覧は畳んでおき、誰と誰の対戦かを先に見せる ----
rep("""<div class="empty">技の候補（相手に合わせて4つ選び、数字で勝っている相手には比べ技も出す）</div><ul class="moves">${POOL[i].map(m=>`<li><span class="mn">${esc(m[1])}</span><span class="mf">${esc(m[3])}</span></li>`).join('')}</ul>`; }""",
"""<details class="mvs"${WIDE()?' open':''}><summary>技の候補 ${POOL[i].length}個<span class="mvp">（${esc(POOL[i].slice(0,3).map(m=>m[1]).join('・'))}${POOL[i].length>3?' など':''}）</span></summary>
  <div class="empty">相手に合わせて4つ選び、数字で勝っている相手には比べ技も出す</div><ul class="moves">${POOL[i].map(m=>`<li><span class="mn">${esc(m[1])}</span><span class="mf">${esc(m[3])}</span></li>`).join('')}</ul></details>`; }
const WIDE=()=>{ try{ return matchMedia('(min-width: 720px)').matches; }catch(_){ return false; } };""")
rep('.fname a{font-size:12px;color:var(--muted)}', """.fname a{font-size:12px;color:var(--muted)}
.mvs{border-top:1px solid var(--line);padding-top:6px}
.mvs summary{cursor:pointer;font-size:13px;color:var(--muted);list-style-position:inside}
.mvs .mvp{font-size:12px}
.mvs[open] .mvp{display:none}
.mvs .empty{margin:6px 0}
.matchup{font-family:var(--f-display);font-weight:400;font-size:18px;line-height:1.35;text-align:center;overflow-wrap:anywhere}
.matchup .a{color:var(--a)} .matchup .b{color:var(--b)} .matchup .vs{color:var(--muted);font-size:14px;margin:0 .5em}""")
rep('<div class="go">', '<div class="matchup" id="mu" aria-live="polite"></div>\n    <div class="go">')
rep("function updateFight(){ $('#fight').disabled=!(sel[0]!==null&&sel[1]!==null&&sel[0]!==sel[1]); }",
    "function updateFight(){ $('#fight').disabled=!(sel[0]!==null&&sel[1]!==null&&sel[0]!==sel[1]);\n  const n=k=>sel[k]===null?'？':esc(F[sel[k]][0]); $('#mu').innerHTML=`<span class=\"a\">${n(0)}</span><span class=\"vs\">VS</span><span class=\"b\">${n(1)}</span>`; }")


# ---- 11. 足もとのルール説明（計算式）は公開しない ----
s = re.sub(r'\n    <span>ルール：[^\n]*</span>', '', s, count=1)
assert 'ルール：' not in s


# ---- 12. 「王座戦」と「自由対戦」を見出しで分ける ----
rep('<section id="setup" class="card" style="padding:16px;display:flex;flex-direction:column;gap:14px">',
    '<section id="setup" class="card" style="padding:16px;display:flex;flex-direction:column;gap:14px">\n    <div class="sechead"><h2>自由対戦</h2><span>好きな2記事を選んで戦わせる。結果は記録に残りません</span></div>')
rep('<div class="crown">王座戦 ／ 第${d.reignNo}代王者</div>',
    '<div class="sechead"><h2>王座戦</h2><span>いまの王者に挑み、勝てば王座を奪う</span></div>\n  <div class="crown">第${d.reignNo}代王者</div>')
rep('#throne{padding:16px;display:flex;flex-direction:column;gap:12px;border-top:4px solid var(--hl)}',
    """#throne{padding:16px;display:flex;flex-direction:column;gap:12px;border-top:4px solid var(--hl);background:color-mix(in srgb,var(--hl) 9%,var(--paper))}
#setup{border-top:4px solid var(--line)}
.sechead{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.sechead h2{margin:0;font-family:var(--f-display);font-weight:400;font-size:20px;line-height:1.3}
.sechead span{font-size:12px;color:var(--muted)}""")


# ---- 13. 王座戦の試合は、自由対戦と見た目・置き場所・結果の札を分ける ----
rep("let timer=null, current=null;", """let timer=null, current=null, MODE=null;   // MODE：王座戦の挑戦なら {res, no}
function ringHead(m){ if(!m) return '<div class="ringhead">自由対戦</div>';
  return `<div class="ringhead th">王座戦 ／ 第${m.no}代王者 ${esc(m.res.champ.display)} に ${esc(m.res.challenger.display)} が挑む</div>`; }""")
rep("const an=analyze(ai,bi); current={ai,bi,an};", """const an=analyze(ai,bi); current={ai,bi,an,mode:MODE}; MODE=null;""")
rep("const {r}=an; const ring=$('#ring'); ring.hidden=false;", """const {r}=an; const ring=$('#ring'); ring.hidden=false;
  (current.mode?$('#throne'):$('#setup')).after(ring); ring.classList.toggle('thmode',!!current.mode);""")
rep("""  ring.innerHTML=`
  <div class="mtype">""", """  ring.innerHTML=`
  ${ringHead(current.mode)}<div class="mtype">""")
rep("""  if(w!==null){ if(streak.idx===w) streak.n++; else streak={idx:w,n:1}; rec.best=Math.max(rec.best,streak.n); } else streak={idx:null,n:0};""",
"""  const M=current.mode;
  if(M) streak={idx:null,n:0};
  else if(w!==null){ if(streak.idx===w) streak.n++; else streak={idx:w,n:1}; rec.best=Math.max(rec.best,streak.n); } else streak={idx:null,n:0};""")
rep("""  const title=w===null?'引き分け':`${F[w][0]}の勝ち`;""",
"""  let title=w===null?'引き分け':`${F[w][0]}の勝ち`;
  if(M){ const x=M.res; title=x.result==='win'?`新王者誕生！ 第${M.no+1}代王者 ${x.challenger.display}`:x.result==='late'?`${x.challenger.display}の勝ち。ただし王座はすでに別の記事へ`:x.result==='draw'?`引き分け。王者${x.champ.display}の防衛`:`王者${x.champ.display}、${x.champ.defenses}度目の防衛`; }""")
rep("""  const share=w===null?`【百科拳典】""", """  let share=w===null?`【百科拳典】""")
rep("""  const seen=new Map(); r.summoned.forEach(t=>seen.set(t[2],t));""",
"""  if(M){ const x=M.res; share=share.replace('【百科拳典】','【百科拳典 王座戦】')+(x.result==='win'?`第${M.no+1}代王者に。`:x.result==='lose'||x.result==='draw'?`王者は${x.champ.defenses}度目の防衛。`:''); }
  const seen=new Map(); r.summoned.forEach(t=>seen.set(t[2],t));""")
rep("""    <div class="next">
      ${w!==null?`<button type="button" class="btn big" id="cont">${esc(F[w][0])}に次の挑戦者</button>`:''}
      <button type="button" class="btn" id="again">別の組み合わせ</button>
      <button type="button" class="btn" id="back">選び直す</button>
    </div>""", """    <div class="next">${M?`
      <button type="button" class="btn big" id="thr">${M.res.result==='win'?'新王者に挑む':'別の記事で挑む'}</button>
      <button type="button" class="btn" id="tofree">自由対戦へ</button>`:`
      ${w!==null?`<button type="button" class="btn big" id="cont">${esc(F[w][0])}に次の挑戦者</button>`:''}
      <button type="button" class="btn" id="again">別の組み合わせ</button>
      <button type="button" class="btn" id="back">選び直す</button>`}
    </div>""")
rep("""  $('#again').onclick=async()=>{""", """  if(M){ $('#thr').onclick=()=>{ $('#throne').scrollIntoView({behavior:'smooth',block:'start'}); setTimeout(()=>{ const t=$('#chT'); if(t) t.focus({preventScroll:true}); },400); };
    $('#tofree').onclick=()=>{ $('#setup').scrollIntoView({behavior:'smooth',block:'start'}); }; }
  if($('#again')) $('#again').onclick=async()=>{""")
rep("""  $('#back').onclick=()=>{ $('#setup').scrollIntoView""", """  if($('#back')) $('#back').onclick=()=>{ $('#setup').scrollIntoView""")
# 挑戦したときは王座戦の試合として再生する
rep("if(a>=0&&b>=0){ sel=[a,b]; streak={idx:null,n:0}; renderPick(0); renderPick(1); updateFight(); startBattle(); }",
    "if(a>=0&&b>=0){ MODE={res:d,no:THRONE?THRONE.reignNo:1}; startBattle([a,b]); }")   # 自由対戦のカードは書き換えない
rep("function startBattle(){\n  clearInterval(timer);\n  const [ai,bi]=sel;", "function startBattle(pair){\n  clearInterval(timer);\n  const [ai,bi]=pair||sel;")
rep('#setup{border-top:4px solid var(--line)}', """#setup{border-top:4px solid var(--line)}
.ringhead{font-size:13px;font-weight:700;color:var(--muted);letter-spacing:.06em;padding:4px 0 6px;border-bottom:1px solid var(--line);margin-bottom:6px}
.ringhead.th{color:var(--ink);background:color-mix(in srgb,var(--hl) 35%,var(--paper));border:none;border-radius:4px;padding:6px 10px}
.thmode .result{box-shadow:0 0 0 4px var(--hl) inset}
.thmode .result .win{color:var(--hl)}""")


# ---- 14. 自由対戦では、いまの王者を選べないようにする（王者との勝負は王座戦だけ） ----
rep("let THRONE=null;", """let THRONE=null;
const isChamp=i=>!!(THRONE&&i!==null&&i>=0&&F[i]&&F[i][1]===THRONE.champ.title);
async function fixChamp(){ for(const s of [0,1]){ if(isChamp(sel[s])){ sel[s]=await rnd([sel[1-s]]); renderPick(s); const n=$(s===0?'#pickA':'#pickB').querySelector('.empty'); if(n) n.textContent='いまの王者は自由対戦に出せないので、入れ替えました'; } } updateFight(); }""")
rep("const i=await loadTitle(t); if(i>=0&&!ex.includes(i)&&!BLOCK.has(i)) return i; }",
    "const i=await loadTitle(t); if(i>=0&&!ex.includes(i)&&!BLOCK.has(i)&&!isChamp(i)) return i; }")
rep("if(note) note.textContent='「'+v+'」は内容を確認中のため、いまは選べません。'; return; }",
    "if(note) note.textContent='「'+v+'」は内容を確認中のため、いまは選べません。'; return; }\n    if(isChamp(k)){ e.target.value=''; e.target.placeholder='「'+v+'」はいまの王者です'; if(note) note.textContent='「'+v+'」はいまの王者なので、自由対戦には出せません。戦わせたいときは、上の王座戦から挑んでください。'; return; }")
rep("const [ai,bi]=pair||sel; if(ai===null||bi===null||BLOCK.has(ai)||BLOCK.has(bi)) return;",
    "const [ai,bi]=pair||sel; if(ai===null||bi===null||BLOCK.has(ai)||BLOCK.has(bi)) return;\n  if(!pair&&(isChamp(ai)||isChamp(bi))){ fixChamp(); return; }")
rep("if(d&&d.champ) renderThrone(d,msg);", "if(d&&d.champ){ renderThrone(d,msg); fixChamp(); }")


# ---- 15. 記事選びのお知らせは、技一覧（畳まれている）ではなく入力欄のすぐ下に出す ----
rep('data-rnd="${side}">ランダム</button></div>', 'data-rnd="${side}">ランダム</button></div>\n  <div class="pmsg" aria-live="polite"></div>')
rep("const note=el.querySelector('.empty');", "const note=el.querySelector('.pmsg');")
rep("querySelector('.empty'); if(n) n.textContent='いまの王者", "querySelector('.pmsg'); if(n) n.textContent='いまの王者")
rep('.matchup{', '.pmsg{font-size:13px;color:var(--b)}\n.pmsg:empty{display:none}\n.matchup{')


# ---- 16. 自由対戦の初期表示は、毎回ランダムな組み合わせにする ----
rep("""  sel=[await loadTitle('東京タワー'),await loadTitle('エッフェル塔')];
  if(sel[0]<0||sel[1]<0||BLOCK.has(sel[0])||BLOCK.has(sel[1])){ sel[0]=await rnd([]); sel[1]=await rnd([sel[0]]); }""",
"""  sel[0]=await rnd([]); sel[1]=await rnd([sel[0]]);""")


# ---- 17. Google Search Console の所有権確認 ----
# （GitHub Pages時代の Search Console 確認用タグは、hyakkakenten.com への引っ越しで不要になったので外した）
# rep('<meta name="twitter:card" content="summary">\n', '<meta name="twitter:card" content="summary">\n<meta name="google-site-verification" content="3es2dab9K6v41F4ald_9FXt0Djnh8pU9qI8MPVjV5f0" />\n')


# ---- 18. 対戦URLで共有：?a=記事&b=記事（自由対戦）／?c=挑戦の番号（王座戦の記録） ----
rep("current={ai,bi,an,mode:MODE}; MODE=null;", "current={ai,bi,an,mode:MODE}; MODE=null; try{ history.replaceState(null,'',battleURL()); }catch(_){}")
rep("  const seen=new Map(); r.summoned.forEach(t=>seen.set(t[2],t));", "  const SHAREURL=battleURL();\n  const seen=new Map(); r.summoned.forEach(t=>seen.set(t[2],t));")
rep('<div class="share"><output id="share">${esc(share)}</output><button type="button" class="btn small" id="copy">コピー</button></div>',
    """<div class="share"><output id="share">${esc(share)}</output><button type="button" class="btn small" id="copy">コピー</button></div>
    <div class="share2"><a class="btn small" id="tw" target="_blank" rel="noopener" href="https://x.com/intent/tweet?text=${encodeURIComponent(share)}&url=${encodeURIComponent(SHAREURL)}">Xに投稿</a>${navigator.share?'<button type="button" class="btn small" id="nshare">共有</button>':''}<a class="url" href="${esc(SHAREURL)}">この試合のURL</a></div>""")
rep("const t=$('#share').textContent;", "const t=$('#share').textContent+'\\n'+SHAREURL;")
rep("  $('#copy').onclick=async", "  if($('#nshare')) $('#nshare').onclick=()=>{ navigator.share({title:'百科拳典',text:$('#share').textContent,url:SHAREURL}).catch(()=>{}); };\n  $('#copy').onclick=async")
rep('.share{display:flex', '.share2{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px}\n.share2 .url{font-size:12px;color:inherit;opacity:.8}\n.share{display:flex')
rep('return `<div class="ringhead th">王座戦 ／ 第${m.no}代王者', 'return `<div class="ringhead th">${m.replay?\'王座戦の記録（\'+esc(dt(m.res.at))+\'）\':\'王座戦\'} ／ 第${m.no}代王者')
rep("MODE={res:d,no:THRONE?THRONE.reignNo:1}", "MODE={res:d,no:d.reignNo||(THRONE?THRONE.reignNo:1)}")
rep("let THRONE=null;", """let THRONE=null;
function battleURL(){ const base=location.origin+location.pathname; if(!current) return base;
  if(current.mode&&current.mode.res&&current.mode.res.id) return base+'?c='+current.mode.res.id;
  return base+'?a='+encodeURIComponent(F[current.ai][1])+'&b='+encodeURIComponent(F[current.bi][1]); }
// 共有URLから開いたとき：その試合を再生する。うまくいかなければ false
async function openShared(){ const q=new URLSearchParams(location.search);
  if(q.get('c')&&API){ try{ await loadThrone(); const x=await fetch(API+'/api/challenge/'+encodeURIComponent(q.get('c'))).then(r=>r.json()); if(x.error) return false;
      const a=await loadTitle(x.challenger.title), b=await loadTitle(x.champ.title); if(a<0||b<0) return false;
      sel[0]=await rnd([a,b]); sel[1]=await rnd([a,b,sel[0]]); renderPick(0); renderPick(1); updateFight();
      MODE={res:x,no:x.reignNo,replay:true}; startBattle([a,b]); return true; }catch(_){ return false; } }
  const ta=q.get('a'), tb=q.get('b'); if(!ta||!tb) return false;
  await loadThrone();
  const ids=[await loadTitle(ta).catch(()=>-1), await loadTitle(tb).catch(()=>-1)]; const why=[];
  for(const s of [0,1]){ const i=ids[s], t=[ta,tb][s];
    if(i<0) why[s]='「'+t+'」は収録していないので、別の記事にしました';
    else if(BLOCK.has(i)) why[s]='「'+t+'」は確認中なので、別の記事にしました';
    else if(isChamp(i)) why[s]='「'+t+'」はいまの王者なので自由対戦に出せません。別の記事にしました';
    else sel[s]=i; }
  for(const s of [0,1]) if(why[s]) sel[s]=await rnd([sel[1-s]]);
  renderPick(0); renderPick(1); updateFight();
  for(const s of [0,1]) if(why[s]){ const n=$(s===0?'#pickA':'#pickB').querySelector('.pmsg'); if(n) n.textContent=why[s]; }
  if(!why[0]&&!why[1]) startBattle(); return true; }""")
rep("  sel[0]=await rnd([]); sel[1]=await rnd([sel[0]]);", "  if(await openShared()) return; sel[0]=await rnd([]); sel[1]=await rnd([sel[0]]);")


# ---- 19. ファビコン・ホーム画面のアイコン・共有カードの画像 ----
rep('<meta name="twitter:card" content="summary">\n', """<meta name="twitter:card" content="summary">
<meta property="og:image" content="https://hyakkakenten.com/og.png">
<meta property="og:url" content="https://hyakkakenten.com/">
<link rel="canonical" href="https://hyakkakenten.com/">
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="favicon-16.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#0e288c">
""")


# ---- 20. 共有ボタンが使える端末（スマホ）ではコピーボタンを出さない。パソコンなど共有できない端末だけに残す ----
rep('<output id="share">${esc(share)}</output><button type="button" class="btn small" id="copy">コピー</button>',
    '<output id="share">${esc(share)}</output>${navigator.share?\'\':\'<button type="button" class="btn small" id="copy">コピー</button>\'}')
rep("  $('#copy').onclick=async e=>", "  if($('#copy')) $('#copy').onclick=async e=>")


# ---- 21. 「言語版の数」は使わない（日本の記事が不利になり、不公平感が強いため） ----
n0 = len(s)
s = re.sub(r"\n    out\.push\(\['MULTI','多言語包囲'[^\n]*", '', s, count=1)
s = re.sub(r"\n  _sl:\{lab:'言語版の数'[^\n]*", '', s, count=1)
assert len(s) < n0 and '多言語包囲' not in s.split('const MID=')[0].split('function extMoves')[1][:3000] if 'function extMoves' in s else True
rep("const v=k==='_sl'?m.sl:", "if(k==='_sl') return null; const v=")
rep("['_sl','言語版の数','多くの言語で書かれているほう'],", "")


# 瞬殺のきっかけは、言語版の数の代わりに「1年間の閲覧数」で1200倍以上の差（どちらも日本語版の数字なので公平）
rep("R.filter(x=>PHYS.includes(x.k)||x.k==='_sl').map(x=>({...x,r:Math.max(x.a,x.b)/Math.min(x.a,x.b)})).filter(x=>x.r>=(x.k==='_sl'?40:1e4))",
    "R.filter(x=>PHYS.includes(x.k)||x.k==='_pv').map(x=>({...x,r:Math.max(x.a,x.b)/Math.min(x.a,x.b)})).filter(x=>x.r>=(x.k==='_pv'?1200:1e4))", 2)
rep("""      if(gap.k==='_sl'){
        log.push(sys(P(['{L}、礼儀正しく日本語で名乗る。','{L}、深く一礼して名乗りを上げる。日本語で。'],o)));
        log.push(sys(P(['{W}、{n}の言語で一斉に名乗り返す。{L}は最初の3言語までは聞き取れた。','{W}の名乗りが{n}の言語に翻訳されて会場に響く。{L}の名乗りは、日本語版にしか載っていない。','{W}、{n}言語分の名乗りを同時に上げる。通訳が足りず、会場は混乱した。'],o)));""",
"""      if(gap.k==='_pv'){
        log.push(sys(P(['{L}、名乗りを上げる。客席の反応は控えめだった。','{L}、深く一礼して入場する。拍手は、まばらだった。','{L}、入場。会場の何人かが、記事名を検索し始めた。'],o)));
        log.push(sys(P(['{W}が入場すると、{vw}読まれてきた視線が一斉に{L}へ向いた。','{W}は名乗る必要がない。{vw}読まれているので、全員もう知っている。','{L}の記事は{vl}、{W}は{vw}。読まれた回数の差が、そのまま圧になった。'],o)));""")


# ---- 22. 記事名は「候補から選ぶ」だけにする。候補はWikipediaの検索候補のうち、収録している記事だけ ----
rep("const TIX={};      // 記事名 → 番号", """const TIX={};      // 記事名 → 番号
const TIDX={};     // 記事名だけの索引（data/t/）：候補を収録記事に絞るため
async function tindex(k){ if(!TIDX[k]) TIDX[k]=fetch('data/t/'+k+'.json.gz?v='+VER).then(async r=>{ if(!r.ok) throw new Error(r.status);
    return new Set(JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text())); }).catch(()=>{ delete TIDX[k]; return new Set(); }); return TIDX[k]; }
async function inData(t){ return (await tindex(fnv(t)%NB)).has(t); }
// 入力に合う候補：Wikipediaの検索候補（読み・転送ページにも強い）から、収録している記事だけを残す
async function suggest(v,exclude){ const j=await fetch('https://ja.wikipedia.org/w/api.php?action=opensearch&format=json&origin=*&namespace=0&redirects=resolve&limit=20&search='+encodeURIComponent(v)).then(r=>r.json());
  const c=[...new Set(j[1]||[])]; const ok=await Promise.all(c.map(t=>inData(t))); return c.filter((t,i)=>ok[i]&&!(exclude&&exclude(t))).slice(0,10); }
const champTitle=()=>THRONE&&THRONE.champ?THRONE.champ.title:null;""")
# 自由対戦の入力欄
rep("""    try{ const r=await fetch('https://ja.wikipedia.org/w/api.php?action=opensearch&format=json&origin=*&namespace=0&redirects=resolve&limit=10&search='+encodeURIComponent(v)); const j=await r.json(); if(my!==seq) return;
      dl.innerHTML=(j[1]||[]).map(n=>`<option value="${esc(n)}"></option>`).join(''); }catch(_){} },250); });""",
"""    try{ const list=await suggest(v,t=>t===champTitle()); if(my!==seq) return; OPT=new Set(list);
      dl.innerHTML=list.map(n=>`<option value="${esc(n)}"></option>`).join('');
      const note=el.querySelector('.pmsg'); if(note){ if(!list.length) note.textContent='「'+v+'」に合う収録記事が見つかりません'; else if(/見つかりません$/.test(note.textContent)) note.textContent=''; } }catch(_){} },250); });""")
rep("const inp=el.querySelector('input'), dl=el.querySelector('datalist'); let tm=null, seq=0;",
    "const inp=el.querySelector('input'), dl=el.querySelector('datalist'); let tm=null, seq=0, OPT=new Set();")
rep("""  inp.addEventListener('change',async e=>{ const v=e.target.value.trim(); if(!v) return; const note=el.querySelector('.pmsg');""",
"""  inp.addEventListener('change',async e=>{ const v=e.target.value.trim(); if(!v) return; const note=el.querySelector('.pmsg');
    if(!OPT.has(v)){ if(note) note.textContent='入力すると出てくる候補の中から選んでください（収録している記事だけが候補に出ます）'; return; }""")
# 王座戦の入力欄
rep("""    try{ const j=await fetch('https://ja.wikipedia.org/w/api.php?action=opensearch&format=json&origin=*&namespace=0&redirects=resolve&limit=10&search='+encodeURIComponent(v)).then(r=>r.json()); if(my!==sq) return;
      dl.innerHTML=(j[1]||[]).map(n=>`<option value="${esc(n)}"></option>`).join(''); }catch(_){} },250); });""",
"""    try{ const list=await suggest(v,t=>t===champTitle()); if(my!==sq) return; CHOPT=new Set(list);
      dl.innerHTML=list.map(n=>`<option value="${esc(n)}"></option>`).join(''); }catch(_){} },250); });""")
rep("let THRONE=null;", "let THRONE=null, CHOPT=new Set();")
rep("""  if(!t){ m.className='msg err'; m.textContent='挑戦する記事名を入れてください'; return; }""",
"""  if(!t){ m.className='msg err'; m.textContent='挑戦する記事名を入れてください'; return; }
  if(!CHOPT.has(t)){ m.className='msg err'; m.textContent='入力すると出てくる候補の中から選んでください（収録している記事だけが候補に出ます）'; return; }""")

# ---- 23. 決め手は短くまとめる：勝者の決め手／裏目に出た技／因縁、を各1行に ----
rep("""  const lines=dec.map(d=>d.who===-1?`因縁の初撃1.5倍がなければ、${esc(nm(d.alt))}${d.alt===null?'':'の勝ち'}だった`:
    d.who===d.alt?`${esc(F[d.who][0])}が【${esc(d.move)}】を使わなければ、${esc(F[d.who][0])}の勝ちだった（自滅）`:
    `${esc(F[d.who][0])}の【${esc(d.move)}】がなければ、${esc(nm(d.alt))}${d.alt===null?'':'の勝ち'}だった`);""",
"""  const mv=(arr)=>arr.slice(0,3).map(d=>'【'+esc(d.move)+'】').join('')+(arr.length>3?'ほか'+(arr.length-3)+'つ':'');
  const byWho=i=>dec.filter(d=>d.who===i&&d.who!==d.alt);
  const lines=[];
  for(const i of (w===null?[ai,bi]:[w,l])){ const k=byWho(i); if(k.length) lines.push(`<b>${i===w?'決め手':'惜しかった'}</b>：${esc(F[i][0])}の${mv(k)}`); }
  for(const i of [ai,bi]){ const k=dec.filter(d=>d.who===i&&d.who===d.alt); if(k.length) lines.push(`<b>自滅</b>：${esc(F[i][0])}の${mv(k)}（使わなければ勝っていた）`); }
  if(dec.some(d=>d.who===-1)) lines.push('<b>因縁</b>：初撃の1.5倍がなければ、結果は違っていた');""")
rep("""lines.length?`<div><div class="sub">決め手（外して再試合すると結果が変わるもの）</div><ul>${lines.map(x=>`<li>${x}</li>`).join('')}</ul></div>`""",
    """lines.length?`<div class="keys">${lines.map(x=>`<div>${x}</div>`).join('')}</div>`""")
rep('.share2{display:flex', '.keys{display:flex;flex-direction:column;gap:2px;font-size:14px}\n.share2{display:flex')


rep('能力値だけなら${esc(nm(an.baseW))}が勝つ組み合わせ', '能力値だけなら${an.baseW===null?\'引き分けの\':esc(nm(an.baseW))+\'が勝つ\'}組み合わせ')


# ---- 24. 候補から選ぶまでは、対戦開始・挑戦のボタンを押せないようにする ----
rep("function updateFight(){ $('#fight').disabled=!(sel[0]!==null&&sel[1]!==null&&sel[0]!==sel[1]);",
    """const pickOK=s=>{ const i=sel[s]; if(i===null) return false; const e=$('#in'+s); if(!e) return true; const v=e.value.trim(); return v===F[i][0]||v===F[i][1]; };   // 入力欄を書き換え中（選び直す途中）は未確定
function updateFight(){ $('#fight').disabled=!(sel[0]!==null&&sel[1]!==null&&sel[0]!==sel[1]&&pickOK(0)&&pickOK(1));""")
rep("  inp.addEventListener('input',()=>{ clearTimeout(tm); const v=inp.value.trim(); if(!v) return; tm=setTimeout(async()=>{ const my=++seq;",
    "  inp.addEventListener('input',()=>{ updateFight(); clearTimeout(tm); const v=inp.value.trim(); if(!v) return; tm=setTimeout(async()=>{ const my=++seq;")
rep('<button type="submit" class="btn">挑戦する</button>', '<button type="submit" class="btn" disabled>挑戦する</button>')
rep("  inp.addEventListener('input',()=>{ clearTimeout(tm); const v=inp.value.trim(); if(!v) return; tm=setTimeout(async()=>{ const my=++sq;",
    "  const chk=()=>{ $('#chf button').disabled=!CHOPT.has(inp.value.trim()); };\n  inp.addEventListener('change',chk);\n  inp.addEventListener('input',()=>{ chk(); clearTimeout(tm); const v=inp.value.trim(); if(!v) return; tm=setTimeout(async()=>{ const my=++sq;")
rep("if(my!==sq) return; CHOPT=new Set(list);", "if(my!==sq) return; CHOPT=new Set(list); chk();")


# ---- 25. 記事名の検索を部分一致に。候補はブラウザ任せの datalist をやめ、自前の候補リストで出す ----
rep("""async function suggest(v,exclude){ const j=await fetch('https://ja.wikipedia.org/w/api.php?action=opensearch&format=json&origin=*&namespace=0&redirects=resolve&limit=20&search='+encodeURIComponent(v)).then(r=>r.json());
  const c=[...new Set(j[1]||[])]; const ok=await Promise.all(c.map(t=>inData(t))); return c.filter((t,i)=>ok[i]&&!(exclude&&exclude(t))).slice(0,10); }""",
"""// 部分一致：記事名を2文字ずつに切った索引（data/g/）から、いちばん絞り込める2文字の一覧を取り、全体を含むものだけ残す
const GIDX={};
async function gindex(k){ if(!GIDX[k]) GIDX[k]=fetch('data/g/'+k+'.json.gz?v='+VER).then(async r=>{ if(!r.ok) throw new Error(r.status);
    return JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text()); }).catch(()=>{ delete GIDX[k]; return {}; }); return GIDX[k]; }
const normQ=s=>s.normalize('NFKC').toLowerCase().replace(/[ぁ-ゖ]/g,c=>String.fromCharCode(c.charCodeAt(0)+0x60));   // ひらがなはカタカナにそろえる
async function partial(v){ const n=normQ(v); if(n.length<2) return [];
  let gs=[...new Set(Array.from({length:n.length-1},(_,i)=>n.slice(i,i+2)))];
  if(gs.length>6){ const st=(gs.length-1)/5; gs=[0,1,2,3,4,5].map(i=>gs[Math.round(i*st)]); }
  const lists=await Promise.all(gs.map(async g=>(await gindex(fnv(g)%NB))[g]||[0,[]]));
  lists.sort((a,b)=>a[0]-b[0]); if(!lists[0][0]) return [];
  return lists[0][1].filter(t=>normQ(t).includes(n)); }
// Wikipediaの前方一致（転送ページの名前にも強い）と、自前の部分一致を合わせる。完全一致→部分一致（よく読まれている順）→Wikipediaだけが拾えたもの
async function suggest(v,exclude){
  const pre=fetch('https://ja.wikipedia.org/w/api.php?action=opensearch&format=json&origin=*&namespace=0&redirects=resolve&limit=15&search='+encodeURIComponent(v)).then(r=>r.json()).then(async j=>{ const c=[...new Set(j[1]||[])]; const ok=await Promise.all(c.map(t=>inData(t))); return c.filter((t,i)=>ok[i]); }).catch(()=>[]);
  const [a,b]=await Promise.all([pre,partial(v).catch(()=>[])]); const n=normQ(v);
  const all=[...new Set([...b.filter(t=>normQ(t)===n),...a.filter(t=>normQ(t)===n),...b,...a])];   // 完全一致のあとは、よく読まれている順
  return all.filter(t=>!(exclude&&exclude(t))).slice(0,12); }
// 候補リスト：ブラウザごとの絞り込みに左右されないよう自前で出す（タップ・↑↓・Enterで選べる）
function showSugg(inp,ul,list){ ul.innerHTML=list.map((t,i)=>`<li role="option" data-i="${i}">${esc(t)}</li>`).join(''); ul.hidden=!list.length||document.activeElement!==inp; ul._list=list; ul._on=-1;
  if(inp._sg) return; inp._sg=1;
  const pick=t=>{ inp.value=t; ul.hidden=true; inp.dispatchEvent(new Event('change')); };
  ul.addEventListener('mousedown',e=>{ const li=e.target.closest('li'); if(!li) return; e.preventDefault(); pick(ul._list[+li.dataset.i]); });
  inp.addEventListener('blur',()=>setTimeout(()=>{ ul.hidden=true; },150));
  inp.addEventListener('change',()=>{ if(ul._list&&ul._list.includes(inp.value.trim())) ul.hidden=true; });
  inp.addEventListener('focus',()=>{ if(ul._list&&ul._list.length&&inp.value.trim()) ul.hidden=false; });
  inp.addEventListener('keydown',e=>{ if(ul.hidden||!ul._list||!ul._list.length) return; const L=ul.querySelectorAll('li');
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){ e.preventDefault(); ul._on=(ul._on+(e.key==='ArrowDown'?1:-1)+L.length)%L.length; L.forEach((x,i)=>x.classList.toggle('on',i===ul._on)); L[ul._on].scrollIntoView({block:'nearest'}); }
    else if(e.key==='Enter'&&ul._on>=0){ e.preventDefault(); pick(ul._list[ul._on]); }
    else if(e.key==='Escape'){ ul.hidden=true; } }); }""")
rep('<input id="in${side}" list="names${side}" placeholder="記事名を入力（例：富士山）" value="${i===null?\'\':esc(F[i][0])}" aria-label="${side===0?\'青コーナー\':\'赤コーナー\'}の記事" autocomplete="off"><datalist id="names${side}"></datalist>',
    '<span class="sgw"><input id="in${side}" placeholder="記事名の一部を入力（例：富士）" value="${i===null?\'\':esc(F[i][0])}" aria-label="${side===0?\'青コーナー\':\'赤コーナー\'}の記事" autocomplete="off"><ul class="sg" role="listbox" hidden></ul></span>')
rep('<input id="chT" list="chL" placeholder="挑戦する記事名" autocomplete="off" aria-label="挑戦する記事名"><datalist id="chL"></datalist>',
    '<span class="sgw"><input id="chT" placeholder="挑戦する記事名（一部でも可）" autocomplete="off" aria-label="挑戦する記事名"><ul class="sg" id="sgT" role="listbox" hidden></ul></span>')
rep("const inp=el.querySelector('input'), dl=el.querySelector('datalist');", "const inp=el.querySelector('input'), dl=el.querySelector('.sg');")
rep("const inp=$('#chT'), dl=$('#chL');", "const inp=$('#chT'), dl=$('#sgT');")
rep("""      dl.innerHTML=list.map(n=>`<option value="${esc(n)}"></option>`).join('');
      const note=el.querySelector('.pmsg');""", """      showSugg(inp,dl,list);
      const note=el.querySelector('.pmsg');""")
rep("""      dl.innerHTML=list.map(n=>`<option value="${esc(n)}"></option>`).join(''); }catch(_){} },250); });
  $('#chf').onsubmit""", """      showSugg(inp,dl,list); }catch(_){} },250); });
  $('#chf').onsubmit""")
rep('    <datalist id="names"></datalist>\n', '')
rep('.share2{display:flex', """.sgw{position:relative;flex:1;min-width:0;display:flex}
.sgw input{flex:1;min-width:0}
#throne .sgw{flex:1 1 200px}
.sg{position:absolute;left:0;right:0;top:100%;z-index:30;margin:2px 0 0;padding:4px 0;list-style:none;background:var(--paper);border:1px solid var(--line);border-radius:6px;box-shadow:0 6px 18px rgba(0,0,0,.15);max-height:min(60vh,360px);overflow:auto}
.sg li{padding:9px 12px;cursor:pointer;font-size:15px;line-height:1.35;overflow-wrap:anywhere}
.sg li:hover,.sg li.on{background:var(--a-soft)}
.share2{display:flex""")


# ---- 26. スマホ：候補リストがキーボードに隠れないよう、入力欄を画面上部へ寄せ、リストの高さを見えている範囲に合わせる ----
rep("function showSugg(inp,ul,list){ ul.innerHTML=", """const TOUCH=(()=>{ try{ return matchMedia('(pointer: coarse)').matches; }catch(_){ return false; } })();
function fitSugg(inp,ul){ if(ul.hidden) return; const vv=window.visualViewport; const r=inp.getBoundingClientRect();
  const bottom=vv?vv.offsetTop+vv.height:innerHeight; ul.style.maxHeight=Math.max(140,Math.floor(bottom-r.bottom-16))+'px'; }
function liftInput(inp){ if(!TOUCH) return; setTimeout(()=>{ const r=inp.getBoundingClientRect(); const top=window.visualViewport?window.visualViewport.offsetTop:0; if(r.top-top>70) window.scrollBy({top:r.top-top-12,behavior:'smooth'}); },350); }
if(typeof window!=='undefined'&&window.visualViewport){ const re=()=>document.querySelectorAll('.sg').forEach(ul=>{ const i=ul.parentNode.querySelector('input'); if(i) fitSugg(i,ul); }); visualViewport.addEventListener('resize',re); visualViewport.addEventListener('scroll',re); }
function showSugg(inp,ul,list){ ul.innerHTML=""")
rep("ul.hidden=!list.length||document.activeElement!==inp; ul._list=list; ul._on=-1;", "ul.hidden=!list.length||document.activeElement!==inp; ul._list=list; ul._on=-1; fitSugg(inp,ul);")
rep("  inp.addEventListener('focus',()=>{ if(ul._list&&ul._list.length&&inp.value.trim()) ul.hidden=false; });",
    "  inp.addEventListener('focus',()=>{ if(ul._list&&ul._list.length&&inp.value.trim()){ ul.hidden=false; fitSugg(inp,ul); } });")


rep("const inp=el.querySelector('input'), dl=el.querySelector('.sg');", "const inp=el.querySelector('input'), dl=el.querySelector('.sg'); inp.addEventListener('focus',()=>liftInput(inp));")
rep("const inp=$('#chT'), dl=$('#sgT');", "const inp=$('#chT'), dl=$('#sgT'); inp.addEventListener('focus',()=>liftInput(inp));")


# ---- 27. 王座戦：挑む相手（王者）を送って取り違えを防ぐ／王座戦欄を30秒ごと・タブに戻ったときに更新（入力中の内容は残す） ----
rep("body:JSON.stringify({title:t,name})", "body:JSON.stringify({title:t,name,reign:THRONE&&THRONE.champ?THRONE.champ.id:0})")
rep("  if(d.error){ m.className='msg err'; m.textContent=d.error; return; }",
    "  if(d.error&&d.changed){ await loadThrone(null,true); const m2=$('#chM'); m2.className='msg err'; m2.textContent=d.error; return; }\n  if(d.error){ m.className='msg err'; m.textContent=d.error; return; }")
rep("async function loadThrone(msg){ if(!API) return; try{ const d=await fetch(API+'/api/throne').then(r=>r.json()); if(d&&d.champ){ renderThrone(d,msg); fixChamp(); } }catch(_){} }",
"""// keep=true なら、入力中の記事名・名前・カーソル位置を残したまま描き直す
function renderKeep(d,msg){ const t=$('#chT'), n=$('#chN'); const prev={t:t?t.value:'',n:n?n.value:'',f:document.activeElement&&document.activeElement.id};
  renderThrone(d,msg); const t2=$('#chT'), n2=$('#chN'); if(t2){ t2.value=prev.t; t2.dispatchEvent(new Event('change')); } if(n2&&prev.n) n2.value=prev.n;
  if(prev.f==='chT'&&t2) t2.focus({preventScroll:true}); else if(prev.f==='chN'&&n2) n2.focus({preventScroll:true}); }
async function loadThrone(msg,keep){ if(!API) return; try{ const d=await fetch(API+'/api/throne').then(r=>r.json()); if(d&&d.champ){ keep?renderKeep(d,msg):renderThrone(d,msg); fixChamp(); } }catch(_){} }
// 王者が変わっていたら、王座戦欄を新しくする（30秒ごと・タブに戻ったとき）
async function refreshThrone(){ if(!API||document.hidden||!THRONE) return; try{ const d=await fetch(API+'/api/throne').then(r=>r.json()); if(!d||!d.champ) return;
  const o=THRONE.champ; if(d.champ.id===o.id&&d.champ.defenses===o.defenses) return;
  const busy=$('#chf button')&&$('#chf button').disabled&&$('#chM')&&/挑戦しています/.test($('#chM').textContent); if(busy) return;
  renderKeep(d,d.champ.id!==o.id?'王者が「'+esc(d.champ.display)+'」に変わりました':($('#chM')?$('#chM').innerHTML:'')); fixChamp(); }catch(_){} }
setInterval(refreshThrone,30000); document.addEventListener('visibilitychange',()=>{ if(!document.hidden) refreshThrone(); });""")


# ---- 28. 結果の札に、戦った2記事のWikipediaへのリンクを置く（王座戦・自由対戦の共通） ----
rep('    <div class="share"><output id="share">', """    <div class="reads"><span>記事を読む</span>${[ai,bi].map(i=>`<a href="https://ja.wikipedia.org/wiki/${encodeURIComponent(F[i][1])}" target="_blank" rel="noopener">${esc(F[i][0])} ↗</a>`).join('')}</div>
    <div class="share"><output id="share">""")
rep('.share2{display:flex', """.reads{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;font-size:13px}
.reads span{opacity:.75;margin-right:2px}
.reads a{color:inherit;border:1px solid currentColor;border-radius:999px;padding:4px 12px;text-decoration:none;font-weight:700;overflow-wrap:anywhere}
.reads a:hover{background:rgba(255,255,255,.12)}
.share2{display:flex""")


# ---- 29. アクセス解析（Cloudflare Web Analytics：Cookieを使わない） ----
rep('</body>', '<!-- Cloudflare Web Analytics --><script type=\'module\' src=\'https://static.cloudflareinsights.com/beacon.min.js\' data-cf-beacon=\'{"token": "92aaad9660e1433f8d518c17a8ac2512"}\'></script><!-- End Cloudflare Web Analytics -->\n</body>')


# ---- 30. 試合の終わりを分かりやすく：比べ合いは取った本数を●で表示／決着したら得点板に「決着」と勝者を出す ----
rep('<span class="hpbar"><i id="hpA" style="width:100%"></i></span><span class="hpn" id="hpnA">${r.max[0]} / ${r.max[0]}</span>',
    '${an.type===\'kurabe\'?`<span class="pips" id="pipA">${\'<i></i>\'.repeat(r.tick)}</span><span class="hpn" id="hpnA">0本</span>`:`<span class="hpbar"><i id="hpA" style="width:100%"></i></span><span class="hpn" id="hpnA">${r.max[0]} / ${r.max[0]}</span>`}')
rep('<span class="hpbar"><i id="hpB" style="width:100%"></i></span><span class="hpn" id="hpnB">${r.max[1]} / ${r.max[1]}</span>',
    '${an.type===\'kurabe\'?`<span class="pips" id="pipB">${\'<i></i>\'.repeat(r.tick)}</span><span class="hpn" id="hpnB">0本</span>`:`<span class="hpbar"><i id="hpB" style="width:100%"></i></span><span class="hpn" id="hpnB">${r.max[1]} / ${r.max[1]}</span>`}')
rep("  const setHP=idx=>{ const l=r.log[idx]; if(!l) return; $('#hpA').style.width=",
    """  const setHP=idx=>{ const l=r.log[idx]; if(!l) return;
    if(an.type==='kurabe'){ const w=[0,0]; for(let k=0;k<=idx;k++){ const x=r.log[k]; if(x&&x.side>=0&&!x.kai) w[x.side]++; }
      ['A','B'].forEach((s,j)=>{ const ps=$('#pip'+s).children; for(let k=0;k<ps.length;k++) ps[k].classList.toggle('on',k<w[j]); $('#hpn'+s).textContent=w[j]+'本'; }); $('#tk').textContent=l.t; return; }
    $('#hpA').style.width=""")
rep("${an.type==='kurabe'?'（バーは取られた本数）':''}", "${an.type==='kurabe'?'（●は取った本数）':''}")
rep("function showResult(){\n  if(!current||current.shown) return; current.shown=true;",
    """function showResult(){
  if(!current||current.shown) return; current.shown=true;
  { const sb=$('#sb'), ww=current.an.r.w; if(sb){ sb.classList.add('done'); const tk=$('#tk'); if(tk) tk.textContent=ww===null?'引分':'決着';
      const A=sb.querySelector('.sb.A'), B=sb.querySelector('.sb.B'); if(ww!==null){ (ww===current.ai?A:B).classList.add('won'); (ww===current.ai?B:A).classList.add('lost'); } } }""")
rep('.tick{font-family:var(--f-display);font-size:13px;color:var(--muted);text-align:center}',
    """.tick{font-family:var(--f-display);font-size:13px;color:var(--muted);text-align:center}
.pips{display:flex;gap:4px;height:12px;align-items:center}
.sb.B .pips{justify-content:flex-end}
.pips i{width:12px;height:12px;border-radius:50%;border:2px solid var(--line);box-sizing:border-box}
.sb.A .pips i.on{background:var(--a);border-color:var(--a)}
.sb.B .pips i.on{background:var(--b);border-color:var(--b)}
.scoreboard.done .tick{background:var(--hl);color:var(--hl-ink);border-radius:4px;padding:2px 8px;font-size:15px;animation:pop .35s ease-out}
.sb.won .nm::after{content:" 勝ち";color:var(--hl-ink);background:var(--hl);border-radius:3px;padding:0 4px;margin-left:4px;font-size:11px;vertical-align:1px}
.sb.B.won .nm::after{content:"";padding:0;margin:0}
.sb.B.won .nm::before{content:"勝ち ";color:var(--hl-ink);background:var(--hl);border-radius:3px;padding:0 4px;margin-right:4px;font-size:11px;vertical-align:1px}
.sb.lost{opacity:.45}
@keyframes pop{0%{transform:scale(.6)}70%{transform:scale(1.15)}100%{transform:scale(1)}}
@media (prefers-reduced-motion:reduce){.scoreboard.done .tick{animation:none}}""")


# ---- 31. 王座戦の一覧（最近の挑戦・最長防衛・歴代王者）から、その試合を再生できるように ----
rep("<details><summary>最近の挑戦</summary><ol>${d.recent.map(x=>`<li>${esc(x.display)} <span class=\"who\">",
    "<details><summary>最近の挑戦</summary><ol>${d.recent.map(x=>`<li><a class=\"rp\" href=\"?c=${x.id}\" data-c=\"${x.id}\">${esc(x.display)}${x.cdisplay?' 対 '+esc(x.cdisplay):''}</a> <span class=\"who\">")
rep("<details><summary>最長防衛ランキング</summary><ol>${d.best.map(x=>`<li><b>${esc(x.display)}</b>",
    "<details><summary>最長防衛ランキング</summary><ol>${d.best.map(x=>`<li>${x.cid?`<a class=\"rp\" href=\"?c=${x.cid}\" data-c=\"${x.cid}\"><b>${esc(x.display)}</b></a>`:`<b>${esc(x.display)}</b>`}")
rep("<details><summary>歴代王者</summary><ol reversed>${d.history.map(x=>`<li><b>${esc(x.display)}</b> 防衛${x.defenses}回 <span class=\"who\">（${esc(x.holder)}・${esc(dt(x.started_at))}〜${x.ended_by?'、'+esc(x.ended_by)+'に敗れる':'在位中'}）</span></li>`).join('')}",
    "<details><summary>歴代王者</summary><ol reversed>${d.history.map(x=>`<li>${x.cid?`<a class=\"rp\" href=\"?c=${x.cid}\" data-c=\"${x.cid}\"><b>${esc(x.display)}</b></a>`:`<b>${esc(x.display)}</b>`} 防衛${x.defenses}回 <span class=\"who\">（${esc(x.holder)}・${esc(dt(x.started_at))}〜${x.ended_by?'、'+(x.lostcid?`<a class=\"rp\" href=\"?c=${x.lostcid}\" data-c=\"${x.lostcid}\">${esc(x.ended_by)}に敗れる</a>`:esc(x.ended_by)+'に敗れる'):'在位中'}）</span></li>`).join('')}")
rep("  $('#chf').onsubmit=e=>{ e.preventDefault(); doChallenge(); }; }",
    "  $('#chf').onsubmit=e=>{ e.preventDefault(); doChallenge(); };\n  el.querySelectorAll('[data-c]').forEach(a=>a.onclick=e=>{ e.preventDefault(); replayChallenge(+a.dataset.c); }); }\n// 記録された挑戦を、その場で再生する\nasync function replayChallenge(id){ try{ const x=await fetch(API+'/api/challenge/'+id).then(r=>r.json()); if(x.error) return;\n  const a=await loadTitle(x.challenger.title), b=await loadTitle(x.champ.title); if(a<0||b<0) return; MODE={res:x,no:x.reignNo,replay:true}; startBattle([a,b]); }catch(_){} }")
rep('#throne .r-win{color:var(--ok);font-weight:700}', '#throne .r-win{color:var(--ok);font-weight:700}\n#throne a.rp{color:inherit;text-decoration:underline;text-decoration-color:var(--muted);text-underline-offset:3px}')


# ---- 32. 王座戦の挑戦回数を「ブラウザごと」に数えるため、端末に乱数の番号を持たせて一緒に送る ----
rep("body:JSON.stringify({title:t,name,reign:THRONE&&THRONE.champ?THRONE.champ.id:0})",
    "body:JSON.stringify({title:t,name,reign:THRONE&&THRONE.champ?THRONE.champ.id:0,client:clientId()})")
rep("let THRONE=null, CHOPT=new Set();", """let THRONE=null, CHOPT=new Set();
// ブラウザごとの番号（個人を表すものではない乱数。挑戦回数の上限を、同じ回線の他人と分けて数えるためだけに使う）
function clientId(){ try{ let c=localStorage.getItem('hk-cid'); if(!/^[a-z0-9]{16,40}$/.test(c||'')){ const a=new Uint8Array(12); crypto.getRandomValues(a); c=[...a].map(x=>x.toString(16).padStart(2,'0')).join(''); localStorage.setItem('hk-cid',c); } return c; }catch(_){ return ''; } }""")


# ---- 33. 試合の型（比べ合いなど）も左右の並び順に左右されないように：常にQIDの小さい側を左として計算し、表示側に合わせて反転する ----
rep("function analyze(ai,bi){", """function analyze(ai,bi){ if(lt(ai,bi)) return analyze0(ai,bi);
  const an=analyze0(bi,ai), r=an.r;   // 並びを入れ替えて計算した結果を、左右反転して返す（勝者・決め手は記事の番号なので、そのまま）
  return {...an, r:{...r, log:r.log.map(l=>({...l,side:l.side<0?-1:1-l.side,hp:l.hp?[l.hp[1],l.hp[0]]:l.hp})), hp:[r.hp[1],r.hp[0]], max:[r.max[1],r.max[0]]}}; }
function analyze0(ai,bi){""")


# 過去の記録を再生して、いまの計算と勝者が違うときは、そのことを書き添える（計算の修正前の記録）
rep('    <div class="reads"><span>記事を読む</span>', """    ${(()=>{ if(!M||!M.replay) return ''; const x=M.res; const recW=x.result==='win'||x.result==='late'?x.challenger.title:x.result==='lose'?x.champ.title:null; const calcW=w===null?null:F[w][1];
      return recW===calcW?'':`<div class="sub">※この挑戦は、判定の計算を直す前に記録されたものです。記録上は「${esc(recW?(recW===x.challenger.title?x.challenger.display:x.champ.display):'引き分け')}」の勝ちとして扱われていますが、いまの計算で再生すると結果が異なります。</div>`; })()}
    <div class="reads"><span>記事を読む</span>""")

# ---- 34. 過去の王座戦を再生したときは「記録」だと分かるようにし、ボタンはいまの王者への挑戦にする ----
rep("x.champ.defenses}度目の防衛`; }", "x.champ.defenses}度目の防衛`; if(M.replay) title='【記録】'+title; }")
rep("""<button type="button" class="btn big" id="thr">${M.res.result==='win'?'新王者に挑む':'別の記事で挑む'}</button>""",
    """${M.replay?`<div class="sub" style="flex-basis:100%">${esc(dt(M.res.at))}の試合の再生です。${THRONE&&THRONE.champ?'いまの王者は'+esc(THRONE.champ.display)+'。':''}</div>`:''}
      <button type="button" class="btn big" id="thr">${M.replay?'いまの王者に挑む':M.res.result==='win'?'新王者に挑む':'別の記事で挑む'}</button>""")

# ---- 35. みんなの対戦数：自由対戦の数をブラウザでまとめて数え、ときどきサーバーに送る。フッタに全体の数を出す ----
rep("rec.battles++; if(upset) rec.upsets++;", "rec.battles++; if(upset) rec.upsets++; if(!current.mode) addPlay();")
rep("const d=await fetch(API+'/api/throne').then(r=>r.json()); if(d&&d.champ){ keep?", "const d=await fetch(API+'/api/throne').then(r=>r.json()); setAll(d); if(d&&d.champ){ keep?")
rep("const d=await fetch(API+'/api/throne').then(r=>r.json()); if(!d||!d.champ)", "const d=await fetch(API+'/api/throne').then(r=>r.json()); setAll(d); if(!d||!d.champ)")
rep("let THRONE=null, CHOPT=new Set();", """let THRONE=null, CHOPT=new Set();
// みんなの対戦数。自由対戦は1戦ごとに送らず、この端末で数えておいて、数分おきとページを離れるときにまとめて送る
var ALL=null; const PEND_KEY='hk-plays';
function pend(){ try{ return Math.max(0,parseInt(localStorage.getItem(PEND_KEY)||'0',10)||0); }catch(_){ return 0; } }
function setPend(n){ try{ localStorage.setItem(PEND_KEY,String(Math.max(0,n))); }catch(_){} }
function addPlay(){ setPend(pend()+1); if(ALL){ ALL.plays++; renderRec(); } }
function setAll(d){ if(d&&d.count){ ALL={plays:d.count.plays+pend(),throne:d.count.throne}; renderRec(); } }
function flushPlays(beacon){ const n=Math.min(30,pend()); if(!n||!API) return; const body=JSON.stringify({n,client:clientId()}); let ok=false;
  try{ if(beacon&&navigator.sendBeacon) ok=navigator.sendBeacon(API+'/api/plays',new Blob([body],{type:'text/plain'}));
    else { fetch(API+'/api/plays',{method:'POST',headers:{'Content-Type':'text/plain'},body,keepalive:true}).catch(()=>{}); ok=true; } }catch(_){}
  if(ok) setPend(pend()-n); }
setInterval(()=>flushPlays(false),120000);
addEventListener('visibilitychange',()=>{ if(document.visibilityState==='hidden') flushPlays(true); });
addEventListener('pagehide',()=>flushPlays(true));""")
rep("function renderRec(){ $('#record').innerHTML=`<span><b>${rec.battles}</b>戦観戦</span>",
    "function renderRec(){ const A=(typeof ALL!=='undefined'&&ALL)?`<div class=\"all\">みんなで <b>${(ALL.plays+ALL.throne).toLocaleString()}</b>試合 <span>（うち王座戦 ${ALL.throne.toLocaleString()}）</span></div>`:'';\n  $('#record').innerHTML=A+`<div class=\"mine\"><span class=\"you\">あなた</span><span><b>${rec.battles}</b>戦観戦</span>")
rep("<span>勝ち抜き最高 <b>${rec.best}</b>連勝</span>`; }", "<span>勝ち抜き最高 <b>${rec.best}</b>連勝</span></div>`; }")
rep(".record{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;color:var(--muted)}",
    ".record{display:flex;flex-direction:column;gap:6px;font-size:13px;color:var(--muted)}\n.record .mine{display:flex;gap:18px;flex-wrap:wrap;align-items:baseline}\n.record .all{font-size:14px;color:var(--ink)}\n.record .all b{font-size:24px}\n.record .you{font-size:12px;border:1px solid var(--line);border-radius:999px;padding:0 8px}")

# ---- 36. 共有文に「架空の試合」の断り書きを付ける（実在の国・団体・人物どうしの試合が、切り取られたり自動翻訳されたりしても誤解されないように） ----
rep("  const SHAREURL=battleURL();", """  share=fitPost(share)+'\\n'+DISC;
  const SHAREURL=battleURL();""")
rep("let THRONE=null, CHOPT=new Set();", """let THRONE=null, CHOPT=new Set();
const DISC='※Wikipediaの記述をもとにした架空の試合です。実在の国・団体・人物の優劣を示すものではありません';
// Xの文字数（日本語などは2、英数字は1。URLは23として数える）に収まるよう、本文を切り詰める
const xlen=s=>[...s].reduce((n,c)=>n+(c.codePointAt(0)<0x1100?1:2),0);
function fitPost(s){ const room=280-24-xlen(DISC)-1; if(xlen(s)<=room) return s; let o=''; for(const c of s){ if(xlen(o+c)>room-2) break; o+=c; } return o+'…'; }""")

# ---- 37. 「試合の型」は特別な型（比べ合い・瞬殺・泥仕合・因縁の対決）のときだけ出す ----
rep("""<div class="mtype">試合の型：<b>${esc(an.tlabel||'')}</b>${an.type==='kurabe'?'（●は取った本数）':''}</div>""",
    """${an.type&&an.type!=='normal'?`<div class="mtype">試合の型：<b>${esc(an.tlabel||'')}</b>${an.type==='kurabe'?'（●は取った本数）':''}</div>`:''}""")

# ---- 38. 王座戦で挑んだあと、試合の始まりまで確実にスクロールする（iPhone対策） ----
#  ・キーボードを先に閉じる ・王座戦欄の描き直しを試合の前に済ませる ・キーボードが閉じてからスクロール
#  ・スクロールが途中で止まったら位置を直す（自分で触ったときは直さない）
#  ・王座戦欄を描き直して高さが変わったら、そのぶん見ている位置を戻す（Safariは自動でやってくれない）
rep("""  try{ const a=await loadTitle(d.challenger.title), b=await loadTitle(d.champ.title); if(a>=0&&b>=0){ MODE={res:d,no:d.reignNo||(THRONE?THRONE.reignNo:1)}; startBattle([a,b]); } }catch(_){}
  await loadThrone(msg); }""", """  try{ const ae=document.activeElement; if(ae&&ae.blur) ae.blur(); }catch(_){}
  await loadThrone(msg);
  try{ const a=await loadTitle(d.challenger.title), b=await loadTitle(d.champ.title); if(a>=0&&b>=0){ MODE={res:d,no:d.reignNo||(THRONE?THRONE.reignNo:1)}; await kbClosed(); startBattle([a,b]); } }catch(_){} }
// スマホのキーボードが閉じきるのを待つ（最大0.7秒）
function kbClosed(){ const vv=window.visualViewport; if(!TOUCH||!vv) return Promise.resolve();
  return new Promise(res=>{ const t0=Date.now(); const ck=()=>{ if(vv.height>innerHeight-80||Date.now()-t0>700) res(); else setTimeout(ck,60); }; ck(); }); }
// なめらかなスクロールが途中で止まったときに、位置を直す
function settleTo(el){ let touched=false; const mark=()=>{ touched=true; }; ['touchstart','wheel','keydown'].forEach(e=>addEventListener(e,mark,{once:true,passive:true}));
  setTimeout(()=>{ ['touchstart','wheel','keydown'].forEach(e=>removeEventListener(e,mark)); if(touched||!el.isConnected||el.hidden) return;
    const want=parseFloat(getComputedStyle(el).scrollMarginTop)||0; if(Math.abs(el.getBoundingClientRect().top-want)>40) el.scrollIntoView({block:'start'}); },1000); }""")
rep("  ring.scrollIntoView({behavior:'smooth',block:'start'});", "  ring.scrollIntoView({behavior:'smooth',block:'start'}); settleTo(ring);")
rep("async function loadThrone(msg,keep){", """{ const base=renderThrone; renderThrone=function(d,msg){ const el=$('#throne'), ring=$('#ring');
    const below=ring&&!ring.hidden&&(el.compareDocumentPosition(ring)&Node.DOCUMENT_POSITION_FOLLOWING); const r0=below?ring.getBoundingClientRect().top:null;
    base(d,msg);
    if(r0!==null&&r0<innerHeight&&r0>-ring.offsetHeight){ const dy=ring.getBoundingClientRect().top-r0; if(Math.abs(dy)>1) scrollBy(0,dy); } }; }
async function loadThrone(msg,keep){""")

# ---- 39. 決め手・惜しかった・自滅・因縁は「外すと勝者が変わる」ものだけにする（勝ち方だけが変わるものは数えない。勝者に「自滅」が付く誤りの修正） ----
rep("const byWho=i=>dec.filter(d=>d.who===i&&d.who!==d.alt);", "const decW=dec.filter(d=>d.alt!==w);   // 外すと勝者が変わるものだけ\n  const byWho=i=>decW.filter(d=>d.who===i&&d.who!==d.alt);")
rep("const k=dec.filter(d=>d.who===i&&d.who===d.alt);", "const k=decW.filter(d=>d.who===i&&d.who===d.alt);")
rep("if(dec.some(d=>d.who===-1)) lines.push(", "if(decW.some(d=>d.who===-1)) lines.push(")
rep("const key=dec.find(d=>d.who===w);", "const key=decW.find(d=>d.who===w);")

# ---- 40. 仲間図鑑：記事の「召喚」のつながり（所属先・生みの親・名前の由来・シリーズ・戦争の両陣営）を逆にたどった「一門」を見せ、そこから選んで戦わせる ----
rep("""  <details class="mvs"${WIDE()?' open':''}>""", """  <div class="fams" data-fi="${i}"></div>
  <details class="mvs"${WIDE()?' open':''}>""")
rep("const inp=el.querySelector('input'), dl=el.querySelector('.sg'); inp.addEventListener('focus',()=>liftInput(inp));",
    "famFill(el); const inp=el.querySelector('input'), dl=el.querySelector('.sg'); inp.addEventListener('focus',()=>liftInput(inp));")
rep("EXCL=new Set(ex); setCount();", "EXCL=new Set(ex); setCount(); famToday();")
rep('<div class="record card" style="padding:10px 14px" id="record"></div>', '<section id="zukan" class="card" hidden></section>\n  <div class="record card" style="padding:10px 14px" id="record"></div>\n  <dialog id="famdlg" aria-label="仲間図鑑"></dialog>')
rep("let THRONE=null, CHOPT=new Set();", """let THRONE=null, CHOPT=new Set();
/* ---------- 仲間図鑑 ---------- */
const FAMK={p:n=>n+'の一門',c:n=>n+'が生んだもの',o:n=>n+'から名前をもらったもの',s:n=>/シリーズ$/.test(n)?n:n+'シリーズ',w:n=>n+'が戦った戦い'};
const FKIND={'親分召喚':'p','生みの親召喚':'c','本家召喚':'o','シリーズ召喚':'s','両陣営召喚':'w'};
let FAMNB=512, FEAT=[]; const FAMB={};
function famShard(key){ const k=fnv(key)%FAMNB; if(!FAMB[k]) FAMB[k]=fetch('data/fam/'+k+'.json.gz?v='+VER).then(async r=>{ if(!r.ok) throw 0; return JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text()); }).catch(()=>{ delete FAMB[k]; return {}; }); return FAMB[k]; }
async function famGet(key){ return (await famShard(key))[key]||null; }
function famKeys(i){ const out=[]; for(const m of F[i][7]||[]){ if(m[0]==='SUMMON'&&FKIND[m[1]]&&Array.isArray(m[7])) for(const t of m[7]) if(t[2]) out.push(FKIND[m[1]]+t[2]); } return [...new Set(out)]; }
const famChip=(g,big)=>`<button type="button" class="famchip${big?' big':''}" data-fam="${g.k}${esc(g.q)}">${esc(FAMK[g.k](g.n))}<b>${g.c}</b></button>`;
async function famFill(el){ const box=el.querySelector('.fams'); if(!box) return; const i=+box.dataset.fi; const keys=famKeys(i); if(!keys.length) return;
  const gs=(await Promise.all(keys.map(famGet))).filter(g=>g&&g.c>=2); if(!gs.length||!box.isConnected) return;
  box.innerHTML='<span class="fl">仲間</span>'+gs.map(g=>famChip(g)).join('');
  box.querySelectorAll('[data-fam]').forEach(b=>b.onclick=()=>openFam(b.dataset.fam,F[i][1])); }
const jpv=v=>v>=1e8?(Math.round(v/1e7)/10)+'億':v>=1e4?(Math.round(v/1e3)/10)+'万':v.toLocaleString('ja-JP');
async function openFam(key,cur){ const g=await famGet(key); const dlg=$('#famdlg'); if(!g||!dlg) return;
  dlg.innerHTML=`<div class="fhead"><div><div class="fk">仲間図鑑</div><h3>${esc(FAMK[g.k](g.n))}</h3>${g.d?`<div class="fd">${esc(g.n)}：${esc(g.d)}</div>`:''}<div class="fc">${g.c}記事${g.c>g.m.length?`（よく読まれている${g.m.length}件を表示）`:'（よく読まれている順）'}</div>
  <div class="fsh"><a class="btn small" id="famtw" target="_blank" rel="noopener" href="https://x.com/intent/tweet?text=${encodeURIComponent(famText(g))}&url=${encodeURIComponent(famURL(key))}">Xに投稿</a>${navigator.share?'<button type="button" class="btn small" id="famshare">共有</button>':'<button type="button" class="btn small" id="famcopy">URLをコピー</button>'}</div></div><button type="button" class="btn small" id="famx" autofocus>閉じる</button></div>
  <ol class="flist">${g.m.map(m=>`<li${m[0]===cur?' class="cur"':''}><div class="fn"><a href="https://ja.wikipedia.org/wiki/${encodeURIComponent(m[0])}" target="_blank" rel="noopener">${esc(m[1])}</a>${m[2]?`<span class="fpv">年${jpv(m[2])}回</span>`:''}</div><div class="fb">${m[0]===champTitle()?'<span class="fch">王者（自由対戦には出せません）</span>':`<button type="button" class="btn small fa" data-t="${esc(m[0])}" data-n="${esc(m[1])}" data-s="0" aria-pressed="false">青へ</button><button type="button" class="btn small fbb" data-t="${esc(m[0])}" data-n="${esc(m[1])}" data-s="1" aria-pressed="false">赤へ</button>`}</div></li>`).join('')}</ol>
  <div class="fnote">Wikipedia（Wikidata）に書かれたつながりから見つけた仲間です。すべてを網羅しているわけではありません。</div>
  <div class="ffoot"><div class="fpair"><span class="pa"></span><span class="pv">vs</span><span class="pb"></span></div><div class="fgo"><button type="button" class="btn" id="famset">選んで閉じる</button><button type="button" class="btn big" id="famgo">この2つで対戦</button></div></div>`;
  // 選んでいる途中の組み合わせ（はじめは、いま自由対戦に入っている2記事）
  FP=[0,1].map(s=>sel[s]!==null&&sel[s]>=0&&!isChamp(sel[s])?{t:F[sel[s]][1],n:F[sel[s]][0]}:null);
  $('#famx').onclick=()=>dlg.close();
  if($('#famshare')) $('#famshare').onclick=()=>{ navigator.share({title:'百科拳典 仲間図鑑',text:famText(g),url:famURL(key)}).catch(()=>{}); };
  if($('#famcopy')) $('#famcopy').onclick=async e=>{ try{ await navigator.clipboard.writeText(famURL(key)); e.target.textContent='コピーしました'; }catch(_){ e.target.textContent=famURL(key); } };
  dlg.querySelectorAll('[data-t]').forEach(b=>b.onclick=()=>{ const s=+b.dataset.s, x={t:b.dataset.t,n:b.dataset.n};
    if(FP[1-s]&&FP[1-s].t===x.t) FP[1-s]=FP[s];   // 反対側に入っている記事なら、入れ替える
    FP[s]=x; famMark(); });
  $('#famset').onclick=()=>famApply(false); $('#famgo').onclick=()=>famApply(true);
  famMark(); if(!dlg.open) dlg.showModal(); dlg.scrollTop=0; }
let FP=[null,null];
const famURL=key=>location.origin+'/?fam='+encodeURIComponent(key);
function famText(g){ const top=g.m.slice(0,3).map(m=>m[1]); return `【百科拳典 仲間図鑑】${FAMK[g.k](g.n)}は${g.c}記事。${top.join('、')}${g.c>top.length?'…':''}\nWikipediaのつながりから見つけた仲間たち`; }
function famMark(){ const dlg=$('#famdlg'); if(!dlg) return;
  dlg.querySelectorAll('.flist li').forEach(li=>{ const b=li.querySelectorAll('[data-t]'); const t=b[0]?b[0].dataset.t:null;
    const a=!!(t&&FP[0]&&FP[0].t===t), r=!!(t&&FP[1]&&FP[1].t===t); li.classList.toggle('sa',a); li.classList.toggle('sb',r);
    b.forEach(x=>{ const on=+x.dataset.s===0?a:r; x.classList.toggle('on',on); x.setAttribute('aria-pressed',on); x.textContent=(+x.dataset.s===0?'青':'赤')+(on?'に決定':'へ'); }); });
  dlg.querySelector('.ffoot .pa').textContent='青：'+(FP[0]?FP[0].n:'未選択'); dlg.querySelector('.ffoot .pb').textContent='赤：'+(FP[1]?FP[1].n:'未選択');
  $('#famgo').disabled=!(FP[0]&&FP[1]); }
async function famApply(go){ const dlg=$('#famdlg');
  for(const s of [0,1]) if(FP[s]){ const i=await loadTitle(FP[s].t); if(i>=0) sel[s]=i; }
  if(dlg.open) dlg.close(); renderPick(0); renderPick(1); updateFight(); await fixChamp();
  if(go&&sel[0]!==null&&sel[1]!==null) startBattle(); else $('#setup').scrollIntoView({behavior:'smooth',block:'start'}); }
async function famToday(){ try{ const d=await fetch('data/fam/featured.json?v='+VER).then(r=>r.json()); FAMNB=d.nb||512; FEAT=d.featured||[]; }catch(_){ return; }
  const z=$('#zukan'); if(z&&FEAT.length){ const day=Math.floor((Date.now()+9*3600e3)/86400e3); const pickF=n=>FEAT[(n%FEAT.length+FEAT.length)%FEAT.length];
    let k=hash('fam'+day); const draw=()=>{ const f=pickF(k); z.querySelector('.today').innerHTML=famChip({k:f[0][0],q:f[0].slice(1),n:f[1],c:f[2]},true); z.querySelector('[data-fam]').onclick=()=>openFam(f[0]); };
    z.innerHTML=`<div class="sechead"><h2>仲間図鑑</h2><span>Wikipediaのつながりから、埋もれた仲間を探す。記事カードの「仲間」からも開けます</span></div><div class="trow"><span class="tl">今日の一門</span><span class="today"></span><button type="button" class="btn small" id="famrnd">ほかの一門</button></div>`;
    z.hidden=false; draw(); $('#famrnd').onclick=()=>{ k=Math.floor(Math.random()*1e9); draw(); }; }
  const dlg=$('#famdlg'); if(dlg) dlg.addEventListener('click',e=>{ if(e.target===dlg) dlg.close(); });
  const q=new URLSearchParams(location.search).get('fam'); if(q&&/^[pcosw]Q\\d+$/.test(q)) openFam(q); }""")
rep(".mtype{", """.fams{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.fams .fl{font-size:11px;color:var(--muted);margin-right:2px}
.famchip{font:inherit;font-size:12px;line-height:1.4;padding:3px 10px;border-radius:999px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer;text-align:left}
.famchip:hover{border-color:var(--ink)}
.famchip b{margin-left:6px;font-family:var(--f-display);font-weight:400;color:var(--muted)}
.famchip.big{font-size:15px;font-weight:700;padding:6px 14px;border-color:var(--ink)}
#zukan{padding:16px;display:flex;flex-direction:column;gap:12px}
#zukan .trow{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
#zukan .tl{font-size:12px;color:var(--muted)}
#famdlg{border:none;border-radius:14px;padding:0;width:min(600px,94vw);max-height:84vh;overflow:auto;background:var(--paper);color:var(--ink);box-shadow:0 20px 60px rgba(0,0,0,.35)}
#famdlg::backdrop{background:rgba(10,14,24,.5)}
@media (max-width:640px){#famdlg{width:100vw;max-width:100vw;margin:auto 0 0;border-radius:16px 16px 0 0;max-height:88vh}}
.fhead{position:sticky;top:0;z-index:1;background:var(--paper);display:flex;justify-content:space-between;align-items:flex-start;gap:10px;padding:14px 16px 10px;border-bottom:1px solid var(--line)}
.fhead h3{margin:2px 0 4px;font-family:var(--f-display);font-weight:400;font-size:20px;line-height:1.3;overflow-wrap:anywhere}
.fk{font-size:11px;letter-spacing:.12em;color:var(--muted)} .fd,.fc{font-size:12px;color:var(--muted)}
.flist{list-style:none;margin:0;padding:4px 16px 8px}
.flist li{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding:10px 0;border-bottom:1px solid var(--line);align-items:center}
.flist li.cur{background:color-mix(in srgb,var(--hl) 25%,transparent);margin:0 -16px;padding:10px 16px}
.fn{font-weight:700;overflow-wrap:anywhere} .fn a{color:inherit;text-decoration-color:var(--line);text-underline-offset:3px}
.fpv{font-size:11px;color:var(--muted);margin-left:8px;font-weight:400;white-space:nowrap}
.fb{grid-column:2;display:flex;gap:6px}
.fb .fa{border-color:var(--a);color:var(--a)} .fb .fbb{border-color:var(--b);color:var(--b)}
.fnote{font-size:11px;color:var(--muted);padding:4px 16px 18px}
.fsh{display:flex;gap:6px;margin-top:8px}
.flist li.sa{box-shadow:inset 4px 0 0 var(--a);background:var(--a-soft);margin:0 -16px;padding:10px 16px}
.flist li.sb{box-shadow:inset 4px 0 0 var(--b);background:var(--b-soft);margin:0 -16px;padding:10px 16px}
.fb .fa.on{background:var(--a);color:#fff} .fb .fbb.on{background:var(--b);color:#fff}
.fch{font-size:11px;color:var(--muted)}
.ffoot{position:sticky;bottom:0;background:var(--paper);border-top:1px solid var(--line);padding:10px 16px calc(12px + env(safe-area-inset-bottom));display:flex;flex-direction:column;gap:8px;box-shadow:0 -6px 16px rgba(0,0,0,.08)}
.fpair{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px;font-weight:700;font-size:14px}
.fpair .pa{color:var(--a)} .fpair .pb{color:var(--b)} .fpair .pv{font-family:var(--f-display);font-weight:400;color:var(--muted);font-size:12px}
.fgo{display:flex;gap:8px;justify-content:flex-end}
.mtype{""")

# ---- 41. ランダム（初期表示・ランダムボタン・別の組み合わせ）に、性的な内容の記事を出さない（自分で名前を入れれば選べる） ----
rep("""    const i=await loadTitle(t); if(i>=0&&!ex.includes(i)&&!BLOCK.has(i)&&!isChamp(i)) return i; }""",
    """    if(NORAND.has(t)) continue;
    const i=await loadTitle(t); if(i>=0&&!ex.includes(i)&&!BLOCK.has(i)&&!isChamp(i)&&!NORAND.has(F[i][1])) return i; }""")
rep("async function rnd(ex){", "let NORAND=new Set();   // ランダムに出さない記事（tools/norand.py で作る）\nasync function rnd(ex){")
rep("EXCL=new Set(ex); setCount(); famToday();", "EXCL=new Set(ex); setCount(); famToday();\n  try{ NORAND=new Set(await fetch('data/norand.json?v='+VER).then(r=>r.ok?r.json():[])); }catch(_){}")

# ---- 42. 王座戦欄の更新を控えめにする（無料枠を守る）：2分ごと。欄が画面に見えていない・10分以上操作がない・タブが裏にあるときは確認しない ----
rep("""setInterval(refreshThrone,30000); document.addEventListener('visibilitychange',()=>{ if(!document.hidden) refreshThrone(); });""",
"""let TH_LAST=Date.now(), TH_ACT=Date.now(), TH_SEEN=true;
function thTick(force){ if(document.hidden||(!TH_SEEN&&!force)||Date.now()-TH_ACT>600000) return; if(!force&&Date.now()-TH_LAST<120000) return; TH_LAST=Date.now(); refreshThrone(); }
['pointerdown','keydown','scroll','touchstart'].forEach(e=>addEventListener(e,()=>{ const idle=Date.now()-TH_ACT>600000; TH_ACT=Date.now(); if(idle) thTick(true); },{passive:true}));
try{ new IntersectionObserver(es=>{ TH_SEEN=es.some(e=>e.isIntersecting); if(TH_SEEN) thTick(); }).observe($('#throne')); }catch(_){}
setInterval(()=>thTick(),15000);
document.addEventListener('visibilitychange',()=>{ if(!document.hidden) thTick(); });""")

# ---- 43. 表示を速くする：フォントの読み込みで画面を止めない・記事データをまとめて同時に読む・試合の再生を先に始める ----
rep("""<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Zen+Kaku+Gothic+New:wght@400;500;700&family=Zen+Old+Mincho:wght@600&display=swap">""",
    """<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Zen+Kaku+Gothic+New:wght@400;500;700&family=Zen+Old+Mincho:wght@600&display=swap" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Zen+Kaku+Gothic+New:wght@400;500;700&family=Zen+Old+Mincho:wght@600&display=swap"></noscript>""")
rep("""  try{ NORAND=new Set(await fetch('data/norand.json?v='+VER).then(r=>r.ok?r.json():[])); }catch(_){}
  if(await openShared()) return; sel[0]=await rnd([]); sel[1]=await rnd([sel[0]]);""",
"""  const nrP=fetch('data/norand.json?v='+VER).then(r=>r.ok?r.json():[]).then(a=>{ NORAND=new Set(a); }).catch(()=>{});
  if(await openShared()) return;
  const [x,y]=await Promise.all([rnd([]),rnd([])]); await nrP;   // 2記事を同時に読む。ランダムに出さない記事に当たっていたら引き直す
  sel[0]=NORAND.has(F[x][1])?await rnd([y]):x; sel[1]=(y===sel[0]||NORAND.has(F[y][1]))?await rnd([sel[0]]):y;""")
rep("""  if(q.get('c')&&API){ try{ await loadThrone(); const x=await fetch(API+'/api/challenge/'+encodeURIComponent(q.get('c'))).then(r=>r.json()); if(x.error) return false;
      const a=await loadTitle(x.challenger.title), b=await loadTitle(x.champ.title); if(a<0||b<0) return false;
      sel[0]=await rnd([a,b]); sel[1]=await rnd([a,b,sel[0]]); renderPick(0); renderPick(1); updateFight();
      MODE={res:x,no:x.reignNo,replay:true}; startBattle([a,b]); return true; }catch(_){ return false; } }""",
"""  if(q.get('c')&&API){ try{ const [,x]=await Promise.all([loadThrone(), fetch(API+'/api/challenge/'+encodeURIComponent(q.get('c'))).then(r=>r.json())]); if(x.error) return false;
      const [a,b]=await Promise.all([loadTitle(x.challenger.title), loadTitle(x.champ.title)]); if(a<0||b<0) return false;
      MODE={res:x,no:x.reignNo,replay:true}; startBattle([a,b]);   // 再生を先に始めて、自由対戦の欄はあとから埋める
      const [c,d]=await Promise.all([rnd([a,b]),rnd([a,b])]); sel[0]=c; sel[1]=d===c?await rnd([a,b,c]):d; renderPick(0); renderPick(1); updateFight(); return true; }catch(_){ return false; } }""")
rep("""  await loadThrone();
  const ids=[await loadTitle(ta).catch(()=>-1), await loadTitle(tb).catch(()=>-1)]; const why=[];""",
"""  const [,ia,ib]=await Promise.all([loadThrone(), loadTitle(ta).catch(()=>-1), loadTitle(tb).catch(()=>-1)]);
  const ids=[ia,ib]; const why=[];""")

# ---- 44. 同じ組み合わせの王座戦は一度きり：断られたときは、その試合の再生リンクを添える ----
rep("  if(d.error){ m.className='msg err'; m.textContent=d.error; return; }",
    "  if(d.error){ m.className='msg err'; m.textContent=d.error;\n    if(d.known&&d.known.id){ const a=document.createElement('a'); a.href='?c='+d.known.id; a.textContent=' その試合を見る'; a.className='rp'; a.onclick=e=>{ e.preventDefault(); replayChallenge(d.known.id); }; m.appendChild(a); }\n    return; }")

# ---- 45. 「自滅」に、使わなかったら何が起きたかを1行で添える（代わりに出した技と、勝ち方） ----
rep("const c=simC(ai,bi,{disable:{[i]:m}}); if(c.w!==r.w||c.kind!==r.kind) dec.push({who:i,move:m,alt:c.w}); }",
    "const c=simC(ai,bi,{disable:{[i]:m}}); if(c.w!==r.w||c.kind!==r.kind) dec.push({who:i,move:m,alt:c.w,ak:c.kind,at:c.tick,rep:repMove(r,c,i===ai?0:1,m)}); }")
rep("function analyze0(ai,bi){", """// 技を1つ外してやり直した試合で、その技の代わりに最初に出した技（[技名, 種類]）
function repMove(r,c,sd,m){ let k=0; while(k<r.log.length&&k<c.log.length&&r.log[k].s===c.log[k].s) k++;
  for(let j=k;j<c.log.length;j++){ const e=c.log[j]; if(e.side===sd&&e.mv&&e.mv[1]!==m) return [e.mv[1],e.mv[0]]; } return null; }
function analyze0(ai,bi){""")
rep("for(const i of [ai,bi]){ const k=decW.filter(d=>d.who===i&&d.who===d.alt); if(k.length) lines.push(`<b>自滅</b>：${esc(F[i][0])}の${mv(k)}（使わなければ勝っていた）`); }",
    """for(const i of [ai,bi]){ const k=decW.filter(d=>d.who===i&&d.who===d.alt); if(!k.length) continue;
    const d=k[0], op=F[i===ai?bi:ai][0];
    if(k.length===1&&d.rep){ const eff=d.rep[1]==='BIND'?`で${esc(op)}の動きを鈍らせ`:d.rep[1]==='HASTE'?'で次の行動を早め':'を出し';
      const how=d.ak==='KO'?`${d.at}カウントでKO勝ちしていた`:d.ak==='判定'?'判定で勝っていた':'勝っていた';
      lines.push(`<b>自滅</b>：${esc(F[i][0])}の【${esc(d.move)}】。使わなければ代わりに【${esc(d.rep[0])}】${eff}、${how}`); }
    else lines.push(`<b>自滅</b>：${esc(F[i][0])}の${mv(k)}（使わなければ勝っていた）`); }""")

# ---- 46. サーバーで勝敗を決めるときは、表示用の計算（技を外したやり直し・番狂わせの判定）を省く（勝敗には使っていない） ----
rep("function analyze(ai,bi){ if(lt(ai,bi)) return analyze0(ai,bi);\n  const an=analyze0(bi,ai), r=an.r;",
    "function analyze(ai,bi,lite){ if(lt(ai,bi)) return analyze0(ai,bi,lite);\n  const an=analyze0(bi,ai,lite), r=an.r;")
rep("function analyze0(ai,bi){\n  const r=simC(ai,bi); const base=simC(ai,bi,{noMoves:true,noRiv:true});\n  const dec=[];",
    "function analyze0(ai,bi,lite){   // lite：勝敗だけ分かればよいとき（サーバー）。決め手・番狂わせの計算をしない\n  const r=simC(ai,bi); const base=lite?{w:null}:simC(ai,bi,{noMoves:true,noRiv:true});\n  const dec=[]; if(!lite){")
rep("if(r.riv){ const c=simC(ai,bi,{noRiv:true}); if(c.w!==r.w||c.kind!==r.kind) dec.push({who:-1,move:'因縁',alt:c.w}); }\n  return stage(ai,bi,{r,upset:r.w!==null&&base.w!==r.w,baseW:base.w,dec});",
    "if(r.riv){ const c=simC(ai,bi,{noRiv:true}); if(c.w!==r.w||c.kind!==r.kind) dec.push({who:-1,move:'因縁',alt:c.w}); } }\n  return stage(ai,bi,{r,upset:!lite&&r.w!==null&&base.w!==r.w,baseW:base.w,dec});")

# ---- 47. 実況の言い回しを増やす（勝敗・ダメージは変えない。同じ試合なら同じ文になる） ----
# 技の文（mv[6]）を配列でも持てるようにし、試合ごと・行動ごとに選ぶ
rep("const tp=mv[6]||null;", "const tp=Array.isArray(mv[6])?pickT(mv[6],k+'|'+mv[1]):(mv[6]||null);")
rep("const line=d.line.replace('{R}',ratioTxt(r)).replace('{C}',countTxt(r));",
    "const line=[].concat(d.line).map(L=>L.replace('{R}',ratioTxt(r)).replace('{C}',countTxt(r)));")
rep("const line=tpl.replace(/\\{F\\}/g,shown.join('・')).replace(/\\{n\\}/g,fmt(n));",
    "const line=[].concat(tpl).map(t=>t.replace(/\\{F\\}/g,shown.join('・')).replace(/\\{n\\}/g,fmt(n)));")
DL = {
 "line:'{A}の【{N}】！ {B}の{R}の文字数を誇る記事の重みでのしかかる。'":
  ["{A}の【{N}】！ {B}の{R}の本文を一冊に綴じて、その角で殴る。","{A}の【{N}】！ 「続きを読む」が終わらない。{B}の{R}の文字数で押しつぶす。","{A}の【{N}】！ {B}の{R}の加筆の積み重ねを、そのまま重みにして叩きつける。"],
 "line:'{A}の【{N}】！ {B}の{R}の被リンクで張り巡らせた網で縛る。{B}の動きが鈍った。'":
  ["{A}の【{N}】！ {B}の{R}の記事から名前を呼ばれる人脈で、{B}を取り囲む。{B}の動きが鈍った。","{A}の【{N}】！ 「リンク元」を開けば{B}の{R}。その顔の広さで{B}を縛る。{B}の動きが鈍った。"],
 "line:'{A}の【{N}】！ {B}の{R}読まれている人気で押し寄せ、{H}連撃。'":
  ["{A}の【{N}】！ {B}の{R}の閲覧数。読者の視線が束になって、{H}連撃。","{A}の【{N}】！ 「{B}より{R}読まれています」——アクセス数を背負って{H}連撃。","{A}の【{N}】。{B}の{R}の読者が一斉にページを開き、{H}連撃。"],
 "line:'{A}の【{N}】！ {B}の{R}のカテゴリに顔を出している顔の広さで殴る。'":
  ["{A}の【{N}】！ {B}の{R}のカテゴリに名を連ねる顔の広さで、正面から殴る。","{A}の【{N}】！ 「どの分類にも顔が利く」——{B}の{R}のカテゴリを背負って殴る。","{A}の【{N}】！ {B}の{R}のカテゴリから知り合いを総動員する勢いで殴る。"],
 "line:'{A}の【{N}】。{B}の{R}のリンクで道案内して迷わせ、そこを殴る。'":
  ["{A}の【{N}】。{B}の{R}のリンクで作った迷路に{B}を誘い込み、行動が遅れたところを殴る。","{A}の【{N}】。「詳しくはこちら」「関連項目も参照」——{B}の{R}のリンクで寄り道させ、そこを殴る。","{A}の【{N}】。{B}の{R}のリンクを次々に踏ませて記事の外へ連れ出し、戻ってきたところを殴る。"],
 "line:'{A}の【{N}】！ {B}の{R}の高さから見下ろし、そのまま踏みつける。'":
  ["{A}の【{N}】！ {B}の{R}の高さ。見上げる{B}の首が痛くなったところを踏みつける。","{A}の【{N}】！ {B}の{R}の高さから、文字どおり上から目線で殴る。"],
 "line:'{A}の【{N}】！ {B}の{R}の人数で押し寄せ、{H}連撃。'":
  ["{A}の【{N}】！ {B}の{R}の人口が一斉に動き出し、{H}連撃。","{A}の【{N}】！ 住民を数えれば{B}の{R}。その全員で{H}連撃。"],
}
for a, extra in DL.items():
    orig = a[len("line:"):]
    rep(a, "line:[" + orig + "," + ",".join("'" + x + "'" for x in extra) + "]")

# 記事データ系の技
rep("cntT(m.ch,[3000,10000,30000,60000,100000]),0,'{A}の【{N}】！ 約'+jn(m.ch)+'文字の記事本文を丸ごと{B}に叩きつける。','meta']",
    "cntT(m.ch,[3000,10000,30000,60000,100000]),0,['{A}の【{N}】！ 約'+jn(m.ch)+'文字の記事本文を丸ごと{B}に叩きつける。','{A}の【{N}】！ 約'+jn(m.ch)+'文字の本文を、冒頭から脚注まで一気に{B}へぶつける。','{A}の【{N}】！ 約'+jn(m.ch)+'文字。{B}が読み終わる前に殴り終わっている。'],'meta']")
rep("0,pickT(['{A}の【{N}】！ '+m.lh+'本'+(m.lhp?'以上':'')+'の被リンクで{B}を縛り上げる。{B}の動きが鈍った。','{A}の【{N}】！ 自分を指す'+m.lh+'本'+(m.lhp?'以上':'')+'のリンクを投げ縄にして{B}を捕まえる。{B}の動きが鈍った。'],String(i)),'meta']",
    "0,['{A}の【{N}】！ '+m.lh+'本'+(m.lhp?'以上':'')+'の被リンクで{B}を縛り上げる。{B}の動きが鈍った。','{A}の【{N}】！ 自分を指す'+m.lh+'本'+(m.lhp?'以上':'')+'のリンクを投げ縄にして{B}を捕まえる。{B}の動きが鈍った。','{A}の【{N}】！ '+m.lh+'本'+(m.lhp?'以上':'')+'のリンク元から一斉に糸が伸び、{B}に絡みつく。{B}の動きが鈍った。'],'meta']")
rep("0,'{A}の【{N}】！ 年間'+jn(m.pv)+'回読まれた視線が{B}に突き刺さり、{H}連撃。','meta']",
    "0,['{A}の【{N}】！ 年間'+jn(m.pv)+'回読まれた視線が{B}に突き刺さり、{H}連撃。','{A}の【{N}】！ 1年で'+jn(m.pv)+'回開かれたページから、読者の視線が{B}へ。{H}連撃。','{A}の【{N}】！ 年間'+jn(m.pv)+'回の閲覧。その視線がすべて{B}に向き、{H}連撃。'],'meta']")
rep("0,g0.cc?'{A}の【{N}】！ 「'+g0.cc[0]+'」「'+g0.cc[1]+'」など'+ca+'個のカテゴリで{B}を分類し尽くす。{B}の動きが鈍った。':'{A}の【{N}】！ '+ca+'個のカテゴリで{B}を分類し尽くす。{B}の動きが鈍った。','wp']",
    "0,g0.cc?['{A}の【{N}】！ 「'+g0.cc[0]+'」「'+g0.cc[1]+'」など'+ca+'個のカテゴリで{B}を分類し尽くす。{B}の動きが鈍った。','{A}の【{N}】！ 「'+g0.cc[0]+'」にも「'+g0.cc[1]+'」にも属する顔の広さで、'+ca+'方向から{B}を囲む。{B}の動きが鈍った。']:['{A}の【{N}】！ '+ca+'個のカテゴリで{B}を分類し尽くす。{B}の動きが鈍った。','{A}の【{N}】！ '+ca+'個のカテゴリが四方から{B}を囲む。{B}の動きが鈍った。'],'wp']")
rep("0,g0.h?'{A}の【{N}】！ 「'+g0.h.join('」「')+'」……記事の見出し'+se+'個を次々に叩きつけ、{H}連撃。':'{A}の【{N}】！ 記事の見出し'+se+'個を次々に叩きつけ、{H}連撃。','wp']",
    "0,g0.h?['{A}の【{N}】！ 「'+g0.h.join('」「')+'」……記事の見出し'+se+'個を次々に叩きつけ、{H}連撃。','{A}の【{N}】！ 目次を開くと「'+g0.h.join('」「')+'」……見出し'+se+'個が順番に飛んでくる。{H}連撃。']:['{A}の【{N}】！ 記事の見出し'+se+'個を次々に叩きつけ、{H}連撃。','{A}の【{N}】！ 目次に並ぶ見出し'+se+'個が順番に飛んでくる。{H}連撃。'],'wp']")
rep("0,'{A}の【{N}】。記事から伸びる'+ln+(lc?'本以上':'本')+'のリンクで{B}を迷子にさせ、そこを殴る。','wp']",
    "0,['{A}の【{N}】。記事から伸びる'+ln+(lc?'本以上':'本')+'のリンクで{B}を迷子にさせ、そこを殴る。','{A}の【{N}】。'+ln+(lc?'本以上':'本')+'のリンクを次々に踏ませて{B}を寄り道させ、行動が遅れたところを殴る。'],'wp']")

# 汎用技
rep("0,pickT(['{A}の【{N}】！ その正体は「'+g.c+'」。意表を突かれた{B}に一撃。','{A}の【{N}】。「実は、'+g.c+'なんです」——{B}が戸惑った隙に殴る。'],String(i)),'gen']",
    "0,['{A}の【{N}】！ その正体は「'+g.c+'」。意表を突かれた{B}に一撃。','{A}の【{N}】。「実は、'+g.c+'なんです」——{B}が戸惑った隙に殴る。','{A}の【{N}】！ Wikidataが告げる。{A}は「'+g.c+'」である、と。返す言葉のない{B}に一撃。','{A}の【{N}】。名札に「'+g.c+'」と書いてある。それを見せつけながら{B}を殴る。'],'gen']")
rep("0,'{A}の【{N}】！ '+al+(g.r[0]>g.r.length-1?'など':'')+g.r[0]+'個の別名に分身して、{H}連撃。','gen']",
    "0,['{A}の【{N}】！ '+al+(g.r[0]>g.r.length-1?'など':'')+g.r[0]+'個の別名に分身して、{H}連撃。','{A}の【{N}】！ '+al+(g.r[0]>g.r.length-1?'など':'')+'——転送ページ'+g.r[0]+'個ぶんの{A}が現れ、{H}連撃。','{A}の【{N}】！ どの名前で検索しても{A}にたどり着く。'+al+(g.r[0]>g.r.length-1?'など':'')+g.r[0]+'個の別名で{H}連撃。'],'gen']")
rep("0,'{A}の【{N}】。記事から張られた外部リンク'+g.x+'本を飛び石にして{B}の背後へ回り込み、一撃。勢いで次の行動が早まる。','gen']",
    "0,['{A}の【{N}】。記事から張られた外部リンク'+g.x+'本を飛び石にして{B}の背後へ回り込み、一撃。勢いで次の行動が早まる。','{A}の【{N}】。外部リンク'+g.x+'本を次々にたどって会場の外を一周し、{B}の背後から一撃。勢いで次の行動が早まる。','{A}の【{N}】。外部リンク'+g.x+'本を踏み台に跳び上がり、{B}の頭上から一撃。勢いで次の行動が早まる。','{A}の【{N}】。記事の外へ出ていく'+g.x+'本のリンクを渡り歩き、思わぬ方向から{B}に一撃。勢いで次の行動が早まる。'],'gen']")
rep("2.5,0,'{A}の【{N}】！ '+g.job+'としての本領を発揮して{B}に挑む。','gen']",
    "2.5,0,['{A}の【{N}】！ '+g.job+'としての本領を発揮して{B}に挑む。','{A}の【{N}】！ 職業欄には「'+g.job+'」。その肩書きのまま{B}を殴る。','{A}の【{N}】！ '+g.job+'として磨いた腕を、なぜか{B}を殴ることに使う。'],'gen']")
rep("3,0,'{A}の【{N}】！ {B}の記事に貼られた「出典が不足している」の札を指さした。{B}の動きが止まった。']",
    "3,0,['{A}の【{N}】！ {B}の記事に貼られた「出典が不足している」の札を指さした。{B}の動きが止まった。','{A}の【{N}】！ 「その話、出典はありますか」。{B}の記事に貼られた札を読み上げる。{B}の動きが止まった。','{A}の【{N}】！ {B}の記事に掲げられた「出典が不足している」の札。{B}は言い返せず、動きが止まった。']]")
rep("2,0,'{A}の【{N}】。{B}の記事がまだ書きかけだと指摘する。加筆に気を取られた{B}を殴る。']",
    "2,0,['{A}の【{N}】。{B}の記事がまだ書きかけだと指摘する。加筆に気を取られた{B}を殴る。','{A}の【{N}】。「{B}さん、記事がまだ書きかけですよ」。加筆に気を取られた{B}を殴る。','{A}の【{N}】。{B}の記事の「書きかけ」の札を指でつつく。{B}が加筆に走ったところを殴る。']]")
rep("0,'{A}は【{N}】。'+ym(ga.ct)+'からWikipediaにいる古株として、'+(yb-ya)+'年後輩の{B}の攻撃を{P}%受け流す構え。ついでに小突く。']",
    "0,['{A}は【{N}】。'+ym(ga.ct)+'からWikipediaにいる古株として、'+(yb-ya)+'年後輩の{B}の攻撃を{P}%受け流す構え。ついでに小突く。','{A}は【{N}】。'+ym(ga.ct)+'の初版から書き継がれてきた記事として、'+(yb-ya)+'年後輩の{B}の攻撃を{P}%受け流す構え。ついでに小突く。','{A}は【{N}】。「私がWikipediaに来たのは'+ym(ga.ct)+'です」。'+(yb-ya)+'年後輩の{B}の攻撃を{P}%受け流す構えで、ついでに小突く。']]")

# 名前で殴る・年功序列（その場で文を作る技）
rep("line='{A}の【{N}】！ '+(ma<=2?'たった':'')+ma+'音の名前を全力で叩きつける'+(r>=1?'。':'が、'+mb+'音の{B}には効きが薄い。'); }",
    "line=pickT(['{A}の【{N}】！ '+(ma<=2?'たった':'')+ma+'音の名前を全力で叩きつける','{A}の【{N}】！ 名前を一音ずつ区切って、'+(ma<=2?'たった':'')+ma+'音ぶん叩きつける','{A}の【{N}】！ 自分の名前を'+(ma<=2?'たった':'')+ma+'音、大声で名乗りながら殴る'],k+'|nm')+(r>=1?'。':'が、'+mb+'音の{B}には効きが薄い。'); }")
rep("line='{A}は【{N}】を主張した（{F}）。しかし{B}は年齢不詳。先輩風は空を切った。'; }",
    "line=pickT(['{A}は【{N}】を主張した（{F}）。しかし{B}は年齢不詳。先輩風は空を切った。','{A}は【{N}】を主張した（{F}）。しかし{B}の記事には年が書かれていない。先輩風は空を切った。'],k+'|sn'); }")
rep("line='{A}の【{N}】。{F}の{A}が、'+ys(y.year)+'の{B}に先輩風を吹かせて小突く。'+fmt(y.year-x.year)+'年の差で攻撃力が上がった。'; }",
    "line=pickT(['{A}の【{N}】。{F}の{A}が、'+ys(y.year)+'の{B}に先輩風を吹かせて小突く。'+fmt(y.year-x.year)+'年の差で攻撃力が上がった。','{A}の【{N}】。{F}の{A}が、'+fmt(y.year-x.year)+'年後輩の{B}に「昔はね」と語りかけながら小突く。攻撃力が上がった。','{A}の【{N}】。「'+ys(y.year)+'？ まだ若いですね」——{F}の{A}が先輩の顔で小突く。'+fmt(y.year-x.year)+'年の差で攻撃力が上がった。'],k+'|sn'); }")
rep("line='{A}は【{N}】を主張した（{F}）。しかし{B}のほうが'+fmt(x.year-y.year)+'年先輩だった。何も起きない。'; } }",
    "line=pickT(['{A}は【{N}】を主張した（{F}）。しかし{B}のほうが'+fmt(x.year-y.year)+'年先輩だった。何も起きない。','{A}は【{N}】を主張した（{F}）。ところが{B}は'+fmt(x.year-y.year)+'年も先輩だった。何も起きない。'],k+'|sn'); } }")

# MAP の技
rep("'{A}の【{N}】！ {F}など記録上{n}個の肩書きを次々に名乗り、{H}連撃。']",
    "['{A}の【{N}】！ {F}など記録上{n}個の肩書きを次々に名乗り、{H}連撃。','{A}の【{N}】！ 名刺を{n}枚。{F}などの肩書きを一枚ずつ差し出しながら、{H}連撃。']]")
rep("'{A}の【{N}】！ {F}の作法で{B}を殴る。']",
    "['{A}の【{N}】！ {F}の作法で{B}を殴る。','{A}の【{N}】！ ジャンルは{F}。その流儀のまま{B}に殴りかかる。']]")

# 解説の一言を増やす（既存の行の末尾に足すだけ。喋るかどうかの判定は変えない）
MX = [
 ("'外部サイトを経由して回り込む。セキュリティ的には推奨されません' ]]", ["外部リンクは、本来は出典や公式サイトを示すためのものです","リンク先のサイトにとっては、知らないうちに試合会場になっています","飛び石が一つでもリンク切れなら、いまごろ池の中です"]),
 ("'古株の構え。初版の頃の苦労がにじみます' ]]", ["記事の作成日で守りを固める。編集履歴は、こういう時に読み返されます","古い記事には、古い記事なりの重みがあります","初版を書いた人も、まさか盾にされるとは思わなかったでしょう"]),
 ("'別名の数だけ自分がいる。少し怖いですね' ]]", ["転送ページも、数が集まれば軍勢になります","どの名前で呼んでも本人。相手からすれば、悪夢です"]),
 ("'本業で勝負する。ここが職場かどうかは、議論の余地があります' ]]", ["本職の技です。職務経歴書に書けるかは分かりません","職業欄が、ここでは武器になります"]),
 ("'節の見出しが飛んでくる。本文は置いてきたようです' ]]", ["見出しだけ読んで分かった気になる。ネットではよくあることです","章立てが整っていると、殴る順番にも迷いがありません"]),
 ("'カテゴリで囲む。整理整頓が攻撃になる瞬間です' ]]", ["カテゴリの数は、その記事がどれだけ多くの棚に並んでいるかを示します","分類されると、逃げ場がなくなります"]),
 ("'分類されただけで殴られる。理不尽ですが、事実です' ]]", ["自己紹介が、そのまま攻撃になっています","Wikidataの分類に、反論の余地はありません"]),
 ("'反論するにも、まず出典が要ります' ]]", ["この札が貼られた記事は、実はかなり多いんです","札を外すには、出典を足すしかありません"]),
 ("'書きかけでも、戦わなければならない時があります' ]]", ["書きかけの記事は、伸びしろの塊でもあります","加筆を待っている記事は、日本語版だけでも膨大な数です"]),
 ("'生まれた年で殴る。本人の努力とは一切関係ありません' ]]", ["年上というだけで強い。理屈ではありません"]),
 ("'リンクの先にも記事があります。全員、巻き込まれています' ]]", ["リンクの数は、記事どうしのつながりの数でもあります","青い文字の一つ一つが、縄の一本になっています"]),
 ("'文字数は、積み重なると鈍器になります' ]]", ["この文字数を書いたのは、名もなき編集者の皆さんです","長い記事ほど、殴られたときに痛い。当然です"]),
 ("'閲覧数の多さは、時に物理的な質量を持ちます' ]]", ["読者の数だけ拳がある。そう考えると、恐ろしい技です","今日この試合を見ている人も、閲覧数に数えられるのでしょうか"]),
 ("'比べられた側には、反論の機会が与えられていません' ]]", ["数字は嘘をつきません。ただ、容赦もしません","比べ方を選んだ時点で、勝負はついていたのかもしれません"]),
 ("'全部読んだ人は、この会場にはいないでしょう' ]]", ["作品が多いということは、それだけ語られてきたということです"]),
 ("'これは効いた。記事が一段落削られたような衝撃です','大きい。いまの一撃で、要約欄が書き換わったかもしれません','重い一撃です。脚注まで響いています','いまのは痛い。版の差分で見ても、かなりの削除量です','効いています。カテゴリがいくつか外れたかもしれません' ]]", ["いまの一撃は、ノートページで議論になるレベルです","効いた。差し戻しが必要かもしれません"]),
]
rep("'音の数で殴る。言語学者が見たら泣くでしょう' ]; }]", "'音の数で殴る。言語学者が見たら泣くでしょう','長い名前は、名乗るだけで一仕事です','名付けた人も、まさか殴るのに使われるとは' ]; }]")
for a, extra in MX:
    rep(a, a[:-len(" ]]")] + "," + ",".join("'" + x + "'" for x in extra) + " ]]")

# ---- 48. あなたの代表戦：誕生日・生まれた年・出身地。入れたい項目だけで「あなたの代表」を探し、きょう生まれの代表と戦わせる ----
#   誕生日が同じ人：日本語版Wikipediaの日付の記事（「6月18日」など）の「誕生日」の節。直近30日の閲覧数順
#   同い年：data/bd/years.json.gz（tools/build_bd.py で収録データから作る）。1年間の閲覧数順
#   同郷：日本語版Wikipediaの「Category:◯◯出身の人物」。直近30日の閲覧数順
#   入力はこの端末の中だけで使う。覚えておくかどうかも選べる。共有文に何を書くかも選べる
rep('  <section id="zukan" class="card" hidden></section>\n',
    '  <section id="zukan" class="card" hidden></section>\n  <section id="mine" class="card"><div class="sechead"><h2>あなたの代表戦</h2><span>誕生日・生まれた年・出身地。入れたい項目だけで、あなたの代表を探して戦わせる</span></div><div class="trow"><button type="button" class="btn" id="mineopen">自分の代表を探す</button></div></section>\n')
rep("#zukan{padding:16px;display:flex;flex-direction:column;gap:12px}",
    "#zukan,#mine{padding:16px;display:flex;flex-direction:column;gap:12px}\n#mine .trow{display:flex;gap:8px}\n"
    "#famdlg [hidden]{display:none!important}\n"
    ".mform{display:grid;grid-template-columns:auto 1fr;gap:10px 12px;align-items:center;padding:14px 16px}\n"
    ".mform label{font-size:13px;color:var(--muted);white-space:nowrap}\n"
    ".mform .mrow{display:flex;gap:6px;align-items:center;flex-wrap:wrap}\n"
    ".mform input,.mform select{box-sizing:border-box;font:inherit;font-size:16px;padding:6px 8px;border:1px solid var(--line);border-radius:8px;background:var(--paper);color:var(--ink);min-width:0}\n"
    ".mform input[type=text]{width:100%}.mform input[type=number]{width:7em}\n"
    ".mform .mtip{grid-column:1/-1;font-size:13px;color:var(--muted)}\n"
    ".mform .mkeep{grid-column:1/-1;font-size:12px;color:var(--muted);display:flex;gap:6px;align-items:center}\n"
    ".mform .mkeep input{width:auto}\n"
    ".mform .mgo{grid-column:1/-1;display:flex;gap:8px;align-items:center;margin-top:4px}\n"
    ".mform .mgo .btn.big{flex:1}\n"
    ".mst{font-size:12px;color:var(--muted);padding:0 16px}\n"
    ".msum{display:flex;gap:8px;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid var(--line);font-size:13px;color:var(--muted)}\n"
    ".msum span{overflow-wrap:anywhere}\n"
    ".mcard{margin:14px 16px;padding:14px;border:1px solid var(--line);border-radius:12px;display:flex;flex-direction:column;gap:12px}\n"
    ".mcard .mpick{display:flex;flex-wrap:wrap;gap:6px}\n"
    ".mcard .mpick button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--paper);color:var(--ink);border-radius:999px;padding:4px 10px;cursor:pointer}\n"
    ".mcard .mpick button[aria-pressed=true]{border-color:var(--a);background:var(--a);color:#fff}\n"
    ".mduel{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:start}\n"
    ".mduel>div{display:flex;flex-direction:column;gap:2px;min-width:0}.mduel>div:last-child{text-align:right;align-items:flex-end}\n"
    ".mduel small{font-size:11px;color:var(--muted)}.mduel b{font-size:18px;overflow-wrap:anywhere;line-height:1.3}\n"
    ".mduel .ma b{color:var(--a)}.mduel .mb b{color:var(--b)}.mduel .mvx{font-size:12px;color:var(--muted);padding-top:18px}\n"
    ".mlink{font:inherit;font-size:12px;background:none;border:none;padding:2px 0;color:var(--muted);text-decoration:underline;text-underline-offset:3px;cursor:pointer}\n"
    ".mact{display:flex;gap:8px;align-items:center}.mact .btn.big{flex:1}\n"
    ".mshare{border-top:1px dashed var(--line);padding-top:12px;display:flex;flex-direction:column;gap:8px}\n"
    ".mshare .mpv{font-size:12px;white-space:pre-wrap;border:1px solid var(--line);border-radius:8px;padding:8px 10px;overflow-wrap:anywhere;color:var(--muted)}\n"
    ".mshare label{font-size:13px;display:flex;gap:6px;align-items:center}\n"
    ".mwarn{font-size:11px;color:var(--muted)}\n"
    ".mmore{margin:0 16px 8px}.mmore summary{font-size:13px;color:var(--muted);cursor:pointer;padding:8px 0}\n"
    ".mmore .flist{padding:0}\n"
    ".flist li.mh{display:block;border:none;padding:14px 0 2px;font-size:12px;color:var(--muted);font-weight:700}\n"
    ".mwho{display:block;font-size:11px;color:var(--muted);font-weight:400;margin-top:1px}\n"
    ".flist li.mon .fn{color:var(--a)}\n"
    ".mmiss{font-size:12px;color:var(--muted);font-weight:400}\n#famx{white-space:nowrap;flex-shrink:0}")
rep("async function famToday(){", r"""/* ---------- あなたの代表戦（入力はこの端末の中だけで使う） ---------- */
const MINE_K='hk_mine';
const mineLoad=()=>{ try{ return JSON.parse(localStorage.getItem(MINE_K)||'null'); }catch(_){ return null; } };
const mineSave=o=>{ try{ if(o) localStorage.setItem(MINE_K,JSON.stringify(o)); else localStorage.removeItem(MINE_K); }catch(_){} };
function todayJ(){ const d=new Date(Date.now()+9*3600e3); return {m:d.getUTCMonth()+1,d:d.getUTCDate()}; }
async function mineFind(v){ v=String(v||'').trim(); if(!v) return null; if(await inData(v)) return v;
  try{ const c=await suggest(v,null); return c[0]||null; }catch(_){ return null; } }
// 誕生日・出身地・同い年は、百科拳典に置いた索引（tools/build_bd.py で作る）から探す。外には問い合わせない
const gzj=u=>fetch(u).then(async r=>{ if(!r.ok) throw new Error(r.status); return JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text()); });
const BDF={}; const bdFile=p=>BDF[p]||(BDF[p]=gzj('data/bd/'+p+'.json.gz?v='+VER).catch(e=>{ delete BDF[p]; throw e; }));
let BDM=null; const bdMeta=()=>BDM||(BDM=fetch('data/bd/meta.json?v='+VER).then(r=>{ if(!r.ok) throw new Error(r.status); return r.json(); }).catch(e=>{ BDM=null; throw e; }));
const births=(m,d)=>bdFile('d/'+m).then(o=>(o[m+'/'+d]||[]).map(a=>({t:a[0],n:a[1],y:a[2]})));
async function placeKey(v){ const M=await bdMeta(); const get=async k=>{ const o=await bdFile('p/'+(fnv(k)%M.nbp)); return o[k]?k:null; };
  if(/[都道府県市区町村]$/.test(v)&&await get(v)) return v;   // 「岡山市」「岡山県」のように書いてあれば、そのまま
  const C=[]; for(const k of [v+'県',v+'都',v+'府',v,v+'市',v+'区',v+'町',v+'村']){ if(await get(k)) C.push(k); }   // 「岡山」→ 広いほう（岡山県）を先に。狭いほう（岡山市）は案内だけ
  if(C.length){ PALT[v]=C.slice(1).filter(k=>k===v+'市'); return C[0]; }
  const t=await mineFind(v); return t?get(t):null; }   // 一覧にない書き方のときだけ、Wikipediaの検索で正式な記事名を探す
const PALT={};
const natives=k=>bdMeta().then(M=>bdFile('p/'+(fnv(k)%M.nbp))).then(o=>(o[k]||[]).map(a=>({t:a[0],n:a[1],y:a[2]})));
const years=()=>bdFile('years');
const sameDay=(y,m,d)=>bdFile('ymd/'+y).then(o=>(o[m+'/'+d]||[]).map(a=>({t:a[0],n:a[1],y}))).catch(e=>{ if(/404/.test(e.message)) return []; throw e; });
const bdTop=(list,n,skip)=>list.filter(x=>!(skip&&skip(x))).slice(0,n);
const ysJ=y=>y<0?'紀元前'+(-y)+'年':y+'年';
// 代表の「根拠」と、共有したときに推測されうること
const MB={ymd:{lab:'生年月日が同じ',why:v=>v.y+'年'+v.m+'月'+v.d+'日生まれ',warn:'あなたの生年月日'},bd:{lab:'誕生日が同じ',why:v=>v.m+'月'+v.d+'日生まれ',warn:'あなたの誕生日'},yr:{lab:'同い年',why:v=>v.y+'年生まれ',warn:'あなたの年齢'},pl:{lab:'同郷',why:v=>v.pt+'出身',warn:'あなたの出身地'}};
function openMine(){ const dlg=$('#famdlg'); if(!dlg) return; const sv=mineLoad(); const o=sv||{}; const td=todayJ();
  const opt=(n,cur)=>Array.from({length:n},(_,k)=>`<option value="${k+1}"${+cur===k+1?' selected':''}>${k+1}</option>`).join('');
  dlg.setAttribute('aria-label','あなたの代表戦');
  dlg.innerHTML=`<div class="fhead"><div><h3>あなたの代表戦</h3></div><button type="button" class="btn small" id="famx" autofocus>閉じる</button></div>
  <form class="mform" id="mform">
    <div class="mtip">あなたにゆかりのある記事を、代表として戦わせます。入れたい項目だけで大丈夫です。</div>
    <label>誕生日</label><div class="mrow"><select id="mm" aria-label="誕生日の月"><option value="">－</option>${opt(12,o.m)}</select>月<select id="md" aria-label="誕生日の日"><option value="">－</option>${opt(31,o.d)}</select>日</div>
    <label for="my">生まれた年</label><div class="mrow"><input id="my" type="number" inputmode="numeric" min="1900" max="${new Date().getFullYear()}" placeholder="例：1990" value="${esc(o.y||'')}">年</div>
    <label for="mp">出身地</label><input id="mp" type="text" placeholder="例：札幌市" value="${esc(o.p||'')}" autocomplete="off">
    <label class="mkeep"><input type="checkbox" id="mkeep"${sv?' checked':''}>この端末に入力を覚えておく</label>
    <div class="mgo"><button type="submit" class="btn big" id="mfind">代表を探す</button><button type="button" class="btn small" id="mclr">入力を消す</button></div>
  </form>
  <div class="mst" id="mst"></div>
  <div id="mres" hidden></div>
  <div class="fnote">入力は記事を探すためだけに使い、サーバーには送りません。誕生日・生まれた年・出身地は、百科拳典に置いた一覧（Wikidataの生年月日・出生地と、1年間の閲覧数から作成）からこの端末の中で探します。</div>`;
  $('#famx').onclick=()=>dlg.close();
  const notCh=x=>x.t===champTitle();   // いまの王者は自由対戦に出せない（開いたあとに王座の情報が届くこともあるので、毎回たしかめる）
  let seq=0, ST=null;
  function cur(){ return {m:$('#mm').value,d:$('#md').value,y:$('#my').value.trim(),p:$('#mp').value.trim(),f:''}; }
  function keep(){ const v=cur(); mineSave($('#mkeep').checked&&(v.m||v.d||v.y||v.p||v.f)?v:null); }
  const bsub=x=>typeof x.y==='number'?ysJ(x.y)+'生まれ':'';
  function shareText(){ const r=ST.reps[ST.pick], why=$('#mwhy')&&$('#mwhy').checked;
    return fitPost(`【百科拳典】私の代表は${r.x.n}${why?'（'+MB[r.k].why(ST.v)+'）':''}。きょう${td.m}月${td.d}日生まれの${ST.opp.n}と対決！ あなたの代表は？`)+'\n'+DISC; }
  function draw(){ const {reps,pick,v,groups}=ST; const box=$('#mres');
    if(!reps.length){ box.innerHTML=''; return; }
    const r=reps[pick], opp=ST.opp; const sumL=[v.m&&v.d?v.m+'月'+v.d+'日':'',v.y?v.y+'年':'',v.p,v.f].filter(Boolean).join('・');
    box.innerHTML=`<div class="msum"><span>${esc(sumL)}</span><button type="button" class="btn small" id="medit">条件を変える</button></div>
    <div class="mcard">
      ${reps.length>1?`<div class="mpick" role="group" aria-label="代表を選ぶ">${reps.map((x,k)=>`<button type="button" data-k="${k}" aria-pressed="${k===pick}">${esc(MB[x.k].lab)}</button>`).join('')}</div>`:''}
      <div class="mduel"><div class="ma"><small>あなたの代表・${esc(MB[r.k].lab)}</small><b>${esc(r.x.n)}</b><small>${esc(bsub(r.x))}</small></div><span class="mvx">vs</span>
        <div class="mb"><small>きょう${td.m}月${td.d}日生まれ</small>${opp?`<b>${esc(opp.n)}</b><small>${esc(bsub(opp))}</small>${ST.opps.length>1?'<button type="button" class="mlink" id="mopp">相手を変える</button>':''}`:'<small>読み込めませんでした</small>'}</div></div>
      <div class="mact"><button type="button" class="btn big" id="mrepgo"${opp?'':' disabled'}>この対戦を見る</button><button type="button" class="btn small" id="mshr" aria-expanded="false"${opp?'':' disabled'}>共有</button></div>
      <div class="mshare" id="mshp" hidden>
        <label><input type="checkbox" id="mwhy">選ばれた理由（${esc(MB[r.k].why(v))}）も書く</label>
        <div class="mpv" id="mpv"></div>
        ${MB[r.k].warn?`<div class="mwarn">理由を書かなくても、代表の名前から${MB[r.k].warn}が推測されることがあります。</div>`:''}
        <div><a class="btn small" id="mtw" target="_blank" rel="noopener">Xで投稿</a></div></div>
    </div>
    <details class="mmore"><summary>ほかの候補から代表を選ぶ</summary><ol class="flist">${groups.map((g,gi)=>`<li class="mh">${esc(g.h)}</li>`+g.L.map((x,i)=>`<li${x.t===(reps.find(q=>q.k===g.k)||{x:{}}).x.t?' class="mon"':''}><div class="fn">${esc(x.n)}${bsub(x)?`<span class="mwho">${esc(bsub(x))}</span>`:''}</div><div class="fb"><button type="button" class="btn small" data-g="${gi}" data-i="${i}">代表にする</button></div></li>`).join('')).join('')}</ol></details>`;
    box.hidden=false; $('#mform').hidden=true;
    $('#medit').onclick=()=>{ box.hidden=true; $('#mform').hidden=false; $('#mst').textContent=''; dlg.scrollTop=0; };
    box.querySelectorAll('.mpick button').forEach(b=>b.onclick=()=>{ ST.pick=+b.dataset.k; draw(); });
    if($('#mopp')) $('#mopp').onclick=()=>{ ST.oi=(ST.oi+1)%ST.opps.length; ST.opp=ST.opps[ST.oi]; draw(); };
    box.querySelectorAll('[data-g]').forEach(b=>b.onclick=()=>{ const g=groups[+b.dataset.g]; const x=g.L[+b.dataset.i]; const k=reps.findIndex(q=>q.k===g.k);
      if(k>=0){ reps[k]={k:g.k,x}; ST.pick=k; } draw(); dlg.scrollTo({top:0,behavior:'smooth'}); });
    const upd=()=>{ const t=shareText(); $('#mpv').textContent=t+'\n'+location.origin+'/?me=1'; $('#mtw').href='https://x.com/intent/tweet?text='+encodeURIComponent(t)+'&url='+encodeURIComponent(location.origin+'/?me=1'); };
    $('#mshr').onclick=()=>{ const p=$('#mshp'); p.hidden=!p.hidden; $('#mshr').setAttribute('aria-expanded',!p.hidden); if(!p.hidden) upd(); };
    $('#mwhy').onchange=upd;
    $('#mrepgo').onclick=()=>{ if(!opp) return; const c=[r.x,opp].find(x=>notCh(x));   // 開いている間に王座が替わっていたら、探し直して知らせる
      if(c){ run().then(()=>{ const m=$('#mst'); m.textContent='「'+c.n+'」はいま王者になったので、自由対戦に出せません。王座戦で挑めます'; }); return; }
      FP=[{t:r.x.t,n:r.x.n},{t:opp.t,n:opp.n}]; famApply(true); }; }
  async function run(){ const my=++seq; const v=cur(); keep();
    if(!(v.m&&v.d)&&!v.y&&!v.p&&!v.f){ $('#mst').textContent='どれか1つ入れてください'; return; }
    $('#mst').textContent='探しています…';
    const errs=[]; const safe=(p,lab)=>p.catch(()=>{ errs.push(lab); return null; });
    const yi=/^\d{4}$/.test(v.y)?+v.y:null;
    const both=!!(v.m&&v.d&&yi);   // 誕生日と生まれた年の両方があるときは、両方が同じ人（生年月日が同じ人）を探す
    const chT=champTitle(), CH={};   // いまの王者が、本来なら一覧に出るはずだったか（出るはずだったら、外したことを知らせる）
    const top=(L,n,key)=>{ if(chT&&L.slice(0,n+1).some(x=>x.t===chT)) CH[key]=1; return bdTop(L,n,notCh); };
    const [ymdl,bdl,todl,yrd,plt,fvt]=await Promise.all([
      both?safe(sameDay(yi,+v.m,+v.d).then(L=>top(L,10,'ymd')),'生年月日'):null,
      v.m&&v.d?safe(births(+v.m,+v.d).then(L=>top(L,10,'bd')),'誕生日'):null,
      safe(births(td.m,td.d).then(L=>top(L,6,'td')),'きょう'),
      yi?safe(years().then(Y=>Y[yi]||{p:[],o:[]}),'生まれた年'):null,
      v.p?safe(placeKey(v.p),'出身地'):null,
      null ]);
    let pll=null; if(plt) pll=await safe(natives(plt).then(L=>top(L,10,'pl')),'出身地');
    const fvg=[];
    if(my!==seq) return;
    if(yrd&&chT){ if(yrd.p.slice(0,11).some(a=>a[0]===chT)) CH.yr=yi+'年生まれ'; else if(yrd.o.slice(0,7).some(a=>a[0]===chT)) CH.yr=yi+'年にできたもの'; }
    const yp=yrd?yrd.p.map(a=>({t:a[0],n:a[1],y:yi})).filter(x=>!notCh(x)).slice(0,10):[], yo=yrd?yrd.o.map(a=>({t:a[0],n:a[1]})).filter(x=>!notCh(x)).slice(0,6):[];
    const reps=[], groups=[...fvg];
    const and=both&&ymdl&&ymdl.length;
    if(and){ reps.push({k:'ymd',x:ymdl[0]}); groups.push({k:'ymd',h:`生年月日が同じ人（${yi}年${v.m}月${v.d}日生まれ）`,L:ymdl}); }
    else if(bdl&&bdl.length){ reps.push({k:'bd',x:bdl[0]}); groups.push({k:'bd',h:`誕生日が同じ人（${v.m}月${v.d}日生まれ）`,L:bdl}); }
    if(!and&&(yp.length||yo.length)){ reps.push({k:'yr',x:yp[0]||yo[0]}); groups.push({k:'yr',h:`同い年（${yi}年生まれ・${yi}年にできたもの）`,L:[...yp,...yo]}); }
    if(pll&&pll.length){ reps.push({k:'pl',x:pll[0]}); groups.push({k:'pl',h:`同郷の人（${plt}出身）`,L:pll}); }
    const used=new Set(reps.map(r=>r.x.t)); const opps=(todl||[]).filter(x=>!used.has(x.t));
    v.pt=plt||v.p; ST={reps,pick:0,opps,oi:0,opp:opps[0]||null,v,groups};
    const miss=[]; if(v.p&&!(pll&&pll.length)) miss.push('出身地「'+v.p+'」');  if(yi&&!(yp.length||yo.length)) miss.push(yi+'年'); const note=[both&&!and&&!errs.length?yi+'年'+v.m+'月'+v.d+'日生まれの人は見つからなかったので、誕生日と生まれた年で別々に探しました':'',
      (()=>{ const L=[and&&CH.ymd?yi+'年'+v.m+'月'+v.d+'日生まれ':'',!and&&CH.bd&&bdl?v.m+'月'+v.d+'日生まれ':'',!and&&CH.yr?CH.yr:'',CH.pl&&pll?plt+'出身':'',CH.td?'きょう'+td.m+'月'+td.d+'日生まれ':''].filter(Boolean);
        return L.length?'いまの王者「'+((THRONE&&THRONE.champ&&THRONE.champ.display)||chT)+'」（'+L.join('・')+'）は自由対戦に出せないので外しました。王座戦で挑めます':''; })(),
      plt&&plt!==v.p?'出身地は「'+plt+'」で探しました'+((PALT[v.p]||[]).length?'（'+PALT[v.p].map(x=>'「'+x+'」').join('や')+'で探すときは、そのとおり入力してください）':''):''].filter(Boolean).join('。');
    $('#mst').textContent=errs.length?errs.join('・')+'は読み込めませんでした。少し待って、もう一度試してください':!reps.length?'代表が見つかりませんでした'+(miss.length?'（'+miss.join('、')+'）':''):[miss.length?miss.join('、')+'は見つかりませんでした':'',note].filter(Boolean).join('。');
    draw(); dlg.scrollTop=0; }
  $('#mform').onsubmit=e=>{ e.preventDefault(); run(); };
  $('#mkeep').onchange=keep;
  $('#mclr').onclick=()=>{ mineSave(null); $('#mkeep').checked=false; ['mm','md','my','mp'].forEach(k=>$('#'+k).value=''); $('#mst').textContent=''; };
  if(!dlg.open) dlg.showModal(); dlg.scrollTop=0; if(sv) run(); }
function mineInit(){ const b=$('#mineopen'); if(b) b.onclick=openMine; if(new URLSearchParams(location.search).has('me')) openMine();
  const dlg=$('#famdlg'); if(dlg) dlg.addEventListener('close',()=>dlg.setAttribute('aria-label','仲間図鑑')); }
async function famToday(){""")
rep("setCount(); famToday();", "setCount(); famToday(); mineInit();")

# ---- 49. 今日の一戦：日本時間の日付ごとに、全員に同じ対戦（人気の記事 vs 埋もれた記事）を出す。観戦の前に勝敗を予想できる ----
#   組み合わせは日付から決まる（サーバーには何も記録しない）。予想と的中はこの端末にだけ覚える
rep('  <section id="setup" class="card"', '  <section id="today" class="card" hidden></section>\n\n  <section id="setup" class="card"')
rep("#zukan,#mine{padding:16px;display:flex;flex-direction:column;gap:12px}",
    "#zukan,#mine,#today{padding:16px;display:flex;flex-direction:column;gap:12px}\n"
    "#today .tdvs{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:center}\n"
    "#today .tdvs>div{display:flex;flex-direction:column;gap:2px;min-width:0}#today .tdvs>div:last-child{text-align:right;align-items:flex-end}\n"
    "#today .tdvs small{font-size:11px;color:var(--muted)}#today .tdvs b{font-size:20px;line-height:1.3;overflow-wrap:anywhere}\n"
    "#today .tdvs .tA b{color:var(--a)}#today .tdvs .tB b{color:var(--b)}#today .tdvs .tvx{font-family:var(--f-display);font-size:18px;color:var(--muted)}\n"
    "#today .tdq{font-size:13px;color:var(--muted);text-align:center}\n"
    "#today .tdbtn{display:grid;grid-template-columns:1fr 1fr;gap:8px}\n"
    "#today .tdbtn .pa{border-color:var(--a);color:var(--a)}#today .tdbtn .pb{border-color:var(--b);color:var(--b)}\n"
    "#today .tdrow{display:flex;gap:8px;align-items:center;justify-content:center;flex-wrap:wrap;font-size:14px}\n"
    "#today .tdres{font-size:15px;text-align:center;line-height:1.6}#today .tdres b.hit{color:var(--a)}\n"
    "#today .mlink{font:inherit;font-size:12px;background:none;border:none;padding:2px 0;color:var(--muted);text-decoration:underline;text-underline-offset:3px;cursor:pointer}\n"
    "#today .tdttl{display:inline-block;margin-top:4px;padding:2px 10px;border-radius:999px;background:var(--hl);font-size:13px;font-weight:700}\n"
    "#today .tdtmr{font-size:13px;text-align:center;padding:8px 10px;border:1px dashed var(--line);border-radius:10px}\n"
    "#today .tdcal summary{font-size:13px;color:var(--muted);cursor:pointer}\n"
    "#today .hoshi{position:relative;margin-top:8px;border:3px double var(--ink);padding:12px 10px 10px;font-family:'Hiragino Mincho ProN','Yu Mincho','Noto Serif JP',serif;background:var(--paper)}\n"
    "#today .hh{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid var(--ink);padding-bottom:6px;margin-bottom:8px}\n"
    "#today .ht{font-size:12px;line-height:1.4}#today .ht b{font-size:22px;letter-spacing:.15em}\n"
    "#today .hr{font-size:11px;text-align:right;display:flex;flex-direction:column}#today .hr b{font-size:24px;letter-spacing:.1em}\n"
    "#today .hg{display:grid;grid-template-columns:repeat(10,1fr);gap:0;border-top:1px solid var(--ink);border-left:1px solid var(--ink)}\n"
    "#today .hd{border-right:1px solid var(--ink);border-bottom:1px solid var(--ink);display:flex;flex-direction:column;align-items:center;padding:2px 0 4px;min-width:0}\n"
    "#today .hd.now{background:color-mix(in srgb,var(--hl) 45%,transparent)}\n"
    "#today .hd .dn{font-size:9px;color:var(--muted);line-height:1.3;white-space:nowrap}\n"
    "#today .hd .mk{font-size:20px;line-height:1.1;height:1.1em}#today .mk.y{font-size:13px;color:var(--muted)}#today .mk.kk{color:var(--muted)}\n"
    "#today .hf{display:flex;gap:12px;align-items:baseline;justify-content:center;margin-top:10px}#today .hf b{font-size:24px;letter-spacing:.1em}#today .hf span{font-size:13px;color:var(--muted)}\n"
    "#today .hk{font-size:10px;color:var(--muted);text-align:center;margin-top:6px;line-height:1.6}\n"
    "#today .seal{position:absolute;right:10px;bottom:34px;color:#c0392b;border:3px solid #c0392b;border-radius:50%;width:70px;height:70px;display:flex;align-items:center;justify-content:center;text-align:center;font-size:15px;line-height:1.15;font-weight:700;transform:rotate(-14deg);opacity:.85;background:color-mix(in srgb,var(--paper) 70%,transparent)}\n"
    ".tdnote{margin:0 0 10px;padding:8px 12px;border-radius:10px;background:color-mix(in srgb,var(--hl) 25%,transparent);font-size:14px;text-align:center}")
rep("current={ai,bi,an,mode:MODE}; MODE=null;", "current={ai,bi,an,mode:MODE,today:TODAYF}; MODE=null; TODAYF=null;")
rep("(current.mode?$('#throne'):$('#setup')).after(ring);", "(current.mode?$('#throne'):current.today?$('#today'):$('#setup')).after(ring);")
rep("if(!current||current.shown) return; current.shown=true;", "if(!current||current.shown) return; current.shown=true; if(current.today) setTimeout(()=>todayDone(current),0);")
rep("async function famToday(){", r"""/* ---------- 今日の一戦 ---------- */
var TODAYF=null, TD=null;
const TD_K='hk_today';
const tdLoad=()=>{ try{ return JSON.parse(localStorage.getItem(TD_K)||'{}')||{}; }catch(_){ return {}; } };
const tdSave=o=>{ try{ const ks=Object.keys(o).sort(); while(ks.length>60) delete o[ks.shift()]; localStorage.setItem(TD_K,JSON.stringify(o)); }catch(_){} };
const jstDay=(off=0)=>new Date(Date.now()+9*3600e3-off*864e5).toISOString().slice(0,10);
const mdJ=d=>(+d.slice(5,7))+'月'+(+d.slice(8,10))+'日';
function tdStreak(o){ let n=0; for(let k=0;k<400;k++){ const x=o[jstDay(k)]; if(x&&x.hit) n++; else if(k===0&&!(x&&x.done)) continue; else break; } return n; }
// 組み合わせ：日付から決める。人気の記事（POPULAR）と、収録記事からくじ引きした「埋もれた記事」
async function todayPair(day){ const nr=await fetch('data/norand.json?v='+VER).then(r=>r.ok?r.json():[]).then(a=>new Set(a)).catch(()=>new Set());
  for(let k=0;k<30&&!THRONE;k++) await new Promise(r=>setTimeout(r,100));   // 王者は出さないので、王座の情報を少し待つ
  // みんなに同じものを出して𝕏にも流れるので、政治家や、宗教・民族・事件などの題材は避ける
  const NGc=/宗教|民族|人種|性的|犯罪|事件|戦争|紛争|兵器|武器|テロ|災害|病|死刑/;
  const POL=/政治家|活動家|議員|大臣|知事|市長|町長|村長|首相|大統領|政党/;
  const pol=i=>{ const g=GEN[i]||{}; return POL.test([g.job||'',...(g.cc||[]),...(g.h||[])].join(' '))||(EXT[i]||[]).some(e=>(e[0]==='P106'||e[0]==='P102')&&(e[2]||[]).some(x=>POL.test(Array.isArray(x)?x[0]:x))); };
  const ok=i=>i>=0&&!BLOCK.has(i)&&!isChamp(i)&&!nr.has(F[i][1])&&!NORAND.has(F[i][1])&&!NGc.test(((GEN[i]||{}).c||'')+' '+F[i][1])&&!pol(i);
  let a=-1; for(let k=0;k<30&&a<0;k++){ const t=POPULAR[hash('today-a/'+day+'/'+k)%POPULAR.length]; if(!t||nr.has(t)) continue; const i=await loadTitle(t); if(ok(i)) a=i; }
  let b=-1; for(let k=0;k<30&&b<0;k++){ const B=await bucket(hash('today-b/'+day+'/'+k)%NB); const ks=Object.keys(B).sort(); if(!ks.length) continue;
    const t=ks[hash('today-t/'+day+'/'+k)%ks.length]; if(nr.has(t)) continue; const i=await loadTitle(t); if(ok(i)&&i!==a&&(F[i][7]||[]).length) b=i; }
  return a>=0&&b>=0?{day,a,b}:null; }
async function todayInit(){ const box=$('#today'); if(!box||!POPULAR.length) return; const day=jstDay();
  try{ TD=await todayPair(day); }catch(_){ TD=null; } if(!TD) return; todayDraw();
  if(new URLSearchParams(location.search).has('today')) box.scrollIntoView({behavior:'smooth',block:'start'}); }
const TITLES=[[30,'生ける出典'],[14,'歩く百科事典'],[7,'百科の予言者'],[3,'目利き']];   // 連続的中の日数と称号
const tdTitle=n=>(TITLES.find(t=>n>=t[0])||[])[1]||'';
// 的中の記録は、大相撲の星取表にならう（当たり○・外れ●・予想なしの観戦は□・来なかった日は「や」）。番付は今月の勝ち星で決まる
const KANJI=n=>{ const d='〇一二三四五六七八九'; if(n<10) return d[n]; if(n<20) return '十'+(n%10?d[n%10]:''); return d[Math.floor(n/10)]+'十'+(n%10?d[n%10]:''); };
const MON=['','一','二','三','四','五','六','七','八','九','十','十一','十二'];
const BANZUKE=[[27,'横綱'],[24,'大関'],[21,'関脇'],[18,'小結'],[15,'前頭'],[12,'十両'],[9,'幕下'],[6,'三段目'],[3,'序二段'],[0,'序ノ口']];
function tdCal(o){ const now=jstDay(), y=+now.slice(0,4), m=+now.slice(5,7), today=+now.slice(8,10), days=new Date(Date.UTC(y,m,0)).getUTCDate();
  let W=0,L=0,K=0,Y=0; const first=Object.keys(o).filter(k=>k.slice(0,7)===now.slice(0,7)&&o[k].done).sort()[0]; const d0=first?+first.slice(8,10):today;
  const cells=[]; for(let d=1;d<=days;d++){ const k=now.slice(0,8)+String(d).padStart(2,'0'), x=o[k];
    let mk='', c='';
    if(x&&x.done){ if(x.p===null||x.p===undefined){ mk='□'; c='kk'; K++; } else if(x.hit){ mk='○'; c='w'; W++; } else { mk='●'; c='l'; L++; } }
    else if(d<today&&d>=d0){ mk='や'; c='y'; Y++; }   // 初めて来た日より前は数えない
    cells.push(`<div class="hd${d===today?' now':''}"><span class="dn">${KANJI(d)}</span><span class="mk ${c}">${mk}</span></div>`); }
  const rank=(BANZUKE.find(b=>W>=b[0])||[])[1];
  const kachi=W>L&&W+L>=8;
  return `<details class="tdcal"><summary>星取表　${MON[m]}月場所 ${KANJI(W)}勝${KANJI(L)}敗・${rank}</summary><div class="hoshi">
    <div class="hh"><div class="ht">百科拳典<br><b>${MON[m]}月場所</b></div><div class="hr">今場所の番付<b>${rank}</b></div></div>
    <div class="hg">${cells.join('')}</div>
    <div class="hf"><b>${KANJI(W)}勝${KANJI(L)}敗</b>${Y?`<span>${KANJI(Y)}休</span>`:''}${K?`<span>観戦のみ ${KANJI(K)}</span>`:''}</div>
    ${kachi?'<div class="seal">勝ち<br>越し</div>':''}
    <div class="hk">○当たり　●外れ　□予想なしで観戦　や休場（来なかった日）　番付は今月の当たりの数で上がります</div></div></details>`; }
let TMR=null;   // 当てた人だけに見せる、明日の人気の記事
async function tdTomorrow(){ if(TMR) return TMR; const d=jstDay(-1); try{ const x=await todayPair(d); TMR=x?{day:d,a:F[x.a][0]}:null; }catch(_){ TMR=null; } return TMR; }
function todayDraw(){ const box=$('#today'); if(!box||!TD) return; const {day,a,b}=TD; const o=tdLoad(), me=o[day]||{};
  const kind=i=>{ const c=(GEN[i]||{}).c||''; return c==='ヒト'?'人物':c; }; const nm=i=>F[i][0];
  let act;
  if(me.done){ const w=me.w; const res=w===null?'引き分け':esc(w===0?nm(a):nm(b))+'の勝ち';
    const st=tdStreak(o);
    const ttl=me.hit?tdTitle(st):'';
    act=`<div class="tdres">結果：${res}${me.p!==undefined&&me.p!==null?`<br>あなたの予想は<b class="${me.hit?'hit':''}">${me.hit?'当たり！':'外れ'}</b>${me.hit&&st>1?`（${st}日連続）`:''}`:''}${ttl?`<br><span class="tdttl">称号「${esc(ttl)}」</span>`:''}</div>
      ${me.hit?'<div class="tdtmr" id="tdtmr">明日の一戦を少しだけ…</div>':''}
      <div class="tdrow"><button type="button" class="btn small" id="tdre">もう一度見る</button><a class="btn small" id="tdsh" target="_blank" rel="noopener">Xで共有</a></div>`; }
  else if(me.p===0||me.p===1||me.p===null) act=`<div class="tdrow">あなたの予想：<b>${me.p===null?'なし':esc(me.p===0?nm(a):nm(b))}</b><button type="button" class="btn" id="tdgo">観戦する</button></div>`;
  else act=`<div class="tdq">どっちが勝つ？ 予想してから観戦しよう</div><div class="tdbtn"><button type="button" class="btn pa" data-p="0">${esc(nm(a))}</button><button type="button" class="btn pb" data-p="1">${esc(nm(b))}</button></div><div class="tdrow"><button type="button" class="mlink" id="tdno">予想せずに観戦する</button></div>`;
  box.innerHTML=`<div class="sechead"><h2>今日の一戦</h2><span>${mdJ(day)}の対戦。みんな同じ組み合わせで、毎日0時に入れ替わります</span></div>
    <div class="tdvs"><div class="tA"><small>人気の記事</small><b>${esc(nm(a))}</b><small>${esc(kind(a))}</small></div><span class="tvx">vs</span><div class="tB"><small>埋もれた記事</small><b>${esc(nm(b))}</b><small>${esc(kind(b))}</small></div></div>${act}${Object.values(o).some(x=>x&&x.done)?tdCal(o):''}`;
  if($('#tdtmr')) tdTomorrow().then(x=>{ const e=$('#tdtmr'); if(!e) return; e.innerHTML=x?`当てたあなたに、明日の一戦を少しだけ：<b>${esc(x.a)}</b> が登場予定。相手は明日のお楽しみ`:''; if(!x) e.remove(); });
  box.hidden=false;
  const go=()=>{ if(isChamp(a)||isChamp(b)){ todayDraw(); return; } TODAYF={day}; startBattle([a,b]); };
  box.querySelectorAll('[data-p]').forEach(x=>x.onclick=()=>{ const o=tdLoad(); o[day]={p:+x.dataset.p}; tdSave(o); todayDraw(); go(); });
  if($('#tdno')) $('#tdno').onclick=()=>{ const o=tdLoad(); o[day]={p:null}; tdSave(o); todayDraw(); go(); };
  if($('#tdgo')) $('#tdgo').onclick=go;
  if($('#tdre')) $('#tdre').onclick=go;
  if($('#tdsh')){ const st=tdStreak(o); const t=fitPost(`【百科拳典 今日の一戦 ${mdJ(day)}】${nm(a)} vs ${nm(b)}`+(me.p!==null&&me.p!==undefined?`\n予想は${me.hit?'当たり！'+(st>1?`（${tdTitle(st)?tdTitle(st)+'・':''}${st}日連続）`:''):'外れ…'}`:'')+'\nあなたはどっちが勝つと思う？')+'\n'+DISC;
    $('#tdsh').href='https://x.com/intent/tweet?text='+encodeURIComponent(t)+'&url='+encodeURIComponent(location.origin+'/?today=1'); } }
function todayDone(cur){ if(!TD||!cur.today||cur.today.day!==TD.day) return; const o=tdLoad(), me=o[TD.day]||{p:null}; const w=cur.an.r.w;
  const wi=w===null?null:(w===TD.a?0:1); if(!me.done){ me.done=1; me.w=wi; me.hit=me.p!==null&&me.p!==undefined&&me.p===wi; o[TD.day]=me; tdSave(o); }
  todayDraw();
  const res=$('#res'); if(res&&me.p!==null&&me.p!==undefined){ const st=tdStreak(o); const n=document.createElement('div'); n.className='tdnote';
    n.textContent='今日の一戦の予想は'+(me.hit?'当たり！'+(st>1?'（'+(tdTitle(st)?'称号「'+tdTitle(st)+'」・':'')+st+'日連続）':''):'外れでした'); res.prepend(n); } }
async function famToday(){""")
rep("setCount(); famToday(); mineInit();", "setCount(); famToday(); mineInit(); todayInit();")

# ---- 50. トップページの整理：今日の一戦を入口に。王座戦は王者だけ見せて、挑戦の欄と記録は畳む。仲間図鑑と代表戦は「見つける」にまとめる ----
# 今日の一戦を一番上へ（読み込むまでは枠だけ出して、あとから下の枠がずれないようにする）
rep('  <section id="today" class="card" hidden></section>\n\n  <section id="setup" class="card"', '  <section id="setup" class="card"')
rep('  <section id="throne" class="card" hidden aria-live="polite"></section>',
    '  <section id="today" class="card tdload"><div class="sechead"><h2>今日の一戦</h2><span>きょうの組み合わせを準備しています…</span></div></section>\n\n  <section id="throne" class="card" hidden aria-live="polite"></section>')
rep("async function todayInit(){ const box=$('#today'); if(!box||!POPULAR.length) return; const day=jstDay();\n  try{ TD=await todayPair(day); }catch(_){ TD=null; } if(!TD) return; todayDraw();",
    "async function todayInit(){ const box=$('#today'); if(!box) return; if(!POPULAR.length){ box.hidden=true; return; } const day=jstDay();\n  try{ TD=await todayPair(day); }catch(_){ TD=null; } if(!TD){ box.hidden=true; return; } box.classList.remove('tdload'); todayDraw();")
# 王座戦：王者の行だけ見せ、挑戦の欄と記録は「この王者に挑む」で開く
rep("  <div class=\"meta\">この王者を倒せる記事を、",
    "  <details class=\"thx\" id=\"thx\"${THOPEN||msg?' open':''}><summary>この王者に挑む・王座戦の記録</summary>\n  <div class=\"meta\">この王者を倒せる記事を、")
rep("在位中'}）</span></li>`).join('')}</ol></details>`;", "在位中'}）</span></li>`).join('')}</ol></details></details>`;")
rep("  const inp=$('#chT'), dl=$('#sgT');", "  $('#thx').addEventListener('toggle',e=>{ THOPEN=e.target.open; });\n  const inp=$('#chT'), dl=$('#sgT');")
rep("if(M){ $('#thr').onclick=()=>{ $('#throne').scrollIntoView", "if(M){ $('#thr').onclick=()=>{ THOPEN=true; if($('#thx')) $('#thx').open=true; $('#throne').scrollIntoView")
rep("var TODAYF=null, TD=null;", "var TODAYF=null, TD=null, THOPEN=false;")
# 見つける：仲間図鑑と代表戦を1つの枠に
rep('<section id="zukan" class="card" hidden></section>\n  <section id="mine" class="card"><div class="sechead"><h2>あなたの代表戦</h2><span>誕生日・生まれた年・出身地。入れたい項目だけで、あなたの代表を探して戦わせる</span></div><div class="trow"><button type="button" class="btn" id="mineopen">自分の代表を探す</button></div></section>\n',
    '<section id="find" class="card"><div class="sechead"><h2>見つける</h2><span>Wikipediaに埋もれた記事を探して、戦わせる</span></div>\n    <div class="fgrid"><div id="zukan" hidden></div>\n    <div id="mine"><h3>あなたの代表戦</h3><p class="fsub">誕生日・生まれた年・出身地から、ゆかりのある人を代表に</p><div class="trow"><button type="button" class="btn" id="mineopen">自分の代表を探す</button></div></div></div></section>\n')
rep('z.innerHTML=`<div class="sechead"><h2>仲間図鑑</h2><span>Wikipediaのつながりから、埋もれた仲間を探す。記事カードの「仲間」からも開けます</span></div><div class="trow">',
    'z.innerHTML=`<h3>仲間図鑑</h3><p class="fsub">Wikipediaのつながりから、埋もれた仲間を探す。記事カードの「仲間」からも開けます</p><div class="trow">')
rep("#zukan,#mine,#today{padding:16px;display:flex;flex-direction:column;gap:12px}",
    "#today{padding:16px;display:flex;flex-direction:column;gap:12px}\n#today.tdload{min-height:240px}\n"
    "#find{padding:16px;display:flex;flex-direction:column;gap:12px}\n"
    "#find .fgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px 24px}\n"
    "@media (max-width:640px){#find .fgrid{grid-template-columns:1fr}}\n"
    "#zukan,#mine{display:flex;flex-direction:column;gap:8px;min-width:0}\n"
    "#zukan h3,#mine h3{margin:0;font-size:16px}#find .fsub{margin:0;font-size:12px;color:var(--muted)}\n"
    "#zukan .trow,#mine .trow{display:flex;flex-wrap:wrap;gap:8px;align-items:center}\n"
    "#throne .thx>summary{display:inline-block;margin-top:10px;padding:8px 14px;border:1px solid var(--ink);border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;list-style:none}\n"
    "#throne .thx>summary::-webkit-details-marker{display:none}\n"
    "#throne .thx>summary::after{content:' ▼';font-size:11px}#throne .thx[open]>summary::after{content:' ▲'}\n"
    "#throne .thx[open]>summary{margin-bottom:10px}")

# ---- 51. トップページの整理（続き）：自由対戦の能力値を2列に、VSを小さく、記録は一番下の注意書きとまとめる、説明文を短く ----
rep('<p class="lede">記事を2つ選ぶと、Wikidataに載っている事実だけで戦います。技の下の小さな文字が、その技の元になった事実です。</p>',
    '<p class="lede">勝敗も技も、記事に書かれた事実だけで決まります。まずは「今日の一戦」からどうぞ。</p>')
rep('  <div class="record card" style="padding:10px 14px" id="record"></div>\n', '')
rep('  <footer>\n', '  <footer>\n    <div class="record" id="record"></div>\n')
rep(".setup{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:start}",
    ".setup{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:start}\n"
    "@media (max-width:640px){.stats{grid-template-columns:auto 1fr auto auto 1fr auto!important;column-gap:8px!important}.vsmark{font-size:18px!important;margin:-6px 0}.matchup{display:none}}\n"   # スマホ：能力値は2つずつ横に、VSは小さく、カードと重なる「A vs B」の行は出さない   # スマホでは上下に並ぶので、VSは小さく、カードと重なる「A vs B」の行は出さない
    "footer .record{border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:6px}")
rep("<details class=\"mvs\"${WIDE()?' open':''}>", "<details class=\"mvs\">")   # 技の候補は、パソコンでも最初は畳む（自由対戦の枠が長くなりすぎるため）

# ---- 52. 仲間図鑑の入口を整える：今日の一門を1枚のカード（押すと開く）にし、「ほかの一門」は控えめな文字リンクに ----
rep('z.innerHTML=`<h3>仲間図鑑</h3><p class="fsub">Wikipediaのつながりから、埋もれた仲間を探す。記事カードの「仲間」からも開けます</p><div class="trow"><span class="tl">今日の一門</span><span class="today"></span><button type="button" class="btn small" id="famrnd">ほかの一門</button></div>`;',
    'z.innerHTML=`<h3>仲間図鑑</h3><p class="fsub">Wikipediaのつながりから、埋もれた仲間を探す</p><div class="today"></div><div class="frow"><button type="button" class="flink" id="famrnd">ほかの一門を見る</button><span class="fhint">記事カードの「仲間」からも開けます</span></div>`;')
rep("let k=hash('fam'+day); const draw=()=>{ const f=pickF(k); z.querySelector('.today').innerHTML=famChip({k:f[0][0],q:f[0].slice(1),n:f[1],c:f[2]},true); z.querySelector('[data-fam]').onclick=()=>openFam(f[0]); };",
    "let k=hash('fam'+day), other=false; const draw=()=>{ const f=pickF(k); const g={k:f[0][0],q:f[0].slice(1),n:f[1],c:f[2]};\n      z.querySelector('.today').innerHTML=`<button type=\"button\" class=\"famcard\" data-fam=\"${g.k}${esc(g.q)}\"><small>${other?'こんな一門も':'今日の一門'}</small><b>${esc(FAMK[g.k](g.n))}</b><span>${g.c}記事 ›</span></button>`; z.querySelector('[data-fam]').onclick=()=>openFam(f[0]); };")
rep("$('#famrnd').onclick=()=>{ k=Math.floor(Math.random()*1e9); draw(); }; }", "$('#famrnd').onclick=()=>{ k=Math.floor(Math.random()*1e9); other=true; draw(); }; }")
rep("#zukan h3,#mine h3{margin:0;font-size:16px}",
    "#zukan h3,#mine h3{margin:0;font-size:16px}\n"
    ".famcard{display:grid;grid-template-columns:1fr auto;grid-template-rows:auto auto;gap:2px 12px;align-items:center;width:100%;text-align:left;font:inherit;color:var(--ink);background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:10px 14px;cursor:pointer}\n"
    ".famcard:hover{border-color:var(--ink)}\n"
    ".famcard small{grid-column:1;font-size:11px;color:var(--muted)}\n"
    ".famcard b{grid-column:1;font-size:16px;line-height:1.35;overflow-wrap:anywhere}\n"
    ".famcard span{grid-column:2;grid-row:1/3;font-size:13px;color:var(--muted);white-space:nowrap}\n"
    "#zukan .frow{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}\n"
    ".flink{font:inherit;font-size:13px;background:none;border:none;padding:0;color:var(--ink);text-decoration:underline;text-underline-offset:3px;cursor:pointer}\n"
    "#zukan .fhint{font-size:11px;color:var(--muted)}\n"
    "@media (max-width:640px){#mine{border-top:1px solid var(--line);padding-top:14px;margin-top:4px}}")

# ---- 53. 実際に操作して見つけたところを直す ----
#  1. 試合の見出しを、どこから始めた試合かに合わせる（今日の一戦／仲間図鑑から／あなたの代表戦／自由対戦）
#  2. 今日の一戦の結果：共有文に勝者を書かない（見た人のネタバレになるため）。続けるボタンも今日の一戦向けに
#  3. 仲間図鑑・代表戦から始めた試合のあとに、元の画面へ戻るボタン
#  4. 記事名の候補リストが、入力欄から離れても残り、下の部品を押したつもりで候補を選んでしまう
#  5. 小さすぎる押し場所を広げる
rep("var TODAYF=null, TD=null, THOPEN=false;", "var TODAYF=null, TD=null, THOPEN=false, ORIG=null, MINE_LAST=null;")
rep("current={ai,bi,an,mode:MODE,today:TODAYF}; MODE=null; TODAYF=null;", "current={ai,bi,an,mode:MODE,today:TODAYF,orig:ORIG}; MODE=null; TODAYF=null; ORIG=null;")
rep("function ringHead(m){ if(!m) return '<div class=\"ringhead\">自由対戦</div>';",
    "function ringHead(m,c){ if(!m) return '<div class=\"ringhead\">'+(c&&c.today?'今日の一戦':c&&c.orig&&c.orig.k==='fam'?'仲間図鑑から':c&&c.orig&&c.orig.k==='mine'?'あなたの代表戦':'自由対戦')+'</div>';")
rep("${ringHead(current.mode)}", "${ringHead(current.mode,current)}")
# 今日の一戦の共有文（勝者は書かない）
rep("  share=fitPost(share)+'\\n'+DISC;\n  const SHAREURL=battleURL();",
    "  const TDY=current.today&&TD&&current.today.day===TD.day;\n"
    "  if(TDY){ const me=tdLoad()[TD.day]||{}; const wi=w===null?null:(w===TD.a?0:1); const hit=(me.p===0||me.p===1)&&me.p===wi; const st=tdStreak({...tdLoad(),[TD.day]:{...me,done:1,hit}});\n"
    "    share=`【百科拳典 今日の一戦 ${mdJ(TD.day)}】${F[TD.a][0]} vs ${F[TD.b][0]}`+(me.p===0||me.p===1?`\\n予想は${hit?'当たり！'+(st>1?`（${tdTitle(st)?tdTitle(st)+'・':''}${st}日連続）`:''):'外れ…'}`:'')+'\\nあなたはどっちが勝つと思う？'; }\n"
    "  share=fitPost(share)+'\\n'+DISC;\n  const SHAREURL=TDY?location.origin+'/?today=1':battleURL();")
rep("""    <div class="next">${M?`""",
    """    <div class="next">${TDY?`
      <button type="button" class="btn big" id="tdback">今日の一戦の星取表へ</button>
      <button type="button" class="btn" id="tofree">自由対戦で遊ぶ</button>`:M?`""")
rep("""      <button type="button" class="btn" id="back">選び直す</button>`}""",
    """      <button type="button" class="btn" id="back">選び直す</button>
      ${current.orig&&current.orig.k==='fam'?'<button type="button" class="btn" id="toorig">一門に戻る</button>':current.orig&&current.orig.k==='mine'?'<button type="button" class="btn" id="toorig">代表戦に戻る</button>':''}`}""")
rep("$('#tofree').onclick=()=>{ $('#setup').scrollIntoView({behavior:'smooth',block:'start'}); }; }",
    "$('#tofree').onclick=()=>{ $('#setup').scrollIntoView({behavior:'smooth',block:'start'}); }; }\n"
    "  if($('#tofree')&&!M) $('#tofree').onclick=()=>{ $('#setup').scrollIntoView({behavior:'smooth',block:'start'}); };\n"
    "  if($('#tdback')) $('#tdback').onclick=()=>{ const c=$('#today .tdcal'); if(c) c.open=true; $('#today').scrollIntoView({behavior:'smooth',block:'start'}); };\n"
    "  { const o=current.orig; if($('#toorig')&&o) $('#toorig').onclick=()=>o.k==='fam'?openFam(o.key):openMine(); }")
# 仲間図鑑・代表戦から始めたことを覚える
rep("$('#famset').onclick=()=>famApply(false); $('#famgo').onclick=()=>famApply(true);\n  famMark(); if(!dlg.open) dlg.showModal(); dlg.scrollTop=0; }",
    "$('#famset').onclick=()=>famApply(false); $('#famgo').onclick=()=>{ ORIG={k:'fam',key}; famApply(true); };\n  famMark(); if(!dlg.open) dlg.showModal(); dlg.scrollTop=0; }")
rep("      FP=[{t:r.x.t,n:r.x.n},{t:opp.t,n:opp.n}]; famApply(true); }; }",
    "      FP=[{t:r.x.t,n:r.x.n},{t:opp.t,n:opp.n}]; ORIG={k:'mine'}; famApply(true); }; }")
rep("if(go&&sel[0]!==null&&sel[1]!==null) startBattle(); else $('#setup').scrollIntoView({behavior:'smooth',block:'start'}); }", "if(go&&sel[0]!==null&&sel[1]!==null) startBattle(); else $('#setup').scrollIntoView({behavior:'smooth',block:'start'}); ORIG=null; }")
# 代表戦に戻ったとき、覚えない設定でも直前の入力で結果を出し直す
rep("function openMine(){ const dlg=$('#famdlg'); if(!dlg) return; const sv=mineLoad(); const o=sv||{};",
    "function openMine(){ const dlg=$('#famdlg'); if(!dlg) return; const sv=mineLoad(); const o=sv||MINE_LAST||{};")
rep("if(!dlg.open) dlg.showModal(); dlg.scrollTop=0; if(sv) run();", "if(!dlg.open) dlg.showModal(); dlg.scrollTop=0; if(sv||MINE_LAST) run();")
rep("async function run(){ const my=++seq; const v=cur(); keep();", "async function run(){ const my=++seq; const v=cur(); keep(); MINE_LAST=v;")
# 今日の一戦の当たり外れは、結果の枠の中の一番上に
s = s.replace("res.prepend(n); } }", "(res.querySelector('.result')||res).prepend(n); } }", 1)
# 候補リスト：入力欄が画面から外れたら閉じる。リストと入力欄の外を触ったら閉じる
rep("async function famToday(){", r"""function sgClose(except){ document.querySelectorAll('ul.sg:not([hidden]),ul.msug:not([hidden])').forEach(ul=>{ if(except&&ul.parentElement.contains(except)) return; ul.hidden=true; const i=ul.parentElement.querySelector('input'); if(i) i.setAttribute('aria-expanded','false'); }); }
addEventListener('scroll',()=>{ document.querySelectorAll('ul.sg:not([hidden])').forEach(ul=>{ const i=ul.parentElement.querySelector('input'); if(!i) return; const r=i.getBoundingClientRect(); if(r.bottom<0||r.top>innerHeight) sgClose(); }); },{passive:true});
document.addEventListener('pointerdown',e=>{ if(!e.target.closest('.sgw')) sgClose(); },true);
async function famToday(){""")
# 押し場所を広げる（見た目の大きさはほぼ変えない）
rep(".fname a{font-size:12px;color:var(--muted)}", ".fname a{font-size:12px;color:var(--muted);padding:10px 6px;margin:-10px -6px}")
rep(".result{padding:16px;display:flex;flex-direction:column;gap:10px;background:var(--ink);color:var(--bg);border-radius:6px}",
    ".result{padding:16px;display:flex;flex-direction:column;gap:10px;background:var(--ink);color:var(--bg);border-radius:6px}\n"
    ".result .tdnote{margin:0;background:var(--hl);color:var(--ink);font-weight:700}\n"
    "#res .result{scroll-margin-top:120px}\n"
    "#today .mlink,#today .tdcal>summary,.flink{padding:10px 6px;margin:-4px -6px}\n"
    "#throne details details>summary{padding:8px 0}")

# ---- 54. 王座戦の説明を短くし、入力欄を先に出す（決まりは入力欄の下に1行で） ----
rep('<div class="meta">この王者を倒せる記事を、約140万記事の中から探してください。勝てば王座はあなたの記事のもの。結果は何度やっても同じなので、一度王座戦で戦った組み合わせは、もう戦えません。</div>', '')
rep('<button type="submit" class="btn" disabled>挑戦する</button></form>',
    '<button type="submit" class="btn" disabled>挑戦する</button></form>\n  <div class="meta thn">勝てば、あなたの記事が次の王者。同じ組み合わせで挑めるのは1回だけです。</div>')
rep(".meta{font-size:13px;color:var(--muted)}", ".meta{font-size:13px;color:var(--muted)}\n#throne .thn{font-size:12px;margin-top:6px}")

# ---- 55. 試合後に「この試合で分かったこと」：勝負を決めた事実を2〜3個、出どころと時点を添えて並べる（勝敗は変えない） ----
rep("const n=pick.length%2?pick.length:pick.length-1; const Q=pick.slice(0,n);", "const n=pick.length%2?pick.length:pick.length-1; const Q=pick.slice(0,n); an.kq=Q.map(x=>({...x,ia:ai,ib:bi}));")
rep("const key=decW.find(d=>d.who===w);", r"""const key=decW.find(d=>d.who===w);
  // この試合で分かったこと：試合で実際に使われた事実だけを、記録どおりの書き方で出す（言い換えたり、推し量ったりしない）
  // 記事そのものの数字（文字数・閲覧数・カテゴリやリンクの数・作成日など）は、読んでも知識が増えないので出さない。対象そのものについての事実だけ
  const META_MV=new Set(['文字数マウント','人脈マウント','閲覧数マウント','カテゴリ数マウント','見出し数マウント','画像数マウント','リンク数マウント','長文で殴る','リンク網','注目の視線','カテゴリ包囲','見出し連打','リンク乱打','画像攻撃','外部リンク渡り','要出典','書きかけ指摘','古参の貫禄','分身の術','名前で殴る','百科事典の権威','事典掲載マウント','肩書きマウント']);   // 数だけで中身の分からないもの（載っている事典の数・肩書きの数）も出さない
  const facts=(()=>{ const nm=i=>F[i][0]; const out=[], seen=new Set(), per={};
    const add=(who,t,cap)=>{ t=String(t||'').trim(); if(!t||seen.has(t)) return false; if(who!==null&&(per[who]||0)>=(cap||2)) return false; seen.add(t); out.push({who,t}); if(who!==null) per[who]=(per[who]||0)+1; return true; };
    // 1. 試合で使われた比べ（どちらの数字かを書く）。比べ合いの数字は、計算したときの左右（ia/ib）で名前を付ける。画面の左右と逆のことがあるため
    if(an.kq) an.kq.filter(x=>!['_sl','_pv','_ch','P106','P1343'].includes(x.k)).slice(0,2).forEach(x=>add(null,(RLAB[x.k]||x.k)+'：'+nm(x.ia)+' '+fmtR(x.k,x.a)+' ／ '+nm(x.ib)+' '+fmtR(x.k,x.b)));
    else for(const x of r.log){ if(!x.mv||x.side<0||!(x.d>0)||META_MV.has(x.mv[1])||!x.mv[3]) continue; const me=x.side===0?ai:bi, op=x.side===0?bi:ai; const t=x.mv[3];
      if(/^相手の/.test(t)) continue;
      const c=t.match(/^(.+?)：(.+) 対 (.+)$/); if(c&&out.filter(o=>o.who===null).length<1) add(null,c[1]+'：'+nm(me)+' '+c[2]+' ／ '+nm(op)+' '+c[3]); }
    // 2. それぞれの記事の、対象そのものについての事実（技の候補全体から、中身の分かるものを順番に）
    const pri=m=>{ const t=m[3]||''; if(META_MV.has(m[1])&&m[1]!=='カテゴリ包囲') return 99; if(/^\S*\d[\d,]*件$/.test(t)) return 99;   // 「登録作品13件」のように数だけのものは出さない
      if(/^職業：/.test(t)) return 1; if(/^(生まれた場所|所在地|活動地)：/.test(t)) return 2; if(/^受賞：/.test(t)) return 3; if(/^(主要作品|代表作)/.test(t)) return 4;
      if(/^所属/.test(t)) return 5; if(/^(生みの親|名前の由来|着想を得たもの|元ネタ)：/.test(t)) return 6; if(PLAIN.some(p=>p[1]===m[1])) return 7; if(/^構成要素：/.test(t)) return 8;
      if(m[1]==='カテゴリ包囲') return /（.+など）/.test(t)?9:99; if(m[0]==='SENIORITY') return 10; if(/^Wikidataでの分類：ヒト$/.test(t)) return 99; if(m[0]==='NAME'||/：.*対/.test(t)) return 99; return 8.5; };
    const prof=i=>(POOL[i]||[]).map(m=>({m,p:pri(m)})).filter(o=>o.p<99).sort((x,y)=>x.p-y.p).map(o=>{ const t=o.m[3];
      if(o.m[1]==='カテゴリ包囲'){ const c=t.match(/（(.+?)など）/); return c?'カテゴリ：'+c[1]:''; }
      // 場所は、名前だけだと分かりにくいことがある（「7区」など）。Wikidataの説明文を添える（「日本の都道府県」「〜の国」のように自明なものは省く）
      const pl=t.match(/^(所在地|活動地|生まれた場所)：(.+)$/), tg=Array.isArray(o.m[7])&&o.m[7][0];
      if(pl&&tg&&tg[0]===pl[2]&&tg[1]&&!/[都道府県国]$/.test(pl[2])&&!/^(日本の都道府県|.*の国|国|都市|市)$/.test(tg[1])) return t+'（'+tg[1]+'）'; return t; });
    const A=prof(ai), B=prof(bi); A.slice(0,4).forEach(t=>add(ai,t)); B.slice(0,4).forEach(t=>add(bi,t));   // 1記事2つまで（add の上限）
    return out; })();
  const ASOF=((document.querySelector('footer')||{}).textContent||'').match(/(\d{4}年\d+月\d+日)時点/);""")
rep('<div class="reads"><span>記事を読む</span>',
    """${facts.length?`<div class="facts"><div class="fh">2つの記事から分かること</div>${(()=>{ const cmp=facts.filter(f=>f.who===null), by=[ai,bi].map(i=>({i,L:facts.filter(f=>f.who===i)})).filter(g=>g.L.length);   // 比べは先に、あとは記事ごとにまとめる
      return (cmp.length?`<ul>${cmp.map(f=>`<li>${esc(f.t)}</li>`).join('')}</ul>`:'')+by.map(g=>`<div class="fwho">${esc(F[g.i][0])}</div><ul>${g.L.map(f=>`<li>${esc(f.t)}</li>`).join('')}</ul>`).join(''); })()}<div class="fsrc">Wikidataと日本語版Wikipediaの記録${ASOF?'（'+ASOF[1]+'時点）':''}より。</div></div>`:''}
    <div class="reads"><span>記事を読む</span>""")
rep(".reads{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;font-size:13px}",
    ".reads{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;font-size:13px}\n"
    ".facts{border:1px solid rgba(255,255,255,.18);border-radius:8px;padding:10px 12px}\n"
    ".facts .fh{font-weight:700;font-size:14px}\n"
    ".facts ul{margin:6px 0 0;padding-left:1.2em;font-size:14px;line-height:1.7;overflow-wrap:anywhere}\n"
    ".facts .fwho{font-weight:700;font-size:13px;margin-top:8px}.facts .fwho+ul{margin-top:2px}\n"
    ".facts .fsrc{font-size:11px;opacity:.7;margin-top:6px;line-height:1.5}")

# ---- 56. 数値の訂正表（data/fix.json）：Wikidata の明らかな誤りを、出どころを確かめたうえで百科拳典の側で直す ----
#   書き方：{"記事名": {"標高": 3776.12, "出典": "…", "確認日": "YYYY-MM-DD"}}。数字の項目名は FIXK のもの
#   記事を読み込むとき（register）に、収録データの数字（qt）を上書きする。技の説明文（「標高◯m」）も、この数字から作り直される
rep("function register(rec){ const t=rec.f[1];", r"""const FIXK={'標高':'e','高さ':'h','重さ':'m','面積':'a','人口':'p','長さ':'l','深さ':'d','速さ':'s'};
let FIX=null, FIXP=null;
function fixLoad(){ if(FIX) return Promise.resolve(); return FIXP||(FIXP=fetch('data/fix.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{}).then(o=>{ FIX=o||{}; }).catch(()=>{ FIX={}; })); }
function register(rec){ const t=rec.f[1];
  { const fx=FIX&&FIX[t]; if(fx){ rec.qt={...(rec.qt||{})}; for(const [k,v] of Object.entries(fx)) if(FIXK[k]&&typeof v==='number') rec.qt[FIXK[k]]=v; } }""")
rep("async function loadTitle(t){ t=String(t||'').trim(); if(!t) return -1;", "async function loadTitle(t){ await fixLoad(); t=String(t||'').trim(); if(!t) return -1;")

# ---- 57. 報告をページの中で受け付ける（GitHubのアカウントがなくても送れる）。送り先は百科拳典のサーバー（/api/report） ----
#   送る人の手間を減らす：
#     数字や事実の誤り … 「2つの記事から分かること」の下の「違う点を知らせる」→ 行を押す。どの記事のどの事実かは自動で入る（正しい値・出典は任意）
#     不適切な内容      … 同じ場所の「不適切な内容を知らせる」→ どれについてか → 理由を押すと送る（ひとことは任意）
#   管理者の手間を減らす：何を何に直すかが分かる形で送る（記事・項目・いまの値・正しい値）
# 1. 事実に、報告用の中身（記事・項目・いまの値）を持たせる
rep("const add=(who,t,cap)=>{ t=String(t||'').trim(); if(!t||seen.has(t)) return false; if(who!==null&&(per[who]||0)>=(cap||2)) return false; seen.add(t); out.push({who,t});",
    "const add=(who,t,cap,rp)=>{ t=String(t||'').trim(); if(!t||seen.has(t)) return false; if(who!==null&&(per[who]||0)>=(cap||2)) return false; seen.add(t); out.push({who,t,rp});")
rep("forEach(x=>add(null,(RLAB[x.k]||x.k)+'：'+nm(x.ia)+' '+fmtR(x.k,x.a)+' ／ '+nm(x.ib)+' '+fmtR(x.k,x.b)));",
    "forEach(x=>add(null,(RLAB[x.k]||x.k)+'：'+nm(x.ia)+' '+fmtR(x.k,x.a)+' ／ '+nm(x.ib)+' '+fmtR(x.k,x.b),0,{k:RLAB[x.k]||x.k,it:[{t:F[x.ia][1],n:nm(x.ia),v:fmtR(x.k,x.a)},{t:F[x.ib][1],n:nm(x.ib),v:fmtR(x.k,x.b)}]}));")
rep("add(null,c[1]+'：'+nm(me)+' '+c[2]+' ／ '+nm(op)+' '+c[3]); }",
    "add(null,c[1]+'：'+nm(me)+' '+c[2]+' ／ '+nm(op)+' '+c[3],0,{k:c[1],it:[{t:F[me][1],n:nm(me),v:c[2]},{t:F[op][1],n:nm(op),v:c[3]}]}); }")
rep("A.slice(0,4).forEach(t=>add(ai,t)); B.slice(0,4).forEach(t=>add(bi,t));",
    "const rp1=(i,t)=>{ const m=t.match(/^(.+?)：(.+)$/); return {k:m?m[1]:'',it:[{t:F[i][1],n:nm(i),v:m?m[2]:t}]}; };\n"
    "    A.slice(0,4).forEach(t=>add(ai,t,2,rp1(ai,t))); B.slice(0,4).forEach(t=>add(bi,t,2,rp1(bi,t)));")
# 2. 行には目印を出さず、押せるようにする目印（data-fi）だけ
rep("  const ASOF=((document.querySelector('footer')", "  const fxa=f=>API&&f.rp?' data-fi=\"'+facts.indexOf(f)+'\"':'';\n  const ASOF=((document.querySelector('footer')")
rep("return (cmp.length?`<ul>${cmp.map(f=>`<li>${esc(f.t)}</li>`).join('')}</ul>`:'')+by.map(g=>`<div class=\"fwho\">${esc(F[g.i][0])}</div><ul>${g.L.map(f=>`<li>${esc(f.t)}</li>`).join('')}</ul>`).join('');",
    "return (cmp.length?`<ul>${cmp.map(f=>`<li${fxa(f)}>${esc(f.t)}</li>`).join('')}</ul>`:'')+by.map(g=>`<div class=\"fwho\">${esc(F[g.i][0])}</div><ul>${g.L.map(f=>`<li${fxa(f)}>${esc(f.t)}</li>`).join('')}</ul>`).join('');")
rep("時点）':''}より。</div></div>", "時点）':''}より。${API&&facts.some(f=>f.rp)?'<button type=\"button\" class=\"fxgo\" aria-pressed=\"false\">違う点を知らせる</button>':''}${API?'<button type=\"button\" class=\"fxbad\">不適切な内容を知らせる</button>':''}</div><div class=\"fxhint\" hidden>違うと思う行を押してください</div><div class=\"fxmsg\" aria-live=\"polite\"></div></div>")
# 事実がひとつもない試合でも、知らせる入口は出す
rep("${facts.length?`<div class=\"facts\"><div class=\"fh\">2つの記事から分かること</div>", "${facts.length||API?`<div class=\"facts\">${facts.length?'<div class=\"fh\">2つの記事から分かること</div>':''}")
# 3. 送る枠（1つの枠を、押した場所の近くに動かして使う）
rep('<div class="report" style="margin-top:10px"><span>この対戦の内容が不適切だと思ったら知らせる：</span><button type="button" data-rep="a">${esc(F[ai][0])}の記事</button><button type="button" data-rep="b">${esc(F[bi][0])}の記事</button><button type="button" data-rep="text">対戦の文面</button><span id="repmsg" aria-live="polite"></span></div>`;',
    '''  <form class="repf" id="repf" hidden novalidate>
    <div class="rhd" id="rphd"></div>
    <div class="rchips" id="rpside" hidden></div>
    <div class="rnum" id="rpnum" hidden>
      <input id="rpfix" maxlength="60" autocomplete="off" placeholder="正しい値（分かれば）" aria-label="正しい値（分かれば）">
      <input id="rpu" type="url" inputmode="url" maxlength="300" autocomplete="off" placeholder="出典のURL（分かれば）" aria-label="出典のURL（分かれば）">
      <div class="rgo"><button type="submit" class="btn small" id="rpgo">送る</button><button type="button" class="btn small rpx">やめる</button></div>
    </div>
    <div class="rbad" id="rpbad" hidden>
      <textarea id="rptx" maxlength="200" rows="2" placeholder="ひとこと（任意）" aria-label="ひとこと（任意）"></textarea>
      <div class="rlab">理由を押すと送ります</div>
      <div class="rchips"><button type="button" data-rr="fact">数字や事実が違う</button><button type="button" data-rr="dis">差別的・攻撃的</button><button type="button" data-rr="subj">扱いがふさわしくない題材</button><button type="button" data-rr="other">その他</button></div>
      <div class="rgo"><button type="button" class="btn small rpx">やめる</button></div>
    </div>
    <input id="rphp" name="website" class="rhp" tabindex="-1" autocomplete="off" aria-hidden="true">
    <div class="rerr" id="rperr" aria-live="polite"></div>
    <div class="rnote">送られるのは、この報告の内容と、続けて送られるのを防ぐための回線・ブラウザの番号（元に戻せない形に変えて保存）です。見るのは管理者だけです。</div>
  </form>`;''')
rep("""  document.querySelectorAll('[data-rep]').forEach(btn=>btn.onclick=()=>{ const kind=btn.dataset.rep;
    const tgt=kind==='a'?F[ai][0]:kind==='b'?F[bi][0]:F[ai][0]+' 対 '+F[bi][0];
    const title=(kind==='text'?'【文面】':'【記事】')+tgt;
    const body='対戦：'+F[ai][0]+' 対 '+F[bi][0]+'\\n対象：'+(kind==='text'?'実況の文面':tgt+'の記事')+'\\n\\n気になった点（任意）：\\n';
    window.open('https://github.com/y-krn/hyakka-kenten/issues/new?labels=report&title='+encodeURIComponent(title)+'&body='+encodeURIComponent(body),'_blank','noopener');
    $('#repmsg').textContent='GitHubの報告ページを開きました（GitHubのアカウントが必要です）。確認して、必要なら収録から外します。'; });""",
    r"""  { const f=$('#repf'), msg=$('#res .fxmsg'), err=$('#rperr'), bad=$('#res .fxbad'); let st=null, t0=0;
    const all=()=>document.querySelectorAll('#res .facts li[data-fi],#res .fxbad'), fb=$('#res .facts'), go=$('#res .fxgo');
    // 「違う点を知らせる」を押すと、事実の行が押せるようになる（ふだんは行に何も出さない）
    const pick=on=>{ if(!fb) return; fb.classList.toggle('pick',on); if(go){ go.textContent=on?'やめる':'違う点を知らせる'; go.setAttribute('aria-pressed',on); } fb.querySelector('.fxhint').hidden=!on;
      fb.querySelectorAll('li[data-fi]').forEach(li=>{ if(on&&!li.dataset.done){ li.tabIndex=0; li.setAttribute('role','button'); } else { li.removeAttribute('tabindex'); li.removeAttribute('role'); } }); };
    const close=()=>{ f.hidden=true; const was=st&&st.mode==='num'; st=null; all().forEach(x=>x.classList.remove('on')); if(was) pick(false); };
    if(go) go.onclick=()=>{ const on=!fb.classList.contains('pick'); if(st){ f.hidden=true; st=null; all().forEach(x=>x.classList.remove('on')); } pick(on); };
    const open=(s,btn,where)=>{ st=s; t0=Date.now(); err.textContent=''; msg.textContent=''; all().forEach(x=>x.classList.toggle('on',x===btn));
      where.after(f); f.hidden=false; $('#rpnum').hidden=s.mode!=='num'; $('#rpbad').hidden=s.mode!=='bad';
      f.querySelector('[data-rr="subj"]').hidden=s.target==='text';   // 実況の文面には「題材」は当てはまらない
      f.scrollIntoView({behavior:'smooth',block:'nearest'}); };
    // 事実の行の「違う？」：どの記事のどの事実かは、こちらで入れる
    const pickLine=btn=>{ if(!fb.classList.contains('pick')||btn.dataset.done) return; const fc=facts[+btn.dataset.fi]; if(!fc||!fc.rp) return; const rp=fc.rp;
      if(st&&st.btn===btn){ f.hidden=true; st=null; btn.classList.remove('on'); return; }
      open({mode:'num',btn,rp,side:rp.it.length===1?0:null},btn,btn.closest('ul'));
      const side=$('#rpside'), hd=$('#rphd');
      const head=()=>{ const it=st.side===null?null:rp.it[st.side]; hd.textContent=it?'「違う」と知らせる：'+it.n+'の'+(rp.k?rp.k+' ':'')+it.v:'どちらの数字が違いますか？'; };
      side.hidden=rp.it.length<2; side.innerHTML=rp.it.length<2?'':rp.it.map((it,k)=>`<button type="button" data-sd="${k}">${esc(it.n)}　${esc(it.v)}</button>`).join('');
      side.querySelectorAll('[data-sd]').forEach(b=>b.onclick=()=>{ st.side=+b.dataset.sd; side.querySelectorAll('[data-sd]').forEach(x=>x.classList.toggle('on',x===b)); err.textContent=''; head(); $('#rpfix').focus({preventScroll:true}); });
      $('#rpfix').value=''; $('#rpu').value=''; head(); };
    document.querySelectorAll('#res .facts li[data-fi]').forEach(li=>{ li.onclick=()=>pickLine(li); li.onkeydown=e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); pickLine(li); } }; });
    // 下の「気になる点を知らせる」：どれについてかを選ぶと、理由のボタンが出る（押すと送る）
    if(bad) bad.onclick=()=>{ if(st&&st.mode==='bad'){ close(); return; } if(st) close(); pick(false);
      open({mode:'bad',btn:bad,target:null},bad,fb.querySelector('.fsrc')); const side=$('#rpside'); side.hidden=false;
      side.innerHTML=[['a',F[ai][0]+'の記事'],['b',F[bi][0]+'の記事'],['text','実況の文面']].map(([k,t])=>`<button type="button" data-tg="${k}">${esc(t)}</button>`).join('');
      side.querySelectorAll('[data-tg]').forEach(b=>b.onclick=()=>{ st.target=b.dataset.tg; side.querySelectorAll('[data-tg]').forEach(x=>x.classList.toggle('on',x===b)); f.querySelector('[data-rr="subj"]').hidden=st.target==='text'; err.textContent=''; });
      $('#rphd').textContent='どれについてですか？'; $('#rptx').value=''; };
    f.querySelectorAll('.rpx').forEach(b=>b.onclick=close);
    const send=async body=>{ const bs=f.querySelectorAll('button'); bs.forEach(b=>b.disabled=true); err.textContent='送っています…';
      await new Promise(r=>setTimeout(r,Math.max(0,900-(Date.now()-t0))));   // 開いてすぐ（機械的な送信）と見分けるため、少しだけ待つ
      try{ const r=await fetch(API+'/api/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,a:F[ai][1],b:F[bi][1],hp:$('#rphp').value,ms:Date.now()-t0,client:clientId()})});
        const d=await r.json().catch(()=>({}));
        if(r.ok&&d.ok){ const b=st.btn, m=st.mode; close(); const ok=d.dup?'同じ報告を受け付け済みです':'受け付けました。ありがとうございます';
          if(m==='num'){ b.dataset.done=1; b.classList.add('done'); b.insertAdjacentHTML('beforeend','<span class="fxok">　'+(d.dup?'受け付け済み':'受け付けました')+'</span>'); } else { msg.textContent=ok+'。確かめたうえで対応します。'; if(bad) bad.disabled=true; } err.textContent=''; }
        else err.textContent=d.error||'送れませんでした。時間をおいてもう一度お願いします。'; }
      catch(_){ err.textContent='送れませんでした。通信の状態を確かめてください。'; }
      bs.forEach(b=>b.disabled=false); };
    f.onsubmit=e=>{ e.preventDefault(); if(!st||st.mode!=='num') return; if(st.side===null){ err.textContent='どちらの数字かを選んでください'; return; }
      const it=st.rp.it[st.side]; send({kind:'num',reason:'fact',target:it.t===F[ai][1]?'a':'b',fact:{n:it.t,k:st.rp.k,v:it.v},fix:$('#rpfix').value,url:$('#rpu').value}); };
    f.querySelectorAll('[data-rr]').forEach(b=>b.onclick=()=>{ if(!st||st.mode!=='bad') return; const rr=b.dataset.rr, tx=$('#rptx').value.trim(); if(!st.target){ err.textContent='どれについてかを選んでください'; return; }
      if(rr==='fact'&&!tx){ err.textContent='どこが違うか、ひとこと書いてから押してください（記事の事実は「2つの記事から分かること」の「違う？」からも送れます）'; $('#rptx').focus(); return; }
      send({kind:rr==='fact'?'num':'bad',reason:rr,target:st.target,text:tx}); }); }""")
rep(".report button{all:unset;cursor:pointer;text-decoration:underline}",
    ".report button{all:unset;cursor:pointer;text-decoration:underline;padding:6px 2px}\n.report button.on{color:var(--ink);font-weight:700}.report button:disabled{opacity:.5;cursor:default}\n"
    ".facts .fxgo,.facts .fxbad{all:unset;cursor:pointer;text-decoration:underline;padding:8px 4px;margin:-8px 0 -8px 4px;white-space:nowrap}.facts .fxbad:disabled{opacity:.5;cursor:default}\n"
    ".facts .fxmsg{font-size:12px;margin-top:6px}.facts .fxmsg:empty{display:none}\n"
    ".facts .fxhint{font-size:12px;font-weight:700;margin-top:6px}\n"
    ".facts.pick li[data-fi]:not([data-done]){cursor:pointer;text-decoration:underline dashed;text-underline-offset:4px}\n"
    ".facts.pick li[data-fi].on{text-decoration:underline solid}\n"
    ".facts li .fxok{font-size:12px;opacity:.7}\n"
    ".repf{margin-top:6px;display:flex;flex-direction:column;gap:8px;padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink)}\n"
    ".facts .repf{margin:8px 0 4px}.result .repf .btn{border-color:var(--ink);color:var(--ink);background:var(--paper)}.result .repf .btn:hover{background:var(--ink);color:var(--paper)}\n"
    ".repf .rhd{font-size:14px;font-weight:700;overflow-wrap:anywhere}\n"
    ".repf .rnum,.repf .rbad{display:flex;flex-direction:column;gap:8px}\n"
    ".repf textarea,.repf input{font:inherit;font-size:16px;padding:6px 8px;border:1px solid var(--line);border-radius:8px;background:var(--paper);color:var(--ink);box-sizing:border-box;width:100%}\n"
    ".repf textarea{resize:vertical}\n"
    ".repf .rchips{display:flex;flex-wrap:wrap;gap:8px}\n"
    ".repf .rchips button{font:inherit;font-size:14px;padding:9px 12px;border:1px solid var(--ink);border-radius:999px;background:var(--paper);color:var(--ink);cursor:pointer}\n"
    ".repf .rchips button.on{background:var(--ink);color:var(--paper)}.repf .rchips button:disabled{opacity:.5}\n"
    ".repf .rlab{font-size:12px;color:var(--muted)}\n"
    ".repf .rhp{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}\n"
    ".repf .rgo{display:flex;gap:8px;align-items:center;flex-wrap:wrap}\n"
    ".repf .rerr{font-size:13px;color:var(--ink)}.repf .rerr:empty{display:none}\n"
    ".repf .rnote{font-size:11px;color:var(--muted)}\n"
    ".repf[hidden],.repf [hidden]{display:none!important}")
# 4. 違う回線の2人以上から「内容が不適切」と知らされた記事は、確かめるまで今日の一戦とランダムに出さない（サーバーの /api/holds）
rep("async function todayPair(day){ const nr=await fetch('data/norand.json?v='+VER).then(r=>r.ok?r.json():[]).then(a=>new Set(a)).catch(()=>new Set());",
    "let HOLDS=null; function holdsGet(){ return HOLDS||(HOLDS=API?fetch(API+'/api/holds').then(r=>r.ok?r.json():{}).then(o=>Array.isArray(o.titles)?o.titles:[]).catch(()=>[]):Promise.resolve([])); }\n"
    "async function todayPair(day){ const nr=await Promise.all([fetch('data/norand.json?v='+VER).then(r=>r.ok?r.json():[]).catch(()=>[]),holdsGet()]).then(([a,h])=>new Set([...a,...h]));")
rep("const nrP=fetch('data/norand.json?v='+VER).then(r=>r.ok?r.json():[]).then(a=>{ NORAND=new Set(a); }).catch(()=>{});",
    "const nrP=Promise.all([fetch('data/norand.json?v='+VER).then(r=>r.ok?r.json():[]).catch(()=>[]),holdsGet()]).then(([a,h])=>{ NORAND=new Set([...a,...h]); }).catch(()=>{});")

# ---- 58. 結果の枠を短く：勝ち方・残りHP・「能力値だけなら」の行はやめる（試合の経過と「番狂わせ」の札で分かる）。連勝中だけ残す ----
rep("""<div class="sub">${w===null?'':esc(how)+(r.kind==='比べ合い'?'':'　／　残りHP '+wHP)}${upset?`　／　能力値だけなら${an.baseW===null?'引き分けの':esc(nm(an.baseW))+'が勝つ'}組み合わせ`:''}${streak.n>=2?`　／　${esc(F[w][0])} ${streak.n}連勝中`:''}</div>""",
    """${w!==null&&streak.n>=2?`<div class="sub">${esc(F[w][0])} ${streak.n}連勝中</div>`:''}""")

# ---- 59. 訂正表で、誤った数字を「消す」こともできるように（値を null にする）。末尾の説明を実際の扱いに合わせる ----
rep("for(const [k,v] of Object.entries(fx)) if(FIXK[k]&&typeof v==='number') rec.qt[FIXK[k]]=v; } }",
    "const PN={e:'標高落とし',h:'急降下',m:'のしかかり',a:'領土拡大',p:'人海戦術',l:'全長包囲',d:'深淵送り'};\n"
    "    for(const [k,v] of Object.entries(fx)){ const q=FIXK[k]; if(!q) continue; if(typeof v==='number'&&v>0) rec.qt[q]=v; else if(v===null||typeof v==='number'){ delete rec.qt[q]; rec.f=rec.f.slice(); rec.f[7]=(rec.f[7]||[]).filter(m=>m[1]!==PN[q]); } } } }")
rep("Wikidataと日本語版の記事で数値が食い違うものは日本語版に合わせています。", "Wikidataの数値に誤りが見つかったものは、日本語版の記事などで確かめて直しています。")

# ---- 60. 自動の訂正表（data/fixa/<番号>.json）：日本語版の情報欄から確実に読めた数字に合わせる（tools/check/numcheck.mjs で作る）。手で書く訂正表（fix.json）のほうが優先 ----
#   記事ごとに必要な分だけ読む（256に分けてある）。書き方は fix.json と同じ {"記事名": {"人口": 32862000}}
rep("function register(rec){ const t=rec.f[1];", """const FXNB=256, FXA={}, FXAP={};
function fixAuto(t){ const k=fnv(t)%FXNB; return FXAP[k]||(FXAP[k]=fetch('data/fixa/'+k+'.json').then(r=>r.ok?r.json():{}).catch(()=>({})).then(o=>{ Object.assign(FXA,o); })); }
function register(rec){ const t=rec.f[1];""")
rep("{ const fx=FIX&&FIX[t]; if(fx){", "{ const fx=(FIX&&FIX[t])||FXA[t]; if(fx){")
rep("async function loadTitle(t){ await fixLoad(); t=String(t||'').trim();", "async function loadTitle(t){ t=String(t||'').trim(); await Promise.all([fixLoad(),t?fixAuto(t):0]);")

# ---- 61. 「埋もれた」をやめる（記事を書いた人やファンにとって、見下されたように読める）。選ばれ方をそのまま書く ----
rep('<small>埋もれた記事</small>', '<small>ランダムな記事</small>')
rep('<span>Wikipediaに埋もれた記事を探して、戦わせる</span>', '<span>Wikipediaの中から、まだ知らない記事を探して、戦わせる</span>')
rep('<p class="fsub">Wikipediaのつながりから、埋もれた仲間を探す</p>', '<p class="fsub">Wikipediaのつながりから、意外な仲間を探す</p>')
s = s.replace('収録記事からくじ引きした「埋もれた記事」', '収録記事からランダムに選んだ記事')

# ---- 62. みんなの対戦数を、遊び方ごとにも数える（今日の一戦 t・あなたの代表戦 m・仲間図鑑から f。残りが自由対戦）。週間レポートに出す ----
rep("function addPlay(){ setPend(pend()+1);", """const PENDK_KEY='hk-plays-k';
function pendK(){ try{ const o=JSON.parse(localStorage.getItem(PENDK_KEY)||'{}'); return o&&typeof o==='object'?o:{}; }catch(_){ return {}; } }
function setPendK(o){ try{ localStorage.setItem(PENDK_KEY,JSON.stringify(o)); }catch(_){} }
function addPlay(){ setPend(pend()+1); { const c=current||{}, k=c.today?'t':c.orig&&c.orig.k==='mine'?'m':c.orig&&c.orig.k==='fam'?'f':''; if(k){ const o=pendK(); o[k]=(o[k]||0)+1; setPendK(o); } }""")
rep("function flushPlays(beacon){ const n=Math.min(30,pend()); if(!n||!API) return; const body=JSON.stringify({n,client:clientId()}); let ok=false;",
    "function flushPlays(beacon){ const n=Math.min(30,pend()); if(!n||!API) return; const o=pendK(), k={}; let left=n; for(const x of ['t','m','f']){ const v=Math.min(left,Math.max(0,o[x]|0)); if(v){ k[x]=v; left-=v; } }\n  const body=JSON.stringify({n,k,client:clientId()}); let ok=false;")
rep("  if(ok) setPend(pend()-n); }", "  if(ok){ setPend(pend()-n); const o2=pendK(); for(const x in k) o2[x]=Math.max(0,(o2[x]|0)-k[x]); setPendK(o2); } }")

# ---- 63. 訂正表で「職業」も直せるように（文字。null で職業そのものを出さない）。例：NMB48 は Wikidata で職業が「著作家」になっている ----
rep("    for(const [k,v] of Object.entries(fx)){ const q=FIXK[k]; if(!q) continue;",
    "    if('職業' in fx&&rec.gen){ rec.gen={...rec.gen}; if(typeof fx['職業']==='string'&&fx['職業']) rec.gen.job=fx['職業']; else delete rec.gen.job; }\n    for(const [k,v] of Object.entries(fx)){ const q=FIXK[k]; if(!q) continue;")

# ---- 64. 自動の訂正表の「主要作品」：作品の記事がよく読まれている順に選び直した先頭2件で、Wikidata の登録順の2件を置き換える。手の訂正表とは項目ごとに合わせる ----
rep("{ const fx=(FIX&&FIX[t])||FXA[t]; if(fx){", "{ const fx=(FIX&&FIX[t])||FXA[t]?{...(FXA[t]||{}),...((FIX&&FIX[t])||{})}:null; if(fx){")
rep("    if('職業' in fx&&rec.gen){", "    if(Array.isArray(fx['主要作品'])&&fx['主要作品'].length){ rec.ext=(rec.ext||[]).map(e=>e[0]==='P800'?[e[0],e[1],fx['主要作品']]:e); }\n    if('職業' in fx&&rec.gen){")

# ---- 65. 王者の殿堂（防衛5回以上の王者を称える。記録と歴代王者も）----
rep("#throne .champ{", "#throne .hallgo{margin-top:6px}\n.hl-sub{font-size:12px;color:var(--muted);line-height:1.5}\n.hl-sec{padding:12px 16px 4px}.hl-sec h4{margin:0 0 8px;font-size:13px;letter-spacing:.08em;color:var(--muted);font-weight:700}\n.hl-plq{border:1px solid var(--line);border-left:4px solid var(--hl);border-radius:10px;padding:10px 12px;margin:0 0 10px;background:var(--bg)}\n.hl-plq .nm{font-family:var(--f-display);font-weight:400;font-size:20px;line-height:1.25;overflow-wrap:anywhere}\n.hl-plq .sub{font-size:12px;color:var(--muted)}\n.hl-plq .lk{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:6px;font-size:13px}\n.hl-rec{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:14px;margin:0}\n.hl-rec dt{color:var(--muted);font-size:12px;padding-top:2px}.hl-rec dd{margin:0;overflow-wrap:anywhere}\n.hl-his{margin:0;padding-left:2.6em;list-style:decimal;font-size:14px}.hl-his li{margin:2px 0}.hl-his .who{font-size:12px;color:var(--muted)}\n.hl-none{font-size:13px;color:var(--muted);margin:0 0 10px}\n.hl-plq.leg{border:3px solid #c9a227;padding:14px 14px 12px;background:linear-gradient(135deg,rgba(255,215,64,.55),rgba(201,162,39,.22) 60%,rgba(255,236,150,.45));box-shadow:0 0 0 1px rgba(201,162,39,.35),0 6px 22px rgba(201,162,39,.35)}\n.hl-plq.leg .nm{font-size:28px}\n.hl-plq.leg .sub{color:var(--ink)}\n.hl-sec h4.leg{color:#a8841a;font-size:14px}\n.hl-plq .bdg{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.06em;padding:1px 8px;border-radius:99px;margin-right:6px;background:var(--hl);color:var(--hl-ink)}\n#throne .champ{")
rep("""  <details class="thx" id="thx\"""", """  <div class="hallgo"><button type="button" class="btn small" id="hallopen">王者の殿堂 ▶</button></div>
  <details class="thx" id="thx\"""")
rep("  $('#thx').addEventListener('toggle',e=>{ THOPEN=e.target.open; });", "  $('#thx').addEventListener('toggle',e=>{ THOPEN=e.target.open; }); $('#hallopen').onclick=()=>openHall();")
rep("// 記録された挑戦を、その場で再生する", r"""// 王者の殿堂：防衛5回以上の王者を称える札と、記録、歴代王者
const HALL_MIN=5, HALL_LEG=10;   // 防衛5回で殿堂入り、10回で伝説の王者
const span=(a,b)=>{ const m=Math.max(0,Math.round((new Date(b)-new Date(a))/60000)); if(m<1) return '1分未満'; if(m<60) return m+'分'; const h=Math.floor(m/60); if(h<24) return h+'時間'+(m%60?m%60+'分':''); const d=Math.floor(h/24); return d+'日'+(h%24?h%24+'時間':''); };
const ymd=s=>{ try{ const d=new Date(s); return d.getFullYear()+'/'+(d.getMonth()+1)+'/'+d.getDate(); }catch(_){ return ''; } };
async function openHall(){ const dlg=$('#famdlg'); if(!dlg) return; let d;
  try{ d=await fetch(API+'/api/hall').then(r=>r.json()); }catch(_){ d=null; } if(!d||!d.reigns) return;
  const R=d.reigns, cur=R.find(x=>!x.ended_at), end=x=>x.ended_at||d.now;
  const rp=(id,t)=>id?`<a class="rp" href="?c=${id}" data-c="${id}">${t}</a>`:'';
  const nm=x=>`<b>${esc(x.display)}</b>`;
  const fame=R.filter(x=>x.defenses>=HALL_MIN&&x.defenses<HALL_LEG).sort((a,b)=>b.defenses-a.defenses||a.id-b.id), leg=R.filter(x=>x.defenses>=HALL_LEG).sort((a,b)=>b.defenses-a.defenses||a.id-b.id);
  const plq=x=>`<div class="hl-plq${x.defenses>=HALL_LEG?' leg':''}"><div class="sub">${x.defenses>=HALL_LEG?'<span class="bdg">👑 伝説の王者</span>':''}第${x.id}代王者${x.ended_at?'':'・在位中'}</div><div class="nm">${esc(x.display)}</div>
    <div class="sub">防衛 <b>${x.defenses}</b>回 ／ 在位 ${esc(span(x.started_at,end(x)))}（${esc(ymd(x.started_at))}〜${x.ended_at?esc(ymd(x.ended_at)):''}） ／ 王座を取った人：${esc(x.holder)}</div>
    <div class="lk">${rp(x.cid,'王座を取った試合 ▶')}${x.ended_by?(x.lostcid?rp(x.lostcid,esc(x.ended_by)+'に敗れた試合 ▶'):'<span>'+esc(x.ended_by)+'に敗れる</span>'):''}</div></div>`;
  const best=[...R].sort((a,b)=>b.defenses-a.defenses||a.id-b.id)[0];
  const long=[...R].sort((a,b)=>(new Date(end(b))-new Date(b.started_at))-(new Date(end(a))-new Date(a.started_at))||a.id-b.id)[0];
  const k=d.killer&&d.killer[0], mo=d.most&&d.most[0];
  const rec=[best&&best.defenses>0?['最多防衛',`${nm(best)} ${best.defenses}回`]:null,
    long?['最長在位',`${nm(long)} ${esc(span(long.started_at,end(long)))}${long.ended_at?'':'（在位中）'}`]:null,
    k&&k.n>1?['王者キラー',`<b>${esc(k.display)}</b> ${k.n}代の王者を倒す`]:null,
    mo&&mo.n>0?['最も挑まれた王者',`<b>${esc(mo.display)}</b> ${mo.n}回の挑戦を受ける`]:null].filter(Boolean);
  const left=cur?(cur.defenses<HALL_MIN?HALL_MIN:HALL_LEG)-cur.defenses:0;
  dlg.setAttribute('aria-label','王者の殿堂');
  dlg.innerHTML=`<div class="fhead"><div><h3>王者の殿堂</h3><div class="hl-sub">防衛${HALL_MIN}回で殿堂入り🏛、${HALL_LEG}回で伝説の王者👑</div></div><button type="button" class="btn small" id="famx" autofocus>閉じる</button></div>
  ${leg.length?`<div class="hl-sec"><h4 class="leg">👑 伝説の王者</h4>${leg.map(plq).join('')}</div>`:''}<div class="hl-sec"><h4>🏛 殿堂入り</h4>${fame.map(plq).join('')||`<p class="hl-none">${leg.length?'防衛5〜9回の王者はいません。':'まだ殿堂入りした王者はいません。'}</p>`}
    ${cur&&left>0?`<p class="hl-none">いまの王者 <b>${esc(cur.display)}</b> は、あと${left}回防衛すれば${cur.defenses<HALL_MIN?'殿堂入り':'伝説の王者'}。</p>`:''}</div>
  ${rec.length?`<div class="hl-sec"><h4>記録</h4><dl class="hl-rec">${rec.map(([a,b])=>`<dt>${a}</dt><dd>${b}</dd>`).join('')}</dl></div>`:''}
  <div class="hl-sec"><h4>歴代王者</h4><ol class="hl-his">${R.map(x=>`<li value="${x.id}">${x.cid?rp(x.cid,nm(x)):nm(x)}${x.defenses>=HALL_LEG?' 👑':x.defenses>=HALL_MIN?' 🏛':''} <span class="who">防衛${x.defenses}回・${esc(span(x.started_at,end(x)))}${x.ended_at?'':'・在位中'}${x.ended_by?' ／ '+(x.lostcid?rp(x.lostcid,esc(x.ended_by)+'に敗れる'):esc(x.ended_by)+'に敗れる'):''}</span></li>`).join('')}</ol></div>
  <div class="fnote">試合の名前を押すと、その試合を見られます。🏛は殿堂入り、👑は伝説の王者です。</div>`;
  $('#famx').onclick=()=>dlg.close();
  dlg.querySelectorAll('[data-c]').forEach(a=>a.onclick=e=>{ e.preventDefault(); dlg.close(); replayChallenge(+a.dataset.c); });
  if(!dlg.open) dlg.showModal(); dlg.scrollTop=0; }
// 記録された挑戦を、その場で再生する""")
rep("if(new URLSearchParams(location.search).has('me')) openMine();", "if(new URLSearchParams(location.search).has('me')) openMine(); if(new URLSearchParams(location.search).has('hall')) openHall();")

# ---- 66. 王座戦の欄から「最長防衛ランキング」「歴代王者」を外す（王者の殿堂にまとめた）----
rep_span("  <details><summary>最長防衛ランキング</summary>", "</ol></details></details>`;", "</details>`;")

# ---- 67. 対戦に戻す一覧（data/unhold.json）：「確認中」（保留）の記事のうち、確かめて問題ないものを対戦に戻す ----
#   {"記事": {"記事名": "確かめた理由（日付）"}, "理由": {"保留の理由（年の括弧を除く）": "確かめた理由（日付）"}}
rep("let FIX=null, FIXP=null;", "let FIX=null, FIXP=null, UNH=null;")
rep("function fixLoad(){ if(FIX) return Promise.resolve(); return FIXP||(FIXP=fetch('data/fix.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{}).then(o=>{ FIX=o||{}; }).catch(()=>{ FIX={}; })); }",
    "function fixLoad(){ if(FIX) return Promise.resolve(); return FIXP||(FIXP=Promise.all([fetch('data/fix.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({})),fetch('data/unhold.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({}))]).then(([o,u])=>{ UNH=u||{}; FIX=o||{}; })); }\nconst unheld=(t,why)=>!!UNH&&(!!(UNH['記事']||{})[t]||!!(UNH['理由']||{})[String(why).replace(/（[^（）]*年[^（）]*）$/,'')]);   // 確かめて対戦に戻した記事")
rep("function register(rec){ const t=rec.f[1];", "function register(rec){ const t=rec.f[1]; if(rec.hold&&unheld(t,rec.hold)){ rec={...rec}; delete rec.hold; }")

# ---- 68. 世界観をボクシング・プロレスにそろえる（大相撲・柔道の言葉を言い換える）----
def repall(a, b):
    global s
    assert a in s, a[:60]
    s = s.replace(a, b)
# 今日の一戦の予想成績：星取表 → 戦績表、番付 → ボクサーの格付け
repall("// 的中の記録は、大相撲の星取表にならう（当たり○・外れ●・予想なしの観戦は□・来なかった日は「や」）。番付は今月の勝ち星で決まる",
       "// 的中の記録は、ボクサーの戦績表にならう（当たり○・外れ●・予想なしの観戦は□・来なかった日は「－」）。格付けは今月の当たりの数で決まる")
repall("const BANZUKE=[[27,'横綱'],[24,'大関'],[21,'関脇'],[18,'小結'],[15,'前頭'],[12,'十両'],[9,'幕下'],[6,'三段目'],[3,'序二段'],[0,'序ノ口']];",
       "const BANZUKE=[[27,'世界王者'],[24,'世界ランカー'],[21,'東洋太平洋王者'],[18,'日本王者'],[15,'日本ランカー'],[12,'A級ボクサー'],[9,'B級ボクサー'],[6,'C級ボクサー'],[3,'プロテスト合格'],[0,'練習生']];")
repall("else if(d<today&&d>=d0){ mk='や'; c='y'; Y++; }", "else if(d<today&&d>=d0){ mk='－'; c='y'; Y++; }")
repall('<span class="dn">${KANJI(d)}</span>', '<span class="dn">${d}</span>')
repall("<summary>星取表　${MON[m]}月場所 ${KANJI(W)}勝${KANJI(L)}敗・${rank}</summary>", "<summary>戦績表　${m}月 ${W}勝${L}敗・${rank}</summary>")
repall('<div class="hh"><div class="ht">百科拳典<br><b>${MON[m]}月場所</b></div><div class="hr">今場所の番付<b>${rank}</b></div></div>',
       '<div class="hh"><div class="ht">百科拳典 予想戦績<br><b>${m}月</b></div><div class="hr">今月の格付け<b>${rank}</b></div></div>')
repall('<div class="hf"><b>${KANJI(W)}勝${KANJI(L)}敗</b>${Y?`<span>${KANJI(Y)}休</span>`:\'\'}${K?`<span>観戦のみ ${KANJI(K)}</span>`:\'\'}</div>',
       '<div class="hf"><b>${W}勝${L}敗</b>${Y?`<span>欠場 ${Y}</span>`:\'\'}${K?`<span>観戦のみ ${K}</span>`:\'\'}</div>')
repall("${kachi?'<div class=\"seal\">勝ち<br>越し</div>':''}", "${kachi?'<div class=\"seal\">好調</div>':''}")
repall("○当たり　●外れ　□予想なしで観戦　や休場（来なかった日）　番付は今月の当たりの数で上がります", "○当たり　●外れ　□予想なしで観戦　－欠場（来なかった日）　格付けは今月の当たりの数で上がります")
repall("今日の一戦の星取表へ", "今日の一戦の戦績表へ")
# 戦績表の見た目：明朝体・二重線（番付表ふう）→ ゴシック体・太い枠と黒い見出し帯（試合ポスターふう）
repall("#today .hoshi{position:relative;margin-top:8px;border:3px double var(--ink);padding:12px 10px 10px;font-family:'Hiragino Mincho ProN','Yu Mincho','Noto Serif JP',serif;background:var(--paper)}",
       "#today .hoshi{position:relative;margin-top:8px;border:3px solid var(--ink);border-radius:6px;padding:0 10px 10px;background:var(--paper);overflow:hidden}")
repall("#today .hh{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid var(--ink);padding-bottom:6px;margin-bottom:8px}",
       "#today .hh{display:flex;justify-content:space-between;align-items:flex-end;background:var(--ink);color:var(--paper);margin:0 -10px 10px;padding:8px 12px}")
repall("#today .ht b{font-size:22px;letter-spacing:.15em}", "#today .ht b{font-family:var(--f-display);font-weight:400;font-size:22px;letter-spacing:.05em}")
repall("#today .hr b{font-size:24px;letter-spacing:.1em}", "#today .hr b{font-family:var(--f-display);font-weight:400;font-size:20px;letter-spacing:.02em;color:var(--hl)}")
repall("#today .hf b{font-size:24px;letter-spacing:.1em}", "#today .hf b{font-family:var(--f-display);font-weight:400;font-size:24px;letter-spacing:.05em}")
# 比べ合い（数字勝負）：「全三番勝負・第一番・旗・審判団」→ プロレスの「3本勝負・1本目」と、ボクシングのジャッジ
repall("全{n}番勝負。数字の大きいほうが一本を取る。", "{n}本勝負。数字の大きいほうが1本を取る。")
repall("全{n}番勝負。勝敗は、すでにWikipediaに書いてある。", "{n}本勝負。勝敗は、すでにWikipediaに書いてある。")
repall("第{k}番、", "{k}本目、")
repall("どれだけ読まれたかで殴る、最も現代的な一番。", "どれだけ読まれたかで殴る、最も現代的な1本。")
repall("わずかな差で{W}に旗。", "わずかな差で{W}の手が上がる。")
repall("審判団、協議の末、{W}に旗。", "ジャッジ陣、協議の末、{W}の手を挙げる。")
repall("旗が上がる。{W}。", "レフェリーが{W}の手を挙げる。")
repall("lab:RLAB[x.k],k:KANJI[k]};", "lab:RLAB[x.k],k:k+1};")
repall("{W}の一本。", "{W}の1本。")
repall("{W}、一本。", "{W}、1本。")
repall("{W}、辛くも一本。", "{W}、辛くも1本。")
repall("一本も取れませんでした。", "1本も取れませんでした。")
repall("審判団", "ジャッジ陣")
repall("審判も困っています", "ジャッジも困っています")
repall("決まり手は【{lm}】。", "フィニッシュは【{lm}】。")
repall("両者が同じ土俵に上がる日は来ないはずだった。", "両者が同じリングに上がる日は来ないはずだった。")
# 自由対戦の青・赤は、ボクシングのコーナーの呼び方に
repall("aria-pressed=\"false\">青へ</button>", "aria-pressed=\"false\">青コーナーへ</button>")
repall("aria-pressed=\"false\">赤へ</button>", "aria-pressed=\"false\">赤コーナーへ</button>")
repall("x.textContent=(+x.dataset.s===0?'青':'赤')+(on?'に決定':'へ');", "x.textContent=(+x.dataset.s===0?'青コーナー':'赤コーナー')+(on?'に決定':'へ');")
repall("textContent='青：'+(FP[0]?FP[0].n:'未選択');", "textContent='青コーナー：'+(FP[0]?FP[0].n:'未選択');")
repall("textContent='赤：'+(FP[1]?FP[1].n:'未選択');", "textContent='赤コーナー：'+(FP[1]?FP[1].n:'未選択');")

# ---- 69. 遊びやすさの見直し（2026-11-06 にスマホで遊んで見つけた点）----
# 自由対戦の最初の組み合わせは、よく読まれている記事から（初めての人が知らない記事2つで戸惑わないように）。「おまかせで組む」はこれまでどおり半分は全記事から
repall("async function rnd(ex){ for(let k=0;k<12;k++){ let t;\n    if(Math.random()<0.5&&POPULAR.length)", "async function rnd(ex,pop){ for(let k=0;k<12;k++){ let t;\n    if((pop||Math.random()<0.5)&&POPULAR.length)")
repall("const [x,y]=await Promise.all([rnd([]),rnd([])]);", "const [x,y]=await Promise.all([rnd([],1),rnd([],1)]);")
repall("sel[0]=NORAND.has(F[x][1])?await rnd([y]):x; sel[1]=(y===sel[0]||NORAND.has(F[y][1]))?await rnd([sel[0]]):y;", "sel[0]=NORAND.has(F[x][1])?await rnd([y],1):x; sel[1]=(y===sel[0]||NORAND.has(F[y][1]))?await rnd([sel[0]],1):y;")
# 今日の一戦：記事の名前の下に、何の記事かを1行で（Wikipedia の記事の冒頭から。読み込めないときはカテゴリ）
repall('<b>${esc(nm(a))}</b><small>${esc(kind(a))}</small>', '<b>${esc(nm(a))}</b><small class="tdk" id="tdka">${esc(TDH[F[a][1]]||kind(a)||cats(a))}</small>')
repall('<b>${esc(nm(b))}</b><small>${esc(kind(b))}</small>', '<b>${esc(nm(b))}</b><small class="tdk" id="tdkb">${esc(TDH[F[b][1]]||kind(b)||cats(b))}</small>')
repall("const kind=i=>{ const c=(GEN[i]||{}).c||''; return c==='ヒト'?'人物':c; };", "const kind=i=>{ const c=(GEN[i]||{}).c||''; return c==='ヒト'?'人物':c; }; const cats=i=>((GEN[i]||{}).cc||[]).slice(0,2).join('・');")
repall("${act}${Object.values(o).some(x=>x&&x.done)?tdCal(o):''}`;\n", "${act}${Object.values(o).some(x=>x&&x.done)?tdCal(o):''}`;\n  tdHint(a,'#tdka'); tdHint(b,'#tdkb');\n")
repall("function tdCal(o){", r"""const TDH={};   // 今日の一戦の記事の、ひとこと説明（記事名 → 文）
async function tdHint(i,sel){ const t=F[i][1]; let h=TDH[t];
  if(!h){ try{ const d=await fetch('https://ja.wikipedia.org/api/rest_v1/page/summary/'+encodeURIComponent(t.replace(/ /g,'_')),{headers:{'Api-User-Agent':'hyakka-kenten (+https://github.com/y-krn)'}}).then(r=>r.ok?r.json():null); if(!d) return;
      h=(d.description||'').trim();   // 短い説明（Wikidata）。なければ記事の冒頭の一文（日本語版Wikipedia・CC BY-SA 4.0。記事へのリンクとページ下の注記で出どころを示す）
      if(!h&&d.extract){ h=d.extract.replace(/（[^（）]*）|\([^()]*\)/g,'').split('。')[0]; h=h.replace(/^.{1,40}?(とは|は)、/,''); }
      h=h.trim(); if(!h) return; if(h.length>42) h=h.slice(0,40)+'…'; TDH[t]=h; }catch(_){ return; } }
  const e=$(sel); if(e) e.innerHTML='<a href="https://ja.wikipedia.org/wiki/'+encodeURIComponent(t.replace(/ /g,'_'))+'" target="_blank" rel="noopener">'+esc(h)+'</a>'; }
function tdCal(o){""")
repall(".tdvs b{font-size:20px;line-height:1.3;overflow-wrap:anywhere}", ".tdvs b{font-size:20px;line-height:1.3;overflow-wrap:anywhere;word-break:auto-phrase;text-wrap:balance}\n.tdvs .tdk{line-height:1.4}\n.tdvs .tdk a{color:inherit;text-decoration:underline dotted;text-underline-offset:2px}\n.tdbtn .btn{word-break:auto-phrase;text-wrap:balance}")
# 観戦中は、新しい実況に合わせて画面を送る（自分でスクロールしたら、それ以降は送らない）
repall("items[k].classList.remove('hide'); items[k].classList.add('pop'); setHP(k); k++;", "items[k].classList.remove('hide'); items[k].classList.add('pop'); setHP(k); if(follow&&k) items[k].scrollIntoView({block:'nearest',behavior:'smooth'}); k++;")
repall("const reduce=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;", "const reduce=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;\n  let follow=true; const unf=()=>{ follow=false; }; ['wheel','touchmove','keydown'].forEach(ev=>addEventListener(ev,unf,{once:true,passive:true}));")
# 決着したら、得点板を画面の上に張り付けない（結果・共有を読むときの邪魔になる）
repall(".sb{display:flex;flex-direction:column;gap:4px;min-width:0}", ".scoreboard.done{position:relative}\n.sb{display:flex;flex-direction:column;gap:4px;min-width:0}")
repall("Wikidataの数値に誤りが見つかったものは、日本語版の記事などで確かめて直しています。</span>", "Wikidataの数値に誤りが見つかったものは、日本語版の記事などで確かめて直しています。今日の一戦の記事のひとこと説明は、日本語版Wikipediaの記事の冒頭などから引いています（CC BY-SA 4.0、説明を押すと元の記事が開きます）。</span>")
# 戦績表の「好調」：和風のはんこ（表に重なる）をやめて、勝敗の横にチャンピオンベルトふうの帯
repall("<div class=\"hf\"><b>${W}勝${L}敗</b>${Y?", "<div class=\"hf\"><b>${W}勝${L}敗</b>${kachi?'<em class=\"belt\">好調</em>':''}${Y?")
repall("\n    ${kachi?'<div class=\"seal\">好調</div>':''}", "")
repall("#today .seal{position:absolute;right:10px;bottom:34px;color:#c0392b;border:3px solid #c0392b;border-radius:50%;width:70px;height:70px;display:flex;align-items:center;justify-content:center;text-align:center;font-size:15px;line-height:1.15;font-weight:700;transform:rotate(-14deg);opacity:.85;background:color-mix(in srgb,var(--paper) 70%,transparent)}",
       "#today .belt{align-self:center;font-style:normal;font-family:var(--f-display);font-weight:400;font-size:14px;letter-spacing:.12em;color:#1b1b1b;background:linear-gradient(180deg,#ffe36b,#f2c230);border:2px solid #1b1b1b;border-radius:4px;padding:3px 14px;box-shadow:inset 0 0 0 2px rgba(255,255,255,.55)}")
# 代表戦：誕生日がきょうなら、相手も同じ誕生日なので、そう書く
repall('<div class="mb"><small>きょう${td.m}月${td.d}日生まれ</small>', '<div class="mb"><small>${+v.m===td.m&&+v.d===td.d?\'もう一人の\':\'きょう\'}${td.m}月${td.d}日生まれ</small>')
repall("。きょう${td.m}月${td.d}日生まれの${ST.opp.n}と対決！", "。${+ST.v.m===td.m&&+ST.v.d===td.d?'同じ':'きょう'}${td.m}月${td.d}日生まれの${ST.opp.n}と対決！")

# ---- 70. 「数えない」印：動作確認に使うブラウザで、アクセス解析と利用回数に数えない ----
#   URL に ?nostat=1 を付けて一度開くと、そのブラウザに印が残る（?nostat=0 で外す）。印があるときは、Cloudflare Web Analytics を読み込まず、利用回数（/api/plays）も送らない
repall("<script>\n/* ---------- 記事データ：必要になった記事だけを読み込む ---------- */", "<script>\nconst NOSTAT=(()=>{ try{ const q=new URLSearchParams(location.search).get('nostat'); if(q==='1') localStorage.setItem('hk-nostat','1'); if(q==='0') localStorage.removeItem('hk-nostat'); return localStorage.getItem('hk-nostat')==='1'; }catch(_){ return false; } })();   // 動作確認に使うブラウザは数えない\n/* ---------- 記事データ：必要になった記事だけを読み込む ---------- */")
repall("function flushPlays(beacon){ const n=Math.min(30,pend()); if(!n||!API) return;", "function flushPlays(beacon){ const n=Math.min(30,pend()); if(!n||!API||NOSTAT) return;")
repall("""<!-- Cloudflare Web Analytics --><script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "92aaad9660e1433f8d518c17a8ac2512"}'></script><!-- End Cloudflare Web Analytics -->""",
       """<!-- Cloudflare Web Analytics（「数えない」印のあるブラウザでは読み込まない） --><script>if(!NOSTAT){ const s=document.createElement('script'); s.type='module'; s.src='https://static.cloudflareinsights.com/beacon.min.js'; s.setAttribute('data-cf-beacon','{"token": "92aaad9660e1433f8d518c17a8ac2512"}'); document.body.appendChild(s); }</script><!-- End Cloudflare Web Analytics -->""")

# ---- 71. 記事カードの「配慮：存命人物」などの札を出さない（遊ぶ人には役に立たず、「配慮」の言葉で誤解を招くため。文面を控えめにする仕組みはそのまま）----
repall("\n  ${f[5]==='配慮'?`<div><span class=\"chip\">配慮：${esc(f[6].replace(/：.*/,''))}</span></div>`:''}", "")

# ---- 72. 同じ表示名どうしの対戦（「冬将軍」と「冬将軍 (曲)」など）は、括弧つきの記事名で見分けられるようにする ----
repall("function simulate(ai,bi,opt={}){\n", "// 表示名が同じ2記事は、記事名（括弧の説明つき）で表示する（この端末で開いている間ずっと）\nfunction disamb(a,b){ if(a!==null&&b!==null&&a!==b&&F[a]&&F[b]&&F[a][0]===F[b][0]){ F[a][0]=F[a][1]; F[b][0]=F[b][1]; } }\nfunction simulate(ai,bi,opt={}){ disamb(ai,bi);\n")
repall("function updateFight(){ ", "function updateFight(){ if(sel[0]!==null&&sel[1]!==null&&F[sel[0]]&&F[sel[1]]&&F[sel[0]][0]===F[sel[1]][0]){ disamb(sel[0],sel[1]); renderPick(0); renderPick(1); }\n  ")

# ---- 73. 王座戦：結果（防衛・新王者など）は、試合を見終わってから出す。試合の途中に王座の欄で結果が分かってしまわないように ----
repall("let TH_LAST=Date.now(), TH_ACT=Date.now(), TH_SEEN=true;", "let TH_LAST=Date.now(), TH_ACT=Date.now(), TH_SEEN=true, TH_HOLD=null;   // TH_HOLD：試合のあとに出す結果 {msg, at}")
repall("async function refreshThrone(){ if(!API||document.hidden||!THRONE) return;", "async function refreshThrone(){ if(!API||document.hidden||!THRONE) return; if(TH_HOLD&&Date.now()-TH_HOLD.at<300000) return; /* 試合中は王座の欄を変えない（5分たったら戻す） */")
repall("  await loadThrone(msg);\n  try{ const a=await loadTitle(d.challenger.title), b=await loadTitle(d.champ.title); if(a>=0&&b>=0){ MODE={res:d,no:d.reignNo||(THRONE?THRONE.reignNo:1)}; await kbClosed(); startBattle([a,b]); } }catch(_){} }",
       "  let shown=false; m.className='msg'; m.textContent='試合開始。結果は、試合のあとでここに出ます。';\n  try{ const a=await loadTitle(d.challenger.title), b=await loadTitle(d.champ.title); if(a>=0&&b>=0){ TH_HOLD={msg,at:Date.now()}; MODE={res:d,no:d.reignNo||(THRONE?THRONE.reignNo:1)}; await kbClosed(); startBattle([a,b]); shown=true; } }catch(_){}\n  if(!shown){ TH_HOLD=null; await loadThrone(msg); } }")
repall("  if(!current||current.shown) return; current.shown=true;", "  if(!current||current.shown) return; current.shown=true; if(current.mode&&TH_HOLD){ const h=TH_HOLD.msg; TH_HOLD=null; setTimeout(()=>loadThrone(h),0); } /* 王座戦の結果は、ここで王座の欄に出す */")

# ---- 74. 共有URL（?a=…&b=…）で開いた対戦は、片方がいまの王者でも、そのまま観戦できるようにする（投稿したトーナメントの試合などが、あとで王者になった記事のせいで見られなくなっていた）----
#   王座は動かない観戦だけ。王者を自由対戦の欄で選べないのは、いままでどおり
repall("    else if(isChamp(i)) why[s]='「'+t+'」はいまの王者なので自由対戦に出せません。別の記事にしました';\n", "")
repall("  if(!why[0]&&!why[1]) startBattle(); return true; }",
       "  if(!why[0]&&!why[1]){ const ch=isChamp(sel[0])||isChamp(sel[1]); startBattle(ch?[sel[0],sel[1]]:undefined);   // 王者が出ている共有の対戦も、観戦はできる\n    if(ch) for(const s of [0,1]) if(isChamp(sel[s])){ const n=$(s===0?'#pickA':'#pickB').querySelector('.pmsg'); if(n) n.textContent='いまの王者です。共有された対戦の観戦だけで、王座は動きません'; } }\n  return true; }")

# ---- 75. 試作（プレビューだけ）：百科ダンジョン。記事のリンクをたどり、扉の先の記事と殴り合って、何階まで潜れるかに挑む ----
#   扉は、いまいる記事のリンク先から3つ（日付とその記事から決まるので、同じ日なら誰でも同じ扉）。勝てば扉の先へ進み、倒した記事に乗り換えることもできる。負けたら終わり
repall('  <section id="setup" class="card" style="padding:16px;display:flex;flex-direction:column;gap:14px">',
  '''  <section id="dg" class="card" style="padding:16px;display:flex;flex-direction:column;gap:12px">
    <div class="sechead"><h2>百科ダンジョン</h2><span>リンクの扉をくぐって、どこまで潜れるか</span></div>
    <div id="dgbox" class="dgbox" aria-live="polite">準備しています…</div>
  </section>

  <section id="setup" class="card" style="padding:16px;display:flex;flex-direction:column;gap:14px">''')
repall("input,select,textarea{font-size:16px!important}", "input,select,textarea{font-size:16px!important}#dg .dgbox{display:flex;flex-direction:column;gap:10px}#dg .dgst{font-size:13px;color:var(--muted);line-height:1.6}#dg .dgst b{color:var(--ink)}#dg .dgq{font-weight:700}#dg .dgfl{font-size:22px;font-weight:800;color:var(--ink)}#dg .dgin{width:100%;box-sizing:border-box;font-size:20px;justify-content:center}#dg .dgres .dgc{display:block;margin-top:2px}#dg .dgdoors{display:flex;flex-direction:column;gap:8px}#dg #dgpin{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid var(--line);border-radius:8px}#dg .dgd{justify-content:flex-start;text-align:left;white-space:normal;line-height:1.5;padding:10px 12px}#dg .dgc{font-size:12px;font-weight:normal;color:var(--muted)}#dg .dgres{border:1px solid var(--line);border-radius:10px;padding:10px 12px;line-height:1.6}#dg .dgres.lose{border-color:var(--red,#c33)}#dg .dgpath{font-size:13px;line-height:1.7}#dg .dgshare{white-space:pre-wrap;font-size:13px;background:var(--bg);border:1px dashed var(--line);border-radius:8px;padding:8px 10px}")
_dg = r"""
// ---- 百科ダンジョン（試作） ----
let DG=null;   // {day, me（自分の選手）, pos（いまいる記事）, floor, path:[{t, ev}], seen:Set}
// 扉に出さない記事：年・日付・一覧と、どこからでもつながる大きすぎる記事
const DG_NG=/^(紀元前)?\d+年(代)?$|^\d+月\d+日$|^\d+月$|^\d+世紀$|一覧|^日本$|^日本語$|^英語$|^アメリカ合衆国$|^東京都$|^ウィキ|^Wikipedia|^ISBN|^国際標準|^バーチャル国際典拠|^典拠管理|^世界の国/;
const DGE={start:'🏁',win:'⚔️',switch:'🔁',draw:'🤝',lose:'💀'};
async function dgLinks(t){ const out=[]; let cont={};
  for(let k=0;k<3;k++){ const j=await fetch('https://ja.wikipedia.org/w/api.php?'+new URLSearchParams({format:'json',origin:'*',action:'query',prop:'links',titles:t,plnamespace:0,pllimit:'max',redirects:1,...cont})).then(r=>r.json()).catch(()=>({}));
    for(const p of Object.values((j.query||{}).pages||{})) for(const l of (p.links||[])) out.push(l.title);
    if(!j.continue) break; cont=j.continue; }
  return out; }
// 扉：いまいる記事のリンク先から、収録している記事を3つ（順番は日付と記事名で決まる）
async function dgDoors(){ const here=F[DG.pos][1], L=[...new Set(await dgLinks(here))].filter(t=>!DG_NG.test(t)&&!DG.seen.has(t));
  const order=L.map(t=>[t,hash('dg/'+DG.day+'/'+here+'/'+t)]).sort((a,b)=>a[1]-b[1]).map(x=>x[0]); const out=[];
  for(const t of order){ if(out.length>=3) break; const i=await loadTitle(t).catch(()=>-1); if(i<0||BLOCK.has(i)||isChamp(i)||i===DG.me||out.includes(i)) continue; out.push(i); }
  return out; }
// 扉の手がかり：分類と、その記事らしい事実を1つだけ（数値の能力は出さない。知識で読む余地を残す）
const dgClue=i=>{ const c=(CL[i]||[])[1], m=(POOL[i]||[]).find(m=>m[3]&&/：/.test(m[3])&&!/^(Wikidataでの分類|別名)/.test(m[3])&&m[0]!=='NAME'&&m[0]!=='SENIORITY'&&!/マウント|長文|リンク|注目|カテゴリ|見出し|画像|名前/.test(m[1])); const fact=m?m[3]:''; return `<span class="dgc">${[c,fact].filter(Boolean).map(esc).join('｜')}</span>`; };
const dgHead=()=>`<div class="dgfl">${DG.floor}階</div><div>あなた：<b>${esc(F[DG.me][0])}</b>　${dgClue(DG.me)}</div><div class="dgpath">${DG.path.map(p=>DGE[p.ev]+esc(p.t)).join(' → ')}</div>`;
// 今日の挑戦は1日1回。記録は hk-dg {day, deep, path, done}。途中で離れたら、そこまでで終わり
const dgRec=()=>{ try{ const o=JSON.parse(localStorage.getItem('hk-dg')||'{}'); return o.day===jstDay()&&Array.isArray(o.path)&&o.path.length?o:null; }catch(_){ return null; } };   // 最初の試作の記録（{day, best}）は読まない
function dgSave(done){ if(!DG||DG.practice) return; const deep=DG.path.filter(p=>p.ev==='win'||p.ev==='switch'||p.ev==='draw').length; try{ localStorage.setItem('hk-dg',JSON.stringify({day:DG.day,deep,path:DG.path,done:!!done})); }catch(_){} }
function dgShare(day,path){ const md=day.slice(5).replace('-','/').replace(/^0/,''), deep=path.filter(p=>p.ev==='win'||p.ev==='switch'||p.ev==='draw').length; return `百科ダンジョン ${md}\n${path[0].t}から潜って ${deep}階突破\n${path.map(p=>DGE[p.ev]).join('')}\n${path.map(p=>p.t).join(' → ')}\n${location.origin}/`; }
function dgStart(i,practice){ DG={day:jstDay(),practice:!!practice,me:i,pos:i,floor:1,path:[{t:F[i][1],ev:'start'}],seen:new Set([F[i][1]])}; dgSave(false); dgFloor(); }
async function dgFloor(){ const box=$('#dgbox'); box.innerHTML=`<div class="dgst">${dgHead()}</div><div class="dgst">…</div>`;
  const doors=await dgDoors(); if(!DG) return;
  if(!doors.length){ dgEnd('行き止まり。この記事からは、もう扉が見つからない'); return; }
  box.innerHTML=`<div class="dgst">${dgHead()}</div><div class="dgq">どの扉に入る？</div><div class="dgdoors">${doors.map((d,k)=>`<button type="button" class="btn dgd" data-k="${k}"><span>🚪 <b>${esc(F[d][0])}</b><br>${dgClue(d)}</span></button>`).join('')}</div><div class="trow"><button type="button" class="btn small" id="dgquit">引き返す</button></div>`;
  box.querySelectorAll('.dgd').forEach(b=>b.onclick=()=>dgFight(doors[+b.dataset.k]));
  $('#dgquit').onclick=()=>dgEnd('🏳️ 引き返した'); }
function dgFight(d){ const me=DG.me, an=analyze(me,d), r=an.r, w=r.w;
  const how=r.how||(r.kind==='KO'?r.tick+'カウントでKO':r.kind==='判定'?'判定':r.kind||''); const dm=(an.dec||[]).find(x=>x.who===w&&x.move);
  const key=dm?`。決め手は【${esc(dm.move)}】`:''; DG.seen.add(F[d][1]); const box=$('#dgbox');
  const watch=`<button type="button" class="btn small" id="dgw">観戦</button>`;
  if(w===me){ DG.path.push({t:F[d][1],ev:'win'}); DG.pos=d; dgSave(false);
    box.innerHTML=`<div class="dgst">${dgHead()}</div><div class="dgres win">⚔️ <b>${esc(F[d][0])}</b>に勝った<div class="dgc">${esc(how)}${key}</div></div><div class="trow"><button type="button" class="btn" id="dgkeep">このまま進む</button><button type="button" class="btn" id="dgsw">🔁 ${esc(F[d][0])}になって進む</button>${watch}</div>`;
    $('#dgkeep').onclick=()=>{ DG.floor++; dgFloor(); }; $('#dgsw').onclick=()=>{ DG.me=d; DG.path[DG.path.length-1].ev='switch'; dgSave(false); DG.floor++; dgFloor(); }; }
  else if(w===null){ DG.path.push({t:F[d][1],ev:'draw'}); DG.pos=d; dgSave(false);
    box.innerHTML=`<div class="dgst">${dgHead()}</div><div class="dgres">🤝 <b>${esc(F[d][0])}</b>と引き分け</div><div class="trow"><button type="button" class="btn" id="dgkeep">進む</button>${watch}</div>`;
    $('#dgkeep').onclick=()=>{ DG.floor++; dgFloor(); }; }
  else { DG.path.push({t:F[d][1],ev:'lose'}); dgEnd(`💀 <b>${esc(F[d][0])}</b>に負けた<div class="dgc">相手の${esc(how)}${key}</div>`,d); }
  const wb=$('#dgw'); if(wb) wb.onclick=()=>{ MODE=null; startBattle([me,d]); }; }
function dgEnd(msg,foe){ const box=$('#dgbox'), deep=DG.path.filter(p=>p.ev==='win'||p.ev==='switch'||p.ev==='draw').length, pr=DG.practice; dgSave(true);
  const share=dgShare(DG.day,DG.path), me=DG.me;
  box.innerHTML=`<div class="dgfl">${deep}階突破</div><div class="dgres lose">${msg}</div><div class="dgpath">${DG.path.map(p=>DGE[p.ev]+esc(p.t)).join(' → ')}</div><div class="trow">${pr?'':'<button type="button" class="btn" id="dgcopy">'+dgShareLab()+'</button>'}${foe!==undefined?`<button type="button" class="btn small" id="dgw">観戦</button>`:''}<button type="button" class="btn small" id="dgagain">閉じる</button></div>`;
  if($('#dgcopy')) $('#dgcopy').onclick=()=>dgCopy(share);
  if($('#dgw')) $('#dgw').onclick=()=>{ MODE=null; startBattle([me,foe]); };
  $('#dgagain').onclick=()=>{ DG=null; dgInit(); }; }
// スマホでは共有の画面を開き、パソコンではコピーする。ボタンの名前もそれに合わせる
const dgShareLab=()=>navigator.share&&TOUCH?'結果を共有':'結果をコピー';
async function dgCopy(share){ try{ if(navigator.share&&TOUCH) await navigator.share({text:share}); else { await navigator.clipboard.writeText(share); const b=$('#dgcopy'); if(b) b.textContent='コピーしました'; } }catch(_){} }
// 入口：今日のお題（1日1回の挑戦）と、練習（何度でも。記録に残らない）
async function dgInit(){ try{ await dgInit0(); }catch(e){ const box=$('#dgbox'); if(box) box.textContent='準備できませんでした。ページを読み込み直してください。'; } }
async function dgInit0(){ const box=$('#dgbox'); if(!box) return; if(!POPULAR.length){ box.textContent='今日のお題を用意できませんでした。'; return; } const day=jstDay();
  let t0=-1; for(let k=0;k<20&&t0<0;k++){ const t=POPULAR[hash('dg-start/'+day+'/'+k)%POPULAR.length]; if(!t) continue; const i=await loadTitle(t).catch(()=>-1); if(i>=0&&!BLOCK.has(i)&&!isChamp(i)) t0=i; }
  const o=dgRec(); if(o&&!o.done){ o.done=true; try{ localStorage.setItem('hk-dg',JSON.stringify(o)); }catch(_){} }   // 挑戦の途中で離れたら、そこまでの記録で終わり
  const rule='決まりごと：いまいる記事のリンク先が、3つの扉になります。扉には、その記事の分類と、事実がひとつ書いてあります。扉の先の記事と殴り合い、勝てば先へ。倒した記事に乗り換えてもかまいません。負けたら終わり。今日の挑戦は1日1回で、同じ日なら誰が潜っても同じ扉が出ます。';
  if(o){ const share=dgShare(day,o.path);
    box.innerHTML=`<div class="dgfl">今日は ${o.deep}階突破</div><div class="dgpath">${o.path.map(p=>DGE[p.ev]+esc(p.t)).join(' → ')}</div><div class="trow"><button type="button" class="btn" id="dgcopy">${dgShareLab()}</button></div><div class="dgst">次のお題は明日</div>`;
    $('#dgcopy').onclick=()=>dgCopy(share); }
  else { box.innerHTML=`<div class="dgst">今日の入口</div>${t0>=0?`<button type="button" class="btn big dgin" id="dgtoday">🚪 ${esc(F[t0][0])}</button>`:''}<div class="dgst">1日1回</div>`;
    if($('#dgtoday')) $('#dgtoday').onclick=()=>dgStart(t0,false); }
  /* 練習（dgPick）は、分かりにくいので入口を外している */ }
// 練習で潜る記事を選ぶ（記事名を入れるか、ランダム）。今日のお題は、挑戦が済むまで練習に使えない
function dgPick(o,t0){ const box=$('#dgbox'), cur=sel[0]!==null&&sel[0]>=0?F[sel[0]][1]:'';
  box.innerHTML=`<div class="dgq">練習で潜る記事を選ぶ</div><div class="dgst">練習は何度でもできます。記録には残りません。</div><input id="dgpin" type="text" placeholder="記事名（例：東京タワー）" value="${esc(cur)}" autocomplete="off" aria-label="練習で潜る記事名"><div class="trow"><button type="button" class="btn" id="dgpgo">この記事で練習</button><button type="button" class="btn small" id="dgprnd">ランダムな記事で練習</button><button type="button" class="btn small" id="dgpback">戻る</button></div><div class="fsub" id="dgpmsg" aria-live="polite"></div>`;
  const msg=t=>{ $('#dgpmsg').textContent=t; };
  const go=async i=>{ if(i<0||BLOCK.has(i)) return msg('その記事は見つかりませんでした。記事名を確かめてください'); if(isChamp(i)) return msg('いまの王者では潜れません'); if(!o&&i===t0) return msg('今日のお題の練習は、今日の挑戦のあとでできます'); dgStart(i,true); };
  $('#dgpgo').onclick=async()=>{ const t=$('#dgpin').value.trim(); if(!t) return msg('記事名を入れてください'); msg('探しています…'); go(await loadTitle(t).catch(()=>-1)); };
  $('#dgpin').onkeydown=e=>{ if(e.key==='Enter'){ e.preventDefault(); $('#dgpgo').click(); } };
  $('#dgprnd').onclick=async()=>{ msg('選んでいます…'); go(await rnd(t0>=0?[t0]:[])); };
  $('#dgpback').onclick=()=>{ DG=null; dgInit(); }; }
"""
repall("\nrenderRec();\n(async()=>{", _dg+"\nrenderRec();\n(async()=>{")
repall("setCount(); famToday(); mineInit(); todayInit();", "setCount(); famToday(); mineInit(); todayInit(); dgInit();")

# ---- 76. 自由対戦の選手カードに、能力の数値（HP・攻撃・防御・速さ）を出さない。強さは記事の事実（技の候補）から読む形にそろえる ----
repall("""  <div class="stats">${f[3].map((v,k)=>`<span>${STAT[k]}</span><span class="bar"><i style="width:${Math.min(100,v/MAX[k]*100)}%"></i></span><span>${v}</span>`).join('')}</div>\n""", "")

# 確認画面の枠と、使わなくなった表示を消す
rep('  <section id="review" class="card" hidden></section>\n', '')
open(dst, 'w', encoding='utf-8').write(s)
left = [w for w in ['DATA.', 'NAMES', 'recompute(', 'renderReview', 'dbRef', 'window.claude', 'isAdmin', "list=\"names\""] if w in s]
print('ok', len(s), 'leftover:', left)

# ---- サーバー（王座戦の判定）用：ページと同じ戦闘エンジンを ES モジュールとして書き出す ----
js = s[s.index('<script>') + 8:s.rindex('</script>')]
a = js[:js.index('/* ---------- 記録（この端末だけ）')]
b = js[js.index('/* ---------- 保留・通報・確認'):js.index('function setCount()')]
a = a.replace("const $=s=>document.querySelector(s);", "")
eng = "/* 百科拳典の戦闘エンジン（index.html から自動生成。直接編集しない） */\nlet DATA_BASE='data/', FETCH=u=>fetch(u);\n" + a.replace("fetch('data/a/'", "fetch(DATA_BASE+'a/'").replace("fetch(DATA_BASE+'a/'", "FETCH(DATA_BASE+'a/'") + b.replace("fetch('data/fix.json?t='+Date.now(),{cache:'no-store'})", "FETCH(DATA_BASE+'fix.json')").replace("fetch('data/unhold.json?t='+Date.now(),{cache:'no-store'})", "FETCH(DATA_BASE+'unhold.json')").replace("fetch('data/fixa/'+k+'.json')", "FETCH(DATA_BASE+'fixa/'+k+'.json')") + r"""
/* ---------- サーバー用：1記事だけを取り出して登録する（全体を解析しないので軽い） ---------- */
const TXT={};
function pickRec(txt,t){ const key=JSON.stringify(t)+':{'; let i=txt.indexOf(key); if(i<0) return null; i+=key.length-1; let d=0,inS=false;
  for(let j=i;j<txt.length;j++){ const c=txt.charCodeAt(j); if(inS){ if(c===92){ j++; continue; } if(c===34) inS=false; continue; }
    if(c===34) inS=true; else if(c===123) d++; else if(c===125){ d--; if(!d) return JSON.parse(txt.slice(i,j+1)); } } return null; }
async function loadOne(t){ t=String(t||'').trim(); await Promise.all([fixLoad(),t?fixAuto(t):0]); if(!t) return -1; if(TIX[t]!==undefined) return TIX[t]; const k=fnv(t)%NB;
  if(!TXT[k]){ const r=await FETCH(DATA_BASE+'a/'+k+'.json.gz?v='+VER); if(!r.ok) throw new Error('data '+r.status);
    TXT[k]=await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text(); }
  const rec=pickRec(TXT[k],t); return rec?register(rec):-1; }
function setup(o){ if(o.base) DATA_BASE=o.base; if(o.fetch) FETCH=o.fetch; if(o.nb) NB=o.nb; if(o.ver&&o.ver!==VER){ VER=o.ver; for(const k in TXT) delete TXT[k]; } if(o.excl) EXCL=new Set(o.excl); }
function verdict(ai,bi){ const an=analyze(ai,bi,true); const r=an.r; return {w:r.w===null?null:F[r.w][1], kind:r.kind, how:r.how||(r.kind==='KO'?r.tick+'カウントでKO勝ち':r.kind==='判定'?'判定勝ち':r.kind), type:an.type||null}; }
function info(i){ const f=F[i]; return {title:f[1], name:f[0], q:f[2], stats:f[3], hold:!!HOLD[i], blocked:BLOCK.has(i)}; }
export {setup, loadOne, verdict, info};
"""
open(os.path.join(os.path.dirname(dst), 'engine.mjs'), 'w', encoding='utf-8').write(eng)
print('engine', len(eng))
