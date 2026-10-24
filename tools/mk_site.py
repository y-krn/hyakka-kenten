# 試作の page.html から、公開用（記事データを必要なときだけ読む版）の index.html を作る
# python3 mk_site.py <page.html> <out/index.html>
import sys, re
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

# 確認画面の枠と、使わなくなった表示を消す
rep('  <section id="review" class="card" hidden></section>\n', '')
open(dst, 'w', encoding='utf-8').write(s)
left = [w for w in ['DATA.', 'NAMES', 'recompute(', 'renderReview', 'dbRef', 'window.claude', 'isAdmin', "list=\"names\""] if w in s]
print('ok', len(s), 'leftover:', left)
