# Backend Summary — Redesign v2 (Phase B + C)

## 1. 改了哪些檔案

### 新增檔案
| 檔案 | 說明 |
|---|---|
| `backend/alembic/versions/0003_realtime_wide_format.py` | B1-3: Alembic migration，純 ORM op.create_table（禁 raw SQL） |
| `backend/app/models/realtime_metric_wide.py` | B1-1: RealtimeMetricWide SQLAlchemy model（wide format） |
| `backend/app/schemas/realtime.py` | B2-1/B2-2: RealtimeSnapshot / RealtimeSnapshotResponse / RealtimeHistoryResponse |
| `backend/app/api/v1/realtime.py` | C1: GET /api/v1/realtime/history router |
| `backend/tests/test_realtime_history.py` | C1-4: pytest（7 tests） |
| `backend/tests/test_password_update.py` | C2-4: pytest（8 tests） |
| `backend/tests/test_analytics_timerange_regression.py` | C3-4: pytest 防回歸（5 tests） |
| `backend/tests/test_admin_realtime_history_wide.py` | C4-4: pytest（5 tests） |
| `backend/tests/test_analytics_unified.py` | C5-4/C6-3: pytest（8 tests） |

### 修改檔案
| 檔案 | 修改內容 |
|---|---|
| `backend/app/models/__init__.py` | B1-2: 匯出 RealtimeMetricWide |
| `backend/app/schemas/admin.py` | B2-3: 加 legacy comment，保持 RealtimeMetricResponse（backward compat） |
| `backend/app/schemas/analytics.py` | C5-1/C6-2: 加 UnifiedSummaryResponse / RealtimeCategoriesResponse |
| `backend/app/schemas/user.py` | C2-1: 加 PasswordUpdateRequest |
| `backend/app/services/realtime_service.py` | B3 全部: random walk + wide snapshot + 異常注入 + DB 初始狀態 |
| `backend/app/services/batch_writer.py` | B4: 寫雙 table（wide + long） |
| `backend/app/services/analytics_service.py` | C5-2/C6-1: get_unified_summary / get_realtime_categories |
| `backend/app/api/v1/__init__.py` | C1-3: include realtime_router |
| `backend/app/api/v1/analytics.py` | C3/C5/C6: _to_naive_utc + unified-summary + realtime-categories |
| `backend/app/api/v1/admin.py` | C4: realtime-history 改 wide format + 加 realtime_metrics_wide 到 db-status |
| `backend/app/api/v1/users.py` | C2-2/C2-3: update_password endpoint + audit log |
| `backend/tests/test_admin.py` | 更新為 wide format（seed_realtime_wide fixture + 移除 category 測試） |

---

## 2. 新增 endpoint / table / column / migration

### Migration 0003
- `realtime_metrics_wide` table: id (BigInt PK), ts (DateTime tz=True), temperature/humidity/pressure/voltage/cpu_usage (Numeric 18,4 nullable), anomaly_flags (JSON), source (String 50)
- Index: `ix_realtime_metrics_wide_ts_desc` on `ts`
- upgrade / downgrade 兩方向都實作

### 新 endpoints
| Method | Path | Permission |
|---|---|---|
| GET | `/api/v1/realtime/history` | AnyRole |
| PATCH | `/api/v1/users/{user_id}/password` | admin（改任意人）/ self（user/viewer） |
| GET | `/api/v1/analytics/unified-summary` | AnyRole |
| GET | `/api/v1/analytics/realtime-categories` | AnyRole |

### 改動 endpoints
| Method | Path | 改動 |
|---|---|---|
| GET | `/api/v1/analytics/timerange` | 加 tz-naive UTC 轉換防衛 |
| GET | `/api/v1/admin/realtime-history` | 改 wide format，移除 category 參數 |

---

## 3. API Contract 細節（給 frontend-engineer 的單一真理）

### GET /api/v1/realtime/history
```
Query: seconds: int [1, 3600] default=60
Headers: Authorization: Bearer <JWT>
Response 200:
{
  "snapshots": [
    {
      "schema_version": "v2",
      "ts": "2026-05-26T10:00:00+00:00",
      "temperature": 25.3,
      "humidity": 60.1,
      "pressure": 1013.2,
      "voltage": 12.0,
      "cpu_usage": 42.5,
      "anomaly_flags": {"temperature": false, ...},
      "source": "simulator"
    }
  ],
  "count": 60
}
Errors: 401 (no token), 422 (seconds out of range)
```

### PATCH /api/v1/users/{user_id}/password
```
Body: { "new_password": "...", "old_password": "..." }
- new_password: min_length=8 (422 if shorter)
- old_password: required when changing own password, not required for admin changing others
Response 200: { "ok": true, "updated_at": "..." }
Errors: 400 (missing/wrong old_password), 401 (no token), 403 (non-admin changing others), 404 (user not found), 422 (password too short)
```

### GET /api/v1/admin/realtime-history
```
Query: page, size, date_from, date_to (category 參數已移除)
Response 200: PaginatedResponse 每筆 item 為 RealtimeSnapshotResponse (wide format):
{
  "schema_version": "v2",
  "ts": "...",
  "temperature": 25.3, "humidity": 60.1, "pressure": 1013.2, "voltage": 12.0, "cpu_usage": 42.5,
  "anomaly_flags": {...},
  "source": "simulator"
}
注意：舊 response 的 value / category / is_anomaly 欄位已移除
Errors: 403 (non-admin)
```

### GET /api/v1/analytics/unified-summary
```
Query: date_from (optional), date_to (optional), source: "both"|"realtime"|"records" (default="both")
Response 200:
{
  "source": "both",
  "realtime": {
    "total": 86400, "anomaly_count": 234,
    "metrics": {"temperature": {"avg": 25.3, "min": 18.0, "max": 35.1, "anomaly_count": 50}, ...}
  },
  "records": { "total": 200, "anomaly_count": 5, "categories": ["temperature", ...] },
  "combined": { "total": 86600, "anomaly_count": 239 }
}
```

### GET /api/v1/analytics/realtime-categories
```
Query: date_from (optional), date_to (optional)
Response 200:
{
  "metrics": [
    {"metric": "temperature", "count": 86400, "avg": 25.3, "anomaly_count": 50},
    {"metric": "humidity", ...},
    {"metric": "pressure", ...},
    {"metric": "voltage", ...},
    {"metric": "cpu_usage", ...}
  ]
}
```

### WS /ws/realtime
payload schema v2:
```json
{
  "schema_version": "v2",
  "ts": "2026-05-26T10:00:00+00:00",
  "temperature": 25.3,
  "humidity": 60.1,
  "pressure": 1013.2,
  "voltage": 12.0,
  "cpu_usage": 42.5,
  "anomaly_flags": {"temperature": false, "humidity": false, "pressure": false, "voltage": false, "cpu_usage": false}
}
```

---

## 4. Q7 Root Cause

**Root cause C（FE 渲染 bug）**。

curl 驗證回傳：
- date_from=2026-05-20T00:00:00Z ~ date_to=2026-05-26T23:59:59Z
- buckets 有 6 筆資料（count 24~27 not empty）

結論：backend 運作正確，問題在前端渲染（Q7 待 frontend-engineer 修）。

防衛措施：在 `analytics.py` 的 `analytics_timerange` endpoint 加了 `_to_naive_utc()` 轉換，確保 tz-aware datetime input 不造成 root cause B（萬一 DB column 未來改 naive）。

---

## 5. 紀律驗證

### 禁 raw SQL
```bash
grep -rn 'text("SELECT...' backend/app/
# 只有 main.py:135 的 /health SELECT 1（白名單例外）
```

### 5/21 Rule F - 所有 helper fn 已整合主流程
- `random_walk_step` → called in `_make_snapshot`
- `_make_snapshot` → called in `_tick`
- `_load_initial_state_from_db` → called in `start`
- `_to_naive_utc` → called in `analytics_timerange`
- `get_unified_summary` / `get_realtime_categories` → called in analytics.py endpoints
- `_get_realtime_summary` / `_get_records_summary` / `_count_realtime_anomaly` → called in service

---

## 6. 測試結果

```
135 passed, 2 warnings (deprecation) in ~70s
Exit code: 0
```

### 新增測試檔案 (37 new tests)
- `test_realtime_history.py`: 7 tests
- `test_password_update.py`: 8 tests
- `test_analytics_timerange_regression.py`: 5 tests
- `test_admin_realtime_history_wide.py`: 5 tests
- `test_analytics_unified.py`: 8 tests (C5+C6 合一檔)

其餘 98 個原有 tests 全部維持 pass。

---

## 7. Follow-up / Known Limitations

1. **B1-4/B1-5（alembic upgrade/downgrade 本地驗證）**：SQLite in-memory test 已驗（conftest 走 Base.metadata.create_all），但未在實際 MariaDB 跑 alembic upgrade head。Zeabur 部署時 main.py lifespan 會自動跑。

2. **AC-01 (BE 30s 不開 FE 驗 wide rows)**：本地沒有運行的 DB server 無法跑完整 integration test，需在 Zeabur 環境驗。

3. **Q7 FE rendering fix**：backend 已確認回傳正確，frontend-engineer 負責修渲染邏輯。

4. **analytics/realtime-categories anomaly_count 計算**：目前走 Python side 計算（avoid SQLite/MariaDB JSON path dialect 差異），大量資料時可能效能較低。v3 可考慮改 JSON path 或 denormalized column。

5. **Phase D（frontend）**：本次 backend-engineer 不觸碰前端，由 frontend-engineer 依此 API contract 實作。
