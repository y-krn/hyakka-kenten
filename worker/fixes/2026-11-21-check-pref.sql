-- 確かめるだけ（読むだけで、何も変えない）：都道府県の応援の効果の記録と、県対抗の集計
SELECT day, pref, k, n FROM pref_ev ORDER BY day, pref, k;
SELECT month, pref, w, l, c FROM pref_month ORDER BY month, pref;
