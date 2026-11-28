// 王座戦の夜のまとめ通知（GitHub Actions から毎晩動かす）
//   その日（日本時間）に王座の交代があったときだけ、ntfy に「今日の王座戦」を送る。タップするとXの投稿画面が開く
//   あわせて、1時間ごとの片付けが止まっていないかも見る（止まっていたら別の通知を送る）
//   環境変数: SITE（既定 https://hyakkakenten.com）, NTFY_TOPIC（なければ何もしない）, DAY（試すとき：YYYY-MM-DD）
const SITE = process.env.SITE || 'https://hyakkakenten.com', NTFY = process.env.NTFY_TOPIC;
const DISC = '※Wikipediaの記述をもとにした架空の試合です。実在の国・団体・人物の優劣を示すものではありません';
const xlen = s => [...s].reduce((n, c) => n + (c.codePointAt(0) < 0x1100 ? 1 : 2), 0);   // Xの文字数の数え方
const d = await fetch(SITE + '/api/throne/day' + (process.env.DAY ? '?d=' + process.env.DAY : '')).then(r => r.json());
console.log(JSON.stringify(d));
// 1時間ごとの片付け（古い番号・IPを消す処理）が止まっていないかを見る。3時間より前で止まっていたら、まとめとは別に知らせる
if (typeof d.cleanupAt === 'number' && Date.now() - d.cleanupAt > 3 * 3600e3) {
  const h = Math.round((Date.now() - d.cleanupAt) / 3600e3);
  console.log(`片付けが${h}時間止まっています`);
  if (NTFY) await fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
    topic: NTFY, title: '百科拳典：片付けが止まっています', message: `古い番号・IPを消す1時間ごとの片付けが、${h}時間動いていません。Cloudflare の管理画面で、Worker の定期実行（Cron）を確かめてください。`, tags: ['warning'] }) });
}
// 百科ダンジョンのお題が30日先まであるかを見る（ダンジョンのお題をまだ配っていなければ何もしない）
{ const j = n => new Date(Date.now() + 9 * 3600e3 + n * 864e5).toISOString().slice(0, 10), get = day => fetch(SITE + '/data/dg/' + day.slice(0, 7) + '.json').then(r => r.ok ? r.json() : null).catch(() => null);
  const now = await get(j(0)), later = await get(j(30));
  if (now && !(later && later[j(30)])) { console.log('ダンジョンのお題が30日先までありません');
    if (NTFY) await fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      topic: NTFY, title: '百科拳典：ダンジョンのお題が残り少ない', message: `お題の有効期間が30日後（${j(30)}）に切れます。GitHub の「配る記事データを作る（正本から）」を動かして、お題を作り直してください（180日分できます）。`, tags: ['warning'] }) }); } }
if (!d.changes) { console.log('今日は王座の交代がありませんでした。送りません'); process.exit(0); }
const md = (+d.day.slice(5, 7)) + '月' + (+d.day.slice(8, 10)) + '日';
const head = d.changes >= 10 ? `王座が${d.changes}回入れ替わる大乱戦。` : d.changes >= 3 ? `王座が${d.changes}回入れ替わる混戦。` : `王座の交代は${d.changes}回。`;
const lines = [`【今日の王座戦 ${md}】${head}`, `挑戦は${d.challenges}回。`];
const same = d.best && d.best.display === d.champ.display && d.best.defenses === d.champ.defenses;   // いちばん粘ったのが、いまの王者（同じ記事が前に王者だったときの防衛は別に書く）
if (d.best && d.best.defenses > 0 && !same) lines.push(`いちばん粘ったのは${d.best.display}（防衛${d.best.defenses}回${d.best.display === d.champ.display ? '。いまは王座を取り返したところ' : ''}）。`);
lines.push(`いまの王者は第${d.champ.reignNo}代 ${d.champ.display}${d.champ.defenses > 0 ? `（防衛${d.champ.defenses}回）` : ''}。`, '#百科拳典');
while (lines.length > 2 && xlen(lines.join('\n') + '\n' + DISC) > 280 - 24) lines.splice(lines.length - 2, 1);   // 長すぎるときは途中の行から削る
const text = lines.join('\n') + '\n' + DISC, url = SITE + '/';
console.log(text);
if (!NTFY) { console.log('NTFY_TOPIC がないので送りません'); process.exit(0); }
const intent = 'https://x.com/intent/post?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(url);
const r = await fetch('https://ntfy.sh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
  topic: NTFY, title: `今日の王座戦 ${md}：交代${d.changes}回`, message: text + '\n\nタップするとXの投稿画面が開きます', tags: ['crown'], click: intent,
  ...(d.lastWin ? { attach: SITE + '/og/c/' + d.lastWin + '.jpg', filename: 'hyakkakenten-' + d.lastWin + '.jpg' } : {}),
  actions: [{ action: 'view', label: 'Xで投稿', url: intent, clear: true }, { action: 'view', label: '王座戦を見る', url }] }) });
console.log('通知', r.status);
if (!r.ok) process.exit(1);
