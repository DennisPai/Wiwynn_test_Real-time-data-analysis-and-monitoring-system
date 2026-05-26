#!/usr/bin/env bash
# migrate_0004.sh — Migration runner for 0004_data_records_wide_unification
#
# Usage:
#   DB_HOST=localhost DB_USER=root DB_PASS=secret DB_NAME=wiwynn \
#     bash backend/scripts/migrate_0004.sh
#
# 必要環境變數：DB_HOST  DB_USER  DB_PASS  DB_NAME
# 選用環境變數：BACKUP_DIR（預設 /data/backups）
#
# Steps:
#   1. mysqldump 完整備份
#   2. gzip 壓縮
#   3. 跑 audit_pre_0004.sql（pre-migration 稽核）
#   4. alembic upgrade head
#   5. 跑 sanity_post_0004.sql（post-migration 驗證）
#   任一步驟失敗 → abort（set -e 保證）

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-/data/backups}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Colour codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Colour

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Validate required env vars
# ---------------------------------------------------------------------------
for var in DB_HOST DB_USER DB_PASS DB_NAME; do
    if [[ -z "${!var:-}" ]]; then
        log_error "環境變數 $var 未設定。中止。"
        exit 1
    fi
done

MYSQL_CMD="mysql --host=${DB_HOST} --user=${DB_USER} --password=${DB_PASS}"
MYSQLDUMP_CMD="mysqldump --host=${DB_HOST} --user=${DB_USER} --password=${DB_PASS}"

# ---------------------------------------------------------------------------
# Step 1: mysqldump 完整備份
# ---------------------------------------------------------------------------
log_info "Step 1: 建立 mysqldump 備份..."
mkdir -p "${BACKUP_DIR}"
BACKUP_SQL="${BACKUP_DIR}/pre_0004_${TIMESTAMP}.sql"

${MYSQLDUMP_CMD} \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    "${DB_NAME}" > "${BACKUP_SQL}"

log_info "  備份完成：${BACKUP_SQL}"

# ---------------------------------------------------------------------------
# Step 2: gzip 壓縮
# ---------------------------------------------------------------------------
log_info "Step 2: gzip 壓縮備份..."
gzip "${BACKUP_SQL}"
BACKUP_GZ="${BACKUP_SQL}.gz"
log_info "  壓縮完成：${BACKUP_GZ}（$(du -sh "${BACKUP_GZ}" | cut -f1)）"

# ---------------------------------------------------------------------------
# Step 3: 跑 pre-migration audit 稽核 SQL
# ---------------------------------------------------------------------------
AUDIT_SQL="${SCRIPT_DIR}/audit_pre_0004.sql"
AUDIT_LOG="${BACKUP_DIR}/audit_pre_0004_${TIMESTAMP}.log"

log_info "Step 3: 跑 pre-migration audit..."
if [[ ! -f "${AUDIT_SQL}" ]]; then
    log_error "找不到 audit SQL：${AUDIT_SQL}"
    exit 1
fi

${MYSQL_CMD} "${DB_NAME}" < "${AUDIT_SQL}" > "${AUDIT_LOG}" 2>&1
log_info "  Audit 完成，結果寫入：${AUDIT_LOG}"
log_warn "  請人工確認 audit log 無嚴重問題再繼續（特別是 Audit 1 非 whitelist category）"
cat "${AUDIT_LOG}"

# ---------------------------------------------------------------------------
# Step 4: alembic upgrade head
# ---------------------------------------------------------------------------
log_info "Step 4: 跑 alembic upgrade head..."
cd "${BACKEND_DIR}"
alembic upgrade head
log_info "  alembic upgrade 完成。"

# ---------------------------------------------------------------------------
# Step 5: 跑 post-migration sanity SQL
# ---------------------------------------------------------------------------
SANITY_SQL="${SCRIPT_DIR}/sanity_post_0004.sql"
SANITY_LOG="${BACKUP_DIR}/sanity_post_0004_${TIMESTAMP}.log"

log_info "Step 5: 跑 post-migration sanity 驗證..."
if [[ ! -f "${SANITY_SQL}" ]]; then
    log_error "找不到 sanity SQL：${SANITY_SQL}"
    exit 1
fi

${MYSQL_CMD} "${DB_NAME}" < "${SANITY_SQL}" > "${SANITY_LOG}" 2>&1
log_info "  Sanity 完成，結果寫入：${SANITY_LOG}"
cat "${SANITY_LOG}"

# Check critical sanity expectations: Sanity 2, 3, 4, 5 should all return 0
# We extract the numeric results from the log and alert if non-zero.
check_zero() {
    local label="$1"
    local value="$2"
    if [[ "${value}" != "0" ]] && [[ -n "${value}" ]]; then
        log_error "Sanity FAIL: ${label} 預期 0，實際 ${value}"
        return 1
    fi
    log_info "  Sanity OK: ${label} = 0"
}

# Parse the sanity log: results are tab-separated (label\tcount)
while IFS=$'\t' read -r label count; do
    case "${label}" in
        "null_metric_rows")
            check_zero "全 NULL metric row（Sanity 2）" "${count}" ;;
        "incomplete_anomaly_flags")
            check_zero "anomaly_flags JSON_LENGTH != 5（Sanity 3）" "${count}" ;;
        "null_ts_rows")
            check_zero "ts IS NULL（Sanity 4）" "${count}" ;;
        "invalid_source_rows")
            check_zero "source NOT IN whitelist（Sanity 5）" "${count}" ;;
    esac
done < <(grep -E "^(null_metric_rows|incomplete_anomaly_flags|null_ts_rows|invalid_source_rows)" "${SANITY_LOG}" || true)

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log_info ""
log_info "========================================"
log_info "  MIGRATION 0004 COMPLETE"
log_info "========================================"
log_info "  備份：    ${BACKUP_GZ}"
log_info "  Audit log：${AUDIT_LOG}"
log_info "  Sanity log：${SANITY_LOG}"
log_info "========================================"
