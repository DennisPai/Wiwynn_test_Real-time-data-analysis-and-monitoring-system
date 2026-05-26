-- audit_pre_0004.sql
-- Pre-migration audit for 0004_data_records_wide_unification
-- 跑時機：alembic upgrade head 之前（data_records 仍是 long format）
--
-- 3 條稽核查詢，結果輸出供人工審查：
--   Audit 1: 非 5-metric whitelist 的 category（不能被映射到 metric column）
--   Audit 2: value=NULL 的 long row（聚合時此 metric 視為 NULL）
--   Audit 3: 同 minute + owner_id + category 重複 row（聚合時取最後一筆）

-- ============================================================
-- Audit 1: 偵測非 5-metric whitelist 的 category
-- ============================================================
-- 預期：理想狀況下結果為空（0 row）
-- 若有非 whitelist category，這些 row 的 value 不會被填進任何 metric column，
-- 聚合後 metric 全 NULL → Step 4 被刪除。建議人工確認是否接受資料遺失。
SELECT
    'Audit 1: non-whitelist category' AS audit_label,
    category,
    COUNT(*) AS row_count
FROM data_records
WHERE category NOT IN ('temperature', 'humidity', 'pressure', 'voltage', 'cpu_usage')
GROUP BY category
ORDER BY row_count DESC;

-- ============================================================
-- Audit 2: 偵測 value=NULL 的 long row
-- ============================================================
-- 預期：理想狀況下為 0
-- NULL value 的 row 在聚合後該 metric 欄位為 NULL（如該 minute+owner 組只有此 row 則
-- 該 wide row 的此 metric 為 NULL）
SELECT
    'Audit 2: null value rows' AS audit_label,
    COUNT(*) AS null_value_count
FROM data_records
WHERE value IS NULL;

-- ============================================================
-- Audit 3: 偵測同 minute + owner_id + category 重複 row
-- ============================================================
-- 預期：理想狀況下為 0（每 minute+owner+category 唯一）
-- 若有重複，聚合時 MAX(value) 取最大值（非最後一筆）
SELECT
    'Audit 3: duplicate minute+owner+category' AS audit_label,
    DATE_FORMAT(recorded_at, '%Y-%m-%d %H:%i:00') AS minute_bucket,
    owner_id,
    category,
    COUNT(*) AS dup_count
FROM data_records
GROUP BY
    DATE_FORMAT(recorded_at, '%Y-%m-%d %H:%i:00'),
    owner_id,
    category
HAVING COUNT(*) > 1
ORDER BY dup_count DESC, minute_bucket ASC;
