// Wikimedia API 共通（識別付き・同時接続制限・429/503 は Retry-After に従う）
'use strict';
const UA='WikiBattlerResearch/0.2 (https://github.com/y-krn; prototype game data build)';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let active=0; const MAXC=+(process.env.MAXC||3); const waitq=[];
const slot=async()=>{ while(active>=MAXC) await new Promise(r=>waitq.push(r)); active++; };
const free=()=>{ active--; const r=waitq.shift(); if(r) r(); };
let pauseUntil=0, nreq=0;
// Nodeのfetchは代理サーバー経由だと1本ずつしか流れないため、curlで取る
const {execFile}=require('child_process');
const curlJ=url=>new Promise(res=>execFile('curl',['-sS','--compressed','-m','60','-A',UA,'-w','\n%{http_code}','-D','-',url],{maxBuffer:256*1024*1024},(err,out)=>{
 if(err) return res({status:0}); const i=out.lastIndexOf('\n'); const code=+out.slice(i+1); let body=out.slice(0,i);
 const hEnd=body.lastIndexOf('\r\n\r\n'); const head=hEnd>=0?body.slice(0,hEnd):''; body=hEnd>=0?body.slice(hEnd+4):body;
 const ra=(head.match(/retry-after:\s*(\d+)/i)||[])[1]; res({status:code,ra,body}); }));
async function getJ(url){
 for(let k=0;k<6;k++){
  const w=pauseUntil-Date.now(); if(w>0) await sleep(Math.min(w,30000));
  await slot();
  try{ const r=await curlJ(url); nreq++;
   if(r.status===429||r.status===503){ pauseUntil=Math.max(pauseUntil,Date.now()+(+(r.ra||5)+1)*1000); continue; }
   if(r.status!==200){ await sleep(2000*(k+1)); continue; }
   return JSON.parse(r.body);
  }catch(e){ await sleep(2000*(k+1)); } finally{ free(); }
 }
 throw new Error('fail '+url.slice(0,120));
}
const KEEPP=new Set(['P31','P279','P225','P141','P138','P61','P112','P170','P50','P131','P276','P127','P137','P176','P361','P179','P449','P1433','P749','P710','P527','P1552','P2283','P39','P54','P607','P800','P106','P1399','P1196','P1889','P2067','P1082','P2046','P1128','P2109','P2895','P2527','P2044','P2048','P2660','P2052','P2043','P4511','P569','P570','P571','P577','P2031','P580','P575','P1619','P1191','P576','P2032','P582','P730','P585']);
const MAPP=["P1552","P1299","P1343","P793","P186","P166","P22","P25","P40","P3373","P1066","P802","P737","P463","P69","P108","P1412","P106","P101","P2579","P800","P1441","P136","P1830","P127","P84","P149","P1435","P366","P2283","P1365","P156","P4969","P1034","P397","P398","P47","P150","P190","P1376","P206","P706","P610","P2348","P135","P178","P176","P375","P3342","P19","P61","P941","P2670","P1344","P937"];
MAPP.forEach(p=>KEEPP.add(p));
const QQ=new Set(['P580','P582','P585','P574','P1350']);
const trim=e=>{ const c={}; for(const [p,ss] of Object.entries(e.claims||{})){ if(!KEEPP.has(p)) continue; c[p]=ss.map(s=>{ const o={rank:s.rank,mainsnak:{datavalue:s.mainsnak.datavalue?{value:s.mainsnak.datavalue.value}:undefined}}; if(s.qualifiers){ const q={}; for(const k of Object.keys(s.qualifiers)) if(QQ.has(k)) q[k]=s.qualifiers[k].map(x=>({datavalue:x.datavalue?{value:x.datavalue.value}:undefined})); if(Object.keys(q).length) o.qualifiers=q; } return o; }); }
 const sl=Object.keys(e.sitelinks||{}).filter(x=>/wiki$/.test(x)&&!/commons|species|wikidata|meta|wikimania|sources|quote|books|news|voyage|versity|wiktionary/.test(x)).length;
 return {id:e.id,jt:e.sitelinks&&e.sitelinks.jawiki&&e.sitelinks.jawiki.title,c,l:{ja:e.labels&&e.labels.ja&&e.labels.ja.value,en:e.labels&&e.labels.en&&e.labels.en.value},d:{ja:e.descriptions&&e.descriptions.ja&&e.descriptions.ja.value,en:e.descriptions&&e.descriptions.en&&e.descriptions.en.value},sl}; };
async function getEnts(list,withSL,ENTS,onProg){ const need=[...new Set(list)].filter(q=>/^Q\d+$/.test(q)&&!ENTS[q]); const jobs=[];
 for(let i=0;i<need.length;i+=50){ const part=need.slice(i,i+50);
  jobs.push(getJ('https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims|labels|descriptions'+(withSL?'|sitelinks':'')+'&languages=ja|en&ids='+part.join('|')).then(j=>{ Object.values(j.entities||{}).forEach(e=>{ if(e.id&&!e.missing) ENTS[e.id]=trim(e); }); if(onProg) onProg(Object.keys(ENTS).length); }));
  if(jobs.length>=4){ await Promise.all(jobs); jobs.length=0; } }
 await Promise.all(jobs); }
const LP=['P279','P31','P138','P61','P112','P170','P50','P131','P276','P137','P176','P127','P749','P449','P179','P361','P1433','P710','P527','P39','P607','P141','P106','P800','P1889',...MAPP];
const idv=s=>s&&s.mainsnak&&s.mainsnak.datavalue&&s.mainsnak.datavalue.value&&s.mainsnak.datavalue.value.id;
const linkedOf=(qs,ENTS,props=LP)=>{ const s=new Set(); qs.forEach(q=>{ const c=(ENTS[q]||{}).c||{}; props.forEach(p=>(c[p]||[]).forEach(x=>{ const v=idv(x); if(v) s.add(v); })); }); return [...s]; };
async function search(s,lim){ const j=await getJ('https://www.wikidata.org/w/api.php?action=query&format=json&list=search&srnamespace=0&srlimit='+lim+'&srsearch='+encodeURIComponent(s)); return {n:j.query.searchinfo.totalhits,ids:j.query.search.map(x=>x.title)}; }
module.exports={trim,getJ,getEnts,linkedOf,search,sleep,stats:()=>({nreq,pauseUntil})};
