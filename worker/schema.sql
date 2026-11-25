-- 百科拳典 王座戦（何度流しても壊れないよう IF NOT EXISTS）
CREATE TABLE IF NOT EXISTS reigns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,        -- Wikipediaの正式な記事名
  display TEXT NOT NULL,      -- 表示名
  holder TEXT NOT NULL,       -- 王座を取った人の名前
  started_at TEXT NOT NULL,
  ended_at TEXT,              -- NULL ならいまの王者
  ended_by TEXT,              -- 倒した記事の表示名
  defenses INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS reigns_open ON reigns(ended_at);
CREATE INDEX IF NOT EXISTS reigns_def ON reigns(defenses DESC);
CREATE TABLE IF NOT EXISTS challenges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reign_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  display TEXT NOT NULL,
  name TEXT NOT NULL,
  result TEXT NOT NULL,       -- win / lose / draw / late
  how TEXT,
  at TEXT NOT NULL,
  iphash TEXT NOT NULL,
  client TEXT,                -- ブラウザごとの番号（を、さらにハッシュしたもの）
  UNIQUE(reign_id, title)
);
CREATE INDEX IF NOT EXISTS ch_ip ON challenges(iphash, at);
CREATE INDEX IF NOT EXISTS ch_title ON challenges(title, reign_id);   -- 記事名で過去の挑戦を探す（歴代王者の一覧・同じ組み合わせの対戦）
-- みんなの対戦数（自由対戦はブラウザでまとめて数えて、ときどき送ってもらう）
CREATE TABLE IF NOT EXISTS stats (k TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS plays (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  n INTEGER NOT NULL,          -- まとめて送られてきた対戦数
  at TEXT NOT NULL,
  iphash TEXT NOT NULL,
  client TEXT,
  kt INTEGER NOT NULL DEFAULT 0,   -- うち今日の一戦
  km INTEGER NOT NULL DEFAULT 0,   -- うちあなたの代表戦
  kf INTEGER NOT NULL DEFAULT 0,   -- うち仲間図鑑から
  kd INTEGER NOT NULL DEFAULT 0    -- うち百科ダンジョン
);
CREATE INDEX IF NOT EXISTS plays_client ON plays(client, at);
CREATE INDEX IF NOT EXISTS plays_ip ON plays(iphash, at);
-- 王座戦の試合ごとの共有画像（GitHub Actions で作って預けてもらう）
CREATE TABLE IF NOT EXISTS ogimg (id INTEGER PRIMARY KEY, img BLOB NOT NULL, at TEXT NOT NULL);
-- 利用者からの報告（数字が違う・内容が不適切）。名前やメールアドレスは持たない
CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, iphash TEXT NOT NULL, client TEXT, kind TEXT NOT NULL, a TEXT, b TEXT, target TEXT, text TEXT, url TEXT, status TEXT NOT NULL DEFAULT 'new', reason TEXT, title TEXT, fk TEXT, fv TEXT, fix TEXT, rkey TEXT);
CREATE INDEX IF NOT EXISTS rep_ip ON reports(iphash, at);
-- ページを開いたブラウザ（1日1回。client は plays と同じ変換をした番号。ref は来た元のサイト名だけ）
CREATE TABLE IF NOT EXISTS visits (day TEXT NOT NULL, client TEXT NOT NULL, at TEXT NOT NULL, ref TEXT, mob INTEGER NOT NULL DEFAULT 0, fresh INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, client));
CREATE INDEX IF NOT EXISTS visits_at ON visits(at);
-- 今日の一戦の共有画像（日付ごとに1枚。GitHub Actions が毎日0時すぎに作って預ける）
CREATE TABLE IF NOT EXISTS today_og (day TEXT PRIMARY KEY, a TEXT NOT NULL, b TEXT NOT NULL, img BLOB NOT NULL, at TEXT NOT NULL);
-- 遊ばれ方の日ごとの合計（誰のものかは持たない）。サーバーが受け取った時点で足す（src/index.js の bump）
--   ev：visit 来訪（k＝new 初めて／d1 前日も／w 1週間以内／long 久しぶり、x＝入口）・ref 来た元のサイト（k＝サイト名）
--       play 対戦（k＝t 今日の一戦／m 代表戦／f 図鑑から／d ダンジョン／free）・reach その日の節目（k＝1・2・4・10試合目）
--   dev：m スマホ／d パソコン、src：来た元の種類（mugen・x・search・direct・other）
CREATE TABLE IF NOT EXISTS daily_stats (day TEXT NOT NULL, ev TEXT NOT NULL, k TEXT NOT NULL, dev TEXT NOT NULL DEFAULT '', src TEXT NOT NULL DEFAULT '', x TEXT NOT NULL DEFAULT '', n INTEGER NOT NULL, PRIMARY KEY (day, ev, k, dev, src, x));
