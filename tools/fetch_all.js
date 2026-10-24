// 全記事版：Wikidata取得を「束（バッチ）」ごとに区切って進める。1回 DEADLINE 秒で止まり、次回は続きから。
// node fetch_all.js <root> <seconds>
//   root/batches/NNN.q   … その束の記事のQID（1行1件）
//   root/ents/NNN.jsonl  … その束で新たに取ったエンティティ
//   root/have_full.txt / have_lab.txt … どの束で取ったかに関係なく取得済みのID（重複取得を避ける）
//   root/p279.jsonl      … 上位クラス（P279）を持つものの [id,[P279...]]（クラスをたどるため）
//   root/miss.txt / state.json / log.txt
'use strict';
const fs=require('fs'), path=require('path'); const W=require('./wm_vm.js');
const R=process.argv[2]; const T0=Date.now(); const DEADLINE=T0+(+process.argv[3]||170)*1000;
const timeUp=()=>Date.now()>DEADLINE;
const rd=f=>fs.existsSync(f)?fs.readFileSync(f,'utf8'):'';
const ST=path.join(R,'state.json'); const S=fs.existsSync(ST)?JSON.parse(rd(ST)):{cur:0,phase:'main',depth:0};
const BATCHES=fs.readdirSync(path.join(R,'batches')).filter(f=>/\.q$/.test(f)).sort();
const haveF=new Set(rd(path.join(R,'have_full.txt')).split('\n').filter(Boolean));
const haveL=new Set(rd(path.join(R,'have_lab.txt')).split('\n').filter(Boolean));
const miss=new Set(rd(path.join(R,'miss.txt')).split('\n').filter(Boolean));
const P279={}; rd(path.join(R,'p279.jsonl')).split('\n').filter(Boolean).forEach(l=>{ const [i,a]=JSON.parse(l); P279[i]=a; });
const fF=fs.openSync(path.join(R,'have_full.txt'),'a'), fL=fs.openSync(path.join(R,'have_lab.txt'),'a'), fM=fs.openSync(path.join(R,'miss.txt'),'a'), fP=fs.openSync(path.join(R,'p279.jsonl'),'a');
const idv=s=>s&&s.mainsnak&&s.mainsnak.datavalue&&s.mainsnak.datavalue.value&&s.mainsnak.datavalue.value.id;
const ids=(e,p)=>((e&&e.c&&e.c[p])||[]).map(idv).filter(Boolean);
let ENTS={}, out=null, MAIN=[], got0=0;
function loadBatch(){ const b=BATCHES[S.cur]; const ef=path.join(R,'ents',b.replace(/\.q$/,'.jsonl'));
 MAIN=rd(path.join(R,'batches',b)).split('\n').filter(Boolean); ENTS={};
 rd(ef).split('\n').filter(Boolean).forEach(l=>{ const e=JSON.parse(l); ENTS[e.id]=e; });
 if(out) fs.closeSync(out); out=fs.openSync(ef,'a'); }
function store(e,labelsOnly){ ENTS[e.id]=e; fs.writeSync(out,JSON.stringify(e)+'\n'); got0++;
 if(labelsOnly){ haveL.add(e.id); fs.writeSync(fL,e.id+'\n'); }
 else { haveF.add(e.id); fs.writeSync(fF,e.id+'\n'); const p=ids(e,'P279'); if(p.length){ P279[e.id]=p; fs.writeSync(fP,JSON.stringify([e.id,p])+'\n'); } } }
// withClaims: 中身ごと取る / labelsOnly: 名前と説明だけ
async function fetchEnts(list,mode){ const full=mode!=='lab';
 const isMain=mode==='main'; const has=q=>isMain?!!(ENTS[q]&&ENTS[q].sl!==undefined&&ENTS[q].c):(haveF.has(q)||(!full&&haveL.has(q)));
 const need=[...new Set(list)].filter(q=>/^Q\d+$/.test(q)&&!miss.has(q)&&!has(q));
 const PAR=+(process.env.MAXC||3); for(let i=0;i<need.length&&!timeUp();i+=50*PAR){ const parts=[]; for(let k=0;k<PAR;k++){ const p=need.slice(i+50*k,i+50*k+50); if(p.length) parts.push(p);}
  await Promise.all(parts.map(async part=>{ const j=await W.getJ('https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props='+(full?'claims|labels|descriptions'+(mode==='main'?'|sitelinks':''):'labels|descriptions')+'&languages=ja|en&ids='+part.join('|'));
   const got=new Set(); Object.values(j.entities||{}).forEach(e=>{ if(e.id&&!e.missing&&(e.claims||!full)){ store(W.trim(e),!full); got.add(e.id);} });
   part.forEach(q=>{ if(!got.has(q)&&!has(q)){ miss.add(q); fs.writeSync(fM,q+'\n'); } }); })); }
 return need.filter(q=>!has(q)&&!miss.has(q)).length; }
const NEEDP=['P31','P279','P138','P61','P112','P170','P50','P131','P276','P137','P176','P127','P749','P449','P179','P361','P1433','P106'];
const p279of=q=>ENTS[q]&&ENTS[q].c&&Object.keys(ENTS[q].c).length?ids(ENTS[q],'P279'):(P279[q]||[]);
(async()=>{
 while(S.cur<BATCHES.length&&!timeUp()){
  loadBatch();
  if(S.phase==='main'){ const left=await fetchEnts(MAIN,'main'); if(!left) S.phase='linked'; }
  if(S.phase==='linked'&&!timeUp()){ const NEED=new Set(W.linkedOf(MAIN,ENTS,NEEDP)); const all=W.linkedOf(MAIN,ENTS);
   const l1=await fetchEnts(all.filter(q=>NEED.has(q)),'full'); let l2=1; if(!l1&&!timeUp()) l2=await fetchEnts(all.filter(q=>!NEED.has(q)),'lab'); if(!l1&&!l2) S.phase='l2'; }
  if(S.phase==='l2'&&!timeUp()){ const L1=W.linkedOf(MAIN,ENTS); const nx=new Set(); L1.forEach(q=>p279of(q).forEach(x=>nx.add(x)));
   const left=await fetchEnts([...nx],'full'); if(!left){ S.phase='class'; S.depth=0; } }
  if(S.phase==='class'&&!timeUp()){ // 記事のP31 → P279 を最大6段
   let fr=new Set(MAIN.flatMap(q=>ids(ENTS[q],'P31'))); for(let d=0;d<S.depth;d++){ const nx=new Set(); fr.forEach(q=>p279of(q).forEach(x=>nx.add(x))); fr=nx; }
   while(S.depth<6&&!timeUp()){ const left=await fetchEnts([...fr],'full'); if(left) break; const nx=new Set(); fr.forEach(q=>p279of(q).forEach(x=>nx.add(x))); fr=nx; S.depth++; }
   if(S.depth>=6){ S.cur++; S.phase='main'; S.depth=0; } }
  fs.writeFileSync(ST,JSON.stringify(S));
 }
 fs.writeFileSync(ST,JSON.stringify(S));
 const line=JSON.stringify({t:new Date().toISOString(),cur:S.cur,of:BATCHES.length,phase:S.phase,depth:S.depth,got:got0,req:W.stats().nreq,sec:Math.round((Date.now()-T0)/1000),full:haveF.size,lab:haveL.size,miss:miss.size});
 fs.appendFileSync(path.join(R,'log.txt'),line+'\n'); console.log(line); process.exit(0);
})().catch(e=>{ fs.writeFileSync(ST,JSON.stringify(S)); console.log('ERR',e.message); process.exit(1); });
