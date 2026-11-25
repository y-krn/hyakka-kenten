// Cloudflare Web Analytics（ブラウザの計測）から、表示のずれ（CLS）の内訳を読むだけ。何も変えない
// 使うもの：CLOUDFLARE_API_TOKEN（アカウントの解析を読む権限が要る）、CLOUDFLARE_ACCOUNT_ID
const T=process.env.CLOUDFLARE_API_TOKEN, A=process.env.CLOUDFLARE_ACCOUNT_ID, DAYS=+(process.env.DAYS||7);
const gql=async(query,variables={})=>{ const r=await fetch('https://api.cloudflare.com/client/v4/graphql',{method:'POST',headers:{'Authorization':'Bearer '+T,'Content-Type':'application/json'},body:JSON.stringify({query,variables})}); const j=await r.json(); if(j.errors&&j.errors.length) console.log('ERR',JSON.stringify(j.errors).slice(0,800)); return j.data; };
// 1. 使える項目を調べる（名前の違いに備える）
const intro=async n=>{ const d=await gql(`{__type(name:"${n}"){fields{name type{name kind ofType{name}}}}}`); return ((d&&d.__type&&d.__type.fields)||[]).map(f=>f.name); };
const dimsT='AccountRumWebVitalsEventsAdaptiveGroupsDimensions';
const dims=await intro(dimsT); console.log('dims', dims.join(','));
const top=await intro('AccountRumWebVitalsEventsAdaptiveGroups'); console.log('groups', top.join(','));
const sumF=await intro('AccountRumWebVitalsEventsAdaptiveGroupsSum'); console.log('sum', sumF.join(','));
const avgF=await intro('AccountRumWebVitalsEventsAdaptiveGroupsAvg'); console.log('avg', avgF.join(','));
const qF=await intro('AccountRumWebVitalsEventsAdaptiveGroupsQuantiles'); console.log('quantiles', qF.join(','));
// 2. サイトを探す
const since=new Date(Date.now()-DAYS*864e5).toISOString().slice(0,10), until=new Date(Date.now()+864e5).toISOString().slice(0,10);
const host=dims.includes('requestHost')?'requestHost':null;
const want=['cumulativeLayoutShiftElement','cumulativeLayoutShiftPath','requestPath','deviceType','userAgentBrowser','countryName'].filter(x=>dims.includes(x));
const S=[...sumF.filter(x=>/layoutShift|visits|count/i.test(x))], V=[...avgF.filter(x=>/layoutShift/i.test(x))], Q=qF.filter(x=>/layoutShift/i.test(x));
const body=(dd)=>`count ${S.length?'sum{'+S.join(' ')+'}':''} ${V.length?'avg{'+V.join(' ')+'}':''} ${Q.length?'quantiles{'+Q.join(' ')+'}':''} dimensions{${dd.join(' ')}}`;
const filt=`{date_geq:"${since}",date_leq:"${until}"${host?',requestHost:"hyakkakenten.com"':''}}`;
for(const dd of [[...(host?[host]:[]),'deviceType'].filter(x=>dims.includes(x)), want.filter(x=>x!=='countryName'&&x!=='userAgentBrowser'), ['cumulativeLayoutShiftElement','deviceType'].filter(x=>dims.includes(x)), ['requestPath','deviceType'].filter(x=>dims.includes(x))]){
  const d=await gql(`query{viewer{accounts(filter:{accountTag:"${A}"}){rumWebVitalsEventsAdaptiveGroups(limit:60,filter:${filt},orderBy:[count_DESC]){${body(dd)}}}}}`);
  const rows=d&&d.viewer&&d.viewer.accounts[0]&&d.viewer.accounts[0].rumWebVitalsEventsAdaptiveGroups;
  console.log('CHJSON'+JSON.stringify({by:dd,rows}));
}
