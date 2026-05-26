# Frontend Summary — Story #4 + #6 + #10（Sprint 2 Core UX）

**Date**：2026-05-26
**Agent**：frontend-engineer（Story C.1 / C.2 / C.10 實作）
**Change**：`redesign-v3-uxfix-2026-05-26`
**Worktree**：`.claude/worktrees/agent-a510ae695c8bdeb5f`

---

## 改動檔案

| File | Line 範圍 | Story | 改動說明 |
|---|---|---|---|
| `frontend/streamlit_app/pages/4_即時監控.py` | 整體重寫 | #4 #6 #8(a)(b) #10 | 詳見下方各 story 說明 |

**BE 完全不動**（符合 design.md §2 硬限制）。

---

## Story #4 — Demo 控制面板 + FE-only mock anomaly

### 改動 file:line

`4_即時監控.py`：

- **Line 13**：新增 `import logging` + `logger = logging.getLogger(__name__)`
- **Line 19**：新增 `from plotly.subplots import make_subplots`
- **Line 54-62**：新增 `METRIC_DISPLAY_NAMES` dict（Story #10 告警卡片用完整中文名稱）
- **Line 97-127**：新增 `_mock_anomaly_snapshot()` helper（file 頂部 helper 區，`require_auth()` 之前）
- **Line 195-206**：新增 `with st.container(border=True):` Demo 控制 container（system status header 之後、multiselect 之前）

### (a) mock dict 5 欄位（schema 對齊 VA-8 BLOCKER）

```python
{
    "schema_version": "v2",                          # ws_client.py:122 驗
    "ts": now.replace(tzinfo=None).isoformat(timespec="seconds"),  # naïve ISO（對齊 BE 實際，無 Z）
    "temperature": 150.0,   # > 100 high threshold → anomaly
    "humidity": 50.0,
    "pressure": 1013.25,
    "voltage": 12.0,
    "cpu_usage": 95.0,      # > 90 high threshold → anomaly
    "anomaly_flags": {
        "temperature": True,
        "humidity": False,
        "pressure": False,
        "voltage": False,
        "cpu_usage": True,
    },
    "source": "mock",        # 區分 simulator vs mock
}
```

關鍵 spike 發現（A.4）：BE 實際 `ts` 為 naïve ISO（`"2026-05-26T07:52:26"`），而非 design.md line 137 的 `+Z` 格式。mock 使用 `now.replace(tzinfo=None).isoformat(timespec="seconds")` 對齊 BE 實際格式。

---

## Story #6 — plotly subplots small multiples 重構

### 改動 file:line

`4_即時監控.py`：

- **Line 214**（原 line 151）：multiselect `default` 從 `_METRIC_KEYS`（全 5）改為 `["temperature", "pressure", "cpu_usage"]`（VA-19：預設 3 條）
- **Line 276-363**（原 line 205-266）：整段折線圖改寫為 `make_subplots`

### (b) subplots row=N marker 位置

```python
fig_rt = make_subplots(
    rows=n_rows,        # len(selected_metrics)
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.04,
    subplot_titles=[_METRIC_ZH.get(m, m) for m in metrics_to_show],
)

for idx, metric_key in enumerate(metrics_to_show, start=1):
    # 主線 trace → row=idx
    fig_rt.add_trace(go.Scatter(..., showlegend=False), row=idx, col=1)
    # 異常 marker trace → 同一 row=idx（確保 marker 在正確 subplot）
    fig_rt.add_trace(go.Scatter(..., mode="markers", marker={circle-open, red}), row=idx, col=1)
    fig_rt.update_yaxes(title_text=..., row=idx, col=1)

fig_rt.update_layout(
    height=min(180 * n_rows, 900),  # A.5 spike 推薦公式，防超 1080p
    uirevision="realtime_chart",    # 防 autorefresh hover 閃爍
)
fig_rt.update_xaxes(title_text="時間（台北）", row=n_rows, col=1)  # 只最底軸
```

spike A.5 驗證：marker trace 的 `xaxis/yaxis` 自動對應 `row=idx`，不錯位。G2 fallback 不需做（spike 100% 通過）。

---

## Story #10 — 告警卡片嚴重度視覺化

### 改動 file:line

`4_即時監控.py`：

- **Line 54-62**：新增 `METRIC_DISPLAY_NAMES` dict
- **Line 248**：`st.columns(min(n_alerts, 3))`（從 min(n,5) 改 min(n,3)，每行最多 3 張）
- **Line 249-269**：每卡片顯示 metric 完整中文名稱 + 超閾值/低閾值 delta 文字 + `delta_color="normal"`（Story #8a）

### (c) METRIC_DISPLAY_NAMES dict 內容

```python
METRIC_DISPLAY_NAMES = {
    "temperature": "溫度",
    "humidity": "濕度",
    "pressure": "氣壓",
    "voltage": "電壓",
    "cpu_usage": "CPU 使用率",
}
```

告警卡片 delta text 格式：
- 超閾值：`f"超閾值 +{delta:.2f}（>{high_thr}）"`
- 低閾值：`f"低閾值 -{delta:.2f}（<{low_thr}）"`

5 個告警時，`col_idx = i % 3` 確保分行（第 1-3 張 col 0/1/2，第 4-5 張 col 0/1）。

---

## 使用的 Backend API Endpoint（cross-reference backend-summary）

| Endpoint | 用途 | Story |
|---|---|---|
| GET `/realtime/history?seconds=60` | REST 預載 buffer | 既有功能，不新增 |
| WS `/ws/realtime` | 即時推送 | 既有功能，不新增 |
| **不打 BE** | Demo 控制 mock anomaly 純 FE-only | Story #4 Q1 拍板 |

---

## Edge Case 處理

| Edge Case | 處理方式 |
|---|---|
| ws_client schema_version != "v2" 直接丟棄 | mock hardcode `"v2"` 通過 ws_client.py:122 驗 |
| BE ts 是 naïve ISO（無 Z） | mock 也用 naïve：`now.replace(tzinfo=None).isoformat(timespec="seconds")` |
| buffer 已滿 60 筆 | deque maxlen=60 自動 popleft，符合設計 |
| multiselect 全清空（n_rows=0） | `if n_rows > 0` guard，改顯示 info 提示 |
| 5 個 metric 全異常 | `col_idx = i % 3` 自動分行，2 行 3+2 排列 |
| Styler 渲染失敗 | `except Exception as exc: logger.warning(...) + st.warning(...) + st.dataframe(無樣式 fallback)` |
| subplots G2 fallback | A.5 spike 100% 通過，不需做 |

---

## 測試結果

### Python AST 語法驗證

```
python3 -c "import ast; ast.parse(open('4_即時監控.py').read())"
→ AST parse: OK
```

### Schema 對齊驗證

```
BE keys (sorted):   ['anomaly_flags', 'cpu_usage', 'humidity', 'pressure', 'schema_version', 'source', 'temperature', 'ts', 'voltage']
Mock keys (sorted): ['anomaly_flags', 'cpu_usage', 'humidity', 'pressure', 'schema_version', 'source', 'temperature', 'ts', 'voltage']
Schema match: True
Anomaly flags keys match: True
True flags count: 2 (temperature + cpu_usage)
ts is naïve ISO (no Z): True
schema_version == 'v2': True
All 5 metrics are float: True
temperature 150.0 > threshold 100.0: True
cpu_usage 95.0 > threshold 90.0: True
```

### Story #6 subplots 邏輯驗證

```
3 metrics: height = min(180*3, 900) = 540
5 metrics: height = min(180*5, 900) = 900
Total traces: 6 (3 lines + 3 markers)
Marker 1: xaxis=x,  match=True  (row 1)
Marker 2: xaxis=x2, match=True  (row 2)
Marker 3: xaxis=x3, match=True  (row 3)
uirevision: realtime_chart
```

### Story #10 告警卡 column 邏輯驗證

```
1 alerts → 1 columns
2 alerts → 2 columns
3 alerts → 3 columns
4 alerts → 3 columns (col_idx: 0,1,2,0)
5 alerts → 3 columns (col_idx: 0,1,2,0,1)
```

---

## 禁忌清單確認

- [x] 未動任何 backend 檔案
- [x] 未發明新 endpoint
- [x] mock ts 用 naïve ISO（對齊 BE 實際，不用 +Z）
- [x] subplots anomaly marker 用 row=idx（不用全圖共用 trace）
- [x] G2 fallback 未做（A.5 spike 不需要）
- [x] autorefresh / multiselect / WS subscribe / 清空緩衝區按鈕保留
- [x] Sprint 1 改動不 break（auth.py / Home.py 不動）
- [x] Styler fallback 加 logger.warning + st.warning（非 silent fallback）

---

C.1+C.2+C.10 DONE
