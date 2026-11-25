-- 今までの来訪（visits）と対戦数（plays）の1件ずつの記録を、日ごとの合計（daily_stats）にまとめる。1回だけ使う
--   2026-11-26（日本時間の日付）より前の日だけをまとめる。2026-11-26 の日からは、サーバーが受け取った時点で足している
--   まとめたあと、合計が元の記録と一致することを確かめてから、元の記録を消す（別の手順。承認を得てから）
--   D1 では一時的なビューを作れないので、問い合わせごとに WITH で同じものを書く
-- 来訪（初めて／前日も／1週間以内／久しぶり × 入口）
WITH v_src AS (SELECT v.day, v.client, v.ref, v.fresh, v.land, CASE
  WHEN v.ref IS NULL OR v.ref = '' THEN 'direct'
  WHEN v.ref = 'freegame-mugen.jp' OR v.ref LIKE '%.freegame-mugen.jp' THEN 'mugen'
  WHEN v.ref IN ('t.co', 'x.com', 'twitter.com') OR v.ref LIKE '%.x.com' OR v.ref LIKE '%.twitter.com' THEN 'x'
  WHEN v.ref LIKE '%google.%' OR v.ref LIKE '%bing.%' OR v.ref LIKE '%yahoo.%' OR v.ref LIKE '%duckduckgo.%' THEN 'search'
  ELSE 'other' END AS src, CASE WHEN v.mob = 1 THEN 'm' ELSE 'd' END AS dev,
  (SELECT MAX(v2.day) FROM visits v2 WHERE v2.client = v.client AND v2.day < v.day) AS pd
  FROM visits v WHERE v.day < '2026-11-26')
INSERT OR REPLACE INTO daily_stats (day, ev, k, dev, src, x, n)
SELECT day, 'visit', CASE WHEN fresh = 1 THEN 'new' WHEN pd IS NULL THEN 'long' WHEN julianday(day) - julianday(pd) = 1 THEN 'd1' WHEN julianday(day) - julianday(pd) <= 7 THEN 'w' ELSE 'long' END AS k,
  dev, src, COALESCE(land, 'other') AS x, COUNT(*) FROM v_src GROUP BY day, k, dev, src, x;
-- 来た元のサイト
WITH v_src AS (SELECT v.day, v.client, v.ref, v.fresh, v.land, CASE
  WHEN v.ref IS NULL OR v.ref = '' THEN 'direct'
  WHEN v.ref = 'freegame-mugen.jp' OR v.ref LIKE '%.freegame-mugen.jp' THEN 'mugen'
  WHEN v.ref IN ('t.co', 'x.com', 'twitter.com') OR v.ref LIKE '%.x.com' OR v.ref LIKE '%.twitter.com' THEN 'x'
  WHEN v.ref LIKE '%google.%' OR v.ref LIKE '%bing.%' OR v.ref LIKE '%yahoo.%' OR v.ref LIKE '%duckduckgo.%' THEN 'search'
  ELSE 'other' END AS src, CASE WHEN v.mob = 1 THEN 'm' ELSE 'd' END AS dev,
  (SELECT MAX(v2.day) FROM visits v2 WHERE v2.client = v.client AND v2.day < v.day) AS pd
  FROM visits v WHERE v.day < '2026-11-26')
INSERT OR REPLACE INTO daily_stats (day, ev, k, dev, src, x, n)
SELECT day, 'ref', ref, dev, src, '', COUNT(*) FROM v_src WHERE ref IS NOT NULL AND ref <> '' GROUP BY day, ref, dev, src;
-- 対戦数（日本時間の日付。端末と来た元は、同じブラウザのその日の来訪から。わからなければ空）
WITH v_src AS (SELECT v.day, v.client, v.ref, v.fresh, v.land, CASE
  WHEN v.ref IS NULL OR v.ref = '' THEN 'direct'
  WHEN v.ref = 'freegame-mugen.jp' OR v.ref LIKE '%.freegame-mugen.jp' THEN 'mugen'
  WHEN v.ref IN ('t.co', 'x.com', 'twitter.com') OR v.ref LIKE '%.x.com' OR v.ref LIKE '%.twitter.com' THEN 'x'
  WHEN v.ref LIKE '%google.%' OR v.ref LIKE '%bing.%' OR v.ref LIKE '%yahoo.%' OR v.ref LIKE '%duckduckgo.%' THEN 'search'
  ELSE 'other' END AS src, CASE WHEN v.mob = 1 THEN 'm' ELSE 'd' END AS dev,
  (SELECT MAX(v2.day) FROM visits v2 WHERE v2.client = v.client AND v2.day < v.day) AS pd
  FROM visits v WHERE v.day < '2026-11-26'), p_day AS (SELECT p.n, p.kt, p.km, p.kf, p.kd, date(datetime(p.at, '+9 hours')) AS day, COALESCE(p.client, 'ip:' || p.iphash) AS who,
  COALESCE((SELECT dev FROM v_src v WHERE v.client = p.client AND v.day = date(datetime(p.at, '+9 hours'))), '') AS dev,
  COALESCE((SELECT src FROM v_src v WHERE v.client = p.client AND v.day = date(datetime(p.at, '+9 hours'))), '') AS src
  FROM plays p WHERE date(datetime(p.at, '+9 hours')) < '2026-11-26')
INSERT OR REPLACE INTO daily_stats (day, ev, k, dev, src, x, n)
SELECT day, 'play', k, dev, src, '', SUM(c) FROM (
  SELECT day, 't' AS k, dev, src, COALESCE(kt, 0) AS c FROM p_day UNION ALL
  SELECT day, 'm', dev, src, COALESCE(km, 0) FROM p_day UNION ALL
  SELECT day, 'f', dev, src, COALESCE(kf, 0) FROM p_day UNION ALL
  SELECT day, 'd', dev, src, COALESCE(kd, 0) FROM p_day UNION ALL
  SELECT day, 'free', dev, src, n - COALESCE(kt, 0) - COALESCE(km, 0) - COALESCE(kf, 0) - COALESCE(kd, 0) FROM p_day)
  GROUP BY day, k, dev, src HAVING SUM(c) > 0;
-- その日の節目（1・2・4・10試合目に届いたブラウザの数）
WITH v_src AS (SELECT v.day, v.client, v.ref, v.fresh, v.land, CASE
  WHEN v.ref IS NULL OR v.ref = '' THEN 'direct'
  WHEN v.ref = 'freegame-mugen.jp' OR v.ref LIKE '%.freegame-mugen.jp' THEN 'mugen'
  WHEN v.ref IN ('t.co', 'x.com', 'twitter.com') OR v.ref LIKE '%.x.com' OR v.ref LIKE '%.twitter.com' THEN 'x'
  WHEN v.ref LIKE '%google.%' OR v.ref LIKE '%bing.%' OR v.ref LIKE '%yahoo.%' OR v.ref LIKE '%duckduckgo.%' THEN 'search'
  ELSE 'other' END AS src, CASE WHEN v.mob = 1 THEN 'm' ELSE 'd' END AS dev,
  (SELECT MAX(v2.day) FROM visits v2 WHERE v2.client = v.client AND v2.day < v.day) AS pd
  FROM visits v WHERE v.day < '2026-11-26'), p_day AS (SELECT p.n, p.kt, p.km, p.kf, p.kd, date(datetime(p.at, '+9 hours')) AS day, COALESCE(p.client, 'ip:' || p.iphash) AS who,
  COALESCE((SELECT dev FROM v_src v WHERE v.client = p.client AND v.day = date(datetime(p.at, '+9 hours'))), '') AS dev,
  COALESCE((SELECT src FROM v_src v WHERE v.client = p.client AND v.day = date(datetime(p.at, '+9 hours'))), '') AS src
  FROM plays p WHERE date(datetime(p.at, '+9 hours')) < '2026-11-26')
INSERT OR REPLACE INTO daily_stats (day, ev, k, dev, src, x, n)
SELECT day, 'reach', CAST(t.v AS TEXT), dev, src, '', COUNT(*) FROM
  (SELECT day, who, MAX(dev) AS dev, MAX(src) AS src, SUM(n) AS s FROM p_day GROUP BY day, who) w
  JOIN (SELECT 1 AS v UNION ALL SELECT 2 UNION ALL SELECT 4 UNION ALL SELECT 10) t ON w.s >= t.v
  GROUP BY day, t.v, dev, src;
