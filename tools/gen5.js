const TIER=(x,cuts,lg)=>{ if(x===null||x===undefined||isNaN(x)) return null; const f=v=>lg?Math.log10(Math.max(v,1e-12)):v; const X2=f(x), Kc=cuts.map(f); if(X2<Kc[0]) return 0; for(let i=0;i<Kc.length-1;i++) if(X2<Kc[i+1]) return i+1+(X2-Kc[i])/(Kc[i+1]-Kc[i]); return 5; };
const gen5=(store,K)=>{ const C=store.C, NOW=2026;
const vals=(c,p)=>(c[p]||[]).filter(s=>s.rank!=='deprecated');
const pref=(c,p)=>{const a=vals(c,p); const pr=a.filter(s=>s.rank==='preferred'); return pr.length?pr:a;};
const idv=s=>s.mainsnak?.datavalue?.value?.id; const ids=(c,p)=>vals(c,p).map(idv).filter(Boolean);
const yOf=t=>{if(!t) return null; const m=String(t).match(/^([+-]\d+)-/); return m?parseInt(m[1]):null;};
const years=(c,ps)=>ps.flatMap(p=>pref(c,p).map(s=>yOf(s.mainsnak?.datavalue?.value?.time))).filter(y=>y!==null);
const qy=(s,k)=>yOf(s.qualifiers?.[k]?.[0]?.datavalue?.value?.time);
const CONV={P2067:{Q11570:1,Q41803:0.001,Q191118:1000,Q100995:0.45359,Q180892:1.989e30,Q651336:1.898e27},P1082:{'1':1,Q199:1},P2046:{Q712226:1,Q25343:1e-6,Q35852:0.01,Q706688:3.3058e-6,Q232291:2.59},P1128:{'1':1,Q199:1,Q1543700:1},P2109:{Q25236:1,Q3320608:1e3,Q6982035:1e6,Q160857:735.5,Q2276380:745.7},P2895:{Q180154:1,Q182429:3.6,Q211256:1.609344,Q128822:1.852},P2527:{'1':1,Q199:1},P2044:{Q11573:1,Q828224:1000,Q174728:0.01,Q174789:0.001,Q3710:0.3048,Q218593:0.0254},P2048:{Q11573:1,Q828224:1000,Q174728:0.01,Q174789:0.001,Q3710:0.3048,Q218593:0.0254},P2660:{Q11573:1,Q828224:1000,Q174728:0.01,Q174789:0.001,Q3710:0.3048},P2052:{Q180154:1,Q182429:3.6,Q211256:1.609344,Q128822:1.852}};
const qty=(c,p)=>{const conv=CONV[p]; let best=null; for(const s of pref(c,p)){const v=s.mainsnak?.datavalue?.value; if(!v||v.amount===undefined) continue; const u=(v.unit||'1').split('/').pop(); const f=conv[u]; if(f===undefined) continue; const x=parseFloat(v.amount)*f; if(best===null||x>best) best=x;} return best;};
const tier=TIER;
const mx=(...a)=>{const b=a.filter(v=>v!==null&&v!==undefined); return b.length?Math.max(...b):null;};
const DC=K.direct; const dt=(c,p)=>tier(qty(c,p),DC[p].cuts,DC[p].log);
const lab=q=>C[q]?((C[q].ja||'')+' '+(C[q].en||'')).toLowerCase():'';
const OCC={mil:/武将|軍人|大名|武士|軍事|司令|将軍|military|soldier|samurai|general|daimyo/,pol:/政治家|君主|天皇|皇帝|国王|大臣|首相|大統領|politician|monarch|emperor|king/,wrk:/作家|小説家|詩人|画家|作曲家|音楽家|漫画家|学者|哲学者|数学者|物理学者|化学者|歌手|俳優|声優|映画監督|イラストレーター|歴史家|評論家|ジャーナリスト|writer|novelist|poet|painter|composer|musician|scientist|philosopher|mathematician|singer|actor|director|author|artist|illustrator|historian/};
const START=['P569','P571','P577','P2031','P580','P575','P1619','P1191'], END=['P570','P576','P2032','P582','P730'];
const LINKG=[['P138','P61','P112','P170','P50'],['P131','P276'],['P137','P176','P127','P749'],['P449','P179','P361','P1433']];
const endRe=/(\d{3,4})年(?:に)?(没|解散|廃止|閉鎖|閉館|閉校|廃校|消滅|終了|廃線|休止|引退|退役|解体|滅亡|閉店|閉園)/;
const catYears=(t)=>{const cs=store.cats[t]||[]; const st=[],en=[]; let living=false, born=null, died=null;
 for(const c of cs){ if(c==='存命人物') living=true; const mb=c.match(/^(紀元前)?(\d{3,4})年生$/); if(mb) born=(mb[1]?-1:1)*(+mb[2]); const md=c.match(/^(紀元前)?(\d{3,4})年没$/); if(md) died=(md[1]?-1:1)*(+md[2]);
  const me=c.match(endRe); if(me){en.push(+me[1]); continue;} const m=c.match(/(紀元前)?(\d{3,4})年(?!代)/); if(m) st.push((m[1]?-1:1)*(+m[2])); }
 return {start:st.length?Math.min(...st):null,end:en.length?Math.min(...en):null,living,born,died};};
const base=t=>t.replace(/\s*[（(][^）)]*[）)]\s*$/,'');
const toHira=s=>s.replace(/[ァ-ヶ]/g,c=>String.fromCharCode(c.charCodeAt(0)-0x60));
const isKana=s=>/^[ぁ-ゖァ-ヺー・\s]+$/.test(s);
const reading=r=>{ const b=base(r.t); if(isKana(b)) return toHira(b); const d=store.ds[r.t]; if(d&&/[ぁ-ゖァ-ヺ]/.test(d)) return toHira(d.replace(/[\s,、・]/g,'')); return null; };
const mora=s=>[...s].filter(ch=>/[ぁ-ゖー]/.test(ch)&&!/[ゃゅょぁぃぅぇぉゎ]/.test(ch)).length;
const titleFeat=r=>{const b=[...base(r.t)]; const y=reading(r); const m=y?mora(y):Math.round(b.length*1.5); const dens=y? m/Math.max(1,b.length) : 1+b.filter(ch=>/\p{Script=Han}/u.test(ch)).length/Math.max(1,b.length); return {m,dens,y};};
const titleT=r=>{const f=titleFeat(r); const tl=tier(f.m,K.titleLen,false), td=tier(f.dens,K.titleDens,false); return [tl,Math.max(0,4-tl),td,Math.max(0,4-td)];};
const directT=c=>({HP:mx(dt(c,'P2067'),dt(c,'P1082'),dt(c,'P2046'),dt(c,'P1128')),ATK:mx(dt(c,'P2109'),dt(c,'P2895'),dt(c,'P2527')),DEF:mx(dt(c,'P2044'),dt(c,'P2048'),dt(c,'P2660')),SPD:dt(c,'P2052')});
const timeAx=(start,end,isP,living)=>{const o={}; if(start===null) return o; const st=tier(start,K.spdc,false); o.SPD=st; o.DEF=Math.max(0,4-st); let per=null; if(end!==null) per=Math.max(0,end-start); else if(!isP||living) per=NOW-start; if(per!==null){let ht=tier(per,K.perc,false); if(isP&&end===null) ht=Math.max(ht,2); o.HP=ht; if(!isP) o.ATK=Math.max(0,4-ht);} return o;};
const lite=q=>{ if(!C[q]) return {}; const c=C[q].c; const isP=ids(c,'P31').includes('Q5'); const o={}; if(!isP){const d=directT(c); for(const k in d) if(d[k]!==null) o[k]=d[k];}
 const ys=years(c,START), ye=years(c,END); const ta=timeAx(ys.length?Math.min(...ys):null, ye.length?Math.min(...ye):null, isP, !ye.length); for(const k in ta) if(o[k]===undefined) o[k]=ta[k]; return o;};
const KK=['HP','ATK','DEF','SPD']; const out=[];
for(const r of store.res){ const c=C[r.q].c; const isP=ids(c,'P31').includes('Q5'); const taxon=vals(c,'P225').length>0; const cand={HP:[],ATK:[],DEF:[],SPD:[]};
 const add=(k,v,s)=>{ if(v!==null&&v!==undefined&&!isNaN(v)) cand[k].push({v:Math.max(0,Math.min(5,v)),s}); };
 const cy=catYears(r.t); let timeO={}, timeSrc='y';
 if(isP){ let b=years(c,['P569'])[0]??null, d=years(c,['P570'])[0]??null, bs='w';
  if(b===null&&cy.born!==null){b=cy.born; bs='k';} if(d===null&&cy.died!==null) d=cy.died;
  const living=d===null&&(cy.living||(b!==null&&b>=1930));
  if(b!==null&&(d!==null||living)){let h=tier((d??NOW)-b,K.life,false); if(d===null) h=Math.max(h,2); add('HP',h,bs==='k'?'k':'p');}
  const occ=ids(c,'P106').map(lab).join(' '); const at=[]; const rv=store.rev[r.q]||{};
  if(OCC.mil.test(occ)){const u=new Set([...ids(c,'P607'),...(rv.mil||[])]).size; if(u) at.push(tier(u,K.count,true));}
  if(OCC.pol.test(occ)){const n=vals(c,'P39').length; if(n) at.push(tier(n,K.count,true));}
  if(OCC.wrk.test(occ)){let u=new Set([...ids(c,'P800'),...(rv.wrk||[])]).size; if((rv.wrk||[]).length>=50) u=Math.max(u,rv.wrkTotal||0); if(u) at.push(tier(u,K.count,true));}
  const st54=vals(c,'P54'); if(st54.length){let apps=0; st54.forEach(s=>{const a=s.qualifiers?.P1350?.[0]?.datavalue?.value?.amount; if(a!==undefined) apps+=+a;}); at.push(apps>0?tier(apps,K.apps,true):tier(st54.length,K.count,true));}
  if(at.length) add('ATK',Math.max(...at),'p');
  const ten=[...vals(c,'P39'),...st54].map(s=>{const a=qy(s,'P580'),e=qy(s,'P582'); return (a!==null&&e!==null)?e-a:null;}).filter(x=>x!==null); if(ten.length) add('DEF',tier(Math.max(...ten),K.tenure,false),'p');
  const ach=[...vals(c,'P39').map(s=>qy(s,'P580')),...vals(c,'P607').flatMap(s=>[qy(s,'P580'),qy(s,'P585')])].filter(x=>x!==null); if(ach.length&&b!==null&&!st54.length){const age=Math.min(...ach)-b; add('SPD',[50,40,30,25,20].filter(k=>age<=k).length,'p');}
  timeO=timeAx(b,d,true,living); timeSrc=bs==='k'?'k':'y';
 } else if(taxon){ const y=vals(c,'P225').map(s=>qy(s,'P574')).filter(x=>x!==null)[0]??null; const iu=idv(pref(c,'P141')[0]||{}); const IU={Q211005:3,Q719675:2,Q278113:1,Q11394:0,Q219127:0};
  const d=directT(c); add('HP',d.HP,'d'); add('SPD',d.SPD,'d'); if(iu&&IU[iu]!==undefined) add('DEF',IU[iu],'x'); if(y!==null){const st=tier(y,K.spdc,false); add('SPD',st,'x'); add('DEF',Math.max(0,4-st),'x');}
 } else {
  if((store.typeCnt[r.q]||0)>0){ add('HP',tier(store.typeCnt[r.q],K.spread,true),'c'); const n=['P527','P1552','P2283'].reduce((s,p)=>s+vals(c,p).length,0); if(n) add('ATK',tier(n,[1,2,3,5,8],false),'c'); }
  const d=directT(c); for(const k of KK) add(k,d[k],'d');
  const ys=years(c,START), ye=years(c,END); let s0=ys.length?Math.min(...ys):null, e0=ye.length?Math.min(...ye):null;
  if(s0===null&&cy.start!==null){s0=cy.start; timeSrc='k';} if(e0===null&&cy.end!==null) e0=cy.end;
  timeO=timeAx(s0,e0,false,true);
 }
 for(const [a,b] of [['SPD','DEF'],['HP','ATK']]){ if(timeO[a]===undefined) continue; if(!cand[a].length&&!cand[b].length){ add(a,timeO[a],timeSrc); if(timeO[b]!==undefined) add(b,timeO[b],timeSrc);} }
 const t={}, src={};
 for(const k of KK){ const cs=cand[k]; if(!cs.length) continue; t[k]=cs[0].v; src[k]=cs[0].s; }
 if(KK.some(k=>t[k]===undefined)){ let cl=[]; if(!isP&&!taxon){const L1=ids(c,'P279'); const L2=L1.flatMap(q=>C[q]?ids(C[q].c,'P279'):[]); const tx=[...L1,...L2].find(q=>C[q]&&vals(C[q].c,'P225').length); if(tx) cl.push(tx);}
  for(const g of LINKG) for(const p of g){const v=ids(c,p)[0]; if(v) cl.push(v);}
  for(const q of cl){ let lt=lite(q); if(C[q]&&vals(C[q].c,'P225').length){const y=vals(C[q].c,'P225').map(s=>qy(s,'P574')).filter(x=>x!==null)[0]; lt={}; if(y!=null){const st=tier(y,K.spdc,false); lt.SPD=st; lt.DEF=Math.max(0,4-st);}}
   if(Object.keys(lt).length){ for(const k in lt) if(t[k]===undefined){t[k]=2+(lt[k]-2)/2; src[k]='i';} break; } } }
 const tt=titleT(r);
 KK.forEach((k,i)=>{ if(t[k]===undefined){t[k]=2+(tt[i]-2)/2; src[k]='t';} });
 out.push({t:r.t,q:r.q,person:isP,raw:KK.map(k=>t[k]),src:KK.map(k=>src[k]).join(''),tt,feat:titleFeat(r)}); }
return out;};
module.exports={gen5,TIER};
