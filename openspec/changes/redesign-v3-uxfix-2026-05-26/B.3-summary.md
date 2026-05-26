# B.3 Story #3 — 5 頁 Onboarding Micro-copy 實作摘要

**完成時間**：2026-05-26
**任務 ID**：B.3.1
**負責 agent**：frontend-engineer

---

## 改動 Component / Page

### 1. `frontend/streamlit_app/pages/1_儀表板.py`

**插入位置**：line 41（`st.title("儀表板")` 在 line 30，caption 在 line 41，差 11 行）

**插入在**：`st.markdown("---")` 之前（標題列 `col_title/col_user` 結束後）

**caption 文字**：
```
您可以在這裡掌握系統整體狀態：上方為角色權限說明，中間為即時連線狀態與最近告警數，下方為合計筆數統計與最近資料快照。可在底部展開帳號設定修改密碼。
```

---

### 2. `frontend/streamlit_app/pages/2_資料管理.py`

**插入位置**：line 51（`st.title("資料管理")` 在 line 41，差 10 行）

**插入在**：`st.markdown("---")` 之前、第一個 `st.expander("篩選條件")` 之前

**caption 文字**：
```
您可以在這裡管理資料：上傳 CSV / JSON 批量匯入、用篩選條件搜尋已有資料、inline 編輯欄位後一次儲存。Viewer 角色為唯讀，User 只能編輯自己的資料，Admin 可編輯所有資料。
```

---

### 3. `frontend/streamlit_app/pages/3_分析報表.py`

**插入位置**：line 54（`st.title("分析報表")` 在 line 44，差 10 行）

**插入在**：`st.markdown("---")` 之前、第一個 `st.expander("查詢條件")` 之前

**caption 文字**：
```
您可以在這裡查看資料分析報表：即時 + 錄入資料的統計摘要、時間趨勢圖、類別分布長條圖。可切換資料來源（兩者 / 僅即時 / 僅錄入）、調整時間粒度（小時 / 日），並可匯出 Excel 檔。
```

---

### 4. `frontend/streamlit_app/pages/4_即時監控.py`

**插入位置**：line 112（`st.title("即時監控")` 在 line 86，差 26 行）

**插入在**：`st.markdown("---")` 之前（位於 `st_autorefresh` 之後、status columns 之前）

**caption 文字**：
```
您可以在這裡觀察 5 大指標的即時資料：透過 WebSocket 每秒推送，紅色 marker 為超閾值異常告警，淡粉紅背景的資料列代表該秒有異常發生。可用 multiselect 選擇要顯示的指標線。
```

---

### 5. `frontend/streamlit_app/pages/5_系統管理.py`

**插入位置**：line 68（`st.title("系統管理")` 在 line 58，差 10 行）

**插入在**：`st.markdown("---")` 之前、第一個 `st.tabs()` 之前

**caption 文字**：
```
您是 Admin 角色，可以在這裡管理整個系統：使用者列表（改角色 / 啟用 / 刪除 / 改密碼）、查看 Audit log、檢視 DB 連線池與表統計、即時資料歷史查詢、動態調整異常閾值與 tick 間隔。
```

---

## Backend API 使用

Story #3 為純靜態 UI 文字渲染，無任何 API 呼叫。不觸碰 backend-summary 中的任何 endpoint。

---

## Edge Case / 失敗 path 處理

1. **caption 長度**：5 段均 ≤ 80 中文字，符合 AC-1 至 AC-5 要求
2. **禁 HTML**：全部使用純中文 + 標點，不含 HTML 標籤，符合 `st.caption()` API 最佳實踐
3. **不修改既有邏輯**：只在現有 `st.title()` 之後插入 `st.caption()`，不移動、不刪除任何現有元件
4. **Viewer 無法進入系統管理**：5_系統管理.py 有 `role != "admin"` 守衛（line 38-41），caption 只有 admin 能看到，符合 Story #3 AC-5
5. **title 50 行內驗證**：
   - 1_儀表板.py：title line 30，caption line 41，差 11 行
   - 2_資料管理.py：title line 41，caption line 51，差 10 行
   - 3_分析報表.py：title line 44，caption line 54，差 10 行
   - 4_即時監控.py：title line 86，caption line 112，差 26 行
   - 5_系統管理.py：title line 58，caption line 68，差 10 行
   - 全部在 50 行內，符合 AC-6

---

## 驗證結果

```
grep -n "st\.caption" frontend/streamlit_app/pages/1_儀表板.py
→ 41: st.caption("您可以在這裡掌握系統整體狀態...")

grep -n "st\.caption" frontend/streamlit_app/pages/2_資料管理.py
→ 51: st.caption("您可以在這裡管理資料...")

grep -n "st\.caption" frontend/streamlit_app/pages/3_分析報表.py
→ 54: st.caption("您可以在這裡查看資料分析報表...")

grep -n "st\.caption" frontend/streamlit_app/pages/4_即時監控.py
→ 112: st.caption("您可以在這裡觀察 5 大指標的即時資料...")

grep -n "st\.caption" frontend/streamlit_app/pages/5_系統管理.py
→ 68: st.caption("您是 Admin 角色，可以在這裡管理整個系統...")
```

全部 5 頁各有 1 個 onboarding caption 在 `st.title()` 50 行內出現，符合 Story #3 AC-6。

---

B.3 DONE
