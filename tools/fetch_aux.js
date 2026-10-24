// 全記事版の補助データ：種類ごとの項目数（typeCnt）と人物の作品数（works）を検索で数える。区切って実行、次回は続きから。
// node fetch_aux.js <root> <seconds>   … root/aux_targets.json を読み、root/aux_type.jsonl, root/aux_works.jsonl に追記
'use strict';
const fs=require('fs'), path=require('path'); const W=require('./wm_vm.js');
const R=process.argv[2]; const T0=Date.now(); const DEADLINE=T0+(+process.argv[3]||140)*1000; const timeUp=()=>Date.now()>DEADLINE;
const TG=JSON.parse(fs.readFileSync(path.join(R,'aux_targets.json'),'utf8'));
const rdj=f=>fs.existsSync(f)?fs.readFileSync(f,'utf8').split('\n').filter(Boolean).map(l=>JSON.parse(l)):[];
const FT=path.join(R,'aux_type.jsonl'), FW=path.join(R,'aux_works.jsonl');
const doneT=new Set(rdj(FT).map(x=>x[0])), doneW=new Set(rdj(FW).map(x=>x[0]));
const PAR=+(process.env.MAXC||6);
async function run(list,fn){ for(let i=0;i<list.length&&!timeUp();i+=PAR) await Promise.all(list.slice(i,i+PAR).map(fn)); }
(async()=>{
 const T=TG.types.filter(q=>!doneT.has(q));
 await run(T,async q=>{ const r=await W.search('haswbstatement:P31='+q,1); fs.appendFileSync(FT,JSON.stringify([q,r.n])+'\n'); doneT.add(q); });
 const P=TG.persons.filter(([q])=>!doneW.has(q));
 if(!timeUp()) await run(P,async([q,mil])=>{ const w=await W.search('haswbstatement:"P50='+q+'|P170='+q+'|P86='+q+'|P57='+q+'|P175='+q+'|P161='+q+'|P725='+q+'"',50);
  let m=[]; if(mil) m=(await W.search('haswbstatement:P710='+q,50)).ids; fs.appendFileSync(FW,JSON.stringify([q,w.n,w.ids,m])+'\n'); doneW.add(q); });
 const line=JSON.stringify({t:new Date().toISOString(),type:doneT.size+'/'+TG.types.length,works:doneW.size+'/'+TG.persons.length,req:W.stats().nreq,sec:Math.round((Date.now()-T0)/1000)});
 fs.appendFileSync(path.join(R,'log_aux.txt'),line+'\n'); console.log(line); process.exit(0);
})().catch(e=>{ console.log('ERR',e.message); process.exit(1); });
