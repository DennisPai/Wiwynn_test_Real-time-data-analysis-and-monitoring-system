# Dual-Track Audit — Wiwynn 即時資料分析與監控系統

> **Audit 主題**：系統是否為「即時監控 + 資料管理」雙軌設計？目前 UI/UX 是否清楚表達雙軌？需求文檔背後設計意圖是否被正確實作？
> **產出日期**：2026-05-26
> **Audit 作者**：ux-researcher + product-manager 結合 sub-agent（v6.1 Software Factory）
> **觸發脈絡**：懷特 5/26 17:50 看完 demo 後問「我設計出這個系統，分別獨立監看即時數據，以及另外可以藉由平台整理和圖表分析自己匯入的示範 CSV，是這樣嗎？」← 大總管解讀為「雙軌設計」需 audit 驗證
> **資料來源**（全文逐字讀過）：
> - Wiwynn 需求文檔 docx（`~/.claude/channels/discord/inbox/1779649343977-1508183354124537886.docx` 解析全文）
> - `README.md`（281 行）
> - `docs/sample_data.csv`（61 行，60 筆資料）
> - `frontend/streamlit_app/pages/2_資料管理.py`（329 行）
> - `frontend/streamlit_app/pages/3_分析報表.py`（533 行）
> - `backend/app/models/data_record.py`（46 行，long 表）
> - `backend/app/models/realtime_metric_wide.py`（32 行，wide 表）
> - `openspec/changes/redesign-v3-uxfix-2026-05-26/ux-research.md`（659 行）
> - `openspec/changes/redesign-v3-uxfix-2026-05-26/customer-journey-map.md`（1125 行）
> - `openspec/changes/redesign-v3-uxfix-2026-05-26/pm-strategy.md`（466 行）
> - `~/.claude/agents/ux-researcher.md` + `product-manager.md`
> - `~/.claude/skills/customer-journey-map/SKILL.md`

---

## 目錄

- [Section 1: 需求文檔背後的設計目的（重新解讀）](#section-1-需求文檔背後的設計目的重新解讀)
- [Section 2: 我（大總管）的解讀是否正確？評分與校正](#section-2-我大總管的解讀是否正確評分與校正)
- [Section 3: 使用者旅程審視（4 persona × 雙軌使用場景）](#section-3-使用者旅程審視4-persona--雙軌使用場景)
- [Section 4: UI/UX 體現審視（Top 5 好 + Top 5 gap）](#section-4-uiux-體現審視top-5-好--top-5-gap)
- [Section 5: 補強建議優先級（5-8 條，含 file:line 與工時）](#section-5-補強建議優先級5-8-條含-fileline-與工時)
- [Section 6: 給 frontend-engineer 的具體 spec](#section-6-給-frontend-engineer-的具體-spec)

---

## Section 1: 需求文檔背後的設計目的（重新解讀）

### 1.1 需求文檔逐字證據盤點

從 docx 解析全文，與「雙軌設計」相關的關鍵段落：

**段落 A — 標題**（docx 第 6 行）：
> 題目：即時資料分析與監控系統

**段落 B — 系統能力概述**（docx 第 8 行）：
> 開發一個「即時資料分析與監控系統」，該系統需要：(1) FastAPI ... (5) **包含但不限於使用者認證和權限管理** (6) **實現即時資料推送功能**

**段落 C — 功能需求第 2 模組「資料管理模組」**（docx 第 47-52 行）：
> 2. 資料管理模組
>    - 創建資料記錄（包含但不限於：**標題、數值、分類、時間戳**）
>    - 讀取資料（支援分頁、篩選、排序）
>    - 更新資料（僅限創建者或Admin）
>    - 刪除資料（僅限創建者或Admin）
>    - 批量導入資料（CSV/JSON）

**段落 D — 功能需求第 3 模組「即時監控模組」**（docx 第 53-57 行）：
> 3. 即時監控模組
>    - **模擬即時資料生成器（每秒生成隨機資料）**
>    - WebSocket 連接推送即時資料
>    - 前端即時圖表更新（折線圖、柱狀圖）
>    - 資料異常告警（數值超過閾值時標記）

**段落 E — 功能需求第 4 模組「資料分析模組」**（docx 第 58-63 行）：
> 4. 資料分析模組
>    - 統計分析（總計、平均、最大、最小值）
>    - 時間範圍查詢
>    - 分類資料聚合
>    - 資料趨勢圖表
>    - 可下載Excel

**段落 F — 功能需求第 5 模組「系統管理模組（Admin 專用）」**（docx 第 64-69 行）：
> 5. 系統管理模組（Admin 專用）
>    - 查看所有使用者列表
>    - 使用者權限管理
>    - 系統日誌查詢
>    - 資料庫狀態監控
>    - **即時資料的歷史資料查詢**

### 1.2 重新解讀：是不是「雙軌設計」？

**結論：是雙軌設計，但需求文檔並未明寫「兩個 schema 並存」這件事**。需求文檔列出 5 個模組，其中：

| 模組 | 資料來源（推論） | schema 性質 | 是否雙軌之一 |
|---|---|---|---|
| 2 資料管理 | 使用者人工 / CSV 匯入「過去 / 外部」資料 | long format（單筆 1 metric） | **軌 1 — 錄入軌** |
| 3 即時監控 | simulator 每秒生成 + WebSocket 推送 | 沒明說但「每秒 1 筆」+「異常閾值」暗示需要 wide 或多 metric 結構 | **軌 2 — 即時軌** |
| 4 資料分析 | 跨「錄入 + 即時」做統計 / 時間 / 分類 / 匯出 | 讀兩軌做分析 | **兩軌的 consumer** |
| 5.5「即時資料的歷史資料查詢」 | 軌 2 即時資料的歷史 | 同軌 2 schema | 屬於軌 2 |

**雙軌的本質差異（需求文檔明確/暗示）**：

| 比較項 | 軌 1 — 錄入軌（資料管理） | 軌 2 — 即時軌（即時監控） |
|---|---|---|
| 觸發者 | 使用者人工 / 上傳 CSV / API POST | simulator / sensor 自動 |
| 頻率 | 任意（補登 / 一次批匯入 500 筆 / inline 改） | **每秒 1 筆固定**（docx 段落 D 明寫） |
| 內容單元 | 1 row = 1 metric + 1 timestamp（title/value/category/recorded_at）| 1 row = **全部 5 metric snapshot**（推送一次帶 temperature/humidity/pressure/voltage/cpu_usage 全套） |
| 推送機制 | 無，使用者主動 fetch | **WebSocket 即時推送**（docx 段落 D 明寫） |
| CRUD 權限 | 創建者或 Admin（docx 段落 C 明寫） | simulator 自動寫，使用者不可改（推論） |
| 異常標記 | 使用者自己標 `is_anomaly` flag | 系統自動判定 `anomaly_flags` |
| 用途 | 外部資料整合 / 補資料 / 自訂量測 | 現場即時監控 / 告警 |

### 1.3 「資料管理 vs 系統管理 5.5 即時資料的歷史資料查詢」是同一回事嗎？

**結論：完全不是同一回事**。這是這份需求文檔最容易被誤讀的兩個點。

| 比較項 | 資料管理（模組 2）| 即時資料的歷史資料查詢（模組 5.5）|
|---|---|---|
| 角色 | User / Admin 都可用 | **Admin 專用**（docx 段落 F「Admin 專用」明寫） |
| 資料源 | 軌 1 錄入資料（CSV / inline） | 軌 2 即時資料的**過去**snapshot |
| 寫入 | 可 CRUD | 唯讀（admin 也不能改） |
| Schema | long（data_records 表） | wide（realtime_metrics_wide 表） |
| 用途 | 整理 / 分析「自己匯入」資料 | 追根本原因 / 異常事後重播 |

**這個區分對 demo narrative 極關鍵**：candidate 若把這兩件事混為一談（例如把即時資料寫進 data_records 表），就會破壞 wide vs long 的設計初衷，也會讓系統管理頁的「即時資料歷史」功能無從實作。

### 1.4 雙軌共同來源於同一個監控系統的 5 個 metric

從 `docs/sample_data.csv` 的 category 欄位（5/26 17:50 懷特看到的「示範 CSV」）：

```
temperature, humidity, pressure, voltage, cpu_usage
```

對齊 `frontend/streamlit_app/pages/3_分析報表.py:71` 的 `_KNOWN_CATEGORIES`：

```python
_KNOWN_CATEGORIES = ["（全部）", "temperature", "humidity", "pressure", "voltage", "cpu_usage"]
```

對齊 `backend/app/models/realtime_metric_wide.py:25-29` 的 5 個欄位：

```python
temperature, humidity, pressure, voltage, cpu_usage
```

**證據鎖死**：sample CSV 的 category 五選一 = realtime wide 表的五欄 = 分析報表 selectbox 的五選項。**這是同一個監控系統的同一組 5 metric，只是被裝在兩個 schema 容器**。

### 1.5 需求文檔背後的設計目的（推論）

把 docx 5 個模組合起來看，需求方（Wiwynn 招募方）期待的是：

> 「一個能**同時處理『機器自動 1 秒 1 筆推送』**+**『人工/匯入歷史/外部資料補登』**的 SaaS 即時監控雛形，並能對兩軌做統一分析、Excel 匯出、Admin 後台查歷史」

**這個解讀有幾個關鍵推論**：

1. **「即時」+「批量導入 CSV/JSON」並列在需求文檔**（模組 3 + 模組 2.5）= 招募方明知這是兩個 ingestion path
2. **「資料管理」明寫「標題、數值、分類、時間戳」**（docx 段落 C）= long format 欄位設計（單筆 1 metric）
3. **「即時監控」明寫「每秒生成」+「資料異常告警」**（docx 段落 D）= 高頻寫入 + per-snapshot 全套 metric（wide 自然選擇）
4. **「資料分析模組」需要跨兩軌統合**（docx 段落 E「統計分析」「分類資料聚合」沒指定來源）= 招募方期待 candidate 自己處理兩軌統一閱讀

→ 招募方雖然沒明寫「請用 wide + long 兩個 schema」，但**從業務需求自然推導出來的最合理工程方案就是雙軌**。Candidate 的設計符合需求文檔的設計意圖。

---

## Section 2: 我（大總管）的解讀是否正確？評分與校正

**整體評分：8.5 / 10**（大方向正確，部分細節需修正）

### 2.1 正確的部分 ✅

| # | 我的原話 | 正確性 | 證據 |
|---|---|---|---|
| 1 | 「軌 1：即時監控 — sensor/simulator 自動每秒推送『現在』資料（realtime_metrics_wide 表）」 | ✅ 完全正確 | `realtime_metric_wide.py:18-30` wide 表確實存 simulator/WS 推送 |
| 2 | 「軌 2：資料管理 — 使用者透過 UI / CSV 匯入『過去 / 外部』歷史資料（data_records 表）」 | ✅ 完全正確 | `data_record.py:22-43` long 表存 title/value/category/recorded_at 對齊 docx 段落 C |
| 3 | 「兩者同 5 metric category（temperature/humidity/pressure/voltage/cpu_usage）」 | ✅ 完全正確 | sample_data.csv + `3_分析報表.py:71` + wide 表三方鎖死 |
| 4 | 「schema 不同是工程權衡」 | ✅ 完全正確 | wide 適合高頻 + 跨 metric 同 timestamp 查詢；long 適合任意補登 + 異質 category |
| 5 | 「分析報表用 source toggle 讓使用者切兩軌做比較分析」 | ✅ 正確 | `3_分析報表.py:90-94, 156-161, 393-398` 三個 source toggle 確實是雙軌切換 UI |

### 2.2 需要修正的部分 ⚠️

| # | 我的原話 | 修正 | 理由 |
|---|---|---|---|
| M1 | 「資料管理 — 使用者透過 UI / CSV 匯入『過去 / 外部』歷史資料」 | **校正**：不只「過去 / 外部」，也可以是「現在的人工標註」（如使用者手動標 anomaly、新增自訂 metric 試驗值） | docx 段落 C 沒限定時間性，只說「創建資料記錄」 |
| M2 | 隱含「即時軌只能讀不能寫」 | **校正**：即時軌的「寫」是 simulator 寫 + admin 可改 `app_settings` 異常閾值間接影響，但「raw snapshot」確實 user 不可改 | 嚴格說「即時軌唯讀」對 user/viewer 對，但 admin 可改 threshold = 間接影響軌 2 |
| M3 | 「schema 不同是工程權衡」說得太輕 | **校正**：schema 不同**不只是 nice-to-have 的工程權衡，而是業務本質的反映**。wide 反映「全套 metric 同時刻 snapshot」這個物理事實，long 反映「人工補登可能只記得 1 個欄位」這個業務事實。這是「業務驅動 schema 選擇」的好範例，是 candidate 的設計賣點，不該被當作 trade-off 弱化 | 招募方應該對「為什麼這樣設計」感興趣，candidate 應該主動 surface 這個設計理由（pm-strategy P0-2 onboarding micro-copy 缺失） |

### 2.3 我沒提到但很重要的觀點 💡

#### 補充 #1：兩軌的「來源語意」差異不只是寫入頻率

我原本只說「sensor 自動 vs UI 手動」，但更深層的差異是「**權威性**」：

- **軌 2 即時軌**：machine-generated → ground truth，可信度高
- **軌 1 錄入軌**：human-generated → 可能有錯字、可能補登時記錯、可能類別填錯

所以**分析報表 source toggle 不只是「切資料源」，也是「切信任度層級」**。User 用 records source 做趨勢分析需要警覺「我自己上傳的資料品質如何」；用 realtime source 不需要懷疑資料品質但要懷疑「sensor 有沒有壞」。

**對 UI 的暗示**：分析報表 source toggle 旁邊應該加一行 caption 解釋「源頭差異」，讓 user 知道自己選的是什麼。

#### 補充 #2：雙軌設計也支援「人機混合驗證」use case

這是 Wiwynn 業務情境特別重要的：

- 工廠 sensor 自動推送軌 2 即時資料
- 工程師現場用儀器測量得到「金標準」數值，透過軌 1 補登
- 分析報表能對比「sensor 即時讀數」vs「金標準補登」→ 校正 sensor

→ 這是製造業真實工作流。Candidate 沒在 README 或頁面 caption 提這個業務情境（用過去/外部資料這種抽象描述），等於把 Wiwynn 招募方最在意的「業務 sense」訊號浪費掉。

#### 補充 #3：雙軌資料融合在 unified-summary endpoint 已實作

`3_分析報表.py:97-103` 已經有 `_fetch_unified_summary`，呼叫 `/analytics/unified-summary?source=both/realtime/records` 拿融合統計。**這是 candidate 設計裡最強的雙軌 surface**，但完全沒在 UI 上強調這個 endpoint 的價值。M2 metric card「合計筆數」沒解釋怎麼合計，user 完全看不出「這數字是兩軌加總」（pm-strategy 模組 4 #4.5 落差也提到此點）。

#### 補充 #4：5/26 17:50 懷特看到的 sample CSV 與即時資料「schema 不一樣」是 features 不是 bugs

懷特當下的判斷「schema 不一樣」**字面上正確但語意上錯位**。正確的描述應該是：

> 「sample CSV 是軌 1 錄入軌的範例資料，軌 2 即時資料的 schema 不同，因為前者每筆只記 1 個 metric（適合人工補登）、後者每筆記全部 5 個 metric（適合 1 秒 1 筆 snapshot）。兩軌都記同一組 5 metric 但裝在不同容器。」

這個 narrative 必須出現在 UI / README / 資料管理頁 caption 上，否則 5/26 17:50 的疑惑會在評審 Eric 開 demo 5 分鐘內再次發生。**這是本次 audit 觸發點，也是必補的最大 UX 缺口**。

#### 補充 #5：雙軌設計是 RBAC 行為差異的根因

| 角色 | 軌 1 錄入軌 | 軌 2 即時軌 |
|---|---|---|
| Admin | 可改任何 record | 不可改 raw snapshot 但可改 threshold（間接影響軌 2 anomaly flag）|
| User | 可改自己 record | 唯讀 |
| Viewer | 唯讀 | 唯讀 |

**雙軌 × 三角色 = 6 種行為**。目前 UI 只表達了「軌 1 RBAC」（資料管理頁有 inline edit + 權限矩陣），**軌 2 完全沒表達「即時軌沒人可以改 raw snapshot」這件事**。這是評審追問 RBAC 細節時會踩雷的點。

---

## Section 3: 使用者旅程審視（4 persona × 雙軌使用場景）

> Focus 在「雙軌資料如何被使用」與「使用者是否能理解雙軌」。

### 3.1 Persona A — Admin 林佳穎

**JTBD（雙軌相關）**：「異常發生時，我要對比 sensor 即時讀數（軌 2）vs 工程師現場補登的人工量測（軌 1），確認 sensor 是否誤報。」

**現況旅程**：

| Stage | 動作 | 期待對雙軌理解 | 實際 | Friction |
|---|---|---|---|---|
| A1 | 收到 PagerDuty 進系統 | 知道告警源自軌 2 即時 | Dashboard `1_儀表板.py:147-155` 4 metric card「合計 / 即時 / 錄入 / 異常」**確實有分軌呈現** ✅ | 但「異常筆數（合計）」沒分「即時軌異常 N + 錄入軌異常 M」→ admin 看不出告警是從哪軌來 |
| A2 | 切到即時監控頁查當下 sensor | 確認是純軌 2 視圖 | `4_即時監控.py` 整頁都是軌 2，沒人工 record 混入 ✅ | 但頁面沒明寫「本頁僅顯示即時軌資料」→ admin 不知道有沒有混 |
| A3 | 切到資料管理頁看工程師有沒有補登人工量測 | 確認是純軌 1 視圖 | `2_資料管理.py` 整頁都是軌 1 ✅ | caption line 51 完全沒提「這是與即時資料分開的錄入軌」 |
| A4 | 切到分析報表用 source=both 對比兩軌 | 看到 sensor 平均 vs 工程師補登平均 | `3_分析報表.py:119-123` 4 metric card「合計筆數 / 合計異常 / 即時筆數 / 錄入筆數」**已分軌呈現** ✅ | 但 metric card 沒 tooltip 解釋「即時來自 simulator、錄入來自人工」 |
| A5 | 切到系統管理 Tab 4「即時資料歷史」追根本原因 | 看軌 2 過去資料 | `5_系統管理.py:412-526` 確實是軌 2 歷史 | 但圖表跟「即時監控頁」幾乎一樣（pm-strategy P1-1 第 9 項）→ admin 不確定差別在哪 |

**Admin 對雙軌的理解**：**部分清楚**（看到 metric card 有分軌呈現）但**缺乏 explicit explanation**（沒 tooltip / caption 解釋兩軌差別）。Admin 若是 Wiwynn 內部資深工程師可能自己推導出來，新手 admin 會迷路。

**評分**：6 / 10

### 3.2 Persona B — User 陳家豪

**JTBD（雙軌相關）**：「我手上有 CSV 資料（軌 1）想匯入系統，然後跟 simulator 自動推送的（軌 2）對比畫趨勢圖，看我的測量數值跟 sensor 是否一致。」

**現況旅程**：

| Stage | 動作 | 期待對雙軌理解 | 實際 | Friction |
|---|---|---|---|---|
| B1 | 進資料管理頁準備上傳 CSV | 知道這頁是軌 1 入口 | caption line 51 完全沒提「軌 1 / 軌 2 區分」「跟即時資料的關係」 ❌ | user 不知道上傳完後資料會怎麼被即時監控頁使用（答案是：不會，因為兩軌分開），可能會期待「上傳 CSV 後即時監控會自動顯示」 |
| B2 | 上傳 sample_data.csv 60 筆 | 知道這些資料存在 data_records | 確實如此 ✅ | 但 user 不知道「為什麼即時監控頁沒有出現我剛上傳的 60 筆」 |
| B3 | 切到即時監控想看自己 CSV 的趨勢 | 期待看到自己上傳的資料 | **看不到**，即時監控頁只顯示軌 2 simulator 資料 ❌ | **user 預期被破壞** — 因為頁面沒解釋兩軌分開 |
| B4 | 切到分析報表 source=records 才看到自己 CSV | 期待 source toggle 旁邊有解釋 | source selectbox label「錄入資料（data_records）」`3_分析報表.py:158` 有提 data_records 表名 ✅ | 但 user 不懂 data_records 是什麼，沒有「您剛剛上傳的 CSV 在這裡」這種敘事性連結 |
| B5 | 切 source=realtime 想看 simulator 資料 | 期待看到 sensor 自動資料 | label「即時資料（realtime）」`3_分析報表.py:159` ✅ | 但 user 不懂「即時是不是包含我的 CSV」（答案：不包含） |

**User 對雙軌的理解**：**極不清楚**。User 沒 IT 背景看不出 data_records vs realtime_metrics_wide 的差別，會經歷「上傳 CSV → 即時監控看不到 → 困惑 → 自己摸索切 source toggle 才理解」這個 3-5 分鐘的試錯期。

**評分**：3 / 10（最低）

### 3.3 Persona C — Viewer 王主管

**JTBD（雙軌相關）**：「週會前 30 秒看一下系統健康。我不在乎軌 1 軌 2 的技術差異，我要看『過去一週系統有沒有異常 + 趨勢 OK』。」

**現況旅程**：

| Stage | 動作 | 期待對雙軌理解 | 實際 | Friction |
|---|---|---|---|---|
| C1 | 登入跳 Dashboard | viewer 不在乎雙軌 | Dashboard 4 metric card 把「即時 / 錄入」分軌呈現 ⚠️ | viewer **不需要知道分軌**，看到「即時筆數 / 錄入筆數」兩張卡反而增加認知負荷 |
| C2 | 想看分析報表趨勢 | 期待「總覽不分軌」的趨勢 | 分析報表頂部 source toggle 預設「兩者」 ✅ | 但 source toggle 對 viewer 是雜訊（他不需要切） |

**Viewer 對雙軌的理解**：**不需要理解，但目前 UI 把雙軌複雜度暴露給他**。Viewer 應該只看到「合計筆數 / 合計異常率」這種跨軌統合數字，不需要看「即時 N / 錄入 M」分軌呈現。

**對 UI 的啟示**：考慮在 Dashboard 與分析報表加「進階模式」toggle，預設關閉，關閉時只顯示跨軌統合數字；admin/user 想看分軌時再開。或更激進：Dashboard metric card 順序改成「合計 → 異常率 → 即時 → 錄入」，前兩張對 viewer 友善，後兩張對 admin/user 才有用。

**評分**：5 / 10（不爛但有認知負荷）

### 3.4 Persona D — 評審工程師 Eric（最關鍵）

**JTBD（雙軌相關）**：「我要在 5-10 分鐘看出 candidate 的『系統設計能力』，雙軌設計（wide + long 兩 schema 並存）就是這題的招牌設計賣點，我要確認 candidate 有意識地做這個 trade-off 還是不小心做的。」

**現況旅程**：

| Stage | 動作 | 期待對雙軌理解 | 實際 | Friction |
|---|---|---|---|---|
| E1 | 開 README | 想第一眼看到「雙軌設計」說明 | **README 完全沒提「雙軌」概念** ❌ | README 「功能模組」section 把「資料管理」「即時監控」並列當 5 個 module，沒講「這兩個其實是同一個監控系統的兩條 ingestion path」← **這是評審 5 秒內想看到的設計理由** |
| E2 | 開 docs/architecture.md | 想看 ER 圖區分兩 schema | （未在此 audit 範圍，但 pm-strategy §1.2 提到 ER 圖存在）⚠️ | ER 圖即使有也藏在 docs/ 子目錄，評審不一定會點 |
| E3 | 開 demo 進資料管理頁 | 想看 caption 解釋「這頁的資料來源是什麼 / 跟即時資料的關係」 | caption line 51 寫「您可以在這裡管理資料：上傳 CSV / JSON 批量匯入、用篩選條件搜尋已有資料、inline 編輯欄位後一次儲存」 ❌ | **完全沒提軌 1 / 軌 2 區分**，評審看不出 candidate 是不是有意識地做雙軌 |
| E4 | 開即時監控頁 | 想看 caption 解釋「這頁僅顯示軌 2 即時資料，與資料管理頁分開」 | （即時監控頁 caption 在 ux-research §2.5 多處被檢視但都沒提雙軌）❌ | 同上 friction |
| E5 | 開分析報表頁看 source toggle | 想看 toggle 旁邊解釋「records vs realtime」差別 | source toggle label 寫 `錄入資料（data_records）` / `即時資料（realtime）` `3_分析報表.py:157-160` ⚠️ | **這是 candidate 唯一 surface 雙軌設計的地方**，但 label 寫「data_records」用 schema 名而非業務名（如「人工錄入 / 上傳 CSV」「sensor 自動推送」）→ 評審看到 schema 名能猜出來，但不夠直白 |
| E6 | 開 docs/sample_data.csv | 想看「這 CSV 對應哪一軌」說明 | CSV 沒任何 header 註解 ❌ | 評審看到 CSV 第 1 行 `title,value,category,recorded_at` 對齊 docx 段落 C 的 long format，能推出這是軌 1，但**沒明寫**讓評審浪費 30 秒推導 |

**評審對雙軌的理解**：**能推導出來但需要時間 + 沒直接證據**。Candidate 沒有任何「設計理由 callout」surface 這個雙軌決策，等於把最強的設計賣點藏起來（ux-research §1 Persona D 痛點 3 同論點）。

**評分**：4 / 10（致命傷，因為這是面試題最該 surface 的設計賣點）

### 3.5 4 persona × 雙軌理解度總結

| Persona | 雙軌理解度 | 主要 Friction |
|---|---|---|
| A Admin | 6/10 | metric card 分軌呈現但沒 tooltip 解釋 |
| B User | 3/10（最低） | 上傳 CSV 後預期破壞，沒任何頁面解釋兩軌分開 |
| C Viewer | 5/10 | 不需要知道但 UI 暴露雙軌複雜度給他 |
| D 評審（最關鍵） | 4/10 | candidate 把最強設計賣點藏起來，README / caption 全沒提雙軌 |

**統合洞察**：雙軌設計本身是 candidate 的工程強項，**但目前 UI/UX 完全沒把這個強項 surface 出來**。對 admin / user / viewer 是「沒講清楚 → 困惑」；對評審是「沒講清楚 → 設計能力被低估」。

---

## Section 4: UI/UX 體現審視（Top 5 好 + Top 5 gap）

### 4.1 「雙軌設計被清楚體現」的 Top 5 好設計 ✅

#### G1 — 分析報表 unified summary 4 metric card 分軌呈現

- **位置**：`3_分析報表.py:119-123`
- **設計**：4 個 metric card「合計筆數 / 合計異常 / 即時筆數 / 錄入筆數」第 3、4 卡明確分軌
- **為什麼好**：admin / 評審看一眼即知「系統有兩條 ingestion path 各 N 筆」
- **可強化**：每張卡加 `help=` tooltip 解釋來源（見 Section 5 建議 #2）

#### G2 — 分析報表 source toggle 切兩軌

- **位置**：`3_分析報表.py:90-94, 156-161, 393-398` 三處 source selectbox
- **設計**：「兩者（即時+錄入）/ 僅即時資料 / 僅錄入資料」三選一
- **為什麼好**：這是整個系統最直白 surface 雙軌的 UI 元件
- **可強化**：label 改成業務語言而非 schema 名（見 Section 5 建議 #3）

#### G3 — `/analytics/unified-summary` endpoint 後端有實作雙軌融合

- **位置**：`3_分析報表.py:97-103` 呼叫端 + 後端對應 endpoint
- **設計**：API 支援 `source=both/realtime/records` 參數，後端做跨軌聚合
- **為什麼好**：candidate 不只 UI 層分軌，連 API 層都明確設計成「軌融合 endpoint」+「軌分流 endpoint」並存
- **可強化**：在 README API 速查表（line 88-98）標註此 endpoint 的雙軌設計賣點

#### G4 — 即時監控頁完全只顯示軌 2，沒混入錄入資料

- **位置**：`4_即時監控.py`（371 行整頁）
- **設計**：WebSocket + REST `/realtime/history` 都只查 realtime_metrics_wide 表，沒查 data_records
- **為什麼好**：清楚的「即時 = 軌 2 only」單一語意，避免雙軌混淆
- **可強化**：頁面 title 下方加 caption 明寫「本頁僅顯示即時感測資料（軌 2）」（見 Section 5 建議 #4）

#### G5 — 資料管理頁 inline edit 只能改軌 1 資料

- **位置**：`2_資料管理.py:151-168` data_editor 的 column_config 用 long format（標題 / 數值 / 類別 / 記錄時間）對齊軌 1 schema
- **設計**：data_editor 改的是 data_records 表，不能改 realtime_metrics_wide
- **為什麼好**：清楚的「inline edit = 軌 1 only」單一語意，避免 user 期待能改 sensor 即時資料
- **可強化**：頁面 title 下方加 caption 明寫「本頁管理錄入資料（軌 1），如需查看 sensor 即時資料請至『即時監控』頁」（見 Section 5 建議 #1）

### 4.2 「雙軌設計沒清楚體現」的 Top 5 UX gap ❌

#### Gap-1 — README 沒有「雙軌設計」概念說明（**致命**）

- **位置**：`README.md`（281 行全文）
- **觀察**：「功能模組」section（line 5-13）把「資料管理」「即時監控」並列為 5 個 module，沒講兩者是「同一監控系統的雙軌 ingestion」
- **影響 persona**：D 評審（致命）+ A admin / B user 首次使用
- **嚴重度**：致命（評審 5 秒內看不到設計賣點）
- **修補方向**：在「功能模組」table 之後、「技術棧」之前，加一個「雙軌資料架構」section（見 Section 6 spec）

#### Gap-2 — 資料管理頁 caption 沒提「跟即時資料的關係」

- **位置**：`2_資料管理.py:51`
- **觀察**：caption 寫「您可以在這裡管理資料：上傳 CSV / JSON 批量匯入、用篩選條件搜尋已有資料、inline 編輯欄位後一次儲存。Viewer 角色為唯讀，User 只能編輯自己的資料，Admin 可編輯所有資料。」**完全沒提「這是軌 1 錄入軌、與即時監控頁分開」**
- **影響 persona**：B user（極高，會期待上傳 CSV 後即時監控頁看到）+ D 評審（高）
- **嚴重度**：高（B user 體驗 broken expectation）
- **修補方向**：caption 末尾加「本頁管理使用者錄入資料（軌 1），與即時監控頁的 sensor 自動推送資料（軌 2）分開存儲。如需跨軌比較分析請至『分析報表』頁。」

#### Gap-3 — 分析報表 source toggle 用 schema 名（data_records / realtime）不是業務名

- **位置**：`3_分析報表.py:157-160, 394-397`
- **觀察**：toggle label 寫「錄入資料（data_records）」「即時資料（realtime）」，schema 名只有工程師看得懂
- **影響 persona**：B user（中-高，看不懂 data_records）+ C viewer（中）+ D 評審（低，但會懷疑 candidate UX sense）
- **嚴重度**：中-高
- **修補方向**：label 改成業務語言：「使用者錄入資料（CSV / 手動）」「Sensor 即時推送資料」+ 旁邊加 `help=` tooltip 1 行解釋來源差異（見 Section 5 建議 #3）

#### Gap-4 — `docs/sample_data.csv` 沒 header 註解說明「這對應哪一軌」

- **位置**：`docs/sample_data.csv:1-61`
- **觀察**：CSV 第 1 行直接是 `title,value,category,recorded_at`，沒任何 `#` comment 解釋這 60 筆對應哪一軌
- **影響 persona**：D 評審（中-高，會打開 CSV 看格式）+ B user（中，下載 sample 後不知用途）
- **嚴重度**：中
- **修補方向**：CSV 第 0 行加 5 行 `#` comment header 解釋（見 Section 6 spec）。或在 README 「範例資料」section（line 127-131）擴充。

#### Gap-5 — Dashboard 4 metric card 沒解釋「即時 vs 錄入」差別

- **位置**：`1_儀表板.py:147-155`（per ux-research §2.2 D-1 痛點）
- **觀察**：4 個 card「合計資料筆數 / 即時資料筆數 / 錄入資料筆數 / 異常筆數（合計）」第 2、3 卡分軌呈現但沒 tooltip 解釋「即時」「錄入」是什麼
- **影響 persona**：C viewer（高，看不出系統健康）+ B user（中）+ A admin（中）+ D 評審（中）
- **嚴重度**：高（pm-strategy P0-3 + D-1 已論證）
- **修補方向**：每張 card 加 `help=` tooltip + 改 label 從「即時資料筆數」→「即時資料筆數（軌 2，sensor 推送）」（見 Section 5 建議 #2）

### 4.3 補充：「雙軌設計沒清楚體現」次要 gap（未進 Top 5）

- **Gap-6**：即時監控頁 title 下方沒 caption（依 ux-research §2.5 多處未檢驗，但比對 `2_資料管理.py:51` 確實沒）→ 評審切到此頁不知道「這頁只顯示軌 2」
- **Gap-7**：系統管理 Tab 4「即時資料歷史」與「即時監控」頁圖表幾乎重複（pm-strategy P1-1 第 9 項）→ 評審混淆「為什麼有兩個一樣的頁」，但其實一個是 admin-only 後台歷史、一個是 user-facing 即時，這個語意差也沒在 UI 表達
- **Gap-8**：分析報表「類別分佈」section（`3_分析報表.py:391-475`）source toggle 改 cat_source 後左右兩 bar chart 切換 records / realtime，但**標題沒同步改**（cat_label 變數有處理但仍模糊）→ user 切了不確定看的是哪軌

---

## Section 5: 補強建議優先級（5-8 條，含 file:line 與工時）

> 按 **「對評審 demo 成敗影響 × 工時 ROI」** 排序。

### 補強 #1（**最高優先**）— README 加「雙軌資料架構」section

- **改哪個 file:line**：`README.md` 第 13 行（「功能模組」table 結尾）之後、第 15 行「技術棧」之前
- **補什麼內容**：3 段內容
  - 一段 200 字「雙軌設計理由」說明
  - 一個 2-column table 比較軌 1 vs 軌 2
  - 一個 mermaid flowchart 標雙軌資料流（or 連結到 docs/architecture.md）
- **對 demo narrative 的影響**：**致命修復**。評審 5 秒看到「雙軌設計」這個 keyword，立刻把 candidate 從「做完需求」升級到「有設計思考」評等
- **預估工時**：30 分鐘
- **完整 spec**：見 Section 6.1

### 補強 #2（**極高優先**）— Dashboard 4 metric card 加 tooltip + 改 label

- **改哪個 file:line**：`1_儀表板.py:147-155` 4 個 `st.metric()` 全改
- **補什麼內容**：
  - card 1 label「合計資料筆數」+ help「= 即時資料 + 錄入資料（兩軌統合）」
  - card 2 label「即時資料筆數（軌 2）」+ help「Sensor / Simulator 每秒自動推送的 snapshot 數」
  - card 3 label「錄入資料筆數（軌 1）」+ help「使用者透過 CSV 匯入或 inline edit 新增的 record 數」
  - card 4 label「異常筆數（合計）」+ help「兩軌總異常數，超過閾值會自動標記」
- **對 demo narrative 的影響**：viewer / 評審 hover 5 秒即理解雙軌
- **預估工時**：15 分鐘
- **完整 spec**：見 Section 6.2

### 補強 #3（**極高優先**）— 分析報表 source toggle 改業務語言 + 加 help text

- **改哪個 file:line**：`3_分析報表.py:92, 156-160, 393-397` 三處 selectbox
- **補什麼內容**：
  - 修正 label：`錄入資料（data_records）` → `使用者錄入資料（CSV / 手動）`、`即時資料（realtime）` → `Sensor 即時推送資料`
  - 每個 selectbox 加 `help=` 1 行 tooltip 解釋
  - 第 92 行 summary selectbox 加 caption「『兩者』= sensor 自動推送（軌 2）+ 使用者錄入（軌 1）統合」
- **對 demo narrative 的影響**：user 切 source 即知差別、評審看到「軌 1 / 軌 2」業務名稱判讀正確
- **預估工時**：20 分鐘
- **完整 spec**：見 Section 6.3

### 補強 #4（**高優先**）— 資料管理頁 caption 補軌 1 / 軌 2 區分

- **改哪個 file:line**：`2_資料管理.py:51`
- **補什麼內容**：caption 末尾加 1 句「本頁管理使用者錄入資料（軌 1），與即時監控頁的 sensor 自動推送資料（軌 2）分開存儲。如需跨軌比較分析請至『分析報表』頁。」
- **對 demo narrative 的影響**：B user 上傳 CSV 前就知道「即時監控頁看不到」、評審看到 candidate 主動 surface 雙軌
- **預估工時**：5 分鐘
- **完整 spec**：見 Section 6.4

### 補強 #5（**高優先**）— 即時監控頁 title 下方加 caption

- **改哪個 file:line**：`4_即時監控.py:86` `st.title("即時監控")` 之後
- **補什麼內容**：`st.caption("本頁即時顯示 sensor / simulator 每秒推送的 5 個 metric（軌 2）。如需查看使用者手動錄入或 CSV 匯入資料（軌 1），請至『資料管理』頁。歷史資料分析請至『分析報表』頁。")`
- **對 demo narrative 的影響**：與補強 #4 對稱，雙向標清軌道
- **預估工時**：5 分鐘
- **完整 spec**：見 Section 6.5

### 補強 #6（中優先）— `docs/sample_data.csv` 加 header 註解

- **改哪個 file:line**：`docs/sample_data.csv` 第 0 行（在 header line 之前）
- **補什麼內容**：5 行 `#` comment 說明「本檔對應軌 1 錄入軌」+ schema 欄位 + 60 筆內容 breakdown
- **注意**：標準 RFC 4180 CSV 不支援 comment row，但 pandas `read_csv(comment='#')` 支援。需驗證 backend bulk-import 是否會忽略 `#` 開頭行（如不忽略，改放 README + 在 CSV 前單獨建 `docs/sample_data.README.md`）
- **對 demo narrative 的影響**：評審打開 CSV 看 schema 時 5 秒理解這是哪軌
- **預估工時**：15 分鐘（含驗證 backend 是否吞 comment row）
- **完整 spec**：見 Section 6.6

### 補強 #7（中優先）— Dashboard 上方加「雙軌資料總覽」卡片

- **改哪個 file:line**：`1_儀表板.py` 在 `st.title("儀表板")` 與 system status header 之間插入新區塊
- **補什麼內容**：`st.container(border=True)` 內含
  - 一段 markdown「**本系統雙軌架構**」+ 1 行 80 字說明
  - 2-column 對照表：軌 1 錄入 / 軌 2 即時
  - 每軌的「今日筆數」+「今日異常數」+ 「最後寫入時間」3 個 derived metric
- **對 demo narrative 的影響**：評審登入後第一視覺就看到雙軌設計賣點
- **預估工時**：1.5 小時（需要 backend `/analytics/unified-summary` 加「last_write_at」per source 欄位 or FE 自己算）
- **注意**：與 pm-strategy §4 方案 A「Dashboard 頂部固定權限矩陣卡片」會搶頂部位置，需協調（建議：權限矩陣放右、雙軌總覽放左，2-column 並排）
- **完整 spec**：見 Section 6.7

### 補強 #8（中-低優先）— 系統管理 Tab 4 「即時資料歷史」 title 改名

- **改哪個 file:line**：`5_系統管理.py` Tab 4 的 title section（line 範圍需驗）
- **補什麼內容**：將 tab 名「即時資料歷史」改成「軌 2 即時資料歷史查詢（Admin 後台）」+ tab 內 page title 下方加 caption 解釋「與『即時監控』頁差別：本頁支援自訂時間範圍 + Excel 匯出，即時監控頁僅顯示最近 60 秒」（如果 caption 描述為真，否則 surface 真實差別）
- **對 demo narrative 的影響**：評審切到此 tab 不會混淆「為什麼有兩個一樣的頁」（pm-strategy P1-1 第 9 項）
- **預估工時**：10 分鐘
- **完整 spec**：見 Section 6.8

### 5.9 補強建議優先級總覽

| # | 補強 | 優先級 | 工時 | ROI |
|---|---|---|---|---|
| 1 | README 加「雙軌資料架構」section | 最高 | 30 分 | 極高 |
| 2 | Dashboard metric card tooltip + label | 極高 | 15 分 | 極高 |
| 3 | 分析報表 source toggle 改業務語言 | 極高 | 20 分 | 高 |
| 4 | 資料管理頁 caption 補軌 1/2 區分 | 高 | 5 分 | 高 |
| 5 | 即時監控頁加 caption | 高 | 5 分 | 高 |
| 6 | sample_data.csv 加 header 註解 | 中 | 15 分 | 中 |
| 7 | Dashboard 加「雙軌資料總覽」卡片 | 中 | 90 分 | 中-高 |
| 8 | 系統管理 Tab 4 改名 + caption | 中-低 | 10 分 | 中 |

**累計工時：3 小時 10 分**（補強 #1-#5 + #6 + #8 = 1 小時 40 分鐘解決 80% 影響度；補強 #7 額外 90 分鐘解決剩餘 20%）

---

## Section 6: 給 frontend-engineer 的具體 spec

> 此 section 是給下一個 sub-agent（frontend-engineer）的逐項施工指南，每條含「改哪個檔 / 改在哪 / 改成什麼字 / 驗收標準」。

### 6.1 README 加「雙軌資料架構」section（補強 #1）

**目標檔**：`/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/README.md`

**插入位置**：第 13 行「功能模組」table 結尾 `| 系統管理（Admin）| 使用者列表 / 系統日誌 / DB 連線池狀態 / 即時資料歷史查詢 / 動態調整異常閾值 |` 之後、第 14 行空行之前

**插入內容**（Markdown）：

```markdown

## 雙軌資料架構

本系統採用「雙軌資料 ingestion」設計，對應需求文檔中「即時監控（每秒自動推送）」與「資料管理（CSV / 人工錄入）」兩個獨立模組：

| 比較項 | 軌 1 — 錄入軌（data_records）| 軌 2 — 即時軌（realtime_metrics_wide）|
|---|---|---|
| 觸發 | 使用者 CSV 匯入 / inline edit / POST `/data` | Simulator 每秒生成 + WebSocket 推送 |
| Schema | long（1 row = 1 metric） | wide（1 row = 全部 5 metric snapshot） |
| 欄位 | title, value, category, recorded_at | ts, temperature, humidity, pressure, voltage, cpu_usage, anomaly_flags |
| 異常標記 | 使用者自行標 `is_anomaly` | 系統依閾值自動判定 `anomaly_flags` |
| RBAC | 創建者 / Admin 可改 | 全唯讀（admin 可改閾值間接影響） |
| 用途 | 外部資料整合 / 人工補登 / 校正 sensor | 機房現場即時監控 / 異常告警 |

**兩軌共享同一組 5 個 metric category**（temperature / humidity / pressure / voltage / cpu_usage），可在「分析報表」頁透過 `source` toggle 切換或統合查看。

**雙軌設計動機**：
- 高頻 sensor 推送（每秒 1 筆）採用 wide 格式可單筆寫入完整 snapshot，降低 DB IO
- 人工補登 / CSV 匯入可能只記得 1 個 metric（如某時刻僅量到溫度），long 格式提供 schema 彈性
- 跨軌分析交由 backend `/analytics/unified-summary` endpoint 統合，前端透過 source toggle 切換視圖

詳細 ER 圖與資料流見 [docs/architecture.md](docs/architecture.md)。
```

**驗收標準**：
- README rendered 後在 GitHub 看到完整 table
- 「雙軌」「軌 1」「軌 2」keyword 各出現 ≥ 3 次
- 連結到 docs/architecture.md 可點

---

### 6.2 Dashboard 4 metric card tooltip + label（補強 #2）

**目標檔**：`/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/frontend/streamlit_app/pages/1_儀表板.py`

**改哪行**：line 147-155（4 個 `st.metric()`）

**改前**（推估，依 ux-research D-1 描述）：

```python
m1, m2, m3, m4 = st.columns(4)
m1.metric("合計資料筆數", combined.get("total", "—"))
m2.metric("即時資料筆數", realtime.get("total", "—"))
m3.metric("錄入資料筆數", records.get("total", "—"))
m4.metric("異常筆數（合計）", combined.get("anomaly_count", "—"))
```

**改後**：

```python
m1, m2, m3, m4 = st.columns(4)
m1.metric(
    "合計筆數（兩軌）",
    combined.get("total", "—"),
    help="= 軌 1 錄入資料 + 軌 2 即時資料的統合總數",
)
m2.metric(
    "軌 2 即時資料筆數",
    realtime.get("total", "—"),
    help="Sensor / Simulator 每秒自動推送的 wide snapshot 數（realtime_metrics_wide 表）",
)
m3.metric(
    "軌 1 錄入資料筆數",
    records.get("total", "—"),
    help="使用者透過 CSV 匯入或 inline edit 新增的 long format record 數（data_records 表）",
)
m4.metric(
    "異常筆數（合計）",
    combined.get("anomaly_count", "—"),
    help="兩軌總異常數：軌 1 由使用者標記、軌 2 由系統依動態閾值自動判定",
)
```

**驗收標準**：
- 4 個 card 都有 hover tooltip
- card 2 / card 3 都明確顯示「軌 X」前綴
- viewer 角色 hover 5 秒後能說出「即時 vs 錄入」差別

---

### 6.3 分析報表 source toggle 改業務語言 + help（補強 #3）

**目標檔**：`/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/frontend/streamlit_app/pages/3_分析報表.py`

**改哪行**：
- line 92-94（_SOURCE_OPTIONS）
- line 156-161（_TREND_SOURCE_OPTIONS）
- line 393-398（_CAT_SOURCE_OPTIONS）

**改前 line 92-94**：

```python
_SOURCE_OPTIONS = {"兩者（即時+錄入）": "both", "僅即時資料": "realtime", "僅錄入資料": "records"}
source_label = st.selectbox("資料來源", list(_SOURCE_OPTIONS.keys()), index=0, key="summary_source")
```

**改後 line 92-94**：

```python
_SOURCE_OPTIONS = {
    "兩軌統合（軌 1 + 軌 2）": "both",
    "僅軌 2（Sensor 即時推送）": "realtime",
    "僅軌 1（使用者錄入 / CSV）": "records",
}
source_label = st.selectbox(
    "資料來源",
    list(_SOURCE_OPTIONS.keys()),
    index=0,
    key="summary_source",
    help="軌 1 = 使用者透過 CSV 匯入或 inline edit 錄入的歷史 / 外部資料；軌 2 = Sensor 每秒自動推送的即時 snapshot。兩軌共享同一組 5 個 metric。",
)
```

**改前 line 156-161**：

```python
_TREND_SOURCE_OPTIONS = {
    "錄入資料（data_records）": "records",
    "即時資料（realtime）": "realtime",
}
trend_source_label = st.selectbox("趨勢圖資料來源", list(_TREND_SOURCE_OPTIONS.keys()), index=0, key="trend_source")
```

**改後 line 156-161**：

```python
_TREND_SOURCE_OPTIONS = {
    "軌 1 — 使用者錄入資料": "records",
    "軌 2 — Sensor 即時推送資料": "realtime",
}
trend_source_label = st.selectbox(
    "趨勢圖資料來源",
    list(_TREND_SOURCE_OPTIONS.keys()),
    index=0,
    key="trend_source",
    help="軌 1 顯示歷史 / 外部資料的時間趨勢（依您選擇的時間粒度 bucket）；軌 2 顯示過去 60 分鐘 sensor snapshot 的 5 個 metric 個別 small multiples。",
)
```

**改前 line 393-398**：

```python
_CAT_SOURCE_OPTIONS = {
    "錄入資料（data_records）": "records",
    "即時資料（realtime）": "realtime",
}
cat_source_label = st.selectbox("分佈資料來源", list(_CAT_SOURCE_OPTIONS.keys()), index=0, key="cat_source")
```

**改後 line 393-398**：

```python
_CAT_SOURCE_OPTIONS = {
    "軌 1 — 使用者錄入資料": "records",
    "軌 2 — Sensor 即時推送資料": "realtime",
}
cat_source_label = st.selectbox(
    "分佈資料來源",
    list(_CAT_SOURCE_OPTIONS.keys()),
    index=0,
    key="cat_source",
    help="軌 1 顯示使用者錄入資料的 category 分佈；軌 2 顯示 sensor 5 個 metric 的筆數 / 平均值分佈。",
)
```

**驗收標準**：
- 3 個 selectbox 全部使用「軌 1 / 軌 2」前綴
- 全部有 `help=` 1 行 tooltip
- 不再出現「data_records」「realtime」schema 名（避免 user 困惑）

---

### 6.4 資料管理頁 caption 補軌 1 / 軌 2 區分（補強 #4）

**目標檔**：`/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/frontend/streamlit_app/pages/2_資料管理.py`

**改哪行**：line 51

**改前**：

```python
st.caption("您可以在這裡管理資料：上傳 CSV / JSON 批量匯入、用篩選條件搜尋已有資料、inline 編輯欄位後一次儲存。Viewer 角色為唯讀，User 只能編輯自己的資料，Admin 可編輯所有資料。")
```

**改後**：

```python
st.caption(
    "**本頁管理軌 1 — 使用者錄入資料**（data_records 表）。"
    "您可以在這裡：上傳 CSV / JSON 批量匯入歷史或外部量測資料、用篩選條件搜尋已有 record、inline 編輯欄位後一次儲存。"
    "**與『即時監控』頁的軌 2 — Sensor 即時推送資料（realtime_metrics_wide 表）分開存儲**，如需跨軌比較分析請至『分析報表』頁。"
    "Viewer 角色為唯讀，User 只能編輯自己的資料，Admin 可編輯所有資料。"
)
```

**驗收標準**：
- caption 包含「軌 1」「軌 2」keyword
- caption 明確提到「分開存儲」+ 指引「分析報表」頁

---

### 6.5 即時監控頁加 caption（補強 #5）

**目標檔**：`/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/frontend/streamlit_app/pages/4_即時監控.py`

**改哪行**：line 86 `st.title("即時監控")` 之後（與其他頁面 `st.caption()` 位置對齊）

**補上內容**：

```python
st.caption(
    "**本頁即時顯示軌 2 — Sensor / Simulator 每秒推送的 5 個 metric snapshot**"
    "（realtime_metrics_wide 表，wide format）。"
    "WebSocket 連線即時推送，前端維護 60 秒滑動 buffer。"
    "**如需查看使用者手動錄入或 CSV 匯入資料（軌 1），請至『資料管理』頁**；"
    "歷史資料分析請至『分析報表』頁切換 source = 軌 2。"
)
```

**驗收標準**：
- caption 與資料管理頁 caption 對稱（雙向標清軌道）
- 包含「軌 2」keyword
- 指引使用者「軌 1 在資料管理頁」

---

### 6.6 sample_data.csv 加 header 註解（補強 #6）

**目標檔**：`/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/docs/sample_data.csv`

**改哪行**：第 0 行（在 `title,value,category,recorded_at` 之前）

**前置驗證**：先確認 `backend/app/services/bulk_import.py`（or 同等檔）是否能處理 `#` 開頭的 comment row：

```bash
grep -rn "comment\|skiprows\|skipinitialspace" backend/app/services/ backend/app/api/v1/data.py
```

**如果 backend 不支援 `#` comment**，把註解內容改放到「`docs/sample_data.README.md`」單獨檔案，並在 README line 127-131「範例資料」section 加連結。

**如果 backend 支援**，CSV 改後內容：

```csv
# 本檔為軌 1 — 使用者錄入資料範例（long format）
# 對應 backend.app.models.DataRecord（data_records 表）
# 60 筆資料跨 7 天，涵蓋本系統 5 個 metric category：temperature / humidity / pressure / voltage / cpu_usage
# 含 9 筆高異常 + 5 筆低異常（依預設 anomaly_threshold_high=80 / low=10 判定）
# 與軌 2 — Sensor 即時推送資料（realtime_metrics_wide wide format）分開存儲
title,value,category,recorded_at
室內溫度（°C）,85.58,temperature,2026-05-18T09:00:00Z
...
```

**驗收標準**：
- 前置驗證確認 backend 不會把 `#` 行當資料 import
- CSV 仍能透過 `/data/bulk-import` 成功匯入 60 筆（不變）
- 評審 open CSV file 第一眼看到「軌 1」說明

---

### 6.7 Dashboard 加「雙軌資料總覽」卡片（補強 #7，可選）

**目標檔**：`/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/frontend/streamlit_app/pages/1_儀表板.py`

**插入位置**：`st.title("儀表板")` 之後、system status header 之前（依 pm-strategy §4 方案 A 已預留此 slot 給「角色權限矩陣卡片」，需協調 2-column 並排）

**插入內容**：

```python
st.markdown("### 本系統雙軌資料架構")
st.markdown(
    "本系統採用「**雙軌資料 ingestion**」設計："
    "**軌 1（錄入軌）** = 使用者 CSV 匯入 / inline edit / API 手動建立；"
    "**軌 2（即時軌）** = Simulator 每秒自動推送 + WebSocket 訂閱。"
    "兩軌共享同一組 5 個 metric（temperature / humidity / pressure / voltage / cpu_usage）。"
)

track_col1, track_col2 = st.columns(2)
with track_col1:
    st.container(border=True)
    st.markdown("##### 軌 1 — 錄入軌（data_records）")
    # 從 unified.records 拉資料
    records_info = unified.get("records", {})
    st.metric("今日筆數", records_info.get("today_count", "—"))
    st.metric("今日異常", records_info.get("today_anomaly", "—"))
    st.caption(f"最後寫入：{records_info.get('last_write', '—')}")

with track_col2:
    st.container(border=True)
    st.markdown("##### 軌 2 — 即時軌（realtime_metrics_wide）")
    realtime_info = unified.get("realtime", {})
    st.metric("今日筆數", realtime_info.get("today_count", "—"))
    st.metric("今日異常", realtime_info.get("today_anomaly", "—"))
    st.caption(f"最後寫入：{realtime_info.get('last_write', '—')}")

st.markdown("---")
```

**Backend 配合**：需 `/analytics/unified-summary` endpoint 加 `today_count` / `today_anomaly` / `last_write` 三個 derived 欄位 per source。

**或 FE-only 版**（避免改 BE）：直接從現有 `/data?date_from=today` 與 `/realtime/history?seconds=86400` 拉資料前端算（增加 2 次 API call）。

**驗收標準**：
- Dashboard 頂部第一視覺即看到「雙軌資料架構」卡片
- 兩軌數字各自獨立可比
- 評審 / viewer 5 秒理解「系統有兩條 ingestion path」

**注意**：此補強較大 + 需協調權限矩陣卡片位置，**可選實作**。如時間不夠優先做 #1-#5。

---

### 6.8 系統管理 Tab 4「即時資料歷史」改名 + caption（補強 #8）

**目標檔**：`/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/frontend/streamlit_app/pages/5_系統管理.py`

**改哪行**：先 grep `即時資料歷史` 找確切 line（依 ux-research §2.6 在 line 71-77 5 個 tab label 處 + line 412-526 tab content 處）

**改前**（tab label 推估）：

```python
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "使用者列表",
    "系統日誌",
    "資料庫狀態",
    "即時資料歷史",  # ← 這個
    "系統設定",
])
```

**改後**：

```python
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "使用者列表",
    "系統日誌",
    "資料庫狀態",
    "軌 2 即時資料歷史（Admin 後台）",  # ← 改這個
    "系統設定",
])
```

**Tab 4 content 內加 caption**（在 `with tab4:` 區塊頂部）：

```python
with tab4:
    st.caption(
        "**Admin 後台軌 2 歷史查詢**：與「即時監控」頁差別在於"
        "(1) 本頁支援自訂時間範圍（最大 24 小時）"
        "(2) Admin 專用（user / viewer 無權限）"
        "(3) 純歷史唯讀，不訂閱 WebSocket。"
        "如需即時 60 秒滑動視圖請至『即時監控』頁。"
    )
    # ... 既有圖表邏輯
```

**驗收標準**：
- Tab 4 名稱明確標「軌 2」+ 「Admin 後台」+ 與「即時監控」頁差別 caption 清楚
- 評審切到此 tab 不再混淆「為什麼跟即時監控頁長一樣」

---

### 6.9 施工順序建議

```
Phase 1（1.5 小時）— 核心 caption / label 修正：
  - 補強 #4：資料管理頁 caption（5 分）
  - 補強 #5：即時監控頁 caption（5 分）
  - 補強 #2：Dashboard metric card tooltip（15 分）
  - 補強 #3：分析報表 source toggle（20 分）
  - 補強 #8：系統管理 Tab 4 改名（10 分）
  - 補強 #6：sample_data.csv header 註解（15 分）
  - 補強 #1：README 雙軌 section（30 分）

Phase 2（可選 1.5 小時）— Dashboard 加總覽卡：
  - 補強 #7：Dashboard 雙軌總覽卡片（90 分）

Phase 3（驗收 30 分）— 視覺驗證：
  - Chrome MCP 截圖 5 頁 × 3 角色
  - 派獨立 sub-agent Read 截圖確認「軌 1 / 軌 2」keyword 在每頁可見
```

**最低可行版**：只做 Phase 1 約 1 小時 40 分鐘解決 80% 雙軌 surface 缺口。

---

## 結語

**核心洞察**：candidate 已經在 backend / schema / API 層級完整實作雙軌設計（wide + long 並存 + unified-summary 統合 endpoint），是這份 demo 最強的設計賣點，**但前端 UX 層完全沒 surface 這個賣點**。

5/26 17:50 懷特看完 demo 後問「我設計出這個系統，分別獨立監看即時數據，以及另外可以藉由平台整理和圖表分析自己匯入的示範 CSV，是這樣嗎？」——這個問題本身就是「雙軌 UX surface 失敗」的直接證據。**懷特身為系統設計者都需要重新讀需求文檔才確認，評審 Eric 5-10 分鐘看不到的機率極高**。

本 audit 提出 8 條補強建議，前 5 條約 1 小時 40 分鐘可完成 80% 雙軌 surface 修補。建議 Phase 1 立即執行，Phase 2 視時間決定。

**下一步**：派 frontend-engineer sub-agent 依 Section 6.1-6.8 spec 施工，完成後派獨立 visual-validator sub-agent Chrome MCP 截圖驗收，最終 Discord 通知懷特。

DUAL-TRACK AUDIT DONE
