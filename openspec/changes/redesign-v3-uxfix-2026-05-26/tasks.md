# Tasks — Redesign v3 UX Fix（Wiwynn 即時資料分析與監控系統）

**Date**：2026-05-26
**Owner**：spec-writer（tech lead）
**Change**：`redesign-v3-uxfix-2026-05-26`
**讀 brief**：必先讀 `design.md`（600+ 行）+ `user-stories.md`（12 stories）

---

## 任務符號

- [ ] = 未開始
- [x] = 完成
- 每任務：**任務 ID** / **負責 agent** / **依賴 task ID** / **可並行嗎** / **驗證條件**
- Agent 派遣標準：依 v6.1 Software Factory 14 個 sub-agent + main session 分工
- **Re-Read brief.md first** 規則：每 sub-agent prompt 必含此指令（design.md 完整禁簡化）

---

## Phase A — 1.5 hr 動工前 5 假設驗（Q3 拍板）

> 投資 1.5 hr de-risk，避免後續 6 hr 重做。任何 VA 假設失敗 → 走 design.md Story # 退化路徑。

- [ ] **A.1** VA-9 curl `/admin/settings` viewer 角色（5 min）
  - 負責：**main session**（無需 sub-agent，curl 一發即知）
  - 依賴：無
  - 可並行：是（與 A.2 A.3 A.4 A.5 都可並行）
  - 動作：
    1. `curl -X POST <ZEABUR_BE_URL>/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"viewer@example.com","password":"viewer123"}'`
    2. 取 access_token
    3. `curl -H "Authorization: Bearer <jwt>" <ZEABUR_BE_URL>/api/v1/admin/settings`
  - 驗證：HTTP status code = 403（預期，因 AdminOnly 守衛 deps.py:60）→ Story #5 走 fallback 路徑；若 200 → Story #5 走 normal path（升級 BE perm 矩陣風險）
  - 結果寫到：commit message 或 Discord 通知

- [ ] **A.2** VA-20 Zeabur webhook trivial commit 驗（5 min）
  - 負責：**main session**
  - 依賴：無
  - 可並行：是
  - 動作：
    1. 在 `frontend/streamlit_app/Home.py` 末尾加一行註釋 `# v3 phase A.2 webhook test`
    2. `git commit -am "test: v3 phase A.2 webhook smoke" && git push origin <fork-branch>`
    3. 等 5 分鐘
    4. `ZEABUR_API_TOKEN=<token>` 查 deployment status
  - 驗證：status = RUNNING；若 != RUNNING 主動 `redeployService`；超時 10 min → Discord 升級懷特（feedback_zeabur_push_active_check）

- [ ] **A.3** VA-1/16/17 Home 三按鈕 + session_state 預填 spike（30 min）
  - 負責：**frontend-engineer sub-agent**
  - 依賴：無
  - 可並行：是
  - Prompt to sub-agent：「Re-Read design.md Section 4 Story #1 完整。在 `frontend/streamlit_app/Home.py:23` 之前加 `st.expander('試用帳號（Demo 用）', expanded=True)` 含 3 顆按鈕 admin/user/viewer，按下後 `st.session_state['prefill_email']` + `prefill_password`，line 29-30 form input 加 `value=st.session_state.get('prefill_email', '')` 預填。試 `st.rerun()` 後 form 是否能 programmatic submit。完成印『SPIKE A.3 DONE』+ 列 (a) programmatic submit 可行 / 需 2-click (b) 改動 file:line」
  - 驗證：本地 `streamlit run Home.py` 開 → 點按鈕 → 看是否自動登入 or 需手動按「登入」；2-click 也算 PASS

- [ ] **A.4** VA-8/7 FE-only mock anomaly snapshot spike（45 min）
  - 負責：**frontend-engineer sub-agent**
  - 依賴：無
  - 可並行：是
  - Prompt：「Re-Read design.md Section 3.4 + Section 4 Story #4 完整（schema 對齊規則 BLOCKER）。寫 `_mock_anomaly_snapshot()` helper 在 `pages/4_即時監控.py` 內。手動跑 `streamlit run` 後 print mock dict → 與 `client.get('/realtime/history?seconds=60').json()['snapshots'][-1]` 真實 BE response 逐欄位 diff（schema_version / ts / 5 metric / anomaly_flags / source）。把 mock dict `ws_client.push_tick(fake)` → 等 autorefresh → 看 (a) 告警卡 fire (b) Styler 淡粉紅 row (c) 折線圖 anomaly marker。完成印『SPIKE A.4 DONE』+ (a) schema diff 結果 (b) 三層 UX 各層 fire 與否」
  - 驗證：schema 5 欄位完全對齊 + 三層 UX 至少 2 層 fire

- [ ] **A.5** VA-10 plotly subplots 5 row + anomaly marker spike（1 hr）
  - 負責：**frontend-engineer sub-agent**
  - 依賴：無（與 A.4 可並行，不同檔案區塊）
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #6 完整（核心技術選擇 pseudocode）。複製 `pages/4_即時監控.py:214-264` 到 mini script `/tmp/spike_subplots.py`，改 `plotly.subplots.make_subplots(rows=5, cols=1, shared_xaxes=True)`，加 anomaly marker 用 `row=idx`。用假資料（60 個 tick，每 10 個 tick 對溫度 + cpu 設 anomaly_flags True）跑，看 (a) 5 subplot 是否各自獨立 Y 軸 (b) anomaly marker 是否落在正確 subplot (c) 1080p viewport 是否需要 scroll。完成印『SPIKE A.5 DONE』+ (a) marker 位置驗 PASS/FAIL (b) viewport 5 subplot 高度建議」
  - 驗證：marker 位置 PASS = Story #6 走正常 small multiples path；FAIL = 走 G2 fallback secondary y-axis

- [ ] **A.6** Phase A 結果彙整 + Discord 通知 + go/no-go 決策（5 min）
  - 負責：**main session**
  - 依賴：A.1-A.5 全完成
  - 可並行：否
  - 動作：彙整 5 個 VA 假設結果，決策每個 Story 走 normal / fallback / 砍項 → Discord 通知懷特 + push CC 儀表板 URL

---

## Phase B — Sprint 1 Foundation（Hour 1.5 - 4）

> Story #1 + #2 + #3 三個並行可派 3 sub-agent。

### B.1 Story #1 — Home 試用帳號一鍵帶入

- [ ] **B.1.1** 抽 `render_role_matrix(role)` helper 進 `auth.py:91+`（讓 Story #2 共用，先抽）
  - 負責：**frontend-engineer sub-agent**
  - 依賴：A.6
  - 可並行：是（與 B.1.2 不同檔案）
  - Prompt：「Re-Read design.md Section 4 Story #2 完整。在 `frontend/streamlit_app/auth.py:91` 之後新增 `render_role_matrix(role: str)` helper pure function，從 `pages/5_系統管理.py:88-105` 複製 13 行 markdown table，當前角色那欄前面加 ` **粗體 ✓** `（VA-13 失敗走 markdown bold fallback，禁 HTML）。不刪除 `5_系統管理.py:88-105` 既有 expander，只改 `expanded=False` → `True`。完成印『B.1.1 DONE』+ 列改動 file:line」
  - 驗證：grep `def render_role_matrix` 在 `auth.py` 存在 + admin 登入 系統管理 看 expander 預設展開

- [ ] **B.1.2** Home 加試用帳號 expander + 3 顆按鈕（依 A.3 spike 結果）
  - 負責：**frontend-engineer sub-agent**
  - 依賴：A.3 + A.6
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #1 完整。實作 Home.py expander + 3 顆按鈕，依 A.3 spike 結果決定 1-click（programmatic submit）or 2-click（auto-fill + 手動 submit）。試用帳號明文密碼（AC edge case 5 已接受）。完成印『B.1.2 DONE』」
  - 驗證：本地 streamlit run → 截 Home 頁 → 點「以 Viewer 登入」→ 看是否到 Dashboard

### B.2 Story #2 — Dashboard 角色矩陣固定卡片

- [ ] **B.2.1** Dashboard 插入 `render_role_matrix(role)` 呼叫
  - 負責：**frontend-engineer sub-agent**
  - 依賴：B.1.1（helper 抽完）
  - 可並行：是（與 B.3 不同檔案）
  - Prompt：「Re-Read design.md Section 4 Story #2 完整。在 `pages/1_儀表板.py:41` `st.markdown('---')` 之後、line 43 `# ── D2-4 System status header` 之前插入 `with st.container(border=True): render_role_matrix(role)`。確認既有 status header + 4 metric cards layout 不破。完成印『B.2.1 DONE』」
  - 驗證：3 角色登入 Dashboard 截圖 → 看矩陣 + status header + metric cards 都正常

### B.3 Story #3 — 5 頁 onboarding micro-copy

- [ ] **B.3.1** 5 頁加 caption（並行可派 5 sub-agent）
  - 負責：**5 個 frontend-engineer sub-agent**（每個改 1 個 page file）
  - 依賴：A.6
  - 可並行：是（5 個檔案完全獨立）
  - Prompt for each：「Re-Read design.md Section 4 Story #3 完整（caption 5 段內容表）。在 `pages/<N>_<頁名>.py:<插入位置>` 加 `st.caption('...')` 對應內容。文字 ≤ 80 中文字，禁 HTML。完成印『B.3.<N> DONE』」
  - 驗證：`rg "st\.caption" frontend/streamlit_app/pages/` 看 5 頁各 ≥ 1 caption 在 title 50 行內

### B.4 Sprint 1 驗收

- [ ] **B.4.1** pytest 全綠
  - 負責：**test-automator sub-agent**
  - 依賴：B.1.1 B.1.2 B.2.1 B.3.1 全完成
  - 可並行：否
  - Prompt：「Re-Read design.md Section 5.3 round 1 8 個 P0 bug smoke test 表。`cd backend && pytest -v --cov=app` 全綠 + 跑 round 1 8 個 curl smoke test。完成印『B.4.1 DONE』+ 列 pytest 通過數 + smoke test 結果」
  - 驗證：pytest exit 0 + 8 smoke test 全 200

- [ ] **B.4.2** Chrome MCP 截 3 角色 × Dashboard 看矩陣 + caption
  - 負責：**main session**（Chrome MCP 不繼承 sub-agent）
  - 依賴：B.4.1
  - 可並行：否
  - 驗證：3 張截圖 → main 自己 Read → 看 (a) 矩陣卡在 status header 上 (b) 當前角色 bold ✓ (c) caption 在 title 下方

- [ ] **B.4.3** Discord 通知 Sprint 1 完成 + push CC
  - 負責：**main session**

---

## Phase C — Sprint 2 Core UX（Hour 4 - 11）

> Story #4 → #6 → #5 鏈式依賴（#6 必先 #4 驗 anomaly marker）；#7 #8 可並行

### C.1 Story #4 — Demo 控制 + FE-only mock anomaly

- [ ] **C.1.1** 實作 `_mock_anomaly_snapshot()` helper + Demo 控制 container
  - 負責：**frontend-engineer sub-agent**
  - 依賴：A.4（spike 結果）+ Phase B 完成
  - 可並行：是（與 C.4 C.5 不同區塊）
  - Prompt：「Re-Read design.md Section 4 Story #4 完整（pseudocode 含 5 欄位 schema 對齊 BLOCKER）+ Section 3.4 端對端資料流。在 `pages/4_即時監控.py:145` 之前插入 `st.container(border=True)` 含 Demo 控制 + 按鈕。完成印『C.1.1 DONE』+ (a) 改動 file:line (b) mock dict 5 欄位列出對齊 BE schema」
  - 驗證：手動點按鈕 → 1-2 秒後告警 + 表格 + 圖三層 fire

- [ ] **C.1.2** Styler logging（M5 拆分 b，時間箱壓力大可砍）
  - 負責：**frontend-engineer sub-agent**
  - 依賴：C.1.1
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #8（M5 拆分 b）。改 `pages/4_即時監控.py:357-359` except 加 `logger.warning + st.warning`。grep audit `delta_color="inverse"` 全 repo。完成印『C.1.2 DONE』」
  - 驗證：grep `delta_color="inverse"` 確認剩餘位置都有 comment 說明

### C.2 Story #6 — plotly subplots small multiples（依 A.5 spike 結果）

- [ ] **C.2.1** 改寫 `pages/4_即時監控.py:214-264` 為 `make_subplots`
  - 負責：**frontend-engineer sub-agent**
  - 依賴：C.1.1（mock anomaly 才能驗 marker）+ A.5 spike
  - 可並行：否（必在 C.1.1 後）
  - Prompt：「Re-Read design.md Section 4 Story #6 完整 pseudocode。改 `pages/4_即時監控.py:214-264` 為 `plotly.subplots.make_subplots(rows=n_rows, cols=1, shared_xaxes=True)`，anomaly marker 加 `row=idx` 對應 metric。multiselect default 改 `["temperature", "pressure", "cpu_usage"]`（line 152）。height=180*n_rows，uirevision 保留。若 A.5 spike fail → 走 G2 fallback secondary y-axis（Phase E）。完成印『C.2.1 DONE』」
  - 驗證：手動觸發 Story #4 mock anomaly → 看溫度 subplot + cpu_usage subplot 各自有 red marker

### C.3 Story #5 — 動態閾值 fetch（依 VA-9 結果決定路徑）

- [ ] **C.3.1** 新增 `fetch_dynamic_thresholds()` helper
  - 負責：**frontend-engineer sub-agent**
  - 依賴：A.1（VA-9 驗證結果）+ Phase B 完成
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #5 完整。在 `pages/4_即時監控.py:55-69` hardcode dict 之後新增 `fetch_dynamic_thresholds()` `@st.cache_data(ttl=30)`。依 VA-9 結果：若 viewer 403 → 走 AC-3 fallback（caption 「閾值顯示為預設值（唯讀）」）；若 200 → 走 normal path。Line 186-189 改讀 dynamic dict。完成印『C.3.1 DONE』+ (a) VA-9 走哪條 path (b) 改動 file:line」
  - 驗證：admin 改設定 → 30 秒後即時監控反映 + viewer 看到 caption

### C.4 Story #7 — 角色 Demo Banner

- [ ] **C.4.1** auth.py 新增 `render_demo_banner(role)` helper + Dashboard 插入
  - 負責：**frontend-engineer sub-agent**
  - 依賴：B.2.1（同檔 auth.py 已抽 helper）
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #7 完整。在 `auth.py` 新增 `render_demo_banner(role)`（依角色顯示 st.info + 不再顯示 checkbox）。Dashboard 在 `render_role_matrix(role)` 之後插入 `render_demo_banner(role)`。完成印『C.4.1 DONE』」
  - 驗證：3 角色登入 Dashboard 看 banner 文字反映角色

### C.5 Story #8 — Delta Color 修復

- [ ] **C.5.1** grep audit + 改 `delta_color="inverse"` → `"normal"`
  - 負責：**frontend-engineer sub-agent**
  - 依賴：Phase B 完成
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #8（M5 拆分 a）。grep 全 frontend repo `delta_color\s*=\s*"inverse"`，逐處 audit：4_即時監控.py:196 必改；1_儀表板.py:154 改（雖未設 delta 也改避免誤導）。完成印『C.5.1 DONE』+ 列每個改動 file:line + 該位置改前/改後」
  - 驗證：grep `delta_color="inverse"` 確認 0 個（或有 comment 說明為什麼保留）

### C.6 Sprint 2 驗收

- [ ] **C.6.1** pytest 全綠 + round 1 smoke test
  - 負責：**test-automator sub-agent**
  - 依賴：C.1.1 C.1.2 C.2.1 C.3.1 C.4.1 C.5.1 全完成
  - 可並行：否
  - 驗證：同 B.4.1

- [ ] **C.6.2** Chrome MCP 截即時監控頁 × 3 角色 × 觸發 mock anomaly 前後
  - 負責：**main session**
  - 依賴：C.6.1
  - 可並行：否
  - 驗證：6 張截圖（3 角色 × 觸發前 / 後）→ main Read 看 (a) 5 subplots（or 3）獨立 Y 軸 (b) 觸發後告警卡 fire + 表格粉紅 + 折線圖 marker 三層 (c) viewer 看到「閾值唯讀」caption

- [ ] **C.6.3** Discord 通知 Sprint 2 完成

---

## Phase D — Sprint 3 Polish（Hour 11 - 14）

> Story #9 #10 #11 並行可派 3 sub-agent

### D.1 Story #9 — Metric Cards 品質化

- [ ] **D.1.1** Dashboard col4 改「今日異常率」+ delta vs 昨日
  - 負責：**frontend-engineer sub-agent**
  - 依賴：Phase C 完成
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #9 完整。改 `pages/1_儀表板.py:151-155` 為 `col4.metric('今日異常率', f'{rate:.3f}%', delta=f'{delta_pct:+.3f}% vs 昨日', delta_color='normal', help='...')`。需第二次 fetch unified-summary（昨日範圍）。4 個 cards 全加 help 參數。完成印『D.1.1 DONE』」
  - 驗證：開 Dashboard 看 col4 顯示百分比 + delta + hover 看 tooltip

### D.2 Story #10 — 告警卡嚴重度

- [ ] **D.2.1** 告警卡 cols max 3 + > 3 走 list view
  - 負責：**frontend-engineer sub-agent**
  - 依賴：C.1.1（mock anomaly）+ C.2.1（subplots）
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #10。改 `pages/4_即時監控.py:184` `st.columns(min(len(...), 5))` → `min(3)`。`len > 3` 改顯 markdown 表格 list view。完成印『D.2.1 DONE』」
  - 驗證：mock anomaly 多次觸發 5 metric 全異常 → 看是否切 list view

### D.3 Story #11 — 系統管理 4 個 P1 修補

- [ ] **D.3.1** Audit log size 改 50
  - 負責：**frontend-engineer sub-agent**
  - 依賴：Phase C 完成
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #11 AC-1。改 `pages/5_系統管理.py` audit log section `params['size']` 從 10 改 50。完成印『D.3.1 DONE』」

- [ ] **D.3.2** Settings expander 預設 collapsed + 展開全部按鈕
  - 負責：**frontend-engineer sub-agent**
  - 依賴：D.3.1
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #11 AC-2。改 `pages/5_系統管理.py:577-632` setting expander `expanded=True` → 用 `st.session_state['expand_all_settings']` 控制；頂部加 `st.button('展開全部設定')`。完成印『D.3.2 DONE』」

- [ ] **D.3.3** DELETE user button（補 5.3 需求缺口，P1 路徑非 G1）
  - 負責：**frontend-engineer sub-agent**
  - 依賴：D.3.1
  - 可並行：是
  - Prompt：「Re-Read design.md Section 4 Story #11 AC-3 端對端資料流。在 `pages/5_系統管理.py` 使用者列表下方新增 `st.selectbox('選擇要刪除的使用者')` + `st.button('刪除使用者', type='primary')` → 呼叫 `client.delete(f'/users/{uid}')`。FE disable 「刪除自己」（compare `current_user_id != target_id`）。404 處理「此用戶已被刪除」。完成印『D.3.3 DONE』+ 列改動 file:line」
  - 驗證：admin 刪除 viewer 角色 user → 看是否消失 + audit log 多一筆 `delete_user`

### D.4 Sprint 3 驗收

- [ ] **D.4.1** pytest 全綠 + round 1 smoke
  - 負責：**test-automator sub-agent**
  - 依賴：D.1.1 D.2.1 D.3.1 D.3.2 D.3.3 全完成

---

## Phase E — 灰色地帶 G2 補強（Hour 14 - 16，僅 A.5 spike 失敗才做）

> Q5 拍板：補 G2 only（plotly secondary y-axis fallback if VA-10 subplots 失敗）

- [ ] **E.1** 評估 C.2.1 結果是否需 G2
  - 負責：**main session**
  - 依賴：C.6.2 截圖驗收結果
  - 動作：若 small multiples PASS → 跳過 Phase E；FAIL → 走 E.2
  - 驗證：main 看 C.6.2 截圖 + 自測

- [ ] **E.2** 改 `pages/4_即時監控.py:214-264` 為 secondary y-axis（pressure 獨立軸，其他 4 共軸）
  - 負責：**frontend-engineer sub-agent**
  - 依賴：E.1 決策 = 需要
  - Prompt：「Re-Read design.md Section 4 Story #6 G2 fallback 段。改用 `make_subplots(specs=[[{'secondary_y': True}]])`，pressure trace `secondary_y=True`，其他 4 metric `secondary_y=False`。anomaly marker 同樣依 metric 分軸。完成印『E.2 DONE』」
  - 驗證：截即時監控頁看 voltage / temperature 各自可讀

---

## Phase F — 驗收（Hour 16 - 22）

### F.1 pytest 全綠 + round 1 8 個 P0 smoke test

- [ ] **F.1.1** 跑 `pytest -v --cov=app`
  - 負責：**test-automator sub-agent**
  - 依賴：Phase D / E 完成
  - 可並行：否
  - Prompt：「Re-Read design.md Section 5.3 round 1 8 個 P0 bug smoke test 表。`cd backend && pytest -v --cov=app` + 跑 round 1 8 curl smoke test。完成印『F.1.1 DONE』+ (a) 通過數 (b) regress 項目（若有）」
  - 驗證：exit 0 + 8 smoke test 全 200

### F.2 端對端 Chrome MCP 5 頁 × 3 角色 = 15 張截圖

- [ ] **F.2.1** Chrome MCP 開瀏覽器 → 3 角色 × 5 頁逐張截
  - 負責：**main session**（MCP 不繼承 sub-agent）
  - 依賴：F.1.1
  - 可並行：否
  - 動作：
    1. viewer 登入 → 截 Home / Dashboard / 資料管理 / 分析報表 / 即時監控 = 5 張
    2. user 登入 → 同 5 張
    3. admin 登入 → 6 張（多系統管理頁）
  - 驗證：每張 main 自己 Read → 描述「我看到什麼」→ 對照 design.md Section 6.4 截圖驗收標準表

- [ ] **F.2.2** 派 sub-agent 看圖（feedback_v6_full_closed_loop 5/25 嚴令）
  - 負責：**ui-ux-tester sub-agent**（注意只能 Read 圖檢視，不能跑 Chrome MCP）
  - 依賴：F.2.1（main 把圖存到固定路徑）
  - Prompt：「Re-Read design.md Section 6.4 + Section 7 DOD。Read 15 張截圖（路徑：main 提供）。對每張描述 (a) 我看到什麼 (b) design.md 期望什麼 (c) 差異 → escalate。完成印『F.2.2 DONE』+ 列任何破洞」
  - 驗證：sub-agent 報告無破洞

### F.3 Demo Script A/B/C 跑通

- [ ] **F.3.1** Demo Script A — Viewer 5 分鐘掃
  - 負責：**main session**
  - 依賴：F.2.1
  - 動作：依 user-stories.md Section 5 Script A 逐步驗 4 個 step → K1 K2 K3 都達標
  - 驗證：5 分鐘內看到 RBAC / 即時 / 異常觸發

- [ ] **F.3.2** Demo Script B — Admin 深度驗
  - 負責：**main session**
  - 依賴：F.3.1
  - 動作：依 Script B 4 step → K4 K5 + 需求覆蓋感知達標

- [ ] **F.3.3** Demo Script C — Builder 自測 11 條 checklist
  - 負責：**main session**
  - 依賴：F.3.2
  - 動作：依 Script C 11 條 checklist 全勾 ✓

### F.4 ui-ux-tester sub-agent 整體 UX 驗收

- [ ] **F.4.1** 派 ui-ux-tester sub-agent 跑整體 UX audit
  - 負責：**ui-ux-tester sub-agent**
  - 依賴：F.3.3
  - Prompt：「Re-Read design.md（全）+ user-stories.md（12 stories AC）+ 15 張截圖路徑。對每個 Story AC 對應「實際看到 vs 期望」評分 1-5。完成印『F.4.1 DONE』+ 任何 Score < 3 escalate」
  - 驗證：所有 Story AC 平均 ≥ 4

### F.5 implementation-validator 找 spec vs code gap

- [ ] **F.5.1** 派 implementation-validator sub-agent
  - 負責：**implementation-validator sub-agent**
  - 依賴：F.4.1
  - Prompt：「Re-Read design.md Section 4 12 個 Story 改動檔案清單 + Section 5 風險表 + Section 7 DOD。對每個 Story 跑 (a) grep 驗 file:line 改動是否存在 (b) AC 逐條對照 code (c) 端對端資料流 5 段對齊驗（design.md Section 3.4 + 每 Story 的 5 段表）。產出 80-120 條 validation checklist。完成印『F.5.1 DONE』+ checklist 100% 綠或 escalate」
  - 驗證：checklist 100% 綠

---

## Phase G — commit + push + 部署驗（Hour 22 - 24）

- [ ] **G.1** commit 帶 Co-Authored-By Claude（pr-reviewer 看過）
  - 負責：**main session**
  - 依賴：F.5.1
  - 動作：
    1. `git status` 看所有改動
    2. `git diff --stat`
    3. `git add -A && git commit -m "feat(v3): UX redesign — 12 stories (M1-M5 + P1)\n\n...\n\nCo-Authored-By: Claude <noreply@anthropic.com>"`
  - 驗證：commit message 完整

- [ ] **G.2** push DennisPai fork（依 feedback_git_remote_check 4/22 嚴令）
  - 負責：**main session**
  - 依賴：G.1
  - 動作：
    1. `git remote -v` 確認 origin 是 `DennisPai`（非 santifer）
    2. `git push origin <branch>`
  - 驗證：remote URL 含 `DennisPai`

- [ ] **G.3** 主動查 Zeabur 部署（依 feedback_zeabur_push_active_check 5/23 嚴令）
  - 負責：**main session**
  - 依賴：G.2
  - 動作：
    1. 等 5 分鐘
    2. `ZEABUR_API_TOKEN=<token>` 查 deployment status
    3. status = RUNNING → 下一步；其他 → 自助 `redeployService`
    4. 超時 max 10 min wait → Discord 升級懷特
  - 驗證：Zeabur status = RUNNING + commit SHA 對應

- [ ] **G.4** 重 test 3 角色生產環境（重跑 F.3 但走 Zeabur URL）
  - 負責：**main session**
  - 依賴：G.3
  - 動作：Chrome MCP 開 Zeabur URL → 3 角色登入 → Demo Script A 跑一遍
  - 驗證：所有 Story AC 在生產環境也綠

- [ ] **G.5** Discord 最終通知 + push CC 儀表板
  - 負責：**main session**
  - 依賴：G.4
  - 動作：Discord 1491076042906013796 通知 + push CC + 給 URL

---

## 附錄 — Sub-agent 派遣標準 prompt template

每派 sub-agent 必含以下 5 段（依 CLAUDE.md 4/10 禁簡化嚴令）：

```
你是 <agent role> sub-agent，負責 <task ID>。

**MUST 動作型指令**（禁簡化）：
1. Re-Read /home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/openspec/changes/redesign-v3-uxfix-2026-05-26/design.md（完整，禁簡化）
2. Re-Read 對應 Story # 的 Section 4 設計表（含 5 段端對端資料流對齊）
3. Re-Read assumption-mapping.md Section 4 對應 VA-x（若有 spike 退化路徑）
4. 動工（具體到改 file:line）
5. 完成後印「<TASK ID> DONE」+ 列 (a) 改動 file:line (b) pytest 結果 (c) 自測 checklist

**禁止**：
- 禁簡化 SOP / 禁寫 batch brief
- 禁假設「endpoint 改了不用驗」必 curl smoke
- 禁靠記憶判斷檔案位置，必 Read / Grep / Glob 查清楚再動
- 禁繼承「pytest 綠 = done」（5/25 教訓），視覺類必派 main 截圖

**端對端鐵律**（5/23 嚴令）：
FE 改完必驗端對端資料流（FE 送 → BE 收 → DB 存 → BE 回 → FE 顯示）對齊 design.md 對應 Story 的 5 段對照表。任何欄位 / 型別不對齊 → BLOCKER 必標。

**北極星**（CLAUDE.md 4/10）：
- 使用者效益最大化（評審 5 分鐘看到技術深度）
- 完整執行使用者命令（12 story 全做，禁自行剃 2-3 個）
- 主動為懷特想到他沒想到的事（看到 spec 漏 case 主動提）
```

---

BRIEF DONE
```

---

**檔案路徑（兩份請 main session 用 Write 落地）**：
- `/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/openspec/changes/redesign-v3-uxfix-2026-05-26/design.md`
- `/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/openspec/changes/redesign-v3-uxfix-2026-05-26/tasks.md`

**關鍵技術裁示重點摘要**（給 main session 快速 reference）：

- **BLOCKER #1**：VA-9 viewer JWT 打 `/admin/settings` 必先 curl 驗（design.md Section 4 Story #5 + tasks.md A.1）。BE `admin.py:169` 走 `AdminOnly`，預期 403 → Story #5 走 AC-3 fallback 路徑（FE caption「閾值唯讀」）
- **BLOCKER #2**：Story #4 mock anomaly 5 欄位必對齊 `RealtimeSnapshotResponse` v2 schema（`backend/app/schemas/realtime.py:22-35`），特別是 `schema_version="v2"` 否則 `ws_client.py:122` 直接 reject
- **Sub-agent MCP 限制**：Chrome MCP / Playwright 必 main session 跑（F.2 截圖 + G.4 重 test 不能派 sub-agent）
- **規則 F 5/21**：每 sub-agent 改完必派獨立 sub-agent 驗（feedback_separate_implement_verify_agents 5/23）
- **5/25 視覺驗收教訓**：F.4 ui-ux-tester 必跑 Chrome MCP screenshot，禁「pytest 綠 = done」（feedback_v6_full_closed_loop）

BRIEF DONE