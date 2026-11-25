-- 日ごとの合計に、今までの記録をまとめた時刻（11:49:50 UTC）から、新しい版が動き出した時刻（11:51:44 UTC）までに古い表へ入った来訪・対戦を足す（1回だけ）
WITH v_src AS (SELECT v.day, v.fresh, v.land, v.ref, CASE
  WHEN v.ref IS NULL OR v.ref = '' THEN 'direct'
  WHEN v.ref = 'freegame-mugen.jp' OR v.ref LIKE '%.freegame-mugen.jp' THEN 'mugen'
  WHEN v.ref IN ('t.co', 'x.com', 'twitter.com') OR v.ref LIKE '%.x.com' OR v.ref LIKE '%.twitter.com' THEN 'x'
  WHEN v.ref LIKE '%google.%' OR v.ref LIKE '%bing.%' OR v.ref LIKE '%yahoo.%' OR v.ref LIKE '%duckduckgo.%' THEN 'search'
  ELSE 'other' END AS src, CASE WHEN v.mob = 1 THEN 'm' ELSE 'd' END AS dev,
  (SELECT MAX(v2.day) FROM visits v2 WHERE v2.client = v.client AND v2.day < v.day) AS pd
  FROM visits v WHERE v.at >= '2026-11-25T11:49:50Z' AND v.at < '2026-11-25T11:51:44Z')
INSERT INTO daily_stats (day, ev, k, dev, src, x, n)
SELECT day, 'visit', CASE WHEN fresh = 1 THEN 'new' WHEN pd IS NULL THEN 'long' WHEN julianday(day) - julianday(pd) = 1 THEN 'd1' WHEN julianday(day) - julianday(pd) <= 7 THEN 'w' ELSE 'long' END AS k,
  dev, src, COALESCE(land, 'other') AS x, COUNT(*) FROM v_src GROUP BY day, k, dev, src, x
  ON CONFLICT(day, ev, k, dev, src, x) DO UPDATE SET n = n + excluded.n;
INSERT INTO daily_stats (day, ev, k, dev, src, x, n)
SELECT date(datetime(at, '+9 hours')) AS day, 'play', 'free', '', '', '', SUM(n - COALESCE(kt, 0) - COALESCE(km, 0) - COALESCE(kf, 0) - COALESCE(kd, 0)) AS c
  FROM plays WHERE at >= '2026-11-25T11:49:50Z' AND at < '2026-11-25T11:51:44Z' GROUP BY day HAVING c > 0
  ON CONFLICT(day, ev, k, dev, src, x) DO UPDATE SET n = n + excluded.n;
INSERT INTO daily_stats (day, ev, k, dev, src, x, n)
SELECT date(datetime(at, '+9 hours')) AS day, 'play', 't', '', '', '', SUM(COALESCE(kt, 0)) AS c
  FROM plays WHERE at >= '2026-11-25T11:49:50Z' AND at < '2026-11-25T11:51:44Z' GROUP BY day HAVING c > 0
  ON CONFLICT(day, ev, k, dev, src, x) DO UPDATE SET n = n + excluded.n;
