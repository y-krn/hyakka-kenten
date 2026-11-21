-- 都道府県の応援：県対抗の月ごとの集計（month は日本時間の YYYY-MM。w・l は県の代表の記事が勝った・負けた数、c は応援試合の数）
CREATE TABLE IF NOT EXISTS pref_month (month TEXT NOT NULL, pref TEXT NOT NULL, w INTEGER NOT NULL DEFAULT 0, l INTEGER NOT NULL DEFAULT 0, c INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (month, pref));
