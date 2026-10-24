// Wikipediaバトラー：対戦データの一括生成（v2）
// 入力（すべて JSONL / JSON、取得工程は fetch_*.js が用意する）
//   arts.jsonl   : 記事ごと {t,q,cats[],sec,out,inl,bytes,pop,open,ds,disamb,img}
//   ents.jsonl   : Wikidata 項目 {id,c(claims),l:{ja,en},d:{ja,en},sl}
//   aux.json     : {typeCnt:{q:n}, rev:{q:{mil:[],wrk:[],wrkTotal}}, works:{q:n}, cls:{q:[...]}, pvScale}
// 出力：big_v2.json（build_big.py が読む big.json と同じ形）
'use strict';
const fs=require('fs'), path=require('path');
const {gen5,TIER:tier}=require('./gen5.js');
const DIR=process.argv[2]||'.';
// 大きなファイルも読めるよう、バイト列のまま行に分ける
const readJL=f=>{ const buf=fs.readFileSync(path.join(DIR,f)); const out=[]; let s=0; for(let i=0;i<=buf.length;i++){ if(i===buf.length||buf[i]===10){ if(i>s) out.push(JSON.parse(buf.toString('utf8',s,i))); s=i+1; } } return out; };

/* ---------- 校正済みの区切り（既存1,122記事から逆算／不明分は仮置き） ---------- */
const K={
 direct:{P2048:{cuts:[0.35,1.11,2.315,30,102],log:true},P2044:{cuts:[18,128,353,924,1751],log:true},
  P2067:{cuts:[0.129,52.4,8100,5.62e27,3.62e30],log:true},P2046:{cuts:[3.81,28.47,235.12,2336,15101],log:true},
  P1082:{cuts:[741,4562,28522,178380,1131016],log:true},P2052:{cuts:[30,46.3,66.7,160.9,592],log:true},
  // 以下は旧データに例がなく仮置き
  P1128:{cuts:[10,100,1000,1e4,1e5],log:true},P2109:{cuts:[1e2,1e4,1e6,1e8,1e9],log:true},
  P2895:{cuts:[30,100,300,1000,1e4],log:true},P2527:{cuts:[3,5,6,7,8.5],log:false},P2660:{cuts:[100,300,1000,2000,4000],log:true}},
 titleLen:[4,7,9,13,19], titleDens:[0.75,1,1.5,2,2.25],
 count:[1,1.5,4,19,70], tenure:[1,5,10,20,40], spread:[1,1.5,3,12,26],
 spdc:null, perc:null, life:null, apps:null };     // 未確定：fit_k.js で既存データから逆算して上書き
const OFF={p0:-0.5,p1:-0.53,p2:-0.17,y0:-0.58,y1:0.48,y2:0.4,y3:-0.47,k0:-0.26,k1:0.21,k2:1.1,k3:-1.35,i0:-0.91,i1:0.68,i2:0.03,i3:0.14,d0:-0.96,d2:-0.41,c0:-0.49,t0:-0.22,t1:0.12,t2:-0.38,t3:0.27};
if(fs.existsSync(path.join(DIR,'k_fit.json'))) Object.assign(K,JSON.parse(fs.readFileSync(path.join(DIR,'k_fit.json'),'utf8')));

/* ---------- 共通 ---------- */
const vals=(c,p)=>(c&&c[p]||[]).filter(s=>s.rank!=='deprecated');
const pref=(c,p)=>{const a=vals(c,p); const pr=a.filter(s=>s.rank==='preferred'); return pr.length?pr:a;};
const idv=s=>s&&s.mainsnak&&s.mainsnak.datavalue&&s.mainsnak.datavalue.value&&s.mainsnak.datavalue.value.id;
const ids=(c,p)=>vals(c,p).map(idv).filter(Boolean);
const yOf=t=>{if(!t) return null; const m=String(t).match(/^([+-]\d+)-/); return m?parseInt(m[1]):null;};
const qy=(s,k)=>yOf(s.qualifiers&&s.qualifiers[k]&&s.qualifiers[k][0]&&s.qualifiers[k][0].datavalue&&s.qualifiers[k][0].datavalue.value.time);
const JP=/[ぁ-んァ-ヶ一-龯]/;
const LEN={Q11573:1,Q828224:1000,Q174728:0.01,Q174789:0.001,Q3710:0.3048,Q218593:0.0254,Q253276:1609.344};
const CONV={P2067:{Q11570:1,Q41803:0.001,Q191118:1000,Q100995:0.45359,Q180892:1.989e30,Q651336:1.898e27},P1082:{'1':1,Q199:1},P2046:{Q712226:1,Q25343:1e-6,Q35852:0.01,Q706688:3.3058e-6,Q232291:2.59},P2044:LEN,P2048:LEN,P2043:LEN,P4511:LEN,P2052:{Q180154:1,Q182429:3.6,Q211256:1.609344,Q128822:1.852}};
const qty=(c,p)=>{let best=null; for(const s of pref(c,p)){const v=s.mainsnak.datavalue&&s.mainsnak.datavalue.value; if(!v||v.amount===undefined) continue; const u=(v.unit||'1').split('/').pop(); const f=CONV[p][u]; if(f===undefined) continue; const x=parseFloat(v.amount)*f; if(best===null||x>best) best=x;} return best;};
const START=['P569','P571','P577','P2031','P580','P575','P1619','P1191'], END=['P570','P576','P2032','P582','P730'];
const jn=n=>{ n=+n; if(n<1e8) return Math.round(n).toLocaleString('ja-JP'); if(n>=1e20){ const e=Math.floor(Math.log10(n)); return '約'+(n/10**e).toFixed(1)+'×10'+String(e).replace(/\d/g,d=>'⁰¹²³⁴⁵⁶⁷⁸⁹'[d]); }
 const U=[[1e16,'京',1e12,'兆'],[1e12,'兆',1e8,'億'],[1e8,'億',1e4,'万']].find(u=>n>=u[0]); const a=Math.floor(n/U[0]); const b=Math.round((n-a*U[0])/U[2]); return a.toLocaleString('ja-JP')+U[1]+(b?b+U[3]:''); };
const fmt=(v,d=0)=>(+v).toLocaleString('ja-JP',{maximumFractionDigits:d});
const yS=y=>y<=-1e4?jn(-y)+'年前':y<0?'紀元前'+(-y)+'年':y+'年';

/* ---------- 入力 ---------- */
const ARTS=readJL('arts.jsonl'); const E={}; readJL('ents.jsonl').forEach(e=>E[e.id]=e);
const AUX=JSON.parse(fs.readFileSync(path.join(DIR,'aux.json'),'utf8'));
const lab=q=>E[q]?((E[q].l&&(E[q].l.ja||E[q].l.en))||q):q;
const labJ=q=>{const l=E[q]&&E[q].l&&E[q].l.ja; return l&&JP.test(l)&&!/一覧|ウィキメディア/.test(l)&&!/^\d+$/.test(l)?l:null;};
const desJ=q=>{const d=E[q]&&E[q].d&&E[q].d.ja; return d&&!/ウィキメディア/.test(d)?d:'';};
const desAny=q=>desJ(q)||(E[q]&&E[q].d&&E[q].d.en?E[q].d.en+'（英語の説明のみ）':'');

/* ---------- 扱わない題材の判定（judge6 相当＋保留） ---------- */
const EV=/(事件|事故|災害|(?<![スアヘ])テロ(?![イーメップ])|虐殺|殺人|誘拐|水害|豪雨|震災|地震|津波|噴火|大火|火災|空襲|銃撃|乱射|暗殺|爆破|墜落|沈没|遭難|戦争$|の戦い$|紛争|内戦)/;
const NEG=/(題材|扱った|を描いた|作品|映画|フィクション|架空|ドラマ|小説|漫画|アニメ|楽曲|歌|ゲーム|学者|研究|学$|機関|組織|法$|法令|拠点|対策|防災|補償|予知|保険|医学|工学|シリーズ|病院|条約|アルカロイド)/;
const PER=/(自殺した|殺害された|暗殺された|処刑された|死刑囚|殺人犯|テロリスト|犯罪者|被害者|犠牲者|スプリーキラー|シリアルキラー|連続殺人犯|事件の当事者)/;
const TITLE=/(事件|事故|災害|大震災|地震|豪雨|水害|空襲|テロ|虐殺|乱射|墜落|沈没)(\s*\(.+\))?$/;
const EVW=/(事件|事故|(?<![スアヘ])テロ(?![イーメップ])|虐殺|殺人|誘拐|大火|空襲|銃撃|乱射|暗殺|爆破|墜落|遭難|迫害|侵攻|ホロコースト|原爆|核実験|ミサイル発射|犠牲者|慰霊|大爆撃|難民)/;
const CUT=1900, NOW=2026;
const yr1=(c,p)=>{const s=(c[p]||[]).find(s=>s.mainsnak.datavalue&&s.mainsnak.datavalue.value.time); return s?parseInt(s.mainsnak.datavalue.value.time):null;};
function judge(a,e){ const title=a.t, cats=a.cats||[], c=e.c||{}, cls=(AUX.cls||{})[a.q]||[];
 const isH=ids(c,'P31').includes('Q5')||cats.includes('存命人物')||cats.some(x=>/^\d+年(生|没)$/.test(x));
 if(isH){ const b=yr1(c,'P569'); let d=yr1(c,'P570'); if(d===null){const x=cats.find(x=>/^\d+年没$/.test(x)); if(x) d=parseInt(x);}
  const living=cats.includes('存命人物')||(d===null&&b!==null&&b>=NOW-110);
  const conv=ids(c,'P1399').length>0, mod=ids(c,'P1196'), pc=cats.filter(x=>PER.test(x));
  const crim=conv||pc.some(x=>/犯罪者|殺人犯|死刑囚|テロリスト|キラー/.test(x));
  if(crim&&(living||d===null||d>=CUT)) return ['除外','犯罪の記録'];
  if((living||(d!==null&&d>=CUT))&&(mod.some(m=>['Q149086','Q10737','Q132821'].includes(m))||pc.length)) return ['除外','死因・事件の当事者'];
  if(d!==null&&d>=2025) return ['除外','最近亡くなった人物（'+d+'年）'];
  if(living) return ['配慮','存命人物'];
  if(d!==null&&d>=2016) return ['配慮','2016年以降に亡くなった人物'];
  const anc=cats.some(x=>/(時代|世紀|古代|中世|近世|朝の)/.test(x)); const by=b!==null?b:(()=>{const x=cats.find(x=>/^\d+年生$/.test(x)); return x?parseInt(x):null;})();
  if(pc.length&&d===null&&!anc) return ['保留','人物カテゴリ「'+pc[0]+'」'];
  if(d===null&&by===null&&!anc) return ['配慮','生没年不明の人物'];
  if(d===null&&by!==null&&by>=1890) return ['配慮','没年不明の人物（'+by+'年生まれ）'];
  return ['通常','']; }
 const t=[yr1(c,'P582'),yr1(c,'P585'),yr1(c,'P580'),yr1(c,'P571')].filter(x=>x!==null);
 const cys=cats.map(x=>{const m=x.match(/^(\d{3,4})年/); return m?+m[1]:null;}).filter(x=>x!==null);
 const last=t.length?Math.max(...t):(cys.length?Math.max(...cys):null);
 const ec=cats.filter(x=>EV.test(x)&&!NEG.test(x)); const ti=TITLE.test(title)&&!/一覧/.test(title);
 const strong=cls.length||ti||ec.length>=2; const why=cls.length?'Wikidataの分類「'+cls[0]+'」':ti?'記事名':ec.length?'カテゴリ「'+ec[0]+'」':null;
 if(strong){ if(last!==null&&last<CUT) return ['配慮','歴史上の出来事（'+(last<0?'紀元前'+(-last):last)+'年）：'+why];
  if(last===null&&!cls.length&&!ti) return ['保留','事件系カテゴリ'+ec.length+'個（年不明）'];
  return ['除外',why+(last===null?'（年不明）':'（'+last+'年）')]; }
 if(last!==null&&last<CUT) return ['通常',''];
 if(ec.length===1) return ['保留','カテゴリ「'+ec[0]+'」'+(last!==null?'（'+last+'年）':'')];
 const pcs=cats.filter(x=>PER.test(x)&&!/(題材|扱った|を描いた|作品|映画|ドラマ|小説|漫画|アニメ)/.test(x)); if(pcs.length) return ['保留','カテゴリ「'+pcs[0]+'」'];
 const bt=title.replace(/\s*\(.+\)$/,''); const m=bt.match(EVW); const WORK=['Q11424','Q5398426','Q21198342','Q8274','Q7725634','Q8261','Q63952888','Q7889','Q482994','Q7366','Q571','Q1259759','Q24856','Q74262765','Q1107','Q47461344']; if(m&&!NEG.test(bt)&&!ids(c,'P31').some(x=>WORK.includes(x))) return ['保留','記事名に「'+m[1]+'」'];
 return ['通常','']; }

/* ---------- 実行 ---------- */
const BAD=['Q4167410','Q13406463','Q4167836','Q11266439','Q17633526','Q15184295','Q14204246'];
const keep=[], DROP=[], HOLD={};
for(const a of ARTS){ const e=E[a.q]; if(!e||!e.c){ DROP.push([a.grp||'',a.t,'Wikidataなし']); continue; }
 if(a.disamb||ids(e.c,'P31').some(x=>BAD.includes(x))||/一覧$/.test(a.t)){ DROP.push([a.grp||'',a.t,'一覧・曖昧さ回避']); continue; }
 const j=judge(a,e); if(j[0]==='除外'){ DROP.push([a.grp||'',a.t,'除外：'+j[1]]); continue; }
 keep.push({a,e,judge:j}); }

// 能力値（gen5）
const C={}; for(const [q,e] of Object.entries(E)) if(e.c) C[q]={c:e.c,ja:(e.l&&e.l.ja)||'',en:(e.l&&e.l.en)||''};
const store={C,cats:Object.fromEntries(keep.map(k=>[k.a.t,k.a.cats||[]])),typeCnt:AUX.typeCnt||{},rev:AUX.rev||{},ds:Object.fromEntries(keep.map(k=>[k.a.t,k.a.ds||null])),res:keep.map(k=>({t:k.a.t,q:k.a.q}))};
const G5=gen5(store,K); const FI={};
for(const o of G5){ const tt=o.raw.map((v,i)=>{const s=o.src[i]; let x=v+(OFF[s+i]??0); if(s!=='t') x+=(o.tt[i]-2)*0.125; return Math.max(0,Math.min(5,x));});
 FI[o.q]={tiers:tt,src:o.src,mora:o.feat.m}; }

// 技
const REL={P138:['本家召喚','名前の由来'],P112:['生みの親召喚','生みの親'],P61:['生みの親召喚','生みの親'],P170:['生みの親召喚','生みの親'],P50:['生みの親召喚','生みの親'],P361:['親分召喚','所属先'],P179:['シリーズ召喚','シリーズ']};
const STIER={'本家召喚':3,'生みの親召喚':3,'親分召喚':2,'シリーズ召喚':2,'両陣営召喚':2};
const PW={P569:'生まれ',P571:'成立',P577:'公開',P575:'発見',P1619:'開業',P580:'開始',P2031:'活動開始',P1191:'初演'};
const okT=q=>!!labJ(q)&&!/ウィキメディアの/.test(desJ(q));
const tgt=q=>[labJ(q),desAny(q),q];
function yearOf(c){ if(vals(c,'P225').length){ const p580=pref(c,'P580').map(s=>yOf(s.mainsnak.datavalue&&s.mainsnak.datavalue.value.time)).filter(y=>y!==null)[0];
  if(p580!==undefined) return {y:p580,txt:yS(p580)+'から存在'}; const ty=vals(c,'P225').map(s=>qy(s,'P574')).filter(x=>x!==null)[0]; if(ty!==undefined) return {y:ty,txt:ty+'年に学名がついた'}; }
 for(const p of START){ const y=pref(c,p).map(s=>yOf(s.mainsnak.datavalue&&s.mainsnak.datavalue.value.time)).filter(y=>y!==null); if(y.length){ const v=Math.min(...y); return {y:v,txt:yS(v)+(v<=-1e4?'に誕生':(PW[p]||'成立'))}; } }
 return null; }
function baseMoves(k){ const q=k.a.q, c=k.e.c, isP=ids(c,'P31').includes('Q5'), living=/存命|2016|不明/.test(k.judge[1]), M=[];
 const add=(kind,name,fact,t,extra={})=>M.push([kind,name,fact,extra.card||fact,+(t||0).toFixed(2),extra.once?1:0,extra.tpl||0,...(extra.targets?[extra.targets]:[])]);
 const cuts=p=>K.direct[p].cuts;
 if(!isP){ const Q={}; for(const p of Object.keys(CONV)){ const x=qty(c,p); if(x!==null) Q[p]=x; }
  if(Q.P2044) add('STRIKE','標高落とし','標高'+fmt(Q.P2044)+'m',tier(Q.P2044,cuts('P2044'),true));
  if(Q.P2048&&!living) add('STRIKE','急降下','高さ'+fmt(Q.P2048,1)+'m',tier(Q.P2048,cuts('P2048'),true));
  if(Q.P2067&&!living) add('STRIKE','のしかかり','体重'+(Q.P2067<1?Math.round(Q.P2067*1000).toLocaleString('ja-JP')+'g':jn(Q.P2067)+'kg'),tier(Q.P2067,cuts('P2067'),true));
  if(Q.P2046) add('SLOW','領土拡大','面積'+jn(Q.P2046)+'km²',tier(Q.P2046,cuts('P2046'),true));
  if(Q.P1082) add('MULTI','人海戦術','人口'+jn(Q.P1082)+'人',tier(Q.P1082,cuts('P1082'),true));
  if(Q.P2052) add('HASTE','全力疾走','時速'+fmt(Q.P2052)+'km',tier(Q.P2052,cuts('P2052'),true));
  if(Q.P2043&&Q.P2043>=1000) add('BIND','全長包囲','全長'+jn(Q.P2043/1000)+'km',tier(Q.P2043,[100,1000,1e4,1e5,1e6],true));
  if(Q.P4511) add('STRIKE','深淵送り','最大水深'+fmt(Q.P4511,1)+'m',tier(Q.P4511,[5,20,50,100,500],true));
  const tc=(AUX.typeCnt||{})[q]||0; if(tc>0) add('MULTI','同族召喚','記録上の仲間'+fmt(tc)+'件',tier(tc,K.spread,true));
  const iu=idv(pref(c,'P141')[0]); if(iu&&labJ(iu)) add('GUARD','保護動物の構え',labJ(iu),3);
  const parts=[...new Set(ids(c,'P527'))].filter(okT); if(parts.length>=2){ const ls=parts.slice(0,2).map(labJ); const n=parts.length;
   add('STRIKE','総力戦',ls.join('・')+'など'+n+'件',tier(n,[1,2,3,5,8],false),{card:'構成要素：'+ls.join('・')+'など全'+n+'件',tpl:'{A}の【{N}】！ '+ls.join('・')+'など、{A}を構成する'+n+'個の要素が総出で{B}に襲いかかる。'}); }
  const pt=[...new Set(ids(c,'P710'))].filter(okT); if(pt.length>=2){ const it=pt.slice(0,2); add('SUMMON','両陣営召喚',it.map(labJ).join('と'),STIER['両陣営召喚'],{card:'参戦者：'+it.map(labJ).join('、'),once:1,targets:it.map(tgt)}); }
 } else {
  const rv=(AUX.rev||{})[q]||{mil:[],wrk:[]}; const bc=new Set([...ids(c,'P607'),...(rv.mil||[])]).size;
  if(bc>0) add('GUARD','歴戦の構え','記録された参戦'+bc+'件',tier(bc,K.count,true));
  const pos=vals(c,'P39').map(s=>({label:labJ(idv(s)),s:qy(s,'P580'),e:qy(s,'P582')})).filter(p=>p.label&&p.s!==null&&p.e!==null&&p.e>p.s).sort((a,b)=>(b.e-b.s)-(a.e-a.s))[0];
  if(pos) add('HEAL','長期政権',pos.label+'在任'+(pos.e-pos.s)+'年',tier(pos.e-pos.s,K.tenure,false),{once:1});
  let w=new Set([...ids(c,'P800'),...(rv.wrk||[])]).size; const W=(AUX.works||{})[q]; if(W!==undefined&&W>w) w=W;
  if(w>0) add('MULTI','作品ラッシュ','登録作品'+w+'件',tier(w,K.count,true));
 }
 const byRel={}, seen=new Set();
 const push=(p,tq)=>{ const r=REL[p]; if(!r||seen.has(tq)||!okT(tq)) return; seen.add(tq); (byRel[r[0]]=byRel[r[0]]||{rel:r[1],items:[]}).items.push(tq); };
 ids(c,'P138').forEach(x=>push('P138',x)); for(const p of ['P61','P112','P170','P50','P361','P179']) ids(c,p).forEach(x=>push(p,x));
 for(const [name,v] of Object.entries(byRel)){ const it=v.items.slice(0,2); const ls=it.map(labJ); add('SUMMON',name,ls.join('と'),STIER[name],{card:v.rel+'：'+ls.join('、'),once:1,targets:it.map(tgt)}); }
 const yo=yearOf(c); if(yo) add('SENIORITY','年功序列',yo.txt,0);
 if(M.length<2&&!M.some(m=>m[0]==='NAME')) add('NAME','名前で殴る',FI[q].mora+'音',2,{card:'名前の音の数：'+FI[q].mora+'音'});
 return {M,yo}; }

// MAP（ページ側の技一覧）を page.html から読む
const PAGE=fs.readFileSync(path.join(__dirname,'..','proto','page.html'),'utf8');
const MAPKEYS={}; for(const m of PAGE.matchAll(/^ (P\d+):\['([A-Z])'/gm)) MAPKEYS[m[1]]=m[2];
const LIVING_SKIP=['P22','P25','P40','P3373','P19','P69','P108','P1066','P802','P26','P451','P2048','P2067'];

const recs=[];
for(const k of keep){ const q=k.a.q, c=k.e.c; if(!FI[q]) continue; const {M,yo}=baseMoves(k); const living=/存命|2016|不明/.test(k.judge[1]);
 const QT={}; const pk=(kk,p,div=1)=>{ const x=qty(c,p); if(x!==null) QT[kk]=+(x/div).toPrecision(6); };
 if(!living){ pk('h','P2048'); pk('m','P2067'); } if(qty(c,'P1082')===null) pk('e','P2044'); pk('a','P2046'); pk('p','P1082'); pk('l','P2043',1000); pk('d','P4511'); pk('s','P2052');
 const EXT=[]; for(const [p,ty] of Object.entries(MAPKEYS)){ if(living&&LIVING_SKIP.includes(p)) continue; const is=[...new Set(ids(c,p))]; const ok=is.filter(labJ); if(!ok.length) continue;
  const n=is.length; if((ty==='C'||ty==='G')&&n<2) continue; EXT.push([p,n,ok.slice(0,2).map(t=>ty==='S'?[labJ(t),desJ(t).slice(0,30),t]:labJ(t))]); }
 const a=k.a; const pvy=Math.round((a.pop||0)*(AUX.pvScale||0));
 EXT.push(['_m',k.e.sl||0,a.bytes||0,Math.min(a.inl||0,500),(a.inl||0)>=500?1:0,pvy]);
 const isP=ids(c,'P31').includes('Q5'); const name=a.t.replace(/\s*[（(][^）)]*[）)]\s*$/,'');
 recs.push({q,t:a.t,grp:a.grp||'',isP,F:[name,a.t,q,[0,0,0,0],FI[q].mora,k.judge[0]==='保留'?'通常':k.judge[0],k.judge[0]==='保留'?'':k.judge[1],M,yo?yo.y:null,ids(c,'P361')],
  TI:[FI[q].tiers.map(x=>+x.toFixed(2)),FI[q].src],QT,EXT,X2:[(a.cats||[]).length,a.out||0,0,a.img||0,a.sec||0,isP?((AUX.works||{})[q]??-1):-1],hold:k.judge[0]==='保留'?k.judge[1]:null,
  refs:[...new Set(Object.entries(c).flatMap(([p,ss])=>ss.map(s=>{const v=idv(s); return v?p+':'+v:null;}).filter(Boolean)))]}); }

// 表示名の重複は記事名に戻す
const cnt={}; recs.forEach(r=>cnt[r.F[0]]=(cnt[r.F[0]]||0)+1); recs.forEach(r=>{ if(cnt[r.F[0]]>1) r.F[0]=r.t; });
// 因縁（Wikidataでの直接参照のみ）
const idx={}; recs.forEach((r,i)=>idx[r.q]=i); const RV={};
recs.forEach((r,i)=>r.refs.forEach(x=>{ const [p,v]=x.split(':'); const j=idx[v]; if(j===undefined||j===i) return; const key=Math.min(i,j)+','+Math.max(i,j); if(RV[key]&&p!=='P1889') return;
 const ev=n=>/^歴史上/.test(recs[n].F[6]);
 RV[key]=p==='P1889'?'Wikidataに、両者は「互いに異なるもの」と明記されている':(ev(i)||ev(j))?'Wikidataで直接つながっている、歴史上の因縁の相手':p==='P138'?recs[i].F[0]+'の名前の由来は'+recs[j].F[0]:'Wikidataで、'+recs[i].F[0]+'の「'+((E[p]&&E[p].l&&(E[p].l.ja||E[p].l.en))||p)+'」は'+recs[j].F[0]; }));
recs.forEach((r,i)=>{ if(r.hold) HOLD[i]=r.hold; });

const out={F:recs.map(r=>r.F),TI:recs.map(r=>r.TI),QT:Object.fromEntries(recs.map((r,i)=>[i,r.QT]).filter(x=>Object.keys(x[1]).length)),EXT:Object.fromEntries(recs.map((r,i)=>[i,r.EXT])),
 RV,GRP:recs.map(r=>r.grp),PERSON:recs.map(r=>r.isP?1:0),DROP,HOLD,X2:Object.fromEntries(recs.map((r,i)=>[i,r.X2])),asof:AUX.asof||''};
fs.writeFileSync(path.join(DIR,'big_v2.json'),JSON.stringify(out));
console.log(JSON.stringify({arts:ARTS.length,keep:recs.length,drop:DROP.length,hold:Object.keys(HOLD).length,rv:Object.keys(RV).length,bytes:fs.statSync(path.join(DIR,'big_v2.json')).size}));
