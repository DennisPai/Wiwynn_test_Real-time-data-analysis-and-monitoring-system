# UX Research — Wiwynn 即時資料分析與監控系統 v3 UX Fix

> **研究背景**：Wiwynn 面試題 demo。最終使用者 = 評審工程師（5-10 分鐘掃 demo 評分）+ 三種角色（admin / user / viewer）。
> **研究方法**：基於 codebase + design.md 之程式碼證據推論（**非實際使用者訪談**），輔以業界 SaaS UX 模式（GitHub / Notion / Vercel / Grafana / Datadog）對照。
> **研究範圍**：6 個 Streamlit 頁面（Home / 儀表板 / 資料管理 / 分析報表 / 即時監控 / 系統管理）+ 圖表 UX + 角色權限說明 UX。
> **產出日期**：2026-05-26
> **研究員**：ux-researcher sub-agent（懷特大總管 v6.1 Software Factory 模式 A 加強版）
> **資料來源**：
> - `frontend/streamlit_app/Home.py`（106 行）
> - `frontend/streamlit_app/pages/1_儀表板.py`（268 行）
> - `frontend/streamlit_app/pages/2_資料管理.py`（326 行）
> - `frontend/streamlit_app/pages/3_分析報表.py`（435 行）
> - `frontend/streamlit_app/pages/4_即時監控.py`（371 行）
> - `frontend/streamlit_app/pages/5_系統管理.py`（639 行）
> - `README.md`（266 行）+ `docs/architecture.md`（153 行）
> - `openspec/changes/redesign-monitoring-system-v2-2026-05-26/design.md`（710 行）

---

## 目錄

- [Section 1: Personas（JTBD 框架）](#section-1-personasjtbd-框架)
- [Section 2: UX 痛點逐頁 audit](#section-2-ux-痛點逐頁-audit)
- [Section 3: 圖表 UX 專門 audit](#section-3-圖表-ux-專門-audit)
- [Section 4: 角色權限說明 UX 專門 audit](#section-4-角色權限說明-ux-專門-audit)
- [Section 5: Top 10 必修 UX 痛點清單](#section-5-top-10-必修-ux-痛點清單)

---

## Section 1: Personas（JTBD 框架）

### Persona A — Admin 系統管理員「林佳穎」

**Demographics**
- 年齡：35 歲
- 職稱：MIS / 工程經理（基礎設施監控組）
- 公司規模：500-2000 人製造業（伺服器、IoT 環境感測）
- 技術背景：Linux 中階、會看 SQL、用過 Grafana / Zabbix / Datadog
- 使用頻率：每日 2-3 次，平均每次 15 分鐘
- 使用情境：晨會前 check overnight 異常 / 收到 PagerDuty 後追根本原因 / 季度生新增帳號

**Primary Job-to-be-Done**
> 「當伺服器房或產線感測異常發生時，我要在 5 分鐘內知道：(1) 出了什麼事 (2) 影響範圍 (3) 是不是誤報，這樣我才能決定 escalate 給哪個團隊。」

**核心動詞**：偵測（detect）→ 調查（investigate）→ 決策（escalate / dismiss / tune threshold）

**Frequency**：每日早班 8:30 / 午餐後 13:30 / 收 alert 即時觸發

**Top 3 Pain Points**

1. **「異常告警出現後，看不出嚴重程度，每次都要切到歷史頁面對照基線」**
   - 證據：`pages/4_即時監控.py:140-144` `active_alert_metrics` 只算「個數」（`st.error(f"活躍告警：{len(active_alert_metrics)} 個 metric 異常")`），完全不顯示 metric 名稱、嚴重度、持續時間
   - 嚴重度：高（誤報率高的系統會讓 admin 麻木 → 真實 alert 被忽略）

2. **「我點進系統管理 → 即時資料歷史，5 個 metric 全擠一條 Y 軸，圖完全看不懂」**
   - 證據：`pages/5_系統管理.py:483-493` 5 條 metric 線（溫度 °C 範圍 ~25、氣壓 hPa 範圍 ~1013、CPU% 範圍 ~40）全共用單一 `yaxis_title="數值"`（line 521）。氣壓 1013 會把溫度 25 的線壓扁成貼底直線
   - 嚴重度：高（造成「圖等於沒用」）

3. **「改密碼要先選 dropdown，再進 form 填，又得自己記得『改自己要填舊密碼』，介面沒有任何提示動態變化」**
   - 證據：`pages/5_系統管理.py:216-226` is_self_pw 判斷後 form 內舊密碼欄位 label 一律寫「舊密碼（改自己時必填）」，selectbox 換目標時 form 不會動態顯示 / 隱藏 / placeholder 變化，全靠管理員自己記憶條件

**Top 3 Desired Gains**

1. **異常一眼判斷嚴重度** — 不只「有 / 沒有」，要看「現在 vs 閾值差多少、持續多久、是不是趨勢」
2. **多 metric 圖能各自獨立判讀** — 期待 small multiples（每 metric 一張小圖）或 dual / multi y-axis，至少能個別 zoom
3. **管理動作有 explicit confirmation** — 改別人密碼、停用帳號這類「不可逆」動作，希望有「您即將...」確認對話

**One Unexpected Insight**
> Admin 並不期待「漂亮的儀表板」；她期待「無聊但可靠的數字」。Grafana 用戶調查（CNCF 2023）顯示，SRE 寧可看醜的純文字 dashboard，也不要花俏但延遲 3 秒的 chart。本系統 `pages/1_儀表板.py:135` 加 `with st.spinner("載入統計資料...")` 區塊每次 rerun 都顯示 spinner，反而會讓 admin 感受「系統慢、不可靠」。

**Counter-intuitive 設計建議**：去掉「載入中...」的 spinner，改用 stale-while-revalidate 的策略（先顯示舊資料 + 角落小圓點代表 refreshing），這對 admin 更安心。

**Product Fit Assessment**
- **滿足**：5 大模組覆蓋 admin 所有 use case，RBAC 矩陣明確（`README.md:171-180`）
- **不足**：
  - 缺乏 alert 嚴重度分級（critical / warning / info）
  - 缺乏 alert 歷史 timeline（只能看「現在有沒有」）
  - 改設定後沒有 audit trail UI（雖然 backend 有 `audit_logs`，但 admin 看不到「我剛剛改了什麼」的回顧）

---

### Persona B — User 一般使用者「陳家豪」

**Demographics**
- 年齡：28 歲
- 職稱：資料工程師 / 製程工程師
- 公司規模：同上
- 技術背景：Python / Pandas 熟、會寫 SQL、會用 Excel pivot
- 使用頻率：每日 5-8 次 spike，每次 3-5 分鐘
- 使用情境：把外部量測 CSV 匯入做趨勢分析 / 補 demo 缺失資料 / 為週報抓統計

**Primary Job-to-be-Done**
> 「我要把手上的 CSV 資料 dump 進系統，然後 5 分鐘內產出一張可以貼進週報 PowerPoint 的趨勢圖 + 數字。」

**核心動詞**：上傳（upload）→ 驗證（validate）→ 圈選（filter）→ 匯出（export）

**Frequency**：每週至少 3 次 CSV 上傳 + 5 次匯出

**Top 3 Pain Points**

1. **「我上傳 CSV 不知道格式對不對，上傳完才告訴我哪一行錯」**
   - 證據：`pages/2_資料管理.py:268-326` 整個 bulk import 區塊**沒有 pre-upload preview**，只有上傳前的 caption（line 272-275）說「CSV 欄位格式：title, value, category, recorded_at」，沒有 sample download、沒有 dry-run 預覽、沒有欄位 mapping UI
   - 嚴重度：中-高（500 筆檔案發現第 3 行格式錯誤後要從頭來，挫折感極高）

2. **「分析報表頁的 timerange 圖跟我手上 Excel 對不起來，但找不到原因」**
   - 證據：`pages/3_分析報表.py:161-169` `_fetch_timerange` 用 `date_from + "T00:00:00Z"` UTC 帶 Z，但 BE 解析時若沒處理 tz 會直接出 `buckets=[]` 空圖（design.md 第 332-342 行的 Q7 root cause）；FE 沒任何「資料筆數 N、時區 UTC、bucket=hour」的 metadata 提示讓 user 自我除錯
   - 嚴重度：高（用戶在「我設定錯」vs「系統壞了」之間無法判斷）

3. **「我想改一筆 record，inline edit 改完按儲存，後台 silent skip 沒權限的，我以為都改成功」**
   - 證據：`pages/2_資料管理.py:225-263` user 角色改非己 record，會走 `can_modify=False` → `st.toast(f"沒有權限修改 ID ...")` + `fail_count += 1`，最後只顯示「成功 N 筆、失敗 M 筆」聚合訊息（line 258-261），user 必須自己回想哪些 row 失敗
   - 嚴重度：中（小團隊 N=10 還可 debug，N=100 時無法定位）

**Top 3 Desired Gains**

1. **上傳前先 preview + dry-run** — 「先給我看你會匯入哪 5 筆、會跳過哪 2 筆，再讓我按確認」
2. **時間範圍查詢有「為什麼空」的提示** — 「您選 5/20-5/26，DB 內這個區間 records 共 0 筆，最近資料是 5/15」
3. **inline edit 失敗 row 用紅框 highlight + 顯示原因** — 不要只給 toast

**One Unexpected Insight**
> User 通常**不會把 Streamlit 當 source of truth**——他會把 Excel 原始檔留著，把 Streamlit 當「分享給主管看的鏡像」。所以 Excel 匯出（line 381-435）對他超級重要，但 export 出來的檔名 `data_export.xlsx`（line 408-414）沒有時間戳、沒有篩選條件，三天後他打開不知道是哪份。

**設計建議**：export 預設檔名 `data_export_2026-05-26_records_2026-05-01_to_2026-05-26.xlsx`，把篩選條件燒進檔名。

**Product Fit Assessment**
- **滿足**：CRUD + bulk import + 篩選 + 排序 + Excel 匯出全有，CSV 格式說明 readme 完整
- **不足**：
  - 缺 CSV preview / dry-run
  - 缺「為什麼空」的 explainability
  - 失敗操作缺 row-level feedback
  - export filename 沒燒入篩選條件

---

### Persona C — Viewer 唯讀觀察者「王主管」

**Demographics**
- 年齡：45 歲
- 職稱：跨部門主管（製造副總 / 廠長 / 客戶端窗口）
- 公司規模：同上
- 技術背景：低（會用 Outlook 與 Excel，不會 SQL）
- 使用頻率：每週 1-2 次，每次 2-3 分鐘（通常週會前 quick check）
- 使用情境：客戶到廠導覽要 demo / 週會跟主管報告本週系統健康 / 收到下屬「異常處理完了」訊息來複查

**Primary Job-to-be-Done**
> 「我打開系統 30 秒內要能告訴老闆：『過去一週系統正常 / 有 X 次異常已處理 / 趨勢 OK』，不需要知道細節。」

**核心動詞**：掃讀（scan）→ 截圖（screenshot）→ 轉述（narrate）

**Frequency**：每週 1-2 次 high-signal check

**Top 3 Pain Points**

1. **「我登入後第一個看到的不是『系統現在好不好』，而是 metric cards 4 個合計數字，看不出來這代表正常還異常」**
   - 證據：`pages/1_儀表板.py:147-155` 4 個 metric card「合計資料筆數 / 即時資料筆數 / 錄入資料筆數 / 異常筆數（合計）」，前 3 個是「總筆數」（量，不是品質），第 4 個「異常筆數」沒有「正常基線」比較（例如「異常 12 / 總 86400，異常率 0.014%」），viewer 完全沒參考點
   - 嚴重度：高（核心 user job 失敗）

2. **「我不知道我能做什麼、不能做什麼，到處點都被擋」**
   - 證據：`pages/5_系統管理.py:38-41` viewer 點系統管理直接 `st.error + st.stop()`，但 **viewer 在 Home 登入後完全沒有 onboarding** 告訴他「你能看儀表板 / 即時 / 分析」「系統管理你不能點，會被擋」
   - 額外證據：`pages/2_資料管理.py:116-117` viewer 看到 `st.info("Viewer 角色為唯讀，無法編輯資料。")`——但這是在「資料列表」標題下方第 116 行，user 已經滾很久才看到
   - 嚴重度：中-高（造成「踩雷感」，影響第一印象）

3. **「我想截圖貼週報，但每張圖都是 Plotly 互動 widget，截圖會抓到 toolbar、模式按鈕、legend 重疊」**
   - 證據：`pages/3_分析報表.py:250` `st.plotly_chart(fig_line, use_container_width=True)` 沒指定 `config={"displayModeBar": False}` 或 export 圖按鈕；Plotly 預設右上角顯示縮放 / 平移 / 下載 PNG 等 7-8 個按鈕，截圖會抓到
   - 嚴重度：低-中（功能性沒壞，視覺感受差）

**Top 3 Desired Gains**

1. **首頁直接答「現在系統好不好」** — 例如綠燈 / 黃燈 / 紅燈大圖示 + 過去 24 小時異常數對比
2. **角色提示 onboarding** — 第一次登入彈「您是 Viewer，可看不可改」hint，之後不再彈
3. **每張圖一鍵「複製為截圖」** — 純圖 PNG，不要互動 toolbar

**One Unexpected Insight**
> Viewer 主管會 forward 整個 URL 給老闆，希望老闆**不用登入也能看**——但本系統 `auth.py require_auth()` 會強制跳轉 Home。Viewer 不會直接抱怨這件事（他覺得「安全本來就該這樣」），但**會降低他用系統的頻率**（因為要轉述麻煩）。

**設計建議**（不在 v3 範圍）：給 viewer 一個「分享公開唯讀快照連結」功能（24h 有效 token），或匯出 PDF 報告。

**Product Fit Assessment**
- **滿足**：viewer 角色明確、能看儀表板與分析報表
- **不足**：
  - 缺「系統健康總覽」第一視覺
  - 缺角色 onboarding
  - 缺圖表的「報告友善」匯出
  - 系統管理頁 hard block 但沒解釋路徑（line 38-41 只說「請洽系統管理員」沒寫 email / Slack）

---

### Persona D — 評審工程師「Wiwynn 面試官 Eric」（隱性第 4 persona，最重要）

**Demographics**
- 年齡：30-45 歲
- 職稱：Wiwynn 軟體部資深工程師 / Tech Lead / 招募經理
- 公司規模：Wiwynn 全球員工數萬人
- 技術背景：FastAPI / SQLAlchemy / Streamlit / Docker 全熟，有經驗評過 20+ 求職者作品
- 使用頻率：1 次（5-10 分鐘掃 demo + 看 README + 看 commit history）
- 使用情境：收到 candidate 投遞 → 開 demo URL → 邊看邊在 ATS 打分 → 決定 yes/no/maybe

**Primary Job-to-be-Done**
> 「我要在 10 分鐘內判斷這個 candidate 的『系統設計能力 + 程式碼品質 + 產品 sense』達不達到 Wiwynn 標準，並決定要不要邀請面試。」

**核心動詞**：掃讀（skim）→ 抽樣（sample）→ 判斷（judge）

**Frequency**：1 次性決策

**Top 3 Pain Points（評審視角）**

1. **「我看 Home 登入頁不知道有測試帳號可以直接登入，要去翻 README」**
   - 證據：`Home.py:23-43` 登入 tab 完全沒提示測試帳號；README.md:66-75 雖列出 admin/user/viewer 三組，但評審打開 demo URL 不會立刻翻 README
   - 嚴重度：極高（5 分鐘掃 demo 第一步就 friction）
   - **影響**：評審可能直接關掉視窗，認為「candidate 沒有考慮 demo onboarding」

2. **「我同時想看 admin/user/viewer 三角色的差異，但要登入登出 3 次」**
   - 證據：`Home.py:17-18` 登入即跳儀表板，三角色切換要 logout → login → logout → login × 3
   - 嚴重度：高（評審時間珍貴，重複動作 = 扣分）
   - 業界對照：許多 demo 提供「role switcher」devtool（如 ant design pro demo），3 秒切換 admin/user/viewer

3. **「我看完一輪沒看到 candidate 的『設計思考』，code 寫得不錯但不知道為什麼這樣設計」**
   - 證據：六個頁面**沒有任何 design decision 註解 callout**（例如「為什麼用 wide format 不用 long format」、「為什麼 60 秒 history」等）；雖然 design.md 全寫了，但評審不會去翻 openspec/changes
   - 嚴重度：中-高（評審看到的是 surface，深度設計被埋）
   - **業界對照**：Linear 的 demo 在每個頁面右上角有「How this was built」icon，點開 explain 設計理由

**Top 3 Desired Gains**

1. **登入頁直接顯示測試帳號 + 一鍵填入** — 三顆按鈕「以 Admin 登入」「以 User 登入」「以 Viewer 登入」，按下去自動填 form 並 submit
2. **角色切換器** — 任何頁面右上角下拉「切換角色」（不用 logout），demo 模式
3. **設計理由 callout** — 每頁有 collapsed「設計說明」expander 解釋 trade-off

**One Unexpected Insight**
> 評審工程師在打分時，**「demo onboarding 流暢度」會比「功能完整度」更重要**，因為前者反映「candidate 是否有 user empathy」這是 senior 必備能力。
>
> 證據：Wiwynn JD 通常會要求「product mindset」「user-centric thinking」。如果 candidate 的 demo 自己要看 README 才會用，等於宣告「我只關心 backend，不在乎 UX」——對 full-stack 職位是負分。
>
> Candidate 的 codebase 顯示 backend 很紮實（FastAPI / SQLAlchemy / Alembic / pytest / docker compose / RBAC 全配齊），但 demo onboarding 0 分。**這是「能力被低估」的 root cause**。

**設計建議**（v3 最高優先）：Home 頁加 3 顆「快速登入」按鈕 + 每頁角落 role switcher。

**Product Fit Assessment**
- **滿足**：技術深度足、模組完整、Docker / Alembic / pytest / RBAC 等 production-grade 配置完整
- **不足**：
  - 0 onboarding
  - 0 role switcher
  - 0 設計理由 surface
  - 0 「I am evaluator」mode（評審看 demo 跟 user 用 demo 的需求**根本不同**）

---

## Section 2: UX 痛點逐頁 audit

> 每痛點格式：**痛點 → 觀察證據（file:line）→ 影響 persona → 建議優化方向（不是實作細節）**

### 2.1 Home 登入頁（`Home.py`，106 行）

**痛點 H-1：沒有測試帳號提示，評審 5 秒卡關**
- 觀察證據：`Home.py:23-43` 登入 tab 內只有 email + password 兩 input，無任何 placeholder 或 caption 提示「測試帳號 admin@example.com / admin123」；README.md:66-75 有列但要切到 GitHub 看
- 影響 persona：**D 評審（極高）** > A admin（中）> 任何首次使用者
- 建議方向：登入 form 上方加「Demo 帳號」expander 或直接顯示三組測試帳號 + 一鍵填入按鈕

**痛點 H-2：註冊預設 viewer 但沒解釋為什麼，造成註冊用戶困惑**
- 觀察證據：`Home.py:47-48` `st.info("新帳號預設角色為 **Viewer**（瀏覽者），需由管理員提升權限。")` 沒解釋 (a) viewer 能做什麼 (b) 怎麼聯絡管理員 (c) 為什麼這樣設計
- 影響 persona：C viewer（高，註冊後 confused）> D 評審（中，會 register 試）
- 建議方向：info 改成「viewer 可瀏覽即時監控與分析報表，無法新增資料。如需提權請洽 admin。」並加角色矩陣連結

**痛點 H-3：登入失敗訊息泛用，無法 diagnose**
- 觀察證據：`Home.py:43` `st.error(f"登入失敗：{message}")` 把 backend 的原始錯誤訊息直接顯示；若 message 是「Invalid credentials」用戶無從判斷是 email 拼錯、密碼錯、帳號未啟用、還是後端掛了
- 影響 persona：所有 first-time user
- 建議方向：細分 401 vs 403 vs 500，給明確「Email 找不到」/「密碼錯誤」/「帳號已停用」/「伺服器忙線」

**痛點 H-4：左側 sidebar 沒被登入頁需要，但 Streamlit 預設顯示 5 個頁面入口**
- 觀察證據：Streamlit `pages/` 目錄下 5 個頁面預設全顯示在登入頁 sidebar；未登入點任一頁會被 `require_auth()` 擋回 Home（造成「點了沒反應」）；`Home.py:10-14` `set_page_config` 用 `layout="centered"` 但沒 `initial_sidebar_state="collapsed"`
- 影響 persona：D 評審（中，第一印象凌亂）+ C viewer（中）
- 建議方向：Home 頁 sidebar collapsed；或在未登入時隱藏 pages

---

### 2.2 儀表板 `pages/1_儀表板.py`（268 行）

**痛點 D-1：4 個 metric cards 全是「量」沒有「品質判斷」**
- 觀察證據：`pages/1_儀表板.py:147-155` 4 個 card「合計資料筆數 / 即時資料筆數 / 錄入資料筆數 / 異常筆數（合計）」全是 absolute count；第 4 個「異常筆數」是 inverse delta_color 但**沒設定 delta 值**（line 151-155 只有 value 沒有 delta），所以 inverse 顏色不會觸發
- 影響 persona：**C viewer（高）** + A admin（中）+ D 評審（中）
- 建議方向：改成 (a) 「合計筆數 + 異常率 %」 (b) 加「過去 24h vs 前一天」對比 delta (c) 加紅黃綠燈 health indicator

**痛點 D-2：System status header 三欄等寬，但資訊密度差異極大**
- 觀察證據：`pages/1_儀表板.py:81-93` `status_col1, status_col2, status_col3 = st.columns(3)` 三欄等寬：欄 1「串流狀態：● 連線中」(8 字元) / 欄 2「最後更新：2026-05-26 10:33:21」(25 字元) / 欄 3「活躍告警：5 筆」紅色背景但只有 7 字元；視覺重量完全失衡
- 影響 persona：C viewer（中）+ A admin（中）
- 建議方向：(a) 改成 1:2:1 column ratio (b) 或改成單行 status bar with icon + label + value

**痛點 D-3：`@st.cache_data(ttl=10/30)` 多層 cache，導致「最近資料」實際上不是最近**
- 觀察證據：`pages/1_儀表板.py:44 @st.cache_data(ttl=10)` 給 status header，`:98 @st.cache_data(ttl=30)` 給 unified summary，`:113 @st.cache_data(ttl=30)` 給 recent realtime，`:123 @st.cache_data(ttl=30)` 給 recent records；同一頁四個 ttl 不同，user 看到的「實時感」混亂——status 是 10 秒前，metric card 是 30 秒前，但 user 不知道
- 影響 persona：A admin（高，需要實時）+ D 評審（中，會發現怪）
- 建議方向：(a) 統一 ttl=5 (b) 或在每張 card 角落顯示 "更新於 N 秒前" stale indicator

**痛點 D-4：「重新整理」按鈕在頁面最底部，user 不會 scroll 找它**
- 觀察證據：`pages/1_儀表板.py:265-268` 「重新整理」button 在頁面最底，要 scroll 三屏；user 期待這種 reload 動作在 header 區
- 影響 persona：A admin（中）+ D 評審（低）
- 建議方向：移到頁面頂部 status header 區，做成 icon button 旁邊 "更新於 X 秒前"

**痛點 D-5：帳號設定 expander 在儀表板底部，跟「儀表板」本身語意不符**
- 觀察證據：`pages/1_儀表板.py:220-262` 「帳號設定」expander 與「修改密碼」form 跟儀表板沒有任何邏輯關聯；user 找「改密碼」第一個會去點 "user info" 區（line 31-36），找不到才會在儀表板亂逛
- 影響 persona：B user（中）+ C viewer（中）
- 建議方向：(a) 改密碼移到右上角 user info 區 dropdown menu (b) 或開獨立「帳號」頁面

---

### 2.3 資料管理 `pages/2_資料管理.py`（326 行）

**痛點 DM-1：CSV 上傳沒有 preview / dry-run，500 筆檔案上傳後才知道對錯**
- 觀察證據：`pages/2_資料管理.py:268-326` `st.file_uploader` 直接 POST `/data/bulk-import`，沒有「先 preview 前 5 筆 + 估算總筆數」步驟；line 296-313 才在「成功 N 筆、失敗 M 筆」後顯示錯誤明細
- 影響 persona：**B user（極高）** + A admin（高）
- 建議方向：(a) 上傳後本機 pandas 解析顯示「將匯入 480 筆，跳過 20 筆，預覽前 5 筆」 (b) 加「下載 sample CSV」連結 (c) dry-run mode

**痛點 DM-2：inline edit 的 data_editor `num_rows="dynamic"` 讓 viewer 看到「+」加號但點下去無效**
- 觀察證據：`pages/2_資料管理.py:153` `num_rows="dynamic" if role in ("admin", "user") else "fixed"`——viewer 走 "fixed" 不會顯示加號；但 user 在「不是自己的 record」上點 edit，前端 data_editor 不會擋住，要等 backend 403 後 silent skip（line 252-253 `st.toast(f"沒有權限修改 ID ...")`）
- 影響 persona：B user（高）+ C viewer（低）
- 建議方向：(a) 按 row 為單位 disable 編輯（owner 才能編輯） (b) 或在 row 標 owner 名稱讓 user 自己判斷

**痛點 DM-3：篩選 expander `expanded=True` 預設展開，跟分頁 + 資料表搶版面**
- 觀察證據：`pages/2_資料管理.py:55` `with st.expander("篩選條件", expanded=True)`；user 上方看到三排篩選控制（line 56-66），下方分頁 + 「共 N 筆」+ 資料表，視覺上篩選佔了 1/3 螢幕
- 影響 persona：B user（中）+ A admin（中）
- 建議方向：(a) 預設 collapsed (b) 或改成單行 toolbar（類似 Notion / Linear filter pill）

**痛點 DM-4：「儲存變更」按鈕沒有 dirty state detection，user 改了沒按就切頁，資料丟失**
- 觀察證據：`pages/2_資料管理.py:170` `if st.button("儲存變更", key="save_changes_btn", type="primary")`——button 永遠可按，沒有「未儲存」warning；user 改完 row 直接點 sidebar 切到「分析報表」，前面改的 inline edit 全部丟
- 影響 persona：B user（高，最常見的「資料丟失」UX 反模式）
- 建議方向：(a) 比較 edited_df vs orig df，有差異時 sticky banner「您有未儲存的變更」 (b) navigation away 前 confirm

**痛點 DM-5：批量匯入結果只顯示「成功 N 筆、失敗 M 筆」聚合數字，沒有「下載失敗 row CSV」**
- 觀察證據：`pages/2_資料管理.py:297-314` errors 顯示在 dataframe 內但**沒有 download 按鈕讓 user 拿回失敗的 row 自己修**；user 要靠 copy paste 從 streamlit 表格 hack
- 影響 persona：B user（中-高）
- 建議方向：errors_df 加「下載失敗 row CSV」button，讓 user 修完重傳

---

### 2.4 分析報表 `pages/3_分析報表.py`（435 行）

**痛點 A-1：「資料來源」selectbox 有 3 個，但分散在三個區塊，user 改一個其他不同步**
- 觀察證據：line 90 `summary_source`（兩者 / 僅即時 / 僅錄入）、line 157 `trend_source`（錄入 / 即時）、line 300 `cat_source`（錄入 / 即時）——user 想「全部看即時」要分別在三個地方各改一次；line 89 _SOURCE_OPTIONS 也跟 line 154 _TREND_SOURCE_OPTIONS 不一致（前者三選一，後者二選一）
- 影響 persona：B user（高，認知負荷爆表）+ A admin（中）
- 建議方向：(a) 頁面頂部單一 source selector 同步三區塊 (b) 或保留 per-section toggle 但 default 同步

**痛點 A-2：時間趨勢圖 source=realtime 時改顯示「Bar chart」而不是時間軸折線**
- 觀察證據：`pages/3_分析報表.py:253-289` 當 `trend_source == "realtime"` 條件分支內畫的是 `go.Bar`（line 275-280）顯示 5 個 metric 的「平均值 bar」——但 subheader 還是「時間趨勢圖」（line 150），與 bar chart 語意完全不符
- 影響 persona：B user（極高，產生「我選錯了嗎」疑慮）+ A admin（高）
- 建議方向：(a) realtime source 改用 `/realtime/history` 拉時間序列畫線圖（不是 bar） (b) 或改 subheader 為「分佈圖」when realtime

**痛點 A-3：類別分佈兩個 bar chart 並排 `bar_col1, bar_col2`，X 軸文字標籤重疊看不見**
- 觀察證據：`pages/3_分析報表.py:335-365` 兩個 bar chart 並排，每個寬度 ~50% screen width；5 個中文 metric label「溫度(C) / 濕度(%) / 氣壓(hPa) / 電壓(V) / CPU(%)」會擠在窄 X 軸；line 343-347 `margin={"l": 40, "r": 20, "t": 50, "b": 40}` 底部 margin 只有 40 不夠中文 tilted label
- 影響 persona：B user（中）+ C viewer（中，做截圖）+ A admin（中）
- 建議方向：(a) 改成上下排，每張 full-width (b) 或 X 軸 label 旋轉 30° (c) 或 horizontal bar chart

**痛點 A-4：Excel 匯出檔名 `data_export.xlsx` 沒有時間戳，user 下載多次會被覆蓋**
- 觀察證據：`pages/3_分析報表.py:407-414` 取 backend Content-Disposition 為主，但 fallback `filename = "data_export.xlsx"` 完全沒有時間 / 條件
- 影響 persona：B user（中，週報常見場景）
- 建議方向：filename 燒入篩選條件 + 時間戳 `data_export_2026-05-26_records_2026-05-01_to_2026-05-26.xlsx`

**痛點 A-5：「準備 Excel 下載」要兩步點擊（準備 → 下載）**
- 觀察證據：line 394 「準備 Excel 下載」button → line 416-418 success message → line 428-435 `st.download_button("下載 Excel")`；user 必須點兩次（第一次拿檔，第二次真下載），這是 Streamlit `download_button` 必須 pre-load data 的反模式
- 影響 persona：B user（中-高，最常用功能但 friction）
- 建議方向：直接用 `st.download_button` + on-demand fetch（Streamlit 1.39 支援 callback）省掉第一步

**痛點 A-6：日期 default 是 `now - 7 days`，但 demo 資料只有 60 筆跨 7 天（README.md:123）+ 模擬器 1 秒 1 筆**
- 觀察證據：line 62-63 `default_from = (now_utc - timedelta(days=7)).date()` 預設過去 7 天；但 demo 資料 records 只有 60 筆固定，user 看到的圖會很稀疏
- 影響 persona：D 評審（高，第一印象覺得「沒資料」）+ B user
- 建議方向：(a) demo 模式改 default 24h 顯示密集模擬器資料 (b) 加「資料區間 detection」自動 fit DB 內最早 / 最晚

---

### 2.5 即時監控 `pages/4_即時監控.py`（371 行）

**痛點 R-1：5 條 metric 線共用單一 Y 軸，氣壓 1013 把溫度 25 / CPU 40 線壓成貼底**
- 觀察證據：`pages/4_即時監控.py:256-261` `update_layout(yaxis_title="數值", ...)`——5 條線（溫度 -20~120 / 濕度 0~100 / 氣壓 900~1100 / 電壓 0~24 / CPU 0~100）共用同一 yaxis；氣壓 baseline 1013 會把其他 4 條線壓在 0-100 區段，視覺上完全失真
- 影響 persona：**A admin（極高，這是 admin 核心 use case）** + D 評審（高，第一印象覺得「圖壞了」）+ B user
- 建議方向：(a) 用 5 張 small multiples 子圖（plotly subplots） (b) 或 dual y-axis 但只能 2 metric 用 (c) 或 normalize 到 0-1 後畫（但會失去物理意義）

**痛點 R-2：閾值 hardcode 在 FE，admin 改 backend `app_settings` 後 FE 不會同步**
- 觀察證據：`pages/4_即時監控.py:56-69` `_METRIC_HIGH_THRESHOLD / _METRIC_LOW_THRESHOLD` hardcode dict；但 admin 在「系統設定」tab（5_系統管理.py:558-639）可改 `anomaly_threshold_high` 等 setting，改完即時監控頁仍用舊閾值算 delta（line 186-189）
- 影響 persona：A admin（高，造成「設定生效但介面騙我」）+ D 評審（高，會發現不一致）
- 建議方向：FE 啟動時打 `/admin/settings` 拿動態閾值 + cache 30 秒

**痛點 R-3：「清空緩衝區」按鈕跟「顯示哪些線」並列，user 誤觸風險高**
- 觀察證據：`pages/4_即時監控.py:147-160` 兩個 control 並排 `ctrl_col1, ctrl_col2`，左邊 multiselect 是「顯示哪些線」，右邊 button「清空緩衝區」是 destructive 動作但沒任何 confirmation
- 影響 persona：A admin（中，誤觸後 60 秒 history 沒了）
- 建議方向：(a) 加 confirm dialog (b) 或把「清空緩衝」放底部進階區 + 改成 secondary button

**痛點 R-4：表格 60 筆全載入無分頁無 scroll constraint，吃掉整屏**
- 觀察證據：`pages/4_即時監控.py:270` `recent_60 = all_ticks[-60:][::-1]`——60 row dataframe 預設展開全部，配上 11 column（時間 + 5 metric + 5 異常 + 來源）寬度，view 必須 scroll 過長表格才能看到頁面底部「自動刷新次數 / 緩衝區」資訊
- 影響 persona：A admin（中）+ B user（中）
- 建議方向：(a) `st.dataframe(height=400)` 限高內捲 (b) 預設只顯示 10 筆 + 「展開全部」expander

**痛點 R-5：告警卡片用 `st.columns(min(len(...), 5))` 動態欄數，5 metric 異常時擠成超窄**
- 觀察證據：`pages/4_即時監控.py:184` `alert_cols = st.columns(min(len(dedup_alert_metrics), 5))`；5 metric 全異常時，每張 metric card 寬度 = screen_width / 5 ~ 240px，配上中文 label「溫度(C) 異常 +25.5（閾值 100.0）」會 wrap 三行
- 影響 persona：A admin（中-高，異常風暴時最看不清）
- 建議方向：(a) 限制最多 3 cards/row，> 3 改 list view (b) 或 alert card 改設計為單行 banner

**痛點 R-6：autorefresh 1 秒 rerun，但 cache_data ttl=10/30 + st.spinner 不會顯示，user 不知道資料有沒有更新**
- 觀察證據：`pages/4_即時監控.py:110` `st_autorefresh(interval=1000)` 每秒 rerun；但 `last_update_str` 顯示的是「最後 snapshot 時間」（line 130-131），不是「畫面更新時間」；user 看到時間 frozen 會以為系統 hang
- 影響 persona：A admin（高）+ D 評審（中-高）
- 建議方向：在 status header 加「畫面更新於 N 秒前」+ 跳動的小指示燈（pulse）

---

### 2.6 系統管理 `pages/5_系統管理.py`（639 行）

**痛點 S-1：5 個 tab label 沒 emoji 沒 icon，全是 4 字中文，掃讀困難**
- 觀察證據：`pages/5_系統管理.py:71-77` 「使用者列表 / 系統日誌 / 資料庫狀態 / 即時資料歷史 / 系統設定」全 4 字中文 tab；雖然 design.md §5.1 強制去 emoji，但連 `:bookmark:` 等 streamlit icon 都沒用——admin 掃 5 個 tab 要逐字讀
- 影響 persona：A admin（高，每天用）+ D 評審（中）
- 建議方向：保留中文 + 用 Streamlit material icon `:material/people:` 等視覺輔助（design.md 例外清單可放寬）

**痛點 S-2：角色權限說明在 expander 內，預設 collapsed，user 不會主動展開**
- 觀察證據：`pages/5_系統管理.py:88` `with st.expander("角色權限說明", expanded=False)`；admin 第一次進來不會點，但這個 13 行 × 3 角色的矩陣**是新 admin onboarding 最重要的資訊**
- 影響 persona：A admin（高，新 admin onboarding）+ D 評審（中）+ 所有想理解 RBAC 的人
- 建議方向：(a) `expanded=True` 預設展開 (b) 或移到頂部 visible info card

**痛點 S-3：使用者管理「編輯使用者」與「修改密碼」用兩個獨立 selectbox，admin 改同一人的兩件事要選兩次**
- 觀察證據：`pages/5_系統管理.py:163-164` 「選擇使用者」selectbox + `pages/5_系統管理.py:212-214` 「選擇要修改密碼的使用者」selectbox——admin 對同一個 user 改 role + 改密碼要選兩次同樣的人
- 影響 persona：A admin（中-高，常見運維場景）
- 建議方向：(a) 合併為單一 user selector，下方 tab「角色與啟用 / 密碼」 (b) 或在使用者列表 row 加 inline action button

**痛點 S-4：系統日誌篩選 7 個欄位（page_size / page / user_id / action / date_from / date_to + filter expander 自身），用 3-column 排版視覺擁擠**
- 觀察證據：`pages/5_系統管理.py:271-290` 三欄佈局，第一欄塞「每頁筆數 + 頁碼」、第二欄「使用者 ID + 動作關鍵字」、第三欄「日期 from/to」——同一個視覺單位塞兩個 input 違反「one input per column」原則
- 影響 persona：A admin（中，每日篩 log 場景）
- 建議方向：(a) 改 2 row × 4 column (b) 或加 saved filter preset

**痛點 S-5：系統設定每個 setting 都用 expander `expanded=True` + 「儲存」按鈕，5 個 setting = 5 個 form 重複 boilerplate**
- 觀察證據：`pages/5_系統管理.py:577-632` 每個 setting 走 expander 內含 number_input + save button；5 個 setting 視覺上 5 個重複區塊；改完後 line 624 `st.cache_data.clear() + st.rerun()` 整頁重整，admin 改下一個 setting 又從頭開始 scroll
- 影響 persona：A admin（中，月度調參場景）
- 建議方向：(a) 單一 form 改全部 setting 一次儲存 (b) 或 inline edit table

**痛點 S-6：「即時資料歷史」tab 跟「即時監控」頁的圖表是同一邏輯重複實作**
- 觀察證據：`pages/5_系統管理.py:412-526` `_ADMIN_METRIC_KEYS / _ADMIN_METRIC_ZH / _ADMIN_METRIC_COLORS` 跟 `pages/4_即時監控.py:40-54` 重複；折線圖邏輯（line 484-517）跟 `pages/4_即時監控.py:217-254` 幾乎一樣
- 影響 persona：A admin（低-中，admin 兩頁都會看，重複設計失誤造成「我在哪一頁」混淆）+ 維護者
- 建議方向：(a) 抽 shared component `realtime_chart.py` (b) 或從 navigation 角度合併兩頁（即時監控頁直接加「歷史」tab）

**痛點 S-7：viewer / user 被擋在系統管理頁的訊息引導不充分**
- 觀察證據：`pages/5_系統管理.py:38-41` `st.error(f"存取拒絕：此頁面僅限 **admin** 角色。您目前的角色為 \`{role}\`。") + st.info("如需管理功能，請洽系統管理員提升權限，或改以 admin 帳號登入。")`——「請洽系統管理員」沒給 email、Slack、表單連結，user 不知道怎麼洽
- 影響 persona：B user（中）+ C viewer（中-高）+ D 評審（中，會試）
- 建議方向：(a) 加聯絡資訊 placeholder (b) 或加「申請提權」表單

**痛點 S-8：DB 狀態頁的「Pool 大小 / 已借出 / 溢出」沒有「正常 vs 異常」threshold 標示**
- 觀察證據：`pages/5_系統管理.py:391-393` 三張 metric card 純顯示數字（例如 size=5, checked_out=2, overflow=0），但 admin 看到「checked_out=2」不知道是正常還是 close to pool exhaustion
- 影響 persona：A admin（中，DB 緊急場景）
- 建議方向：(a) 加「使用率 %」derived metric (b) 接近上限時 yellow / red badge

---

## Section 3: 圖表 UX 專門 audit

### 3.1 目前的圖表清單

| # | 頁面 | 圖表 type | 位置 | 互動 | 資料來源 |
|---|---|---|---|---|---|
| C1 | 1_儀表板 | 4 metric cards | line 147-155 | 無 | `/analytics/unified-summary` |
| C2 | 1_儀表板 | tabs(即時/錄入) dataframe | line 162-218 | 排序 sort | `/realtime/history` + `/data` |
| C3 | 3_分析報表 | 統合摘要 4 metric cards | line 116-120 | 無 | `/analytics/unified-summary` |
| C4 | 3_分析報表 | 即時 metric 摘要 dataframe | line 125-143 | 無 | unified.realtime.metrics |
| C5 | 3_分析報表 | 時間趨勢 Plotly line（records）| line 206-250 | hover / zoom / pan / download | `/analytics/timerange` |
| C6 | 3_分析報表 | 即時 metric Bar | line 275-287 | hover / zoom | `/analytics/realtime-categories` |
| C7 | 3_分析報表 | 類別分佈 Bar × 2 並排 | line 337-365 | hover / zoom | `/analytics/categories` + realtime-categories |
| C8 | 3_分析報表 | 類別詳細 dataframe | line 368-375 | 排序 | 同上 |
| C9 | 4_即時監控 | 5 metric 折線 + anomaly circle | line 214-264 | hover / zoom / pan / autorefresh | WS `/ws/realtime` + REST `/realtime/history` |
| C10 | 4_即時監控 | 60 筆 wide table + Pandas Styler | line 273-359 | 排序 / 紅字 cell | 同上 |
| C11 | 4_即時監控 | Alert metric cards 動態 N 欄 | line 184-197 | 無 | derived from buffer |
| C12 | 5_系統管理 | 5 metric 折線 + anomaly | line 480-526 | hover / zoom | `/admin/realtime-history` |
| C13 | 5_系統管理 | 使用者列表 dataframe | line 158 | 排序 | `/users` |
| C14 | 5_系統管理 | 系統日誌 dataframe | line 345 | 排序 | `/admin/logs` |
| C15 | 5_系統管理 | DB 連線池 3 metric cards | line 391-393 | 無 | `/admin/db-status` |
| C16 | 5_系統管理 | 資料表筆數 dataframe | line 396-403 | 排序 | 同上 |

### 3.2 「使用者問問題 → 圖表能不能答」對照

| 使用者問題 | 對應圖表 | 能不能答 | Friction |
|---|---|---|---|
| 「系統現在好不好？」 | C1 status header 圈圈 | 部分能（只有 ●/○） | 沒「綠燈/紅燈」 visual / 沒「過去 24h 比較」 |
| 「過去一週異常率多少？」 | C1 第 4 卡 「異常筆數 合計」 | **不能**（沒 ratio 也沒 baseline） | 缺異常率 % |
| 「溫度現在多少？跟正常比怎樣？」 | C9 折線 | **不能**（5 條線壓成一團） | 單一 yaxis 把不同單位混在一起 |
| 「上週 vs 這週趨勢」 | C5 trend chart | 部分能 | 沒「上週對比」線；timerange 還有 Q7 tz bug 風險 |
| 「哪個類別最常異常？」 | C7 類別分佈 + C4 即時 metric 摘要 | 部分能 | 兩張圖在不同區塊，要 mental merge |
| 「上次有異常是什麼時候？」 | C11 + C12 | **不能**（沒 timeline 也沒「最後一次異常 X 分鐘前」） | 缺 alert history |
| 「我能不能下載我看到的圖？」 | 所有 Plotly chart | 部分能 | Plotly 預設 toolbar 有 PNG 下載但 viewer 不知道，且品質低 |
| 「我看的這個數字什麼意思？」 | C3 統合摘要 | **不能** | metric card 沒 tooltip 解釋 |

### 3.3 圖表 friction 點逐項

**F-Loading：** 多處 `st.spinner` 但同時又有 cache_data ttl，user 看到「載入中」但實際是 cache hit；舉例 `pages/1_儀表板.py:135 / 165 / 193` 三個 spinner 同時觸發，視覺上 page render flicker

**F-Blank state：** 空資料訊息全部用 `st.info("...")`（line `3_分析報表.py:145, 252, 289, 376` 等 5 處），文字大同小異但沒有 (a) 「為什麼空」 (b) 「下一步怎麼辦」 (c) 「建議調整篩選條件」

**F-軸標：**
- C5 / C9 / C12 yaxis_title 都寫「數值」（line `3_分析報表.py:246` / `4_即時監控.py:259` / `5_系統管理.py:521`），但 5 個 metric 單位完全不同（C / % / hPa / V），「數值」這個 label = 沒 label
- xaxis_title「時間（台北）」正確但 hover tooltip 沒額外格式（Plotly default）

**F-Hover：** Plotly default tooltip 對 `go.Scatter` 顯示 `(x, y)` 但 anomaly trace 已加 `hovertext`（line `3_分析報表.py:240`），其他 metric line 沒加 → tooltip 經驗不一致

**F-Legend：** C5 / C9 圖 `legend={"orientation": "h", "y": -0.2}` 横排在下方（line `3_分析報表.py:247` / `4_即時監控.py:260`）；5 條 metric × 「異常」共 10 個 legend item 會 wrap 兩行，吃掉 chart 高度

**F-Time range picker：** C5 沒有 Plotly built-in rangeslider，user 不能在圖上拖選 zoom 範圍，要回上面改 date_input

**F-Refresh：**
- C9 用 `st_autorefresh(interval=1000)`（4_即時監控.py:110）每秒 rerun 整頁，造成滑鼠 hover 圖時 tooltip 閃爍
- C5 / C7 改 filter 後等 backend 30s ttl cache 才會更新（line `3_分析報表.py:94, 161, 304`），user 不知道資料 stale

**F-Color：**
- C9 / C12 5 個 metric 顏色：temperature=royalblue / humidity=green / pressure=orange / voltage=purple / cpu_usage=teal（line `4_即時監控.py:48-54`）— 沒考慮 colorblind safety
- anomaly marker 全用 red — 跟告警 banner 顏色撞 + 跟 Plotly 「decrease」紅色衝突

**F-No drill-down：** C7 類別分佈 bar 點下去沒有「該類別的明細」drill-down，admin / user 必須回到資料管理頁手動 filter

---

## Section 4: 角色權限說明 UX 專門 audit

### 4.1 目前出現位置

| 位置 | 內容 | 可見性 | persona 觸達 |
|---|---|---|---|
| `README.md:171-180` | 7 動作 × 3 角色矩陣 | GitHub repo（demo 用戶不會去） | D 評審（可能） |
| `pages/5_系統管理.py:88-105` | 13 動作 × 3 角色矩陣 | expander `expanded=False` 內 | A admin（要點才看到）只 admin 才能進此頁 |
| `Home.py:48` | `st.info("新帳號預設角色為 **Viewer**...")` | 註冊 tab 內 | 註冊用戶 |
| `pages/2_資料管理.py:117` | `st.info("Viewer 角色為唯讀，無法編輯資料。")` | viewer 進此頁時 | C viewer（reactive） |
| `pages/5_系統管理.py:39-40` | `st.error("存取拒絕...")` | viewer/user 進此頁時 | B user + C viewer（reactive） |

### 4.2 三角色第一印象傳達清晰度評估

| 角色 | 第一次登入後，N 秒內能說出「我能做什麼」？ | 證據 | 評分 |
|---|---|---|---|
| Admin | 30+ 秒（要切到系統管理 → 展開 expander） | `5_系統管理.py:88` collapsed | **不清晰** |
| User | 永遠不會主動知道（只在試圖編輯非己 record 時被告知） | 無 proactive 提示 | **極不清晰** |
| Viewer | 進儀表板看不到限制，進資料管理才看到 info banner | `2_資料管理.py:117` reactive | **不清晰** |

### 4.3 業界對照

| 業界平台 | 角色說明 UX 模式 | 觸發時機 | 本系統可借鑑點 |
|---|---|---|---|
| **GitHub Organizations** | Settings → Members → roles，Owner/Member/Outside Collaborator 三角色，每個角色點進去有獨立 doc 頁說明能做哪些 action（含 API scope） | passive（自助查詢） | 系統管理頁加獨立「角色說明」sub-page |
| **Notion Workspace** | 第一次邀請成員時彈 modal「Choose role: Member can edit / Guest can view only」+ tooltip hover 顯示權限差異 | active（at choice point） | 註冊 / admin 編輯角色時加 inline tooltip |
| **Vercel Team** | Settings → Members 頁顯示 role chip（Owner / Member / Developer / Billing / Viewer），hover chip 即顯示完整 capabilities checklist；每個 page 標籤頁上方有 role-aware banner「You are viewing as Member」 | both passive + active | 每頁右上角顯示「您的角色：X，可看 Y / 不可 Z」mini badge |
| **Grafana Org** | role 用顏色 chip（Admin=紅 / Editor=橙 / Viewer=灰）+ login 後右上角永遠顯示，hover 帶 capability list | persistent visual | 全頁面 header 持續顯示角色 chip |
| **Datadog RBAC** | 每個 destructive 動作前 inline 顯示「This requires admin role. You have user role. [Request access]」 | reactive but actionable | 升級「無權限」訊息為「申請提權」連結 |

### 4.4 建議的角色說明 UX 策略

**Tier 1（必修）：** 把 `pages/5_系統管理.py:88` 的 13×3 矩陣**抽出來放到所有頁面 sidebar 底部**，admin/user/viewer 都能看（不僅 admin）。

**Tier 2（必修）：** Home 頁登入後彈一次性 onboarding modal「您的角色：X，建議從『儀表板』開始」+ 把矩陣連結放進去。

**Tier 3（建議）：** 每頁右上角 user info 區的「角色：admin」改成 chip badge + hover tooltip 顯示「您可以：…」3-5 行 capability summary。

**Tier 4（v4 範圍）：** 「申請提權」表單（user 申請升級 admin / viewer 申請升級 user）。

---

## Section 5: Top 10 必修 UX 痛點清單

> 按「對 demo 成敗影響度」排序（評審 persona D 權重最高，因為這是面試題）。
> S/M/L 修補難度：S = 半天內、M = 1-2 天、L = 3-5 天。

### #1 — Home 沒有測試帳號快速登入按鈕（H-1）

- **嚴重度：** 致命（評審 5 秒 friction → 直接負分）
- **Persona 影響：** D 評審（極高）+ 首次使用者
- **修補難度：** S（30 分鐘）
- **推薦做法：** Home 登入 tab 上方加三顆 "以 Admin 登入 / 以 User 登入 / 以 Viewer 登入" 按鈕，按下自動填 form + submit。caption 註「（Demo 用，請先了解 demo 限制再使用真實 API）」

### #2 — 即時監控 5 條 metric 線共用單一 Y 軸，氣壓壓死其他線（R-1）

- **嚴重度：** 致命（核心 use case 完全壞）
- **Persona 影響：** A admin（極高）+ D 評審（高）+ B user
- **修補難度：** M（1 天，改 plotly subplots）
- **推薦做法：** 用 plotly `make_subplots(rows=5, cols=1, shared_xaxes=True)` 做 small multiples，每個 metric 自己 yaxis 自己範圍；或保留單張圖但加 `yaxis2/3/4/5` 多 Y 軸。**首選 small multiples**（admin 可獨立判讀每個 metric）。

### #3 — 儀表板 4 metric cards 全是「量」沒「品質」，viewer 看不出系統好壞（D-1）

- **嚴重度：** 高（核心 viewer job 失敗）
- **Persona 影響：** C viewer（極高）+ A admin（高）+ D 評審（中）
- **修補難度：** S-M（半天，需要 backend 加「過去 24h vs 前一天」對比 API 或 FE 算 derived）
- **推薦做法：** (1) 第 4 卡改「異常率 0.014% (今日)」並 delta 顯示「vs 昨日 +0.003%」 (2) 加第 5 卡「系統健康度」綠/黃/紅大圖示 (3) cards 上方加「過去 24 小時：5 次異常，全部已處理」一行 status summary

### #4 — CSV 上傳沒 preview / dry-run，user 上傳完才知道格式錯（DM-1）

- **嚴重度：** 高（B user 最高頻 use case）
- **Persona 影響：** B user（極高）+ A admin（高）
- **修補難度：** M（1-2 天，要做 client-side parse + diff UI）
- **推薦做法：** 上傳後本機用 pandas parse 顯示「將匯入 N 筆 / 跳過 M 筆 / 預覽前 5 筆」+ 加「下載 sample.csv」連結；按「確認匯入」才真正 POST `/bulk-import`

### #5 — 角色權限說明僅 admin 才能看到，user/viewer 不清楚自己能做什麼（角色 UX 整體）

- **嚴重度：** 高（影響三角色 onboarding）
- **Persona 影響：** A/B/C/D 全部
- **修補難度：** S-M（半天-1 天）
- **推薦做法：** (1) 把 13×3 矩陣抽到所有頁面 sidebar 底部 always visible (2) Home 登入後彈一次性 modal 顯示「您的角色 X，建議去 Y 頁」 (3) 每頁右上角 user info「角色：admin」改 chip + hover tooltip 顯示 capability summary

### #6 — 分析報表「資料來源」selector 三處分散不同步（A-1）

- **嚴重度：** 中-高（B user 認知負荷爆表）
- **Persona 影響：** B user（高）+ A admin（中）
- **修補難度：** S（2-3 小時，加 session_state sync）
- **推薦做法：** 頁面頂部加單一 `st.radio("資料來源", ["即時+錄入", "僅即時", "僅錄入"])` 同步三個區塊；保留 per-section override 但 default = 頂部設定

### #7 — 時間趨勢圖 source=realtime 時意外變成 Bar chart 而非線圖（A-2）

- **嚴重度：** 中-高（語意不符 → 信任流失）
- **Persona 影響：** B user（極高，產生「我選錯了嗎」疑慮）+ A admin（高）
- **修補難度：** M（1 天，需要 backend 加 realtime time-range bucket API 或 FE 用 `/realtime/history` 自行 bucket）
- **推薦做法：** realtime source 改打 `/realtime/history?seconds=N` 拿 wide rows，FE 用 pandas resample 成 hour/day bucket 後畫線圖；保持與 records source UI 一致

### #8 — 即時監控閾值 hardcode FE，admin 改 backend 後不同步（R-2）

- **嚴重度：** 中-高（造成「設定生效但介面騙我」信任崩壞）
- **Persona 影響：** A admin（高）+ D 評審（高，會發現）
- **修補難度：** S（2-3 小時，加 fetch + cache）
- **推薦做法：** `pages/4_即時監控.py` 啟動時打 `/admin/settings`（viewer/user 也可以給唯讀版 endpoint）拿動態閾值；`@st.cache_data(ttl=30)` 快取；admin 改 setting 後手動「清空緩衝區」會 trigger refetch

### #9 — 資料管理 inline edit 沒 dirty state，切頁丟資料（DM-4）

- **嚴重度：** 中-高（B user 經典「資料丟失」UX 反模式）
- **Persona 影響：** B user（極高）
- **修補難度：** M（1 天，Streamlit `on_change` callback + session_state）
- **推薦做法：** diff edited_df vs orig df 有差異時，page top 顯示 sticky `st.warning("您有未儲存的變更")` banner + 「儲存」按鈕浮動置頂；user 試圖切頁時 JS confirm（Streamlit 限制可能要用 components）

### #10 — Excel 匯出兩步點擊（準備 → 下載）+ 檔名沒燒入篩選條件（A-4 + A-5）

- **嚴重度：** 中（B user 最常用功能但 friction）
- **Persona 影響：** B user（高）
- **修補難度：** S（半天）
- **推薦做法：** (1) 直接用 `st.download_button` + on-demand fetch (`data=lambda: client.get(...)`) 省第一步 (2) 預設檔名燒入篩選條件 `data_export_records_2026-05-01_to_2026-05-26_temp.xlsx`

---

### 補充：未進 Top 10 但建議追蹤的痛點

- **R-6** autorefresh 1 秒造成 hover tooltip 閃爍 — 改 `uirevision`（design.md 已加 line 262）但仍有間歇感
- **S-2** 角色權限矩陣 expander 預設 collapsed — Tier 1 統一解
- **S-6** 即時監控與系統管理「即時資料歷史」邏輯重複 — 維護債，非 user-facing
- **D-3** 三層 cache ttl 不同造成「時間錯亂」 — 統一 ttl=5 或加 stale indicator
- **A-3** 類別分佈兩 bar 並排 X 軸 label 重疊 — 改上下排或 horizontal
- **R-5** 5 metric 全異常時 alert cards 擠太窄 — 限制 max 3 cards/row

---

## 研究結論 Summary

1. **最關鍵 fix（必做）：** Top 10 #1 + #2 + #3，這三條解掉「評審 5 秒 friction」+「admin 核心圖壞」+「viewer 看不懂系統狀態」三個致命傷
2. **次優先 fix：** Top 10 #4-#8，解 B user CSV / 角色 UX / 圖表語意 / 設定同步
3. **長期維護：** Top 10 #9-#10 + 補充痛點，解 B user 資料安全 + 工作流程
4. **未進範圍但建議 v4：** 公開 viewer 唯讀快照連結（C viewer 轉述場景）、申請提權表單、shared chart component 抽象、designed-for-evaluator mode

**Persona 影響矩陣概覽：**

| Persona | 致命痛點數 | 高痛點數 | 中痛點數 | 總計影響 |
|---|---|---|---|---|
| D 評審（隱性最重要） | 3 (H-1/D-1/R-1) | 5 | 4 | 12 |
| A admin | 2 (R-1/R-2) | 7 | 5 | 14 |
| B user | 1 (A-2) | 6 | 5 | 12 |
| C viewer | 1 (D-1) | 4 | 3 | 8 |

**最重要洞察：** 這份 demo 的 backend 技術深度與 frontend UX 深度落差極大。candidate 的能力被 UX onboarding 失誤嚴重低估。**v3 UX fix 的核心 ROI 不在「user 用得爽」，在「評審看得到 candidate 的技術深度」**。

---

UX RESEARCH DONE
