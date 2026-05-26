-- sanity_post_0004.sql
-- Post-migration sanity verification for 0004_data_records_wide_unification
-- 跑時機：alembic upgrade head 之後（data_records 已是 wide format）
--
-- 5 條驗證查詢，每條均附預期值：
--   Sanity 1: source 分布（informational）
--   Sanity 2: 全 NULL metric row 數量（預期 0）
--   Sanity 3: anomaly_flags JSON_LENGTH != 5 的 row 數量（預期 0）
--   Sanity 4: ts IS NULL 的 row 數量（預期 0）
--   Sanity 5: source NOT IN whitelist 的 row 數量（預期 0）

-- ============================================================
-- Sanity 1: source 分布（informational，確認 user / simulator 分流正確）
-- ============================================================
SELECT
    'Sanity 1: source distribution' AS sanity_label,
    source,
    COUNT(*) AS row_count
FROM data_records
GROUP BY source
ORDER BY source;

-- ============================================================
-- Sanity 2: 全 NULL metric row（預期 0）
-- ============================================================
-- 若 > 0：表示有 wide row 沒有任何 metric 值（違反 CHECK constraint，不應存在）
SELECT
    'null_metric_rows' AS sanity_label,
    COUNT(*) AS count
FROM data_records
WHERE temperature IS NULL
  AND humidity    IS NULL
  AND pressure    IS NULL
  AND voltage     IS NULL
  AND cpu_usage   IS NULL;
-- EXPECTED: 0

-- ============================================================
-- Sanity 3: anomaly_flags JSON_LENGTH != 5（預期 0）
-- ============================================================
-- 若 > 0：表示有 anomaly_flags 不是完整 5 key，需人工修復
SELECT
    'incomplete_anomaly_flags' AS sanity_label,
    COUNT(*) AS count
FROM data_records
WHERE JSON_LENGTH(anomaly_flags) != 5;
-- EXPECTED: 0

-- ============================================================
-- Sanity 4: ts IS NULL（預期 0）
-- ============================================================
-- 若 > 0：表示有 wide row 沒有時間戳（NOT NULL 約束違反，不應存在）
SELECT
    'null_ts_rows' AS sanity_label,
    COUNT(*) AS count
FROM data_records
WHERE ts IS NULL;
-- EXPECTED: 0

-- ============================================================
-- Sanity 5: source NOT IN whitelist（預期 0）
-- ============================================================
-- 若 > 0：表示有 source 值不在 ('user', 'simulator') 白名單內
SELECT
    'invalid_source_rows' AS sanity_label,
    COUNT(*) AS count
FROM data_records
WHERE source NOT IN ('user', 'simulator');
-- EXPECTED: 0

-- ============================================================
-- Extra: owner_id FK 完整性（預期 0）
-- ============================================================
-- 若 > 0：表示有 data_records row 的 owner_id 在 users 表中找不到對應
SELECT
    'orphan_owner_id_rows' AS sanity_label,
    COUNT(*) AS count
FROM data_records dr
LEFT JOIN users u ON dr.owner_id = u.id
WHERE u.id IS NULL;
-- EXPECTED: 0
