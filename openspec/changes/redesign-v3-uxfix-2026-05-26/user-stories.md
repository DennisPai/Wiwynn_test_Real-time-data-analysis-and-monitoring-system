# User Story Document — Wiwynn 即時資料分析與監控系統 Redesign v3 UX Fix

**版本**：v1.0
**日期**：2026-05-26
**作者**：story-writer sub-agent（v6.1 Mode A 加強版 Phase 1）
**讀過的來源文件**：
- `pm-strategy.md`（466 行）— P0/P1 問題分類、M1-M5 必動項、K1-K5 成功指標、§4 角色矩陣方案、§6.3 反指標
- `ux-research.md`（659 行）— 4 Persona JTBD、6 頁逐頁 audit（H/D/DM/A/R/S finding codes）、Top 10 UX 痛點
- `codebase-audit.md`（404 行）— 6 頁元件清單、41 條需求覆蓋、20 個「缺 caption/help」P0 清單、Open Issues O-P0-1~O-P0-6
- `customer-journey-map.md`（1125 行）— 4 Persona 旅程 E/A/U/V 系列、Top 15 摩擦節點、emotion curve before/after
- `assumption-mapping.md`（519 行）— 40 條 VA-1~VA-40 假設、VUBF 四象限、AC-1~AC-10 接受假設、Q1-Q5 決策點

---

## Section 1：Epic

**Epic 名稱**：Redesign v3 UX Fix — 讓評審在 5 分鐘內感受到系統的技術深度與完整度

**Background**：後端已是 production-grade（24 endpoints / RBAC / WS / Alembic / Docker），前端 v2 已完成功能性修補。但現有介面缺乏「評審 5 分鐘 mental model」設計：角色權限藏在 admin 折疊層、每頁零 onboarding 文案、即時監控必須等 60 tick 才能看到異常、delta_color 顏色語意反向。v3 聚焦在「讓已存在的技術深度被看見」，不新增後端功能，全部是前端呈現層修補。

**目標使用者**：Wiwynn 招募評審（Persona D Eric，5 分鐘掃 demo）+ 三角色（Admin 林佳穎 / User 陳家豪 / Viewer 王主管）

**成功定義（5 分鐘 demo 後評審應能說出）**：
1. 「這套系統有 RBAC 三角色設計，Dashboard 第一眼就告訴我能做什麼。」
2. 「即時監控 1 秒推送，異常跳紅，我手動觸發就馬上看到告警。」
3. 「5 大模組需求文檔全部覆蓋，有 Swagger、架構圖、Audit log、動態閾值。」

---

## Section 2：User Stories

### Story #1：Home 頁評審快速登入（測試帳號一鍵帶入）

**優先級**：P0 | **對應 PM 必動項**：M1 方案 C | **Sprint**：1 | **估時**：30-45 分鐘

**As a** 評審（Persona D Eric）
**I want to** 在 Home 頁第一眼就看到三個角色的測試帳號，並能一鍵帶入登入表單
**So that** 我不需要切換到 README 翻帳號，直接在 5 秒內開始 demo

**Acceptance Criteria**：

1. Given 評審打開 Home 頁（未登入狀態），when 頁面渲染完成，then 登入 tab 上方可見「試用帳號」expander，預設展開，列出 Admin / User / Viewer 三組 email + 密碼
2. Given 試用帳號 expander 可見，when 評審點擊「以 Admin 登入」按鈕，then email 欄位帶入 `admin@example.com`、password 欄位帶入對應密碼，且自動觸發登入流程（等同按下「登入」按鈕）
3. Given 評審已點「以 Viewer 登入」自動帶入，when 登入成功，then 跳轉到儀表板，且右上角用戶資訊顯示「viewer」角色名稱
4. Given 試用帳號按鈕存在，when 評審改為手動在 email/password 欄位輸入後按「登入」，then 原有登入邏輯正常運作，試用帳號按鈕不干擾
5. Given 試用帳號 expander 存在，when 評審切換到「註冊」tab，then 試用帳號區塊不出現在註冊 tab 內

**Edge Cases**：

- **Streamlit session_state 預填限制**：Streamlit 1.39 不支援 programmatic form submit（VA-17 信心 2）。若 `st.session_state` 預填後 form 仍需手動按 submit，則退化為「自動帶入 email/密碼欄位，使用者再按一次登入」（2-click，而非 1-click）。此退化方案仍滿足 AC-1
- **並發場景**：兩位評審同時用同一帳號登入（viewer），JWT 各自獨立
- **空 buffer 狀態**：登入成功後儀表板 cold start BE 不到 60 秒，`/realtime/history` 回傳空 list。AC-3 不驗 Dashboard 有資料，只驗登入本身正常
- **密碼欄位顯示**：試用帳號 expander 中密碼以明文顯示（非 input type=password），為 demo 便利性設計（AC-5 接受）
- **網路失敗**：按「以 Admin 登入」後若 BE 無回應，顯示 `st.error("登入失敗，請確認後端服務正在運行")`，不 silent fail

**Out of Scope**：
- 建立「0_系統說明.py」公開頁面（pm-strategy §4.2 方案 C 的完整版，本 story 只做 expander 部分）
- OAuth / SSO 整合
- 試用帳號的 demo 時間限制
- 多語系 i18n

**引用 finding**：H-1（ux-research Top 10 #1）、VA-1（信心 2/風險 5）、VA-16、VA-17、E-01（journey 0-30 秒 friction）、pm-strategy §4.2 方案 C、AC-5

**KPI 影響**：K5（首屏 trust signal density +1）、K1（viewer 角色 5 秒找到帳號）

---

### Story #2：儀表板角色權限矩陣固定卡片（三角色登入後都能看到）

**優先級**：P0 | **對應 PM 必動項**：M1 方案 A | **Sprint**：1 | **估時**：1-1.5 小時

**As a** 任何角色的使用者（Admin / User / Viewer）或評審
**I want to** 在儀表板頂部看到一張固定顯示的角色權限矩陣卡片，並高亮我目前的角色欄位
**So that** 我在第一時間就知道這套系統有三角色 RBAC 設計，以及我自己能做什麼 / 不能做什麼

**Acceptance Criteria**：

1. Given 任何角色登入後進入儀表板，when 頁面渲染完成，then 在頁面標題下方、系統狀態 header 之前，有一個顯眼的 container 卡片（`border=True`），顯示完整 3 × 13 角色權限矩陣
2. Given 權限矩陣卡片渲染，when 當前登入角色是 viewer，then viewer 欄的所有格子視覺上與其他欄不同（高亮色或 bold 標記），並有一行文字「您目前的角色：Viewer（一般訪客）」
3. Given 權限矩陣卡片渲染，when 當前登入角色是 admin，then admin 欄高亮，且矩陣中「✓ 獨有」項目（例如「系統設定」「用戶管理」）有視覺區分
4. Given 矩陣卡片存在，when 頁面繼續往下滾動，then 系統狀態 header（●/○ 連線、告警數）+ 4 個 metric cards 正常顯示，矩陣卡片不遮蓋後續元件
5. Given 系統管理頁的既有矩陣 expander（`5_系統管理.py:88`），when admin 進入系統管理，then 原有矩陣 expander 仍存在且 `expanded=True`（改為預設展開，不刪除）

**Edge Cases**：

- **HTML 高亮被 Streamlit sanitize**（VA-13 信心 3）：若 `unsafe_allow_html=True` 的 `<td style="background:#fff3cd">` 無效，退化為當前角色欄用 markdown `**粗體 ✓**` 標記
- **Viewer 看不到系統管理 tab**：Viewer 進系統管理頁會被 RBAC 擋回，OK
- **矩陣卡片高度過長破壞 viewport**：若 13 行矩陣讓 metric cards 超出首屏，考慮用 `st.expander("角色說明", expanded=True)` 包住矩陣
- **角色名稱顯示一致性**：矩陣中角色名稱（Admin / User / Viewer）必須與右上角用戶資訊欄的角色名稱字串一致

**Out of Scope**：
- Sidebar 角色 badge（pm-strategy §4.2 方案 B，本次不做）
- 矩陣動態更新（Streamlit 頁面重新整理即可）
- 超過 3 個角色的 RBAC 擴充

**引用 finding**：P0-1（pm-strategy §2）、D-1（ux-research 儀表板）、VA-2/VA-3/VA-4/VA-12/VA-13、E-03/E-10（journey）、pm-strategy §4.3 推薦組合、K1

**KPI 影響**：K1（角色 RBAC 可見度）、K5（trust signal +1）

---

### Story #3：5 頁 Onboarding Micro-copy（每頁說明卡）

**優先級**：P0 | **對應 PM 必動項**：M2 | **Sprint**：1 | **估時**：45-60 分鐘

**As a** 首次使用系統的評審或角色使用者
**I want to** 在每個頁面的標題下方看到一段說明「這頁在幹嘛 / 看什麼 / 怎麼用」的微文案
**So that** 我不需要靠猜測就知道每個功能模組的用途，降低認知負荷

**Acceptance Criteria**：

1. Given 評審進入儀表板頁，when 頁面渲染，then 頁面標題下方（在矩陣卡片或 system status header 之前）有 `st.caption()` 顯示說明文字，不超過 80 中文字
2. Given 評審進入資料管理頁，when 頁面渲染，then 頁面標題下方有 caption 說明，包含「上傳 CSV」「inline 編輯」「篩選」等關鍵動詞
3. Given 評審進入分析報表頁，when 頁面渲染，then caption 說明「即時 + 錄入資料的統計摘要、時間趨勢、類別分布，可匯出 Excel」
4. Given 評審進入即時監控頁，when 頁面渲染，then caption 說明「每秒推送 WebSocket 資料，5 大指標即時呈現，紅色告警為超閾值異常」
5. Given 評審進入系統管理頁，when admin 角色渲染，then caption 說明「用戶管理、系統設定、Audit log、動態閾值調整（僅 Admin 可見）」
6. Given 5 頁 caption 已加入，when 開發者 grep 各頁 `st.caption`，then 每頁至少一個 caption 在 `st.title()` 之後 50 行內出現

**Edge Cases**：
- caption 文字版本管理：靜態字串，無需 i18n
- Viewer 進系統管理被擋：caption #5 只有 admin 看到
- caption 過長截斷：可用 `st.markdown("<small>...")` 替代
- 5 頁同時修改並發 push：派 5 個 sub-agent 並行各改 1 頁

**Out of Scope**：
- 互動式 onboarding tour
- 影片或 GIF 教學內嵌
- caption 動態更新

**引用 finding**：P0-2（pm-strategy §2）、VA-5/VA-6、codebase-audit Section 5 #1-#20、pm-strategy §5.1 M2、pm-strategy §6.3 反指標 #2

**KPI 影響**：K3（評審 demo 後能說出 4/5 模組名稱）、K4（功能說明覆蓋率從 41% 提升）

---

### Story #4：即時監控 Demo 控制面板（手動觸發異常）

**優先級**：P0 | **對應 PM 必動項**：M3 | **Sprint**：2 | **估時**：1.5-2 小時

**As a** 評審（Persona D Eric）或任何角色使用者
**I want to** 在即時監控頁看到一個「Demo 控制」區塊，能手動觸發一次異常 snapshot 注入
**So that** 我不需要等 60 秒 APScheduler anomaly injection period，可以立即看到告警卡、紅字 cell、異常 marker 三層視覺效果

**Acceptance Criteria**：

1. Given 評審在即時監控頁，when 頁面渲染，then 折線圖上方或系統狀態 header 下方有一個「Demo 控制」container，包含「觸發一次模擬異常」按鈕
2. Given Demo 控制面板可見，when 評審點擊「觸發一次模擬異常」，then FE 端注入一筆 mock anomaly snapshot（`anomaly_flags` 包含至少 1 個 True），buffer 立即更新，無需等後端 scheduler
3. Given mock anomaly 注入成功，when 頁面下一次 autorefresh（≤ 1 秒），then 活躍告警卡片顯示該 metric 異常（`st.error` 或 `st.warning`），且告警 metric 名稱可讀（非純數字 ID）
4. Given mock anomaly 注入，when Pandas Styler 渲染 60 筆表格，then 含 anomaly_flags=True 的 row 顯示淡粉紅背景，且 anomaly cell 顯示紅字；若 Styler 渲染失敗，顯示 `st.warning("樣式渲染降級，資料仍正確")` 而非靜默 fallback
5. Given mock anomaly 注入，when 折線圖渲染，then 該 tick 的 anomaly 點顯示 circle-open red marker 在正確的 metric subplot 上

**Edge Cases**：
- **FE-only mock 不打 BE**（VA-8 信心 2/風險 5）：mock snapshot 必須使用與後端 wide format v2 schema 完全一致的 Python dict，建立前需 print mock dict 對照 `/realtime/history` 真實 response
- **Pandas Styler 靜默 fallback 風險**（VA-15）：既有 `4_即時監控.py:344-359` 的 `try/except` 靜默吞掉 Styler exception，改為 log + warning
- **Buffer 已滿**：buffer 上限 60 筆，注入後若 buffer > 60，deque 自動 popleft
- **冷啟動空 buffer**：BE cold start 前 60 秒 `/realtime/history` 空，此時按按鈕應仍有效
- **Timezone**：mock snapshot 的 `timestamp` 需用 `datetime.now(timezone.utc).isoformat()`（避免 O-P0-5 timezone 問題）

**Out of Scope**：
- 修改後端 APScheduler 邏輯
- 「持續每秒觸發異常」模式
- mock anomaly 的 category/metric 可自訂

**引用 finding**：P0-3（pm-strategy §2）、R-1（ux-research 即時監控）、VA-7（信心 3/風險 5）、VA-8（信心 2/風險 5）、VA-15、E-06（journey）、pm-strategy §5.1 M3、pm-strategy §8 mitigation

**KPI 影響**：K2（即時告警觸發成功率 100%）、pm-strategy §6.3 反指標 #3（「我等很久都沒看到異常」）

---

### Story #5：即時監控閾值動態同步（Admin 改設定後 FE 同步）

**優先級**：P0 | **對應 PM 必動項**：M3 sub | **Sprint**：2 | **估時**：2-3 小時

**As a** Admin（Persona A 林佳穎）
**I want to** 在系統管理頁改動態閾值後，即時監控頁的異常判斷邏輯能反映最新設定，而不是沿用 hardcode 前端值
**So that** 我調整閾值後確認系統真的以新閾值判斷，避免「設定生效但介面騙我」的信任崩壞

**Acceptance Criteria**：

1. Given Admin 在系統管理頁將 CPU 閾值從 80% 改為 60%，when 即時監控頁下次 autorefresh，then 告警卡片的閾值參考值反映 60%（非 hardcode 80%）
2. Given 即時監控頁啟動，when 頁面第一次渲染，then FE 打一次 `GET /admin/settings`（使用 `@st.cache_data(ttl=30)`），拿到動態閾值並存入 session_state
3. Given Viewer 或 User 角色登入即時監控頁，when 頁面打 `/admin/settings`，then 若回傳 403，FE 靜默使用 hardcode fallback 閾值（不 crash，不 expose 403 給使用者），並在 Demo 控制區塊顯示「閾值顯示為預設值（唯讀）」提示
4. Given Admin 改完閾值並且在即時監控頁，when Admin 點擊「清空緩衝區 / 重新整理閾值」按鈕，then `@st.cache_data.clear()` 清除 settings cache
5. Given 閾值 fetch 網路失敗（BE 無回應），when 頁面渲染，then FE 使用 hardcode fallback 閾值，顯示 `st.warning("無法取得動態閾值，使用預設值")`

**Edge Cases**：
- **VA-9 最關鍵風險**（信心 1/風險 5）：需在動工前 curl viewer JWT 打 `/admin/settings`。若 403，AC-3 fallback 方案是唯一合規解法
- **cache TTL 競爭**：30 秒落差是可接受範圍
- **O-P0-1 category keys hardcode**：列入 Out of Scope
- **Settings API schema 變動**：若不符 FE 期待，warning + fallback

**Out of Scope**：
- 修復 O-P0-1（category keys FE hardcode vs BE SIMULATOR_CATEGORIES）
- Admin 設定變更後的 WebSocket push
- 閾值歷史版本記錄 / rollback

**引用 finding**：R-2（ux-research Top 10 #8）、VA-9（信心 1/風險 5，最關鍵）、O-P0-1、A-06（journey）、pm-strategy §5.1 M3、`4_即時監控.py:196`

**KPI 影響**：K4（顏色語意正確 → 信任感）、pm-strategy §6.1 narrative #2

---

### Story #6：即時監控折線圖多 Metric 獨立可讀性（Small Multiples 重構）

**優先級**：P0 | **對應 PM 必動項**：M3 sub | **Sprint**：2 | **估時**：1-1.5 小時

**As a** Admin（Persona A 林佳穎）或評審（Persona D Eric）
**I want to** 在即時監控頁看到每個 metric（溫度 / 氣壓 / 濕度 / CPU / 電壓）各自在獨立的 Y 軸上繪製折線圖
**So that** 我能個別判讀 voltage（量級 ±5V）而不被氣壓（1013 hPa）壓扁成貼底直線

**Acceptance Criteria**：

1. Given 即時監控頁渲染折線圖，when buffer 有 ≥ 2 筆資料，then 5 個 metric 各自顯示在獨立的 subplot（plotly `make_subplots(rows=5, cols=1, shared_xaxes=True)`），每個 subplot 有獨立 Y 軸標題和自動 range
2. Given 5 個 metric subplots 渲染，when buffer 中某 tick 有 anomaly_flags=True 的 metric，then 該 metric 的 subplot 上對應 tick 位置顯示 circle-open red anomaly marker
3. Given 5 個 subplots 渲染，when Chrome MCP 在 1080p viewport 截圖，then 5 張子圖完整顯示在 viewport 內（不需要 scroll）；若超出，加 multiselect 預設選 2-3 個 metric（VA-19）
4. Given 評審點「觸發一次模擬異常」（Story #4），when mock anomaly 注入 buffer，then 對應 metric subplot 的 anomaly marker 出現，而非誤放到錯誤的 subplot
5. Given subplots 已渲染，when buffer 新增一筆 tick（autorefresh），then 圖形平滑延伸，x 軸時間窗口維持最近 60 筆

**Edge Cases**：
- **VA-10 anomaly marker 位置**（信心 3/風險 4）：marker 的 `row` 參數必須對應正確的 metric index
- **VA-11 單屏顯示**（信心 2/風險 3）：5 張 subplots 在 1080p 高度可能超出，退化為 multiselect 預設選 2-3 個
- **shared_xaxes**：5 subplots 共享 x 軸，缺值 plotly 自動 skip
- **uirevision**：防止 autorefresh 時 hover tooltip 閃爍
- **電壓 voltage 量級**：獨立 Y 軸解決 pm-strategy §6.3 反指標 #5「voltage 的線在哪？」
- **Plotly height**：建議 `height=600-800`

**Out of Scope**：
- 系統管理頁「即時資料歷史」的 5 metric 共軸圖（S-6）
- 為每個 subplot 加個別 zoom / pan 控制
- 其他頁面圖表

**引用 finding**：R-1（ux-research Top 10 #2）、VA-10（信心 3/風險 4）、VA-11（信心 2/風險 3）、VA-19、E-06（journey）、pm-strategy §5.1 M3、pm-strategy §6.3 反指標 #5

**KPI 影響**：K2（即時監控核心 use case 可讀）、pm-strategy §6.1 narrative #2

---

### Story #7：角色 Demo Banner 與建議動線引導

**優先級**：P0 | **對應 PM 必動項**：M4 | **Sprint**：2 | **估時**：1-1.5 小時

**As a** 評審或首次 demo 的角色使用者
**I want to** 在儀表板頁面（登入後首頁）看到一個根據我角色顯示的「建議 demo 動線」提示
**So that** 我知道接下來應該看哪幾頁、按什麼順序，不會花 5 分鐘亂逛卻沒抓到重點

**Acceptance Criteria**：

1. Given Viewer 登入儀表板，when 頁面渲染，then 在角色矩陣卡片下方顯示 `st.info()` banner，內容為「建議 Viewer demo 動線：儀表板 → 即時監控 → 分析報表」
2. Given Admin 登入儀表板，when 頁面渲染，then banner 顯示「建議 Admin demo 動線：儀表板 → 即時監控（試觸發異常）→ 系統管理（改閾值 / 看 Audit log）→ 分析報表（匯出 Excel）」
3. Given User 登入儀表板，when 頁面渲染，then banner 顯示「建議 User demo 動線：儀表板 → 資料管理（上傳 CSV）→ 分析報表 → 即時監控」
4. Given 任何角色的 banner 顯示，when 使用者勾選「不再顯示」checkbox（若實作），then `st.session_state["hide_banner"] = True`
5. Given banner 渲染，when 評審沒有互動只是瀏覽，then banner 不遮擋任何功能操作元件

**Edge Cases**：
- **VA-22 被誤解為強迫導覽**（信心 2/風險 3）：使用 `st.info()` 非 modal
- **VA-23 Admin 反覆看不耐煩**：加「不再顯示」checkbox 存 session_state
- **Banner 連結行為**：Streamlit 多頁面切換連結格式，若寫錯退化為括號標注

**Out of Scope**：
- Onboarding tour（step-by-step 引導）
- 動態生成個人化動線
- 跨頁面 persistent banner

**引用 finding**：VA-22（信心 2/風險 3）、VA-25、E-03/E-10/V-02（journey）、pm-strategy §5.1 M4

**KPI 影響**：K3（評審能說出 4/5 模組名稱）、K5（trust signal +1）

---

### Story #8：Delta Color 反語意修復 + Pandas Styler 穩健化

**優先級**：P0 | **對應 PM 必動項**：M5 | **Sprint**：2 | **估時**：30-45 分鐘

**As a** 評審（Persona D Eric）或 Admin（Persona A 林佳穎）
**I want to** 即時監控頁的告警 metric 卡片顯示正確的顏色語意（異常 +50 顯示紅色警告，而非綠色）
**And I want to** 異常 row 的淡粉紅樣式在任何情況都正確顯示（不因 Pandas Styler 靜默失敗而消失）
**So that** 我不會因為顏色語意反向而誤判系統狀態，也能確保設計賣點（粉紅高亮）真實呈現

**Acceptance Criteria**：

1. Given 告警 metric 卡片顯示異常 metric，when 數值為正偏差（如 CPU +50%），then `st.metric()` delta 顯示紅色（danger）而非綠色；即 `delta_color` 不使用 `"inverse"`
2. Given `4_即時監控.py` 中所有 `delta_color="inverse"` 出現位置，when 開發者 grep，then 每一個位置都被 audit 並有意識決定（保留的有 comment 說明原因）（VA-14）
3. Given Pandas Styler 渲染 60 筆表格，when 包含 anomaly row，then 淡粉紅 background + 紅字 cell 確實顯示（不靜默 fallback）
4. Given Pandas Styler 渲染失敗，when exception 發生，then 記錄到 stderr（`logging.warning()`），頁面顯示 `st.warning("表格樣式載入失敗，資料內容仍正確")`，並以無樣式 `st.dataframe()` 顯示
5. Given M5 修補完成，when 跑 `pytest -v --cov=app`，then 所有後端測試仍全綠

**Edge Cases**：
- **VA-14 影響範圍**（信心 4/風險 2）：需 grep `delta_color="inverse"` 確認位置
- **delta_color 可選值**：Streamlit 1.39 接受 `"normal"` / `"inverse"` / `"off"`
- **Styler 空 buffer / 全異常**：不 crash

**Out of Scope**：
- 重新設計「異常嚴重度」顏色系統
- 其他頁面 delta_color audit（先聚焦 `4_即時監控.py`）

**引用 finding**：P1-1、P1-2（pm-strategy）、VA-14（信心 4/風險 2）、VA-15（信心 3/風險 3）、A-03（journey）、pm-strategy §5.1 M5、pm-strategy §6.3 反指標 #4

**KPI 影響**：K4（視覺設計一致性）

---

### Story #9：儀表板 Metric Cards 品質指標化

**優先級**：P1 | **對應 UX finding**：D-1（Top 10 #3）| **Sprint**：3 | **估時**：45-90 分鐘

**As a** Viewer（Persona C 王主管）或評審
**I want to** 在儀表板 4 個 metric cards 中看到系統「品質」資訊（異常率 / 系統健康度），而不只是筆數
**So that** 我能在 30 秒內判斷系統目前健康還是有問題

**Acceptance Criteria**：
1. Given Viewer 登入儀表板，when 4 個 metric cards 渲染，then 其中至少 1 個卡片顯示「品質」訊號（如「今日異常率 0.014%」或「系統健康度」綠/黃/紅圖示）
2. Given 系統在過去 1 小時有 3 次異常，when 儀表板 metric card 渲染，then 卡片數值反映「3 次異常」，並有 delta 比較
3. Given 4 個 metric cards 存在，when 評審 hover 任一 metric card，then 顯示 tooltip 說明此數字含義（`help=` 參數）
4. Given 系統 BE 無法取得品質統計，when metric cards 渲染，then 顯示「--- 載入中」而非 crash

**Edge Cases**：
- **BE API 支援**：若 `/analytics/summary` 不支援過去 1 小時 anomaly count，FE 需從 `/realtime/history` 計算
- **Viewer 權限**：需確認 RBAC
- **並發刷新**：metric cards 使用 `@st.cache_data(ttl=10)` 快取

**Out of Scope**：
- 完整告警 timeline UI
- 即時 WebSocket push metric cards

**引用 finding**：D-1（ux-research Top 10 #3）、VA-29/VA-30、Top 15 friction #4、V-01/V-05/E-03

**KPI 影響**：K1（viewer 30 秒判斷系統狀態）

---

### Story #10：即時告警卡片嚴重度視覺化

**優先級**：P1 | **對應 UX finding**：R-5（Top 15 #6）| **Sprint**：3 | **估時**：30-45 分鐘

**As a** Admin（Persona A 林佳穎）
**I want to** 在即時監控頁的告警區塊看到每個異常 metric 的名稱 + 當前值 + 超閾值百分比
**So that** 我能一眼判斷哪個 metric 最嚴重

**Acceptance Criteria**：
1. Given 即時監控頁有活躍告警，when `active_alert_metrics` 含 ≥ 1 個 metric，then 告警卡片顯示：metric 中文名稱（如「CPU 使用率」）+ 當前值（如 `92%`）+ 「超閾值 +15%」
2. Given 多個 metric 同時異常，when 告警卡片排列，then 每行最多 3 個卡片（`st.columns(min(len, 3))`）
3. Given 告警卡片渲染，when 即時 autorefresh，then 告警卡片顯示最新 tick 的值

**Edge Cases**：
- **告警 metric 名稱映射**：加 `METRIC_DISPLAY_NAMES` dict 做中文映射
- **全部 5 metric 同時異常**：5 個卡片 2 行顯示

**Out of Scope**：
- 告警嚴重度分級
- 告警歷史 timeline

**引用 finding**：R-5（ux-research 補充）、A-03（journey）、pm-strategy P1-1

**KPI 影響**：K2（告警 100% 可識別）

---

### Story #11：系統管理頁面可用性修補（4 個 P1 痛點）

**優先級**：P1 | **對應 UX finding**：S-3/S-4/S-5/S-7/S-8 | **Sprint**：3 | **估時**：45-60 分鐘

**As a** Admin（Persona A 林佳穎）
**I want to** 系統管理頁的 4 個已知可用性問題被修補（audit log 10 筆限制 / settings expander 全開 / DELETE user UI 缺口 / 角色矩陣 expander 改為預設展開）
**So that** 我能高效率完成用戶管理、設定調整、日誌查詢等管理工作

**Acceptance Criteria**：
1. Given Admin 查看 Audit log，when 超過 10 筆，then 不再用 `limit=10` 截斷，改為顯示前 50 筆 + 分頁按鈕
2. Given Admin 進系統管理頁，when Settings section 渲染，then 5 個設定 expander 預設 `expanded=False`，頂部加「展開全部設定」按鈕
3. Given Admin 在用戶管理 tab 看到用戶列表，when 頁面渲染，then 每個 user row 有「刪除」按鈕，呼叫 `DELETE /users/{id}` API
4. Given Story #2 要求系統管理頁矩陣 expander `expanded=True`，when Admin 進系統管理，then 角色矩陣 expander 預設展開

**Edge Cases**：
- **DELETE user 缺少 confirmation**：可降級為「刪除按鈕旁加 warning text」
- **並發刪除**：FE 需捕捉 404 並顯示「此用戶已被刪除」
- **DELETE 自己**：FE 需隱藏「刪除自己」按鈕或 disable

**Out of Scope**：
- 改密碼 UI 二合一
- Audit log 全量 export

**引用 finding**：S-3/S-4/S-5/S-7/S-8（ux-research）、VA-12/VA-13、codebase-audit Section 3 5.3、E-07（journey）

**KPI 影響**：K4、pm-strategy §6.1 narrative #3

---

### Story #12：分析報表時間趨勢圖 Source Toggle 語意一致性

**優先級**：P2 | **對應 UX finding**：A-2（Top 10 #7）| **Sprint**：保留 | **估時**：1-1.5 小時

**As a** User（Persona B 陳家豪）
**I want to** 在分析報表頁選擇「資料來源：即時資料」時，時間趨勢圖仍顯示折線圖（而非 Bar chart）
**So that** UI 的視覺語言一致

**Acceptance Criteria**：
1. Given User 在分析報表頁將「資料來源」切換到「即時資料」，when 時間趨勢圖渲染，then 顯示折線圖（`go.Scatter`）而非 Bar chart
2. Given 折線圖使用即時資料 source，when 即時資料較少（cold start 30 秒），then 顯示「資料點不足，顯示可用的 N 筆資料」提示
3. Given Source toggle 切換，when 來源從「錄入資料」改為「即時資料」，then 圖表 title 更新

**Edge Cases**：
- **VA-32 接受假設**（信心 2/風險 3）：若評審不深入此頁，影響低
- **BE 無 realtime time-range bucket API**：FE 需從 `/realtime/history` 拿 raw rows 後 pandas resample
- **Source toggle 不同步**：本 story 只修「時間趨勢圖那個 source」

**Out of Scope**：
- 統一三處資料來源 selector（A-1）
- 為 realtime 時間趨勢加 bucket 選擇
- 新增 BE `/analytics/realtime-timerange` endpoint

**引用 finding**：A-2（ux-research Top 10 #7）、VA-32、E-05/U-07/U-08（journey）、AC-6

**KPI 影響**：K4（視覺語言一致性），但 P2

---

## Section 3：優先級與 Sprint 計畫

### 優先級總表

| Story | 標題 | 優先級 | PM 必動項 | Sprint | 估時 |
|---|---|---|---|---|---|
| #1 | Home 試用帳號一鍵帶入 | P0 | M1 方案 C | 1 | 30-45 min |
| #2 | 儀表板角色矩陣固定卡 | P0 | M1 方案 A | 1 | 60-90 min |
| #3 | 5 頁 Onboarding Micro-copy | P0 | M2 | 1 | 45-60 min |
| #4 | 即時監控 Demo 控制面板 | P0 | M3 | 2 | 90-120 min |
| #5 | 即時監控閾值動態同步 | P0 | M3 sub | 2 | 120-180 min |
| #6 | 即時監控 Small Multiples | P0 | M3 sub | 2 | 60-90 min |
| #7 | 角色 Demo Banner | P0 | M4 | 2 | 60-90 min |
| #8 | Delta Color 修復 + Styler | P0 | M5 | 2 | 30-45 min |
| #9 | Metric Cards 品質化 | P1 | — | 3 | 45-90 min |
| #10 | 告警卡片嚴重度視覺化 | P1 | — | 3 | 30-45 min |
| #11 | 系統管理頁面可用性修補 | P1 | — | 3 | 45-60 min |
| #12 | Source Toggle 語意 | P2 | — | 保留 | 60-90 min |

- **P0 合計**：7.5-10.5 hr
- **P1 合計**：2-3.25 hr
- **P2**：1-1.5 hr（有餘裕才做）

### Sprint 計畫

**Sprint 1（Hour 0-2.5）：Foundation — 三角色可見度 + Onboarding**
- Story #1 + #2 + #3（可派 3 sub-agent 並行）
- 驗證閘：pytest 全綠 + Chrome MCP 截 3 角色 × Dashboard

**Sprint 2（Hour 2.5-8）：Core UX — 即時監控修補 + Demo 體驗**
- VA-9 先 curl 驗（5 min）
- Story #4 → #6（依賴）→ #5 → #7 → #8
- 驗證閘：pytest 全綠 + Chrome MCP 截 5 頁 × 3 角色 = 15 張 + 手動觸發異常 demo

**Sprint 3（Hour 8-12，有餘裕才做）：Polish — P1 增色**
- Story #9 + #10 + #11（可並行）

**Sprint 保留（P2）**：Story #12

---

## Section 4：Cross-Story 依賴圖

- Story #1 → 無依賴，最先做
- Story #2 → 依賴 `render_role_matrix()` helper 抽取
- Story #3 → 無依賴（可與 #2 並行）
- Story #4 → 依賴 mock anomaly schema 對齊 BE wide v2
- Story #5 → 依賴 VA-9 驗證結果
- Story #6 → 依賴 #4 完成（anomaly marker 位置驗）+ #5（閾值顯示）
- Story #7 → 依賴 #2 完成（session_state role）
- Story #8 → 無依賴
- Story #9 → 依賴 BE `/analytics/summary` 支援
- Story #10 → 依賴 #4
- Story #11 → 與 #2 AC-5 不衝突
- Story #12 → 無依賴（P2）

**阻塞性依賴**：
- VA-9 驗證是 Story #5 的 blocker
- Story #4 必須在 Story #6 驗收之前完成

**可並行**：
- Sprint 1：#1 / #2 / #3 三個並行
- Sprint 2：#7 / #8 與 #4/#5/#6 並行

---

## Section 5：評審 Demo Script

### Demo Script A：Viewer 5 分鐘快速掃（驗 K1 + K2 + K3）

**角色**：Viewer
**目標**：5 分鐘內讓評審說出「RBAC」「即時監控」「異常觸發」三個關鍵詞

| Step | 時長 | 動作 | 應看到 | 驗 |
|---|---|---|---|---|
| 1 | 0-30s | 開 Home | 試用帳號 expander 列三組帳號 | K5、AC-1 #1 |
| 1.5 | 點「以 Viewer 登入」 | 自動帶入 → 登入 | — | — |
| 2 | 30s-2min | 儀表板 | 角色矩陣（Viewer 高亮）+ Demo Banner | K1、AC-2 #2 / AC-1 #3 / AC-1 #7 |
| 3 | 2-3.5min | 即時監控 | 5 metric small multiples 圖；按「觸發模擬異常」→ 告警卡 + 粉紅 row + 紅字 + marker | K2、K4 |
| 4 | 3.5-5min | 分析報表 | 統計摘要 + 趨勢圖 + Excel 匯出 | K3 |

**總結問**：「你覺得這套系統有幾個角色？每個角色能做什麼？」
→ 預期回答：「3 角色，Dashboard 有告訴我」→ K1 達標

---

### Demo Script B：Admin 深度驗（驗 K4 + K5 + 需求覆蓋感知）

**角色**：Admin
**目標**：驗「Admin 改閾值 → 即時監控同步」、「Audit log 可查」、「5 大模組覆蓋」

| Step | 時長 | 動作 | 驗 |
|---|---|---|---|
| 1 | 0-1min | 登入 + 儀表板 | 角色矩陣 Admin 欄高亮、5 trust signal |
| 2 | 1-3min | 系統管理 | 調整 CPU 閾值、看 Audit log、PATCH role、DELETE user |
| 3 | 3-4min | 即時監控 | 閾值同步、觸發異常、delta_color 顏色語意 |
| 4 | 4-5min | 分析報表 + 資料管理 | Excel 匯出、inline edit |

**總結**：「BE 主要功能？」
→ 預期：「24 endpoints、RBAC、WebSocket、Alembic、Audit log、動態閾值、Docker」
→ 驗 K3 ≥ 4 模組、K5 trust signal ≥ 3

---

### Demo Script C：Builder 自測 Checklist（3 分鐘）

```
□ Home 試用帳號 expander 可見，3 角色帳號列出
□ 點「以 Viewer 登入」→ 自動帶入並成功登入
□ 儀表板：角色矩陣 Viewer 欄高亮，caption 可見
□ 儀表板：Demo Banner 顯示「建議 Viewer 動線」
□ 即時監控：5 metric subplots 各自 Y 軸
□ 即時監控：按「觸發模擬異常」→ 告警卡顯 metric 名稱 + 數值
□ 即時監控：淡粉紅 row 顯示，delta color 紅
□ 分析報表：caption 可見，圖表可載入
□ 資料管理：caption 可見，data_editor 可用
□ 系統管理（admin）：角色矩陣 expander 展開，Audit log >10 筆可見
□ pytest -v：全綠（33 perm tests 不 regress）
```

---

## Appendix：v3 範疇外明確排除清單（v4 候選）

以下 14 個改動本次不做，避免 scope creep：

1. DELETE user UI（G1）— Sprint 1+2 工時充裕可升格，否則 v4
2. CSV upload preview / dry-run（ux-research Top 10 #4）
3. Viewer 公開唯讀快照連結
4. 申請提權表單
5. Plotly `displayModeBar=False`
6. 系統設定單一 form 提交（S-7）
7. Inline edit dirty state warning（DM-4）
8. Excel 單步下載
9. 完整 DB pool 顏色語意系統
10. 角色 chip badge sidebar（方案 B）
11. Audit log timeline UI
12. 登出後 JWT 無效化（需動 BE）
13. 國際化 i18n
14. Streamlit → 其他 framework 替換

---

USER STORIES DONE
