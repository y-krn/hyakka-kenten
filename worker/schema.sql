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
-- みんなの対戦数（自由対戦はブラウザでまとめて数えて、ときどき送ってもらう）
CREATE TABLE IF NOT EXISTS stats (k TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS plays (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  n INTEGER NOT NULL,          -- まとめて送られてきた対戦数
  at TEXT NOT NULL,
  iphash TEXT NOT NULL,
  client TEXT
);
CREATE INDEX IF NOT EXISTS plays_client ON plays(client, at);
CREATE INDEX IF NOT EXISTS plays_ip ON plays(iphash, at);
-- 王座戦の試合ごとの共有画像（GitHub Actions で作って預けてもらう）
CREATE TABLE IF NOT EXISTS ogimg (id INTEGER PRIMARY KEY, img BLOB NOT NULL, at TEXT NOT NULL);
