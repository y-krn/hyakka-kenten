-- 2026-11-02 記録の取り消し：挑戦#92（AKB48 が王者 NMB48 から王座奪取）
-- 運営者の試し打ちで、しかも「同じ組み合わせの王座戦は一度きり」のルールでは受け付けない挑戦（#86 で対戦済み）。
-- #92 と第40代（AKB48）を取り消し、第39代 NMB48 の在位を戻す。
-- 第40代への挑戦が1件でもあれば、何も変えない（状態が変わっていたら手で確かめる）。
DELETE FROM ogimg
  WHERE id = 92 AND NOT EXISTS (SELECT 1 FROM challenges WHERE reign_id = 40);
DELETE FROM challenges
  WHERE id = 92 AND reign_id = 39 AND title = 'AKB48' AND result = 'win' AND NOT EXISTS (SELECT 1 FROM challenges WHERE reign_id = 40);
DELETE FROM reigns
  WHERE id = 40 AND title = 'AKB48' AND NOT EXISTS (SELECT 1 FROM challenges WHERE reign_id = 40)
    AND NOT EXISTS (SELECT 1 FROM challenges WHERE id = 92);
UPDATE reigns SET ended_at = NULL, ended_by = NULL
  WHERE id = 39 AND ended_at IS NOT NULL AND NOT EXISTS (SELECT 1 FROM reigns WHERE id = 40);
UPDATE sqlite_sequence SET seq = 39
  WHERE name = 'reigns' AND NOT EXISTS (SELECT 1 FROM reigns WHERE id > 39);
UPDATE sqlite_sequence SET seq = (SELECT MAX(id) FROM challenges)
  WHERE name = 'challenges' AND NOT EXISTS (SELECT 1 FROM challenges WHERE id = 92);
