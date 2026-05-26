# Tasks — Redesign v2 實作清單

> 依 phase 分組，每 task 是可獨立 commit 的最小變動。
> 每 task 後括號標 `[Q<N>]` 對應懷特 12 點。

---

## Phase B：Backend Schema + 採集解耦 + Wide Snapshot

### B1. Wide table model + migration
- [ ] B1-1：新增 `backend/app/models/realtime_metric_wide.py` model [Q5,Q10]
- [ ] B1-2：在 `backend/app/models/__init__.py` 匯出 `RealtimeMetricWide`
- [ ] B1-3：新增 `backend/alembic/versions/0003_realtime_wide_format.py`（純 ORM，禁 raw SQL）
- [ ] B1-4：本地 `alembic upgrade head` 驗證（SQLite + MariaDB）
- [ ] B1-5：本地 `alembic downgrade -1` 驗證

### B2. Schema / Pydantic
- [ ] B2-1：新增 `backend/app/schemas/realtime.py` 含 `RealtimeSnapshot`（含 schema_version="v2"）
- [ ] B2-2：加 `RealtimeSnapshotResponse` + `RealtimeHistoryResponse`
- [ ] B2-3：修改 `backend/app/schemas/admin.py` 的 `RealtimeMetricResponse` 為 wide schema

### B3. Simulator 改 random walk + wide snapshot
- [ ] B3-1：在 `realtime_service.py` 寫 `_METRIC_PROFILES` 5 metric 的 baseline/sigma/min/max [Q5]
- [ ] B3-2：純函式 `random_walk_step(prev, sigma, low, high, rng)`
- [ ] B3-3：`RealtimeSimulator.__init__` 加 `_state: dict[str, float]`
- [ ] B3-4：改 `_make_tick` → `_make_snapshot` 回 wide snapshot [Q2,Q5]
- [ ] B3-5：改 `_tick` broadcast snapshot.model_dump_json() + enqueue
- [ ] B3-6：startup 讀 wide table 最後一筆作初始 `_state`
- [ ] B3-7：加 `ANOMALY_INJECTION_PERIOD` env var 邏輯
- [ ] B3-8：移除舊 `_CATEGORIES`

### B4. batch_writer 寫雙 table
- [ ] B4-1：改 `batch_writer.py` `_flush` drain `RealtimeSnapshot`
- [ ] B4-2：每 snapshot 建 `RealtimeMetricWide` + 5 個 `RealtimeMetric` long
- [ ] B4-3：`session.add_all(wide_rows + long_rows)` + commit
- [ ] B4-4：logger 紀錄筆數
- [ ] B4-5：測試：BE 30s 不開 FE，curl 驗 ≥ 30 筆 wide + 150 筆 long [AC-01]

---

## Phase C：Backend API Endpoints

### C1. 新增 `GET /api/v1/realtime/history`
- [ ] C1-1：新增 `api/v1/realtime.py` router
- [ ] C1-2：implement `realtime_history(seconds: int = Query(60, ge=1, le=3600))` [Q2,§6.1]
- [ ] C1-3：`api/v1/__init__.py` include router
- [ ] C1-4：pytest `tests/api/test_realtime_history.py`

### C2. 新增 `PATCH /users/{id}/password`
- [ ] C2-1：`schemas/user.py` 加 `PasswordUpdateRequest` [Q12]
- [ ] C2-2：`api/v1/users.py` 加 `update_password` endpoint [§6.2]
- [ ] C2-3：audit log entry `action="update_password"`
- [ ] C2-4：pytest `tests/api/test_password_update.py`

### C3. 修 `GET /analytics/timerange`（Q7 root cause）
- [ ] C3-1：**先 curl 驗 root cause** [Q7]
- [ ] C3-2：若 (B) tz mismatch → endpoint 轉 naive UTC 後傳 service
- [ ] C3-3：或 `data_records.recorded_at` 改 tz-aware + migration 0004
- [ ] C3-4：integration test `tests/api/test_analytics_timerange_regression.py`
- [ ] C3-5：本地 curl 驗 fix 生效

### C4. 改 `GET /admin/realtime-history` 為 wide
- [ ] C4-1：在 `admin.py:126` 改 query model 為 `RealtimeMetricWide`
- [ ] C4-2：移除 `category` query param
- [ ] C4-3：Response model 改 `PaginatedResponse[RealtimeSnapshotResponse]`
- [ ] C4-4：pytest `tests/api/test_admin_realtime_history_wide.py`

### C5. 新增 `GET /analytics/unified-summary`
- [ ] C5-1：`schemas/analytics.py` 加 `UnifiedSummaryResponse` [Q8]
- [ ] C5-2：`services/analytics_service.py` 加 `get_unified_summary`
- [ ] C5-3：`api/v1/analytics.py` 加 endpoint [§6.5]
- [ ] C5-4：pytest

### C6. 新增 `GET /analytics/realtime-categories`
- [ ] C6-1：service 加 `get_realtime_categories` [Q11,§6.6]
- [ ] C6-2：endpoint + schema
- [ ] C6-3：pytest

---

## Phase D：Frontend 全頁重寫

### D1. WS Client 改 wide payload parser
- [ ] D1-1：`ws_client.py` `stream_ticks` 加 schema_version 檢查 [§3.2]
- [ ] D1-2：buffer 元素改 wide snapshot dict
- [ ] D1-3：本地測試

### D2. Home + Dashboard 中文化 + 去 emoji
- [ ] D2-1：`Home.py` `set_page_config(page_icon=None)` [Q3]
- [ ] D2-2：rename `pages/1_📊_Dashboard.py` → `pages/1_儀表板.py` [Q6]
- [ ] D2-3：改 set_page_config + title 中文化
- [ ] D2-4：加 system status header [§4.1]
- [ ] D2-5：metric cards 改打 `/analytics/unified-summary` [Q8]
- [ ] D2-6：最近 10 筆改 tabs（即時/錄入）切換
- [ ] D2-7：移除所有 emoji unicode
- [ ] D2-8：加「帳號設定」expander（user/viewer 改自己密碼）

### D3. 資料管理 inline edit（Q9）
- [ ] D3-1：rename `pages/2_📁_Data.py` → `pages/2_資料管理.py` [Q6]
- [ ] D3-2：改 set_page_config + title 中文化 [Q3,Q6]
- [ ] D3-3：移除「逐筆操作」expander 全段 [Q9]
- [ ] D3-4：移除「新增資料」彈窗，改 `st.data_editor`
- [ ] D3-5：implement `st.data_editor` with column_config [§4.2]
- [ ] D3-6：implement diff 提交 + 403 toast
- [ ] D3-7：保留 CSV/JSON 匯入，去 emoji

### D4. 分析報表（Q6, Q7, Q8）
- [ ] D4-1：rename `pages/3_📈_Analytics.py` → `pages/3_分析報表.py` [Q6]
- [ ] D4-2：set_page_config + title 中文化 [Q3,Q6]
- [ ] D4-3：先驗 Q7 fix 有效（搭 BE C3）[Q7]
- [ ] D4-4：metric cards 改打 unified-summary [Q8]
- [ ] D4-5：時間趨勢圖加 source toggle
- [ ] D4-6：類別分佈加 source toggle
- [ ] D4-7：移除所有 emoji

### D5. 即時監控（Q1,Q2,Q4,Q5 核心）
- [ ] D5-1：rename `pages/4_🔴_Realtime.py` → `pages/4_即時監控.py` [Q6]
- [ ] D5-2：set_page_config + title 中文化 [Q3]
- [ ] D5-3：頁面進入時打 `/realtime/history?seconds=60` 預載 buffer [Q2]
- [ ] D5-4：寫 `metric_zh` mapping + 顏色
- [ ] D5-5：system status header（連線狀態 ●/○ + last update + active alerts）[§4.4]
- [ ] D5-6：告警卡顯示最近 5 筆 + Δ 數值 [Q4]
- [ ] D5-7：折線圖改 5 條線 + 異常點 circle-open red marker [Q5]
- [ ] D5-8：表格擴 60 列 [Q4]
- [ ] D5-9：Pandas Styler 套淡粉紅 row + 紅字 cell [Q4]
- [ ] D5-10：移除類別 selectbox，改「顯示哪些線」multiselect
- [ ] D5-11：移除所有 emoji

### D6. 系統管理（Q11, Q12）
- [ ] D6-1：rename `pages/5_⚙️_Admin.py` → `pages/5_系統管理.py` [Q6]
- [ ] D6-2：set_page_config + title 中文化 [Q3]
- [ ] D6-3：5 個 tab label 全去 emoji [Q3]
- [ ] D6-4：Tab 1 加「角色權限說明」markdown table [Q12]
- [ ] D6-5：Tab 1 加「改密碼」表單 [Q12]
- [ ] D6-6：Tab 4 改打 wide `/admin/realtime-history` [Q11]
- [ ] D6-7：Tab 4 折線圖 5 條線 [Q11]
- [ ] D6-8：Tab 4 移除類別 selectbox
- [ ] D6-9：Tab 5 系統設定去 emoji

---

## Phase E：Testing + 部署 + 收尾

### E1. Backend 整體測試
- [ ] E1-1：`cd backend && pytest -q` 全綠
- [ ] E1-2：覆蓋率不低於 redesign 前
- [ ] E1-3：integration test：BE 啟動 30s 不開 FE，curl 驗 wide rows ≥ 30 [AC-01]
- [ ] E1-4：integration test：curl `/realtime/history?seconds=60` 回 ≤ 60 筆 [AC-03]
- [ ] E1-5：integration test：WS 連 5 tick 含 schema_version=v2 [AC-02]

### E2. Frontend 全頁 grep 驗證
- [ ] E2-1：`rg emoji_unicode_pattern` 結果 0 matches（除 whitelist）[AC-04, Q3]
- [ ] E2-2：grep `page_title=` 全中文 [AC-06, Q6]
- [ ] E2-3：grep `st.title(` 全中文

### E3. Raw SQL 紀律檢查
- [ ] E3-1：rg raw SQL pattern ≤ 1 match（main.py /health）[§7.1]

### E4. Playwright smoke test
- [ ] E4-1：admin → 即時監控 → 看 5 條線 + 60 列 [AC-05]
- [ ] E4-2：admin → 資料管理 → inline edit row → 儲存 → DB 變化 [AC-09]
- [ ] E4-3：user → 改 admin row → toast「沒有權限」[AC-09]
- [ ] E4-4：admin → 系統管理 > 即時資料歷史 → wide table [AC-10]
- [ ] E4-5：admin → 系統管理 > 改密碼 → 用新密碼登入驗證 [AC-11]
- [ ] E4-6：viewer → 儀表板 > 帳號設定 → 改自己密碼（驗 old）→ 新密碼登入 [Q12]

### E5. End-to-end integration script
- [ ] E5-1：擴充 `scripts/integration_zeabur_test.sh`：加新 endpoint + 改 admin/realtime-history wide schema 期望
- [ ] E5-2：跑全綠

### E6. 部署 + 監控
- [ ] E6-1：BE Zeabur push（自動跑 alembic 0003）
- [ ] E6-2：30s 後 curl `/admin/realtime-history` 驗 wide row
- [ ] E6-3：FE Zeabur push
- [ ] E6-4：三角色 login + 5 page smoke test
- [ ] E6-5：跑 integration script 全綠
- [ ] E6-6：24h 監控後 v3 backlog（drop long table）

### E7. 文件
- [ ] E7-1：更新 README：新 endpoint + WS payload v2 + UI 中文化
- [ ] E7-2：更新 `.env.example`：加 `ANOMALY_INJECTION_PERIOD`
- [ ] E7-3：標記 v1 long table `realtime_metrics` 為 deprecated
- [ ] E7-4：寫 v3 backlog

---

## Phase 順序與依賴

```
B1 → B2 → B3 → B4 ─┐
                    ├─→ C1, C2, C3, C4, C5, C6 ─┐
                                                  ├─→ D1 → D2..D6 ─→ E1..E7
```

- B 全做完才能跑 C（C 依賴 wide model + schema）
- C 跑完才能跑 D（D 依賴新 endpoint + WS payload）
- E1..E5 可平行
- E6 必所有 phase 完成
