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
rep('</body>', '<!-- Cloudflare Web Analytics --><script type=\'module\' src=\'https://static.cloudflareinsights.com/beacon.min.js\' data-cf-beacon=\'{"token": "372a3169a34e4c9087b188f33b44e521"}\'></script><!-- End Cloudflare Web Analytics -->\n</body>')


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
eng = "/* 百科拳典の戦闘エンジン（index.html から自動生成。直接編集しない） */\nlet DATA_BASE='data/', FETCH=u=>fetch(u);\n" + a.replace("fetch('data/a/'", "fetch(DATA_BASE+'a/'").replace("fetch(DATA_BASE+'a/'", "FETCH(DATA_BASE+'a/'") + b + r"""
/* ---------- サーバー用：1記事だけを取り出して登録する（全体を解析しないので軽い） ---------- */
const TXT={};
function pickRec(txt,t){ const key=JSON.stringify(t)+':{'; let i=txt.indexOf(key); if(i<0) return null; i+=key.length-1; let d=0,inS=false;
  for(let j=i;j<txt.length;j++){ const c=txt.charCodeAt(j); if(inS){ if(c===92){ j++; continue; } if(c===34) inS=false; continue; }
    if(c===34) inS=true; else if(c===123) d++; else if(c===125){ d--; if(!d) return JSON.parse(txt.slice(i,j+1)); } } return null; }
async function loadOne(t){ t=String(t||'').trim(); if(!t) return -1; if(TIX[t]!==undefined) return TIX[t]; const k=fnv(t)%NB;
  if(!TXT[k]){ const r=await FETCH(DATA_BASE+'a/'+k+'.json.gz?v='+VER); if(!r.ok) throw new Error('data '+r.status);
    TXT[k]=await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text(); }
  const rec=pickRec(TXT[k],t); return rec?register(rec):-1; }
function setup(o){ if(o.base) DATA_BASE=o.base; if(o.fetch) FETCH=o.fetch; if(o.nb) NB=o.nb; if(o.ver&&o.ver!==VER){ VER=o.ver; for(const k in TXT) delete TXT[k]; } if(o.excl) EXCL=new Set(o.excl); }
function verdict(ai,bi){ const an=analyze(ai,bi); const r=an.r; return {w:r.w===null?null:F[r.w][1], kind:r.kind, how:r.how||(r.kind==='KO'?r.tick+'カウントでKO勝ち':r.kind==='判定'?'判定勝ち':r.kind), type:an.type||null}; }
function info(i){ const f=F[i]; return {title:f[1], name:f[0], q:f[2], stats:f[3], hold:!!HOLD[i], blocked:BLOCK.has(i)}; }
export {setup, loadOne, verdict, info};
"""
open(os.path.join(os.path.dirname(dst), 'engine.mjs'), 'w', encoding='utf-8').write(eng)
print('engine', len(eng))
