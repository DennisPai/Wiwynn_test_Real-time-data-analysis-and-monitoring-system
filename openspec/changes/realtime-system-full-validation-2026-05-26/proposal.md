# Full Validation — Wiwynn Real-time System

**狀態**：drafting
**Owner**：大總管（白）
**建立時間**：2026-05-26 09:10 UTC+8
**Zeabur 部署**：
- FE: https://wiwynn-test-real-time-data-analysis-and-monitoring-system.zeabur.app/
- BE: https://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app/
- BE Swagger: https://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app/docs

---

## 1. 為什麼做這個

懷特要求**完整實機測試 + 修正閉環**直到「所有功能正常 + 完全滿足需求文檔」。

現況 spot check：
- ✅ 主 repo 24 endpoints 全實裝（auth 4 / users 4 / data 6 / analytics 4 / admin 5 / ws 1）
- ✅ 5 大 service 全實裝（data / analytics / realtime APScheduler / batch_writer / audit_log）
- ✅ 2 個 utils（csv_importer / excel_exporter）全實裝
- ✅ Streamlit FE 6 頁面（Home / Dashboard / Data / Analytics / Realtime / Admin）
- ✅ Zeabur FE + BE deploy 都活著（/health 200）

但「實裝有」≠「能跑」。要實機測試才知道哪裡壞。

---

## 2. 需求文檔對照

**5 大模組 + 子功能**：

### 模組 1 — 使用者管理
- POST /api/v1/auth/register
- POST /api/v1/auth/login（回 JWT）
- POST /api/v1/auth/logout
- GET /api/v1/auth/me
- 3 角色：Admin / User / Viewer
- RBAC 中介層

### 模組 2 — 資料管理
- POST /api/v1/data（創建）
- GET /api/v1/data（含分頁 / 篩選 / 排序）
- GET /api/v1/data/{id}
- PATCH /api/v1/data/{id}（owner 或 Admin）
- DELETE /api/v1/data/{id}（owner 或 Admin）
- POST /api/v1/data/import（CSV / JSON 批量）

### 模組 3 — 即時監控
- APScheduler 每秒 tick 生成模擬資料
- WebSocket /ws/realtime 推送
- 超閾值異常標記

### 模組 4 — 資料分析
- GET /api/v1/analytics/summary（總計 / 平均 / max / min）
- GET /api/v1/analytics/timerange
- GET /api/v1/analytics/categories（分類聚合）
- GET /api/v1/analytics/export（Excel）

### 模組 5 — 系統管理（Admin）
- GET /api/v1/users（列表）+ PATCH role + DELETE
- GET /api/v1/admin/logs
- GET /api/v1/admin/db-status
- GET /api/v1/admin/realtime-history
- GET /api/v1/admin/settings + PATCH（動態閾值）

### 5 條交付物
1. GitHub repo ✅（DennisPai/Wiwynn_test_Real-time-data-analysis-and-monitoring-system）
2. README.md（介紹 / 技術棧 / 本地運行 / Docker / API / 測試帳號）
3. .env.example
4. CSV 測試範例（docs/sample_data.csv）
5. 系統架構圖（docs/architecture.md）

---

## 3. 測試矩陣（預估 100+ test case）

### 3.1 Backend API 矩陣（test-automator sub-agent）

| 維度 | 計數 |
|---|---|
| Endpoints | 24 |
| 角色（Admin / User / Viewer / unauthenticated） | 4 |
| 權限期望（200 / 403 / 401） | per case |
| 預估 cases | ~70 |

**核心測試項目**：
- 三角色 JWT login + token validity
- CRUD permission matrix（owner vs others vs admin）
- CSV import + JSON import（含 error 逐行回報）
- Analytics summary / timerange / categories / Excel export（驗證 xlsx 真的下載）
- WebSocket /ws/realtime 連線 + 收到 tick
- Admin endpoints 全角色測（403 for non-admin）
- Settings PATCH 動態改閾值 → 影響後續 realtime tick

### 3.2 Frontend Playwright 矩陣（main session 自己跑）

| 流程 | 角色 |
|---|---|
| 登入 / 登出 / Session | 3 角色 |
| Dashboard 顯示 | 3 角色 |
| Data 頁面 CRUD UI | 3 角色 |
| Analytics 頁面 + Excel 下載 | 3 角色 |
| Realtime 頁面 WebSocket 即時圖表 | 3 角色 |
| Admin 頁面 + 隱藏（非 Admin） | 3 角色 |

預估 ~30 case。

### 3.3 Integration / Edge cases

- 第一次啟動 alembic seed 三角色帳號驗證
- 大量 CSV import（60 row 跟更大）
- WS reconnect 行為
- 異常閾值告警在 UI 視覺呈現

---

## 4. 修正閉環

每發現 1 個 bug：
1. **debugger** 找根因（端到端資料流）
2. **backend-engineer / frontend-engineer** 修
3. push GitHub → Zeabur webhook redeploy
4. 重 test → 直到全綠

無 round limit。預估每 bug ~10-20 分鐘 fix。

---

## 5. 範圍

**包含**：實機測試 + bug 修補 + Zeabur 重新部署 + 最終 commit + push

**不包含**：
- 大規模 load test
- security pen-test
- 多語系

---

## 6. 預估時間

| Phase | 內容 | 預估 |
|---|---|---|
| 1 | codebase audit | done (10 min) |
| 2 | OpenSpec + test plan | 10 min |
| 3 | 派 test-automator 跑 backend 測試 | 30-45 min |
| 3.5 | main session 跑 frontend Playwright | 20-30 min |
| 4 | bug 修正閉環 | unknown（看 bug 數量）|
| 5 | implementation-validator 對齊需求 | 15 min |
| 6 | commit + push + 回報 | 10 min |

**總計**：1.5-3+ 小時，bug 數越多越久。
