# Validation Checklist — Redesign v3 UX Fix（Wiwynn 即時資料分析與監控系統）

**Date**：2026-05-26
**Owner**：qa-validation-specialist sub-agent（v6.1 Mode A 加強版 Phase F.5）
**讀過的證據**：design.md（870 行）/ user-stories.md（559 行）/ codebase-audit.md（404 行）/ README.md（266 行）/ report_round1_fixes.md / spike-results.md（630 行）
**驗證方式**：main session 用 Chrome MCP 三角色（admin / user / viewer）實機操作；fail 即進修正閉環直到 100% 綠
**Sprint 已完成**：Story #1-#8 + #10 + #11（commit cf22579 → 19155f3 → 2084be8 → 8c0eea7 全部部署）；Story #9 + #12 待驗（P1/P2）

**Frontend URL（Zeabur prod）**：`https://wiwynn-test-real-time-data-analysis-and-monitoring-system.zeabur.app`
**Backend URL（Zeabur prod）**：`https://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app`
**測試帳號**（README.md:66-75）：
- admin@example.com / admin123
- user@example.com / user123
- viewer@example.com / viewer123

---

## 共用導引

每條 checklist 條目格式：

```
- [ ] <ID> | <角色> | <URL/頁面> | <操作> | <預期 yes/no 結果> | <Story / file:line 證據>
```

驗收方式：
- [ ] = 未驗（main session Chrome MCP 操作後改 [x]）
- [x] = 已驗綠
- [F] = 已驗紅（同行加 ※ fail 描述）

---

## Section 1：模組 1 — 使用者管理（12 條）

對應需求文檔 §1.1-1.6（codebase-audit.md Section 3 模組 1，6 條），補 Story #1/#2/#11 FE UI 條件。

- [ ] M1-01 | 未登入訪客 | `/` (Home) | 打開頁面，看登入 tab 上方 | 「試用帳號（Demo 用）」expander 預設展開（`expanded=True`），列出 Admin/User/Viewer 三組 email + 密碼明文 | Story #1 AC-1 / design.md:150-156 / Home.py:23 之前
- [ ] M1-02 | 未登入訪客 | `/` (Home) | 點「以 Admin 登入」按鈕 | URL 變 `?auto_login=admin` 後自動跳轉到儀表板（zero-click，spike Plan B）；右上角顯示「admin」 | Story #1 AC-2 / spike-results.md §1.4 Plan B / Home.py:16 之前
- [ ] M1-03 | 未登入訪客 | `/` (Home) | 點「以 User 登入」按鈕 | URL 變 `?auto_login=user` 後跳轉到儀表板；右上角顯示「user」 | Story #1 AC-2/3 變體
- [ ] M1-04 | 未登入訪客 | `/` (Home) | 點「以 Viewer 登入」按鈕 | URL 變 `?auto_login=viewer` 後跳轉到儀表板；右上角顯示「viewer」 | Story #1 AC-3 / user-stories.md:44
- [ ] M1-05 | 未登入訪客 | `/` (Home) | 切換到「註冊」tab | 「試用帳號」expander 不出現在註冊 tab 區塊內，註冊 form 4 個 input 正常 | Story #1 AC-5 / Home.py:51-64
- [ ] M1-06 | admin | `/5_系統管理` Tab 1 | 點某 user row → 改角色 selectbox → 按「儲存」 | PATCH `/users/{id}` 200 OK + Audit log 新增 `action="update_user_role"` 一筆 + user 列表角色欄反映新值 | 模組 5 #5.2 / users.py:68-91 / 5_系統管理.py:191
- [ ] M1-07 | admin | `/5_系統管理` Tab 1 | 選一個 viewer user → 點「刪除選定使用者」按鈕（需先勾「確認刪除」checkbox） | DELETE `/users/{id}` 204 + `st.success("已刪除使用者 {email}")` + user 從列表消失 + cache_clear | Story #11 AC-3 / design.md:659 / users.py:93-106
- [ ] M1-08 | admin | `/5_系統管理` Tab 1 | 觀察「刪除選定使用者」selectbox 選項 | 自己的 user_id 不出現在 selectbox 中（或 disabled）+ 旁邊有 warning 文字 | Story #11 AC-3 Edge Case / user-stories.md:375
- [ ] M1-09 | user / viewer | `/5_系統管理` | 直接打開系統管理頁 URL | 顯示 `st.error("僅 Admin 可存取此頁")` + `st.stop()` 後續內容不渲染 | 模組 5 #5.9 / 5_系統管理.py:38-41
- [ ] M1-10 | admin / user / viewer | `/1_儀表板` | 登入後進入儀表板 | 頁面標題下方第一個 container（border=True）渲染角色權限矩陣 13 操作 × 3 角色 markdown table，當前角色欄用 `**✓**` bold 標記 | Story #2 AC-1/2/3 / design.md:184-216 / auth.py:91+ + 1_儀表板.py:41 之後
- [ ] M1-11 | admin | `/1_儀表板` | 看角色矩陣卡片頂部文字 | 「您目前的角色：Admin（系統管理員）」字串可見 | Story #2 AC-2 / design.md:192
- [ ] M1-12 | user | `/1_儀表板` → 帳號設定 expander | 改自己密碼 form 填 new + confirm → 送出 | PATCH `/users/{id}/password` 200 OK，不需 old_password；同流程 admin 改他人密碼也成功 | 模組 1 #1.6 / users.py:108+ / 1_儀表板.py:249-262

---

## Section 2：模組 2 — 資料管理（13 條）

對應需求文檔 §2.1-2.8（codebase-audit.md 模組 2，8 條），補 Story #3 caption 與 v2 已存在功能 regression。

- [ ] M2-01 | user | `/2_資料管理` | inline 編輯自己 owned row（改 title 或 value）→ 按「儲存變更」 | PATCH `/data/{id}` 200 + toast「已儲存 N 筆變更」+ dataframe 更新 | 模組 2 #2.4 / data.py:143-165 / 2_資料管理.py:249
- [ ] M2-02 | viewer | `/2_資料管理` | 開啟 data_editor 嘗試點任一 cell | 全欄位 disabled（readonly），cell 不可編輯 + 無「儲存變更」按鈕（或 disabled） | 模組 2 #2.7 / 2_資料管理.py:146-148
- [ ] M2-03 | user | `/2_資料管理` | 嘗試編輯**他人** owned row（owner_id != current_user_id）→ 按儲存 | silent skip + `st.toast` 提示「無權限編輯他人資料」，BE 不被打 PATCH | 模組 2 #2.8 / 2_資料管理.py:226
- [ ] M2-04 | admin | `/2_資料管理` | 編輯任何 owner 的 row → 儲存 | PATCH 200 OK + `@st.cache_data.clear()` + dataframe rerun 顯示新值 | 模組 2 #2.4 admin override / data.py:143-165
- [ ] M2-05 | user | `/2_資料管理` 批量匯入 | 上傳 `docs/sample_data.csv`（60 row） | POST `/data/bulk-import` 200，response 顯示 `inserted=N, errors=[]`（無 error 場景）或 `inserted<60, errors=[逐行]` | 模組 2 #2.6 / data.py:74-117 / 2_資料管理.py:295
- [ ] M2-06 | user | `/2_資料管理` 批量匯入 | 上傳故意壞掉的 CSV（10 row invalid value 非 float） | response 顯示 inserted=50 + errors 陣列 10 筆，每筆有 row_number + message（中文錯誤）；error dataframe 渲染 | 模組 2 #2.6 + 4.7 / utils/csv_importer.py / 2_資料管理.py:307-314
- [ ] M2-07 | user / admin | `/2_資料管理` | 觀察頁面頂部「篩選條件」expander | `expanded=True` 預設展開 + 6 個 input（含 search、category、date_input × 2、time_input × 2 等） | codebase-audit.md Section 1 頁面 3 / 2_資料管理.py:55-67
- [ ] M2-08 | viewer / user / admin | `/2_資料管理` | 看頁面標題下方 | `st.caption` 出現「管理錄入資料：可篩選、分頁、直接點格子編輯（admin / user），或於下方批量匯入 CSV / JSON。Viewer 為唯讀。」 | Story #3 AC-2 / design.md:227 / 2_資料管理.py:52 之前
- [ ] M2-09 | user / admin | `/2_資料管理` 篩選 | 改 date_input + time_input 後送出 | datetime 組合送 BE GET /data + date_from / date_to 篩選正確（不再用 st.datetime_input） | round 1 D-BLOCK-1 regression / 2_資料管理.py + ws_client D-BLOCK-1
- [ ] M2-10 | user | `/2_資料管理` | 新增一筆資料（data_editor 最末加 row）→ 儲存 | POST `/data` 201，owner_id 自動帶 current_user，新 row 出現在 dataframe | 模組 2 #2.1 / data.py:119-128 / 2_資料管理.py:211
- [ ] M2-11 | user | `/2_資料管理` | 刪除自己的 row（data_editor 勾 delete） → 儲存 | DELETE `/data/{id}` 204 + dataframe row 消失 | 模組 2 #2.5 / 2_資料管理.py:189
- [ ] M2-12 | admin | `/2_資料管理` | 刪除他人 owned row | DELETE 200（admin override）+ row 消失 + audit log 一筆 | 模組 2 #2.5 admin override
- [ ] M2-13 | user / admin | `/2_資料管理` | 觀察分頁控制（line 69-73）+ 排序 column header | 分頁按鈕 prev/next 正常 + 點欄位 header 觸發 sort（GET /data?sort=...） | 模組 2 #2.2 / data.py:32-72 / 2_資料管理.py:69-73

---

## Section 3：模組 3 — 即時監控（18 條）

對應需求文檔 §3.1-3.9（codebase-audit.md 模組 3，9 條），補 Story #4/#5/#6/#8/#10。

- [ ] M3-01 | admin / user / viewer | `/4_即時監控` | 三角色分別打開頁面 | 不被 admin gate 擋（不顯示 `st.error("僅 Admin 可存取此頁")`），頁面正常渲染 | 模組 3 #3.8 / 4_即時監控.py:9 註釋 / round 1 D-BLOCK-2
- [ ] M3-02 | admin | `/4_即時監控` | 頁面 render 後等 2-3 秒 | 系統狀態 header 顯示「●（綠）連線中」+ 連線時間戳更新 | round 1 D-BLOCK-2 / 4_即時監控.py:97-107 + 132-144
- [ ] M3-03 | admin | `/4_即時監控` | 觀察「自動刷新次數 / 緩衝區筆數」caption（頁面最底）| 數字每秒 +1（autorefresh 1000ms），buffer 累積到 60 後維持 60 | 模組 3 #3.7 / 4_即時監控.py:110 + 370
- [ ] M3-04 | admin | `/4_即時監控` | 觀察告警卡上方 caption | 「閾值來源：動態（high=X, low=Y，30 秒 TTL cache）」**或** `fetch_dynamic_thresholds()` 200 路徑下文字反映 | Story #5 AC-1/2 / design.md:325-358 / 4_即時監控.py:55-69 + 184-189
- [ ] M3-05 | viewer / user | `/4_即時監控` | 觀察告警卡上方 caption | 「閾值顯示為預設值（唯讀，僅 Admin 可在系統管理頁調整）」**或** 等價提示（VA-9 viewer/user 403 → fallback path） | Story #5 AC-3 / design.md:356 / spike VA-9
- [ ] M3-06 | admin / user / viewer | `/4_即時監控` Demo 控制區 | 三角色都看到「Demo 控制」container + 「觸發一次模擬異常」按鈕 | 按鈕可點（非 disabled），無 admin 守衛 | Story #4 AC-1 / design.md:248-263
- [ ] M3-07 | viewer | `/4_即時監控` | 點「觸發一次模擬異常」 | 下一次 autorefresh（≤ 1 秒）buffer 多一筆 mock anomaly（`source="mock"` + `temperature=150.0` + `cpu_usage=95.0` + `anomaly_flags.temperature=True, cpu_usage=True`） | Story #4 AC-2 / spike-results.md §2.5 mock 模板 / ws_client.push_tick
- [ ] M3-08 | admin | `/4_即時監控` 折線圖 | 觀察 5 metric 折線圖 layout | 用 `plotly.subplots.make_subplots(rows=5, cols=1, shared_xaxes=True)`，5 個 metric 各自獨立 subplot + 獨立 Y 軸 + 共用 x 軸；總高度 ~800-900px 不超 1080p viewport | Story #6 AC-1/3 / design.md:404-462 / spike §3.3
- [ ] M3-09 | admin | `/4_即時監控` | 點「觸發一次模擬異常」後看折線圖 | temperature subplot（row 1）對應 tick 出現 circle-open red marker；cpu_usage subplot（row 5）對應 tick 出現 marker；其他 3 個 metric subplot 無 marker（mock 未設 True） | Story #6 AC-2/4 / Story #4 AC-5 / spike §3.3 marker alignment
- [ ] M3-10 | admin | `/4_即時監控` 告警卡 | 觸發 mock anomaly 後看 metric card | 卡片 label 顯示「溫度(C) 異常」/「CPU 使用率 異常」中文名（非 metric key），value 顯示數值 `150.00` / `95.00`，delta 顯示 `+50.00（閾值 100）` 或對應差值 | Story #4 AC-3 / Story #10 AC-1 / design.md:632-637 / 4_即時監控.py:184-197
- [ ] M3-11 | admin | `/4_即時監控` | 觸發 5 metric 全異常情境（mock 多次 + 真實 simulator humidity 61% anomaly 累計） | 告警卡每行 max 3 個卡片（`st.columns(min(len, 3))`），>3 個自動換行 or list view | Story #10 AC-2 / design.md:638-639
- [ ] M3-12 | admin | `/4_即時監控` | 點「重新整理閾值 / 清空緩衝區」按鈕 | `@st.cache_data.clear()` 觸發；buffer 清空後 caption「緩衝區筆數」歸 0 | Story #5 AC-4 / design.md:347 / 4_即時監控.py:147-155
- [ ] M3-13 | admin | `/4_即時監控` 表格 | 觸發 mock anomaly 後看「最新 60 筆」表格最上一筆 row | 整 row 淡粉紅背景（`#fde8e8` CSS id selector）+ 異常 cell（temperature / cpu_usage）紅字（`#c0392b`） | Story #4 AC-4 / Story #8 AC-3 / spike §2.3 LAYER 3 / 4_即時監控.py:267-359
- [ ] M3-14 | admin | `/4_即時監控` 表格 | 假設 Styler 渲染失敗（人為破壞 column dtype 觸發 exception）| 出現 `st.warning("表格樣式載入失敗，資料內容仍正確")`，下方仍以 `st.dataframe()` 顯示無樣式資料；不靜默 fallback | Story #4 AC-4 / Story #8 AC-4 / design.md:552-563
- [ ] M3-15 | admin / user / viewer | `/4_即時監控` | 觀察告警 metric card delta 顏色 | 觸發 mock anomaly 後 delta `+50.00` 顯示**紅色**（danger），非綠色；即 `delta_color="normal"` 非 `"inverse"` | Story #8 AC-1 / design.md:543-549 / 4_即時監控.py:196
- [ ] M3-16 | admin | `/4_即時監控` | 看頁面標題下方 caption | 「每秒推送 WebSocket wide snapshot，5 大指標 (溫度 / 濕度 / 氣壓 / 電壓 / CPU) 即時呈現，紅色為超閾值異常。下方可手動觸發示範異常。」 | Story #3 AC-4 / design.md:229 / 4_即時監控.py:113 之前
- [ ] M3-17 | admin | `/4_即時監控` | 觀察 multiselect「顯示哪些線」 | 預設值 `["temperature", "pressure", "cpu_usage"]`（3 條），不是全 5 條 | Story #6 AC-3 Edge / design.md:465 / spike §3.4 VA-19
- [ ] M3-18 | admin | `/4_即時監控` | 系統管理頁改 CPU 閾值 100 → 60 → 等 30 秒（cache TTL） → 回即時監控頁觀察 | 告警卡片「閾值 60.0」反映新值；或點「重新整理閾值」按鈕後立即生效 | Story #5 AC-1 + M5-11 / 4_即時監控.py:fetch_dynamic_thresholds

---

## Section 4：模組 4 — 資料分析（11 條）

對應需求文檔 §4.1-4.9（codebase-audit.md 模組 4，9 條），補 Story #3 caption + Story #12（P2 未做）regression。

- [ ] M4-01 | admin / user / viewer | `/3_分析報表` | 三角色登入打開 | 不被 admin gate 擋，正常渲染 | analytics.py AnyRole / 3_分析報表.py:23
- [ ] M4-02 | admin | `/3_分析報表` | 看頁面標題下方 caption | 「查詢即時 + 錄入資料的統計摘要、時間趨勢、類別分布，可選資料來源 (即時 / 錄入 / 兩者)，並匯出 Excel。」 | Story #3 AC-3 / design.md:228 / 3_分析報表.py:55 之前
- [ ] M4-03 | admin | `/3_分析報表` 統合摘要 | 看 4 個 metric cards | 顯示總計筆數 / 即時筆數 / 錄入筆數 / 異常筆數，每個 metric 有值（不是空白） | 模組 4 #4.5 / analytics.py:138-156 / 3_分析報表.py:87-120
- [ ] M4-04 | admin | `/3_分析報表` 查詢條件 | 改 source selectbox（兩者 / 僅即時 / 僅錄入） | 統合摘要 + 時間趨勢圖 + 類別分布 cards 全部 rerun 反映新 source | 模組 4 #4.9 / 3_分析報表.py:90-91 + 157-158 + 300-301
- [ ] M4-05 | admin | `/3_分析報表` | 改時間粒度 selectbox（hour / day） | GET `/analytics/timerange?bucket=hour|day` 200 + 時間趨勢圖 X 軸 bucket 切換 | 模組 4 #4.2 / analytics.py:54-80 / 3_分析報表.py:166-169
- [ ] M4-06 | admin | `/3_分析報表` 時間趨勢圖 | 觀察 Plotly 折線 | X 軸 ts_tw（台北時間）+ Y 軸 avg_value（主軸）+ count（次要軸）+ red x marker 在 anomaly_count > 0 bucket | codebase-audit.md Section 2 / 3_分析報表.py:206-250
- [ ] M4-07 | admin | `/3_分析報表` 類別分布 | 看 bar chart | 顯示 category × count + category × avg_value 兩個 bar chart，可載入無錯 | 模組 4 #4.3 + #4.6 / analytics.py:82-94 + 158-176 / 3_分析報表.py:338-365
- [ ] M4-08 | admin / user / viewer | `/3_分析報表` | 點「匯出 Excel」按鈕 | `st.download_button` 出現，可下載 .xlsx；下載檔包含對應欄位（不空檔） | 模組 4 #4.4 / analytics.py:96-136 / 3_分析報表.py:379-436
- [ ] M4-09 | admin | `/3_分析報表` | FE 讀 unified-summary key 對齊 BE schema（total_records / avg_value / min_value / max_value）| 4 metric cards 都不是空白（不是 `count/sum/avg/max` 舊鍵名） | round 1 D-BLOCK-3 regression / report_round1_fixes.md / 3_分析報表.py:209/219/352
- [ ] M4-10 | admin | `/3_分析報表` | 切 source → 「即時資料」看時間趨勢圖 | （Story #12 P2 未做）目前仍是 bar chart 或既有渲染；若已修則為折線圖（go.Scatter） | Story #12 AC-1 / design.md:686-712 / 留 v4
- [ ] M4-11 | admin | `/3_分析報表` 查詢條件 | 「篩選條件」expander | `expanded=True` 預設展開 + 4 個 input（含 date_input × 2 + bucket + source 等） | codebase-audit.md Section 1 頁面 4 / 3_分析報表.py:57-76

---

## Section 5：模組 5 — 系統管理 admin only（16 條）

對應需求文檔 §5.1-5.9（codebase-audit.md 模組 5，9 條），補 Story #11 四個 P1 修補。

- [ ] M5-01 | admin | `/5_系統管理` | 看頁面標題下方 caption | 「Admin 限定：使用者管理 / Audit log / DB 狀態 / 即時資料歷史 / 動態系統設定 (閾值即時生效)。」 | Story #3 AC-5 / design.md:230 / 5_系統管理.py:69 之前
- [ ] M5-02 | admin | `/5_系統管理` | 看 5 個 tab labels | 全無 emoji（純文字 label，如「使用者管理」「系統日誌」「DB 狀態」「即時資料歷史」「系統設定」） | codebase-audit.md Section 1 頁面 6 / 5_系統管理.py:71-77
- [ ] M5-03 | admin | `/5_系統管理` → Tab 1 使用者管理 | 看「角色權限說明」expander | `expanded=True` 預設展開（v3 從 False 改 True），顯示 13 操作 × 3 角色 markdown table（✓/✗） | Story #2 AC-5 + Story #11 AC-4 / design.md:188 + 660 / 5_系統管理.py:88
- [ ] M5-04 | admin | `/5_系統管理` → Tab 2 系統日誌 | 看 audit log 預設顯示 | 預設 limit=50（不是舊版 10），selectbox 提供 [20/50/100] 選項 | Story #11 AC-1 / design.md:657 / 5_系統管理.py:309 附近
- [ ] M5-05 | admin | `/5_系統管理` → Tab 2 | 看 audit log caption | 「預設顯示前 50 筆，可調整每頁筆數」或類似文字 | Story #11 AC-1 補完 / user-stories.md:367
- [ ] M5-06 | admin | `/5_系統管理` → Tab 3 DB 狀態 | 看 3 metric cards | 顯示 Pool 大小 / checked_out / overflow，且資料表統計 dataframe 載入 | 模組 5 #5.5 / admin.py:81-127 / 5_系統管理.py:360-405
- [ ] M5-07 | admin | `/5_系統管理` → Tab 4 即時資料歷史 | 看 wide format dataframe | 載入無錯，欄位含 ts + 5 metrics + anomaly_flags（11 欄）+ 分頁控制 | 模組 3 #3.9 + 模組 5 / admin.py:129-166 / 5_系統管理.py:428-551
- [ ] M5-08 | admin | `/5_系統管理` → Tab 5 系統設定 | 看 5 個 setting expander 初始狀態 | 預設全部 `expanded=False`（不是舊版全展開） | Story #11 AC-2 / design.md:658 / 5_系統管理.py:558-639
- [ ] M5-09 | admin | `/5_系統管理` → Tab 5 | 點「展開全部設定」toggle 按鈕 | 5 個 expander 全部切換為 `expanded=True`（透過 `st.session_state["expand_all_settings"]`） | Story #11 AC-2 / design.md:658
- [ ] M5-10 | admin | `/5_系統管理` → Tab 5 | 改某 setting value（如 anomaly_threshold_high 100→60）→ 按儲存 | PATCH `/admin/settings/{key}` 200 + `@st.cache_data.clear()` + setting dataframe rerun 顯示新值 | 模組 5 #5.7 / admin.py:180-201 / 5_系統管理.py:617
- [ ] M5-11 | admin | `/5_系統管理` → Tab 5 → `/4_即時監控` | 改 anomaly_threshold_high 100 → 60 後切到即時監控頁 | 30 秒內（cache TTL）告警判斷以 60 為閾值；告警卡的閾值參考值反映 60 | Story #5 AC-1 / design.md:325-358
- [ ] M5-12 | admin | `/5_系統管理` → Tab 1 | 點某 user row 改密碼 form（不需 old_password） | PATCH `/users/{id}/password` 200 OK | 模組 1 #1.6 admin 分支 / 5_系統管理.py:251
- [ ] M5-13 | admin | `/5_系統管理` → Tab 1 | 看「啟用 checkbox」改 user is_active | PATCH `/users/{id}` 200 + dataframe 反映啟用/停用 | 模組 5 #5.2 / 5_系統管理.py:191
- [ ] M5-14 | admin | `/5_系統管理` → Tab 2 | 用 action 篩選 selectbox 篩 `update_user_role` | dataframe 只顯示對應 action 的 log row | 模組 5 #5.4 / admin.py:38-79 / 5_系統管理.py:268-353
- [ ] M5-15 | admin | `/5_系統管理` → Tab 2 | 展開 metadata expander 看 log row | 顯示 `st.json(item["meta"])`（讀 `meta` 不是 `metadata`），不空白 | round 1 D-HIGH-2 regression / report_round1_fixes.md / 5_系統管理.py:347-351
- [ ] M5-16 | admin | `/5_系統管理` → Tab 1 | 觀察「刪除選定使用者」UI 區塊（line 158 之後新增） | 有 selectbox（選 user）+ confirm checkbox + delete button；DELETE 完成 toast + cache_clear | Story #11 AC-3 / design.md:659

---

## Section 6：角色權限矩陣端對端跨頁（10 條）

13 操作 × 3 角色 = 39 條的關鍵差異化檢核（重複已在 Section 1-5 涵蓋過的不重複），補跨頁 RBAC 端對端。

- [ ] RB-01 | viewer | `/2_資料管理` 嘗試新增 row 操作 | data_editor 「新增 row」UI disabled 或新 row 送出 POST `/data` 被 BE 403 | 角色矩陣「新增資料」viewer ✗ / data.py + 2_資料管理.py:146-148
- [ ] RB-02 | viewer | `/2_資料管理` 嘗試批量匯入 | file_uploader disabled 或 POST `/data/bulk-import` 403 | 角色矩陣「批量匯入」viewer ✗ / 2_資料管理.py:270-325
- [ ] RB-03 | user | `/2_資料管理` 嘗試刪除他人 row | DELETE 403 silent skip + toast「無權限」 | 角色矩陣「刪除他人」user ✗ / data.py:167-175 + 2_資料管理.py:189
- [ ] RB-04 | user | `/5_系統管理` URL 直入 | 顯示 `st.error("僅 Admin 可存取此頁")` + `st.stop()` | 角色矩陣「系統管理」user ✗ / 5_系統管理.py:38-41 = M1-09
- [ ] RB-05 | viewer | `/5_系統管理` URL 直入 | 同 RB-04 被擋 | 角色矩陣「系統管理」viewer ✗
- [ ] RB-06 | user | 嘗試 PATCH 他人角色（curl `/users/{other_id}` PATCH role=admin） | BE 回 403（AdminOnly 守衛） | 角色矩陣「管理使用者角色」user ✗ / users.py:68-91 deps.py AdminOnly
- [ ] RB-07 | viewer | 嘗試打 GET `/admin/settings` curl with viewer JWT | BE 回 403（AdminOnly） | spike-results.md VA-9 已驗 / admin.py:169-178
- [ ] RB-08 | viewer / user | `/3_分析報表` 匯出 Excel | 三角色都能下載（Excel 匯出 AnyRole） | 角色矩陣「分析報表/匯出」all ✓ / analytics.py:96-136
- [ ] RB-09 | viewer / user / admin | `/4_即時監控` | 三角色都連 WS + 看到即時 snapshots | 角色矩陣「即時 WebSocket」all ✓ / ws.py + 4_即時監控.py:97 / round 1 D-BLOCK-2
- [ ] RB-10 | admin / user / viewer | `/1_儀表板` 看角色矩陣 markdown 顯示對應角色名稱 | 矩陣中角色名稱（Admin / User / Viewer）與右上角用戶資訊欄字串一致 | Story #2 AC Edge / user-stories.md:88-89

---

## Section 7：Round 1 + redesign v2 regression（8 條）

防止 round 1 修補的 8 個 P0 bug + v2 D-BLOCK 三個阻斷在 v3 又出現。

- [ ] R1-01 | user | `/` Home | 用 `user@example.com / user123`（7 字密碼）登入 | 200 OK + access_token + 跳轉 Dashboard（不被 8 字元 validator 擋） | round 1 BUG #1 / fb3916b / report_round1_fixes.md
- [ ] R1-02 | 自動 | FE `api_client.py:14` BACKEND_URL fallback | 不為 `http://localhost:8000`，是 Zeabur production URL | round 1 BUG #5 / 63b74e8 / api_client.py:12-14
- [ ] R1-03 | 自動 | FE `ws_client.py:30,32` WS path | 為 `/ws/realtime`（不含 `/api/v1` prefix） | round 1 BUG #6 / 63b74e8 / ws_client.py
- [ ] R1-04 | admin | `/2_資料管理` 篩選 | 用 `st.date_input` + `st.time_input` 組 datetime（不用 `st.datetime_input`） | 篩選正常工作，無 AttributeError | round 1 D-BLOCK-1 / 1c92723
- [ ] R1-05 | viewer | `/4_即時監控` | 進入頁面後 WS `/ws/realtime?token=<JWT>` 連線（不打 admin-only `/admin/realtime-history` polling） | 連線狀態●「連線中」+ 三角色都可看 | round 1 D-BLOCK-2 / 4_即時監控.py:97
- [ ] R1-06 | admin | `/3_分析報表` | unified-summary FE 讀對 BE 的 4 key（`total_records / avg_value / min_value / max_value`） | 4 metric cards 都有值不空白 | round 1 D-BLOCK-3 / 3_分析報表.py:209/219/352
- [ ] R1-07 | admin | `/5_系統管理` Tab 2 | log row metadata 展開後讀 `item["meta"]` | metadata 顯示 JSON 內容不空白 | round 1 D-HIGH-2 / 5_系統管理.py:347-351
- [ ] R1-08 | admin | `/4_即時監控` | `_METRIC_KEYS` 對齊 BE simulator SIMULATOR_CATEGORIES（5 個：temperature/humidity/pressure/voltage/cpu_usage） | 即時資料對應 5 metric，無 vibration/power 等舊鍵名 | round 1 D-HIGH-5 / 4_即時監控.py:40-46

---

## Section 8：Redesign v3 Story 驗收（12 條）

12 個 Story 級別整體 DOD 確認（每 Story 細部 AC 已散落在 Section 1-7）。

- [ ] S-#1 | 全角色 | `/` Home | Story #1 試用帳號 + zero-click 整體驗（含 M1-01 ~ M1-05） | 4 條 AC 全綠：expander 預設展開、3 顆按鈕 query_params 自動登入、跳 Dashboard 顯示對應角色、註冊 tab 不污染 | Story #1 完成（commit cf22579 / Sprint 1）
- [ ] S-#2 | 全角色 | `/1_儀表板` + `/5_系統管理` | Story #2 角色矩陣固定卡片整體驗（含 M1-10/11 + M5-03 + RB-10） | 5 條 AC 全綠：矩陣卡片 in border container 在 status header 之上、當前角色 bold ✓、admin 系統管理 expander 預設展開 | Story #2 完成（commit cf22579 / Sprint 1）
- [ ] S-#3 | 全角色 | 5 頁 | Story #3 onboarding caption 整體驗（含 M2-08 + M3-16 + M4-02 + M5-01 + 儀表板 caption） | 5 頁各至少 1 個 caption 在 title 50 行內 + `rg "st.caption" frontend/streamlit_app/pages/` 至少 5 個 hit | Story #3 完成（commit cf22579 / Sprint 1）
- [ ] S-#4 | 全角色 | `/4_即時監控` | Story #4 Demo 控制面板 mock anomaly 整體驗（含 M3-06 ~ M3-07 + M3-13 ~ M3-15） | 5 條 AC 全綠：Demo 控制 container 可見、按鈕 fire mock、告警卡 + 折線 marker + Styler 三層全 fire、Styler 失敗有 warning | Story #4 完成（commit 19155f3 / Sprint 2）
- [ ] S-#5 | admin | `/5_系統管理` → `/4_即時監控` | Story #5 動態閾值 fetch 整體驗（含 M3-04 + M3-05 + M3-12 + M5-11） | 5 條 AC 全綠：admin 改閾值即時監控同步、`@st.cache_data(ttl=30)` 生效、viewer/user 403 fallback caption、清緩衝區 cache_clear、網路失敗 warning | Story #5 完成（commit 19155f3 / Sprint 2）
- [ ] S-#6 | admin | `/4_即時監控` | Story #6 plotly small multiples 整體驗（含 M3-08 + M3-09 + M3-17） | 5 條 AC 全綠：`make_subplots(rows=5)` 5 個獨立 Y 軸、anomaly marker 在正確 subplot、1080p 不需 scroll、shared_xaxes 同步、multiselect 預設 3 條 | Story #6 完成（commit 19155f3 / Sprint 2）
- [ ] S-#7 | 全角色 | `/1_儀表板` | Story #7 Demo Banner 整體驗 | 5 條 AC 全綠：banner `st.info` 反映角色路線（admin/user/viewer 三條不同文案）、不再顯示 checkbox 存 session_state、不遮元件 | Story #7 完成（commit 2084be8 / Sprint 2）
- [ ] S-#8 | admin | `/4_即時監控` | Story #8 delta_color + Styler 整體驗（含 M3-14 + M3-15） | 5 條 AC 全綠：所有 `delta_color="inverse"` audit 過、正偏差顯紅色（normal）、Styler 失敗 logging + warning、pytest 全綠不 regress | Story #8 完成（commit 2084be8 / Sprint 2）
- [ ] S-#9 | viewer | `/1_儀表板` | Story #9 Metric Cards 品質指標化（P1）| 4 條 AC 全綠：col4 顯示「今日異常率 X.XXX%」+ delta vs 昨日、4 metric 全有 `help=` tooltip、BE 失敗 fallback「載入中」 | **Story #9 P1 待驗**（Sprint 3 未確認 commit）
- [ ] S-#10 | admin | `/4_即時監控` | Story #10 告警卡片嚴重度整體驗（含 M3-10 + M3-11） | 3 條 AC 全綠：metric 中文名 + 當前值 + 「超閾值 +/-N」 + `st.columns(min(len, 3))` max 3 per row | Story #10 完成（commit 8c0eea7 / Sprint 3）
- [ ] S-#11 | admin | `/5_系統管理` | Story #11 系統管理修補整體驗（含 M5-04 + M5-08 + M5-09 + M5-16 + M1-07 + M1-08 + M5-03） | 4 條 AC 全綠：audit log 預設 50 + 分頁、settings expander 預設 collapsed + 展開全部 toggle、DELETE user UI + confirm + disable self、矩陣 expander 預設展開 | Story #11 完成（commit 8c0eea7 / Sprint 3）
- [ ] S-#12 | user | `/3_分析報表` 改 source=realtime | Story #12 Source Toggle 折線圖（P2 v4 候選） | （P2 未做）目前 source=realtime 仍為既有渲染；不阻 v3 DOD | Story #12 P2 留 v4 / design.md:686-712 / user-stories.md:387-413

---

## 附錄：完成定義（DOD）對照表（design.md §7 7 條）

驗收時需確認以下 7 條 DOD 全綠：

| DOD | 對應本 checklist | 驗證方式 |
|---|---|---|
| 1. 12 個 story AC 全綠 | Section 8 S-#1 ~ S-#12 | main session Chrome MCP 跑 12 條 |
| 2. pytest 全綠（33 perm + round 1 8 P0 不 regress）| Section 7 R1-01 ~ R1-08 + `pytest -v --cov=app` | `cd backend && pytest -v` 全綠 |
| 3. 80-120 條 validation checklist 100% 綠 | 全本檔 | main session Chrome MCP 三角色逐條驗 |
| 4. Chrome MCP 15 張截圖合格 | Section 1-5 截圖部分 | sub-agent Read 圖檢視描述 |
| 5. demo script A/B/C 跑通 | user-stories.md Section 5 三 script | main session 逐 step 過 |
| 6. ui-ux-tester sub-agent 整體驗收通過 | 派 ui-ux-tester | v6.1 sub-agent Mode A 加強版 |
| 7. Zeabur 部署成功 + 3 角色 prod smoke test 通過 | 全 Section 對 Zeabur prod URL 跑 | push 後 10 min wait + 三角色登入 |

---

## 統計

- **總條目**：Section 1（12）+ Section 2（13）+ Section 3（18）+ Section 4（11）+ Section 5（16）+ Section 6（10）+ Section 7（8）+ Section 8（12）= **100 條**
- **覆蓋**：5 大模組 41 條需求全覆蓋、12 個 user story AC 全覆蓋、3 角色 × 13 操作 RBAC 端對端覆蓋（合併重複後 10 條）、round 1 + v2 + v3 regression 8 + Story 級 12 條
- **未驗（P1/P2 待）**：Story #9（P1 品質指標化）+ Story #12（P2 source toggle）

---

VALIDATION CHECKLIST DONE
