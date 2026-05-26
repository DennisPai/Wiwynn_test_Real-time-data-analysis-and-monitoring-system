# Research Findings — Real-time Monitoring System Design

**Date**: 2026-05-26 13:00 UTC+8
**Researcher**: general-purpose sub-agent + WebSearch / WebFetch
**Purpose**: 業界即時監控系統設計慣例，供 redesign-v2 spec 決策依據

---

## A. 業界系統架構速覽

- **Prometheus**：pull-based、每筆 `metric_name + ts + value + labels`、scrape 不論前端是否在看都持續跑。
- **Grafana Live**（v8+）：WebSocket pub/sub channels、ephemeral push-only **不持久化**，歷史來自背後 data source。
- **Datadog**：push-based agent 持續送 metric 進 ingestion pipeline，不論 UI 有沒人在看。Anomaly Monitor 用 seasonal/trend-aware 演算法（不是單純閾值）。
- **Zabbix**：Item → Trigger（boolean on item history）→ Event/Problem。Item 連續寫入，trigger 是事後評估。
- **InfluxDB**：Line protocol `measurement,tag_set field_set timestamp`，**同感測器同時刻多 metric 寫在同一行**（wide ingestion line）。

**共識**：**所有系統都「採集與訂閱解耦」** — 後端不論前端是否觀看都持續寫入 DB。

---

## B. 資料 Schema 設計

兩大派：
- **Long format**（Prometheus / OpenTelemetry / 多數 TSDB 內部）：每筆 row 一個 metric value，由 `metric_name + labels` 區分。優：動態擴充 / cardinality 可控 / 單 metric 查詢快。缺：snapshot 要 join。
- **Wide format**（InfluxDB line protocol / SCADA / 傳統 sensor table）：一筆 row 含同 timestamp 下多 fields。優：compression 好 / 一次拿全 snapshot / batch 寫入自然。缺：metric 動態擴充要改 schema。

**業界 norm**：TSDB 內部多 long format（Prometheus dominant）；ingestion 線（InfluxDB / OTel）允許 wide 寫入；hybrid 普遍。

---

## C. 串流訂閱模式（**核心**）

**標準模式 = Snapshot + Delta**：
1. 後端「採集」獨立持續跑（背景 task），不綁前端 lifecycle，DB 永遠累積
2. 前端進入頁面 = REST 拿最近 N 秒 history（snapshot）+ WS subscribe 增量（delta）
3. 圖表 / 表格立刻有資料，不會空白

→ **完美對齊懷特直覺**「電影持續播放、我點進去是中場加入」。

進階：用 monotonic sequence number 讓 client reconnect 後 `/catchup?since=N` 補洞。

---

## D. 異常告警 UX 設計

- **語意配色**：紅=立即行動 / 橘黃=警示 / 綠藍=正常。**禁止只靠顏色**（色盲 1/12），需 icon + text label。
- **Alarm vs Anomaly 區分**：Alarm 奪取注意力（紅+閃+聲音+推播）；Anomaly 可被注意但不打斷（淡粉紅底+邊框+icon）。
- **Delta 顯示**：`▲ +3.2` / `+12.5 above threshold` 提供大小+方向雙資訊。
- **表格列異常標示**：淡色背景（非刺眼飽和紅）+ icon 前綴 + Δ 欄。Carbon Design System status indicator 是 reference。
- **Micro-animation**：200-400ms 過渡標示「剛變化」。

→ 對齊懷特 Q4：**淡粉紅背景 + 紅字 + 註記偏離數值**。

---

## E. 即時資料模擬（無真實 sensor 時）

業界做法：**Random walk / Brownian motion**，不是純 i.i.d. uniform random。

公式：`x_{t+1} = clip(x_t + N(0, σ²) + drift, min, max)`

- 保持 consecutive value flow（相鄰點有相關性）
- 每類別自己的 baseline 跟 σ
- Seed RNG 可重現
- **故意注入異常**：定期某 metric 突破閾值，驗證告警鏈路

純 random 是反例。

---

## F. 監控好用性原則

1. **Visibility of system status** — 永遠顯示「last update 時間 + WS 連線 dot」
2. **Recognition not recall** — 閾值、單位、metric 全名直接顯示
3. **Aesthetic + minimalist** — overview 不塞 raw history，drill-down 才展開
4. **Glanceability > density** — < 3 秒判斷「系統是否健康」，traffic light pattern 先於數字
5. **Hierarchy** — Overview KPI → 表格 latest snapshot → 圖表歷史 → 單筆 drill-down

---

## 🎯 5 條最終設計決策（供 design.md 採用）

1. **採集與訂閱解耦**：模擬器跑成 FastAPI startup background task（已有 `realtime_service`，要確保「不論前端是否開啟都持續寫入 DB」）。前端進頁面 = REST `/api/v1/admin/realtime-history?seconds=60` + WS subscribe 增量。
2. **Schema 選 wide format（給 realtime）**：`realtime_metrics` 改為一筆 row = 一個 ts 所有 metric snapshot（`ts, temperature, humidity, pressure, voltage, cpu_usage, anomaly_flags`）。`data_records` 保留 long format 給使用者自由錄入（兩 table 互通在 Analytics / Dashboard）。
3. **模擬器用 random walk**：`x_{t+1} = clip(x_t + N(0, σ²), min, max)`，每類別自己 baseline + σ。固定 seed。定期注入異常驗證告警鏈路。
4. **異常 UX 三重視覺**：表格異常 row 淡紅背景 + ⚠ icon + Δ 欄（`+12.5 (threshold 80)`）。圖表異常點加紅圈 marker + annotation。
5. **頁面上方 system status header**：last update / WS dot / active alert count。3 秒 glance 判斷健康度。

---

## 來源（17 條）

- [Prometheus scraping (ksolves)](https://www.ksolves.com/blog/big-data/how-prometheus-scraping-works)
- [Prometheus scraping (groundcover)](https://www.groundcover.com/learn/observability/prometheus-scraping)
- [Prometheus naming convention](https://prometheus.io/docs/practices/naming/)
- [InfluxDB schema design](https://docs.influxdata.com/influxdb/v2/write-data/best-practices/schema-design/)
- [Tiger Data — wide vs narrow tables](https://www.tigerdata.com/learn/best-practices-time-series-data-modeling-single-or-multiple-partitioned-tables-aka-hypertables)
- [Grafana Live setup docs](https://grafana.com/docs/grafana/latest/setup-grafana/set-up-grafana-live/)
- [Grafana 8.0 streaming blog](https://grafana.com/blog/new-in-grafana-8-0-streaming-real-time-events-and-data-to-dashboards/)
- [Datadog Anomaly Monitor](https://docs.datadoghq.com/monitors/types/anomaly/)
- [Datadog anomaly detection blog](https://www.datadoghq.com/blog/introducing-anomaly-detection-datadog/)
- [WebSocket patterns for real-time apps](https://blog.bitsrc.io/websocket-communication-patterns-for-real-time-web-apps-526a3d4e8894)
- [FastAPI realtime dashboards](https://oneuptime.com/blog/post/2026-01-25-build-realtime-dashboards-fastapi/view)
- [Smashing Magazine — real-time dashboard UX](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/)
- [Red Hat alert design guidelines](https://ux.redhat.com/elements/alert/guidelines/)
- [Carbon Design System status indicator](https://carbondesignsystem.com/patterns/status-indicator-pattern/)
- [UX for AI — anomaly vs alarm](https://uxforai.com/p/point-anomaly-detection)
- [bitperfect sensor data simulation](https://bitperfect.at/en/blog/simulation-von-sensordaten)
- [NN/G 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
