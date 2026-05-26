# Frontend Summary — Redesign v2 (Phase D)

## 1. 改了哪些 component / page

### 修改的檔案

| 檔案 | 修改內容 |
|---|---|
| `frontend/streamlit_app/ws_client.py` | D1-1/D1-2: 加 schema_version="v2" 驗證，非 v2 payload 被 warning + skip；buffer 改存 wide snapshot dict |
| `frontend/streamlit_app/Home.py` | D2-1: page_icon=None（去 emoji）；switch_page 改指向 `pages/1_儀表板.py` |

### 新增的檔案（舊檔案 git rm 刪除）

| 新檔名 | 舊檔名 | 主要改動 |
|---|---|---|
| `pages/1_儀表板.py` | `pages/1_📊_Dashboard.py` | D2-2~D2-8: 全中文 title、system status header、unified-summary metric cards、最近 10 筆 tabs（即時/錄入）、帳號設定 expander（改自己密碼）|
| `pages/2_資料管理.py` | `pages/2_📁_Data.py` | D3-1~D3-7: 全中文 title、移除「逐筆操作」expander、改 st.data_editor inline edit、diff 提交 + 403 toast、保留 CSV/JSON 匯入（去 emoji）|
| `pages/3_分析報表.py` | `pages/3_📈_Analytics.py` | D4-1~D4-7: 全中文 title、Q7 timerange fix（確保 ts 解析）、unified-summary metric cards、時間趨勢 source toggle、類別分佈 source toggle、去 emoji |
| `pages/4_即時監控.py` | `pages/4_🔴_Realtime.py` | D5-1~D5-11: 全中文 title、REST history 預載 buffer、metric_zh mapping、system status header、告警卡 delta、5 條折線圖（circle-open 異常點）、60 列表格（Pandas Styler 淡粉紅 row + 紅字 cell）、multiselect 顯示哪些線 |
| `pages/5_系統管理.py` | `pages/5_⚙️_Admin.py` | D6-1~D6-9: 全中文 title、5 tab 去 emoji、角色權限矩陣 markdown table、改密碼表單（admin 改任意人）、Tab 4 改 wide format（5 條折線 + wide DataFrame）、Tab 5 去 emoji |

---

## 2. 使用的 Backend API Endpoint（cross-reference backend-summary.md）

| Endpoint | 使用頁面 | 用途 |
|---|---|---|
| `GET /api/v1/realtime/history?seconds=60` | 4_即時監控.py、1_儀表板.py | D5-3: 頁面進入時預載 60 秒歷史；Dashboard system status header |
| `PATCH /api/v1/users/{user_id}/password` | 1_儀表板.py、5_系統管理.py | D2-8: 帳號設定改密碼；D6-5: admin 改任意人密碼 |
| `GET /api/v1/analytics/unified-summary` | 1_儀表板.py、3_分析報表.py | D2-5: Dashboard metric cards；D4-4: 分析報表統合摘要 |
| `GET /api/v1/analytics/realtime-categories` | 3_分析報表.py | D4-6: 類別分佈（即時資料 source） |
| `GET /api/v1/analytics/timerange` | 3_分析報表.py | D4-3: 修後時間趨勢圖（錄入資料 source） |
| `GET /api/v1/admin/realtime-history` | 5_系統管理.py Tab 4 | D6-6: wide format，不帶 category 參數 |
| `WS /ws/realtime?token=...` | 4_即時監控.py | D1-1: wide payload，schema_version="v2" 驗證 |
| `GET /api/v1/data` | 1_儀表板.py、2_資料管理.py | 最近錄入資料 |
| `POST/PATCH/DELETE /api/v1/data` | 2_資料管理.py | inline edit diff 提交 |
| `GET /api/v1/analytics/categories` | 3_分析報表.py | 類別分佈（錄入資料 source） |
| `GET /api/v1/analytics/export` | 3_分析報表.py | Excel 下載 |

---

## 3. 處理的 Edge Case / 失敗 Path

### D1 WS Client
- schema_version != "v2" → logger.warning + continue（忽略舊 payload）
- JSON decode error → logger.warning + continue

### D2 儀表板
- REST history 失敗 → 顯示「重連中」+ 活躍告警無
- unified-summary 失敗 → metric 全顯示「—」
- 改密碼 new != confirm → 顯示錯誤
- 改密碼 old 錯誤 → BE 400 → st.error 顯示 detail

### D3 資料管理
- viewer 角色 → data_editor 全欄 disabled + info 提示
- PATCH 403（無權限修改他人）→ st.toast 提示 + fail_count + 不中斷其他 row
- DELETE 403 → 同上
- 空標題/類別 → 跳過 POST 新行
- 提交成功 success_count>0 → st.rerun 刷新列表

### D4 分析報表
- Q7 fix：ts parse 失敗 → fallback 用原始字串（不 crash）
- buckets 為空 → st.info（不 crash chart）
- unified-summary 失敗 → st.error

### D5 即時監控
- rt_history_loaded 用 session_state flag 確保只預載一次（每次進頁才重設）
- Pandas Styler 失敗 → fallback 無 styler 的 st.dataframe（try/except）
- all_ticks 為空 → 顯示 st.info
- 告警卡：去重（每 metric 只顯示最新一筆）
- multiselect 空選 → fallback 顯示所有線

### D6 系統管理
- admin 改自己密碼 → 強制要求 old_password（前端驗證）
- admin 改他人密碼 → 不帶 old_password（BE 合法）
- Tab 4 wide items 為空 → st.info
- anomaly_flags 不是 dict → fallback {}

---

## 4. Emoji 移除統計

### 完全清除位置
| 位置 | 原本 | 清除後 |
|---|---|---|
| Home.py page_icon | `"📊"` | `None` |
| 1_儀表板.py page_icon | `"📊"` | `None` |
| 2_資料管理.py page_icon | `"📁"` | `None` |
| 3_分析報表.py page_icon | `"📈"` | `None` |
| 4_即時監控.py page_icon | `"🔴"` | `None` |
| 5_系統管理.py page_icon | `"⚙️"` | `None` |
| 各頁面 st.title | `"📊 Dashboard"` / `"🔴 即時資料監控"` / `"⚙️ 系統管理"` 等 | 純中文 |
| tab labels | `"👥 使用者列表"` / `"📋 系統日誌"` / `"🗄️ DB 狀態"` 等 | 純中文 |
| expander label | `"🔍 篩選條件"` / `"🔧 {key}"` | 純中文 |
| 按鈕 label | `"➕ 新增資料"` / `"📥 準備 Excel 下載"` / `"⬇️ 下載 Excel"` / `"🔄 重新整理"` 等 | 純中文 |
| 告警 | `"✅ 目前無異常告警"` | `st.success("目前無異常告警")` |
| 異常欄位 | `"⚠️ 是"` | `"是"` |
| 啟用欄位 | `"✅"` / `"❌"` | `"是"` / `"否"` |
| expander title | `"✏️ 編輯此筆"` / `"🗑️ 刪除此筆"` 等 | 完整移除（逐筆操作已移除）|

### Whitelist（允許保留）
- `✓` (U+2713) 和 `✗` (U+2717)：僅在 5_系統管理.py 角色權限矩陣 markdown table 中使用（design §5.1 明確允許）

---

## 5. WS Payload Parser 改法（D1）

**改動位置**：`ws_client.py` 第 121-127 行

```python
# D1-1: wide payload schema v2 驗證
if data.get("schema_version") != "v2":
    logger.warning("ws: 收到非 v2 payload，忽略 %s", data)
    continue
# D1-2: buffer 元素為 wide snapshot dict
self._buffer.append(data)
on_tick(data)
```

**端對端資料流對齊**：
- BE broadcast：`{"schema_version":"v2","ts":"...","temperature":25.3,"humidity":60.1,"pressure":1013.2,"voltage":12.0,"cpu_usage":42.5,"anomaly_flags":{...}}`
- FE ws_client buffer：每筆 = wide snapshot dict（同上結構）
- FE 4_即時監控.py 讀取：`snap.get("temperature")` / `snap.get("anomaly_flags", {})`

---

## 6. 即時監控改動細節（D5，最複雜）

### REST history 預載（Q2 fix）
```python
if not st.session_state.get("rt_history_loaded"):
    resp_hist = client.get("/realtime/history", params={"seconds": 60})
    if resp_hist.status_code == 200:
        for snap in resp_hist.json().get("snapshots", []):
            ws_client.push_tick(snap)
    st.session_state["rt_history_loaded"] = True
```

### Pandas Styler（Q4 淡粉紅 row + 紅字 cell）

1. 從 wide snapshot 展開 `_anom_*` 欄位到輔助 DataFrame `df_display`
2. `_style_row`：逐行檢查任一 `_anom_*` 欄位，若 True → `background-color: #fde8e8`
3. `_style_metric_col`：對每個 metric 顯示欄，若對應 `_anom_*` 欄位為 True → `color: #c0392b; font-weight: bold`
4. `styled.format()`：metric 欄位格式化為 2 位小數
5. fallback：若 styler 失敗 → 普通 st.dataframe（不 crash）

### 5 條折線圖 + circle-open 異常點（Q5）

- 每個 metric 一個 `go.Scatter(mode="lines")`，顏色由 `_METRIC_COLORS` 對應
- 異常點：`go.Scatter(mode="markers")`，symbol="circle-open"，line.width=2（圓圈框）
- multiselect 控制顯示哪些線（D5-10）

### 告警卡 delta 計算（Q4）

```python
threshold = high_thr if value > high_thr else low_thr
delta_val = value - threshold
sign = "+" if delta_val > 0 else ""
st.metric(label=..., value=f"{value:.2f}", delta=f"{sign}{delta_val:.2f}（閾值 {threshold}）", delta_color="inverse")
```

---

## 7. 測試結果

### syntax check（py_compile）
```
frontend/streamlit_app/ws_client.py          OK
frontend/streamlit_app/Home.py               OK
frontend/streamlit_app/pages/1_儀表板.py     OK
frontend/streamlit_app/pages/2_資料管理.py   OK
frontend/streamlit_app/pages/3_分析報表.py   OK
frontend/streamlit_app/pages/4_即時監控.py   OK
frontend/streamlit_app/pages/5_系統管理.py   OK
```

### emoji grep 結果
```bash
rg -nP '[\x{1F300}-\x{1F9FF}]|[\x{2600}-\x{27BF}]|[\x{2300}-\x{23FF}]' frontend/ ...
```
結果：只有 5_系統管理.py 的角色權限矩陣 ✓ (U+2713) / ✗ (U+2717)，符合 design §5.1 whitelist。

### page_title grep 結果
全部 6 個 set_page_config page_title 均為中文。

### st.title grep 結果
全部 6 個 st.title 均為中文。

---

## 8. 已知 limitation

1. **Pandas Styler + anomaly_flags JSON column**：當 anomaly_flags 從 DB 取回時格式可能為 JSON string 而非 dict，已加 `isinstance(flags, dict)` 防衛。
2. **rt_history_loaded session_state**：每次 browser 重新進頁（新 session）才預載；同一 session 內換頁再回來不重載（設計決策，節省 API call）。
3. **5_系統管理.py Tab 4 動態 closure**：`_is_anom_rth` 函式在 for loop 內定義，使用 `mk: str = metric_key` 預設值 capture 避免 closure bug。
