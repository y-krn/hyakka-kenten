-- みんなの対戦数の内訳に、百科ダンジョンの列を足す
ALTER TABLE plays ADD COLUMN kd INTEGER NOT NULL DEFAULT 0;
