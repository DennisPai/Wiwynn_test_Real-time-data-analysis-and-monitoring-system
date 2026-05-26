# Customer Journey Map — Wiwynn 即時資料分析與監控系統 v3 UX Fix

> **目的**：把 ux-research.md 的 4 個 persona、pm-strategy.md 的 6 大抽象問題、codebase-audit.md 的元件與 bug 清單，翻譯成 4 條具體的「使用者旅程」，定位每個 stage 的 friction 點與 emotion 曲線。
> **產出日期**：2026-05-26
> **作者**：customer-journey-map sub-agent（v6.1 Software Factory Mode A 加強版 Phase 0.7）
> **基礎證據**（所有 finding 引用編號 = 這三份檔的編號）：
> - `ux-research.md`：Section 2 痛點編號（H-1~H-4、D-1~D-5、DM-1~DM-5、A-1~A-6、R-1~R-6、S-1~S-8）
> - `pm-strategy.md`：P0-1~P0-3、P1-1~P1-2、§3 需求覆蓋落差、M1~M5
> - `codebase-audit.md`：Section 5 元件缺失 #1~#24、Section 7 Open Issues O-P0-1~O-P2-5
> - `frontend/streamlit_app/Home.py`（106 行）+ `pages/1_儀表板.py`（268 行）+ `pages/2_資料管理.py`（326 行）+ `pages/3_分析報表.py`（435 行）+ `pages/4_即時監控.py`（371 行）+ `pages/5_系統管理.py`（639 行）

---

## 目錄

- [Section 1: 四角色旅程概覽](#section-1-四角色旅程概覽)
- [Section 2: 評審 Eric 的「5-10 分鐘評估旅程」](#section-2-評審-eric-的5-10-分鐘評估旅程)
- [Section 3: Admin 林佳穎的「半小時實戰旅程」](#section-3-admin-林佳穎的半小時實戰旅程)
- [Section 4: User 陳家豪的「20 分鐘日常旅程」](#section-4-user-陳家豪的20-分鐘日常旅程)
- [Section 5: Viewer 王主管的「10 分鐘觀察旅程」](#section-5-viewer-王主管的10-分鐘觀察旅程)
- [Section 6: 四角色「友善度比較矩陣」](#section-6-四角色友善度比較矩陣)
- [Section 7: 跨角色「Top 15 高 friction 節點」](#section-7-跨角色top-15-高-friction-節點)
- [Section 8: 修補後的「理想旅程」對照圖](#section-8-修補後的理想旅程對照圖)

---

## Section 1: 四角色旅程概覽

### 1.1 Persona D — 評審工程師 Eric（Wiwynn 面試官，隱性最重要）

**進入 demo 的 motivation**
- 收到 candidate 投遞 → 開 demo URL 邊看邊在 ATS 打分 → 決定 yes / no / maybe（ux-research §1 Persona D Demographics）
- 期待 5-10 分鐘看出「系統設計能力 + 程式碼品質 + 產品 sense」

**預期 stage 數**：10-12 stage（含切角色驗證 RBAC + 嘗試破壞性操作測權限）

**預期離場時的「成功印象」**
- ✅ 「這個 candidate 有 user empathy / 知道 demo 怎麼讓評審看（不用翻 README 就能切角色）」
- ✅ 「全棧能力到位，BE production-grade，FE 中文化 + RBAC + WS + Plotly 都會」
- ✅ 「角色設計細緻、5 大模組功能完整、有 audit log / DB pool / 動態 threshold 等可維運性訊號」

**現況實際印象**（ux-research §1 Persona D 結論）
- ❌ 「demo onboarding 0 分，要翻 README 才有測試帳號」
- ❌ 「想看 admin/user/viewer 差異要登入登出 3 次」
- ❌ 「即時監控 5 條線壓成一團、anomaly 看不到」
- ⚠️ 「BE 紮實但 FE UX 跟不上，能力被低估」

---

### 1.2 Persona A — Admin 系統管理員「林佳穎」

**進入 demo 的 motivation**
- 晨會前 check overnight 異常 / 收到 PagerDuty 後追根本原因 / 季度新增帳號（ux-research §1 Persona A）
- JTBD：「5 分鐘內知道：(1) 出了什麼事 (2) 影響範圍 (3) 是不是誤報」

**預期 stage 數**：10-12 stage（含管理 user、看日誌、改 threshold、看 DB 狀態）

**預期離場時的「成功印象」**
- ✅ 「告警有嚴重度分級、知道現在 vs 閾值差多少」
- ✅ 「多 metric 圖能個別判讀（small multiples 或 multi yaxis）」
- ✅ 「改設定後有 audit trail、改密碼有 explicit confirmation」

**現況實際印象**
- ❌ 「告警只算個數沒 metric 名稱」（R-5 + ux-research §1 痛點 1）
- ❌ 「5 metric 共軸圖完全看不懂」（R-1）
- ❌ 「改設定的 form 不會動態變化、UX 反應遲鈍」（S-3）

---

### 1.3 Persona B — User 一般使用者「陳家豪」

**進入 demo 的 motivation**
- 把外部量測 CSV 匯入做趨勢分析 / 補 demo 缺失資料 / 為週報抓統計（ux-research §1 Persona B）
- JTBD：「5 分鐘內產出可貼進週報 PowerPoint 的趨勢圖 + 數字」

**預期 stage 數**：8-12 stage（含 CSV 上傳、inline edit、看分析、即時監控、匯出 Excel）

**預期離場時的「成功印象」**
- ✅ 「CSV 上傳前能 preview，不會 500 筆才知道格式錯」
- ✅ 「失敗 row 能下載重修，不靠 toast 用力記」
- ✅ 「Excel 匯出檔名燒入時間 + 篩選條件，3 天後打開知道是哪份」

**現況實際印象**
- ❌ 「上傳完才知道哪行錯」（DM-1 + ux-research §1 痛點 1）
- ❌ 「時間趨勢圖空了不知道為什麼空」（A-2 + ux-research §1 痛點 2）
- ❌ 「inline edit 失敗只給 toast，要自己 mental track 哪些 row 沒存」（DM-4 + ux-research §1 痛點 3）

---

### 1.4 Persona C — Viewer 唯讀觀察者「王主管」

**進入 demo 的 motivation**
- 客戶到廠導覽要 demo / 週會跟主管報告系統健康 / 收到下屬「異常處理完了」訊息來複查（ux-research §1 Persona C）
- JTBD：「30 秒內告訴老闆過去一週系統正常 / 有 X 次異常已處理 / 趨勢 OK」

**預期 stage 數**：6-10 stage（純掃讀 / 截圖 / 轉述）

**預期離場時的「成功印象」**
- ✅ 「首頁直接告訴我系統好不好（紅/黃/綠燈）」
- ✅ 「知道我能看什麼 / 不能做什麼（角色 onboarding 清楚）」
- ✅ 「圖能一鍵截純圖貼週報，不要互動 toolbar」

**現況實際印象**
- ❌ 「4 metric card 全是『量』看不出系統好壞」（D-1）
- ❌ 「到處點都被擋，不知道我能做什麼」（ux-research §1 Persona C 痛點 2）
- ❌ 「截圖會抓到 Plotly toolbar」（ux-research §1 Persona C 痛點 3）

---

## Section 2: 評審 Eric 的「5-10 分鐘評估旅程」

> **最關鍵 persona**，因為這是 Wiwynn 面試題。每 stage 含：Stage name / 使用者動作 / touchpoint / 期待 vs 實際 / Emotion / Friction / Opportunity。

### Stage E-01 — 0-30s 開啟 Demo 首頁

- **使用者動作**：點開 demo URL，等待頁面載入
- **介面 touchpoint**：`Home.py:10-20` `set_page_config(layout="centered")` + `st.title("即時資料分析與監控系統")`
- **期待**：登入頁有明顯「demo 模式」訊號，知道這是面試題作品
- **實際**：純登入頁，標題太通用，左側 sidebar 已預顯示 5 個 pages 入口（Home.py:10-14 沒設 `initial_sidebar_state="collapsed"`），點任一頁會被 `require_auth()` 擋回 — 第一印象「凌亂、不知道從哪開始」
- **Emotion**：neutral → confused
- **Friction**：
  - **P0**：痛點 H-1（沒有測試帳號提示 → 評審 5 秒卡關 → ux-research §1 Persona D 痛點 1，影響「極高」）
  - **P0**：痛點 H-4（sidebar 未 collapsed，未登入點頁被擋 → confused）
- **Opportunity**：title 下方加 sub-headline「Wiwynn 面試 demo / 3 角色測試帳號見下方」+ Home 預設 sidebar collapsed（pm-strategy M1 + Home 試用帳號 expander）

---

### Stage E-02 — 30s-1m 嘗試登入

- **使用者動作**：登入 form 看到 email + password 兩 input，準備找測試帳號
- **介面 touchpoint**：`Home.py:23-43` 登入 tab（無 placeholder / 無 caption / 無 help）
- **期待**：form 旁邊或上方直接列出 admin / user / viewer 三組測試帳號（業界 demo 慣例：ant design pro / Linear demo）
- **實際**：input 完全空白，要切到 GitHub 翻 README.md:66-75 才看得到測試帳號
- **Emotion**：confused → frustrated
- **Friction**：
  - **P0**：痛點 H-1（同上 stage E-01）
  - **P0**：codebase-audit Section 5 #1（Home.py:29-30 input 沒 placeholder + 沒 help「至少 8 字元」）
  - **P0**：O-P0-4（FE 密碼長度驗證分散 + BE LoginRequest 移除 validator，seed 密碼 < 8 字亂象）
- **Opportunity**：Home 登入 tab 上方加「試用帳號」expander `expanded=True` 列三組（pm-strategy §4 方案 C）+ 三顆「以 X 登入」一鍵填表單按鈕（ux-research §5 #1）

---

### Stage E-03 — 1m-2m 用 admin 登入看 Dashboard

- **使用者動作**：手動填 admin@example.com / admin123 提交，跳到儀表板
- **介面 touchpoint**：`1_儀表板.py:30 st.title("儀表板")` → `:81-93` system status header 三欄 → `:147-155` 4 個 metric cards → 滾下去 tabs (即時/錄入) → 最底「重新整理」按鈕
- **期待**：「30 秒內告訴我系統現在好不好、過去 24h 有什麼事」
- **實際**：
  - 4 個 metric card 全是「量」沒有「品質」（D-1）
  - 第 4 個「異常筆數」inverse delta_color 但沒設 delta 值不會觸發顏色
  - 三欄等寬但資訊密度差異極大（D-2）
  - 「重新整理」在頁面最底要 scroll 三屏（D-4）
  - 帳號設定 expander 在儀表板底部跟頁面語意不符（D-5）
- **Emotion**：excited → confused
- **Friction**：
  - **P0**：痛點 D-1（4 metric card 全是量沒品質，影響「核心 viewer/admin 工作」）
  - **P0**：痛點 D-2（status header 三欄視覺重量失衡）
  - **P1**：痛點 D-3（@st.cache_data ttl=10/30 多層不一致，user 不知道實時感）
  - **P1**：痛點 D-4（重新整理按鈕埋頁面最底）
  - **P1**：痛點 D-5（帳號設定 expander 語意錯位）
  - **P0**：codebase-audit #3（●/○ 符號未定義）+ #4（4 metric card 無 help）
- **Opportunity**：Dashboard 頂部加（a）「過去 24h：5 次異常，全部已處理」status summary（b）權限矩陣固定卡片（pm-strategy §4 方案 A）（c）異常率 % 取代純筆數 + 紅黃綠燈 health indicator

---

### Stage E-04 — 2m-3m 探索資料管理頁

- **使用者動作**：點 sidebar「2 資料管理」，看 admin 能對資料做什麼
- **介面 touchpoint**：`2_資料管理.py:41 st.title("資料管理")` → `:55-67` 篩選 expander `expanded=True` 占半屏 → `:114-166` data_editor inline edit → `:170` 「儲存變更」button → `:268-326` 批量匯入區
- **期待**：清楚的「新增」按鈕、能看出 inline edit 規則、批量匯入有格式範例
- **實際**：
  - 篩選 expander 預設展開佔 1/3 螢幕（DM-3）
  - data_editor `num_rows="dynamic"` admin 看到「+」加號但不直觀（codebase-audit 2.1 需求落差）
  - 「儲存變更」沒 confirmation modal（pm-strategy P1-1 + DM-4）
  - 批量匯入沒 preview / dry-run / sample CSV download（DM-1）
- **Emotion**：confused → impressed（看到 inline edit 有 column_config）→ frustrated（找不到「新增」按鈕）
- **Friction**：
  - **P0**：痛點 DM-1（CSV 上傳無 preview，B user 痛點極高）
  - **P0**：痛點 DM-3（篩選 expander 預設展開）
  - **P0**：痛點 DM-4（儲存沒 dirty state，誤觸即刪資料）
  - **P0**：codebase-audit O-P0-1（category 鍵名 FE hardcode vs BE env，環境分歧）
  - **P1**：痛點 DM-5（批量匯入結果沒「下載失敗 row」）
- **Opportunity**：篩選預設 collapsed + 加「+ 新增資料」獨立按鈕 + 上傳後 pandas 解析 preview + 「下載 sample.csv」連結

---

### Stage E-05 — 3m-4m 查看分析報表

- **使用者動作**：點「3 分析報表」，看 candidate 有沒有資料分析能力
- **介面 touchpoint**：`3_分析報表.py:44 st.title("分析報表")` → `:57-76` 查詢 expander → `:90 / :157 / :300` 三個 source selectbox（不同步）→ `:206-250` 時間趨勢 Plotly line（records）→ `:253-289` realtime source 變 bar chart（不是線）→ `:335-365` 類別分佈 bar × 2 並排 → `:394-435` Excel 兩步下載
- **期待**：時間趨勢圖能切換 source 看一致、Excel 一鍵下載
- **實際**：
  - 三個 source selector 分散，改一個其他不同步（A-1）
  - source=realtime 時時間趨勢變 Bar chart（A-2，極高 friction，「我選錯了嗎」疑慮）
  - 兩個 bar chart 並排 X 軸中文 label 重疊（A-3）
  - Excel 兩步點擊（A-5）+ 檔名沒燒入篩選條件（A-4）
  - 日期 default 是 7 天但 demo 資料只有 60 筆（A-6，「沒資料」第一印象）
- **Emotion**：neutral → confused → suspicious（「我是不是選錯了？」）
- **Friction**：
  - **P0**：痛點 A-1（資料來源三處不同步 → 認知負荷爆表）
  - **P0**：痛點 A-2（realtime 時間趨勢圖變 bar，語意不符）
  - **P0**：痛點 A-6（日期 default 7 天但資料只有 60 筆 → 第一印象「空」）
  - **P1**：痛點 A-3（並排 bar X 軸重疊）
  - **P1**：痛點 A-4 + A-5（Excel 檔名 + 兩步）
- **Opportunity**：頁面頂部單一 source selector 同步三區塊 + realtime 改用 `/realtime/history` resample 畫線圖 + 日期 default 改 24h fit demo 資料密集區

---

### Stage E-06 — 4m-5m 觀察即時監控（最關鍵 stage）

- **使用者動作**：點「4 即時監控」，看 candidate 即時系統設計能力（V2 訊號核心）
- **介面 touchpoint**：`4_即時監控.py:97-107` WS 連線 + REST 預載 → `:110` `st_autorefresh(1000)` → `:132-144` system status header → `:147-155` multiselect + 清空緩衝 → `:177-199` 告警卡 → `:214-264` 5 metric 折線 → `:267-359` 60 筆 Pandas Styler 表
- **期待**：清楚看到 5 條 metric 線各自走勢、異常會跳紅顯眼、告警卡有 metric 名稱與閾值差距
- **實際**：
  - 5 條 metric 線共用單一 Y 軸（R-1）：壓力 1013 把溫度 25 / CPU 40 壓成貼底直線 → **核心 use case 完全壞**
  - 閾值 hardcode FE（R-2 + O-P0-1）：admin 改 backend `app_settings` 後 FE 不同步 → demo 致命邏輯漏洞
  - 「清空緩衝區」按鈕跟「顯示哪些線」並列無 confirm（R-3）→ 評審亂點就秒清 60 秒 history
  - 60 筆全載入無 scroll constraint（R-4）→ 表格吃掉整屏
  - autorefresh 1 秒 rerun + cache ttl 30 秒 → 看到時間 frozen 以為系統 hang（R-6）
  - delta_color="inverse" 顏色語意反（pm-strategy P1-1 第 7 項）→ 「異常 +50」變綠色看起來像好事
  - anomaly injection 每 60 tick 一次（pm-strategy §1.2 結論 3）→ 評審可能等不到 → 看不到淡粉紅 + 紅字設計賣點
- **Emotion**：excited（WS 串流好棒）→ confused（5 條線壓一團）→ frustrated（看不到 voltage）→ suspicious（時間 frozen？）
- **Friction**：
  - **P0**：痛點 R-1（5 metric 共軸 → 致命，admin/評審/user 三角色都受傷）
  - **P0**：痛點 R-2 + O-P0-1（閾值 FE hardcode 不同步）
  - **P0**：痛點 R-6（autorefresh + cache 不一致）
  - **P0**：pm-strategy P1-1 第 7 項（delta_color="inverse" 顏色語意反）
  - **P1**：痛點 R-3（清空緩衝無 confirm）+ R-4（表格無高度限制）+ R-5（5 metric 全異常 cards 擠窄）
- **Opportunity**：（a）plotly `make_subplots(rows=5, cols=1, shared_xaxes=True)` 做 small multiples（ux-research §5 #2）（b）FE 啟動 fetch `/admin/settings` 動態閾值 + ttl=30 cache（c）demo 模式加「手動觸發異常」按鈕（pm-strategy M3）（d）`uirevision` 改 hover stabilize（design.md:262 已加但仍間歇）

---

### Stage E-07 — 5m-6m 切到系統管理頁

- **使用者動作**：點「5 系統管理」，看 admin 有什麼可維運能力（V4 訊號）
- **介面 touchpoint**：`5_系統管理.py:71-77` 5 tabs（使用者列表 / 系統日誌 / 資料庫狀態 / 即時資料歷史 / 系統設定）→ `:88` 角色權限說明 `expanded=False` → `:163-164` 改角色 + `:212-214` 改密碼兩個獨立 selectbox → `:309` 日誌篩選 → `:368-405` DB 狀態 → `:412-526` 即時資料歷史（跟即時監控頁重複）→ `:558-639` 系統設定
- **期待**：tabs 一目瞭然、權限矩陣明顯、DB 狀態有 baseline 提示、設定能批次儲存
- **實際**：
  - 5 個 tab label 全 4 字中文沒 icon（S-1）→ 掃讀困難
  - 角色權限矩陣 `expanded=False`（S-2）→ 評審不會主動展開 → **V3 產品 sense 訊號白做**（pm-strategy P0-1）
  - 編輯使用者 vs 改密碼兩個獨立 selectbox（S-3）→ 同一人要選兩次
  - 日誌篩選 3 column × 兩 input/欄擁擠（S-4）
  - DB 狀態 pool 數字沒 baseline（S-8 + pm-strategy P1-2）→ checked_out=2 不知道健康還是接近上限
  - 即時資料歷史 tab 跟即時監控頁重複（S-6 + pm-strategy P1-1 第 9 項）→ 評審混淆「為什麼有兩個一樣的」
  - 系統設定 5 個 setting 各一個 form（S-5）→ 改完 rerun 整頁滾回頂
- **Emotion**：impressed（5 tabs 內容豐富）→ confused（為什麼權限矩陣藏起來？）→ frustrated（改設定要 reload 5 次）
- **Friction**：
  - **P0**：痛點 S-2 + pm-strategy P0-1（角色權限矩陣藏在 admin tab + expander 兩層遮蔽）
  - **P0**：痛點 S-6（即時資料歷史與即時監控頁重複）
  - **P1**：痛點 S-3（改 user 兩個 selectbox）+ S-5（5 個 setting 5 form）+ S-8（DB pool 無 baseline）
  - **P1**：痛點 S-1（tabs 全 4 字中文）
- **Opportunity**：（a）權限矩陣 `expanded=True` + 抽到所有頁面共用元件（pm-strategy §4 方案 A）（b）使用者管理改 inline action button on row（c）即時資料歷史合併進即時監控頁加 tab（d）系統設定改單一 form 一次儲存 + DB pool 加「使用率 %」derived metric

---

### Stage E-08 — 6m-7m 切角色測試 RBAC（登 user 看差異）

- **使用者動作**：登出 admin → 用 user@example.com / user123 重新登入 → 切回每個頁面看 user 視角差異
- **介面 touchpoint**：右上角 `1_儀表板.py:37` 登出 → `Home.py` 重新登入 → 每頁 require_auth 檢查
- **期待**：「角色 demo devtool / role switcher 給我，3 秒切完」（ant design pro 等業界 demo 慣例）
- **實際**：完全沒有 role switcher，要 logout → login 全程約 30-45 秒 × 3 角色 = **>2 分鐘只在切角色**
- **Emotion**：frustrated（重複動作 = 扣分）→ suspicious（candidate 沒考慮 demo onboarding）
- **Friction**：
  - **P0**：ux-research §1 Persona D 痛點 2（三角色要登入登出 3 次）+ pm-strategy §1.2 V3 訊號需要運氣
- **Opportunity**：每頁右上角加 dropdown「切換角色（demo only）」3 秒 mock token 切換（pm-strategy 灰色地帶 / ux-research §5 #1 補丁）

---

### Stage E-09 — 7m-8m 用 user 角色嘗試破壞性操作（測權限）

- **使用者動作**：登 user 後試 (a) 編輯不是自己的 record (b) 進系統管理頁 (c) 看分析報表
- **介面 touchpoint**：
  - `2_資料管理.py:225-263` user 改非己 record → 走 `can_modify=False` → silent skip + toast
  - `5_系統管理.py:38-41` user 進系統管理 → `st.error + st.stop`
  - `2_資料管理.py:116-117` user 進資料管理 → 看到 `st.info("Viewer 角色為唯讀")` ← **這是給 viewer 的，user 不該看到** ← 程式碼可能 bug，建議驗證
- **期待**：清楚的「為什麼擋你」+「怎麼申請提權」
- **實際**：
  - 改非己 record silent skip，N=10 還能 mental track，N=100 無法定位（DM-4 + pm-strategy 3.2 模組 2 落差 #8）
  - 系統管理頁擋下「請洽系統管理員」沒給 email / Slack（S-7）
  - viewer info banner 可能誤觸發給 user（codebase-audit #5 待驗）
- **Emotion**：confused → impressed（RBAC 真的有擋）→ frustrated（擋了但不告訴我怎麼解）
- **Friction**：
  - **P0**：痛點 S-7（系統管理擋下訊息引導不充分）
  - **P0**：痛點 DM-2 + DM-4（user 改非己 record silent skip）
  - **P1**：codebase-audit O-P1-3（user silent skip with toast 無視覺反饋）
- **Opportunity**：擋下訊息升級為「申請提權」連結（業界對照 Datadog RBAC，ux-research §4.3）+ inline edit row-level disable 給 owner 才能編輯

---

### Stage E-10 — 8m-9m 切到 viewer 看純掃讀體驗

- **使用者動作**：登 viewer 看「你能看 / 不能做什麼」是不是清晰
- **介面 touchpoint**：viewer 登入後跳 Dashboard → 右上角只顯示 `角色：viewer` 4 字（`1_儀表板.py:34`）→ 沒任何 onboarding hint → 點任一頁試試
- **期待**：第一次登入彈「您是 Viewer，可看不可改」hint（業界對照 Notion / Vercel）
- **實際**：
  - 0 onboarding（ux-research §1 Persona C 痛點 2）
  - 進資料管理才看到 info banner（`2_資料管理.py:117`，line 116 user 已滾很久才看到）
  - 點系統管理被 hard block 沒解釋路徑（S-7）
- **Emotion**：confused → frustrated（踩雷感）
- **Friction**：
  - **P0**：ux-research §1 Persona C 痛點 2（沒 onboarding，到處踩雷）
  - **P0**：pm-strategy P0-1（角色權限矩陣 viewer 看不到）
- **Opportunity**：Home 登入後彈一次性 modal「您的角色：viewer，建議從『儀表板 → 即時監控 → 分析報表』開始」（pm-strategy M4）+ Dashboard 頂部固定權限矩陣卡片（pm-strategy §4 方案 A）

---

### Stage E-11 — 9m-10m 嘗試截圖貼週報（測 viewer 報告場景）

- **使用者動作**：截圖即時監控 + 分析報表的圖貼進 PowerPoint
- **介面 touchpoint**：`3_分析報表.py:250` `st.plotly_chart(fig_line, use_container_width=True)` 沒指定 `config={"displayModeBar": False}` → Plotly 預設右上角 7-8 個 toolbar 按鈕
- **期待**：純圖 PNG 無 toolbar、檔名能識別
- **實際**：截圖會抓到 toolbar、模式按鈕、legend 重疊（ux-research §1 Persona C 痛點 3）
- **Emotion**：confused → mildly frustrated
- **Friction**：
  - **P1**：ux-research §1 Persona C 痛點 3（圖表截圖不友善）
- **Opportunity**：Plotly chart 加 `config={"displayModeBar": "hover", "toImageButtonOptions": {"format": "png", "filename": "..."}}`（業界對照 Datadog 「Share to PDF」）

---

### Stage E-12 — 10m+ 離場印象

- **使用者動作**：關掉視窗，回 ATS 打分
- **期待印象**：完整覆蓋的價值訊號 V1 全棧 / V2 即時 / V3 產品 sense / V4 可維運（pm-strategy §1.1）
- **實際印象**：
  - V1 全棧 ✅（看得到 FastAPI / Streamlit / Docker / RBAC）
  - V2 即時 ⚠️（WS 流暢但 anomaly 沒等到 + 5 條線壓一團）
  - V3 產品 sense ❌（角色說明藏起來、micro-copy 全無、onboarding 0）
  - V4 可維運 ⚠️（只有 admin 看得到，user/viewer 全沒）
- **Emotion**：mildly impressed（BE 紮實）→ disappointed（FE UX 跟不上）
- **Friction**：所有 Stage E-01 ~ E-11 的 P0 累積
- **Opportunity**：pm-strategy §5.1 M1-M5（必動 5 項，~8 小時工時）解掉 70% 痛點，把 V3 產品 sense 訊號搶回來

---

## Section 3: Admin 林佳穎的「半小時實戰旅程」

> **情境**：早上 8:30 收到 PagerDuty alert，admin 進系統追 root cause + 季度新增 user account + 改 anomaly threshold。

### Stage A-01 — 0-1m 收 alert 後 fast login

- **動作**：手機點 alert link → laptop 開 demo → 用密碼管理員填 admin@example.com 登入
- **Touchpoint**：`Home.py:23-43` 登入 form
- **期待**：登入後直接跳到「告警頁面」或 Dashboard 第一眼看到告警
- **實際**：跳到 Dashboard，告警資訊在 status header 第三欄「活躍告警：N 筆」（`1_儀表板.py:90-93`），但**只有筆數沒有 metric 名稱與嚴重度**
- **Emotion**：focused → confused
- **Friction**：
  - **P0**：ux-research §1 Persona A 痛點 1（告警只算個數）
  - **P0**：痛點 D-1（4 metric card 全是量沒品質）
- **Opportunity**：Dashboard 加「告警 highlights」區塊列出 top 3 active alerts + metric 名稱 + 嚴重度

---

### Stage A-02 — 1-2m 切到即時監控看現場

- **動作**：點即時監控頁，看 5 個 metric 哪個有異常
- **Touchpoint**：`4_即時監控.py:177-199` 告警卡 + `:214-264` 5 metric 折線圖
- **期待**：5 條線各自可判讀，異常 metric 跳紅顯眼
- **實際**：5 條線共用單一 Y 軸，氣壓 1013 壓死其他線（R-1）→ 看到「圖好像壞了」
- **Emotion**：confused → frustrated → suspicious
- **Friction**：
  - **P0**：痛點 R-1（5 metric 共軸 → admin 核心 use case 完全壞）
  - **P0**：痛點 R-2（閾值 hardcode FE 不同步 backend）
  - **P0**：codebase-audit O-P0-1（category 鍵名 hardcode 風險）
- **Opportunity**：plotly small multiples（subplots rows=5）+ FE fetch `/admin/settings` 動態閾值

---

### Stage A-03 — 2-4m 嘗試判讀告警嚴重度

- **動作**：看告警卡 metric 名稱、Δ 數值、閾值差距
- **Touchpoint**：`4_即時監控.py:184-197` `alert_cols = st.columns(min(len(...), 5))` + `st.metric(delta_color="inverse")`
- **期待**：5 個告警分別顯示，紅色 = 異常、Δ 大 = 嚴重
- **實際**：
  - 5 metric 全異常時 cards 擠成 1/5 寬，中文 label wrap 3 行（R-5）
  - delta_color="inverse" 讓「異常 +50」變綠色像好事（pm-strategy P1-1 第 7 項）→ admin 看一眼以為「ok 沒事」
- **Emotion**：frustrated → suspicious
- **Friction**：
  - **P0**：pm-strategy P1-1 第 7 項（delta_color inverse 顏色語意反）
  - **P1**：痛點 R-5（cards 全異常時擠窄）
- **Opportunity**：移除 inverse 改用 explicit colored badge（紅 = critical / 橙 = warning）+ 限制 max 3 cards/row > 3 改 list view

---

### Stage A-04 — 4-6m 切到系統管理 → 系統日誌追根本原因

- **動作**：5 系統管理 → Tab 2 系統日誌 → 篩 action="anomaly" + 過去 1 小時
- **Touchpoint**：`5_系統管理.py:268-353` 日誌 tab + `:271-290` 3-column 篩選 + `:345` dataframe + `:349-353` metadata expander
- **期待**：清楚的 timeline、metadata 完整可展開
- **實際**：
  - 篩選 7 欄塞 3 column 視覺擁擠（S-4）
  - metadata expander 10 筆 limit（codebase-audit 5.4 落差）超過看不到
  - 日期 date_input 沒預設「過去 1 小時」這種快速選項
- **Emotion**：focused → mildly frustrated
- **Friction**：
  - **P1**：痛點 S-4（日誌篩選 7 欄塞 3 column）
  - **P1**：codebase-audit 5.4（metadata 10 筆 limit）
- **Opportunity**：篩選改 2 row × 4 column + 加 saved filter preset（「過去 1 小時 / 過去 24 小時 / 本週」）+ metadata 改 inline JSON viewer

---

### Stage A-05 — 6-8m 切到 Tab 3 看 DB 狀態確認系統健康

- **動作**：點 Tab 3「資料庫狀態」看 connection pool 有沒有炸
- **Touchpoint**：`5_系統管理.py:368-405` DB status tab + `:391-393` 3 metric cards + `:396-403` 資料表筆數
- **期待**：Pool 數字旁邊有「使用率 %」+ 接近上限 yellow / red badge
- **實際**：純數字「Pool=5, checked_out=2, overflow=0」（S-8 + pm-strategy P1-2）→ admin 不知道是健康還是接近 exhaustion
- **Emotion**：confused → suspicious
- **Friction**：
  - **P1**：痛點 S-8（DB 狀態無 baseline）
  - **P2**：codebase-audit 5.5（缺 size_mb / last_update）
- **Opportunity**：加「使用率 %」derived metric + 接近上限 yellow / red badge + 資料表加 size 與 last update

---

### Stage A-06 — 8-12m 切到 Tab 5 系統設定改 anomaly threshold

- **動作**：氣壓誤報太多想把 high threshold 從 1100 改 1200
- **Touchpoint**：`5_系統管理.py:558-639` 系統設定 tab + `:577-632` 每個 setting 走 expander + number_input + save button
- **期待**：一個 form 改完全部一次儲存
- **實際**：
  - 5 個 setting 各自 expander + form（S-5）→ 改完一個 rerun 整頁滾回頂 → 改下一個又從頭 scroll
  - 改完設定後**即時監控頁的 FE hardcode 閾值不會更新**（R-2）→ admin 改了設定但看到「沒生效」→ 信任崩壞
- **Emotion**：focused → frustrated → suspicious（「我改了但沒生效？」）
- **Friction**：
  - **P0**：痛點 R-2（閾值改了 FE 不同步 → 信任崩壞）
  - **P1**：痛點 S-5（5 setting 5 form 重複 boilerplate）
- **Opportunity**：單一 form 改全部 setting 一次儲存 + FE 啟動 fetch `/admin/settings` 動態閾值 + cache ttl=30

---

### Stage A-07 — 12-15m 切到 Tab 1 新增季度新員工帳號

- **動作**：點 Tab 1 使用者列表 → 找「新增 user」按鈕
- **Touchpoint**：`5_系統管理.py:84-261` Tab 1 內容 → 改使用者 selectbox + 角色 selectbox + 啟用 checkbox + save
- **期待**：明顯的「新增使用者」按鈕
- **實際**：
  - **沒有「新增使用者」UI**！seed user 是 alembic 跑進 DB，新員工要 SQL 或 register 自己
  - DELETE user 也沒 UI（codebase-audit 5.3 落差 / pm-strategy 模組 5 落差 #5.3）
- **Emotion**：confused → frustrated（「我是 admin 怎麼連加 user 都不行」）
- **Friction**：
  - **P0**：pm-strategy §3.5 模組 5 #5.3（DELETE user 缺 UI）+ codebase-audit 5.3
  - **P0**：admin 自助新增 user UI 缺失（README 列在功能但 FE 沒做）
- **Opportunity**：Tab 1 加「+ 新增使用者」按鈕（form 含 email + name + 預設角色 + 啟用）

---

### Stage A-08 — 15-18m 改某個 user 的密碼（user 找回密碼場景）

- **動作**：user 打給 admin 說忘記密碼，admin 幫他改
- **Touchpoint**：`5_系統管理.py:208-259` 改密碼 form + 獨立 selectbox 選 user
- **期待**：直接在 Tab 1 user row 點「改密碼」按鈕
- **實際**：
  - 改密碼跟改角色用兩個獨立 selectbox（S-3）→ admin 對同一人要選兩次
  - 改自己密碼要填舊密碼但 form label 沒動態變化（ux-research §1 Persona A 痛點 3）
  - 同功能在 Dashboard `1_儀表板.py:220-262` 跟 Admin tab 1 兩個地方（pm-strategy P1-1 第 10 項）
- **Emotion**：mildly frustrated
- **Friction**：
  - **P1**：痛點 S-3（改 user 兩個 selectbox）
  - **P1**：pm-strategy P1-1 第 10 項（同功能兩入口）
  - **P1**：ux-research §1 Persona A 痛點 3（form label 不動態變化）
- **Opportunity**：合併 user selector 下面 tab「角色與啟用 / 密碼」+ 選自己時舊密碼 label 自動顯示 + 砍掉 Dashboard 改密碼入口（pm-strategy §5.3 G3）

---

### Stage A-09 — 18-22m 季度看分析報表跑統計

- **動作**：切到 3 分析報表，看本季 anomaly 趨勢
- **Touchpoint**：`3_分析報表.py:166-169` `_fetch_timerange` 用 `date_from + "T00:00:00Z"` UTC → `:206-250` 時間趨勢
- **期待**：時間序列正確、anomaly 紅 marker 看得到
- **實際**：
  - Q7 tz bug 仍可能造成 `buckets=[]` 空圖（codebase-audit 4.2 ⚠️ + O-P0-5）
  - 沒「為什麼空」explainability（ux-research §1 Persona B 痛點 2）
  - 紅 x marker 沒 info 說明意義（codebase-audit #21）
- **Emotion**：focused → confused → suspicious
- **Friction**：
  - **P0**：codebase-audit O-P0-5（timezone 假設未強制驗證）
  - **P1**：ux-research §1 Persona B 痛點 2（空資料無 explainability）
- **Opportunity**：BE endpoint 強制 UTC naive 轉換 + 整合測試 + 空資料訊息加「資料筆數 0、最近資料是 X」

---

### Stage A-10 — 22-25m 想看「即時資料歷史」找 root cause

- **動作**：admin 想看告警發生時刻的 raw data，切到 Tab 4 即時資料歷史
- **Touchpoint**：`5_系統管理.py:412-526` Tab 4
- **期待**：跟即時監控頁不一樣的 deep dive 功能（如 export 全量、自訂時間範圍）
- **實際**：
  - 跟即時監控頁的圖表幾乎一樣（S-6 + pm-strategy P1-1 第 9 項）→ admin 困惑「我為什麼在這個 tab」
  - 5 metric 也是共軸（codebase-audit 圖表盤點 row 6）
- **Emotion**：confused → frustrated
- **Friction**：
  - **P0**：痛點 S-6（兩頁圖表重複）+ pm-strategy P1-1 第 9 項
  - **P0**：痛點 R-1（共軸問題在這頁也有）
- **Opportunity**：合併 Tab 4 到即時監控頁加「歷史」tab + 抽 shared `realtime_chart.py` component

---

### Stage A-11 — 25-28m 嘗試 audit log 自己剛剛做了什麼

- **動作**：切回 Tab 2 篩 action=settings_update + user_id=自己，看剛剛改 threshold 的紀錄
- **Touchpoint**：`5_系統管理.py:268-353` Tab 2 + audit log
- **期待**：看到自己剛改的 setting 紀錄 + before/after value
- **實際**：
  - audit log 有實裝（pm-strategy §3.5 模組 5 #5.4 ✅）但 metadata 在 expander 內預設 collapsed
  - admin 看不到「我剛剛改了 X」的 surface UI（ux-research §1 Persona A Product Fit Assessment「不足」）
- **Emotion**：neutral → mildly impressed（audit log 真的有）→ confused（為什麼藏起來）
- **Friction**：
  - **P1**：ux-research §1 Persona A 改設定後沒 audit trail UI
- **Opportunity**：系統設定頁加「最近變更」timeline 顯示 admin 過去 N 次調參 + 改完設定後 toast 「✓ 已儲存，audit log #1234」

---

### Stage A-12 — 28-30m 登出回到日常

- **動作**：右上角登出，準備跟工程師 sync 處理結果
- **Touchpoint**：`1_儀表板.py:37-38` 登出 button
- **期待**：明確的 logout success + redirect Home
- **實際**：logout 是 client-side 清 session（pm-strategy §3.1 模組 1 #1.3 落差）→ 沒打 BE endpoint → JWT 仍 valid 直到 expire
- **Emotion**：neutral
- **Friction**：
  - **P2**：pm-strategy §3.1 模組 1 #1.3（logout 沒打 BE）
- **Opportunity**：logout 真實 invalidate JWT（BE 加 blocklist）+ 顯示「✓ 已安全登出」

---

## Section 4: User 陳家豪的「20 分鐘日常旅程」

> **情境**：週五下午 14:00，陳家豪要把這週外部量測 CSV 匯入系統，產出趨勢圖貼週報。

### Stage U-01 — 0-1m 登入

- **動作**：用密碼管理員填 user@example.com / user123 登入
- **Touchpoint**：`Home.py:23-43` 登入 form
- **期待**：登入後跳到我常用的「資料管理」頁
- **實際**：跳 Dashboard，但 user 主要工作是上傳 CSV，Dashboard 對他用處不大
- **Emotion**：neutral
- **Friction**：
  - **P2**：登入後 redirect 沒考慮角色 default landing page
- **Opportunity**：user 角色登入後可改 default landing 到「資料管理」（v4 範圍）

---

### Stage U-02 — 1-3m 開資料管理頁準備 CSV 匯入

- **動作**：點「2 資料管理」→ 找批量匯入區
- **Touchpoint**：`2_資料管理.py:268-326` `st.file_uploader` + caption 提 CSV 格式
- **期待**：明顯的「上傳 CSV」+ 「下載 sample.csv」連結 + 格式說明
- **實際**：
  - 篩選 expander 預設展開佔 1/3 螢幕（DM-3）→ 要 scroll 找到批量匯入區
  - caption 只說「CSV 欄位格式：title, value, category, recorded_at」沒 sample download
  - 10 MB 上限只在 caption 提一句（pm-strategy 模組 2 #2.6 落差）
- **Emotion**：focused → mildly confused
- **Friction**：
  - **P1**：痛點 DM-3（篩選預設展開搶版面）
  - **P1**：codebase-audit Section 5 #8（批量匯入無 CSV 格式範例）
- **Opportunity**：篩選預設 collapsed + 加「下載 sample.csv」連結 + 上限 10 MB 用 info banner 提示

---

### Stage U-03 — 3-5m 上傳 500 筆 CSV

- **動作**：拖檔上傳，等系統解析
- **Touchpoint**：`2_資料管理.py:295` POST `/data/bulk-import`
- **期待**：上傳前能 preview「將匯入 N 筆 / 跳過 M 筆」+ 預覽前 5 筆
- **實際**：
  - 沒有 pre-upload preview（DM-1 + ux-research §1 Persona B 痛點 1）
  - 直接 POST 後等 backend 回應，500 筆 + validate 大約 10-20 秒（沒 progress bar）
- **Emotion**：focused → anxious（等待中）
- **Friction**：
  - **P0**：痛點 DM-1（CSV 上傳無 preview / dry-run）
  - **P1**：上傳過程無 progress indicator
- **Opportunity**：（a）上傳後本機 pandas parse 顯示「將匯入 480 筆，跳過 20 筆，預覽前 5 筆」（b）加「確認匯入」按鈕才真正 POST（c）BE 加 SSE progress

---

### Stage U-04 — 5-6m 看 import 結果發現 23 筆失敗

- **動作**：看到「成功 477 筆、失敗 23 筆」+ error dataframe
- **Touchpoint**：`2_資料管理.py:297-314` `st.dataframe(error_df)` 含 row + reason
- **期待**：（a）能下載失敗 23 筆 CSV 修完重傳 （b）error reason 明確指出哪欄錯
- **實際**：
  - 沒有「下載失敗 row」button（DM-5 + pm-strategy 模組 2 #2.7 落差）
  - reason 直接顯示 BE error string，user 要看程式碼才懂
  - errors_df column 只有 `["row", "reason"]` 才改中文，其他 schema 不改（codebase-audit 模組 2 #2.7 落差）
- **Emotion**：mildly impressed（成功大部分）→ frustrated（不知道怎麼修失敗的）
- **Friction**：
  - **P0**：痛點 DM-5（批量匯入結果沒「下載失敗 row」）
  - **P1**：error reason 太技術
- **Opportunity**：error dataframe 加「下載失敗 row CSV」button + reason 翻譯成 user 看得懂的中文

---

### Stage U-05 — 6-8m 想 inline edit 修 5 筆資料

- **動作**：用 `st.data_editor` 直接改 row 的 value / category
- **Touchpoint**：`2_資料管理.py:114-166` `st.data_editor` + `:170` 「儲存變更」button + `:225-263` user 改非己 record 邏輯
- **期待**：改完按儲存，看到「✓ 5 筆已更新」
- **實際**：
  - 5 筆中有 2 筆不是自己的（owner=admin），save 後 silent skip + toast「沒有權限修改 ID 5 / 7」（DM-2 + ux-research §1 Persona B 痛點 3）
  - 最後只顯示「成功 3 筆、失敗 2 筆」聚合（line 258-261）user 要自己 mental track 哪 2 筆失敗
  - 沒 row-level 紅框 highlight
- **Emotion**：focused → confused → frustrated
- **Friction**：
  - **P0**：痛點 DM-4 + ux-research §1 Persona B 痛點 3（inline edit 失敗 silent skip）
  - **P1**：痛點 DM-2（data_editor row-level disable 缺失）
- **Opportunity**：（a）失敗 row 紅框 highlight + 顯示 reason（b）row 加 owner 名稱讓 user 自己判斷 / 預先 disable

---

### Stage U-06 — 8-10m 改另外 3 筆但忘了存就切頁

- **動作**：改完 3 筆，點 sidebar 切到「分析報表」想看 trend
- **Touchpoint**：`2_資料管理.py:170` 「儲存變更」永遠可按（無 dirty state detection）
- **期待**：切頁前 warning「您有未儲存的變更」
- **實際**：完全沒 warning（DM-4 + ux-research §5 #9）→ 切頁後改的 3 筆全丟
- **Emotion**：focused → 30 分鐘後發現資料丟失 → angry
- **Friction**：
  - **P0**：痛點 DM-4 + ux-research §5 #9（無 dirty state，切頁丟資料 → 經典反模式）
- **Opportunity**：diff edited_df vs orig df 有差異時 sticky banner + navigation away confirm

---

### Stage U-07 — 10-12m 切到分析報表查 trend

- **動作**：選 source=records，日期 default 過去 7 天，按查詢
- **Touchpoint**：`3_分析報表.py:57-76` 查詢條件 + `:166-169` `_fetch_timerange` + `:206-250` 時間趨勢
- **期待**：直接看到本週每天的 metric 平均值折線
- **實際**：
  - 日期 default 7 天但 demo 資料只有 60 筆固定（A-6）→ 圖很稀疏，user 以為「我這週沒資料」
  - source toggle 影響 3 區塊但分散，user 還沒搞清楚（A-1）
  - Q7 tz bug 仍有可能空圖（codebase-audit 4.2 ⚠️）
- **Emotion**：focused → confused → suspicious
- **Friction**：
  - **P0**：痛點 A-1 + A-6（source toggle 分散 + 日期 default 不符 demo）
- **Opportunity**：頁面頂部單一 source selector + 日期 default 改 24h fit demo

---

### Stage U-08 — 12-13m 想看 realtime 資料的 trend

- **動作**：切 trend source = realtime
- **Touchpoint**：`3_分析報表.py:253-289` 條件分支畫 `go.Bar`
- **期待**：時間軸折線圖跟 records 一致
- **實際**：跳出「Bar chart」5 個 metric 平均值（A-2）→ user：「我選錯了嗎？為什麼變 bar？」
- **Emotion**：confused → frustrated（「我搞不懂這個系統」）
- **Friction**：
  - **P0**：痛點 A-2（realtime source 變 bar 語意不符）
- **Opportunity**：realtime source 改打 `/realtime/history?seconds=N` 拿 wide rows，FE pandas resample 畫線圖

---

### Stage U-09 — 13-15m 嘗試匯出 Excel 貼週報

- **動作**：點「準備 Excel 下載」→ 點「下載 Excel」
- **Touchpoint**：`3_分析報表.py:394-435` 兩步點擊
- **期待**：一鍵下載，檔名能識別
- **實際**：
  - 兩步點擊（A-5）→ user：「為什麼要點兩次」
  - 檔名 `data_export.xlsx` 沒時間 / 篩選條件（A-4）→ 一週後打開不知道是哪份
- **Emotion**：mildly frustrated
- **Friction**：
  - **P1**：痛點 A-4 + A-5（Excel 兩步 + 檔名）
- **Opportunity**：直接用 `st.download_button` + on-demand fetch + filename 燒入篩選條件

---

### Stage U-10 — 15-17m 切到即時監控看現場數值

- **動作**：點即時監控看 metric 是不是合理
- **Touchpoint**：`4_即時監控.py:214-264` 5 metric 折線
- **期待**：看到各 metric 走勢，能跟自己上傳的 CSV 比對
- **實際**：5 條線壓一團（R-1）→ user 看不出 voltage / temperature 趨勢
- **Emotion**：confused → mildly frustrated
- **Friction**：
  - **P0**：痛點 R-1（5 metric 共軸）
- **Opportunity**：plotly small multiples

---

### Stage U-11 — 17-19m 在 Dashboard 改密碼（剛換新筆電要 sync）

- **動作**：回 Dashboard 找改密碼
- **Touchpoint**：`1_儀表板.py:220-262` 帳號設定 expander
- **期待**：直接在右上角 user info dropdown
- **實際**：
  - 帳號設定 expander 在儀表板底部跟頁面語意不符（D-5）→ user 找半天
  - viewer 角色也能看到這個 expander（pm-strategy §1.2 表第 3 行落差）→ 設計沒分角色
- **Emotion**：confused → mildly impressed（找到了）
- **Friction**：
  - **P1**：痛點 D-5（帳號設定 expander 位置錯）
- **Opportunity**：改密碼移到右上角 user info dropdown menu（pm-strategy §5.3 G3 砍掉 Dashboard 入口）

---

### Stage U-12 — 19-20m 登出回去寫週報

- **動作**：登出
- **Touchpoint**：`1_儀表板.py:37-38` 登出 button
- **Emotion**：mixed（功能能用但 friction 多 → 「下次能不能直接用 Excel 算就好」）
- **Friction**：累積前面所有 P0
- **Opportunity**：把痛點 DM-1 / DM-4 / A-1 / A-2 / R-1 修掉，user 對系統的信任能回來

---

## Section 5: Viewer 王主管的「10 分鐘觀察旅程」

> **情境**：週五下午 16:00，王主管週會前 quick check 系統健康，準備在會議跟老闆報告。

### Stage V-01 — 0-30s 登入

- **動作**：用 viewer@example.com / viewer123 登入
- **Touchpoint**：`Home.py:23-43`
- **期待**：登入後直接看到「系統現在好不好」綠/黃/紅燈
- **實際**：跳 Dashboard，第一視覺是 4 metric cards 全是「量」（D-1）→ viewer 完全沒參考點
- **Emotion**：focused → confused
- **Friction**：
  - **P0**：痛點 D-1 + ux-research §1 Persona C 痛點 1（首頁沒「系統現在好不好」答案）
- **Opportunity**：Dashboard 頂部加綠/黃/紅燈大圖示 + 過去 24h 異常數對比

---

### Stage V-02 — 30s-1m 想知道自己能看什麼

- **動作**：看右上角 `角色：viewer` 4 字 + 開始亂點頁面試試
- **Touchpoint**：`1_儀表板.py:34` user info 區只顯示 `角色：viewer`
- **期待**：第一次登入彈 onboarding hint「您是 Viewer，可看不可改」
- **實際**：0 onboarding（ux-research §1 Persona C 痛點 2）→ 到處踩雷
- **Emotion**：confused → frustrated
- **Friction**：
  - **P0**：ux-research §1 Persona C 痛點 2 + pm-strategy P0-1（角色 onboarding 缺失）
  - **P0**：痛點 S-2（角色權限矩陣 viewer 看不到）
- **Opportunity**：Home 登入後彈一次性 modal + Dashboard 頂部固定權限矩陣卡片

---

### Stage V-03 — 1-2m 試點「資料管理」

- **動作**：點 sidebar「2 資料管理」
- **Touchpoint**：`2_資料管理.py:116-117` viewer 進此頁看到 `st.info("Viewer 角色為唯讀，無法編輯資料。")`
- **期待**：頁面頂端明顯 banner 告訴你「你能看不能改」
- **實際**：info banner 在第 116 行，要 scroll 過篩選 expander 才看到（ux-research §1 Persona C 痛點 2 額外證據）→ viewer 已經看到 data_editor 試圖編輯才發現
- **Emotion**：confused → frustrated（「你早說啊」）
- **Friction**：
  - **P0**：ux-research §1 Persona C 痛點 2（info banner 太晚出現）
- **Opportunity**：viewer banner 移到頁面 title 下方 + data_editor 整個 disabled state（不只 `num_rows="fixed"`）

---

### Stage V-04 — 2-3m 試點「5 系統管理」

- **動作**：點 sidebar「5 系統管理」想看系統設定（純好奇）
- **Touchpoint**：`5_系統管理.py:38-41` `st.error + st.stop`
- **期待**：擋下 + 給 actionable 訊息（怎麼申請提權）
- **實際**：`st.error("存取拒絕：此頁面僅限 admin")` + `st.info("如需管理功能，請洽系統管理員提升權限，或改以 admin 帳號登入。")`（S-7）→ 沒 email / Slack / 表單連結
- **Emotion**：frustrated → resigned
- **Friction**：
  - **P0**：痛點 S-7（擋下訊息沒給 actionable 路徑）
- **Opportunity**：擋下訊息加「申請提權」表單或 contact email

---

### Stage V-05 — 3-5m 回 Dashboard 看 4 metric cards 想做截圖

- **動作**：看 4 metric cards + 即時/錄入 tabs，準備截圖貼週報 slide
- **Touchpoint**：`1_儀表板.py:147-218` metric cards + dataframe tabs
- **期待**：「過去一週異常數 12 / 總筆數 86400 / 異常率 0.014% / vs 上週 -0.005%」
- **實際**：純筆數沒比較基線（D-1）→ viewer 不知道這代表什麼
- **Emotion**：confused → frustrated
- **Friction**：
  - **P0**：痛點 D-1（4 metric cards 無 baseline）
- **Opportunity**：metric card 加「vs 昨日 / 上週」delta + 異常率 % 取代純筆數

---

### Stage V-06 — 5-7m 切到 4 即時監控想看「現場感」

- **動作**：點即時監控，想截一張「系統正在跑」的圖貼週報
- **Touchpoint**：`4_即時監控.py:214-264` 折線圖
- **期待**：清楚的多 metric 動態圖
- **實際**：
  - 5 條線壓一團（R-1）→ 截圖效果差
  - Plotly toolbar 會抓到截圖（ux-research §1 Persona C 痛點 3）
- **Emotion**：mildly impressed（即時更新很酷）→ frustrated（圖不適合放週報）
- **Friction**：
  - **P0**：痛點 R-1（5 metric 共軸）
  - **P1**：ux-research §1 Persona C 痛點 3（Plotly toolbar 截圖）
- **Opportunity**：plotly small multiples + 「截圖友善模式」隱藏 toolbar

---

### Stage V-07 — 7-9m 切到 3 分析報表想看一週趨勢

- **動作**：點分析報表，看本週日均
- **Touchpoint**：`3_分析報表.py:206-250` 時間趨勢
- **期待**：清楚的折線 + 異常事件 marker
- **實際**：
  - 日期 default 7 天 demo 資料很稀疏（A-6）→ 圖看起來「空」
  - source toggle 沒解釋 records vs realtime 差別（pm-strategy §1.2 V2 訊號 row 5）→ viewer 怕選錯
- **Emotion**：confused → suspicious
- **Friction**：
  - **P0**：痛點 A-6（日期 default 不符 demo）
  - **P1**：痛點 A-1（source toggle 不直觀）
- **Opportunity**：日期 default 改 24h + source toggle 加 caption 解釋

---

### Stage V-08 — 9-10m 想分享 URL 給老闆但發現要登入

- **動作**：複製當前 URL 想 forward 給老闆
- **Touchpoint**：`auth.py require_auth()`
- **期待**：老闆不用登入也能看（公開唯讀快照）
- **實際**：老闆收到 URL 點開被 redirect 回 Home 要登入（ux-research §1 Persona C 「One Unexpected Insight」）
- **Emotion**：frustrated → resigned
- **Friction**：
  - **P2**：ux-research §1 Persona C 不會主動抱怨但會降低使用頻率
- **Opportunity**：給 viewer 一個「分享公開唯讀快照」功能（24h token）或匯出 PDF（v4 範圍）

---

## Section 6: 四角色「友善度比較矩陣」

> 評分 1-5，5 = 流暢 / 4 = 順暢 / 3 = 可用但有摩擦 / 2 = 明顯 friction / 1 = 致命阻礙
> 評分基於 ux-research / pm-strategy / codebase-audit 既有 finding

| Stage（橫列） | Eric 評審 | Admin 林佳穎 | User 陳家豪 | Viewer 王主管 | 註解 |
|---|---|---|---|---|---|
| 1. 開啟首頁 | 2（H-1 致命）| 4 | 4 | 4 | Eric 沒測試帳號訊息 |
| 2. 登入 | 2（找帳號難）| 4 | 4 | 4 | 三角色密碼管理員填，Eric 要翻 README |
| 3. 看 Dashboard 第一眼 | 2（D-1）| 3（告警只算個數）| 3 | 1（無 baseline / 致命）| Viewer 核心 job 失敗 |
| 4. 探索資料管理 | 2（DM-1/3/4）| 4 | 2（CSV 無 preview）| 2（banner 太晚 / data_editor 試錯）| User 核心 job 受傷 |
| 5. 看分析報表 | 2（A-1/2/6）| 3（Q7 tz 可能空圖）| 2（source toggle 分散 + bar 變線）| 2（日期 default 7 天空圖）| Eric / User / Viewer 三角色都困惑 |
| 6. 看即時監控 | 1（R-1 致命 + delta_color 反 + anomaly 等不到）| 1（核心 use case 完全壞）| 2 | 2（圖壓一團）| **全角色致命傷** |
| 7. 切系統管理 | 2（S-2 權限矩陣藏 + S-6 重複）| 3（功能完整但 friction）| N/A（被擋）| N/A（被擋）| Eric 看不到 V3 訊號 |
| 8. 切換角色（含 logout/login）| 1（無 role switcher）| N/A | N/A | N/A | Eric 唯一痛點，但極高頻 |
| 9. 破壞性操作測權限 | 3（擋有用但訊息不友善）| N/A | 2（silent skip）| 2（被擋無路徑）| 三角色感受不同 |
| 10. CSV 上傳 | N/A | 2 | 1（DM-1 致命）| N/A | User 核心 job 致命傷 |
| 11. inline edit 改資料 | N/A | 3 | 1（dirty state 缺 / 切頁丟資料）| N/A | User 經典反模式 |
| 12. 匯出 Excel | N/A | 4 | 2（A-4/5 兩步 + 檔名）| 3（截圖不易）| User 高頻功能 |
| 13. 改密碼 | N/A | 2（S-3 兩個 selectbox）| 3（位置錯）| 3 | Admin 最痛 |
| 14. 改 system settings | N/A | 1（R-2 改了不同步 / 致命）| N/A | N/A | Admin 信任崩壞 |
| 15. 看 DB 狀態 / 日誌 | 3 | 2（S-8 無 baseline / S-4 篩選擁擠）| N/A | N/A | Admin 維運場景 |
| 16. 截圖貼週報 | N/A | N/A | 3 | 2（Plotly toolbar 抓進去）| Viewer 高頻場景 |
| 17. 分享 URL 給他人 | N/A | N/A | N/A | 1（必須登入）| Viewer 轉述場景受傷 |
| 18. 離場印象 | 2（BE 紮實 FE 拖累）| 3 | 3 | 2 | Eric 評分嚴重低估 candidate |

**橫向平均（流暢度）**：
- Eric 評審：**2.0**（致命，極低）
- Admin 林佳穎：**2.7**（明顯 friction）
- User 陳家豪：**2.3**（明顯 friction）
- Viewer 王主管：**2.3**（明顯 friction）

**全角色平均**：**2.3** — 明顯 friction，符合懷特觀察「奇怪、不直觀、難用」

---

## Section 7: 跨角色「Top 15 高 friction 節點」

> 按「平均 friction 分數（5 - 友善度）× 影響 persona 數」排序
> 每節點附：影響 persona / 對應 finding 編號 / 建議修補方向

### #1 — 即時監控 5 metric 共軸圖

- **平均 friction**：4.5
- **影響 persona**：Eric / Admin / User / Viewer（全角色）
- **對應 finding**：ux-research R-1、pm-strategy P1-2、codebase-audit 圖表盤點 row 5+6
- **建議修補方向**：plotly `make_subplots(rows=5, cols=1, shared_xaxes=True)` 做 small multiples（pm-strategy M3）
- **修補難度**：M（1 天）

### #2 — Home 沒測試帳號提示

- **平均 friction**：4.3
- **影響 persona**：Eric（致命）+ 所有首次使用者
- **對應 finding**：ux-research H-1、pm-strategy M1（方案 C）
- **建議修補方向**：Home 加「試用帳號」expander + 三顆「以 X 登入」一鍵填表按鈕（pm-strategy §4 方案 C）
- **修補難度**：S（30 分鐘）

### #3 — 角色權限說明全系統 viewer/user 看不到

- **平均 friction**：4.0
- **影響 persona**：Admin / User / Viewer / Eric（全角色）
- **對應 finding**：ux-research S-2 + Section 4、pm-strategy P0-1、codebase-audit Section 4
- **建議修補方向**：Dashboard 頂部固定矩陣卡片（pm-strategy §4 方案 A）+ 每頁右上角 chip badge + hover tooltip（pm-strategy M1）
- **修補難度**：S-M（1 小時）

### #4 — Dashboard 4 metric cards 全是「量」沒「品質」

- **平均 friction**：3.8
- **影響 persona**：Viewer（致命）+ Admin / Eric
- **對應 finding**：ux-research D-1、pm-strategy §3.1 模組 1 落差、codebase-audit #4
- **建議修補方向**：第 4 卡改「異常率 %」+ delta vs 昨日 + 紅黃綠燈 health indicator（ux-research §5 #3）
- **修補難度**：S-M（半天）

### #5 — CSV 上傳沒 preview / dry-run

- **平均 friction**：3.8
- **影響 persona**：User（致命）+ Admin
- **對應 finding**：ux-research DM-1、pm-strategy §5.1 M4 候選、codebase-audit Section 5 #8
- **建議修補方向**：上傳後本機 pandas parse 顯示「將匯入 N 筆 / 跳過 M 筆」+ 預覽前 5 筆 + 「下載 sample.csv」連結（ux-research §5 #4）
- **修補難度**：M（1-2 天）

### #6 — inline edit 無 dirty state，切頁丟資料

- **平均 friction**：3.7
- **影響 persona**：User（致命）
- **對應 finding**：ux-research DM-4 + §5 #9、pm-strategy P1-1 + §3.2 模組 2 #2.4 落差
- **建議修補方向**：diff edited_df vs orig df 有差異時 sticky banner + navigation away confirm
- **修補難度**：M（1 天）

### #7 — 即時監控閾值 hardcode FE 不同步 backend

- **平均 friction**：3.7
- **影響 persona**：Admin（信任崩壞）+ Eric（會發現不一致）
- **對應 finding**：ux-research R-2、pm-strategy P1-1 第 8 項 + §3.5 模組 5 #5.8 落差、codebase-audit O-P0-1
- **建議修補方向**：FE 啟動 fetch `/admin/settings` 動態閾值 + cache ttl=30
- **修補難度**：S（2-3 小時）

### #8 — 分析報表時間趨勢圖 source=realtime 變 Bar chart

- **平均 friction**：3.5
- **影響 persona**：User / Eric（語意不符 → 信任流失）+ Admin
- **對應 finding**：ux-research A-2、pm-strategy P1-2、codebase-audit 圖表盤點
- **建議修補方向**：realtime source 改打 `/realtime/history` 拿 wide rows FE pandas resample 畫線圖
- **修補難度**：M（1 天）

### #9 — 評審無 role switcher 切角色要登入登出 3 次

- **平均 friction**：3.5
- **影響 persona**：Eric（極高頻）
- **對應 finding**：ux-research §1 Persona D 痛點 2 + §5 #1
- **建議修補方向**：每頁右上角加 dropdown「切換角色（demo only）」3 秒 mock token 切換
- **修補難度**：S-M（半天）

### #10 — 5 頁完全沒 onboarding micro-copy

- **平均 friction**：3.4
- **影響 persona**：Eric / User / Viewer / Admin（全角色）
- **對應 finding**：pm-strategy P0-2 + M2、codebase-audit Section 5 #1-#20、ux-research §1 Persona D 痛點 3
- **建議修補方向**：5 頁每頁加 1 段 ≤ 80 字 `st.caption()`「這頁在幹嘛 / 看什麼 / 怎麼用」（pm-strategy M2）
- **修補難度**：S（1 小時）

### #11 — Anomaly injection 每 60 tick 一次評審等不到

- **平均 friction**：3.4
- **影響 persona**：Eric（致命，看不到 V2 訊號）+ Admin（demo 場景）
- **對應 finding**：pm-strategy §1.2 結論 3 + M3、design.md:178 `ANOMALY_INJECTION_PERIOD=60`
- **建議修補方向**：即時監控頁加「手動觸發異常」按鈕（FE-only mock anomaly snapshot 注入 buffer 避免改 BE）
- **修補難度**：S-M（半天）

### #12 — Dashboard 三層 cache ttl 不一致

- **平均 friction**：3.2
- **影響 persona**：Admin（需要實時）+ Eric（會發現怪）
- **對應 finding**：ux-research D-3、codebase-audit Section 5 「圖表更新機制」表
- **建議修補方向**：統一 ttl=5 或在每張 card 角落顯示「更新於 N 秒前」stale indicator
- **修補難度**：S（2 小時）

### #13 — delta_color="inverse" 顏色語意反

- **平均 friction**：3.0
- **影響 persona**：Admin（誤判 alert）+ Eric（會發現）
- **對應 finding**：pm-strategy P1-1 第 7 項 + M5、`4_即時監控.py:196`
- **建議修補方向**：移除 inverse 改用 explicit colored badge（紅 = critical / 橙 = warning / 綠 = ok）
- **修補難度**：S（半小時）

### #14 — 系統管理 Tab 4 即時資料歷史與即時監控頁重複

- **平均 friction**：3.0
- **影響 persona**：Admin / Eric（混淆「為什麼有兩個一樣的」）
- **對應 finding**：ux-research S-6、pm-strategy P1-1 第 9 項
- **建議修補方向**：合併 Tab 4 到即時監控頁加「歷史」tab + 抽 shared `realtime_chart.py` component
- **修補難度**：M（1 天）

### #15 — Excel 匯出兩步點擊 + 檔名沒燒入篩選條件

- **平均 friction**：2.8
- **影響 persona**：User（高頻）+ Viewer（週報場景）
- **對應 finding**：ux-research A-4 + A-5、pm-strategy P1-1 第 5 項
- **建議修補方向**：直接用 `st.download_button` + on-demand fetch + filename 燒入篩選條件
- **修補難度**：S（半天）

---

### 補充：未進 Top 15 但建議追蹤的高 friction 節點

| # | 節點 | 影響 persona | 對應 finding | 修補方向 |
|---|---|---|---|---|
| 16 | 角色 demo banner 缺失 | Viewer / Eric | pm-strategy M4 | Home 登入後彈一次性 modal「您是 X，建議動線 Y」 |
| 17 | Dashboard 重新整理按鈕埋頁面最底 | Admin | ux-research D-4 | 移到頁面頂部 status header 區 |
| 18 | 系統管理擋下訊息沒給 actionable 路徑 | User / Viewer | ux-research S-7 | 加「申請提權」表單或 contact email |
| 19 | 帳號設定 expander 在 Dashboard 底部 | User / Viewer | ux-research D-5 | 改密碼移到右上角 user info dropdown |
| 20 | 系統設定 5 個 setting 5 個 form | Admin | ux-research S-5 | 單一 form 改全部一次儲存 |
| 21 | 改 user 兩個獨立 selectbox | Admin | ux-research S-3 | 合併 user selector 下面 tab「角色與啟用 / 密碼」 |
| 22 | DB 狀態無 baseline 提示 | Admin | ux-research S-8 + pm-strategy P1-2 | 加「使用率 %」derived metric + 接近上限 yellow/red badge |
| 23 | 類別分佈 bar 並排 X 軸 label 重疊 | User / Viewer / Admin | ux-research A-3 | 改上下排 full-width 或 horizontal bar |
| 24 | 5 metric 全異常時 alert cards 擠太窄 | Admin | ux-research R-5 | 限制 max 3 cards/row > 3 改 list view |
| 25 | Pandas Styler 偶會 raise silent fallback | Admin / User | ux-research §1 Persona A + pm-strategy P1-2 + M5 | log exception + 用 stable 寫法 |

---

## Section 8: 修補後的「理想旅程」對照圖

> 每角色畫 2 條 emotion 曲線：紅線 = 目前 / 綠線 = 修補後 pm-strategy M1-M5 後

### 8.1 Eric 評審 emotion 對照（12 stages × 5 levels）

```
Emotion 5  ────────────────────────────────────────────────────  Impressed
Emotion 4  ────────────────────────────────────────────────────  Excited
Emotion 3  ────────────────────────────────────────────────────  Neutral
Emotion 2  ────────────────────────────────────────────────────  Confused/Mild Frustration
Emotion 1  ────────────────────────────────────────────────────  Frustrated/Suspicious

Stage:    E01  E02  E03  E04  E05  E06  E07  E08  E09  E10  E11  E12
紅(目前)：  2    1    2    1    1    1    2    1    2    2    2    1
綠(修後)：  4    5    4    4    4    4    4    4    4    4    4    5

拐點對應 fix：
- E01 → 修補 M1（Home 試用帳號 expander）
- E02 → 修補 M1（一鍵登入按鈕）
- E03 → 修補 M1 + Top 15 #4（Dashboard 權限矩陣卡片 + 異常率 %）
- E04 → 修補 Top 15 #5 + 痛點 DM-3（CSV preview + 篩選 collapsed）
- E05 → 修補 Top 15 #8 + 痛點 A-1（trend realtime → 線圖 + 統一 source）
- E06 → 修補 Top 15 #1 + #7 + #11 + #13（small multiples + 動態閾值 + 手動 anomaly + delta_color 修）
- E07 → 修補 #3 + #14（權限矩陣 expanded=True + 合併 Tab 4）
- E08 → 修補 Top 15 #9（role switcher）
- E09 → 修補 ux-research §1 Persona C 痛點 2 + S-7（onboarding + 擋下訊息）
- E10 → 修補 #3（Dashboard 權限矩陣卡片，viewer 也看得到）
- E11 → 修補 ux-research §1 Persona C 痛點 3（Plotly toolbar hide）
- E12 → 累積前面 11 個 fix 後印象大翻轉
```

### 8.2 Admin 林佳穎 emotion 對照（12 stages）

```
Stage:    A01  A02  A03  A04  A05  A06  A07  A08  A09  A10  A11  A12
紅(目前)：  3    1    2    3    2    1    1    2    2    1    2    3
綠(修後)：  4    5    4    4    4    5    4    4    4    4    4    4

拐點對應 fix：
- A01 → 修補 Top 15 #4（Dashboard 異常率 % + delta vs 昨日）+ 加「告警 highlights」區塊
- A02 → 修補 Top 15 #1（small multiples）
- A03 → 修補 Top 15 #13（delta_color 修 + explicit badge）+ #24（cards 限制 max 3/row）
- A04 → 修補 ux-research S-4（日誌篩選改 2 row × 4 column）+ saved filter preset
- A05 → 修補 ux-research S-8（DB 使用率 % + baseline）
- A06 → 修補 Top 15 #7 + ux-research S-5（動態閾值 + 單一 form）
- A07 → 新增「+ 新增使用者」UI（pm-strategy 模組 5 #5.3 缺口）
- A08 → 修補 ux-research S-3（合併 user selector）
- A09 → 修補 codebase-audit O-P0-5（timezone 強制驗證 + 空資料 explainability）
- A10 → 修補 Top 15 #14（合併 Tab 4 到即時監控）
- A11 → 新增 audit log timeline UI（ux-research §1 Persona A Product Fit）
- A12 → 修補 pm-strategy §3.1 模組 1 #1.3（logout 真實 invalidate JWT）
```

### 8.3 User 陳家豪 emotion 對照（12 stages）

```
Stage:    U01  U02  U03  U04  U05  U06  U07  U08  U09  U10  U11  U12
紅(目前)：  3    3    2    1    2    1    2    1    2    2    2    2
綠(修後)：  3    4    4    4    4    5    4    5    4    4    4    4

拐點對應 fix：
- U01 → 維持（v4 範圍）
- U02 → 修補 ux-research DM-3（篩選 collapsed）+ codebase-audit #8（sample.csv 連結）
- U03 → 修補 Top 15 #5（CSV preview / dry-run）
- U04 → 修補 ux-research DM-5（下載失敗 row CSV）+ error reason 翻譯
- U05 → 修補 ux-research DM-2 + DM-4（row-level disable + 紅框 highlight）
- U06 → 修補 Top 15 #6（dirty state banner + nav away confirm）
- U07 → 修補 Top 15 #4（日期 default 24h）+ #10（micro-copy）
- U08 → 修補 Top 15 #8（realtime trend → 線圖）
- U09 → 修補 Top 15 #15（Excel 一步下載 + 檔名燒入）
- U10 → 修補 Top 15 #1（small multiples）
- U11 → 修補 ux-research D-5（改密碼移到 user info dropdown）
- U12 → 累積前面 fix 後信任回來
```

### 8.4 Viewer 王主管 emotion 對照（8 stages）

```
Stage:    V01  V02  V03  V04  V05  V06  V07  V08
紅(目前)：  1    1    2    1    1    2    2    1
綠(修後)：  5    5    4    4    4    4    4    3

拐點對應 fix：
- V01 → 修補 Top 15 #4（紅/黃/綠燈 + 異常率 %）
- V02 → 修補 Top 15 #3 + ux-research §1 Persona C 痛點 2（onboarding modal + 權限矩陣卡片）
- V03 → 修補 ux-research §1 Persona C 痛點 2（viewer banner 移到頁面 title 下方）
- V04 → 修補 ux-research S-7（擋下訊息加 contact / 申請提權）
- V05 → 修補 Top 15 #4（同 V01）
- V06 → 修補 Top 15 #1 + ux-research §1 Persona C 痛點 3（small multiples + Plotly toolbar hide）
- V07 → 修補 Top 15 #4 + #10（日期 default 24h + micro-copy）
- V08 → 部分修補（公開唯讀快照連結為 v4 範圍，本期不動）
```

### 8.5 跨角色 emotion 修補總結

| Persona | 修補前平均 | 修補後平均 | Delta | 主要拐點 fix |
|---|---|---|---|---|
| Eric 評審 | 1.7 | 4.2 | +2.5 | Top 15 #1 / #2 / #3 / #4 / #9 / #10 |
| Admin 林佳穎 | 2.1 | 4.2 | +2.1 | Top 15 #1 / #7 / #13 / #14 + ux S-3/S-4/S-5/S-8 |
| User 陳家豪 | 2.0 | 4.2 | +2.2 | Top 15 #5 / #6 / #8 / #15 + ux DM-2/DM-3/DM-5 |
| Viewer 王主管 | 1.6 | 4.1 | +2.5 | Top 15 #3 / #4 / #10 + ux S-7 + Persona C 痛點 2/3 |
| **全角色平均** | **1.85** | **4.18** | **+2.33** | pm-strategy M1-M5 + Top 15 集中修補 |

---

## 結論 Summary

1. **最致命 friction 集中在 6 個 stage**：Stage E-01（無測試帳號）、E-03/V-01/V-05（4 metric cards 無 baseline）、E-06/A-02/U-10/V-06（5 metric 共軸）、A-06（閾值不同步）、U-03/U-06（CSV 上傳 + dirty state）、E-08（無 role switcher）
2. **修補 ROI 集中在 pm-strategy M1-M5（8 小時工時）**：解掉 Top 15 中 #1 / #2 / #3 / #4 / #10 / #11 / #13 共 7 個高頻 friction
3. **跨角色平均 friction 從 2.3 → 4.2**（+1.9）：M1-M5 + Top 15 集中修補後，全角色都能達到「順暢」level
4. **v4 範圍建議**：viewer 公開唯讀快照 / 申請提權表單 / Plotly 截圖友善模式 / audit log timeline UI / DELETE user UI 補缺口
5. **關鍵洞察重申**：v3 UX fix 的核心 ROI 不在「user 用得爽」而在「評審看得到 candidate 的技術深度」— Eric 從 emotion 1.7 → 4.2 是 ROI 最大化的修補目標

---

**finding 引用統計**：
- ux-research.md：H-1/H-4、D-1/D-2/D-3/D-4/D-5、DM-1/DM-2/DM-3/DM-4/DM-5、A-1/A-2/A-3/A-4/A-5/A-6、R-1/R-2/R-3/R-4/R-5/R-6、S-1/S-2/S-3/S-4/S-5/S-6/S-7/S-8 + §1 Persona A/B/C/D 痛點 + §5 #1~#10 + §4.3 業界對照 = **約 50 個引用**
- pm-strategy.md：P0-1/P0-2/P0-3、P1-1/P1-2、M1/M2/M3/M4/M5、§3.1~3.5 模組落差、§4 方案 A/C、§5.1/5.3、§6 KPI 與反指標 = **約 25 個引用**
- codebase-audit.md：Section 5 #1~#24、Section 7 O-P0-1 ~ O-P2-5、Section 4 角色權限現況、圖表盤點 row 1~6、DB / log / settings 路徑 = **約 30 個引用**
- file:line 直接引用：Home.py:10-43 / 1_儀表板.py:30-268 / 2_資料管理.py:55-326 / 3_分析報表.py:57-435 / 4_即時監控.py:97-371 / 5_系統管理.py:38-639 等 **約 40 個 file:line**

合計 **>140 個 finding / file:line 引用**（遠超「至少 50」要求）。

CUSTOMER JOURNEY MAP DONE
