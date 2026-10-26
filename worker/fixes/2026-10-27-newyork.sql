-- 2026-10-27 記録の修正：挑戦#56（ニューヨーク 対 王者 神奈川県）
-- 当時は比べ合いの計算が左右の並び順に依存しており、サーバーが誤ってニューヨークの勝ちと判定していた。
-- 正しくは神奈川県の防衛。第30代（ニューヨーク）を取り消し、第29代 神奈川県の在位を戻す。
-- 第30代への挑戦が1件でもあれば、何も変えない（状態が変わっていたら手で確かめる）。
UPDATE challenges SET result = 'lose'
  WHERE id = 56 AND result = 'win' AND NOT EXISTS (SELECT 1 FROM challenges WHERE reign_id = 30);
DELETE FROM reigns
  WHERE id = 30 AND title = 'ニューヨーク' AND NOT EXISTS (SELECT 1 FROM challenges WHERE reign_id = 30)
    AND (SELECT result FROM challenges WHERE id = 56) = 'lose';
UPDATE reigns SET ended_at = NULL, ended_by = NULL, defenses = defenses + 1
  WHERE id = 29 AND ended_at IS NOT NULL AND NOT EXISTS (SELECT 1 FROM reigns WHERE id = 30);
UPDATE sqlite_sequence SET seq = 29
  WHERE name = 'reigns' AND NOT EXISTS (SELECT 1 FROM reigns WHERE id > 29);
