-- 既存のデータベースに、後から足した列と索引を加える（すでにあれば失敗するが、デプロイは止めない）
ALTER TABLE challenges ADD COLUMN client TEXT;
