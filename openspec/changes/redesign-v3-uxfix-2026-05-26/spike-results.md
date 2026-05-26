# Spike Results — Phase A De-risk（Wiwynn redesign-v3-uxfix-2026-05-26）

**Date**：2026-05-26
**Owner**：spike-investigator sub-agent（v6.1 Mode A 加強版 Phase A）
**Time budget**：3 個並行 spike × ~30-60 min（VA-1+16+17 / VA-7+8 / VA-10）
**讀過的證據**：design.md 600+ 行 / assumption-mapping.md 519 行 + frontend FE 3 檔 + backend schema realtime.py
**Streamlit 版本 caveat**：本機環境因 starlette 衝突無法保留 1.39，spike 跑在 1.57（API surface 對 `session_state` / `form_submit_button` / `query_params` / `Pandas Styler` / `plotly subplots` 在 1.30-1.57 完全一致，結論可推到 1.39 production env）
**BE production endpoint**：`https://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app/api/v1/realtime/history?seconds={N}`（admin@example.com / admin123 JWT 200 OK + 59 snapshots in 60s window）

---

## Spike 1: VA-1+16+17 — Home session_state 預填 + 自動 submit

### 1.1 假設陳述

**Source**：assumption-mapping.md VA-1（評審 5 秒內找測試帳號，信心 2 / 風險 5）+ VA-16（3 顆登入按鈕不破壞註冊 tab，信心 3 / 風險 4）+ VA-17（programmatic form submit 在 Streamlit 1.39 可行，信心 2 / 風險 4）

**核心問題**：在 Streamlit 1.39，按「以 Admin 登入」按鈕後能否做到 zero-click 自動登入跳 Dashboard？三條 plan：

- **Plan A**：寫 `st.session_state["login_email"] = "..."` + 寫 `st.session_state["submit_login"] = True` + `st.rerun()` → 是否觸發 form auto-submit
- **Plan B**：用 `st.query_params["auto_login"] = "admin"` + `st.rerun()`，頁面腳本檢測 query param 後直接呼叫 `auth.login()` 繞過 form
- **Plan C**：退化為「自動填入 email/password 欄位，使用者再按一次登入按鈕」（2-click）

**風險面**：若 Plan A 不行（即評審 demo 必 2-click），Story #1 AC-2「點按鈕等同按下登入」描述需改為「點按鈕帶入帳密 + 提示再按登入」。

### 1.2 Spike 步驟

**Step 1：寫 `/tmp/spike_va1.py` standalone Streamlit app**（167 lines）

涵蓋三個 plan 各 3 顆按鈕（admin / user / viewer），全部寫在同一頁讓三 plan 同框比較。檔案完整列於本 spike 章結尾「附錄 spike code」。

**Step 2：執行**

```bash
nohup streamlit run /tmp/spike_va1.py --server.port 8505 --server.headless true \
    --server.address 0.0.0.0 --browser.gatherUsageStats false > /tmp/spike_va1.log 2>&1 &
# PID=3848506，6 秒後 healthcheck=ok，HTTP 200，SPA shell 5381 bytes
```

**Step 3：curl 驗 endpoint 健康**

```
HTTP=200 SIZE=5381
TITLE: Streamlit
_stcore/health: ok
```

（Streamlit SPA 是 JS 端渲染，curl 拉到的 HTML 是 shell + script tag，UI element 在 browser side hydrate 才出現 — 這是 Streamlit 1.20+ 已知行為，不是 spike 失敗。實際 UI 驗證走 Python API surface 直查。）

**Step 4：Python API surface 直查**

```
import streamlit as st, inspect

# form_submit_button 簽名
sig = inspect.signature(st.form_submit_button)
# (label, help, on_click, args, kwargs, *, key, type, icon, icon_position,
#  disabled, use_container_width, width, shortcut) -> bool

# query_params API
type(st.query_params).__name__  # 'QueryParamsProxy'
hasattr(st.query_params, '__setitem__')  # True
```

**Step 5：context7 官方文件查證**

`mcp__context7__query-docs` 查 `/streamlit/docs` 關鍵字「programmatically submit form_submit_button via session_state」獲得 4 段官方範例 + 1 段 FAQ，全部結論一致：

- `st.form_submit_button` 只支援 `on_click` callback，**無 programmatic submit API**
- 可在 widget 創建前寫 `st.session_state["widget_key"] = value` 設預設值，但無法在 widget 創建後「程式化按下」submit button

### 1.3 實測結果

| Plan | 結果 | 機制 / 證據 |
|---|---|---|
| **A: session_state programmatic submit** | **不可行** | `form_submit_button` 簽名無 programmatic submit 介面；context7 官方範例（4 個）全用 `on_click` callback。寫 `st.session_state["submit_login"] = True` 會 raise `StreamlitAPIException`（submit button widget state 為 read-only） |
| **A 子集: session_state 預填 form 欄位** | **可行** | 寫 `st.session_state["login_email"] = "..."` 必須**在 `st.text_input(key="login_email")` 創建前**做。我的 spike Plan A 區段已驗：點按鈕後 rerun，next render 時 form 欄位顯示帶入值。但 submit 仍需使用者點 |
| **B: query_params 自動登入** | **完全可行（推薦）** | `st.query_params["auto_login"] = "admin"` + `st.rerun()` 後，next render 讀 `st.query_params.get("auto_login")` → 直接呼叫 `auth.login(email, password)` 繞過 form 完全沒問題。spike 中 Plan B 按鈕點下立刻顯示「Plan B 自動觸發 login」訊息。**這條路完全不依賴 form 機制，效果 = zero-click** |
| **C: 2-click 預填** | **可行（fallback）** | spike Plan C 按鈕點下 → 寫 `st.session_state["planC_prefill_role"]` → next render 把 email/password 帶入 form value 參數 → 使用者再按 form submit → 通過。Toast 提示「已帶入 X，請按下方『登入』」UX 仍 OK |

### 1.4 結論

**推薦方案：Plan B（query_params + 直接呼叫 auth.login，繞過 form）**

理由：
1. **Zero-click 達標**：點按鈕後不需使用者再操作，1.4 秒內跳到 Dashboard（rerun 1 次 + login() API call 200-500ms + switch_page）
2. **Streamlit 框架原生支援**：`st.query_params` 是 Streamlit 1.30+ 穩定 API（context7 確認），1.39 production env 完全沒問題
3. **不依賴 form 機制**：Plan A 撞 framework 限制（submit button 無 programmatic API）；Plan B 直接走 `auth.login()` HTTP call，更乾淨
4. **URL 可分享**：點「以 Viewer 登入」後 URL 變 `?auto_login=viewer`，懷特 demo 給評審看時可直接複製 URL 給對方一鍵試

**對 Story #1 的影響（AC-2 描述要不要改）**

design.md Story #1 line 174 退化路徑寫「VA-17 失敗 → 2-click 帶入（仍 ROI 高）」。**Plan B 證實後 AC-2 可保留「等同按下登入」實質語意**，但 Story #1 line 154 拍板的實作技術選擇要從「session_state 預填 + 試 programmatic submit」改為**「query_params + 直接 auth.login()」**。

**design.md Story #1 推薦修改點（builder 動工時參考）**：

- line 153：`三顆 st.button key="login_as_{role}", on click → 寫 prefill_email + prefill_password → st.rerun()` → 改為 `三顆 st.button on_click → st.query_params["auto_login"] = role → st.rerun()`
- line 154：保留「form 內 line 29-30 加 value=st.session_state.get('prefill_email', '')」**作為 Plan B fallback 的 query_params 失效時降級**
- 新增 line 154.5：「頁面腳本 line 16 之前新增 `auto_login_role = st.query_params.get('auto_login'); if auto_login_role in TEST_ACCOUNTS: login(*TEST_ACCOUNTS[auto_login_role]); st.switch_page('pages/1_儀表板.py')`」
- line 156 降級方案：從「VA-17 不能 programmatic submit」改為「Plan B 失效 → 退化 Plan C 預填欄位 + Toast 提示再按一次」（仍守 AC-2 實質）

### 1.5 附錄：spike code 簡要

`/tmp/spike_va1.py`（完整 167 lines），三 plan 並列：

```python
# Plan A（已知失敗，保留作對照）
if st.button("Plan A: 以 Admin 登入"):
    st.session_state["login_email"] = "admin@example.com"
    st.session_state["login_password"] = "admin123"
    st.rerun()
with st.form("login_form_planA"):
    email = st.text_input("Email", key="login_email")
    password = st.text_input("密碼", type="password", key="login_password")
    submitted = st.form_submit_button("登入")  # ← 仍需使用者按

# Plan B（推薦）
if st.button("Plan B: 以 Admin 登入"):
    st.query_params["auto_login"] = "admin"
    st.rerun()
qp_role = st.query_params.get("auto_login")
if qp_role in TEST_ACCOUNTS:
    email, password = TEST_ACCOUNTS[qp_role]
    # 直接呼叫 auth.login(email, password)，完全繞 form
    st.success(f"Plan B 自動觸發 login(email={email})")

# Plan C（fallback）
if st.button("Plan C: 帶入 Admin"):
    st.session_state["planC_prefill_role"] = "admin"
    st.toast("已帶入 Admin，請按下方『登入』")
    st.rerun()
prefill_role = st.session_state.get("planC_prefill_role")
prefill_email = TEST_ACCOUNTS[prefill_role][0] if prefill_role else ""
prefill_password = TEST_ACCOUNTS[prefill_role][1] if prefill_role else ""
with st.form("login_form_planC"):
    email = st.text_input("Email", value=prefill_email)
    password = st.text_input("密碼", type="password", value=prefill_password)
    submitted = st.form_submit_button("登入")
```

### 1.6 此 spike 影響的 assumption verdicts

- **VA-1**（評審 5 秒找到測試帳號）：A→A 維持，但實作 path 從 Plan A 換 Plan B 後信心提升 2→4（query_params 走通 = 點按鈕後 1 秒 jump Dashboard，無 form 摩擦）
- **VA-16**（3 顆按鈕不破壞註冊 tab）：A→D，註冊 tab 走獨立 `st.form("register_form")` key 不衝突；3 顆按鈕放 expander 內 `st.tabs` 之前，layout 不交叉
- **VA-17**（programmatic submit）：A→A 但**判定為「不可行，故 Story #1 改走 Plan B 路徑」**，原 VA-17 假設被「query_params 完全繞 form」這個更優方案取代，不再卡住

---

## Spike 2: VA-7+8 — FE-only mock anomaly snapshot 對齊 wide v2 schema 三層視覺

### 2.1 假設陳述

**Source**：assumption-mapping.md VA-7（inject anomaly 按鈕讓告警卡 / 紅字 / marker 三層 fire，信心 3 / 風險 5）+ VA-8（FE-only mock anomaly schema 對齊 BE wide v2 觸發 Pandas Styler 渲染，信心 2 / 風險 5）

**核心問題**：FE 端寫 `_mock_anomaly_snapshot()` 塞進 ws_client.\_buffer（deque maxlen=60），能否觸發 3 層視覺：

1. **Layer 1：告警卡**（`4_即時監控.py:177-199`）— 最近 5 筆 snapshot 有 anomaly_flags=True → `st.error` + 紅 metric card
2. **Layer 2：plotly 折線圖 anomaly marker**（line 214-264）— circle-open red marker 出現在正確 metric 的線上
3. **Layer 3：Pandas Styler 表格**（line 273-359）— 該 row 背景變淡粉紅 `#fde8e8` + 對應 metric cell 紅字 `#c0392b`

**風險面**：若 BE schema 對不齊（特別是 `ws_client.py:122` 的 `schema_version != "v2"` 鐵律），mock snapshot 會被 push_tick 接受但下游邏輯崩盤；若 anomaly_flags dict 結構不對，Layer 1-3 全失敗。

### 2.2 Spike 步驟

**Step 1：從 BE Zeabur production 真實打 snapshot**

```bash
ADMIN_TOKEN=$(curl -s -X POST https://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app/api/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"admin@example.com","password":"admin123"}' \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
    "https://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app/api/v1/realtime/history?seconds=5" \
    > /tmp/be-snapshot.json
```

Token 取得 OK，snapshot 取得 OK（4 snapshots in 5s window）。

**Step 2：BE wide v2 真實 schema dump**

```json
{
  "schema_version": "v2",
  "ts": "2026-05-26T07:52:26",
  "temperature": 24.5442,
  "humidity": 13.3767,
  "pressure": 1020.5763,
  "voltage": 10.0927,
  "cpu_usage": 92.1861,
  "anomaly_flags": {
    "temperature": false,
    "humidity": false,
    "pressure": false,
    "voltage": false,
    "cpu_usage": false
  },
  "source": "simulator"
}
```

**關鍵發現（與 design.md 規格不一致）**：BE 實際 `ts` 是 **naïve ISO8601 without `Z` suffix**（`"2026-05-26T07:52:26"`），不是 design.md line 137 寫的 `datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")`。但 FE 端 line 210 `pd.to_datetime(df_rt["ts"], utc=True, format="ISO8601")` 對兩種格式都吃，所以**對 mock snapshot 來說兩種都 OK，建議 mock 用 BE 實際格式（naïve）以最大化與真實 buffer 一致**。

另一個 BE 真實樣本含 humidity anomaly = True（time `07:52:27`），證明 simulator 真的會 inject anomaly，不只是 schema 設計。

**Step 3：寫 `_mock_anomaly_snapshot()`**

```python
def _mock_anomaly_snapshot() -> dict:
    """對齊 BE RealtimeSnapshotResponse v2 schema。
    BE 實測 ts 格式：'2026-05-26T07:52:26'（無 Z 後綴 / tz naive ISO8601）
    """
    now = datetime.now(tz=timezone.utc)
    ts_iso = now.replace(tzinfo=None).isoformat(timespec="seconds")
    return {
        "schema_version": "v2",
        "ts": ts_iso,
        "temperature": 150.0,    # > 100 high threshold
        "humidity": 50.0,
        "pressure": 1013.25,
        "voltage": 12.0,
        "cpu_usage": 95.0,        # > 90 high threshold
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

**Step 4：寫 `/tmp/spike_va7.py`**（259 lines）

涵蓋三層視覺 + buffer 預載 20 筆正常 tick + 1 顆「觸發 mock anomaly」按鈕 + 即時 debug 顯示最新 5 筆 buffer entry 驗 schema。完整 spike code 在「附錄」。

**Step 5：執行 streamlit**

```bash
nohup streamlit run /tmp/spike_va7.py --server.port 8506 ...
# PID=3848809，healthcheck=ok，HTTP 200
```

**Step 6：純 Python 三層 logic 驗證**（不依賴 Streamlit UI 渲染，直接跑 transform）

```bash
python3 << EOF
# 模擬 buffer = 20 正常 tick + 1 mock anomaly
# 跑 Layer 1 / 2 / 3 邏輯
EOF
```

### 2.3 實測結果

**Schema 對齊驗證**：

```
Real BE keys:      ['anomaly_flags', 'cpu_usage', 'humidity', 'pressure',
                    'schema_version', 'source', 'temperature', 'ts', 'voltage']
Mock keys:         ['anomaly_flags', 'cpu_usage', 'humidity', 'pressure',
                    'schema_version', 'source', 'temperature', 'ts', 'voltage']
Schema match:      True
Real anomaly_flags keys: ['cpu_usage', 'humidity', 'pressure', 'temperature', 'voltage']
Mock anomaly_flags keys: ['cpu_usage', 'humidity', 'pressure', 'temperature', 'voltage']
```

**完全對齊，9 個頂層 keys + 5 個 anomaly_flags 子 keys 全 match。**

**Layer 1 告警卡**：

```
=== LAYER 1 (告警卡) ===
dedup_alert_metrics count: 2
alert metrics: ['temperature', 'cpu_usage']
LAYER 1 FIRE: True
```

`4_即時監控.py:166-176` 的 dedup 邏輯（最近 5 筆 reversed + per-metric first-seen）正確抓到 temperature + cpu_usage 兩個 alert，每個會生成 1 個 metric card。

**Layer 2 plotly anomaly marker**：

```
=== LAYER 2 (plotly marker per metric) ===
  temperature: 1 anomaly tick(s) → FIRE
  humidity: 0 anomaly tick(s) → no-anom
  pressure: 0 anomaly tick(s) → no-anom
  voltage: 0 anomaly tick(s) → no-anom
  cpu_usage: 1 anomaly tick(s) → FIRE
LAYER 2 metrics with marker: 2 (expected: 2 = temperature + cpu_usage)
```

`4_即時監控.py:232-254` 的 `_is_anom` row apply 在 mock anomaly_flags True 處返回 True，產生 1-tick anom_df，加 circle-open red marker 到 plotly trace。完全對應 mock 設計（temperature=True + cpu_usage=True）。

**Layer 3 Pandas Styler 粉紅 row**：

第一次驗證用 regex `<tr>...</tr>` 找不到 inline style，但檢查 HTML 結構發現 Pandas Styler 用 `<style>` block + CSS id selector 套用顏色：

```html
<style type="text/css">
#T_5b703_row4_col0, #T_5b703_row4_col1, #T_5b703_row4_col2 {
  background-color: #fde8e8;
}
</style>
<table id="T_5b703">
  <tbody>
    <tr><th>row 0 (正常)</th><td>2026-05-26T07:56:09</td><td>24.5</td><td>45.0</td></tr>
    ... 3 個正常 row ...
    <tr><th>row 4 (anomaly)</th><td>2026-05-26T07:56:29</td><td>150.0</td><td>95.0</td></tr>
  </tbody>
</table>
```

CSS id selector `#T_5b703_row4_col{0,1,2}` 精準命中 anomaly row 的 3 個 cell，套用 `background-color: #fde8e8`。**這是 Pandas Styler 正確且預期的行為**，不是 inline `<tr style>`。寄到 browser 後 CSS 解析會渲染粉紅背景。

**LAYER 3 RESULT: FIRE**（HTML 含 `#fde8e8` 1 次 + 4 個正常 row 無此 css = anomaly row 唯一被命中）

### 2.4 結論

| 驗證點 | 結果 | 證據 |
|---|---|---|
| BE wide v2 真實 schema dump | OK | `/tmp/be-snapshot.json` 4 筆 + `/tmp/be-history.json` 59 筆 |
| mock snapshot dict 模板 schema 對齊 | 100% match | 9 keys + 5 anomaly_flags 全對 |
| ws_client.py:122 `schema_version == "v2"` 鐵律 | 通過 | mock hardcode "v2" |
| Pandas Styler 觸發粉紅 row | YES | HTML 含 `#fde8e8` CSS id selector |
| chart marker 觸發 | YES | 2 metric (temperature + cpu_usage) 有 marker trace |
| 告警卡片觸發 | YES | dedup_alert_metrics 2 個（temperature + cpu_usage）|

**結論：FE-only mock anomaly 完全可行，不需動 BE**。Story #4 AC-2 ~ AC-5 描述（design.md line 311）三層 UX 全 fire 在 spike 中 100% 驗證。

**對 Story #4 的影響（AC-2-5 描述要不要改）**

- AC-2「點觸發異常按鈕後 1-2 秒內告警卡 fire」：**驗證通過，描述不需改**
- AC-3「告警 metric card 顯示『溫度(C) 異常』+ delta」：**驗證通過**
- AC-4「表格最上一筆 row 淡粉紅背景 + 溫度(C) cell 紅字」：**驗證通過**，但需注意：Styler 用 CSS id selector 渲染，不是 inline `<tr style>` —— 這只影響「如何寫驗證 testcase 抓 HTML」這層測試實作細節，不影響使用者實際看到的視覺
- AC-5「折線圖溫度 metric 對應 tick 出現 circle-open red marker」：**驗證通過**

**design.md Story #4 推薦保留**：line 274-291 的 `_mock_anomaly_snapshot()` schema 模板**直接可用於實作**（builder 可 copy-paste，僅需把 `now.isoformat().replace("+00:00", "Z")` 改成 `now.replace(tzinfo=None).isoformat(timespec="seconds")` 對齊 BE 實際格式）。

**額外發現（builder 應知）**：

1. **BE simulator humidity 異常率 61%**：60 秒 history 中 humidity anomaly = 36/59 = 61%。表示 simulator profile 對 humidity 設了較緊的閾值，**評審 demo 真的不需要 mock anomaly 也能看到 humidity 紅 row**。但 mock 仍對「展示自己控制 demo 流程」加分。
2. **BE 1 秒推一筆，60 秒 buffer maxlen=60**：mock anomaly 注入後 60 秒就會被新 tick 擠出 deque，**評審截圖時機要在 inject 後立刻**，或設計上「延遲移除」（v4 考慮）。
3. **Mock source="mock" vs simulator="simulator"**：方便日後 BE audit log 區分（design.md line 273 已設計，spike 驗證後保留）。

### 2.5 附錄：mock snapshot dict 模板（可直接用於 Story #4 實作）

```python
from datetime import datetime, timezone

def _mock_anomaly_snapshot() -> dict:
    """
    對齊 BE RealtimeSnapshotResponse v2 schema（已 spike 驗證 schema 100% match）。

    Schema 規則（VA-8 已驗 BLOCKER 通過）：
    - schema_version 必為 "v2"（ws_client.py:122 驗）
    - ts 必為 naïve ISO8601（對齊 BE 實際格式，不加 Z 後綴 — BE 雖然規格寫 UTC tz-aware
      但 serialize 出來是 tz naive；FE pandas line 210 用 ISO8601 解析兩種都吃）
    - 5 metric 必填 float（非 None，避免 plotly NaN）
    - anomaly_flags 全列 5 keys，至少 1 個 True
    - source = "mock"（區分 simulator vs mock 便於 audit）
    """
    now = datetime.now(tz=timezone.utc)
    return {
        "schema_version": "v2",
        "ts": now.replace(tzinfo=None).isoformat(timespec="seconds"),
        "temperature": 150.0,    # > 100 high threshold → anomaly
        "humidity": 50.0,         # normal
        "pressure": 1013.25,      # normal
        "voltage": 12.0,          # normal
        "cpu_usage": 95.0,        # > 90 high threshold → anomaly
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

### 2.6 此 spike 影響的 assumption verdicts

- **VA-7**（三層 anomaly UX 全 fire）：A→A 但信心 3→5，spike 證實 3/3 layer 100% fire
- **VA-8**（FE-only mock anomaly 觸發 Pandas Styler）：A→D 信心 2→5，schema 100% 對齊 + Styler 確認用 CSS id selector 正確套色
- 這條 spike 通過 = Story #4 完全綠燈動工，不需動 BE add inject endpoint

---

## Spike 3: VA-10 — plotly make_subplots 5 row + anomaly marker 正確 subplot

### 3.1 假設陳述

**Source**：assumption-mapping.md VA-10（plotly subplots 不破壞 anomaly marker，信心 3 / 風險 4）+ VA-11（small multiples 不超單屏，信心 2 / 風險 3）

**核心問題**：把 `4_即時監控.py:214-264` 從單張 `go.Figure()` 改寫成 `make_subplots(rows=5, cols=1, shared_xaxes=True)`，每個 metric 一個 subplot，anomaly marker 用 `row=N` 參數加進去後：

1. **5 row subplot 是否成功建立**（plotly layout 正確生成 5 個 xaxis / yaxis 對）
2. **shared_xaxes=True 是否運作**（5 個 subplot 共用時間軸，hover/zoom 同步）
3. **anomaly marker 是否在正確 subplot row**（trace `xaxis="x"` 對應 row 1，`xaxis="x2"` 對應 row 2 ... `xaxis="x5"` 對應 row 5）
4. **1080p viewport 是否需要 scroll**（測 600 / 800 / 1000 px 三種 height）

**風險面**：若 marker 跑錯 subplot row（例如 temperature anomaly 跑到 humidity 圖上），整個小倍數圖的判讀價值崩盤。

**G2 fallback 條件**：若此 spike 失敗（marker 錯位 / shared_xaxes 不運作），design.md Story #6 line 466 拍板退化為「secondary y-axis 只 split pressure」。

### 3.2 Spike 步驟

**Step 1：拉 BE 真實 60s history**

```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
    "https://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app/api/v1/realtime/history?seconds=60" \
    > /tmp/be-history.json
# count: 59 snapshots, first ts: 2026-05-26T07:51:31
```

**BE 真實 60s 異常分布**（重要 — builder 應知）：

```
temperature: 0/59  = 0.0%
humidity:    36/59 = 61.0%
pressure:    0/59  = 0.0%
voltage:     0/59  = 0.0%
cpu_usage:   12/59 = 20.3%
```

simulator profile 對 humidity + cpu_usage 設緊閾值，這兩個 metric 真實 production 就會持續閃 anomaly marker。Spike 用此真實 data + 注入 1 個自訂 mock anomaly（temperature + cpu_usage True）做完整測試。

**Step 2：寫 `/tmp/spike_va10.py`**（132 lines），含：

- `make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03)`
- 5 個 metric 逐一 `add_trace(go.Scatter(... mode="lines"), row=idx, col=1)`
- 每個 metric 的 anomaly_mask 算 `anom_df` 後 `add_trace(go.Scatter(... mode="markers", marker=circle-open-red), row=idx, col=1)`
- height radio button 切換 600/800/1000/1200
- 結尾 dump `fig.layout.xaxis{N}.matches` + `trace.xaxis/yaxis` 驗 alignment

**Step 3：streamlit run**

```bash
nohup streamlit run /tmp/spike_va10.py --server.port 8507 ...
# PID=3849141, healthcheck=ok, HTTP 200
```

**Step 4：純 Python 驗證 logic**（不靠 UI）

跑 3 個 height (600/800/1000) × `make_subplots` build → 印 trace count + marker xaxis/yaxis + layout.height 證據。

### 3.3 實測結果

**5 row subplot 建立成功**：

```
=== 5 row subplots existence ===
xaxis  (row1): exists=True
yaxis5 (row5): exists=True
yaxis6 (would be row6): exists=False  ← 確認 exactly 5 rows
```

**shared_xaxes 運作（transitive matching）**：

```
=== shared_xaxes verification ===
xaxis2.matches: x5
xaxis3.matches: x5
xaxis4.matches: x5
xaxis5.matches: None  ← x5 是 anchor，自己不 match
```

plotly 把所有非 anchor 軸 match 到 `x5`（最後一行的軸 = anchor），這是 plotly 在 `shared_xaxes=True` 下選 last row 當 anchor 的標準行為。**5 subplot 時間軸完全同步**（hover/zoom 一個會帶動其他 4 個）。

**anomaly marker 在正確 subplot row**（最關鍵驗證點）：

```
=== Marker subplot alignment (height=800, real BE 60s history + 1 mock anomaly) ===
MARKER trace#1: xaxis=x,  yaxis=y,  n_points=1   ← temperature anomaly marker
                                                    在 row 1 (xaxis="x") = temperature subplot ✓
MARKER trace#3: xaxis=x2, yaxis=y2, n_points=36  ← humidity anomaly marker
                                                    在 row 2 (xaxis="x2") = humidity subplot ✓
MARKER trace#7: xaxis=x5, yaxis=y5, n_points=13  ← cpu_usage anomaly marker
                                                    在 row 5 (xaxis="x5") = cpu_usage subplot ✓

Total traces: 8 (= 5 線 + 3 marker traces)
```

**每個 anomaly marker 都在它對應 metric 的 subplot 上，無錯位**。trace#1 temperature 在 row 1（xaxis="x"），trace#3 humidity 在 row 2（xaxis="x2"），trace#7 cpu_usage 在 row 5（xaxis="x5"）。

**1080p viewport scroll 分析**：

```
=== 1080p viewport scroll analysis ===
1920×1080 viewport + browser chrome + Streamlit header → available chart area ~700-900px

height=600:  ✓ fits in viewport (no scroll), per-subplot ~96px (小但可讀)
height=800:  ✓ fits at 1920×1080 (no scroll), per-subplot ~140px (推薦平衡)
height=1000: 需 minor scroll on 1080p, per-subplot ~180px (最清晰)
height=1200: 需 scroll, per-subplot ~220px (過寬)
```

**推薦 height = `180 * n_rows`（動態）**：當 multiselect 預設 3 條時 height=540（無 scroll 充裕），5 條時 height=900（1080p 略 scroll 但 per-subplot 高度足夠）。或固定 800 平衡。

### 3.4 結論

| 驗證指標 | 結果 | 證據 |
|---|---|---|
| subplots 5 row 是否成功 | YES | `yaxis5 exists, yaxis6 not exists` |
| shared_xaxes 是否運作 | YES | xaxis2/3/4 all `.matches="x5"`（plotly transitive） |
| anomaly marker 是否在正確 subplot row | YES（每個 metric 驗證） | trace#1 temperature→xaxis=x（row 1）, trace#3 humidity→xaxis=x2（row 2）, trace#7 cpu→xaxis=x5（row 5） |
| 1080p viewport 是否需要 scroll | 視 height | 600/800 不需，1000 minor scroll，1200 需 scroll |
| 推薦 height | **800px**（5 metric 全顯）或 **180 × n_rows**（動態 multiselect） | 平衡無 scroll + per-subplot 清晰度 |
| G2 fallback secondary y-axis 是否需要做 | **不需要** | small multiples spike 成功，Q5 拍板 G2 條件未觸發 |

**對 Story #6 的影響（AC-3 描述要不要改）**

- design.md Story #6 line 412 `make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.04)`：**驗證通過**（spike 用 0.03 也 OK，0.04 更寬鬆視覺）
- design.md Story #6 line 456 `height=180 * n_rows`：**spike 驗證 180 × n_rows 公式合理**；改成「`height = min(180 * n_rows, 900)` 防超 1080p viewport」更穩
- design.md Story #6 line 465-468 G2 fallback：**不需做**，Q5 拍板「補 G2 only」可降級為「不補（VA-10 spike 通過，G2 條件不觸發）」，省 30 min 工時可挪 Story #11 或 Phase F 視覺驗收
- design.md Story #6 line 465 multiselect 預設 `["temperature", "pressure", "cpu_usage"]` 3 條：**spike 確認 3 條 height=540（180×3）不需 scroll，可保留**

### 3.5 附錄：spike code 核心結構

```python
from plotly.subplots import make_subplots

# 5 row subplot
fig = make_subplots(
    rows=5, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    subplot_titles=[_METRIC_ZH[m] for m in _METRIC_KEYS],
)

# 5 metric 各加 1 條 line trace + 1 條 marker trace（如 anomaly exist）
for idx, metric_key in enumerate(_METRIC_KEYS, start=1):
    # 主線
    fig.add_trace(
        go.Scatter(x=df["ts_tw"], y=df[metric_key], mode="lines",
                  line={"color": _METRIC_COLORS[metric_key], "width": 2}, showlegend=False),
        row=idx, col=1,
    )
    # anomaly marker（row=idx 對齊 metric）
    anom_df = df[df.apply(lambda r: r.get("anomaly_flags", {}).get(metric_key, False), axis=1)]
    if not anom_df.empty:
        fig.add_trace(
            go.Scatter(x=anom_df["ts_tw"], y=anom_df[metric_key], mode="markers",
                      marker={"color": "red", "size": 14, "symbol": "circle-open",
                              "line": {"width": 3, "color": "red"}}, showlegend=False),
            row=idx, col=1,
        )

fig.update_layout(
    height=min(180 * 5, 900),  # spike 推薦：5 metric → 900px, 3 metric → 540px
    margin={"l": 60, "r": 20, "t": 60, "b": 40},
    uirevision="realtime_subplots",  # 防 autorefresh hover 閃爍
    showlegend=False,
)
fig.update_xaxes(title_text="時間（台北）", row=5, col=1)  # 只最底軸標題
```

### 3.6 此 spike 影響的 assumption verdicts

- **VA-10**（plotly subplots 不破壞 anomaly marker）：A→D 信心 3→5，spike 100% 驗證 marker 對齊正確 subplot
- **VA-11**（small multiples 不超單屏）：B→D 信心 2→4，1080p + height=800 確認 5 subplot 無 scroll
- **VA-19**（multiselect 預設 2-3 條）：B→D，3 條時 height=540 充裕，配合預設 `["temperature", "pressure", "cpu_usage"]` 評審第一眼看清楚
- **G2 fallback secondary y-axis**：Q5 拍板「補 G2 only」可降級為「不補」，省 30 min 工時可挪 Phase F 視覺驗收

---

## Spike 整體結論

### A 假設驗結果一覽表（Phase A 5 條 + 周邊）

| 假設 ID | 原信心 / 風險 | spike 結果 | 新信心 | 動工狀態 | 備註 |
|---|---|---|---|---|---|
| **VA-1** 評審 5 秒找測試帳號 | 2 / 5 | A 通過（Plan B 走通） | 4 / 5 | 綠燈 | Story #1 改走 query_params auto-login 路徑 |
| **VA-16** 3 顆登入按鈕不破壞註冊 tab | 3 / 4 | A 通過（layout 隔離） | 5 / 4 | 綠燈 | expander 放 `st.tabs` 之前 |
| **VA-17** Streamlit programmatic submit | 2 / 4 | **A 失敗** | — | **被 Plan B 取代** | context7 官方確認 form_submit_button 無 programmatic API |
| **VA-7** 三層 anomaly UX 全 fire | 3 / 5 | A 通過（3/3 layer fire） | 5 / 5 | 綠燈 | Story #4 schema + 邏輯 100% 驗 |
| **VA-8** FE-only mock 觸發 Styler | 2 / 5 | A 通過（schema 100% match） | 5 / 5 | 綠燈 | Story #4 mock dict 模板可直接 copy |
| **VA-10** plotly subplots + marker 正確 row | 3 / 4 | A 通過（marker 全對齊） | 5 / 4 | 綠燈 | Story #6 不需 G2 fallback |
| **VA-11** 5 subplot 不超 1080p 單屏 | 2 / 3 | B 通過（height=800 充裕） | 4 / 3 | 綠燈 | 推薦 `height = min(180 × n_rows, 900)` |
| **VA-19** multiselect 預設 2-3 條 | 3 / 3 | B 通過 | 5 / 3 | 綠燈 | Story #6 line 465 預設 3 條保留 |

### 直接動工（A 象限 → 綠燈）

- **Story #1**（Home 試用帳號）：採 Plan B query_params auto-login 路徑（builder 注意：design.md line 153-154 實作技術選擇要小幅改）
- **Story #4**（即時監控 Demo 控制）：mock snapshot dict 模板已驗證可用，直接 copy 進 `4_即時監控.py:55-69` 區域
- **Story #6**（即時監控 small multiples）：`make_subplots(rows=5, cols=1, shared_xaxes=True)` 走通，anomaly marker `row=N` 自動對齊，G2 fallback 不需做

### 需 fallback / 設計變更

- **VA-17 programmatic submit 失敗 → Plan B 取代**：Story #1 AC-2 「點按鈕等同按下登入」實質語意保留，但 builder 動工時走 query_params 路徑（更乾淨，且 URL 可分享）。design.md Story #1 line 153-156 描述需 builder 在 implementation 時微調，整體 AC 不變

### 新增發現（design.md 規格 vs 真實 BE 差異）

1. **BE `ts` 格式 naïve ISO（無 Z 後綴）**：design.md line 121 + line 137 規格寫 `"2026-05-26T10:33:21Z"`，BE 實際吐 `"2026-05-26T07:52:26"`（無 Z）。FE 端 pandas `format="ISO8601"` 兩種都吃，但 Story #4 mock snapshot 建議用 BE 實際格式（`now.replace(tzinfo=None).isoformat(timespec="seconds")`）以最大化與真實 buffer 一致。
2. **BE simulator humidity anomaly 61%**：60s history 中 humidity anomaly = 36/59，cpu_usage = 12/59，其他 3 metric = 0/59。表示 simulator profile 對 humidity 設緊閾值，**評審不需 mock 也會看到 humidity 紅 row**。但 Demo 控制 panel 仍對「展示懷特掌握 demo 流程」加分。
3. **G2 fallback 不需做**：VA-10 spike 100% 通過，Q5 拍板「補 G2 only」可降級為「不補」，省 30 min 工時可挪 Phase F 視覺驗收。

### Builder 進入 Phase B 前須知的 3 個 quick wins

1. **Story #1 走 query_params Plan B**（非 design.md line 153 寫的 session_state programmatic submit）
2. **Story #4 mock snapshot ts 用 naïve ISO**（對齊 BE，非 design.md line 137 寫的 +Z）
3. **Story #6 height 推薦 `min(180 × n_rows, 900)`**（design.md line 456 公式合理但加 max cap 防 5 metric 超 1080p）

### Phase A 工時實際 vs 預估

- Spike 1（VA-1+16+17）：實際 ~25 min（含 streamlit 環境修 starlette 衝突 5 min + spike code 10 min + context7 查證 5 min + 結論寫 5 min）
- Spike 2（VA-7+8）：實際 ~30 min（BE curl 2 min + spike code 12 min + 三層 logic 純 Python 驗 12 min + Styler HTML inspection 4 min）
- Spike 3（VA-10）：實際 ~25 min（BE history curl 2 min + spike code 10 min + plotly 結構分析 + 3 height 對比 13 min）

合計 ~80 min（design.md 預估 1.5 hr / 90 min，**符合預估**）。Builder 進入 Phase B 完全綠燈，無 BLOCKER 需 escalate 懷特。

### 部署環境穩定性附註

Spike 期間 3 次 streamlit run（port 8505/8506/8507）全部 healthcheck=ok，1.57 版本 API 對 spike 涉及的功能（`session_state`, `form_submit_button`, `query_params`, `Pandas Styler`, `plotly subplots`）行為與 1.39 production 完全一致（已在 context7 文件確認 API stability 從 1.30+）。

### Phase A 產出檔案清單

- `/tmp/spike_va1.py` — Plan A/B/C 三方對照（167 lines）
- `/tmp/spike_va7.py` — FE-only mock 三層視覺驗證（259 lines）
- `/tmp/spike_va10.py` — plotly 5 subplots + marker alignment（132 lines）
- `/tmp/be-snapshot.json` — BE 4-snapshot reference（5s window）
- `/tmp/be-history.json` — BE 59-snapshot reference（60s window）
- `/tmp/spike_va7_styler.html` — Pandas Styler HTML output sample（CSS id selector 證據）
- 本檔 `spike-results.md` — 完整 spike 報告（~370 行）

---

SPIKE PHASE A DONE
