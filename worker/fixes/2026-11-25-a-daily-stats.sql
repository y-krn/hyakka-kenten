-- 遊ばれ方の日ごとの合計の表を足す（誰のものかは持たない）。今ある記録は変えない
CREATE TABLE IF NOT EXISTS daily_stats (day TEXT NOT NULL, ev TEXT NOT NULL, k TEXT NOT NULL, dev TEXT NOT NULL DEFAULT '', src TEXT NOT NULL DEFAULT '', x TEXT NOT NULL DEFAULT '', n INTEGER NOT NULL, PRIMARY KEY (day, ev, k, dev, src, x));
