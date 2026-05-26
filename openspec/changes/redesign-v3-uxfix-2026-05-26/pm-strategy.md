# PM Strategy — Redesign v3 UX Fix（Wiwynn 面試題即時資料分析與監控系統）

**Date**：2026-05-26
**Owner**：product-manager（PM 視角）
**Audience**：tech lead + UI/UX 設計師 + 評審（Wiwynn 面試官）
**Decision context**：時間 24 小時、不能重寫、目標是讓評審 5–10 分鐘內看完印象分爆衝
**讀過的證據檔**：
- `README.md` 全 266 行（系統定位 / 5 大模組 / 角色矩陣 / API / 部署）
- `docs/architecture.md` 全 154 行（4 張 mermaid 圖 + 5 個模組責任）
- `openspec/changes/realtime-system-full-validation-2026-05-26/proposal.md` 全 153 行
- `openspec/changes/realtime-system-full-validation-2026-05-26/report_round1_fixes.md` 全 86 行（8 個已修 bug）
- `openspec/changes/redesign-monitoring-system-v2-2026-05-26/proposal.md` 全 170 行（12 點懷特反饋）
- `openspec/changes/redesign-monitoring-system-v2-2026-05-26/design.md` 全 710 行（已落地設計）
- `frontend/streamlit_app/Home.py` 全 107 行
- `frontend/streamlit_app/pages/1_儀表板.py` 全 269 行
- `frontend/streamlit_app/pages/2_資料管理.py` 全 327 行
- `frontend/streamlit_app/pages/3_分析報表.py` 全 436 行
- `frontend/streamlit_app/pages/4_即時監控.py` 全 372 行
- `frontend/streamlit_app/pages/5_系統管理.py` 全 640 行

---

## §0. Executive Summary（先講重點，給沒時間看完整份的人）

這個 demo **後端已經是 production-grade**（24 endpoints / 5 service / WS / wide schema / RBAC / Alembic / Docker），**前端也已經做完 v2 redesign 的所有功能**（5 頁中文化 / 去 emoji / data_editor inline edit / 告警卡 Δ / 60 筆表 + 淡粉紅）。但**懷特實際看完仍覺得「奇怪、不直觀、難用、不確定滿足需求」**。

**核心診斷**：v1 → v2 把「壞掉的功能修好」+「設計層問題修正」，**但沒有從「評審 5 分鐘看完要打分」這個 mental model 重新檢視**。v2 把功能塞滿，但缺：

1. **首屏 trust signal**（評審打開沒看到系統健康/規模/能力的快速 readout）
2. **explain-as-you-go 微 copy**（功能在哪、為何在這、怎麼用，全靠評審自己猜）
3. **資料/角色脈絡的視覺化**（角色權限藏在折疊裡、Tab 4 admin 才能看歷史趨勢、metric 閾值寫死前端）
4. **demo-mode 視角**（評審用 viewer 登進去 → 看不到 admin 頁、改不了密碼預期之外、即時告警可能恰好沒觸發 → 失分）

**P0 必動的 3 件事**（24 小時內，外科手術而非全改）：
- **A. 角色權限說明上首屏**（從 admin tab 折疊裡搬到 Dashboard 頂部固定卡片，3 角色都看得到，含「目前你是 viewer/user/admin，能看到什麼」紅綠燈）
- **B. 每頁加 1 段「這頁在幹嘛 / 看什麼 / 怎麼用」說明卡**（5 頁 × 1 卡 = 5 段 markdown，每段 ≤ 80 字）
- **C. 即時監控頁加 demo 控制（手動觸發異常 + 閾值即時調整 UI）**，讓評審不用乾等 60 tick 看 anomaly injection

下面細節。

---

## §1. 產品定位重新校準（Value Prop Audit）

### 1.1 這個 demo 應該對評審傳達什麼價值主張？

**Job-to-be-Done**（從 Wiwynn 招募方視角）：
> 「我們要找的人能不能在 96 小時面試題裡端出一個**架構合理、能跑、有產品 sense、考慮到角色/異常/可觀測性**的 SaaS 雛形？」

**對應的 4 大價值訊號**（評審打勾項）：

| 訊號 | 表達方式 | 5 分鐘內能否被評審 perceive |
|---|---|---|
| V1. 全棧能力 | FastAPI + SQLAlchemy + Alembic + WS + Streamlit + Docker | 看 README + 開頁面就感受到 |
| V2. 即時系統設計 | 採集 vs 訂閱解耦、wide schema、snapshot+delta、tz-aware | 即時監控頁打開有資料 + 流暢更新 |
| V3. 產品 sense | RBAC 三角色 + 異常 UX + 中文化 + 角色說明 | 角色矩陣明顯、異常顯眼、頁面標題清楚 |
| V4. 可維運性 | Audit log + DB pool status + 動態 threshold + alembic seed | Admin 頁全功能可看 |

### 1.2 目前實際傳達了什麼？（gap 在哪）

我把自己當成評審，假設用 **viewer 角色（最受限）** 開啟系統 5 分鐘：

| 體驗 step | V1 全棧 | V2 即時 | V3 產品 sense | V4 可維運 |
|---|---|---|---|---|
| 打開 Home | 看到登入頁，但「即時資料分析與監控系統」標題太通用，沒有 sub-headline 講解這是什麼 | — | — | — |
| 用 viewer 登入 | 跳到「儀表板」 — title 對了但**沒有 onboarding tour / 沒有「歡迎，您目前的角色是 viewer，能做這 5 件事」** | system status header 有 ●/○ — ok | 角色資訊只顯示在右上角小字 `角色：viewer` — 太弱 | DB 沒露 |
| 看 Dashboard | 4 個 metric card（合計/即時/錄入/異常）— ok | 60 秒 active alert 計數 — ok | 沒提到 viewer 在這頁能不能改密碼？實際看 `1_儀表板.py:222-262` 有 expander，但 viewer 也能用（沒 disable） | — |
| 點到資料管理 | 看到資料表 + 篩選 — ok | — | viewer 看到 `st.info("Viewer 角色為唯讀")`（`2_資料管理.py:117`）— ok 但只有一句 | — |
| 點到分析報表 | 看到 unified summary + 趨勢圖 — ok | 但 trend source toggle 沒解釋 records vs realtime 差別在哪 | — | — |
| 點到即時監控 | WS 串流 — ok | 折線圖 5 條 — ok 但 evaluator 看不到 anomaly（要等隨機 60 tick 一次） | 告警卡空著時顯示 `st.success("目前無異常告警")` — 缺「等等就會看到」說明 | — |
| 點到系統管理 | **viewer 直接被擋**：`st.error("存取拒絕")` + `st.stop()`（`5_系統管理.py:39-41`） | — | **評審看不到角色權限矩陣**（藏在 admin tab 1 的折疊裡 `5_系統管理.py:88-105`） | viewer 看不到 DB pool / logs / settings |

**Gap 總結**：
1. **價值訊號 V3（產品 sense）對 viewer / user 角色根本看不到**：角色權限矩陣藏在 admin 才能進的 tab 裡的 expander 裡 → 2 層遮蔽 → 評審如果用 viewer demo 完全感受不到我們有想過 RBAC
2. **價值訊號 V4（可維運性）對非 admin 完全 0**：viewer/user 看不到 DB pool 狀態、audit log、settings → 評審如果不切到 admin 直接漏掉
3. **價值訊號 V2（即時系統設計）需要運氣**：anomaly injection 每 60 tick 一次（`design.md:178` `ANOMALY_INJECTION_PERIOD=60`），評審可能剛好沒看到告警觸發 → 失分
4. **首屏沒有「這套系統能做什麼」的 5 秒 elevator pitch**

**這就是 6 大抽象問題的根因。**

---

## §2. 6 大抽象問題優先級排序（含程式碼證據）

> 評分標準：**評審第一印象殺傷力 × 修補 ROI（小時 vs 分數）**

### P0-1（最高優先）— 角色權限說明不夠一目瞭然（問題 6）

**現況觀察**：

| 證據 | 引用 | 觀察 |
|---|---|---|
| 權限矩陣表 markdown 寫在 `5_系統管理.py:88-105` | `5_系統管理.py:88-105` 13 條操作 × 3 角色 | 只有 admin 角色能進此頁；非 admin 在 `5_系統管理.py:38-41` 被 `st.stop()` 擋掉 |
| 即使 admin 進來，矩陣藏在 `with st.expander("角色權限說明", expanded=False)` | `5_系統管理.py:88` `expanded=False` | 預設摺疊，admin 也要主動點開才看得到 |
| README 也有角色矩陣 | `README.md:171-181` | 但評審不會回頭看 README |
| viewer 在 dashboard 右上角只看到 `角色：\`viewer\`` 4 個字 | `1_儀表板.py:34` | 完全沒講「viewer 能做什麼」 |
| 資料管理頁 viewer 看到一句 `st.info("Viewer 角色為唯讀，無法編輯資料。")` | `2_資料管理.py:117` | 只講「不能做什麼」，沒講「能做什麼」 |
| 即時監控頁三角色都可用，但沒任何說明 | `4_即時監控.py:31` 只有 `require_auth()` | 評審不知道 viewer 也可以看即時 |

**為什麼是 P0**：這是懷特明點的 6 號抽象問題，且**直接影響 V3 產品 sense 訊號傳達**。角色設計是這題的核心交付物之一（README 列出 3 角色 + RBAC），藏起來等於白做。

**修補建議**：見 §4。

### P0-2 — 功能不直觀 + 沒有任何 onboarding / 微 copy（問題 2）

**現況觀察**：

| 頁面 | 證據 | 觀察 |
|---|---|---|
| Home | `Home.py:20` `st.title("即時資料分析與監控系統")` | 無 sub-headline / 無「這是 Wiwynn 面試 demo / 三角色測試帳號在這」hint。試用帳號只在 README，登入頁完全沒提 |
| 儀表板 | `1_儀表板.py:30` `st.title("儀表板")` 之後直接 metric cards，沒任何「這頁顯示什麼/數字來自哪」說明 | 4 個 metric card 沒 tooltip，「合計資料筆數」評審看不懂是不是含 realtime |
| 資料管理 | `2_資料管理.py:41` `st.title("資料管理")` → 直接篩選 widget | 沒解釋 inline edit 怎麼用、「儲存變更」按鈕在哪 |
| 分析報表 | `3_分析報表.py:44` `st.title("分析報表")` → 3 個 selectbox 沒 hint | trend source「錄入資料 vs 即時資料」差別評審不知道 |
| 即時監控 | `4_即時監控.py:86` `st.title("即時監控")` → 直接 WS | 沒提「等 1 秒會跳第一筆 / 每秒更新 / 異常會跳紅」|
| 系統管理 | `5_系統管理.py:58` `st.title("系統管理")` → 5 tab 沒解釋 | tab 順序為什麼是這樣？「即時資料歷史」跟「即時監控」差別？ |

**為什麼是 P0**：5 頁 × 0 onboarding micro-copy = 評審每頁都要「猜」。即時 demo 場景沒法問問題、沒法看文件 → 直接打折扣。修補 ROI 極高：5 段 markdown 加總 ≤ 400 字。

### P0-3 — 不確定專案是否完全滿足需求文檔（問題 4）+ 不確定所有功能正常運作（問題 5）

**現況觀察**：

| 需求文檔項 | 已實裝？ | 證據 | 落差 |
|---|---|---|---|
| 5 大模組 32 子功能 | ✅ 全綠 | `report_round1_fixes.md:74` | 但**評審無法快速確認**，沒有 self-test / status page |
| 24 API endpoints | ✅ | `realtime-system-full-validation-2026-05-26/proposal.md:18` | Swagger UI 在 `/docs` 但前端沒連結到 |
| 5 條交付物 | ✅ README/env/csv/architecture/repo | `report_round1_fixes.md:79` | 但前端沒展示「系統架構圖」連結 |
| FE 6 頁面 | ✅ 但 Realtime/Analytics 需 deploy 才生效 | `report_round1_fixes.md:54-66` | Zeabur deploy webhook 卡關（需懷特手動處理）— **驗收阻塞** |
| 角色 RBAC | ✅ 但說明藏太深 | P0-1 已論述 | — |
| WS 即時推送 | ✅ wide format | `design.md:33-55` | 評審看不到 schema 細節 |
| Anomaly injection | ✅ 每 60 tick 一次 | `design.md:178` | 評審可能等不到 → 看不出 anomaly UX 設計（淡粉紅 + 紅字）|

**為什麼是 P0**：問題 4+5 的根因不是「沒做」而是「做了但評審不知道做了」。要的不是再做更多，是**做 verification surface**（讓評審 5 秒看出系統是健康的、所有模組都活著、所有需求都覆蓋）。

### P1-1 — UI/UX 設計奇怪、意義不明（問題 1）

**現況觀察**：

| 證據 | 引用 | 為何奇怪 |
|---|---|---|
| Dashboard 「重新整理」按鈕 full-width 在頁面最底 | `1_儀表板.py:266-268` | full-width 太大、放最底找不到，應該放頂部 + 小按鈕 |
| Dashboard 帳號設定 expander 不分角色 | `1_儀表板.py:222-262` | admin 也能在這改自己密碼，但 admin 也能在 `5_系統管理.py:208-259` 改 — **同功能兩個入口** |
| 資料管理篩選 expander 預設 `expanded=True` | `2_資料管理.py:55` | 開頁就佔半屏，評審看不到資料表 |
| 資料管理「儲存變更」按鈕沒 confirmation modal | `2_資料管理.py:170` | 評審亂編輯按下去直接打 API 5 次（含 DELETE）— 風險高 |
| 分析報表「準備 Excel 下載」分兩步驟（按鈕 → 下載按鈕） | `3_分析報表.py:394-435` | 為什麼不一步？多一個 click 沒必要的 friction |
| 即時監控「清空緩衝區」按鈕跟「顯示哪些線」並排 | `4_即時監控.py:147-160` | 一個是 destructive 一個是 view filter，不應放一起 |
| 即時監控告警卡 `delta_color="inverse"`（綠是壞、紅是好） | `4_即時監控.py:196` | Streamlit 預設綠 = good；inverse 讓「異常 +50」變綠色看起來像好事 — confusing |
| 即時監控 metric 閾值寫死前端 `4_即時監控.py:56-69` | `4_即時監控.py:56-69` | 跟後端 `/admin/settings` 動態閾值（README 強調的賣點）不同步 — admin 改了閾值 UI 還是用舊的 |
| 系統管理 Tab 4「即時資料歷史」跟即時監控頁折線圖長得幾乎一模一樣 | `5_系統管理.py:483-525` vs `4_即時監控.py:214-264` | 評審混淆「為什麼有兩個一樣的頁」 |
| 系統管理 Tab 1 改密碼有 form `5_系統管理.py:218-226`、Dashboard 也有 form `1_儀表板.py:226-230` | 兩處 | 同功能 UI 風格不一致（一個叫「改自己」一個有 target selectbox）|

**為什麼是 P1**：每條都是 nit，單獨修很 trivial，但**加總起來給評審「設計凌亂」印象**。建議挑 3 條最痛的修（閾值寫死、delta_color inverse、儀表板重整按鈕位置），其餘留 v4。

### P1-2 — 圖表呈現方式難用（問題 3）

**現況觀察**：

| 證據 | 引用 | 觀察 |
|---|---|---|
| 即時監控折線圖 5 條 metric 共用 Y 軸 | `4_即時監控.py:256-263` | pressure（~1000）+ voltage（~12）+ humidity（0-100）共軸 → voltage 線扁成一條 → 評審看不出 voltage 變化 |
| 60 筆表格 styler 用 `_style_metric_col` apply 偶會 raise → fallback 無 styler | `4_即時監控.py:344-359` | 「淡粉紅 + 紅字」是 v2 設計核心 selling point，但 try/except 默默吞 exception → 評審看到普通表格，沒看到設計 |
| 分析報表時間趨勢圖 trend source 只支援 records 不支援 realtime（realtime 顯示長條圖代替） | `3_分析報表.py:184-289` | trend source toggle 名稱是「時間趨勢」，但 realtime 不畫趨勢只畫 bar chart — 名稱與內容不符 |
| 分析報表類別分佈兩個並排長條圖（筆數 + 平均） | `3_分析報表.py:335-365` | 平均值對 records 來說全部是同類別的數值，意義模糊（temperature 平均 50.3 跟 cpu_usage 平均 50.3 不能比） |
| 系統管理 DB 狀態 metric「Pool 大小 / 已借出 / 溢出」沒 baseline | `5_系統管理.py:388-393` | 評審看到「Pool=20, checked_out=2, overflow=0」不知道是健康還是不健康 |
| 即時監控折線圖預設顯示 5 條全選 | `4_即時監控.py:152` `default=_METRIC_KEYS` | 5 條同時看資訊量爆炸，建議預設 2-3 條 |
| Pandas Styler `try/except Exception: st.dataframe(df_visible)` 靜默吞 | `4_即時監控.py:344-359` | exception 沒 log，評審看到「沒淡粉紅」也不知道為什麼 |

**為什麼是 P1**：圖表壞掉直接影響 V2 即時系統設計訊號。但修補成本中等（需要 plotly secondary y-axis、styler debug、normalize 等）。

---

## §3. 需求文檔覆蓋率 audit（5 大模組 × 子功能 × 落差表）

> 每行：需求 → 目前實裝狀態 → 落差

### 3.1 模組 1：使用者管理

| # | 需求 | 實裝狀態 | 落差 |
|---|---|---|---|
| 1.1 | POST `/auth/register` | ✅ `Home.py:88-95` 表單 + BE endpoint | viewer 預設角色說明在 `Home.py:48` 一句話，但沒解釋為什麼預設 viewer / 怎麼升級 |
| 1.2 | POST `/auth/login` + JWT | ✅ `Home.py:31-43` + BE | login 失敗訊息 `Home.py:43` `f"登入失敗：{message}"` 沒區分「密碼錯」vs「帳號不存在」(411 vs 401) |
| 1.3 | POST `/auth/logout` | ✅ `auth.py` 提供 logout | UI 各頁都有「登出」按鈕 `1_儀表板.py:37` 等，但 logout 是 client-side 清 session，沒打 BE endpoint（檢查 auth.py 確認） |
| 1.4 | GET `/auth/me` | ✅ session_state cache | 沒「重新拉一次 me」按鈕，如果 admin 在 BE 改了你的角色，前端不會更新 |
| 1.5 | 3 角色 Admin/User/Viewer | ✅ 三個 seed 帳號 | 角色說明可見性 = P0-1 |
| 1.6 | RBAC 中介層 | ✅ BE 24 endpoint 全有 perm 守衛 | 前端 viewer 在某些頁面看到的功能跟 BE 拒絕的不一致（如 `1_儀表板.py:222-262` viewer 可看到改密碼 form，但 BE 應該拒絕 — 需 verify） |
| 1.7 | PATCH `/users/{id}/password`（v2 新增）| ✅ Dashboard + Admin 都有 form | 同功能兩入口 — UI inconsistency（P1-1） |

**模組 1 落差數：5**

### 3.2 模組 2：資料管理

| # | 需求 | 實裝狀態 | 落差 |
|---|---|---|---|
| 2.1 | POST `/data` 創建 | ✅ data_editor 新增 row | 用 inline edit 新增，沒有專門「+ 新增資料」按鈕 — 評審可能找不到 |
| 2.2 | GET `/data` 分頁/篩選/排序 | ✅ `2_資料管理.py:55-92` | 篩選 expander 預設展開佔屏（P1-1） |
| 2.3 | GET `/data/{id}` | ✅ BE | FE 沒 detail page，看細節要點開行（data_editor 限制） |
| 2.4 | PATCH `/data/{id}` | ✅ inline edit diff | 沒 confirmation，亂改可能誤刪 |
| 2.5 | DELETE `/data/{id}` | ✅ data_editor 移除 row | 用 data_editor 刪除不直觀，使用者不知道「刪行 = DELETE」 |
| 2.6 | POST `/data/bulk-import` CSV/JSON | ✅ `2_資料管理.py:268-324` | 10 MB 上限只在 caption 提一句，超過後才報錯 |
| 2.7 | 逐行錯誤回報 | ✅ `2_資料管理.py:305-314` 顯示 error_df | 但 column 名只有 `["row", "reason"]` 才改中文，其他 schema 不改 → fragile |
| 2.8 | owner / admin 權限 | ✅ `2_資料管理.py:184, 226` | 403 silent skip + toast，但 toast 字串「沒有權限刪除 ID 5」對評審來說太技術 |

**模組 2 落差數：6**

### 3.3 模組 3：即時監控

| # | 需求 | 實裝狀態 | 落差 |
|---|---|---|---|
| 3.1 | APScheduler 每秒 tick | ✅ BE | 評審看不到 scheduler 是不是真的在跑（缺 health indicator） |
| 3.2 | WebSocket `/ws/realtime` 推送 | ✅ `4_即時監控.py:97` + ws_client | 連線狀態指示 `4_即時監控.py:135` 有 ●/○ — ok |
| 3.3 | 超閾值異常標記 | ✅ wide payload `anomaly_flags` | 閾值寫死前端（P1-1）— admin 改 settings 不影響 |
| 3.4 | 每 tick 全類別 snapshot | ✅ wide format | schema_version v2 — ok |
| 3.5 | Snapshot + Delta（v2 加）| ✅ `4_即時監控.py:99-107` REST history 預載 | 預載 60 秒，但首次 cold start BE 不到 60 秒就會空 |
| 3.6 | 告警卡 Δ 數值 | ✅ `4_即時監控.py:191-197` | `delta_color="inverse"` 顏色語意反 — confusing |
| 3.7 | 60 筆表格 + 異常 row 淡粉紅 + cell 紅字 | ✅ 設計到位 + try/except | exception 靜默 fallback — 設計賣點消失（P1-2） |
| 3.8 | 折線圖 5 條線 | ✅ `4_即時監控.py:214-263` | 共軸壓扁 voltage（P1-2） |
| 3.9 | 異常點 marker | ✅ circle-open red | 50% mean = anomaly，evaluator 5 分鐘可能等不到 |
| 3.10 | system status header | ✅ `4_即時監控.py:132-144` | ok |

**模組 3 落差數：5**

### 3.4 模組 4：資料分析

| # | 需求 | 實裝狀態 | 落差 |
|---|---|---|---|
| 4.1 | GET `/analytics/summary`（總/平均/max/min）| ✅ 整合進 unified-summary | 統計欄位繁體中文 OK |
| 4.2 | GET `/analytics/timerange`（hour/day bucket）| ✅ `3_分析報表.py:166-169` | 預設 7 天範圍可能空（剛 deploy 沒資料）— 改 24 hr |
| 4.3 | GET `/analytics/categories`（分類聚合）| ✅ `3_分析報表.py:307-310` | source toggle 邏輯複雜（P1-2） |
| 4.4 | GET `/analytics/export` Excel | ✅ `3_分析報表.py:394-435` | 兩步驟下載（P1-1） |
| 4.5 | unified summary（v2 新）| ✅ `3_分析報表.py:97-100` | 「合計筆數」評審看不懂是不是真的把 realtime + records 加總（meta 沒解釋） |
| 4.6 | realtime-categories（v2 新）| ✅ | bar chart 顯示 5 metric 平均值在同一 Y 軸 — voltage 看不到 |

**模組 4 落差數：4**

### 3.5 模組 5：系統管理（Admin）

| # | 需求 | 實裝狀態 | 落差 |
|---|---|---|---|
| 5.1 | GET `/users`（列表）| ✅ `5_系統管理.py:127` | 篩選只有 role，沒有 active/inactive |
| 5.2 | PATCH `/users/{id}` role | ✅ `5_系統管理.py:184-201` | 沒 confirmation modal，誤改 admin role 風險 |
| 5.3 | DELETE `/users/{id}` | ⚠️ README 列在 admin endpoint，FE `5_系統管理.py` 沒有 UI | **落差**：BE 有 endpoint，FE 漏了刪除按鈕 |
| 5.4 | GET `/admin/logs` | ✅ `5_系統管理.py:309` | 日期篩選 datepicker，但 metadata 用 expander + 10 筆 limit `5_系統管理.py:349`，超過 10 筆看不到 |
| 5.5 | GET `/admin/db-status` | ✅ `5_系統管理.py:368` | pool 數字沒 baseline（P1-2） |
| 5.6 | GET `/admin/realtime-history` | ✅ wide format `5_系統管理.py:456` | 跟即時監控頁折線圖重複（P1-1） |
| 5.7 | GET `/admin/settings` | ✅ `5_系統管理.py:564` | 設定全部 expander expanded=True 一次展開 5 個 → 滾動長 |
| 5.8 | PATCH `/admin/settings/{key}` 動態閾值 | ✅ `5_系統管理.py:616-624` | 但前端 4_即時監控.py 閾值寫死，admin 改 settings 即時監控不會 reflect — broken loop |
| 5.9 | 角色權限說明 | ✅ `5_系統管理.py:88-105` | P0-1 — admin tab + expander 2 層遮蔽 |
| 5.10 | 改密碼（v2 加）| ✅ `5_系統管理.py:208-259` | UI 跟 Dashboard 不一致（P1-1） |

**模組 5 落差數：8**

### 3.6 需求文檔覆蓋率總計

| 模組 | 子需求數 | 實裝完成 | 有落差項 |
|---|---|---|---|
| 1. 使用者管理 | 7 | 7 | 5 |
| 2. 資料管理 | 8 | 8 | 6 |
| 3. 即時監控 | 10 | 10 | 5 |
| 4. 資料分析 | 6 | 6 | 4 |
| 5. 系統管理 | 10 | 9（DELETE user UI 缺）| 8 |
| **合計** | **41** | **40** | **28** |

**結論**：BE 功能 41/41 完備（除 5.3 DELETE user UI），但 UX 落差佔 68%（28/41）— 都是 onboarding / 視覺一致性 / 動態性 / 角色可見度層。**沒有需要再寫新功能，全部是修補既有的呈現方式**。

---

## §4. 角色權限說明的產品策略（3 方案推薦）

### 4.1 現況回顧

- 矩陣只在 `5_系統管理.py:88-105`（admin tab + expander）+ `README.md:171-181`
- 三個非 admin 角色完全看不到
- 評審若用 viewer demo → V3 產品 sense 訊號 = 0

### 4.2 三個可行方案

#### 方案 A — Dashboard 頂部固定卡片 + 「你能做什麼」高亮（**推薦**）

**做法**：
- Dashboard 頁面（`1_儀表板.py`）在 `st.title("儀表板")` 之後、system status header 之前，加一個 `st.container()`，內容：
  - 一行 markdown：「**您目前的角色：{role}**（{中文角色名}）」
  - 一個 13 行 markdown table（從 `5_系統管理.py:88-105` 移過來）
  - 用 `✓` / `✗` / `✓（唯讀）`，**且當前角色那欄背景色高亮**（用 HTML `<td style="background:#fff3cd">`）
- 同時保留 `5_系統管理.py:88-105` 給 admin 看（不刪、改 `expanded=True`）

**Pros**：
- 三角色登入第一頁就看到
- 評審 5 秒掃完即知 RBAC 設計完整度
- 工作量小：1 段 HTML/markdown，~30 行 code

**Cons**：
- Dashboard 頁面變長
- HTML 高亮跨 Streamlit 版本兼容性需驗

#### 方案 B — 全域 Sidebar 永久顯示

**做法**：
- 在 `auth.py` 加 helper `render_role_badge_sidebar()`
- 每頁 require_auth() 之後呼叫，把角色 badge + 簡化矩陣放 sidebar 底
- Sidebar 永遠可見（Streamlit 多頁面 app 預設行為）

**Pros**：
- 每頁都看得到，不限 Dashboard
- 不佔主內容區

**Cons**：
- Streamlit sidebar 寬度限制，markdown table 會被擠壓
- 評審如果側邊欄沒展開（Streamlit cloud 行動裝置預設收起）會看不到

#### 方案 C — Home 登入頁就秀出 RBAC + 試用帳號

**做法**：
- `Home.py` 在登入 tab 下方加「**試用帳號**」expander（`expanded=True`），列三角色 email/密碼
- 加一個 markdown link「點此查看完整角色權限矩陣」→ 連到一個新的 public `pages/0_系統說明.py`（require_auth 換成 public）
- 該頁顯示完整矩陣 + 系統架構連結 + Swagger 連結

**Pros**：
- 評審還沒登入就感受到 RBAC + 文件完整度
- 試用帳號明示 → 評審不用回 README 找
- 解決 P0-3「不確定滿足需求」— 把架構/Swagger/角色全鏈到登入頁

**Cons**：
- Streamlit 多頁面 `pages/` 全部需要 auth 守衛，要 hack（用 `st.set_page_config` + 不調 `require_auth()`）
- 新增一個 page 違反「不加新功能」原則

### 4.3 推薦：**方案 A + 部分方案 C**

**Why 組合**：
- 方案 A 解決「登入後三角色都看得到」的核心問題（最小變動、最大效益）
- 方案 C 的「Home 加試用帳號 expander」抽出來單獨做（**1 行 markdown** 即可，不需新 page）— 額外帶起「demo 友善度」加分

**不選方案 B**：sidebar 不可靠（Streamlit Cloud 行動裝置預設收起，評審若用手機看必失分）

**實作步驟**（給 builder）：
1. 從 `5_系統管理.py:88-105` 抽出 markdown table 成 `auth.py:render_role_matrix(current_role: str)` helper
2. 在 `1_儀表板.py` 第 41 行 `st.markdown("---")` 之後、第 43 行 system status 之前插入 `with st.container(border=True): render_role_matrix(role)`
3. 在 `Home.py` 第 31 行 `submitted = ...` 之前加 expander：
   ```python
   with st.expander("試用帳號（測試用）", expanded=False):
       st.markdown("| 角色 | Email | 密碼 |\n|---|---|---|\n| Admin | admin@example.com | admin123 |\n| User | user@example.com | user123 |\n| Viewer | viewer@example.com | viewer123 |")
   ```
4. `5_系統管理.py:88` 的 `expanded=False` 改 `expanded=True`

---

## §5. MVP feature 砍接清單（24 小時時間箱）

### 5.1 必動 5 項（按 ROI 排序）

| # | 動作 | 對應問題 | 工時 | ROI |
|---|---|---|---|---|
| M1 | **三角色 Dashboard 固定權限矩陣卡片 + Home 試用帳號 expander**（§4 方案 A+C） | P0-1（問題 6）| 1.5 hr | 極高 — 解決最大失分 |
| M2 | **5 頁加 onboarding micro-copy**（每頁 ≤ 80 字「這頁在幹嘛 / 看什麼 / 怎麼用」placeholder：頁面 title 下方 `st.caption()`）| P0-2（問題 2）| 1 hr | 極高 — 5 段文案搞定 |
| M3 | **即時監控 demo 控制 panel**（手動 inject anomaly 按鈕 + 即時 fetch `/admin/settings` 動態閾值 + 預設只顯示 2 條線 + 折線圖加 secondary y-axis）| P0-3 + P1-2（問題 3+5）| 3 hr | 高 — 解決閾值寫死 + 評審等不到 anomaly |
| M4 | **角色 demo banner**（首屏加「目前你是 X 角色，建議 demo 動線：Dashboard → 即時監控 → 分析報表 → ...」根據角色給不同建議路徑） | P0-3 + P1-1（問題 1+4+5）| 1.5 hr | 高 — 評審知道接下來看什麼 |
| M5 | **修 `delta_color="inverse"` 反語意 + Pandas Styler 不 silent fallback**（log exception + 用 stable 寫法） | P1-1 + P1-2（問題 1+3）| 1 hr | 中 — 修兩個明顯設計 bug |

**累計工時：8 hr**（給 24 hr 留 16 hr 緩衝給驗證/部署/迭代）

### 5.2 保持不動 5 項（resist scope creep）

| # | 不動 | 為什麼 |
|---|---|---|
| K1 | 後端 24 endpoints + wide schema + WS | v2 已驗證全綠，碰必碎 |
| K2 | Alembic migrations 0001/0002/0003 | 已 deploy，碰會 rollback hell |
| K3 | RBAC 守衛邏輯 | BE/FE 已對齊，碰會破 33 個 perm test |
| K4 | 增加新功能（DELETE user UI / 通知整合 / SSO） | 24 hr 不夠 + 不是評審期待 |
| K5 | 國際化 i18n 框架 / Streamlit 換 framework | v2 設計已決定保留 Streamlit，徹底重寫違反指令 |

### 5.3 灰色地帶（看時間決定）

| # | 條件做 | 條件 |
|---|---|---|
| G1 | DELETE user UI（補 5.3 缺口） | 如果 M1-M5 在 6 hr 內做完 |
| G2 | 即時監控折線圖 secondary y-axis（pressure 獨立軸）| 如果 M3 做完還有 1 hr |
| G3 | 改密碼 UI 二合一（Dashboard 砍掉、只留 Admin tab） | 如果 M1 同時順手做 |

---

## §6. 成功指標（評審 5 分鐘 demo 後該講出的 3 句話）

### 6.1 目標 narrative（candidate 希望評審腦中浮現）

評審 demo 完跟同事說：

> 1. 「**這個系統設計考慮到 3 角色 RBAC，Dashboard 第一眼就清楚告訴我能做什麼。**」
> 2. 「**即時監控頁 1 秒一筆 snapshot 推送很流暢，異常會跳紅標示，我手動觸發異常立刻看到告警卡。**」
> 3. 「**5 大模組需求文檔全部覆蓋，BE 有 Swagger 文件、架構圖、Audit log、動態閾值 — production-ready 程度。**」

### 6.2 對應 KPI（拍照式驗收）

| 指標 | 量化 | 量法 |
|---|---|---|
| K1. 角色 RBAC 可見度 | viewer 登入後 5 秒內能否說出「我能/不能做什麼」 | 自測（找 1 個沒看過系統的人） |
| K2. 即時告警觸發成功率 | demo 5 分鐘內 ≥ 1 次 anomaly 出現在告警卡 | 手動按 inject button 保證 100% |
| K3. 需求文檔覆蓋感知 | 評審 demo 後能否說出至少 4/5 大模組名稱 | 看 demo 結束問卷 |
| K4. 視覺設計一致性 | 5 頁中文化 100% + emoji 0 + 顏色語意正確 | grep emoji + 手動 delta_color audit |
| K5. Trust signal density | 首屏（Home + Dashboard）含 ≥ 3 個可信號（架構連結 / Swagger 連結 / 試用帳號 / 角色矩陣 / system status）| count |

### 6.3 反指標（demo 後絕對不能聽到）

- ❌「角色權限是什麼？我看不到」← P0-1 失敗
- ❌「這個按鈕點下去會發生什麼？」← P0-2 失敗
- ❌「我等很久都沒看到異常」← P0-3 失敗
- ❌「為什麼數字 + 50 是綠色？」← P1-1 `delta_color=inverse` 沒修
- ❌「voltage 的線在哪？」← P1-2 共軸壓扁

---

## §7. 給 builder 的施工順序（avoid blocking）

```
Hour 0-1.5：M1（權限矩陣卡片 + Home 試用帳號）
Hour 1.5-2.5：M2（5 段 micro-copy，並行可派 sub-agent 同時寫 5 個檔）
Hour 2.5-5.5：M3（demo 控制 + secondary y-axis + 預設線數）— 最複雜
Hour 5.5-7：M4（角色 demo banner）
Hour 7-8：M5（delta_color + styler fix）
Hour 8-12：驗證 + Zeabur deploy + sub-agent 視覺驗收（截圖 5 頁 × 3 角色 = 15 張）
Hour 12-24：迭代 + bug fix + Discord 回報懷特看 dashboard URL
```

**驗證閘**（每 phase 結束必跑）：
- BE：`pytest -v --cov=app` 全綠
- FE：Chrome MCP 截圖 5 頁 × 3 角色 → 派 sub-agent Read 圖檢視（依 `feedback_v6_full_closed_loop.md` 嚴令）
- 部署：push 後 5 分鐘內查 Zeabur deployment status（依 `feedback_zeabur_push_active_check.md`）
- 端到端：curl 跑 §3 表格中的「實裝狀態」欄位逐項驗

---

## §8. 風險與 mitigation

| 風險 | 機率 | 影響 | mitigation |
|---|---|---|---|
| Zeabur FE webhook 又卡 | 高（v2 已發生）| 評審看不到新 commit | M1 完成立刻測 deploy，若卡先 Discord 升級懷特手動 redeploy（從 v2 經驗學） |
| anomaly inject button 改了 BE schema | 中 | 違反「不動 BE」原則 | 改用 FE-only：每次 page enter 隨機 mock 一個 anomaly snapshot 注入 buffer（不打 BE） |
| 權限矩陣 HTML 高亮 Streamlit 不支援 | 中 | 高亮失效 | fallback 用純 markdown，當前角色那欄改用 `**✓**` bold |
| micro-copy 5 段時間趕不出來 | 低 | 失 P0-2 | 預寫 fallback 1 段 80 字「本頁顯示 X，您可以 Y。」貼到 5 頁 |
| delta_color 修了但其他 metric 連帶壞 | 低 | UI 破 | grep 所有 `delta_color="inverse"` 統一審 |

---

## §9. 北極星對齊檢查

| 北極星 | 本 strategy 怎麼對齊 |
|---|---|
| 1. 使用者效益最大化 | 從評審角度看（不是工程師角度），M1-M5 全部以「評審 5 分鐘看到什麼」決策 |
| 2. 完整執行使用者命令 | 6 大抽象問題 → 全部 cover；35+ 需求項 → 41 項覆蓋；3 方案 → 給出 + 推薦 + 為什麼；5 砍 / 5 接 → 完整對照表 |
| 3. 主動為懷特想到他沒想到的事 | §6 反指標 / §8 風險 / §7 施工順序 / Home 試用帳號 expander（懷特沒提但評審 demo 必踩）/ M4 demo banner（讓評審知道接下來看什麼）/ K5 trust signal density 概念 |

---

## §10. Open Questions（懷特決策點）

1. **方案 A vs C 組合是否採納？** 還是要 sidebar（B）？
2. **demo 控制 panel（M3）是否允許 FE-only mock anomaly**（避免改 BE）？
3. **DELETE user UI（G1）是否必補**？影響需求文檔 5.3 嚴格覆蓋
4. **24 hr 是否含跨夜**？若否，M5 + 灰色地帶可能砍
5. **是否需要錄 demo 影片**配給評審？若需要，M2 micro-copy 要對齊影片旁白
6. **評審看 demo 的場景**（自己玩 vs 你直播）？若直播你能 narrate，micro-copy 可簡；若自玩，必須加 onboarding tour

---

**版本**：v1 — PM strategy 完成
**下一步**：傳給 UI/UX designer 出視覺 spec → tech lead 寫 OpenSpec proposal → builder 施工

PM STRATEGY DONE
