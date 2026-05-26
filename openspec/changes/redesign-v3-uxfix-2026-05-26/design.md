# Design — Redesign v3 UX Fix（Wiwynn 即時資料分析與監控系統）

**Date**：2026-05-26
**Owner**：spec-writer（tech lead 視角，opus 模型）
**Change**：`redesign-v3-uxfix-2026-05-26`
**Time budget**：8-24 hr（v6.1 Mode A 加強版 Phase 2）
**讀過的證據檔**：pm-strategy.md（466 行）/ ux-research.md（659 行）/ codebase-audit.md（404 行）/ customer-journey-map.md（1125 行）/ assumption-mapping.md（519 行）/ user-stories.md（559 行）+ FE/BE 端對端程式碼

---

## Section 1: Why this redesign

### 1.1 為什麼要 v3（context）

v1 把面試題功能填齊、v2 已完成「壞功能修好 + 設計層 12 點反饋」（commit a50b045），但**懷特實際看完仍覺得「奇怪、不直觀、難用」**。根因不是「沒做」，是 **v2 沒從「Wiwynn 招募評審 5 分鐘掃 demo」mental model 重新檢視**：

- BE 紮實（24 endpoints / RBAC / WS / Alembic / Docker），FE 中文化 + 5 頁齊備
- 但 **value signal 沒被 surface**：角色矩陣藏在 admin 折疊裡、5 頁零 onboarding micro-copy、即時監控 5 條線壓成貼底直線、anomaly injection 每 60 tick 一次評審等不到、`delta_color="inverse"` 顏色語意反向
- **結論**：v3 是純前端呈現層修補，**不動 BE**，把「已存在的技術深度」變成「評審 5 分鐘看得見的技術深度」

### 1.2 目前痛在哪（finding 量化）

| 維度 | 量化證據 | 來源 |
|---|---|---|
| 評審 emotion 曲線（12 stage 平均） | **1.7 / 5**（disappointed） | customer-journey-map §6 |
| Admin emotion | 2.1 / 5 | 同上 |
| User emotion | 2.0 / 5 | 同上 |
| Viewer emotion | 1.6 / 5 | 同上 |
| Help/caption 覆蓋率 | **41%**（59% 缺失） | codebase-audit Section 8 |
| 需求覆蓋率 | 38/41（92.7%）— 1 個 FE UI 缺（DELETE user） | codebase-audit Section 3 |
| Top friction 致命傷 | 6 個 stage 集中：H-1 / D-1 / R-1 / R-2 / A-2 / DM-1 | customer-journey-map §8 結論 |

### 1.3 達成後評審 5 分鐘 narrative（success state）

評審 demo 完跟同事說：

1. **「這個系統設計考慮到 3 角色 RBAC，Dashboard 第一眼就清楚告訴我能做什麼。」**
2. **「即時監控頁 1 秒一筆 snapshot 推送很流暢，異常會跳紅標示，我手動觸發異常立刻看到告警卡。」**
3. **「5 大模組需求文檔全部覆蓋，BE 有 Swagger 文件、架構圖、Audit log、動態閾值 — production-ready 程度。」**

**全角色 emotion 目標**：1.85 → 4.18（+2.33，customer-journey-map §8.5）。

---

## Section 2: Constraints + Q1-Q5 Decisions（懷特拍板）

### 2.1 懷特 2026-05-26 15:04 UTC+8 Discord 拍板（5 個決策）

| Q | 拍板 | Why |
|---|---|---|
| **Q1：M3 demo panel anomaly 來源** | **FE-only mock anomaly**（不動 BE） | 動 BE = 動 perm test = VA-26 風險飆 5 / 5；FE-only schema 對齊 `RealtimeSnapshotResponse` v2 即可，視覺效果一樣 |
| **Q2：角色矩陣顯示位置** | **方案 A + 部分 C**：Dashboard 頂部固定卡片 + Home 試用帳號 expander | sidebar（方案 B）不可靠（Streamlit Cloud 行動裝置預設收起）；A+C 雙重 cover「未登入評審看到 RBAC」+「登入後三角色看到」 |
| **Q3：動工順序** | **先 1.5 hr 驗 Top 5 A 假設再動 M1-M5** | 投資 1.5 hr de-risk vs 動到一半發現 VA-9 / VA-10 假設失敗整個 M3 / M6 重做要 6 hr+，ROI 4x |
| **Q4：砍項策略** | **M1-M5 全動**；M5 拆 (a) delta_color 30 min + (b) Styler logging 30 min，時間箱壓力大砍 (b) | M5 修「+50 是綠色」是評審第一印象殺手（pm-strategy §6.3 反指標 #4），不能砍；Styler logging 可降級為 silent fallback |
| **Q5：灰色地帶** | **補 G2 only**（plotly secondary y-axis fallback if VA-10 subplots 失敗）；G1 / G3 留 v4 | G2 是 R-1 致命傷的 fallback path，ROI 高；G1 DELETE user UI（VA-31 風險 1）+ G3 改密碼二合一（VA-33 風險 2）對評審加分有限 |

### 2.2 其他硬限制（不可違反）

| 限制 | Why | 違反後果 |
|---|---|---|
| **禁動 BE schema** | v2 已過 33 perm tests + 24 endpoints，BE production-grade | 動 schema = Alembic 0004 migration + 改 schemas + 改 services + 改 tests，8 hr 不夠 |
| **禁動 BE permission 矩陣** | `AdminOnly` / `AnyRole` 守衛已通過驗證 | 動守衛 = 改 deps.py + 33 perm tests 重跑 + 風險 round 1 8 bug regress |
| **禁 break round 1 修補**（8 個 P0 bug） | report_round1_fixes.md 已綠 | 任何 commit 必跑 round 1 smoke test 確認不 regress |
| **禁加新頁（pages/）** | Streamlit `pages/` 目錄新增 = 全頁面 auth 守衛要 hack + side-effect 風險 | Story #1 Home 試用帳號用 expander 不開新 page；Section 7「out of scope」14 項全列 |
| **禁簡化 SOP**（CLAUDE.md 4/10 嚴令） | 完整執行使用者命令 | 不准寫 batch/brief 繞 skill；sub-agent prompt 必明確指定 file:line + 「Re-Read brief.md first」 |
| **Zeabur deploy 風險** | v2 已踩 webhook stall 卡 30 分（feedback_zeabur_push_active_check） | VA-20 Phase A 早期驗；若卡用 `$ZEABUR_API_TOKEN` `redeployService` 自助（reference_zeabur_api_self_service） |
| **不繼承 MCP 限制** | sub-agent 不繼承 Chrome MCP / Playwright（reference_subagent_tool_inheritance） | Chrome MCP 視覺驗收必 main session 跑；sub-agent 只負責改 code / 跑 pytest |

### 2.3 接受性假設（10 條，動工前已 commit 不修）

assumption-mapping.md AC-1 ~ AC-10 全 inherit：autorefresh hover 閃爍 / Tab 4 與即時監控重複 / Excel 兩步下載 / inline edit 無 dirty state / CSV 無 preview / source=realtime bar chart / Plotly toolbar 截圖 / DB pool 無 baseline / 系統設定 5 個 form / DELETE user UI 缺。詳見 assumption-mapping.md §5。

---

## Section 3: 端對端架構

### 3.1 改動檔案清單（明確 file path + line range）

**FE 直改檔案（8 個）**：

| File | 改動範圍 | 對應 Story |
|---|---|---|
| `frontend/streamlit_app/Home.py` | 新增 expander（line 23 之前）+ 3 顆登入按鈕 + session_state 預填 | #1 |
| `frontend/streamlit_app/auth.py` | 新增 `render_role_matrix(current_role)` helper | #2 |
| `frontend/streamlit_app/pages/1_儀表板.py` | line 41 之後插入 `render_role_matrix()` + caption + Demo Banner + metric card 品質化 + delta_color | #2 #3 #7 #9 |
| `frontend/streamlit_app/pages/2_資料管理.py` | line 41 之後插入 caption | #3 |
| `frontend/streamlit_app/pages/3_分析報表.py` | line 54 之後插入 caption + Source toggle 修補（P2） | #3 #12 |
| `frontend/streamlit_app/pages/4_即時監控.py` | 大改：新增 Demo 控制（line 145 之前）+ fetch `/admin/settings` 動態閾值 + plotly subplots 改寫 line 214-264 + delta_color line 196 + Styler logging line 344-359 + 告警卡 metric 名稱 + 嚴重度 line 184-197 | #4 #5 #6 #8 #10 |
| `frontend/streamlit_app/pages/5_系統管理.py` | line 88 `expanded=False` → `expanded=True` + audit log limit 改 50 + settings expander 預設 collapsed + DELETE user button（P1 #11） | #2 AC-5 #11 |
| `frontend/streamlit_app/Home.py`（再次）+ `pages/1_儀表板.py`（再次） | role-based Demo Banner（依角色顯示動線） | #7 |

**BE 完全不動**（北極星：禁動 schema / perm / endpoint）。

### 3.2 新抽取的 helpers（4 個）

| Helper | 位置 | 簽名 | 用途 |
|---|---|---|---|
| `render_role_matrix(current_role: str) -> None` | `frontend/streamlit_app/auth.py`（append at line 91+） | 渲染 13 行 × 3 角色 markdown table，當前角色欄 bold highlight | Story #2 |
| `render_demo_banner(current_role: str) -> None` | `frontend/streamlit_app/auth.py`（同上） | 依角色 `st.info()` 顯示建議 demo 動線 | Story #7 |
| `fetch_dynamic_thresholds() -> dict` | `frontend/streamlit_app/pages/4_即時監控.py`（local @st.cache_data(ttl=30)） | 打 `/admin/settings` 拿動態閾值，403 fallback 到 hardcode | Story #5 |
| `_mock_anomaly_snapshot() -> dict` | `frontend/streamlit_app/pages/4_即時監控.py`（local） | 構造對齊 `RealtimeSnapshotResponse` v2 schema 的 fake snapshot 塞 buffer | Story #4 |

### 3.3 FE/BE 接觸面（已存在 endpoint，不新增）

| FE 動作 | 呼叫 endpoint | BE 守衛 | Story |
|---|---|---|---|
| Home 試用帳號按鈕 | POST `/auth/login` + GET `/auth/me`（既有） | public + AnyRole | #1 |
| 儀表板載入 | GET `/realtime/history?seconds=60` + `/analytics/unified-summary` + `/data`（既有） | AnyRole | #2 #9 |
| 即時監控啟動 | GET `/realtime/history?seconds=60`（既有）+ WS `/ws/realtime`（既有）+ **GET `/admin/settings`（新呼叫）** | AnyRole + **AdminOnly（VA-9 BLOCKER）** | #5 |
| 即時監控觸發異常 | **不打 BE**（FE-only mock） | — | #4 |
| 系統管理 audit log 改 limit | GET `/admin/logs?size=50`（既有 size param） | AdminOnly | #11 |
| 系統管理 DELETE user | DELETE `/users/{id}`（既有，FE 未呼叫） | AdminOnly | #11 |

### 3.4 與 BE 的合約（schema 對齊 — 端對端資料流規則 5/23 嚴令）

**核心 schema：`RealtimeSnapshotResponse` v2**（`backend/app/schemas/realtime.py:22-35`）

```python
{
  "schema_version": "v2",      # Literal["v2"]
  "ts": "2026-05-26T10:33:21Z",  # datetime → ISO8601 + Z（UTC）
  "temperature": 25.5,         # float | None
  "humidity": 60.0,
  "pressure": 1013.25,
  "voltage": 12.0,
  "cpu_usage": 45.0,
  "anomaly_flags": {"temperature": False, ...},  # dict[str, bool]
  "source": "simulator"        # str
}
```

**Story #4 mock anomaly schema 必對齊**（VA-8 信心 2 / 風險 5 → BLOCKER 檢查點）：

| 欄位 | BE schema | FE mock 必填 | 來源 |
|---|---|---|---|
| schema_version | `Literal["v2"]` | `"v2"` 字串 | `realtime.py:25` |
| ts | `datetime`（serialize 成 ISO8601 + Z） | `datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")` | `realtime.py:26` + ws_client.py:122 驗 schema_version |
| 5 metric | `float \| None` | 全填 float（避免 None 觸發 plotly NaN） | `realtime.py:27-31` |
| anomaly_flags | `dict[str, bool]` | 至少 1 個 True，5 metric keys 全列 | `realtime.py:32` + 4_即時監控.py:235-238 |
| source | `str` | `"mock"`（用以區分 simulator vs mock，方便 audit） | `realtime.py:33` |

**ws_client.py:122 驗 schema_version 鐵律**：mock snapshot 必含 `"schema_version": "v2"` 否則 line 124 `logger.warning("ws: 收到非 v2 payload，忽略")` 直接丟掉。Story #4 `_mock_anomaly_snapshot()` 必 hardcode 此欄位。

---

## Section 4: Story-by-Story 技術設計（12 個 story 逐一展開）

### Story #1 — Home 試用帳號一鍵帶入

**改動檔案**：`frontend/streamlit_app/Home.py:23` 之前插入

**核心技術選擇**：
- `st.expander("試用帳號（Demo 用）", expanded=True)` 列三組 admin/user/viewer email + 密碼明文
- 三顆 `st.button` `key="login_as_{role}"`，on click → 寫 `st.session_state["prefill_email"]` + `prefill_password"]` → `st.rerun()`
- 在 form 內 line 29-30 `text_input` 加 `value=st.session_state.get("prefill_email", "")` 預填
- **降級方案**（VA-17 信心 2 / 風險 4）：若 Streamlit 1.39 不能 programmatic submit form，FE 顯示「已帶入帳密，請按下方『登入』」snackbar（2-click），仍滿足 Story AC-2「等同按下登入」實質

**端對端資料流（5 段）**：

| 段 | 內容 |
|---|---|
| FE 送 | POST `/auth/login` body `{"email": "admin@example.com", "password": "admin123"}`（從 expander 預填到 form 後送出） |
| BE 收 | `LoginRequest` schema（已移除 8 字元 validator，round 1 fix），驗 password hash |
| DB 存 | （只讀）`users` table seed user（alembic 0002 seed admin/user/viewer 三角色） |
| BE 回 | `{"access_token": "<jwt>", "token_type": "bearer"}` + 後續 GET `/auth/me` 回 user dict（id/email/role/display_name/is_active） |
| FE 顯示 | `auth.py:37,51` 寫 `st.session_state["token"]` + `["user"]` → `st.switch_page("pages/1_儀表板.py")` |

**依賴鏈**：無（Sprint 1 最先做）

**驗證方法**：
- **pytest**：無新測試（不動 BE）
- **Chrome MCP**：截 Home 頁 → 看 expander 是否預設展開 → 點「以 Viewer 登入」→ 截下一頁是否到 Dashboard 且右上角顯示 `角色：viewer`

**退化路徑**：
- VA-17 失敗 → 2-click 帶入（仍 ROI 高）
- expander 跟註冊 tab 衝突 → expander 放在 `st.tabs` 之前（公共區）

**引用**：H-1 / VA-1 / VA-16 / VA-17 / E-01-E-02 / pm-strategy §4.2 方案 C

---

### Story #2 — 儀表板角色權限矩陣固定卡片

**改動檔案**：
- `frontend/streamlit_app/auth.py:91+` 新增 `render_role_matrix(current_role: str)` helper（pure function，無 side effect）
- `frontend/streamlit_app/pages/1_儀表板.py:41` `st.markdown("---")` 之後、line 43 `# ── D2-4 System status header ───` 之前插入 `with st.container(border=True): render_role_matrix(role)`
- `frontend/streamlit_app/pages/5_系統管理.py:88` `expanded=False` → `expanded=True`（不刪除既有，預設展開）

**核心技術選擇**：
- `render_role_matrix` 內部：
  ```
  st.markdown(f"**您目前的角色：{role}**（{中文角色名}）")
  st.markdown(<13 行 markdown table，當前角色欄用 **粗體 ✓** 標記>)
  ```
- 高亮方式：用 markdown `**✓**` bold 不用 HTML `<td style="background:#fff3cd">`（VA-13 信心 3，HTML 在 Streamlit 1.39 unsafe_allow_html=True 仍有 sanitize 風險）→ 直接走 fallback VA-24 markdown bold

**端對端資料流（5 段）**：

| 段 | 內容 |
|---|---|
| FE 送 | 無（純前端渲染，無 API call） |
| BE 收 | — |
| DB 存 | — |
| BE 回 | — |
| FE 顯示 | `render_role_matrix(role)` 讀 `session_state["user"]["role"]`（已登入時必存在），渲染 markdown table |

**依賴鏈**：無 helper dependency；Story #2 helper 抽出後 Story #7（Demo Banner）也用同檔案

**驗證方法**：
- **Chrome MCP**：3 角色分別登入 → 截 Dashboard → 看 (a) matrix 卡片是否在 status header 之上 (b) 當前角色欄是否 bold ✓ (c) status header + 4 metric cards 仍正常 layout 無被遮
- **手動**：admin 進系統管理頁 → 看角色 expander 是否預設展開

**退化路徑**：
- 卡片高度過長破壞 viewport → 把 markdown table 包進 `st.expander("角色權限說明", expanded=True)`

**引用**：P0-1 / D-1 / VA-2/3/4/12/13/24 / E-03/E-10 / pm-strategy §4.3 推薦組合

---

### Story #3 — 5 頁 Onboarding Micro-copy

**改動檔案**（5 個 page，每頁 1 段 `st.caption`）：

| File | 插入位置 | caption 內容（≤ 80 字） |
|---|---|---|
| `pages/1_儀表板.py:42` | `st.markdown("---")` 之前 | `總覽系統健康與最近資料。上方為角色權限說明、系統狀態、合計統計，下方為最近 10 筆資料分頁顯示。` |
| `pages/2_資料管理.py:52` | `st.markdown("---")` 之前 | `管理錄入資料：可篩選、分頁、直接點格子編輯（admin / user），或於下方批量匯入 CSV / JSON。Viewer 為唯讀。` |
| `pages/3_分析報表.py:55` | `st.markdown("---")` 之前 | `查詢即時 + 錄入資料的統計摘要、時間趨勢、類別分布，可選資料來源 (即時 / 錄入 / 兩者)，並匯出 Excel。` |
| `pages/4_即時監控.py:113` | `st.markdown("---")` 之前 | `每秒推送 WebSocket wide snapshot，5 大指標 (溫度 / 濕度 / 氣壓 / 電壓 / CPU) 即時呈現，紅色為超閾值異常。下方可手動觸發示範異常。` |
| `pages/5_系統管理.py:69` | `st.markdown("---")` 之前 | `Admin 限定：使用者管理 / Audit log / DB 狀態 / 即時資料歷史 / 動態系統設定 (閾值即時生效)。` |

**核心技術選擇**：純 `st.caption()`，禁用 HTML / markdown 修飾（避免破版）

**端對端資料流（5 段）**：純靜態渲染，無資料流

**依賴鏈**：無（可派 5 個 sub-agent 並行）

**驗證方法**：
- **grep**：`rg "st\.caption" frontend/streamlit_app/pages/` 確認 5 頁各 ≥ 1 個 caption 在 `st.title()` 50 行內
- **Chrome MCP**：截 5 頁 × 1 角色 = 5 張，看 caption 是否在 title 下方第一屏

**退化路徑**：caption 太長 → 改 `st.markdown("<small>...</small>", unsafe_allow_html=True)`

**引用**：P0-2 / VA-5/6 / codebase-audit Section 5 #1-#20 / pm-strategy M2

---

### Story #4 — 即時監控 Demo 控制面板（FE-only mock anomaly）

**改動檔案**：`frontend/streamlit_app/pages/4_即時監控.py:145` 之前（在 ctrl_col 之前）插入 `st.container(border=True)` 加 Demo 控制 + line 344-359 Styler 改 try/except 加 logging

**核心技術選擇**：

```
# Pseudocode（spec only，禁寫實 code 進 brief）
with st.container(border=True):
    st.markdown("**Demo 控制**")
    st.caption("FE 模擬模式：不打 BE，直接在 buffer 插入 1 筆對齊 RealtimeSnapshotResponse v2 schema 的假 snapshot")
    if st.button("觸發一次模擬異常", key="trigger_mock_anomaly"):
        fake = _mock_anomaly_snapshot()
        ws_client.push_tick(fake)   # 直接 append 到 deque
        st.toast("已注入模擬異常，下一秒 autorefresh 後可見")
        st.rerun()

def _mock_anomaly_snapshot() -> dict:
    """構造對齊 backend RealtimeSnapshotResponse v2 schema 的 fake snapshot。
    Schema 對齊規則（VA-8 BLOCKER）：
    - schema_version 必為 "v2" （ws_client.py:122 驗）
    - ts 必為 UTC ISO8601 + Z
    - 5 metric 必 float（非 None，避免 plotly NaN）
    - anomaly_flags 全列 5 keys，至少 1 個 True
    - source = "mock"（區分 simulator vs mock 便於日後 audit）
    """
    now = datetime.now(tz=timezone.utc)
    return {
        "schema_version": "v2",
        "ts": now.isoformat().replace("+00:00", "Z"),
        "temperature": 150.0,    # 超 high threshold 100
        "humidity": 50.0,
        "pressure": 1013.25,
        "voltage": 12.0,
        "cpu_usage": 95.0,        # 超 high threshold 90
        "anomaly_flags": {
            "temperature": True,
            "humidity": False,
            "pressure": False,
            "voltage": False,
            "cpu_usage": True,
        },
        "source": "mock",
    }
```

**Styler logging（M5 拆分 b）**：
- line 357 `except Exception:` → `except Exception as exc: logger.warning("styler render failed: %s", exc); st.warning("表格樣式載入失敗，資料內容仍正確")`

**端對端資料流（5 段）**：

| 段 | 內容 |
|---|---|
| FE 送 | **無 API call**（純 FE buffer 操作） |
| BE 收 | — |
| DB 存 | — |
| BE 回 | — |
| FE 顯示 | `ws_client.push_tick(fake)` 把 dict append 到 `RealtimeWSClient._buffer`（deque maxlen=60，line ws_client.py:79）→ 下次 `st_autorefresh(interval=1000)` rerun 後 line 115 `all_ticks = ws_client.get_buffer()` 拿到含 mock 的 buffer → 走 line 117-128 active alerts 偵測 + line 184-197 告警卡 + line 214-264 折線圖 anomaly marker + line 273-359 Styler 淡粉紅 row + 紅字 cell 三層全 fire |

**依賴鏈**：必須先過 VA-8 spike（Phase A.4）+ schema 對齊驗證；Story #6 plotly subplots 改寫 anomaly marker 要在正確 subplot 上 → 必先驗 Story #4

**驗證方法**：
- **pytest**：無新測試（不動 BE）
- **手動**：點「觸發一次模擬異常」→ 下 1-2 秒看 (a) `st.error` 告警 banner fire (b) 告警 metric card 出現「溫度(C) 異常」+ delta (c) 表格最上一筆 row 淡粉紅背景 + 溫度(C) cell 紅字 (d) 折線圖溫度 metric 對應 tick 出現 circle-open red marker
- **Chrome MCP**：trigger 後截圖驗三層 anomaly UX 全 fire

**退化路徑**：
- VA-8 spike 失敗（Styler 不認 mock snapshot）→ 降級為「即時監控頁加 demo 模式 toggle，按下後 hardcode 閾值暫時調超低，讓真實 simulator tick 都觸發異常」
- ws_client.py:122 拒 mock（schema_version 沒對齊）→ 改用 `push_tick` 直接繞過 WS 校驗（push_tick 是 line 77 public method，無 schema 檢查）

**引用**：P0-3 / R-1 / VA-7（信心 3）/ VA-8（信心 2 風險 5 BLOCKER）/ VA-15 / E-06 / pm-strategy M3 / pm-strategy §8 mitigation row 2

---

### Story #5 — 即時監控閾值動態同步（VA-9 BLOCKER 必先驗）

**改動檔案**：`frontend/streamlit_app/pages/4_即時監控.py:55-69` hardcode dict 之後新增 `fetch_dynamic_thresholds()` helper + line 186-189 `high_thr / low_thr / threshold` 改讀 dynamic dict

**核心技術選擇**：

```
@st.cache_data(ttl=30)
def fetch_dynamic_thresholds() -> tuple[dict, dict, bool]:
    """打 /admin/settings 拿動態閾值。
    回傳 (high_dict, low_dict, is_dynamic)。
    403 / 網路失敗 → 回傳 hardcode + False。
    """
    try:
        resp = client.get("/admin/settings")
        if resp.status_code == 200:
            settings = {s["key"]: s["value"] for s in resp.json()}
            # backend app_settings table 預期有 anomaly_threshold_high / low（per-metric 不支援，全 metric 共用）
            high_val = float(settings.get("anomaly_threshold_high", 100.0))
            low_val = float(settings.get("anomaly_threshold_low", 10.0))
            # 套用到 5 metric（per-metric override 留 v4）
            high = {k: high_val for k in _METRIC_KEYS}  # 已在 line 40 定義
            low = {k: low_val for k in _METRIC_KEYS}
            return high, low, True
        elif resp.status_code == 403:
            # VA-9 已驗 viewer/user 會 403 → 降級
            return _METRIC_HIGH_THRESHOLD, _METRIC_LOW_THRESHOLD, False
    except Exception:
        pass
    return _METRIC_HIGH_THRESHOLD, _METRIC_LOW_THRESHOLD, False

# 使用點 line 184 之前
high_thresholds, low_thresholds, is_dynamic = fetch_dynamic_thresholds()
if not is_dynamic and role != "admin":
    st.caption("閾值顯示為預設值（唯讀，僅 Admin 可修改於系統管理 → 系統設定）")
elif not is_dynamic:
    st.warning("無法取得動態閾值，使用預設值（請檢查 BE 連線）")
```

**端對端資料流（5 段）**：

| 段 | 內容 |
|---|---|
| FE 送 | GET `/api/v1/admin/settings` + Authorization header `Bearer <jwt>` |
| BE 收 | `backend/app/api/v1/admin.py:169-177` `list_settings()` 走 `AdminOnly`（**deps.py:60**）→ viewer/user 直接 403 |
| DB 存 | （只讀）`app_settings` table 全 row `SELECT * FROM app_settings ORDER BY key` |
| BE 回 | `list[AppSettingResponse]` JSON：`[{"id": 1, "key": "anomaly_threshold_high", "value": "100.0", "description": "...", "updated_at": "..."}]` |
| FE 顯示 | parse settings → 套到告警卡的 `high_thr / low_thr / threshold` 計算（line 186-189）→ 告警 metric card 顯示「閾值 XX.X」反映新值 |

**VA-9 BLOCKER 驗證**（Phase A.1 必先 curl）：

```
# 取 viewer JWT
curl -X POST <ZEABUR_URL>/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer@example.com","password":"viewer123"}'

# 用 viewer JWT 打 /admin/settings
curl -H "Authorization: Bearer <jwt>" <ZEABUR_URL>/api/v1/admin/settings
# 預期：403（已確認 AdminOnly deps.py:60）
```

**依賴鏈**：VA-9 驗證結果 = Story #5 設計分支點
- 若 200 → fetch_dynamic_thresholds 正常 path
- 若 403（預期） → AC-3 fallback 唯一合規解法（不動 BE 加 endpoint，違反 Q1 拍板）

**驗證方法**：
- **pytest**：無新測試
- **手動**：
  1. Admin 登入系統管理 → 系統設定 → 改 `anomaly_threshold_high` 從 100 → 60
  2. 切到即時監控頁 → 等 30 秒（cache TTL）or 點「清空緩衝區」
  3. 看告警 metric card 的「閾值 60.0」反映新值
- **Chrome MCP**：viewer 登入即時監控 → 截圖看 caption「閾值顯示為預設值（唯讀）」提示
- **curl smoke**：VA-9 端對端

**退化路徑**：見「VA-9 驗證結果分支」

**引用**：R-2 / VA-9（最關鍵 BLOCKER）/ O-P0-1 / A-06 / pm-strategy M3 / `4_即時監控.py:55-69, 184-189` / backend admin.py:169-177

---

### Story #6 — 即時監控折線圖 Small Multiples 重構

**改動檔案**：`frontend/streamlit_app/pages/4_即時監控.py:214-264` 整段 `go.Figure()` 改寫為 `plotly.subplots.make_subplots`

**核心技術選擇**：

```
# Pseudocode
from plotly.subplots import make_subplots

# selected_metrics 從 line 149 multiselect 拿
n_rows = len(selected_metrics) if selected_metrics else 5

fig_rt = make_subplots(
    rows=n_rows,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.04,
    subplot_titles=[_METRIC_ZH.get(m, m) for m in selected_metrics],
)

for idx, metric_key in enumerate(selected_metrics, start=1):
    if metric_key not in df_rt.columns:
        continue
    df_rt[f"{metric_key}_float"] = pd.to_numeric(df_rt[metric_key], errors="coerce")
    # 正常折線
    fig_rt.add_trace(
        go.Scatter(
            x=df_rt["ts_tw"],
            y=df_rt[f"{metric_key}_float"],
            mode="lines",
            name=_METRIC_ZH.get(metric_key, metric_key),
            line={"color": _METRIC_COLORS.get(metric_key, "gray"), "width": 2},
            showlegend=False,  # subplot title 已顯示
        ),
        row=idx, col=1,
    )
    # 異常 marker（必在對應 row）
    anom_mask = df_rt.apply(lambda r, mk=metric_key: bool(r.get("anomaly_flags", {}).get(mk, False)), axis=1)
    anom_df = df_rt[anom_mask]
    if not anom_df.empty:
        fig_rt.add_trace(
            go.Scatter(
                x=anom_df["ts_tw"],
                y=anom_df[f"{metric_key}_float"],
                mode="markers",
                marker={"color": "red", "size": 12, "symbol": "circle-open", "line": {"width": 2, "color": "red"}},
                showlegend=False,
            ),
            row=idx, col=1,
        )

fig_rt.update_layout(
    height=180 * n_rows,  # 每 subplot 180px → 5 subplot ~900px
    margin={"l": 40, "r": 20, "t": 60, "b": 40},
    uirevision="realtime_chart",  # 防 autorefresh hover 閃爍
    showlegend=False,
)
fig_rt.update_xaxes(title_text="時間（台北）", row=n_rows, col=1)  # 只最底 subplot 標 x 軸
```

**multiselect 預設改為 2-3 條**（VA-19 防超單屏）：
- line 152 `default=_METRIC_KEYS` → `default=["temperature", "pressure", "cpu_usage"]`（最典型對比：溫度/氣壓量級差 + cpu）

**G2 fallback**（Q5 拍板：VA-10 失敗用 secondary y-axis）：
- 若 small multiples spike 失敗 → 改用 `make_subplots(specs=[[{"secondary_y": True}]])` 只 split pressure 到 secondary y-axis，其他 4 個共軸

**端對端資料流（5 段）**：

| 段 | 內容 |
|---|---|
| FE 送 | （續用既有）GET `/realtime/history?seconds=60` + WS `/ws/realtime` |
| BE 收 | realtime.py:18-35 `realtime_history()` 走 AnyRole |
| DB 存 | （只讀）`realtime_metrics_wide` table 最近 60 秒 row |
| BE 回 | `RealtimeHistoryResponse` JSON：`{"snapshots": [...v2 snapshot...], "count": N}` |
| FE 顯示 | line 115 `all_ticks = ws_client.get_buffer()` → line 207 `df_rt = pd.DataFrame(all_ticks)` → 5 個 subplot 各自獨立 Y 軸 → 評審能個別判讀 voltage（量級 ±5V）vs 氣壓 1013 |

**依賴鏈**：必須在 Story #4 完成後驗 anomaly marker 位置（mock anomaly 觸發後看 marker 是否在正確的 subplot 上）；Story #5 動態閾值同步依此後

**驗證方法**：
- **手動**：點 Story #4「觸發模擬異常」（溫度 + cpu_usage 設為 True）→ 看溫度 subplot 上有 red marker、cpu_usage subplot 上有 red marker、其他 3 個 subplot 無 marker
- **Chrome MCP**：1080p 截圖看 5 個 subplot（or multiselect 預設 3 個）是否完整顯示在 viewport 內

**退化路徑**：VA-10 spike 失敗（Phase A.5）→ 走 G2 fallback secondary y-axis

**引用**：R-1（致命傷 Top 15 #1）/ VA-10 / VA-11 / VA-19 / E-06 / pm-strategy §6.3 反指標 #5 / pm-strategy Q5 G2

---

### Story #7 — 角色 Demo Banner 與建議動線

**改動檔案**：
- `frontend/streamlit_app/auth.py:91+` 新增 `render_demo_banner(role: str)` helper
- `frontend/streamlit_app/pages/1_儀表板.py` 緊接 Story #2 矩陣卡片之後（line 41 後新增區塊）插入 `render_demo_banner(role)`

**核心技術選擇**：

```
def render_demo_banner(role: str) -> None:
    """依角色顯示 st.info 建議 demo 動線。
    可勾選「不再顯示」存 session_state[f"hide_banner_{role}"]。
    """
    if st.session_state.get(f"hide_banner_{role}", False):
        return
    routes = {
        "viewer": "儀表板 → 即時監控 → 分析報表",
        "user": "儀表板 → 資料管理 (上傳 CSV) → 分析報表 → 即時監控",
        "admin": "儀表板 → 即時監控 (試觸發異常) → 系統管理 (改閾值 / 看 Audit log) → 分析報表 (匯出 Excel)",
    }
    role_zh = {"admin": "Admin（系統管理員）", "user": "User（一般使用者）", "viewer": "Viewer（瀏覽者）"}
    st.info(f"**建議 {role_zh.get(role, role)} demo 動線：** {routes.get(role, '儀表板 → 即時監控')}")
    # 不再顯示 checkbox（optional，session 級）
    if st.checkbox("不再顯示此提示（本次 session）", key=f"hide_banner_check_{role}"):
        st.session_state[f"hide_banner_{role}"] = True
```

**端對端資料流（5 段）**：純前端，無資料流

**依賴鏈**：依 Story #2（共用 `auth.py` helper 抽取點）

**驗證方法**：
- **Chrome MCP**：3 角色登入 Dashboard 各截圖 → 看 banner 文字反映角色

**退化路徑**：banner 被誤解為強迫導覽 → 用 `st.info` 而非 modal（VA-22 設計選擇）

**引用**：VA-22 / VA-23 / VA-25 / E-03/E-10/V-02 / pm-strategy M4

---

### Story #8 — Delta Color 反語意修復 + Pandas Styler 穩健化

**改動檔案**：
- `frontend/streamlit_app/pages/4_即時監控.py:196` `delta_color="inverse"` → `delta_color="normal"`
- `frontend/streamlit_app/pages/1_儀表板.py:154` 同樣 audit（`col4.metric` `delta_color="inverse"` 但沒設 delta 值不會觸發顏色 → 改 normal 也無視覺差）
- `frontend/streamlit_app/pages/4_即時監控.py:357-359` Styler except 加 logging（M5 拆分 b，時間箱壓力大可砍）

**核心技術選擇**：

```
# 拆 (a) — 30 min — 必做
# 4_即時監控.py:196
st.metric(
    label=f"{_METRIC_ZH.get(metric_key, metric_key)} 異常",
    value=f"{value:.2f}",
    delta=f"{sign}{delta_val:.2f}（閾值 {threshold}）",
    delta_color="normal",  # 從 inverse 改 normal：+50 紅色（異常）/ -50 綠色（恢復）符合直覺
)

# 拆 (b) — 30 min — 時間箱壓力大可砍
# 4_即時監控.py:357 except 改
import logging
logger = logging.getLogger(__name__)
# line 344-359
try:
    styled = df_visible.style.apply(_style_row, axis=1)
    ...
    st.dataframe(styled, use_container_width=True, hide_index=True)
except Exception as exc:
    logger.warning("即時監控 Styler 渲染失敗：%s", exc, exc_info=True)
    st.warning("表格樣式載入失敗（資料正確，僅顏色降級）")
    st.dataframe(df_visible, use_container_width=True, hide_index=True)
```

**grep audit 所有 `delta_color="inverse"`**（VA-14 信心 4 / 風險 2）：

```
rg 'delta_color\s*=\s*"inverse"' frontend/streamlit_app/
```

逐處決策（保留的有 comment 說明）。

**端對端資料流（5 段）**：純前端

**依賴鏈**：無

**驗證方法**：
- **grep**：`rg 'delta_color="inverse"' frontend/` 確認 audit
- **手動**：觸發 Story #4 mock anomaly → 看告警 metric card delta 顯示紅色（非綠色）
- **pytest**：M5 不影響 BE，但 round 1 smoke test 仍跑

**退化路徑**：M5 (b) Styler logging 砍 → 保持既有 silent fallback（pm-strategy Q4 拍板）

**引用**：P1-1 / P1-2 / VA-14 / VA-15 / A-03 / pm-strategy M5 / pm-strategy §6.3 反指標 #4

---

### Story #9 — 儀表板 Metric Cards 品質指標化

**改動檔案**：`frontend/streamlit_app/pages/1_儀表板.py:147-155` 4 個 metric cards

**核心技術選擇**：
- col4 從「異常筆數（合計）」改為「**今日異常率**」+ delta vs 昨日
- 異常率 = `combined.get("anomaly_count", 0) / combined.get("total", 1) * 100`
- delta：FE 自算（從 unified-summary 拉今日 + 昨日各一次）
- 加 `help=` 參數所有 4 個 metric

```
col4.metric(
    label="今日異常率",
    value=f"{(combined.get('anomaly_count', 0) / max(combined.get('total', 1), 1)) * 100:.3f}%",
    delta=f"{delta_pct:+.3f}% vs 昨日",
    delta_color="normal",  # +0.005% 紅色 / -0.005% 綠色
    help="過去 24 小時異常筆數 / 總筆數，含即時 + 錄入",
)
```

**端對端資料流（5 段）**：

| 段 | 內容 |
|---|---|
| FE 送 | GET `/analytics/unified-summary?date_from=<今日>&date_to=<今日>` + 第二次 `date_from=<昨日>&date_to=<昨日>` |
| BE 收 | `analytics.py` get_unified_summary（既有 endpoint） |
| DB 存 | （只讀）combined query realtime_metrics_wide + data_records |
| BE 回 | `{"combined": {"total": N, "anomaly_count": M, ...}, "realtime": {...}, "records": {...}}` |
| FE 顯示 | metric card 顯示「異常率 0.014% / vs 昨日 +0.003%」 |

**依賴鏈**：無

**驗證方法**：
- **手動**：開 Dashboard 看 col4 是否顯示百分比 + delta
- **Chrome MCP**：截 Viewer Dashboard 看是否一眼看出「品質」

**退化路徑**：unified-summary 不分今日/昨日 → FE fallback 顯示「累計異常率」無 delta

**引用**：D-1 / Top 15 friction #4 / V-01/V-05/E-03

---

### Story #10 — 即時告警卡片嚴重度視覺化

**改動檔案**：`frontend/streamlit_app/pages/4_即時監控.py:184-197` 告警卡 cols

**核心技術選擇**：
- `st.columns(min(len(...), 3))`（從 5 改 3，VA-24 row 1 max 3 cards）
- > 3 個告警走 list view（`st.markdown` 表格）
- metric 名稱用 `_METRIC_ZH` 已有 dict（line 41-47），不需新 mapping

**端對端資料流（5 段）**：純前端

**依賴鏈**：依 Story #4 mock anomaly 才能驗 5 metric 全異常情境

**驗證方法**：
- **手動**：模擬 5 metric 全異常（mock 多次觸發）→ 看是否切換為 list view

**退化路徑**：list view 切換邏輯複雜 → 保留 5 cols 全擠（接受 UX 降級）

**引用**：R-5 / Top 15 #6 / A-03

---

### Story #11 — 系統管理頁面可用性修補（4 個 P1）

**改動檔案**：`frontend/streamlit_app/pages/5_系統管理.py`

- **AC-1 audit log limit**：line 309 附近的 `params["limit"] = 10` → `50`；分頁 size 不變
- **AC-2 settings expander**：line 558-639 每個 setting `expanded=True` → `expanded=False`，頂部加 `st.button("展開全部設定")` 切換 `st.session_state["expand_all_settings"]`
- **AC-3 DELETE user button**：line 158 dataframe 之後新增「刪除使用者」selectbox + button，呼叫 `client.delete(f"/users/{uid}")`；FE disable 「刪除自己」按鈕（`current_user_id != target_id`）
- **AC-4**：Story #2 已包含（line 88 `expanded=True`）

**端對端資料流（DELETE user）**：

| 段 | 內容 |
|---|---|
| FE 送 | DELETE `/api/v1/users/{id}` + Authorization JWT (admin) |
| BE 收 | `backend/app/api/v1/users.py:93-106` `delete_user` 走 `AdminOnly` |
| DB 存 | `users` table DELETE row + audit_log INSERT `action="delete_user"` |
| BE 回 | `204 No Content` |
| FE 顯示 | `st.success(f"已刪除使用者 {email}")` + `st.cache_data.clear()` + `st.rerun()` |

**依賴鏈**：無（與 Story #2 不衝突）

**驗證方法**：
- **pytest**：跑 `tests/test_users_admin.py` 確認 DELETE 不 regress
- **手動**：admin 登入 → 系統管理 → 選一個 viewer 角色 user 刪除 → 看是否消失 + audit log 多一筆

**退化路徑**：DELETE 失敗（404 已被他人刪）→ FE 捕捉顯示「此用戶已被刪除」

**引用**：S-3/S-4/S-5/S-7 / codebase-audit Section 3 5.3 / E-07

---

### Story #12 — 分析報表時間趨勢 source=realtime 改線圖（P2）

**改動檔案**：`frontend/streamlit_app/pages/3_分析報表.py:253-289` 條件分支改寫

**核心技術選擇**：
- realtime source 改打 `/realtime/history?seconds=86400`（最近 24 小時 wide rows）
- FE 用 pandas `df.set_index('ts').resample(bucket).mean()` 做 hour/day bucket
- 畫 `go.Scatter` 折線圖（與 records source 一致）

**端對端資料流（5 段）**：

| 段 | 內容 |
|---|---|
| FE 送 | GET `/realtime/history?seconds=86400` |
| BE 收 | realtime.py:18-35 AnyRole（但 max 3600，FE 需迭代多次 or 接受 1 小時 window） |
| DB 存 | （只讀）realtime_metrics_wide |
| BE 回 | RealtimeHistoryResponse |
| FE 顯示 | 折線圖 |

**注意 BE 限制**：realtime.py:22 `seconds: int = Query(60, ge=1, le=3600)` max 3600 = 1 hr，FE 無法直接拿 24h；可改為「最近 1 小時 realtime trend」+ caption 說明限制

**依賴鏈**：無

**驗證方法**：手動切 source=realtime 看是否仍是折線圖

**退化路徑**：P2 砍掉，AC-6 接受「source=realtime 是 bar chart」

**引用**：A-2 / VA-32 / AC-6

---

## Section 5: 風險與 Mitigation

### 5.1 阻塞性風險（驗失敗整個 redesign 卡住）

| 風險 ID | 風險陳述 | 防呆機制 | Phase | Owner |
|---|---|---|---|---|
| **R-BLOCK-1** | VA-9 `/admin/settings` viewer/user 403 → Story #5 設計需走 fallback | Phase A.1 curl 先驗（5 min）；403 走 AC-3 路徑（FE caption「閾值唯讀」） | A.1 | main |
| **R-BLOCK-2** | VA-8 mock anomaly schema 對齊失敗 → Story #4 三層 UX 都不 fire | Phase A.4 spike：印 mock dict diff `/realtime/history` 真實 response | A.4 | frontend-engineer |
| **R-BLOCK-3** | VA-10 plotly subplots 破壞 anomaly marker 位置 → Story #6 退化 G2 | Phase A.5 spike：60 秒模擬資料看 marker 是否在正確 subplot | A.5 | frontend-engineer |
| **R-BLOCK-4** | VA-20 Zeabur webhook 卡 → 評審看不到新 commit | Phase A.2 push trivial commit 5 min 驗；卡用 `$ZEABUR_API_TOKEN` redeployService 自助 | A.2 | main |
| **R-BLOCK-5** | VA-26 v2 33 perm tests regress → demo 環境 5XX | 每 phase 後跑 `pytest -v` 不能紅；F.1 全綠驗收 | F.1 | test-automator |
| **R-BLOCK-6** | VA-27 round 1 8 個 P0 bug 又出現 | F.1 跑 round 1 smoke test 8 個 curl | F.1 | test-automator |

### 5.2 重要風險（影響範圍但可吸收）

| 風險 | 防呆 |
|---|---|
| VA-17 programmatic submit 不可行 | Story #1 降級 2-click，仍滿足 AC |
| VA-11 5 subplots 超單屏 | Story #6 multiselect 預設 3 條 |
| VA-13 HTML 高亮被 sanitize | Story #2 直接走 markdown `**✓**` bold（不嘗試 HTML） |
| VA-21 / VA-37 M3 工時 overrun | Phase C 每 sub-task 計時，過 2 hr 完成不到 50% Discord 升級懷特 |
| `delta_color` 修補影響其他頁面 metric | Story #8 先 grep 全 repo audit |
| Chrome MCP 不繼承 sub-agent | F.2 截圖驗收必 main session 跑 |
| Sub-agent 派完不驗整合（規則 F 5/21） | 每 sub-agent 完成後派獨立驗證 sub-agent（feedback_separate_implement_verify_agents 5/23） |
| 視覺驗收靠 pytest 綠誤判（5/25 P1 教訓） | F.4 ui-ux-tester 必派 Chrome MCP 截圖 + Read 圖檢視（feedback_v6_full_closed_loop） |

### 5.3 v2 round 1 8 個 P0 bug regress 防呆 smoke test 清單

| Bug ID | curl 驗 | 過關條件 |
|---|---|---|
| BUG #1 | POST `/auth/login` `{"email":"viewer@example.com","password":"viewer123"}` | 200 + access_token（短密碼能登） |
| BUG #5 | api_client fallback URL 不為 localhost | `rg "BACKEND_URL" frontend/streamlit_app/api_client.py:12-14` 確認 Zeabur URL |
| BUG #6 | WS path `/ws/realtime` 不走 `/api/v1` | `rg "ws/realtime" frontend/streamlit_app/ws_client.py:30,32` 確認無 `/api/v1` |
| D-BLOCK-1 | data 篩選用 date_input + time_input（不用 datetime_input） | `rg "st.datetime_input" frontend/` 必 0 |
| D-BLOCK-2 | Realtime 走 WS + REST `/realtime/history` 預載 | `rg "run_ws_in_background" frontend/streamlit_app/pages/4_即時監控.py:97` 確認 |
| D-BLOCK-3 | Analytics unified-summary key 對齊 `combined/realtime/records` | `rg "unified.get\(\"combined\"\)" frontend/` 確認 |
| D-HIGH-2 | 日誌 metadata 改讀 `meta` | `rg '\.get\("meta"' frontend/streamlit_app/pages/5_系統管理.py` 確認 |
| D-HIGH-5 | Realtime category hardcode 對齊 simulator | `rg "_METRIC_KEYS\s*=" frontend/streamlit_app/pages/4_即時監控.py:40` 確認 5 metric 對齊 |

---

## Section 6: 部署計畫

### 6.1 Phase 順序（依 Q3 拍板）

```
Phase A (Hour 0 - 1.5)：5 假設先驗（VA-9 / VA-20 / VA-1+16+17 / VA-8+7 / VA-10）
Phase B (Hour 1.5 - 4)：Sprint 1 Foundation（Story #1 #2 #3 並行）
Phase C (Hour 4 - 11)：Sprint 2 Core UX（Story #4 → #6 → #5 + #7 + #8）
Phase D (Hour 11 - 14)：Sprint 3 Polish（Story #9 #10 #11 並行）
Phase E (Hour 14 - 16)：灰色地帶 G2（只有 VA-10 spike 失敗才做）
Phase F (Hour 16 - 22)：驗收（F.1 pytest / F.2 Chrome MCP 15 張 / F.3 demo script A/B/C / F.4 ui-ux-tester / F.5 implementation-validator）
Phase G (Hour 22 - 24)：commit + push DennisPai + Zeabur 部署驗 + 重 test
```

### 6.2 Zeabur webhook 風險與防呆

依 `reference_zeabur_api_self_service`：

```
# 動工後第 1 個 commit（VA-20 trivial commit）push 完
sleep 60  # 等 webhook
# 查 Zeabur deployment
ZEABUR_API_TOKEN=<token> curl -X POST https://api.zeabur.com/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ZEABUR_API_TOKEN" \
  -d '{"query":"query { project(_id:\"<pid>\") { services { latestDeployment { status } } } }"}'

# 若 status != RUNNING 且 webhook 沒 fire → 自助 redeploy
ZEABUR_API_TOKEN=<token> curl -X POST https://api.zeabur.com/graphql \
  -H "Authorization: Bearer $ZEABUR_API_TOKEN" \
  -d '{"query":"mutation { redeployService(_id:\"<sid>\") { _id } }"}'
```

push 後 max 10 min wait，超時 Discord 升級懷特。

### 6.3 pytest baseline（不能 regress）

- v2 既有 33 perm tests + 24 endpoint tests 必全綠
- 每 phase 後跑 `cd backend && pytest -v --cov=app`
- 若有任何測試紅 → 立刻 `git diff` 看哪個改動破了；rollback 或修正
- 不允許「pytest 綠 = done」（5/25 Wiwynn P1 教訓，feedback_v6_full_closed_loop）

### 6.4 Chrome MCP 截圖驗收標準（必 main session 跑）

15 張截圖 = 5 頁 × 3 角色：

| 頁面 \ 角色 | Viewer | User | Admin |
|---|---|---|---|
| Home（未登入） | × 1（試用帳號 expander）| — | — |
| Dashboard | ✓ 含矩陣 + Demo Banner + 4 metric cards（含異常率） | ✓ | ✓ |
| 資料管理 | ✓（唯讀）| ✓（inline edit） | ✓（全功能） |
| 分析報表 | ✓ | ✓ | ✓ |
| 即時監控 | ✓（small multiples + caption「閾值唯讀」） | ✓ | ✓（含 Demo 控制 + 動態閾值） |
| 系統管理 | × stop | × stop | ✓（5 tab + 矩陣展開 + DELETE button） |

合格條件：
- 每張截圖必由 sub-agent Read（用 Read tool 看圖）+ 描述「我看到什麼」
- 缺項或視覺破洞（5 metric 壓一團 / 矩陣藏起 / caption 漏）→ 必 escalate

---

## Section 7: 完成定義（DOD）— 7 條全綠才算 done

1. **12 個 story 的 AC 全綠**（user-stories.md Section 2 每個 story 的 AC 逐條驗）
2. **pytest 全綠**（不 regress 33 perm tests + round 1 8 個 P0 smoke test）
3. **80-120 條 validation checklist 100% 綠**（Phase F.5 implementation-validator 產出）
4. **Chrome MCP 15 張截圖合格**（5 頁 × 3 角色，sub-agent Read 描述全 pass）
5. **demo script A/B/C 跑通**（user-stories.md Section 5 三個 script 逐步驗）
6. **ui-ux-tester sub-agent 整體驗收通過**（v6.1 sub-agent，必 main session 派 + Chrome MCP）
7. **Zeabur 部署成功 + 3 角色生產環境 smoke test 通過**（push 後 max 10 min wait）

### 7.1 Out of Scope（v3 不做，明列 14 項，禁 scope creep）

從 user-stories.md Appendix 完整繼承：

1. DELETE user UI（G1 — Q5 拍板留 v4，但 Story #11 已包含 P1 路徑）
2. CSV upload preview / dry-run（ux-research Top 10 #4）
3. Viewer 公開唯讀快照連結
4. 申請提權表單
5. Plotly `displayModeBar=False` 截圖友善
6. 系統設定單一 form 提交（S-7）
7. Inline edit dirty state warning（DM-4）
8. Excel 單步下載（A-5）
9. 完整 DB pool 顏色語意系統
10. 角色 chip badge sidebar（方案 B）
11. Audit log timeline UI
12. 登出後 JWT 無效化（需動 BE）
13. 國際化 i18n
14. Streamlit → 其他 framework 替換

### 7.2 接受性假設繼承（10 條，動工前不修，出狀況再說）

assumption-mapping.md AC-1 ~ AC-10 全 inherit（見 §2.3）

---

## Section 8: 附錄 — Sub-agent 派遣指引（每 phase 用）

每派 sub-agent 必含：

```
你是 <agent role> sub-agent。

**MUST 動作型指令**：
1. Re-Read /home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/openspec/changes/redesign-v3-uxfix-2026-05-26/design.md（完整 600+ 行禁簡化）
2. Re-Read 對應 story file:line（design.md Section 4 Story #N 改動檔案清單）
3. Re-Read assumption-mapping.md Section 4 對應 VA-x（若 VA-9 / VA-10 spike 失敗有退化路徑）
4. 動工
5. 完成後印「STORY #N DONE」並列 (a) 改動 file:line (b) 跑 pytest 結果 (c) 自測 checklist

**禁 simplification**：CLAUDE.md 4/10 嚴令，禁簡化 SOP / 禁 batch brief。
**禁繼承假設**：不准假裝 endpoint 改了不用驗，必 curl smoke test。
**端對端鐵律**：5/23 嚴令，FE 改完必驗端對端資料流（FE 送 → BE 收 → BE 回 → FE 顯示）對齊 design.md Story #N 5 段對照表。
```

---

DESIGN DONE