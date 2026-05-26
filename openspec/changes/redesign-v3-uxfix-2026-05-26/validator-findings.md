# Validator Findings — Redesign v3 UX Fix

**Date**: 2026-05-26
**Validator**: implementation-validator (opus, READ-ONLY)
**Scope**: spec vs code gap analysis on 4 commits (cf22579 → 19155f3 → 2084be8 → 8c0eea7)

---

## Section 1: Critical Gap（必修才能 ship）

**NONE** — No Critical Gaps Found

12 個 Story AC 對照實際 code，0 BLOCKER 阻 ship。Phase A 5 spike 結論完整落實。端對端資料流對齊 BE wide v2 schema。Round 1 + v2 regression 8/8 安全。

---

## Section 2: High Gap（應修但不阻 ship）

### H-1: Story #9 AC-2 缺 "delta 比較 vs 昨日/小時前"

- **File**: `frontend/streamlit_app/pages/1_儀表板.py:192-222`
- **Spec**: design.md line 596-606 + user-stories.md AC-2 + tasks.md D.1.1
- **實際**: col1/col2 只顯示 30 天累計，無 delta vs 昨日比較
- **影響**: 評審看不到趨勢資訊
- **修補**: 加 fetch 昨日範圍 unified-summary + delta calc，或更新 AC-2 接受「30 天累計，無 delta」

### H-2: D-BLOCK-1 round 1 時間粒度降級

- **File**: `frontend/streamlit_app/pages/2_資料管理.py:63-64`
- **Spec**: report_round1_fixes.md D-BLOCK-1「st.date_input + st.time_input + combine」
- **實際**: 只有 date_input 無 time_input
- **影響**: 篩選只有日級精度（round 1 後降級）
- **修補**: 補回 time_input 或文件接受降級

### H-3: 即時監控 subplot 雙重 metric label 視覺冗餘

- **File**: `4_即時監控.py:336 + 385-388`
- **Spec**: design.md line 421 只設 subplot_titles，無 update_yaxes(title)
- **實際**: 同時設 subplot_titles + y-axis title — metric 名稱雙顯
- **影響**: 視覺冗餘，subplot 高度被推擠
- **修補**: 移除 update_yaxes(title_text=...) 或改為單位（°C / % / hPa）

### H-4: Story #9 col3/col4 範圍與 help 文字不符

- **File**: `1_儀表板.py:106-118 + 212-222`
- **實際**: unified-summary 抓 30 天範圍，但 simulator 在 BE 啟動才開始
- **影響**: help 寫「過去 30 天」但實際遠少於，評審看到實際筆數會質疑
- **修補**: 改 help 文字為「累計推送總筆數」或限制 fetch 範圍

### H-5: Story #5 admin BE 失敗顯 caption 而非 warning

- **File**: `4_即時監控.py:234-240`
- **Spec**: user-stories.md Story #5 AC-5「網路失敗顯示 warning」
- **實際**: admin 失敗時顯示「閾值來源：預設 fallback」caption
- **影響**: admin 在 BE 異常時看不到顯眼提示
- **修補**: admin 失敗路徑改 `st.warning(...)`，viewer/user 維持 caption

### H-6: Story #11 刪除自己 disable 在 button 層而非 selectbox 層

- **File**: `5_系統管理.py:166-249`
- **Spec**: validation-checklist M1-08「自己 user_id 不出現在 selectbox 或 disabled」
- **實際**: selectbox 仍列自己，僅 button disabled + warning
- **影響**: 弱影響，「或 disabled」OR 邏輯滿足 → 可不修

---

## Section 3: Nice-to-have（可後續）

- **N-1**: `4_即時監控.py:462-465` dead code `_style_cell` placeholder
- **N-2**: validation-checklist M5-09 key 名「expand_all_settings」vs 實際「settings_all_expanded」不一致
- **N-3**: `1_儀表板.py:168` `delta_color="inverse"` 保留 comment 簡略，可加強
- **N-4**: subplot height cap 900 對 5 metric 略擠（每 subplot 180px）
- **N-5**: `Home.py:34-35` demo_login 失敗未 `st.stop()`，error 在 title 之上
- **N-6**: Story #12 P2 確認留 v4
- **N-7**: H-2 重複

---

## Section 4: Story-by-Story AC 通過率

| Story | 結論 |
|---|---|
| #1 Home demo accounts | **PASS** |
| #2 角色矩陣 | **PASS** |
| #3 Onboarding caption | **PASS** |
| #4 Demo control panel | **PASS** |
| #5 動態閾值 | **PARTIAL**（H-5 admin warning）|
| #6 small multiples | **PASS**（H-3 雙 label 視覺）|
| #7 Demo Banner | **PASS** |
| #8 delta_color + Styler | **PASS** |
| #9 metric quality | **PARTIAL**（H-1 delta vs 昨日）|
| #10 alert severity | **PASS** |
| #11 系統管理 4 P1 | **PASS** |
| #12 source=realtime trend | **DEFERRED**（P2 留 v4）|

**通過率**：9/11 全綠 PASS，2 PARTIAL（High 級），1 DEFERRED

---

## Section 5: Phase A spike 結論落實確認

| Spike | 結論 | 實作對齊 | 結果 |
|---|---|---|---|
| VA-1/16/17 query_params Plan B | `?demo_login=admin` zero-click | `Home.py:25` `st.query_params.get("demo_login")` | **PASS** |
| VA-7/8 mock anomaly schema | naïve ISO + 5 metric + anomaly_flags + source="mock" | `4_即時監控.py:136-151` 100% 對齊 | **PASS** |
| VA-10 subplots row=N + height | `make_subplots` + marker row=idx + height=min(180*n, 900) | `4_即時監控.py:331-392` 100% 對齊 | **PASS** |
| VA-9 viewer/user fallback | 不打 endpoint 直接 fallback | `4_即時監控.py:94-95` 完全 skip 403 | **PASS**（implementation 比 spec 更激進）|
| VA-20 Zeabur webhook | 4 commits 全 RUNNING | 已驗 | **PASS** |

---

## Section 6: Round 1 + v2 regression 8 條

| Bug ID | 結果 |
|---|---|
| BUG #1（8 字密碼 validator）| **PASS**（v3 未碰 BE）|
| BUG #5（BACKEND_URL fallback）| **PASS**（api_client.py:12-14）|
| BUG #6（WS path）| **PASS**（ws_client.py:30-34）|
| D-BLOCK-1（datetime_input）| **PASS**（無 `datetime_input`，但 H-2 時間粒度降級）|
| D-BLOCK-2（WS 三角色）| **PASS**（4_即時監控.py:168 三角色都可）|
| D-BLOCK-3（unified-summary 鍵對齊）| **PASS**（鍵對齊）|
| D-HIGH-2（log metadata 讀 meta）| **PASS**（5_系統管理.py:398-399）|
| D-HIGH-5（_METRIC_KEYS 對齊）| **PASS**（5 metric 全對齊）|

**Round 1 regression**: 8/8 PASS

---

## Section 7: Final DOD Verdict

### Verdict: **PASS_WITH_2_HIGH_GAPS**

- **0 Critical**（必修才能 ship）
- **6 High**（應修但不阻 ship）：H-1（Story #9 AC-2 delta）/ H-2（時間粒度降級）/ H-3（subplot 雙 label）/ H-4（範圍 help 文字）/ H-5（admin warning）/ H-6（selectbox 過濾）
- **7 Nice-to-have**

### 給 main session 的修補優先級順序

1. **先修 H-1 + H-5**（user-facing 直接相關 AC）— 30-60 min
2. **修 H-3 + H-4**（視覺/文字精度）— 30 min
3. **H-2 / H-6** 與 validation checklist 同步討論
4. **N-1 / N-2 / N-5** 隨手清 — 15 min
5. **N-3 / N-4** 留 v4
6. **Story #12** P2 確認留 v4

### 不需修補

- 8/8 round 1 + v2 regression 全綠
- Phase A 5 spike 結論在實作中完整落地
- 端對端資料流對齊 design.md Section 3.4 + Story 5 段對照表

---

VALIDATOR FINDINGS DONE
