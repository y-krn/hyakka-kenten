-- 今日の一戦の共有画像（日付ごとに1枚。GitHub Actions が毎日0時すぎに作って預ける）
CREATE TABLE IF NOT EXISTS today_og (day TEXT PRIMARY KEY, a TEXT NOT NULL, b TEXT NOT NULL, img BLOB NOT NULL, at TEXT NOT NULL);
