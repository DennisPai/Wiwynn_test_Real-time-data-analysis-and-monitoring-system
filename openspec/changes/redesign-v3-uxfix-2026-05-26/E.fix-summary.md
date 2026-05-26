# E.fix-summary — Phase 11 修正閉環（H-1 / H-5 / Bug#1 / Bug#2）

**Date**：2026-05-26
**Agent**：frontend-engineer sub-agent
**Worktree**：`.claude/worktrees/agent-a5e2ba552b7da4e14`
**Tasks completed**：任務 1（H-1）/ 任務 2（H-5）/ 任務 3（Bug #1）/ 任務 4（Bug #2）

---

## 任務 1 — H-1: Story #9 Dashboard col1 加 delta vs 昨日

**File**：`frontend/streamlit_app/pages/1_儀表板.py`

### 改動位置

| 位置 | Before | After |
|---|---|---|
| line 121-133（新增） | 無 | `_fetch_unified_summary_yesterday()` helper（TTL=300）|
| line 143-149（新增） | `unified = _fetch_unified_summary()` 之後 | `unified_yesterday = _fetch_unified_summary_yesterday()` |
| line 179-216（改） | `_health_delta = f"異常率 {_anomaly_rate:.3f}%"` | 昨日率比較：`f"{_delta_vs_yesterday:+.3f}% vs 昨日"` 或 `"— 無昨日資料"` |
| line 223-230（改） | `help="基於過去 30 天異常率..."` | `help="...；delta 為今日 vs 昨日"` |

### 新增 helper 細節

```python
@st.cache_data(ttl=300)
def _fetch_unified_summary_yesterday() -> dict:
    now_utc = datetime.now(tz=timezone.utc)
    params = {
        "date_from": (now_utc - timedelta(days=2)).isoformat(),
        "date_to": (now_utc - timedelta(days=1)).isoformat(),
        "source": "both",
    }
    resp = client.get("/analytics/unified-summary", params=params)
    ...
```

### Edge case 處理

- `_yesterday_total == 0`（昨日無資料）→ `_health_delta = "— 無昨日資料"`，`_health_delta_color = "off"`
- `unified` 完全失敗 → `_health_delta = None`（維持原邏輯）
- `delta_color = "inverse"`：今日比昨日低（數值降）= 好 = 綠；今日比昨日高 = 壞 = 紅（符合直覺）

### BE API 端對端對齊

- Endpoint：`GET /analytics/unified-summary`（analytics.py line 138）
- Request params：`date_from` / `date_to` / `source="both"`
- Response schema：`UnifiedSummaryResponse`，含 `combined.total` + `combined.anomaly_count`
- FE 計算：`yesterday_rate = (_yesterday_anomaly / _yesterday_total) * 100`
- delta：`today_rate - yesterday_rate`

---

## 任務 2 — H-5: Story #5 即時監控 admin BE 失敗顯 warning

**File**：`frontend/streamlit_app/pages/4_即時監控.py`

### 改動位置

| 位置 | Before | After |
|---|---|---|
| line 234-243 | `st.caption("閾值來源：預設 fallback（無法取得動態設定）")` | `st.warning("無法取得動態閾值，使用預設值（請檢查 BE 連線）")` |

### 三分支邏輯

```
role == "admin" AND _is_dynamic == True  → st.caption（動態閾值已取得）
role == "admin" AND _is_dynamic == False → st.warning（BE 連線失敗）
role != "admin"                          → st.caption（預設值，僅 Admin 可調）
```

### 不破壞既有功能

- `fetch_dynamic_thresholds()` 函式不變
- viewer/user 的 fallback 邏輯（VA-9 BLOCKER 已驗）不變
- 告警卡片、subplots、Styler 邏輯全部不動

---

## 任務 3 — Bug #1: 分析報表錄入趨勢圖視覺強化

**File**：`frontend/streamlit_app/pages/3_分析報表.py`

### 改動位置

| 位置 | Before | After |
|---|---|---|
| line 221-226（改） | `mode="lines+markers"`, `line={"color": "royalblue"}` | 加 `width=3`、`marker={"size":10}`、`fill="tozeroy"`、`fillcolor="rgba(65,105,225,0.15)"` |
| line 232-241（新增） | 無 | `count` 筆數 annotation loop（每個 marker 上方 yshift=15） |
| line 278（改） | `st.plotly_chart(fig_line, ...)` 後無 caption | 加 caption 說明 bucket 粒度與建議 |

### 視覺強化 3 點

1. 線粗從 2（預設）→ 3、marker 從預設 6px → 10px、加 `fill="tozeroy"` 陰影
2. 每個 marker 上方顯示 `N 筆`（`font size=10, color=gray`），`showarrow=False`
3. 圖表下方 caption 提示 bucket 粒度說明

### Edge case

- `df_time` 空或 `count` 欄不存在 → annotation loop 有 `if "count" in df_time.columns and not df_time.empty` guard
- `pd.notna(row["avg_value"])` guard 防 NaN 跑出 annotation

---

## 任務 4 — Bug #2: 即時資料時間趨勢圖改成真正的 trend line

**File**：`frontend/streamlit_app/pages/3_分析報表.py`

### 改動位置

| 位置 | Before | After |
|---|---|---|
| line 12（import）| `import plotly.graph_objects as go` | 加 `from plotly.subplots import make_subplots` |
| line 185-191（新增）| 無 | `_fetch_realtime_history_trend()` helper（TTL=10，`/realtime/history?seconds=3600`）|
| line 280-388（取代）| Bar chart（`go.Bar`，各 metric 平均值）| `make_subplots` 5 metric 各自獨立 Y 軸真正趨勢折線圖 |

### 新 trend line 架構

- Endpoint：`GET /realtime/history?seconds=3600`（realtime.py line 18）
- Response schema：`RealtimeHistoryResponse.snapshots: list[RealtimeSnapshotResponse]`
  - 每筆含：`schema_version="v2"`, `ts`, `temperature`, `humidity`, `pressure`, `voltage`, `cpu_usage`, `anomaly_flags`, `source`
- FE 處理：`pd.to_datetime(ts, utc=True, format="ISO8601").dt.tz_convert("Asia/Taipei")`
- subplots：`make_subplots(rows=n_selected, cols=1, shared_xaxes=True, vertical_spacing=0.04)`
- height：`min(180 * n_selected, 900)`（spike-results.md A.5 公式）
- 異常點：`go.Scatter(mode="markers", marker={"symbol":"circle-open","color":"red"})`，row=idx

### 端對端資料流追蹤（5/23 教訓防範）

| 層 | 內容 |
|---|---|
| FE 送 | `GET /api/v1/realtime/history?seconds=3600`，帶 JWT |
| BE 收 | `seconds: int = Query(60, ge=1, le=3600)`，AnyRole 驗 |
| DB 查 | `RealtimeMetricWide` table，`ts >= cutoff`，order by ts asc |
| BE 回 | `{"snapshots": [...], "count": N}`，每筆 wide format v2 |
| FE 解析 | `df["ts_tw"] = pd.to_datetime(ts, utc=True, format="ISO8601").dt.tz_convert("Asia/Taipei")` |
| FE 渲染 | make_subplots 5 row，shared_xaxes，height=min(180*n,900) |

### 保全既有功能

- `_fetch_realtime_categories()` 函式不刪（「類別分佈」section 仍在 line 376 呼叫）
- `trend_source == "records"` 分支完全不動
- 「類別分佈」section、Excel 匯出 section 全部不動

### Edge case

- `rt_snapshots` 空（cold start / BE 無資料）→ `st.info("此時間內無即時資料...")` 而非 crash
- available_metrics 少於 5（DB 欄位缺）→ 只 loop available_metrics，不 crash
- anomaly_flags 不是 dict → `isinstance(r.get("anomaly_flags"), dict)` guard

### caption 說明

圖表下方加：「即時資料時間趨勢顯示過去 60 分鐘；如需更長範圍請看「錄入資料」source（支援 30 天）。」

---

## Syntax Check 結果

```
python3 -m py_compile frontend/streamlit_app/pages/1_儀表板.py  → OK
python3 -m py_compile frontend/streamlit_app/pages/3_分析報表.py → OK
python3 -m py_compile frontend/streamlit_app/pages/4_即時監控.py → OK
```

---

## 不破壞 Sprint 1+2+3 已驗收的 11 個 Story

| Story | 狀態 | 說明 |
|---|---|---|
| #1 Home demo accounts | 保全 | Home.py 不動 |
| #2 角色矩陣 | 保全 | render_role_matrix 不動 |
| #3 Onboarding caption | 保全 | 各頁 caption 不動 |
| #4 Demo control panel | 保全 | 4_即時監控.py Demo 控制區不動 |
| #5 動態閾值 | 修補 H-5（admin warning）| fetch_dynamic_thresholds 邏輯不動，只改顯示層 |
| #6 small multiples | 保全 | subplots 邏輯不動 |
| #7 Demo Banner | 保全 | render_demo_banner 不動 |
| #8 delta_color + Styler | 保全 | Styler 邏輯不動 |
| #9 metric quality | 修補 H-1（delta vs 昨日）| 只加 helper + 改 delta 計算，metric cards 結構不動 |
| #10 alert severity | 保全 | 告警卡片不動 |
| #11 系統管理 4 P1 | 保全 | 5_系統管理.py 不動 |

---

E.FIX DONE
