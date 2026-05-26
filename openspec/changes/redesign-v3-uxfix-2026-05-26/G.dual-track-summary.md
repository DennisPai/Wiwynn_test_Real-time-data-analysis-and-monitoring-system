# G.dual-track-summary — 雙軌設計 UX 補強

## 任務總覽
本次變更目標：讓使用者一眼看懂「即時監控 + 資料管理 = 同一個監控系統的雙軌資料」，消除「示範 CSV 跟即時資料 schema 不同 → 設計合理性存疑」的誤解。

---

## 改動明細

### 任務 1: README.md — 新增「資料雙軌設計」節

**檔案**: `/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/README.md`

- **插入位置**: line 15（原「## 技術棧」之前，「## 功能模組」表格之後）
- **Before**: 原第 15 行是 `## 技術棧`，無雙軌說明
- **After**: 新增 `## 資料雙軌設計` H2 節（含雙軌對照表 + 為什麼 schema 不同的說明）
- **驗證**: `grep -n "資料雙軌設計" README.md` → line 15

### 任務 2: 2_資料管理.py — caption 補強雙軌脈絡

**檔案**: `/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/frontend/streamlit_app/pages/2_資料管理.py`

- **改動行**: line 51
- **Before**: `st.caption("您可以在這裡管理資料：上傳 CSV / JSON 批量匯入、用篩選條件搜尋已有資料、inline 編輯欄位後一次儲存。Viewer 角色為唯讀，User 只能編輯自己的資料，Admin 可編輯所有資料。")`
- **After**: `st.caption("**本頁管理的是「資料管理軌」**（使用者手動補登或匯入的歷史 / 外部監控資料），與「即時監控軌」（simulator 自動推送）共用同 5 metric category，可在「分析報表」頁切 source toggle 跨軌分析。功能：上傳 CSV / JSON 批量匯入、用篩選條件搜尋、inline 編輯後一次儲存。Viewer 角色為唯讀，User 只能編輯自己的資料，Admin 可編輯所有資料。")`
- **驗證**: `grep -n "資料管理軌"` → line 51

### 任務 3: 3_分析報表.py — 三個 source toggle 加 help text

**檔案**: `/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/frontend/streamlit_app/pages/3_分析報表.py`

#### 3a. summary_source selectbox（line 93 → 展開為 98）
- **Before**: `source_label = st.selectbox("資料來源", list(_SOURCE_OPTIONS.keys()), index=0, key="summary_source")`
- **After**: 展開為多行寫法，加 `help="兩者 = 即時 + 錄入合併統計；僅即時 = simulator 自動推送的軌道；僅錄入 = 使用者手動匯入的軌道。共用同 5 metric category 可跨軌比較。"`
- **驗證**: `grep -n "跨軌比較"` → line 98

#### 3b. trend_source selectbox（line 160 → 展開為 171）
- **Before**: `trend_source_label = st.selectbox("趨勢圖資料來源", list(_TREND_SOURCE_OPTIONS.keys()), index=0, key="trend_source")`
- **After**: 加 `help="即時軌（realtime）= simulator 每秒自動推送的 wide-format 快照，顯示過去 60 分鐘；錄入軌（data_records）= 使用者手動匯入的 long-format 歷史資料，支援 30 天跨期趨勢。共用同 5 metric category 可跨軌比較。"`

#### 3c. cat_source selectbox（line 397 → 展開 + help）
- **Before**: `cat_source_label = st.selectbox("分佈資料來源", list(_CAT_SOURCE_OPTIONS.keys()), index=0, key="cat_source")`
- **After**: 加 `help="即時軌（realtime）= simulator 自動推送的各 metric 分佈統計；錄入軌（data_records）= 使用者手動匯入的各 category 分佈統計。兩軌共用同 5 metric category，切換可比較兩軌資料分佈差異。"`

### 任務 4: docs/sample_data_readme.md — 新建說明文件

**檔案**: `/home/node/projects/Wiwynn_test_Real-time-data-analysis-and-monitoring-system/docs/sample_data_readme.md`

- **Before**: 不存在
- **After**: 新建文件，含：
  - 用途說明（data_records 軌的示範資料）
  - Schema 欄位表（Long Format：title / value / category / recorded_at）
  - 與即時監控軌的關係（共用 5 category + 跨軌比較）
  - 匯入方法 3 步驟
  - 連結到 README 的雙軌說明節

---

## 驗證結果

| 檢查項目 | 指令 | 結果 |
|---|---|---|
| README grep 資料雙軌設計 | `grep -n "資料雙軌設計" README.md` | line 15 PASS |
| 2_資料管理.py grep 資料管理軌 | `grep -n "資料管理軌" 2_資料管理.py` | line 51 PASS |
| 3_分析報表.py grep 跨軌比較 | `grep -n "跨軌比較" 3_分析報表.py` | line 98, 171 PASS |
| sample_data_readme.md 落地 | `test -f docs/sample_data_readme.md` | EXISTS PASS |
| 2_資料管理.py syntax check | `python3 -m py_compile` | SYNTAX OK |
| 3_分析報表.py syntax check | `python3 -m py_compile` | SYNTAX OK |

---

## 邊界說明

- 未動任何後端檔案（backend/ 目錄完全未觸碰）
- 未新增或修改 API endpoint
- 未刪除任何既有功能（caption 是補充，所有原有功能文字均保留）
- Sprint 1-3 / Phase 11 / F.LOCAL 既有改動全部保留
