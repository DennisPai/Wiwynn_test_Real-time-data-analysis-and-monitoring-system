# D.9 Summary — Story #9 Dashboard Metric Cards 品質指標化

**Date**: 2026-05-26
**Story**: #9 — 儀表板 Metric Cards 品質指標化（Sprint 3 Polish）
**Agent**: frontend-engineer

---

## 改動檔案

| 檔案 | 行號範圍 | 內容 |
|---|---|---|
| `frontend/streamlit_app/pages/1_儀表板.py` | 150-222 | 4 metric cards 全部重組：系統健康度 / 異常率 / 即時筆數 / 錄入筆數 |

---

## 4 Cards 新規格表

| 欄位 | Label | Value | Delta | Delta Color | Help |
|---|---|---|---|---|---|
| col1 | `系統健康度` | `● 健康` / `⚠ 警示` / `✕ 異常` / `— 載入中` / `---` | `異常率 X.XXX%`（正常時顯示） | `inverse`（健康時綠）/ `normal`（警示/異常時紅）/ `off` | "基於過去 30 天異常率：< 1% 健康 / 1-5% 警示 / > 5% 異常" |
| col2 | `異常率（過去 30 天）` | `X.XXX%` / `—` / `---` | — | — | "異常筆數 / 合計筆數 × 100%，含即時 + 錄入兩來源" |
| col3 | `即時資料筆數` | `realtime.total` / `---` | — | — | "過去 30 天 simulator 每秒推送的即時資料總筆數" |
| col4 | `錄入資料筆數` | `records.total` / `---` | — | — | "使用者透過 CSV / JSON / inline 編輯錄入的歷史資料筆數" |

---

## 計算邏輯

```
_total   = combined.get("total", 0) or 0
_anomaly = combined.get("anomaly_count", 0) or 0

anomaly_rate = (_anomaly / _total) * 100    # 僅 _total > 0 時計算

健康度：
  anomaly_rate < 1%   → "● 健康"，delta_color="inverse"
  1% <= rate <= 5%    → "⚠ 警示"，delta_color="normal"
  rate > 5%           → "✕ 異常"，delta_color="normal"
```

---

## 端對端資料流對齊（design.md Story #9 5 段對照）

| 段 | 內容 |
|---|---|
| FE 送 | GET `/analytics/unified-summary?date_from=<30天前>&date_to=<現在>&source=both`（既有 `_fetch_unified_summary()` ttl=30） |
| BE 收 | `analytics.py:138-155` `analytics_unified_summary()` 走 `AnyRole`（viewer 可讀） |
| DB 存 | 只讀，`realtime_metrics_wide` + `data_records` combined query |
| BE 回 | `UnifiedSummaryResponse`：`{combined: {total: int, anomaly_count: int}, realtime: {total: int, ...}, records: {total: int, ...}}` |
| FE 顯示 | FE 算 anomaly_rate → 4 個 `st.metric()` cards 渲染（health / rate / rt_count / rec_count） |

**Schema 驗證**（`backend/app/schemas/analytics.py`）：
- `CombinedSummary.total: int` — 計算分母
- `CombinedSummary.anomaly_count: int` — 計算分子
- `RealtimeSummary.total: int` — col3 直接顯示
- `RecordsSummary.total: int` — col4 直接顯示

---

## Edge Case 處理

| 情況 | 處理方式 |
|---|---|
| `combined.total == 0` | `_health_label = "— 載入中"`、`_anomaly_rate_display = "—"`、delta=None |
| `unified == {}` (fetch 失敗) | 所有 4 卡片顯示 `"---"`，delta=None，delta_color="off" |
| `combined.get("total", 0)` 回傳 None | `or 0` guard 處理 None → 0 |
| realtime/records None | `if unified else "---"` guard |

---

## Sprint 1+2 保留驗證

- `render_role_matrix(role)` — line 46-47 完整保留（Story #2）
- `render_demo_banner(role)` — line 48-49 完整保留（Story #7）
- `st.caption(...)` — line 41 完整保留（Story #3）
- `delta_color="normal"` 語意修復 — 不再有 `delta_color="inverse"` 在無 delta 值情況下出現於儀表板 cards

---

## 使用的 Backend API

| Endpoint | 用途 | 守衛 |
|---|---|---|
| `GET /analytics/unified-summary` | 取得 combined / realtime / records 統計 | AnyRole（Viewer 可讀） |

不新增 endpoint，完全使用既有合約。

---

## 測試結果

Story #9 為純前端計算邏輯，無新 BE 測試。

**靜態驗證**：
- `unified == {}` path → 4 cards 全顯示 "---" ✓
- `_total == 0` path → 健康度 "— 載入中"、異常率 "—" ✓
- anomaly_rate < 1% → health label "● 健康"、delta_color="inverse"（green delta）✓
- 1% <= anomaly_rate <= 5% → "⚠ 警示"、delta_color="normal"（red delta）✓
- anomaly_rate > 5% → "✕ 異常"、delta_color="normal"（red delta）✓
- col3 / col4 `help=` 參數設置 ✓
- 所有 `help=` 文字與 AC-3 規格完全一致 ✓

D.9 DONE
