/* 百科拳典の戦闘エンジン（index.html から自動生成。直接編集しない） */
let DATA_BASE='data/';

/* ---------- 記事データ：必要になった記事だけを読み込む ---------- */
const F=[], RV={}; let VER='', N=0, NB=4096, POPULAR=[], EXCL=new Set();
const fnv=t=>{ let h=0x811c9dc5; for(let k=0;k<t.length;k++){ h^=t.charCodeAt(k); h=Math.imul(h,0x01000193)>>>0; } return h>>>0; };
const BUCKET={};   // 読み込んだ振り分けファイル {番号: {記事名: レコード}}
const TIX={};      // 記事名 → 番号
// 振り分けファイルは gzip のまま置いてあるので、ブラウザで展開して読む
async function bucket(k){ if(!BUCKET[k]) BUCKET[k]=fetch(DATA_BASE+'a/'+k+'.json.gz?v='+VER).then(async r=>{ if(!r.ok) throw new Error(r.status);
    const ds=new DecompressionStream('gzip'); return JSON.parse(await new Response(r.body.pipeThrough(ds)).text()); }).catch(e=>{ delete BUCKET[k]; throw e; }); return BUCKET[k]; }
async function loadTitle(t){ t=String(t||'').trim(); if(!t) return -1; if(TIX[t]!==undefined) return TIX[t];
  const b=await bucket(fnv(t)%NB); const rec=b[t]; if(!rec) return -1; return register(rec); }

const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const mark=s=>esc(s).replace(/【(.+?)】/g,'<mark>$1</mark>');
const STAT=['HP','攻撃','防御','速さ'], MAX=[130,36,24,30];
const fmt=n=>(+n).toLocaleString('ja-JP');
const ys=y=>y<=-1e8?Math.floor(-y/1e8)+'億年前':y<=-1e4?fmt(Math.round(-y/1e4))+'万年前':y<0?'紀元前'+(-y)+'年':y+'年';

/* ---------- 戦闘エンジン（決定的） ---------- */
const hash=s=>{let h=2166136261; for(const ch of s){h^=ch.codePointAt(0); h=Math.imul(h,16777619)>>>0;} return h;};
const pickT=(arr,key)=>arr[hash(key)%arr.length];
const rival=(i,j)=>RV[Math.min(i,j)+','+Math.max(i,j)]||null;
const QN=i=>+String(F[i][2]).slice(1), lt=(i,j)=>QN(i)<QN(j)||(QN(i)===QN(j)&&i<j), QK=(i,j)=>lt(i,j)?F[i][2]+'/'+F[j][2]:F[j][2]+'/'+F[i][2];
const SUMMON_LINE={
  '本家召喚':'{A}の【{N}】！ 名前の由来、{F}が一瞬だけ駆けつけた。',
  '生みの親召喚':'{A}の【{N}】！ 生みの親の{F}が一瞬だけ駆けつけた。',
  '親分召喚':'{A}の【{N}】！ 所属先の{F}が丸ごと駆けつけた。',
  'シリーズ召喚':'{A}の【{N}】！ シリーズの{F}が一斉に駆けつけた。',
  '両陣営召喚':'{A}の【{N}】！ 参戦者の{F}が全員駆けつけた。……どちらの味方かは誰にも分からない。'};
/* ---------- 技の候補と、相手に合わせた選択 ---------- */
const EX={}, QT={};
const jn=n=>{ n=+n; if(n<1e4) return (n<10?+n.toFixed(1):Math.round(n)).toLocaleString('ja-JP'); if(n<1e8) return fmt(Math.round(n/1e4))+'万'; if(n<1e12) return fmt(Math.round(n/1e8))+'億'; if(n<1e16) return fmt(Math.round(n/1e12))+'兆'; const e=Math.floor(Math.log10(n)); return '約'+(n/10**e).toFixed(1)+'×10'+String(e).replace(/\d/g,d=>'⁰¹²³⁴⁵⁶⁷⁸⁹'[d]); };
const unitv=(k,v)=>k==='wca'||k==='wse'?v+'個':k==='wim'?v+'枚':k==='wln'?v+'本':k==='_sl'?v+'言語':k==='_ch'?'約'+jn(v)+'文字':k==='_lh'?v+'本':k==='_pv'?'年間'+jn(v)+'回':k.startsWith('P')?fmt(v)+'件':k==='m'?(v<1?Math.round(v*1000)+'g':jn(v)+'kg'):k==='a'?jn(v)+'km²':k==='p'?jn(v)+'人':k==='l'?(v<1?jn(v*1000)+'m':jn(v)+'km'):k==='s'?'時速'+jn(v)+'km':jn(v)+'m';
const AT={'@領土拡大':i=>'面積'+unitv('a',QT[i].a),'@人海戦術':i=>'人口'+unitv('p',QT[i].p),'@のしかかり':i=>'体重'+unitv('m',QT[i].m),'@全長包囲':i=>'全長'+unitv('l',QT[i].l)};
/* ---------- 追加の技（Wikidataの各プロパティと、記事そのもののデータから） ---------- */
const EXT={};
const MAP={
 P1552:['K','特徴アピール','特徴','{A}の【{N}】！ 自慢の「{F}」を見せつけて{B}にぶつかる。'],
 P1299:['C','肖像ラッシュ','{A}を描いた作品','{A}の【{N}】！ 記録された{A}の肖像作品{n}点が額縁ごと押し寄せ、{B}に{H}連撃。'],
 P1343:['G','百科事典の権威','掲載している事典','{A}は【{N}】。{F}など記録上{n}冊の事典に載っている権威で身を固め、次の攻撃を{P}%軽減しつつ{B}に一撃。'],
 P793:['K','歴史の重み','重要な出来事','{A}の【{N}】！ 「{F}」を経験した歴史の重みで{B}を押しつぶす。'],
 P186:['S','素材召喚','材料','{A}の【{N}】！ {A}を形作る{F}が飛び出してきた。'],
 P166:['G','受賞歴のオーラ','受賞','{A}は【{N}】。{F}など記録された受賞{n}件のオーラをまとい、次の攻撃を{P}%軽減しつつ{B}に一撃。'],
 P22:['S','父召喚','父','{A}の【{N}】！ 父の{F}が駆けつけた。'],
 P25:['S','母召喚','母','{A}の【{N}】！ 母の{F}が駆けつけた。'],
 P40:['C','子だくさん','子','{A}の【{N}】！ 記録上の子ども{n}人が一斉に{B}へ飛びかかり、{H}連撃。'],
 P3373:['S','兄弟召喚','きょうだい','{A}の【{N}】！ きょうだいの{F}が加勢に来た。'],
 P1066:['S','師匠召喚','師匠','{A}の【{N}】！ 師匠の{F}が駆けつけ、手本を見せる。'],
 P802:['C','弟子軍団','弟子','{A}の【{N}】！ 記録上の弟子{n}人が師匠のために総出で{H}連撃。'],
 P737:['S','リスペクト召喚','影響を受けたもの','{A}の【{N}】！ 影響を受けた{F}の力を借りる。'],
 P463:['S','仲間召喚','所属グループ','{A}の【{N}】！ 所属する{F}の仲間が駆けつけた。'],
 P69:['S','母校の応援','出身校','{A}の【{N}】！ 母校の{F}から応援団が駆けつけた。'],
 P108:['S','職場の同僚','勤務先','{A}の【{N}】！ 勤め先の{F}から同僚が駆けつけた。'],
 P1412:['C','多言語詠唱','使える言語','{A}の【{N}】！ {F}など記録上{n}か国語でまくし立て、{H}連撃。'],
 P106:['C','肩書きラッシュ','職業','{A}の【{N}】！ {F}など記録上{n}個の肩書きを次々に名乗り、{H}連撃。'],
 P101:['K','専門分野','専門分野','{A}の【{N}】！ 専門の{F}で{B}を論破する。'],
 P2579:['K','専門分野','研究分野','{A}の【{N}】！ 専門の{F}で{B}を論破する。'],
 P800:['S','代表作召喚','主要作品','{A}の【{N}】！ 代表作の{F}が飛び出してきた。'],
 P1441:['S','出演作召喚','登場する作品','{A}の【{N}】！ 出演した{F}の仲間たちが駆けつけた。'],
 P136:['K','ジャンルで殴る','ジャンル','{A}の【{N}】！ {F}の作法で{B}を殴る。'],
 P1830:['S','所有物召喚','所有物','{A}の【{N}】！ 持ち物の{F}を投げつけた。'],
 P127:['S','持ち主召喚','所有者','{A}の【{N}】！ 持ち主の{F}が駆けつけた。'],
 P84:['S','設計者召喚','設計','{A}の【{N}】！ 設計した{F}が図面を片手に駆けつけた。'],
 P149:['G','様式美','建築様式','{A}は【{N}】。{F}の様式美で身を固め、次の攻撃を{P}%軽減しつつ{B}に一撃。'],
 P1435:['G','文化財バリア','遺産保護指定','{A}は【{N}】。{F}として守られ、次の攻撃を{P}%軽減しつつ{B}に一撃。'],
 P366:['K','本来の用途','用途','{A}の【{N}】！ 本来の用途「{F}」を発揮して{B}に襲いかかる。'],
 P2283:['S','道具召喚','使用するもの','{A}の【{N}】！ 愛用の{F}を取り出した。'],
 P1365:['S','先代召喚','先代','{A}の【{N}】！ 先代の{F}が駆けつけた。'],
 P156:['S','後継召喚','後継','{A}の【{N}】！ 後継の{F}が駆けつけた。'],
 P4969:['C','派生作品ラッシュ','派生作品','{A}の【{N}】！ {F}など登録された派生作品{n}本が押し寄せ、{H}連撃。'],
 P1034:['H','腹ごしらえ','主な食べ物','{A}の【{N}】。好物の{F}を食べてHPを{R}回復し、{B}を小突く。'],
 P397:['S','母天体召喚','母天体','{A}の【{N}】！ 周りを回っている{F}が引力で加勢した。'],
 P398:['C','衛星ラッシュ','子天体','{A}の【{N}】！ {F}など登録された{n}個の天体を従えて{H}連撃。'],
 P47:['S','お隣さん召喚','お隣','{A}の【{N}】！ お隣の{F}が駆けつけた。'],
 P150:['C','配下動員','配下の行政区画','{A}の【{N}】！ {F}など配下の{n}区画を動員して{H}連撃。'],
 P190:['S','姉妹都市召喚','姉妹都市','{A}の【{N}】！ 姉妹都市の{F}が駆けつけた。'],
 P1376:['K','首都の威光','首都','{A}の【{N}】！ {F}の首都としての威光で{B}を圧倒する。'],
 P206:['L','地の利','隣接する水域','{A}の【{N}】。{F}に{B}を誘い込み、足止めしたところを殴る。'],
 P706:['L','地の利','位置する地形','{A}の【{N}】。{F}に{B}を誘い込み、足止めしたところを殴る。'],
 P610:['S','最高地点召喚','最も高い地点','{A}の【{N}】！ いちばん高い{F}から飛び降りてきた。'],
 P2348:['K','時代の空気','時代','{A}の【{N}】！ {F}の空気をまとって{B}にぶつかる。'],
 P135:['K','ムーブメント','ムーブメント','{A}の【{N}】！ {F}の勢いに乗って{B}を押し流す。'],
 P178:['S','開発元召喚','開発元','{A}の【{N}】！ 開発元の{F}が駆けつけた。'],
 P176:['S','製造元召喚','製造元','{A}の【{N}】！ 製造元の{F}が駆けつけた。'],
 P375:['S','ロケット召喚','打ち上げロケット','{A}の【{N}】！ 打ち上げた{F}が火を噴いて突っ込んだ。'],
 P3342:['S','キーパーソン召喚','重要な人物','{A}の【{N}】！ 重要人物の{F}が駆けつけた。'],
 P19:['S','地元の声援','生まれた場所','{A}の【{N}】！ 生まれ故郷の{F}から声援が届いた。'],
 P61:['S','発見者召喚','発見者・発明者','{A}の【{N}】！ 見つけてくれた{F}が駆けつけた。'],
 P941:['S','元ネタ召喚','着想を得たもの','{A}の【{N}】！ 元ネタの{F}が駆けつけた。'],
 P2670:['C','部品ラッシュ','含む部分','{A}の【{N}】！ {F}など登録された{n}種類の部品が飛び散り、{H}連撃。'],
 P1344:['S','参加イベント召喚','参加したイベント','{A}の【{N}】！ 参加した{F}の熱気を持ち込んだ。'],
 P937:['L','ホームグラウンド','活動地','{A}の【{N}】。慣れ親しんだ{F}に{B}を誘い込み、足止めして殴る。']};
const SENS=/事件|空襲|暗殺|爆撃|襲撃|の死|ショック|窃盗|ヴァンダリズム|火災|攻囲|包囲|遭難|クーデター|コミューン|処刑|戦争$|占領|題材とした/;
const KMAP={S:'SUMMON',C:'MULTI',G:'GUARD',K:'STRIKE',H:'HEAL',L:'SLOW'};
const cntT=(n,cuts)=>{ let t=0; for(const c of cuts){ if(n>=c) t++; } return t; };
const WP={};
const GEN={};   // 汎用技の素材（分類・別名・作成日・保守タグ・座標・見出し名・カテゴリ名・外部リンク・所在地・本業）
const GENN=new Set(['正体開示','分身の術','外部リンク渡り','地元召喚','本業','要出典','書きかけ指摘','古参の貫禄','北から目線']);
const META=[], CNT=[];
function prepMeta(i){ META[i]=null; CNT[i]={};
  for(const e of (EXT[i]||[])){ if(e[0]==='_m'){ META[i]={sl:e[1],ch:Math.round(e[2]/3),lh:e[3],lhp:e[4],pv:e[5]}; continue; } CNT[i][e[0]]=e[1]; } }
function extMoves(i){ const out=[];
  for(const e of (EXT[i]||[])){ if(e[0]==='_m') continue; const def=MAP[e[0]]; if(!def) continue;
    const [code,name,lab,tpl]=def; let names=e[2].filter(x=>!SENS.test(Array.isArray(x)?x[0]:x)); if(!names.length) continue;
    const n=e[1]; const disp=names.map(x=>Array.isArray(x)?x[0]:x);
    const kind=KMAP[code]; const T=code==='C'?Math.min(5,1+Math.log2(n)/1.3):code==='G'?Math.min(5,1+Math.log2(n)):3;
    const card=lab+'：'+disp.join('、')+(n>disp.length?' など記録上'+n+'件':'');
    const shown=code==='G'||code==='C'?disp.slice(0,1):disp;
    const line=tpl.replace(/\{F\}/g,shown.join('・')).replace(/\{n\}/g,fmt(n));
    out.push([kind,name,disp.join('と'),card,+T.toFixed(2),code==='S'||code==='H'?1:0,line,code==='S'?names:undefined]); }
  const m=META[i]; if(m){
    out.push(['STRIKE','長文で殴る','約'+jn(m.ch)+'文字','日本語版の記事：約'+jn(m.ch)+'文字',cntT(m.ch,[3000,10000,30000,60000,100000]),0,'{A}の【{N}】！ 約'+jn(m.ch)+'文字の記事本文を丸ごと{B}に叩きつける。','meta']);
    out.push(['BIND','リンク網','被リンク'+m.lh+(m.lhp?'以上':''),'この記事へのリンク：'+m.lh+'本'+(m.lhp?'以上':''),cntT(m.lh,[20,60,150,300,500]),0,pickT(['{A}の【{N}】！ '+m.lh+'本'+(m.lhp?'以上':'')+'の被リンクで{B}を縛り上げる。{B}の動きが鈍った。','{A}の【{N}】！ 自分を指す'+m.lh+'本'+(m.lhp?'以上':'')+'のリンクを投げ縄にして{B}を捕まえる。{B}の動きが鈍った。'],String(i)),'meta']);
    out.push(['MULTI','注目の視線','年間'+jn(m.pv)+'回','1年間の閲覧数：'+jn(m.pv)+'回',cntT(m.pv,[1e4,5e4,2e5,6e5,2e6]),0,'{A}の【{N}】！ 年間'+jn(m.pv)+'回読まれた視線が{B}に突き刺さり、{H}連撃。','meta']); }
  const w=WP[i]; if(w){ const [ca,ln,lc,im,se]=w;
    const g0=GEN[i]||{};
    if(ca>=2) out.push(['BIND','カテゴリ包囲','カテゴリ'+ca+'個','属するカテゴリ：'+ca+'個'+(g0.cc?'（'+g0.cc.join('、')+'など）':''),cntT(ca,[3,6,10,15,25]),0,g0.cc?'{A}の【{N}】！ 「'+g0.cc[0]+'」「'+g0.cc[1]+'」など'+ca+'個のカテゴリで{B}を分類し尽くす。{B}の動きが鈍った。':'{A}の【{N}】！ '+ca+'個のカテゴリで{B}を分類し尽くす。{B}の動きが鈍った。','wp']);
    if(se>=3) out.push(['MULTI','見出し連打','見出し'+se+'個','記事の見出し：'+se+'個'+(g0.h?'（'+g0.h.join('、')+'など）':''),cntT(se,[3,6,10,15,25]),0,g0.h?'{A}の【{N}】！ 「'+g0.h.join('」「')+'」……記事の見出し'+se+'個を次々に叩きつけ、{H}連撃。':'{A}の【{N}】！ 記事の見出し'+se+'個を次々に叩きつけ、{H}連撃。','wp']);
    if(ln>=5) out.push(['SLOW','リンク乱打','リンク'+ln+(lc?'本以上':'本'),'記事から出ているリンク：'+ln+(lc?'本以上':'本'),cntT(ln,[20,60,150,300,500]),0,'{A}の【{N}】。記事から伸びる'+ln+(lc?'本以上':'本')+'のリンクで{B}を迷子にさせ、そこを殴る。','wp']);
    if(im>=1) out.push(['STRIKE','画像攻撃','画像'+im+'枚','記事の画像：'+im+'枚',cntT(im,[1,3,6,12,25]),0,'{A}の【{N}】！ 記事に貼られた'+im+'枚の画像を{B}に投げつける。','wp']); }
  const g=GEN[i]; if(g){
    if(g.c) out.push(['STRIKE','正体開示',g.c,'Wikidataでの分類：'+g.c,g.cf||0,0,pickT(['{A}の【{N}】！ その正体は「'+g.c+'」。意表を突かれた{B}に一撃。','{A}の【{N}】。「実は、'+g.c+'なんです」——{B}が戸惑った隙に殴る。'],String(i)),'gen']);
    if(g.r){ const al=g.r.slice(1).map(x=>'「'+x+'」').join(''); out.push(['MULTI','分身の術','別名'+g.r[0]+'個','別名（転送ページ）：'+g.r.slice(1).join('、')+(g.r[0]>g.r.length-1?' など'+g.r[0]+'個':''),cntT(g.r[0],[1,2,4,8,15]),0,'{A}の【{N}】！ '+al+(g.r[0]>g.r.length-1?'など':'')+g.r[0]+'個の別名に分身して、{H}連撃。','gen']); }
    if(g.x) out.push(['HASTE','外部リンク渡り','外部リンク'+g.x+'本','記事の外部リンク：'+g.x+'本',cntT(g.x,[3,8,15,30,60]),0,'{A}の【{N}】。記事から張られた外部リンク'+g.x+'本を飛び石にして{B}の背後へ回り込み、一撃。勢いで次の行動が早まる。','gen']);
    if(g.loc) out.push(['SUMMON','地元召喚',g.loc[0],'所在地：'+g.loc[0],2,1,'{A}の【{N}】！ 所在地の'+g.loc[0]+'が丸ごと駆けつけた。',[[g.loc[0],g.loc[1],g.loc[2]]]]);
    if(g.job) out.push(['STRIKE','本業',g.job,'職業：'+g.job,2.5,0,'{A}の【{N}】！ '+g.job+'としての本領を発揮して{B}に挑む。','gen']); }
  return out; }

/* 数値データ（QT）から、まだ持っていない基本の技を補う。事実の表記もQTから作り直す */
const tierL=(x,cuts)=>{ if(!(x>0)) return 0; const f=v=>Math.log10(v), X=f(x), K=cuts.map(f); if(X<K[0]) return 0; for(let k=0;k<K.length-1;k++) if(X<K[k+1]) return k+1+(X-K[k])/(K[k+1]-K[k]); return 5; };
const PLAIN=[['h','急降下','STRIKE',v=>'高さ'+unitv('h',v),[0.35,1.11,2.315,30,102]],['e','標高落とし','STRIKE',v=>'標高'+jn(v)+'m',[18,128,353,924,1751]],['m','のしかかり','STRIKE',v=>'体重'+unitv('m',v),[0.129,52.4,8100,5.62e27,3.62e30]],
  ['a','領土拡大','SLOW',v=>'面積'+unitv('a',v),[3.81,28.47,235.12,2336,15101]],['p','人海戦術','MULTI',v=>'人口'+unitv('p',v),[741,4562,28522,178380,1131016]],['l','全長包囲','BIND',v=>'全長'+unitv('l',v),[0.1,1,10,100,1000]],
  ['d','深淵送り','STRIKE',v=>'最大水深'+jn(v)+'m',[5,20,50,100,500]],['s','全力疾走','HASTE',v=>unitv('s',v),[30,46.3,66.7,160.9,592]]];
const CLASH={'急降下':['h','高さ'],'標高落とし':['e','標高'],'のしかかり':['m','重さ'],'領土拡大':['a','面積'],'人海戦術':['p','人口'],'全長包囲':['l','長さ'],'深淵送り':['d','水深'],'全力疾走':['s','速さ']};
function plainMoves(i){ const q=QT[i]; if(!q) return []; const out=[];
  for(const [k,name,kind,fx,cuts] of PLAIN){ if(!(q[k]>0)) continue; if(k==='l'&&q[k]<1) continue; const fact=fx(q[k]); out.push([kind,name,fact,fact,+tierL(q[k],cuts).toFixed(2),0,0]); }
  return out; }
const POOL=[];
function makePool(i){ const f=F[i]; const out=[...f[7]]; const have=new Set(out.map(m=>m[1]));
  for(const m of (EX[i]||[])){ if(have.has(m[1])) continue; const mm=[...m]; if(String(mm[2]).startsWith('@')){ const g=AT[mm[2]]; if(!g||!QT[i]) continue; mm[2]=mm[3]=g(i); } out.push(mm); have.add(m[1]); }
  for(const m of plainMoves(i)){ const k=out.findIndex(x=>x[1]===m[1]); if(k>=0){ out[k]=[...out[k]]; out[k][2]=out[k][3]=m[2]; } else { out.push(m); have.add(m[1]); } }
  for(const m of extMoves(i)){ if(have.has(m[1])) continue; out.push(m); have.add(m[1]); }
  return out; }
const dimv=(i,k)=>{ if(k.startsWith('w')){ const w=WP[i]; if(!w) return null; const v=k==='wca'?w[0]:k==='wse'?w[4]:k==='wim'?w[3]:(w[2]?null:w[1]); return v>0?v:null; } if(k.startsWith('_')){ const m=META[i]; if(!m) return null; if(k==='_sl') return null; const v=k==='_ch'?m.ch:k==='_pv'?m.pv:(m.lhp?null:m.lh); return v>0?v:null; } if(k.startsWith('P')){ const v=CNT[i][k]; return v>0?v:null; } const q=QT[i]; if(!q) return null; if(k==='h'){ const v=q.h!==undefined?q.h:(q.l===undefined?q.e:undefined); return v>0?v:null; } const v=q[k]; return v>0?v:null; };
const DIMS={h:{lab:'高さ',plain:['急降下','標高落とし'],kind:'STRIKE',name:'見下ろし',line:'{A}の【{N}】！ {B}の{R}の高さから見下ろし、そのまま踏みつける。'},
  m:{lab:'重さ',plain:['のしかかり'],kind:'STRIKE',name:'重量差',line:'{A}の【{N}】！ {B}の{R}の重さでのしかかる。'},
  a:{lab:'面積',plain:['領土拡大'],kind:'SLOW',name:'面積マウント',line:'{A}の【{N}】！ {B}を{C}個並べられる広さに{B}が迷い込む。行動が遅れたところを殴る。'},
  p:{lab:'人口',plain:['人海戦術'],kind:'MULTI',name:'数の暴力',line:'{A}の【{N}】！ {B}の{R}の人数で押し寄せ、{H}連撃。'},
  l:{lab:'長さ',plain:['全長包囲'],kind:'BIND',name:'長さ比べ',line:'{A}の【{N}】！ {B}の{R}の長さでぐるぐる巻きにする。{B}の動きが鈍った。'},
  s:{lab:'速さ',plain:['全力疾走'],kind:'HASTE',name:'置き去り',line:'{A}の【{N}】！ {B}の{R}の速さで駆け抜けながら体当たり。勢いで次の行動が早まる。'},
  _ch:{lab:'記事の文字数',plain:['長文で殴る'],kind:'STRIKE',name:'文字数マウント',line:'{A}の【{N}】！ {B}の{R}の文字数を誇る記事の重みでのしかかる。',meta:1},
  _lh:{lab:'被リンク数',plain:['リンク網'],kind:'BIND',name:'人脈マウント',line:'{A}の【{N}】！ {B}の{R}の被リンクで張り巡らせた網で縛る。{B}の動きが鈍った。',meta:1},
  _pv:{lab:'閲覧数',plain:['注目の視線'],kind:'MULTI',name:'閲覧数マウント',line:'{A}の【{N}】！ {B}の{R}読まれている人気で押し寄せ、{H}連撃。',meta:1},
  wca:{lab:'カテゴリの数',plain:['カテゴリ包囲'],kind:'STRIKE',name:'カテゴリ数マウント',line:'{A}の【{N}】！ {B}の{R}のカテゴリに顔を出している顔の広さで殴る。',wp:1},
  wse:{lab:'見出しの数',plain:['見出し連打'],kind:'STRIKE',name:'見出し数マウント',line:'{A}の【{N}】！ {B}の{R}の見出しで章立てした構成力で殴る。',wp:1},
  wim:{lab:'画像の数',plain:['画像攻撃'],kind:'STRIKE',name:'画像数マウント',line:'{A}の【{N}】！ {B}の{R}の画像で視覚的に圧倒する。',wp:1},
  wln:{lab:'記事から出ているリンクの数',plain:['リンク乱打'],kind:'SLOW',name:'リンク数マウント',line:'{A}の【{N}】。{B}の{R}のリンクで道案内して迷わせ、そこを殴る。',wp:1},
  P40:{lab:'子どもの数',plain:['子だくさん'],kind:'MULTI',name:'子だくさんマウント',line:'{A}の【{N}】！ 記録上{B}の{R}の子どもを引き連れて{H}連撃。'},
  P800:{lab:'主要作品の数',plain:[],kind:'STRIKE',name:'代表作マウント',line:'{A}の【{N}】！ {B}の{R}の代表作を並べて殴る。'},
  P166:{lab:'受賞の数',plain:['受賞歴のオーラ'],kind:'STRIKE',name:'受賞歴マウント',line:'{A}の【{N}】！ 記録上{B}の{R}の勲章をじゃらじゃら鳴らして殴る。'},
  P1343:{lab:'載っている事典の数',plain:['百科事典の権威'],kind:'STRIKE',name:'事典掲載マウント',line:'{A}の【{N}】！ {B}の{R}の事典に載っている権威で殴る。'},
  P106:{lab:'肩書きの数',plain:['肩書きラッシュ'],kind:'STRIKE',name:'肩書きマウント',line:'{A}の【{N}】！ 記録上{B}の{R}の肩書きを名乗って圧をかける。'},
  P398:{lab:'従える天体の数',plain:['衛星ラッシュ'],kind:'MULTI',name:'子分マウント',line:'{A}の【{N}】！ 記録上{B}の{R}の天体を従えて{H}連撃。'},
  P190:{lab:'姉妹都市の数',plain:['姉妹都市召喚'],kind:'STRIKE',name:'姉妹都市マウント',line:'{A}の【{N}】！ 記録上{B}の{R}の姉妹都市から援軍を呼んで殴る。'}};
const ratioTxt=r=>r<100?r.toFixed(1)+'倍':r<1e4?fmt(Math.round(r))+'倍':jn(r)+'倍';
const countTxt=r=>r<1e4?fmt(Math.round(r)):jn(r);
/* 相手 j に対して記事 i が使う3つの技を選ぶ（同じ組み合わせなら必ず同じ） */
const PICK={};
function pickMoves(i,j){
  const key=i+'>'+j; if(PICK[key]) return PICK[key];
  const cand=[]; const lose=new Set(), cmpd=new Set();
  for(const [k,d] of Object.entries(DIMS)){ const va=dimv(i,k), vb=dimv(j,k); if(va===null||vb===null) continue;
    const r=va/vb;
    if(r>=1.5){ cmpd.add(k); const pl=POOL[i].find(m=>d.plain.includes(m[1])); const T=Math.min(5,Math.max(pl?pl[4]:0,2+Math.log10(r)));
      const line=d.line.replace('{R}',ratioTxt(r)).replace('{C}',countTxt(r));
      cand.push({m:[d.kind,d.name,d.lab+'で'+F[j][0]+'の'+ratioTxt(r),d.lab+'：'+unitv(k,va)+' 対 '+unitv(k,vb),+T.toFixed(2),0,line],s:T+(d.meta?-0.6:d.wp?-1.2:0.5),meta:!!d.meta,wp:!!d.wp}); }
    else if(r<=1/1.5) lose.add(k); }
  { const ga=GEN[i]||{}, gb=GEN[j]||{}; const okB=F[j][5]!=='配慮';
    const push=(m,s)=>cand.push({m:[...m,'gen'],s,gen:true});
    if(okB&&(gb.mt||[]).includes('出典')) push(['BIND','要出典',F[j][0]+'は出典が不足','相手の記事に「出典の明記」の札',3,0,'{A}の【{N}】！ {B}の記事に貼られた「出典が不足している」の札を指さした。{B}の動きが止まった。'],2.6);
    else if(okB&&(gb.mt||[]).includes('スタブ')) push(['SLOW','書きかけ指摘',F[j][0]+'は書きかけ','相手の記事が「書きかけ」',2,0,'{A}の【{N}】。{B}の記事がまだ書きかけだと指摘する。加筆に気を取られた{B}を殴る。'],1.8);
    const ym=c=>c.slice(0,4)+'年'+(+c.slice(5,7))+'月';
    if(ga.ct&&gb.ct){ const ya=+ga.ct.slice(0,4), yb=+gb.ct.slice(0,4); if(yb-ya>=6){ const T=Math.min(5,(yb-ya)/4);
      push(['GUARD','古参の貫禄',ym(ga.ct)+'から','記事の作成：'+ym(ga.ct)+'（'+F[j][0]+'は'+ym(gb.ct)+'）',+T.toFixed(2),0,'{A}は【{N}】。'+ym(ga.ct)+'からWikipediaにいる古株として、'+(yb-ya)+'年後輩の{B}の攻撃を{P}%受け流す構え。ついでに小突く。'],T-0.8); } }
    if(ga.co&&gb.co){ const d=ga.co[0]-gb.co[0]; if(d>=1){ const T=Math.min(5,2+Math.log10(d)*1.5);
      push(['STRIKE','北から目線','緯度で'+d.toFixed(1)+'度北','緯度：北緯'+ga.co[0]+'度（'+F[j][0]+'は'+(gb.co[0]>=0?'北緯':'南緯')+Math.abs(gb.co[0])+'度）',+T.toFixed(2),0,'{A}の【{N}】！ {B}より緯度で'+d.toFixed(1)+'度北から見下ろして殴る。'],T-0.3); } } }
  for(const m of POOL[i]){ let s=m[4];
    const dk=Object.keys(DIMS).find(k=>DIMS[k].plain.includes(m[1]));
    if(dk&&cmpd.has(dk)) continue;
    if(dk&&lose.has(dk)) s-=CLASH[m[1]]?0.6:2;
    if(m[0]==='SENIORITY'){ const ya=F[i][8], yb=F[j][8]; if(ya===null) continue; if(yb===null) s=0.8; else if(ya<yb) s=3; else continue; }
    if(m[0]==='SUMMON'&&(m[7]||[]).some(t=>t[2]===F[j][2])) s+=1.5;
    if(m[0]==='NAME') s=F[i][4]>F[j][4]?1.8:0.6;
    if(m[0]==='HEAL'||m[0]==='GUARD') s=Math.max(s,2.2);
    if(m[7]==='meta') s-=m[1]==='リンク網'?2.2:1.4;
    if(m[7]==='wp') s-=m[1]==='リンク乱打'?1.8:0.9;
    const isG=GENN.has(m[1]); if(isG) s-=m[1]==='外部リンク渡り'?1.5:0.6;
    cand.push({m,s,meta:m[7]==='meta',wp:m[7]==='wp',gen:isG}); }
  /* 同じ組み合わせなら必ず同じになる「ゆらぎ」を足して、相手ごとに顔ぶれを変える */
  cand.forEach(c=>{ c.s+=(hash(QK(i,j)+'/'+F[i][2]+c.m[1])%1000)/1000*1.6; });
  cand.sort((a,b)=>b.s-a.s);
  /* 同じ系統の技ばかりにならないよう、召喚は2つまで */
  const cap={SUMMON:2,GUARD:1,HEAL:1,meta:1,wp:2,gen:2}, used={}; const out=[];
  for(const c of cand){ const g=c.meta?'meta':c.wp?'wp':c.gen?'gen':c.m[0]; if(cap[g]!==undefined){ if((used[g]||0)>=cap[g]) continue; used[g]=(used[g]||0)+1; } out.push(c.m); if(out.length>=4) break; }
  /* 実質的な技（記事データ系以外）が少ない記事は、選んだ技を少し強くして差を縮める */
  const real=POOL[i].filter(m=>m[7]!=='meta'&&m[7]!=='wp'&&!GENN.has(m[1])).length; const bonus=Math.max(0,4-real)*0.4;
  return PICK[key]=bonus?out.map(m=>{ const c=[...m]; c[4]=Math.min(5,+(m[4]+bonus).toFixed(2)); return c; }):out;
}
const BIG=m=>m&&(m[0]==='SUMMON'||(m[0]==='STRIKE'&&m[4]>=4)||(m[0]==='MULTI'&&m[4]>=4));
function simulate(ai,bi,opt={}){
  const mk=(i,o)=>{const f=F[i], s=f[3]; return {i,name:f[0],maxhp:s[0],hp:s[0],atk:s[1],df:s[2],spd:s[3],rate:s[3]+30,g:0,n:0,out:false,atkb:0,guard:0,used:{},first:true,year:f[8],
    moves:opt.noMoves?[]:pickMoves(i,o).filter(m=>!(opt.disable&&opt.disable[i]===m[1]))};};
  const A=mk(ai,bi),B=mk(bi,ai); const riv=opt.noRiv?null:rival(ai,bi); const log=[]; const key=F[ai][2]+F[bi][2]; let senUsed=false; const summoned=[];
  if(riv) log.push({t:0,side:-1,s:'【因縁】'+riv+'。両者とも初撃1.5倍',d:0,hp:[A.hp,B.hp]});
  const baseDmg=(x,y)=>Math.max(1,x.atk+x.atkb-Math.floor(y.df/2));
  const left=x=>x.moves.filter(m=>!x.used[m[1]]&&!(m[0]==='SENIORITY'&&senUsed));
  const est=(x,y,m)=>{ const b0=baseDmg(x,y), T=m[4]; return m[0]==='STRIKE'?b0*(1+0.15*T):m[0]==='MULTI'?(1+Math.floor(T/2))*Math.max(1,Math.round(b0*0.45)):m[0]==='SUMMON'?b0*1.5+5:m[0]==='NAME'?b0:b0*0.6; };
  /* 戦況を見て次の技を選ぶ */
  const choose=(x,y)=>{ const L=left(x); if(!L.length) return [null,''];
    const heal=L.find(m=>m[0]==='HEAL'); if(heal&&x.hp<=x.maxhp*0.45) return [heal,'（追い込まれて）'];
    const guard=L.find(m=>m[0]==='GUARD'); const yn=left(y)[0]; if(guard&&BIG(yn)&&!y.out) return [guard,'（'+y.name+'の大技の気配を察して）'];
    const atk=L.filter(m=>!['GUARD','HEAL','SENIORITY'].includes(m[0])); const fin=atk.find(m=>est(x,y,m)>=y.hp);
    if(fin&&fin!==L[0]&&x.n>1) return [fin,'（ここで決めにいく）'];
    return [L[0],''];};
  const act=(x,y,tick)=>{ x.n++; const [mv,tag]=choose(x,y);
    const outNow=!mv&&!x.out; if(!mv) x.out=true;
    let d=0,line=''; const b0=baseDmg(x,y); const T=mv?mv[4]:0; const k=key+tick+x.i; let H=0;
    if(!mv){ d=b0; line=outNow?(x.moves.length?'{A}は技を出し尽くした。ここからは地道に殴る。':'{A}には技がない。最初から地道に殴る。'):pickT(['{A}、地道に殴る。','{A}は特に何も考えずに殴った。','{A}、黙々と殴る。'],k); }
    else { x.used[mv[1]]=1; const kind=mv[0]; const tp=mv[6]||null;
      if(kind==='STRIKE'){ d=Math.round(b0*(1+0.15*T)); line=tp||pickT(['{A}の【{N}】！ {F}の重みが{B}を襲う。','{A}、{F}を誇示しながら【{N}】。'],k); }
      if(kind==='MULTI'){ H=1+Math.floor(T/2); d=H*Math.max(1,Math.round(b0*0.45)); line=tp||(H===1?'{A}の【{N}】！ {F}が駆けつけ、単発の一撃。':pickT(['{A}の【{N}】！ {F}を総動員して{H}連撃。','{A}の【{N}】！ {F}が押し寄せ、{B}に{H}連撃。'],k)); }
      if(kind==='GUARD'){ x.guard=Math.min(0.6,0.1*T+0.1); d=Math.round(b0*0.5); const pc=Math.round(x.guard*100); line=tp?tp.replace('{P}',pc):mv[1]==='保護動物の構え'?'{A}は【{N}】。{F}として手厚く守られ、次の攻撃を'+pc+'%軽減しつつ、{B}に軽く一撃。':pickT(['{A}は【{N}】。{F}の経験で次の攻撃を'+pc+'%軽減しつつ、{B}に軽く一撃。','{A}、【{N}】をとる。{F}の重みで次の被害を'+pc+'%軽減し、構えたまま{B}を小突く。'],k); }
      if(kind==='HEAL'){ const h=Math.round(x.maxhp*0.04*Math.max(1,T)); x.hp=Math.min(x.maxhp,x.hp+h); d=Math.round(b0*0.5); line=tp?tp.replace('{R}',h):'{A}の【{N}】。{F}の粘りでHPを'+h+'回復し、ついでに{B}を小突く。'; }
      if(kind==='SLOW'){ y.g-=Math.round(10*T); d=Math.round(b0*0.7); line=tp||pickT(['{A}の【{N}】。{F}の土地に{B}が迷い込み、行動が遅れる。そこへ一撃。','{A}、【{N}】。{F}の広さに{B}が立ち往生したところを殴る。'],k); }
      if(kind==='BIND'){ y.g-=Math.round(12*T); d=Math.round(b0*0.5); line=tp||'{A}の【{N}】！ {F}で{B}をぐるりと囲んで締め上げる。{B}の動きが鈍った。'; }
      if(kind==='HASTE'){ x.g+=Math.round(10*T); d=Math.round(b0*0.8); line=tp||'{A}、【{N}】。{F}で駆け抜けながら{B}に体当たり。勢いで次の行動が早まる。'; }
      if(kind==='SUMMON'){ d=Math.round(b0*1.5)+5; const tg=Array.isArray(mv[7])?mv[7]:[]; summoned.push(...tg); line=tp||SUMMON_LINE[mv[1]]||'{A}の【{N}】！ {F}が駆けつけた。';
        const yq=F[y.i][2];
        if(tg.some(t=>t[2]===yq)) line+='……が、呼ばれたのは対戦相手の{B}本人だった。気まずい。';
        else if(mv[1]==='親分召喚'&&tg.some(t=>F[y.i][9].includes(t[2]))) line+='……が、{B}もその一員なので、半分くらいは相手側に立っている。'; }
      if(kind==='NAME'){ const ma=F[x.i][4], mb=F[y.i][4]; const r=Math.max(0.5,Math.min(2,ma/Math.max(1,mb))); d=Math.round(b0*r);
        line='{A}の【{N}】！ '+(ma<=2?'たった':'')+ma+'音の名前を全力で叩きつける'+(r>=1?'。':'が、'+mb+'音の{B}には効きが薄い。'); }
      if(kind==='SENIORITY'){ senUsed=true;
        if(y.year===null){ d=0; line='{A}は【{N}】を主張した（{F}）。しかし{B}は年齢不詳。先輩風は空を切った。'; }
        else if(x.year<y.year){ x.atkb+=3; x.g+=30; d=Math.round(b0*0.5); line='{A}の【{N}】。{F}の{A}が、'+ys(y.year)+'の{B}に先輩風を吹かせて小突く。'+fmt(y.year-x.year)+'年の差で攻撃力が上がった。'; }
        else { d=0; line='{A}は【{N}】を主張した（{F}）。しかし{B}のほうが'+fmt(x.year-y.year)+'年先輩だった。何も起きない。'; } }
      const ck=CLASH[mv[1]];
      if(ck&&QT[x.i]&&QT[y.i]&&QT[x.i][ck[0]]>0&&QT[y.i][ck[0]]>0){ const [k,lab]=ck, va=QT[x.i][k], vb=QT[y.i][k], df0=Math.abs(va-vb), df=(Math.min(va,vb)>=10&&df0>=1)?Math.round(df0):df0, dtx=unitv(k,df);
        if(vb>va&&jn(df)!=='0'){ d=Math.max(1,Math.round(d*0.6)); line+='……が、{B}の'+lab+'は'+unitv(k,vb)+'。'+lab+'で挑んだ{A}、'+dtx+'足りなかった。威力は控えめ。'; }
        else if(va>vb&&jn(df)!=='0') line+=pickT(['（'+lab+'比べは'+dtx+'差で{A}の勝ち）','（{B}の'+unitv(k,vb)+'を'+dtx+'上回った）'],k+key); }
      line=tag+line;
    }
    if(x.first&&riv&&d>0){ d=Math.round(d*1.5); line+='（因縁で1.5倍）'; }
    if(d>0) x.first=false;
    if(y.guard&&d>0){ const red=Math.round(d*y.guard); d-=red; line+=' {B}の構えで'+red+'軽減。'; y.guard=0; }
    line=line.replace(/\{A\}/g,x.name).replace(/\{B\}/g,y.name).replace(/\{N\}/g,mv?mv[1]:'').replace(/\{F\}/g,mv?mv[2]:'').replace(/\{H\}/g,H);
    return {d,line,mv}; };
  let tick; const used={[ai]:[],[bi]:[]};
  for(tick=1;tick<=15;tick++){ const bA=A.g,bB=B.g; A.g+=A.rate; B.g+=B.rate; const actors=[A,B].filter(x=>x.g>=100); if(!actors.length) continue;
    let groups; if(actors.length===2){const l=(100-bA)*B.rate, r=(100-bB)*A.rate; groups=l<r?[[A],[B]]:l>r?[[B],[A]]:[[A,B]];} else groups=[actors];
    for(const g of groups){ if(A.hp===0||B.hp===0) break; const res=g.map(x=>{const y=x===A?B:A; x.g-=100; return [x,y,act(x,y,tick)];});
      for(const [x,y,r] of res){ y.hp=Math.max(0,y.hp-r.d); log.push({t:tick,side:x===A?0:1,s:r.line,d:r.d,hp:[A.hp,B.hp],mv:r.mv}); if(r.mv) used[x.i].push(r.mv[1]); } }
    if(A.hp===0||B.hp===0) break; }
  let w=null,kind; if(A.hp===0&&B.hp===0) kind='相打ち'; else if(B.hp===0){kind='KO';w=ai;} else if(A.hp===0){kind='KO';w=bi;} else {kind='判定'; const l=A.hp*B.maxhp,r=B.hp*A.maxhp; w=l>r?ai:r>l?bi:null;}
  return {w,kind,tick:Math.min(tick,15),log,hp:[A.hp,B.hp],max:[A.maxhp,B.maxhp],riv,used,summoned};
}

/* 左右を入れ替えても結果が変わらないよう、常に記事番号の小さい側をAとして計算し、表示側に合わせて反転する */
function simC(ai,bi,opt={}){
  if(lt(ai,bi)) return simulate(ai,bi,opt);
  const r=simulate(bi,ai,opt);
  return {...r,log:r.log.map(l=>({...l,side:l.side<0?-1:1-l.side,hp:[l.hp[1],l.hp[0]]})),hp:[r.hp[1],r.hp[0]],max:[r.max[1],r.max[0]]};
}
function analyze(ai,bi){
  const r=simC(ai,bi); const base=simC(ai,bi,{noMoves:true,noRiv:true});
  const dec=[];
  for(const i of [ai,bi]) for(const m of [...new Set(r.used[i])]){ const c=simC(ai,bi,{disable:{[i]:m}}); if(c.w!==r.w||c.kind!==r.kind) dec.push({who:i,move:m,alt:c.w}); }
  if(r.riv){ const c=simC(ai,bi,{noRiv:true}); if(c.w!==r.w||c.kind!==r.kind) dec.push({who:-1,move:'因縁',alt:c.w}); }
  return stage(ai,bi,{r,upset:r.w!==null&&base.w!==r.w,baseW:base.w,dec});
}

/* ---------- 試合の型：組み合わせで流れと終わり方を変える（決定的） ---------- */
const CL={};
const realN=i=>POOL[i].filter(m=>m[7]!=='meta'&&m[7]!=='wp'&&!GENN.has(m[1])&&!['NAME','SENIORITY'].includes(m[0])).length;
const PHYS=['h','e','m','a','p','l','d','s'], PCNT=['P800','P166','P1343','P40','P106','P398','P190'], METAD=['_sl','_pv','_ch'];
const RLAB={h:'高さ',e:'標高',m:'重さ',a:'面積',p:'人口',l:'長さ',d:'深さ',s:'速さ',P800:'代表作の数',P166:'受賞の数',P1343:'載っている事典の数',P40:'子どもの数',P106:'肩書きの数',P398:'従える天体の数',P190:'姉妹都市の数',_sl:'言語版の数',_pv:'1年間の閲覧数',_ch:'記事の文字数',yr:'古さ（生まれた・できた年）'};
function rounds(i,j){ const out=[]; const add=k=>{ if(k==='h'&&!((QT[i]||{}).h>0&&(QT[j]||{}).h>0)) return; const a=dimv(i,k), b=dimv(j,k); if(a!==null&&b!==null&&a!==b) out.push({k,a,b}); };
  PHYS.forEach(add); PCNT.forEach(add); if(F[i][8]!==null&&F[j][8]!==null&&F[i][8]!==F[j][8]) out.push({k:'yr',a:-F[i][8],b:-F[j][8]}); METAD.forEach(add); return out; }
function matchType(ai,bi,an){ const r=an.r;
  if(r.riv) return 'innen';
  const cs=CL[ai], cb=CL[bi], R=rounds(ai,bi), nPhys=R.filter(x=>PHYS.includes(x.k)).length, nReal=R.filter(x=>!METAD.includes(x.k)).length;
  const same=cs&&cb&&cs[0]===cb[0];
  const gap=R.filter(x=>PHYS.includes(x.k)||x.k==='_pv').map(x=>({...x,r:Math.max(x.a,x.b)/Math.min(x.a,x.b)})).filter(x=>x.r>=(x.k==='_pv'?1200:1e4)).sort((x,y)=>y.r-x.r)[0];
  if(gap) return 'shunsatsu';
  if(R.length>=3&&(nPhys>=2||nReal>=2||(nReal>=1&&hash('kb'+QK(ai,bi))%3===0)||(same&&cs[1]!=='ヒト'&&nReal>=1)||(same&&cs[1]==='ヒト'&&nReal>=2))) return 'kurabe';
  if(r.w!==null&&r.kind==='KO'){ const w=r.w===ai?0:1; if(r.hp[w]/r.max[w]>=0.6) return 'shunsatsu'; }
  if((Math.max(realN(ai),realN(bi))<=1&&Math.min(realN(ai),realN(bi))===0)||(r.kind==='判定'&&Math.abs(r.hp[0]/r.max[0]-r.hp[1]/r.max[1])<0.12)) return 'doro';
  return 'normal'; }
const TLAB={innen:'因縁の対決',kurabe:'比べ合い',shunsatsu:'瞬殺',doro:'泥仕合',normal:'通常の試合'};
const fmtR=(k,v)=>k==='yr'?ys(-v):unitv(k,v);
/* 語り口：起きていることはすべて事実。それを、誰よりも真剣に実況・解説する */
const PK=(arr,key)=>arr[hash(String(key))%arr.length];
const fill=(s,o)=>s.replace(/\{(\w+)\}/g,(m,k)=>o[k]!==undefined?o[k]:m);
/* 試合の途中で、起きたことに真顔で一言添える（1試合3回まで、続けては入れない） */
const num=s=>{ const m=String(s||'').match(/[\d,]+(?:\.\d+)?/); return m?m[0]:''; };
const tgtNames=mv=>Array.isArray(mv&&mv[7])?mv[7].map(t=>t[0]).filter(Boolean):[];
const MID=[
 // 個別の技
 [e=>e.mv&&/召喚$/.test(e.mv[1])&&tgtNames(e.mv).length, e=>{ const T=tgtNames(e.mv)[0]; return [
   T+'は今日、別件で忙しかったそうです', T+'にとっては、完全にもらい事故です', '召喚された'+T+'、状況がよく分かっていない様子です',
   T+'も、まさか'+e.yn+'と戦うことになるとは思っていなかったでしょう', '呼ばれた側には、事情が説明されていません',
   'Wikidataに書いてある以上、'+T+'は来ないわけにはいかないのでしょう', T+'の交通費は、どちらの陣営が持つのでしょうか',
   T+'、来てはみたものの、何をすればいいのか分かっていません' ]; }],
 [e=>e.mv&&e.mv[1]==='名前で殴る', e=>{ const n=num(e.mv[2]); return [
   '名前の長さで殴る。データが尽きたときの、最後の手段です','読み仮名が、ここで役に立つとは','Wikipediaのふりがなは、こういう時のためにあったんですね',
   n+'音。数えたのは私です','名前は、記事がある限り誰にでもある。平等な技です', '音の数で殴る。言語学者が見たら泣くでしょう' ]; }],
 [e=>e.mv&&e.mv[1]==='年功序列'&&e.d>0, e=>[ '年齢で殴る。古くからある、由緒正しい技です','先輩風は、Wikipediaの中でも吹きます','敬語を使うべき場面でした','生まれた年で殴る。本人の努力とは一切関係ありません' ]],
 [e=>e.mv&&e.mv[1]==='年功序列'&&e.d===0, e=>[ '何も起きませんでした。それもまた、事実です','年齢不詳の相手に年功序列。審判も困っています','先輩風が吹いたつもりで、向かい風でした' ]],
 [e=>/足りなかった/.test(e.s), e=>[ '測量の世界では、誤差とは呼べない差です','挑む前に、相手の記事を読んでおくべきでした','数字で挑み、数字に負ける。美しい展開です','比べなければよかった。それが今の正直な気持ちでしょう' ]],
 [e=>e.mv&&e.mv[1]==='人海戦術', e=>[ num(e.mv[2])+'人以上が押し寄せる。全員、事情は知らされていません','人口で殴る。国勢調査の思わぬ使い道です','住民の皆さんは、今日が試合だと知っていたのでしょうか' ]],
 [e=>e.mv&&e.mv[1]==='標高落とし', e=>[ '標高から落ちてくる。物理的には、かなり危険です','海抜で殴る。登山家なら絶対にやらない技です' ]],
 [e=>e.mv&&e.mv[1]==='急降下', e=>[ '高さから降ってくる。建築基準法上の問題はないのでしょうか','高いところから殴る。古典的ですが、効きます' ]],
 [e=>e.mv&&e.mv[1]==='領土拡大', e=>[ '面積で迷子にする。地理の授業では習わない技です','広さは、それだけで暴力になりえます' ]],
 [e=>e.mv&&e.mv[1]==='のしかかり', e=>[ '体重でのしかかる。計量は試合前に済ませています','重さで殴る。理屈としては、これ以上ないほど明快です' ]],
 [e=>e.mv&&e.mv[1]==='全長包囲', e=>[ '全長で巻きつく。地図で見ると、かなり無理のある体勢です' ]],
 [e=>e.mv&&/保護動物の構え|文化財バリア/.test(e.mv[1]), e=>[ '守られているものを殴るのは、気が引けますね','保護の指定は、試合中も有効です','レッドリストが盾になる。IUCNも想定していなかった使い方でしょう','文化財を殴る。修復費用は誰が持つのでしょうか' ]],
 [e=>e.mv&&e.mv[1]==='歴戦の構え', e=>[ '記録された参戦'+num(e.mv[2])+'件。今日の一戦は、記録されるのでしょうか','戦の経験で構える。本物の戦場と比べれば、ここは平和です' ]],
 [e=>e.mv&&/作品ラッシュ|派生作品ラッシュ|代表作召喚/.test(e.mv[1]), e=>[ '作品が押し寄せる。著作権の扱いが少し気になります','作品で殴る。ファンの方は、目をそらしてください','全部読んだ人は、この会場にはいないでしょう' ]],
 [e=>e.mv&&e.mv[1]==='総力戦', e=>[ '構成要素が総出で来る。自分を分解して殴る、高度な技です','部品が全部出てきました。元に戻せるのでしょうか' ]],
 [e=>e.mv&&e.mv[1]==='正体開示', e=>[ '正体を明かすだけで攻撃になる。それがWikidataです','「'+e.mv[2]+'」。言われてみれば、そうでした','分類されただけで殴られる。理不尽ですが、事実です' ]],
 [e=>e.mv&&e.mv[1]==='要出典', e=>[ '出典がないことで殴られる。百科事典ならではの痛みです','出典を求められた側は、試合どころではありません','反論するにも、まず出典が要ります' ]],
 [e=>e.mv&&e.mv[1]==='書きかけ指摘', e=>[ '書きかけを指摘される。加筆の依頼は、ノートページでお願いします','書きかけでも、戦わなければならない時があります' ]],
 [e=>e.mv&&e.mv[1]==='画像攻撃', e=>[ '画像を投げる。ライセンス表記は試合後に確認されます','画像'+num(e.mv[2])+'枚。Wikimedia Commonsの皆さんには申し訳ない','画像で殴る。百聞は一見にしかず、を物理的に実践しています' ]],
 [e=>e.mv&&e.mv[1]==='見出し連打', e=>[ '見出しで殴る。目次の正しい使い方ではありません','節の見出しが飛んでくる。本文は置いてきたようです' ]],
 [e=>e.mv&&e.mv[1]==='カテゴリ包囲', e=>[ '分類されることが、こんなに苦しいとは','カテゴリで囲む。整理整頓が攻撃になる瞬間です' ]],
 [e=>e.mv&&/リンク乱打|リンク網|人脈マウント|リンク数マウント/.test(e.mv[1]), e=>[ 'リンクで縛る。ハイパーテキストの本来の使い方ではありません','青いリンクも、束ねれば縄になります','リンクの先にも記事があります。全員、巻き込まれています' ]],
 [e=>e.mv&&/多言語包囲|知名度マウント|多言語詠唱/.test(e.mv[1]), e=>[ '多くの言語で同時に責められる。翻訳の仕事が増えます','知名度で殴る。本人は何もしていません','言語の数は、時に拳より重い' ]],
 [e=>e.mv&&/長文で殴る|文字数マウント/.test(e.mv[1]), e=>[ '記事の長さで殴る。加筆した皆さんの努力が、いま報われました','長文で殴る。最後まで読んだ人はいないはずです','文字数は、積み重なると鈍器になります' ]],
 [e=>e.mv&&/注目の視線|閲覧数マウント/.test(e.mv[1]), e=>[ '閲覧数で殴る。アクセス解析の、最も物理的な活用です','読まれた回数で殴られる。読んだ人に罪はありません','人気で殴る。人気者は、それだけで強い','閲覧数の多さは、時に物理的な質量を持ちます' ]],
 [e=>e.mv&&/マウント$|見下ろし|重量差|数の暴力|長さ比べ|置き去り/.test(e.mv[1]), e=>[ '数字で上から殴る。いわゆるマウントです','本人は何もしていません。数字が殴っています','比べられた側には、反論の機会が与えられていません' ]],
 [e=>e.mv&&e.mv[1]==='同族召喚', e=>[ '同じ種類の仲間が押し寄せる。全員、呼ばれた理由を知りません','仲間の数で殴る。数え間違いがないことを祈ります' ]],
 [e=>e.mv&&e.mv[1]==='外部リンク渡り', e=>[ '外部リンクを飛び石にする。リンク切れだったら落ちていました','外部サイトを経由して回り込む。セキュリティ的には推奨されません' ]],
 [e=>e.mv&&e.mv[1]==='古参の貫禄', e=>[ '記事の作成日で威張る。Wikipedia歴は、ここで効いてきます','古株の構え。初版の頃の苦労がにじみます' ]],
 [e=>e.mv&&e.mv[1]==='分身の術', e=>[ '転送ページで分身する。リダイレクトの新しい活用法です','別名の数だけ自分がいる。少し怖いですね' ]],
 [e=>e.mv&&e.mv[1]==='本業', e=>[ e.mv[2]+'としての本領。この試合が本業かどうかは別として', '本業で勝負する。ここが職場かどうかは、議論の余地があります' ]],
 [e=>e.mv&&e.mv[1]==='北から目線', e=>[ '緯度で見下ろす。地球が丸いことは、この際考えません','北にいるだけで偉い。地図の上では、そういうことになります' ]],
 [e=>e.mv&&e.mv[0]==='HEAL', e=>[ '試合中に回復する。ルール上は問題ありません','記事に書いてあることで回復する。便利な体です' ]],
 // 状況
 [e=>/因縁で1\.5倍/.test(e.s), e=>[ '因縁の一撃は1.5倍。データで裏付けられた恨みです','初撃に因縁が乗りました。記述の重みです' ]],
 [e=>/構えで\d+軽減/.test(e.s), e=>[ '構えが間に合いました。読み合いの勝利です','構えていた。その一点だけで、被害が減りました' ]],
 [e=>/大技の気配を察して/.test(e.s), e=>[ '危険を察知して構える。記事にも本能はあるようです','読み切っていましたね。記事を読んだのかもしれません' ]],
 [e=>e.big, e=>[ 'これは効いた。記事が一段落削られたような衝撃です','大きい。いまの一撃で、要約欄が書き換わったかもしれません','重い一撃です。脚注まで響いています','いまのは痛い。版の差分で見ても、かなりの削除量です','効いています。カテゴリがいくつか外れたかもしれません' ]],
 [e=>/技を出し尽くした/.test(e.s), e=>[ 'ここからは地道に殴る。記事の情報は、すべて使い切りました','技が尽きました。ここからは、記事に書いていない戦いです' ]],
];
function midKai(log,key,ai,bi){ const out=[]; let n=0, gap=0; const usedP=new Set();
  log.forEach((x,idx)=>{ out.push(x); gap++; if(n>=3||x.side<0||gap<2||idx===log.length-1) return;
    const e={...x,yn:x.side===0?(F[bi]||[])[0]:(F[ai]||[])[0],big:x.d>0&&x.hp&&x.d>=0.35*Math.max(...x.hp.map((h,k)=>k===(x.side===0?1:0)?h+x.d:0))};
    for(let k=0;k<MID.length;k++){ const [test,pool]=MID[k]; if(usedP.has(k)) continue; let ok=false; try{ ok=test(e); }catch(_){} if(!ok) continue;
      usedP.add(k); if(hash(key+'|'+idx+'|'+k)%10<3) continue;   // いつも喋るわけではない
      const P=pool(e); out.push({t:x.t,side:-1,d:0,hp:x.hp,s:'解説「'+P[hash(key+'/'+k+'/'+idx)%P.length]+'」',kai:1}); n++; gap=0; break; } });
  return out; }
function stage(ai,bi,an){ const type=matchType(ai,bi,an); const r=an.r; const A=F[ai][0], B=F[bi][0]; an.type=type; an.tlabel=TLAB[type];
  const K0=F[ai][2]+'/'+F[bi][2]; let ln=0;
  const sys=(s,hp)=>({t:0,side:-1,s,d:0,hp:hp||[r.max[0],r.max[1]]});
  const kai=(s,hp)=>({t:0,side:-1,s:'解説「'+s+'」',d:0,hp:hp||[r.max[0],r.max[1]],kai:1});
  const P=(arr,o)=>fill(PK(arr,K0+'#'+(ln++)),o||{});
  const endHP=()=>{ const l=r.log[r.log.length-1]; return l?l.hp:[r.max[0],r.max[1]]; };

  /* ---------- 因縁の対決 ---------- */
  if(type==='innen'){ const rv=rival(ai,bi);
    const log=[sys('【因縁の対決】'+rv+'。'),
      sys(P(['この一点において、両者は決して相容れない。','この記述がある限り、両者が同じ土俵に上がる日は来ないはずだった。','長年、誰も触れずにきた因縁である。'])),
      sys(P(['{A}と{B}、ついに相まみえる。','{A}、入場。{B}、入場。会場が静まり返る。','両者、目を合わせない。Wikidataに書いてあるからだ。'],{A,B})),
      ...midKai(r.log.filter(x=>x.side>=0),K0,ai,bi)];
    const W=r.w===null?null:F[r.w][0], L=r.w===null?null:F[r.w===ai?bi:ai][0];
    log.push(sys(r.w===null?'因縁、決着つかず。この続きは記事の編集合戦に持ち越された。':P(['因縁、決着。{W}が{L}を下した。','{W}、因縁を断ち切った。少なくとも今日のところは。','{L}、膝をつく。因縁の記述だけが、静かに残った。'],{W,L}),endHP()));
    log.push(kai(P(['Wikidataの記述は変わりません。ただ、今日の勝敗は語り継がれるでしょう。どこにも書かれませんが','因縁は、終わりませんね。データがそう言っている以上は','両陣営とも、編集履歴に恥じない戦いでした','明日になれば、両者はまた何事もなかったようにリンクで結ばれています','この因縁を記述した編集者に、今日の試合を見せたかった']),endHP()));
    an.r={...r,log}; return an; }

  /* ---------- 瞬殺 ---------- */
  if(type==='shunsatsu'){ const R=rounds(ai,bi); const gap=R.filter(x=>PHYS.includes(x.k)||x.k==='_pv').map(x=>({...x,r:Math.max(x.a,x.b)/Math.min(x.a,x.b)})).filter(x=>x.r>=(x.k==='_pv'?1200:1e4)).sort((x,y)=>y.r-x.r)[0];
    if(gap){ const w=gap.a>gap.b?ai:bi, W=F[w][0], L=w===ai?B:A, hp=[r.max[0],r.max[1]]; hp[w===ai?1:0]=0;
      const rt=gap.r>=1e8?jn(gap.r)+'倍':ratioTxt(gap.r), vw=fmtR(gap.k,Math.max(gap.a,gap.b)), vl=fmtR(gap.k,Math.min(gap.a,gap.b)), lab=RLAB[gap.k];
      const o={W,L,vw,vl,lab,rt,n:Math.max(gap.a,gap.b),m:Math.min(gap.a,gap.b)};
      const log=[sys('【瞬殺】試合開始のゴングが鳴る。')];
      if(gap.k==='_pv'){
        log.push(sys(P(['{L}、名乗りを上げる。客席の反応は控えめだった。','{L}、深く一礼して入場する。拍手は、まばらだった。','{L}、入場。会場の何人かが、記事名を検索し始めた。'],o)));
        log.push(sys(P(['{W}が入場すると、{vw}読まれてきた視線が一斉に{L}へ向いた。','{W}は名乗る必要がない。{vw}読まれているので、全員もう知っている。','{L}の記事は{vl}、{W}は{vw}。読まれた回数の差が、そのまま圧になった。'],o)));
      } else {
        log.push(sys(P(['{L}、構える。{W}は特に構えない。{lab}{vw}。それ自体が{W}の構えだ。','{L}、間合いを測る。{W}の{lab}は{vw}。間合いという概念が成立しない。','{L}、{W}を見上げる。見上げても、まだ{lab}{vw}の全体は見えない。'],o)));
        log.push(sys(P(['{L}は{W}の{lab}を測ろうとした。{vl}用の物差しでは、目盛りが足りなかった。','{L}の{lab}は{vl}。{W}の{lab}は{vw}。以上である。','{L}、渾身の一撃を放つ。{W}は気づかなかった。'],o)));
      }
      log.push({t:1,side:w===ai?0:1,d:r.max[w===ai?1:0],hp,s:P(['{W}、特に何もしていない。{L}の方が勝手に倒れた。','決着。所要時間、0.3カウント。','{W}がそこにいるだけで、{L}は吹き飛んだ。'],o)});
      log.push(kai(P(['差は{rt}です。これを試合と呼んでいいのか、我々はいまも議論を続けています','{lab}で{rt}の差。戦術や気合いでどうにかなる差ではありません','{L}は何も悪くありません。ただ、{lab}が足りなかった','正直に申し上げて、組み合わせを決めた人に問題があります','{L}陣営、試合後のコメントは「比較の対象として不適切」とのことです','実況席から見えていたのは、ほぼ{W}だけでした'],o),hp));
      an.r={...r,log,w,kind:'KO',tick:1,hp,how:lab+'の差で瞬殺',summoned:[]}; an.tail='差は'+rt+'。勝負にならなかった。'; an.dec=[]; an.upset=false; return an; }
    const wS=r.w===ai?0:1, W=F[r.w][0], L=r.w===ai?B:A; const hits=r.log.filter(x=>x.side===wS);
    const log=[sys('【瞬殺】試合開始のゴングが鳴る。'),...hits.slice(-2)];
    log.push(sys(P(['{L}は反撃の機会をうかがっていた。うかがっているうちに終わった。','{L}、まだ自分の技を一つも説明していない。','{L}陣営、タオルを投げる準備すら間に合わなかった。'],{W,L}),endHP()));
    log.push(kai(P(['{W}の残りHPは'+r.hp[wS]+'。ほぼ無傷です。{L}にとっては、事実の暴力でした','技の解説をしようと思っていたのですが、終わってしまいました','{L}は悪くありません。相手が{W}だった、それだけです'],{W,L}),endHP()));
    an.r={...r,log}; an.dec=an.dec.filter(d=>d.who===r.w); return an; }

  /* ---------- 比べ合い ---------- */
  if(type==='kurabe'){ const R=rounds(ai,bi); const pri=x=>PHYS.includes(x.k)?0:PCNT.includes(x.k)?1:x.k==='yr'?2:3;
    const pick=[...R].sort((x,y)=>pri(x)-pri(y)||(hash(K0+x.k)%7)-(hash(K0+y.k)%7)).slice(0,5);
    const n=pick.length%2?pick.length:pick.length-1; const Q=pick.slice(0,n); let sa=0,sb=0; const hp=[r.max[0],r.max[1]]; const need=Math.ceil(n/2)+1;
    const step=[Math.ceil(r.max[0]/need),Math.ceil(r.max[1]/need)];
    const log=[sys(P(['【比べ合い】本日、殴り合いは行わない。両者の数字を、厳正に比べる。','【比べ合い】両者、拳を収める。ここからは数字の格闘技だ。','【比べ合い】審判団が入場する。手にしているのは物差しと電卓である。'])),
      sys(P(['全{n}番勝負。数字の大きいほうが一本を取る。それ以上でも以下でもない。','全{n}番勝負。勝敗は、すでにWikipediaに書いてある。'],{n}))];
    const KANJI=['一','二','三','四','五'];
    Q.forEach((x,k)=>{ const aw=x.a>x.b; const W=aw?A:B, L=aw?B:A; const va=fmtR(x.k,x.a), vb=fmtR(x.k,x.b); const ratio=Math.max(x.a,x.b)/Math.min(x.a,x.b);
      const o={A,B,W,L,va,vb,lab:RLAB[x.k],k:KANJI[k]};
      let intro;
      if(x.k==='yr') intro=P(['第{k}番、古さ。{A}は{va}から、{B}は{vb}から存在していると申告する。','第{k}番、古さ。両者、戸籍に相当する資料を提出する。{A}、{va}。{B}、{vb}。'],o);
      else if(x.k==='_sl') intro=P(['第{k}番、言語版の数。{A}、{va}分の翻訳者を引き連れて入場。{B}は{vb}。','第{k}番、言語版の数。両陣営、各国語版の名刺を並べる。{A}、{va}。{B}、{vb}。'],o);
      else if(x.k==='_pv') intro=P(['第{k}番、1年間の閲覧数。両陣営、アクセス解析の結果を厳粛に提出する。{A}、{va}。{B}、{vb}。','第{k}番、閲覧数。どれだけ読まれたかで殴る、最も現代的な一番。{A}、{va}。{B}、{vb}。'],o);
      else if(x.k==='_ch') intro=P(['第{k}番、記事の文字数。両者、記事を印刷して持ち込む。{A}は{va}、{B}は{vb}。','第{k}番、文字数。{A}の記事は{va}、{B}は{vb}。審判団は全文を読まずに数えた。'],o);
      else intro=P(['第{k}番、{lab}。{A}、{va}の札を掲げる。{B}、{vb}の札で応じる。','第{k}番、{lab}。両者、己の{lab}を申告せよ。{A}、{va}。{B}、{vb}。','第{k}番、{lab}。{A}、{va}。{B}、{vb}。会場がどよめく。'],o);
      if(aw) sa++; else sb++; const lo=aw?1:0; hp[lo]=Math.max(0,hp[lo]-step[lo]);
      const res=ratio>=10?P(['測るまでもなかった。{W}の一本。','審判団、物差しを出しかけて、しまった。{W}。','{W}、一本。{L}陣営は数字を二度見した。'],o)
        :ratio<1.1?P(['審判団、定規を三度当て直す。わずかな差で{W}に旗。','協議は長引いた。僅差で{W}の一本。','審判団、桁を数え直す。{W}、辛くも一本。'],o)
        :P(['審判団、協議の末、{W}に旗。','{W}の一本。','旗が上がる。{W}。'],o);
      log.push({t:k+1,side:aw?0:1,d:0,hp:[hp[0],hp[1]],s:intro+' '+res+'（'+sa+'対'+sb+'）'});
      if(ratio>=100) log.push(kai(P(['{lab}で{L}の'+ratioTxt(ratio)+'。比べる前から分かっていたことですが、比べました','この一番は、比べるという行為の意味を問いかけています','{L}陣営としては、この項目が選ばれた時点で覚悟していたでしょう','桁が違います。桁が違うものを比べるのも、比べ合いの醍醐味です','{W}の数字を読み上げるのに、少し時間がかかりました'],o),[hp[0],hp[1]]));
      else if(ratio<1.05) log.push(kai(P(['僅差です。記事が一度編集されていれば、結果は逆だったかもしれません','この差は誤差ではありません。誤差なら審判団が困ります','ほぼ同じです。ほぼ同じですが、比べ合いに「ほぼ」はありません','審判団、メガネを拭いています','この差を見るために、我々はここに集まりました','{L}陣営、写真判定を要求しています。数字に写真はありません'],o),[hp[0],hp[1]])); });
    const w=sa>sb?ai:bi, W=F[w][0], L=w===ai?B:A; const lastW=[...Q].reverse().find(x=>(x.a>x.b)===(sa>sb)); an.tail='決勝点は【'+RLAB[lastW.k]+'】。';
    const o={W,L,s:Math.max(sa,sb),t:Math.min(sa,sb),lab:RLAB[lastW.k]};
    log.push(sys(fill('{W}、{s}勝{t}敗で比べ合いを制した。',o)+(o.t===0?'完封である。':''),[hp[0],hp[1]]));
    log.push(kai(o.t===0?P(['{W}、数字の上では完勝です。数字の上では','{L}にとっては、どの項目を選んでも厳しい一日でした','一本も取れませんでした。{L}陣営は今夜、Wikipediaの加筆に励むことでしょう','全項目で上回る。比べ合いとして、これ以上なく正しい結果です'],o)
      :P(['最後は{lab}が明暗を分けました。{L}陣営は今夜、{lab}を見直すことになるでしょう','互いに一歩も引かない、いい比べ合いでした。誰も殴られていませんが','{L}も健闘しました。数字が小さかっただけです','審判団の電卓が、今日も正確に仕事をしました','数字は変えられません。変えられるのは、次の項目選びだけです'],o),[hp[0],hp[1]]));
    an.r={...r,log,w,kind:'比べ合い',tick:n,hp,how:Math.max(sa,sb)+'勝'+Math.min(sa,sb)+'敗で勝利',summoned:[]}; an.dec=[]; an.upset=false; return an; }

  /* ---------- 泥仕合 ---------- */
  if(type==='doro'){ const moves=[], normal=[]; r.log.forEach(x=>{ if(x.side<0) return; (/【/.test(x.s)?moves:normal).push(x); });
    const log=[sys(P(['【泥仕合】両者、記事の情報量に恵まれているとは言いがたい。','【泥仕合】互いに決め手を持たない者同士の戦いが始まる。','【泥仕合】本日の対戦、事前の予想は「どちらでもいい」が最多だった。']))];
    midKai(moves.slice(0,4),K0,ai,bi).forEach(m=>log.push(m));
    const last=r.log[r.log.length-1]; const o={A,B,n:normal.length};
    if(normal.length>=2) log.push({...last,side:-1,d:0,s:P(['（{A}、地道に殴る。{B}、地道に殴り返す。これが{n}回続いた。観客の一部が帰り始める）','（以後、技のない殴り合いが{n}回続く。実況席では弁当が配られた）','（{n}回の殴り合い。どちらも相手の記事を読んでいないことが明らかになっていく）'],o)});
    if(r.kind==='判定'){ const C=[['_ch','記事の文字数','文字数の多いほう'],['m0','名前の音の数','名前が長いほう']];
      const c=C[hash(K0)%C.length]; const va=c[0]==='m0'?F[ai][4]:dimv(ai,c[0]), vb=c[0]==='m0'?F[bi][4]:dimv(bi,c[0]);
      log.push({...last,side:-1,d:0,s:'15カウント終了。両者、まだ立っている。'});
      log.push({...last,side:-1,d:0,s:P(['審判団、協議に入る。……協議は長引いている。','審判団、協議に入る。一人が「もう引き分けでいいのでは」と言い、却下された。'])});
      let w=r.w;
      if(va!==null&&vb!==null&&va!==vb){ w=va>vb?ai:bi; const W=F[w][0], L=w===ai?B:A; const fa=c[0]==='m0'?va+'音':unitv(c[0],va), fb=c[0]==='m0'?vb+'音':unitv(c[0],vb);
        log.push({...last,side:-1,d:0,s:'審判団は苦渋の決断として、勝敗を「'+c[1]+'」で決めると発表した。'+A+'、'+fa+'。'+B+'、'+fb+'。'+c[2]+'、'+W+'の勝ち。'});
        log.push({...last,side:-1,d:0,s:P(['{L}陣営から抗議の声が上がったが、受理されなかった。','{L}、判定に一礼する。納得はしていない。','{W}、勝ち名乗りを受ける。本人が一番驚いている。'],{W,L})});
        an.tail='泥仕合の末、判定基準は「'+c[1]+'」。'; }
      else log.push({...last,side:-1,d:0,s:'審判団、残りHPの差で'+(w===null?'引き分け':F[w][0]+'の勝ち')+'を宣告。異論は出なかった。誰も見ていなかったからだ。'});
      log.push(kai(P(['泥仕合でした。いい意味でも悪い意味でもなく、泥仕合でした','両者とも、記事がもう少し長ければ違う展開もあったでしょう','この試合で得たものは何か。我々は答えを持ち合わせていません','判定基準を決めた審判団の勇気を、まず称えたいと思います','記録上は決着です。記憶には、たぶん残りません']),last.hp));
      an.r={...r,log,w,how:'泥仕合の末に判定勝ち'}; if(w!==r.w){ an.dec=[]; an.upset=false; } return an; }
    log.push({...last,side:-1,d:0,s:r.w===null?'泥仕合の末、両者同時に倒れた。審判団は顔を見合わせた。':P(['泥仕合の末、{W}がかろうじて立っていた。理由は誰にも分からない。','{L}、ゆっくりと倒れる。{W}も倒れかけたが、踏みとどまった。','決着。{W}の勝ち。ただし、勝ったという実感は本人にもない。'],{W:F[r.w][0],L:F[r.w===ai?bi:ai][0]})});
    log.push(kai(P(['泥仕合でした。いい意味でも悪い意味でもなく、泥仕合でした','記録上は{W}の勝ちです。記録に残す価値があるかは別として','両者、次は記事を育ててから来てほしいですね'],{W:r.w===null?'':F[r.w][0]}),last.hp));
    an.r={...r,log,how:'泥仕合を制してKO勝ち'}; return an; }

  /* ---------- 通常の試合：決着に解説を一言 ---------- */
  if(r.log.length){ const last=r.log[r.log.length-1]; const W=r.w===null?'':F[r.w][0], L=r.w===null?'':F[r.w===ai?bi:ai][0];
    const lastHit=[...r.log].reverse().find(x=>x.side>=0&&x.d>0); const lm=lastHit?(lastHit.s.match(/【(.+?)】/)||[])[1]:null;
    const o={W,L,lm:lm||'通常攻撃'};
    const wS=r.w===ai?0:1, rem=r.w===null?0:r.hp[wS]/r.max[wS];
    const pool=r.w===null?['相打ちです。事実と事実がぶつかると、こういうことも起きます','両者同時に倒れました。Wikidata上は、どちらも健在です','引き分け。記事の編集合戦なら、まだ続いていたでしょう']
      :an.upset?['能力値では{L}が上でした。事実は、能力値より強い','番狂わせです。Wikidataの記述ひとつで、ここまで変わるものなんですね','{L}陣営は、記事のどの一行に負けたのかを調べることになるでしょう','下馬評を覆しました。下馬評を出していたのは私です']
      :r.kind==='判定'?['判定です。両者、記事の続きで巻き返してほしい','15カウントでは決着がつきませんでした。記事の長さが足りなかったのかもしれません','判定勝ち。勝った側も、少し申し訳なさそうです']
      :r.tick<=4?['{W}、{t}カウントで終わらせました。記事を読む時間もありませんでした','早い。{L}は自己紹介の途中でした','開始早々の決着。{L}の記事は、いまも静かに公開されています']
      :rem<0.1?['{W}、残りHPわずか。勝者も満身創痍です','紙一重でした。一行の加筆で結果は逆だったでしょう','{W}、立ってはいますが、記事の半分は持っていかれた気分でしょう']
      :lm?['決まり手は【{lm}】。事実で殴るとは、こういうことです','最後は【{lm}】。{W}、記事に書いてあることを全部使い切りました','【{lm}】で決着。{L}も、書いてあることで精一杯戦いました','【{lm}】。この技を、記事の編集者は想定していなかったはずです']
      :['最後は普通に殴って決着。技を出し尽くしたあとは、記事の長さではなく気持ちです','技が尽きてからが本当の勝負でした。地味でしたが'];
    o.t=r.tick;
    an.r={...r,log:[...midKai(r.log,K0,ai,bi),kai(P(pool,o),last.hp)]}; }
  return an; }

/* ---------- 保留・通報・確認（判定できない記事の扱い） ---------- */
const HOLD={};            // 事件の疑いがあり、確認するまで対戦させない記事 {index: 理由}
const QIX={};
function register(rec){ const t=rec.f[1]; /* 振り分けは正式な記事名で（表示名は同名の別記事と重なることがある） */ if(TIX[t]!==undefined) return TIX[t]; const i=F.length;
  F.push(rec.f); TIX[t]=i; QIX[rec.f[2]]=i; EXT[i]=rec.ext||[]; if(rec.qt) QT[i]=rec.qt; if(rec.wp) WP[i]=rec.wp; if(rec.gen) GEN[i]=rec.gen; if(rec.hold) HOLD[i]=rec.hold;
  for(const [q,txt] of Object.entries(rec.rv||{})){ const j=QIX[q]; if(j!==undefined&&j!==i) RV[Math.min(i,j)+','+Math.max(i,j)]=txt; }
  CL[i]=rec.p?['Q5','ヒト']:(rec.gen&&rec.gen.c?[rec.gen.c,rec.gen.c]:undefined); prepMeta(i); POOL[i]=makePool(i); if(rec.hold||EXCL.has(t)) BLOCK.add(i); return i; }
const BLOCK=new Set();

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
