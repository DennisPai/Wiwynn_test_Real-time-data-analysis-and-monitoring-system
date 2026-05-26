# Proposal — Redesign v2：監控系統 UX + 即時資料模型重構

**Date**：2026-05-26
**Owner**：tech lead
**Type**：full redesign（涵蓋 schema / 採集邏輯 / 5 個前端頁面 / 部分 API 契約）
**Round 1 前置 fix**：fb3916b + 63b74e8 + 1c92723 + fa4590c 已修補 BE 24/24 endpoint + 3 角色 login + WS with token，但**設計層問題**全在本次 redesign 處理。

---

## 1. Why（為什麼要 redesign）

### 1.1 懷特 12 點反饋（ground truth）

|#|反饋摘要|影響層|對應段|
|---|---|---|---|
|1|模擬腳本是否在後端跑、是即時嗎|採集|design §2|
|2|不該「點進去才累積」，應「電影持續播放、中場加入」|採集+訂閱|design §2/§3|
|3|所有 emoji 拿掉，不專業|UI 紀律|design §5|
|4|告警旁加 Δ 數值；表格擴 60 筆；異常 row 淡粉紅 + 紅字|Realtime UX|design §4.4|
|5|每 tick 應回傳所有類別 snapshot，不是混雜|Schema + 採集|design §1+§2|
|6|Analytics / Dashboard 頁面標題是英文，要中文|i18n|design §4.1/§4.3|
|7|Analytics 時間趨勢圖空白，bug|BE/FE bug|design §4.3|
|8|Realtime 與 Dashboard / Data / Analytics 資料不互通|Schema decoupling|design §1|
|9|資料管理「逐筆操作」難用，要做在表格上 inline edit|FE redesign|design §4.2|
|10|資料各類別獨立、管理混亂|Schema + Analytics view|design §1/§4.3|
|11|系統管理「全類別」即時歷史圖無意義|Admin redesign|design §4.5|
|12|使用者列表角色權限不明、缺改密碼|Admin redesign|design §4.5|

### 1.2 業界 norm（research findings）

- 採集 vs 訂閱解耦（Prometheus / Datadog / Grafana Live / InfluxDB / Zabbix 共識）
- Snapshot + Delta 訂閱模式（前端進頁拿 REST history，再 WS subscribe 增量）
- Wide ingestion line（同 ts 一筆 row 含所有 metric，InfluxDB Line Protocol 範式）
- Random walk 模擬感測器，不是純 i.i.d uniform random
- 異常 UX 三重視覺：淡背景 + icon + Δ（Carbon Design System）
- System status header（last update + WS dot + alert count）3 秒 glance 判健康

→ 完全對齊懷特直覺。

### 1.3 抽象目標（懷特 quote）

1. 所有功能正常 + 滿足需求文檔
2. 好用、知道怎麼用的即時資料分析與監控系統

---

## 2. Scope（範圍）

### 2.1 In scope

#### Backend
- 新增 `realtime_metrics_wide` table（wide format，一筆 row 含全 metric snapshot）
- `realtime_simulator` 改 random walk + 每 tick 廣播全類別 snapshot
- `batch_writer` 改寫入 wide table（同時保留 long table 作 query 相容期）
- 新 endpoint：`GET /api/v1/realtime/history?seconds=N`（任何角色，不再 admin-only）
- 新 endpoint：`PATCH /api/v1/users/{id}/password`（admin 改任意人；user/viewer 改自己）
- 修 endpoint：`GET /api/v1/analytics/timerange`（bucket 為空白 root cause + 跨 dialect timestamp 解析）
- 修 endpoint：`GET /api/v1/admin/realtime-history` 改回傳 wide snapshot row
- WS payload schema：`SnapshotTick`（含 ts + 5 個 metric value + 5 個 anomaly_flag）取代原 `RealtimeTick`
- Alembic migration `0003_realtime_wide_format`（SQLAlchemy ORM 操作，禁 raw SQL）

#### Frontend（全頁中文標題，全部移除 emoji）
- Home：登入頁標題 + 表單字串去 emoji
- Dashboard（標題改「儀表板」+ 加 system status header）
- 資料管理（移除「逐筆操作」expander、改 `st.data_editor` inline edit）
- 分析報表（原 Analytics，標題改中文、修 timerange 圖、整合 realtime+data_records unified view）
- 即時監控（標題保留中文；page enter = REST history 60s + WS subscribe；告警卡 + 60 筆表 + 異常 row 淡粉紅 + 紅字 + Δ 欄）
- 系統管理（標題保留中文；wide snapshot 即時歷史；角色權限說明卡片；改密碼功能）

#### 紀律
- 禁 raw SQL（除 `/health` + 必要 migration utility，需註解理由）
- 禁 emoji（所有 .py 檔頁面標題 / 按鈕 label / 表格欄位 / docstring 全清）
- 禁「import 不用」的 emoji unicode 字元留在源碼

### 2.2 Out of scope

- DB migration 從 wide → 只剩 wide（保留 long format `realtime_metrics` 過渡期，下次 v3 再砍）
- 角色 RBAC 大改（admin/user/viewer 三角色不變）
- 國際化框架（i18n）— 直接寫中文字串
- 真實感測器接入（仍用 simulator）
- 監控 alert 推播（Email / LINE / Slack 整合）
- Anomaly detection 演算法（seasonal / trend-aware）— 保持簡單 high/low 閾值
- Excel export 改格式（保持現有 3-sheet 結構）
- Login 加 OAuth / SSO
- 前端 SPA 化（保持 Streamlit）

---

## 3. Risks + Mitigation

### 3.1 Schema 雙 table 風險（HIGH）
**問題**：新 wide table 與舊 long 並存可能造成 query 邏輯分歧 / 資料雙寫不一致。
**緩解**：batch_writer 同寫兩 table；舊長 table 變唯讀備援；v3 才 drop。

### 3.2 WS payload schema breaking change（MEDIUM）
**問題**：payload 改 wide schema，舊 client 解析會壞。
**緩解**：FE/BE 同 commit 同步上線 + schema_version="v2" 欄位。

### 3.3 Streamlit `st.data_editor` 跨 row 權限控制（MEDIUM）
**問題**：表格 inline edit 一次 mutate 多 row，但 user 只能改自己。
**緩解**：FE 用 disabled cols + 提交時逐筆 PATCH + 無權限 silent skip toast。

### 3.4 修 Analytics timerange 圖空白 root cause 未明（MEDIUM）
**問題**：可能是 (A) timestamp format / (B) tz-aware vs naive mismatch / (C) empty data set。
**緩解**：builder 必須先驗證 root cause（curl 直打 BE）後再修。預期 (B)：DB column 改 `DateTime(timezone=True)` 或 endpoint 轉 naive UTC。

### 3.5 跨頁資料互通的解法選擇（LOW）
**問題**：realtime_metrics_wide vs data_records 兩 source。
**緩解**：API 層加 `/analytics/unified-summary` 整合，不合併 table（語意不同）。

### 3.6 random walk 重啟後狀態流失（LOW）
**緩解**：simulator startup 讀 wide table 最後一筆作 initial state。

### 3.7 業界 norm 與實際 timeline 衝突（LOW）
**緩解**：本次 v2 只做 schema + 採集 + UX 三大塊，演算法升級延後。

---

## 4. Acceptance Criteria（每條對應實作檔案）

| AC | 對應 12 點 | 驗收方式 | 主要實作檔案 |
|---|---|---|---|
| AC-01 | Q1, Q2, Q5 | BE 啟動後 30s 不開 FE，DB 仍有 ≥ 30 筆 wide snapshot | `realtime_service.py` + `batch_writer.py` |
| AC-02 | Q5 | WS 每 tick 收到 payload 含 ts + 5 metric value + 5 anomaly_flag | `realtime_service.py` + `ws_client.py` |
| AC-03 | Q2 | Realtime 頁面打開後 < 1s 顯示最近 60 筆歷史折線 | `pages/4_即時監控.py` + `GET /realtime/history` |
| AC-04 | Q3 | grep emoji unicode 全 codebase 0 matches | 全前端 .py 檔 |
| AC-05 | Q4 | 告警卡 Δ + 60 列表 + 異常 row 淡粉紅 + cell 紅字 | `pages/4_即時監控.py` |
| AC-06 | Q6 | 5 個 page page_title + title 全中文 | 全 5 個 page .py |
| AC-07 | Q7 | curl timerange 有資料區間回 buckets 非空；FE 圖表畫出折線 | `analytics_service.py` + `pages/3_分析報表.py` |
| AC-08 | Q8, Q10 | Dashboard / 分析報表頁顯示 unified count（兩 source 加總） | `/analytics/unified-summary` + 2 個 FE page |
| AC-09 | Q9 | 資料管理頁無 expander「逐筆操作」；表格 inline edit；無權限 toast 拒絕 | `pages/2_資料管理.py` |
| AC-10 | Q11 | 系統管理「即時資料歷史」 tab 顯示 wide snapshot 表 + 多線折線圖 | `pages/5_系統管理.py` |
| AC-11 | Q12 | 使用者列表權限矩陣卡片 + 改密碼表單可用 | `pages/5_系統管理.py` + `PATCH /users/{id}/password` |
| AC-12 | 全部 | pytest 全綠 + Playwright smoke：登入→Realtime→告警→改密碼 | `tests/` + integration script |

---

## 5. Migration / Rollback 計畫

### 5.1 上線順序
1. 部署 BE（含 alembic 0003 自動建 wide table）
2. 驗證 wide table 累積資料
3. 部署 FE（同 commit）
4. 三角色 login + 5 page smoke test
5. 跑 `integration_zeabur_test.sh` 全綠
6. 監控 24h 後 v3 砍 long table

### 5.2 Rollback
- BE：`alembic downgrade -1` 拆 wide table
- FE：revert FE commit

### 5.3 不可逆操作
無（wide 為新增、long 不動）

---

## 6. 與需求文檔對齊

| 需求模組 | 本次動到？ | 對應段 |
|---|---|---|
| 1. 使用者管理 | 是（改密碼 + 角色權限說明）| §4.5, §6 |
| 2. 資料管理 | 是（inline edit）| §4.2 |
| 3. 即時監控 | 全面（schema + 採集 + UX）| §2, §3, §4.4 |
| 4. 資料分析 | 是（修 timerange + unified view）| §4.3, §6 |
| 5. 系統管理 | 是（即時歷史 wide + 改密碼）| §4.5, §6 |
| 技術：SQLAlchemy ORM | 是（migration 走 ORM、禁 raw SQL）| §1 + §7 |
| 技術：WebSocket | 是（payload schema breaking change）| §3 |
| 技術：Alembic | 是（0003 migration）| §1 |
| 技術：Streamlit 多頁面 | 是（5 page 全 review）| §4 |
