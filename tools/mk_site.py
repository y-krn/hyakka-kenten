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
const API='""" + API + """';
let THRONE=null;
const dt=s=>{ try{ const d=new Date(s); return (d.getMonth()+1)+'/'+d.getDate()+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0'); }catch(_){ return ''; } };
const RES={win:'<span class="r-win">王座奪取</span>',lose:'防衛',draw:'引き分け（防衛）',late:'ひと足遅れ'};
function renderThrone(d,msg){ const el=$('#throne'); if(!d){ el.hidden=true; return; } THRONE=d; const c=d.champ; el.hidden=false;
  let nm=''; try{ nm=localStorage.getItem('hk-name')||''; }catch(_){}
  el.innerHTML=`<div class="crown">王座戦 ／ 第${d.reignNo}代王者</div>
  <div class="champ">${esc(c.display)}<a href="https://ja.wikipedia.org/wiki/${encodeURIComponent(c.title)}" target="_blank" rel="noopener">記事 ↗</a></div>
  <div class="meta">防衛 <b>${c.defenses}</b>回 ／ 王座を取った人：<b>${esc(c.holder)}</b> ／ ${esc(dt(c.started_at))}から在位</div>
  <div class="meta">この王者を倒せる記事を、約140万記事の中から探してください。勝てば王座はあなたの記事のもの。結果は何度やっても同じなので、負けた記事での再挑戦はできません。</div>
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
eng = "/* 百科拳典の戦闘エンジン（index.html から自動生成。直接編集しない） */\nlet DATA_BASE='data/';\n" + a.replace("fetch('data/a/'", "fetch(DATA_BASE+'a/'") + b + r"""
/* ---------- サーバー用：1記事だけを取り出して登録する（全体を解析しないので軽い） ---------- */
const TXT={};
function pickRec(txt,t){ const key=JSON.stringify(t)+':{'; let i=txt.indexOf(key); if(i<0) return null; i+=key.length-1; let d=0,inS=false;
  for(let j=i;j<txt.length;j++){ const c=txt.charCodeAt(j); if(inS){ if(c===92){ j++; continue; } if(c===34) inS=false; continue; }
    if(c===34) inS=true; else if(c===123) d++; else if(c===125){ d--; if(!d) return JSON.parse(txt.slice(i,j+1)); } } return null; }
async function loadOne(t){ t=String(t||'').trim(); if(!t) return -1; if(TIX[t]!==undefined) return TIX[t]; const k=fnv(t)%NB;
  if(!TXT[k]){ const r=await fetch(DATA_BASE+'a/'+k+'.json.gz?v='+VER); if(!r.ok) throw new Error('data '+r.status);
    TXT[k]=await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text(); }
  const rec=pickRec(TXT[k],t); return rec?register(rec):-1; }
function setup(o){ if(o.base) DATA_BASE=o.base; if(o.nb) NB=o.nb; if(o.ver&&o.ver!==VER){ VER=o.ver; for(const k in TXT) delete TXT[k]; } if(o.excl) EXCL=new Set(o.excl); }
function verdict(ai,bi){ const an=analyze(ai,bi); const r=an.r; return {w:r.w===null?null:F[r.w][1], kind:r.kind, how:r.how||(r.kind==='KO'?r.tick+'カウントでKO勝ち':r.kind==='判定'?'判定勝ち':r.kind), type:an.type||null}; }
function info(i){ const f=F[i]; return {title:f[1], name:f[0], q:f[2], stats:f[3], hold:!!HOLD[i], blocked:BLOCK.has(i)}; }
export {setup, loadOne, verdict, info};
"""
open(os.path.join(os.path.dirname(dst), 'engine.mjs'), 'w', encoding='utf-8').write(eng)
print('engine', len(eng))
