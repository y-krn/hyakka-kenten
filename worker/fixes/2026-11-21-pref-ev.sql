-- 都道府県の応援：効果を測る（day は日本時間の YYYY-MM-DD。k = in：?pref=県名 のURLから来た、sh：応援試合の結果を共有した、pb：応援試合）
CREATE TABLE IF NOT EXISTS pref_ev (day TEXT NOT NULL, pref TEXT NOT NULL, k TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, pref, k));
