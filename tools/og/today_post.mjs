// 今日の一戦を公式Xに投稿するための通知（半自動）：毎朝、投稿文を作って ntfy でスマホに送る
//   通知をタップすると、Xの投稿画面が文とリンクの入った状態で開く。投稿ボタンを押すのは本人（自動では投稿しない）
//   組み合わせは、サイトの共有カード（?today=1&d=日付 の og:title）から読む。画像は共有カードとしてXが出す
const SITE = process.env.SITE || 'https://hyakkakenten.com', NTFY = process.env.NTFY_TOPIC;
const day = process.env.DAY || new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
const url = SITE + '/?today=1&d=' + day;
const html = await fetch(url, { headers: { 'User-Agent': 'hyakka-kenten today-post (https://github.com/y-krn)' } }).then(r => r.text());
const m = html.match(/<meta property="og:title" content="今日の一戦 ([^：]+)：(.+?) ― 百科拳典"/);
if (!m) { console.log('今日の一戦の組み合わせを読めませんでした'); if (NTFY) await fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic: NTFY, title: '百科拳典：今日の一戦の投稿文を作れませんでした', message: '共有カードがまだできていない可能性があります。サイトを確かめてください。', click: url }) }); process.exit(0); }
const unesc = s => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const md = m[1], vs = unesc(m[2]);
const text = `【百科拳典 今日の一戦 ${md}】${vs}\nどっちが勝つと思う？ 予想してから観戦しよう\n#百科拳典`;
const intent = 'https://x.com/intent/post?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(url);
console.log(text + '\n' + url);
if (NTFY) {
  await fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
    topic: NTFY, title: `今日の一戦を投稿（${md}）`, message: `${vs}\nタップするとXの投稿画面が開きます。`, tags: ['loudspeaker'], click: intent,
    actions: [{ action: 'view', label: 'Xで投稿する', url: intent }, { action: 'view', label: '試合を見る', url }] }) });
  console.log('通知しました');
}
