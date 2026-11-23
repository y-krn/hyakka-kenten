-- 記事名で過去の挑戦を探すための索引（歴代王者の一覧・同じ組み合わせの対戦が、毎回すべての記録を読んでいたため）。データは変えない
CREATE INDEX IF NOT EXISTS ch_title ON challenges(title, reign_id);
