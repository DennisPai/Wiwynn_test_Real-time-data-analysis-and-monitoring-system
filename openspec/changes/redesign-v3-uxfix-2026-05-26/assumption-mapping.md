# Assumption Mapping — Wiwynn Redesign v3 UX Fix

> **Date**：2026-05-26
> **Owner**：assumption-mapping sub-agent（v6.1 Software Factory Mode A 加強版）
> **目的**：在動工前用 VUBF 4 類框架識別假設，de-risk 8-24 hr 時間箱內最該驗的 Top 10，避免「全部 commit 完發現核心假設崩盤」。
> **讀過的證據**：
> - `pm-strategy.md`（466 行，6 大抽象問題 + P0/P1 + 5 修 5 不動 + 6 open questions）
> - `ux-research.md`（659 行，4 persona JTBD + 6 頁 audit + Top 10 痛點 + 圖表 / 角色 UX）
> - `codebase-audit.md`（404 行，41 條需求 + 16 open issues + help/caption 覆蓋率 41%）
> - `~/.claude/agents/assumption-mapping.md`（assumption-mapping agent SOP）
>
> **任務脈絡**：v3 是 Wiwynn 面試題最後輪 UX 優化（v1 → v2 已動過 a50b045 commit），預估 8-24 hr。最大威脅：（1）v2 既有功能迴歸（2）Zeabur 部署再卡（3）新 UX 規約超出時間箱。

---

## Section 1: VUBF 假設提煉框架說明

VUBF = Valuable / Usable / Buildable / Feasible，是 Marty Cagan 提出的 4 大產品風險類別。用在 v3 redesign 上：

### 1.1 Valuable（價值假設）
**核心問句**：使用者 / 評審會在乎這個改動嗎？改了之後**評分會不會提升**？
- 不只「user 喜歡」，更要「在 5-10 分鐘 demo 視窗內，這個改動讓評審打勾 + 1 分」。
- 對應 persona D 評審「掃讀 → 抽樣 → 判斷」工作流。
- **反例**：花 3 hr 加角色 chip badge，評審根本沒看到 → 不 valuable。

### 1.2 Usable（可用性假設）
**核心問句**：使用者能在**不教學的情況下**用對嗎？
- 對應 Persona A/B/C 不同程度的技術背景（admin 中階、user 中、viewer 低）。
- 不只「能用」，要「30 秒內憑直覺找到」。
- **反例**：加「重新整理」icon button 在右上角，admin 看不懂 icon → 不 usable。

### 1.3 Buildable（可建構性假設）
**核心問句**：技術上能做嗎？工時 / 依賴 / 技術風險？
- Streamlit 1.39 框架限制（download_button 必須 pre-load、autorefresh hover 閃爍、HTML 高亮可能被 sanitize）。
- v2 既有 24 endpoints / 33 perm tests / Alembic 0001-0003 migrations 的迴歸風險。
- **反例**：用 Streamlit components 實作 navigation away 確認 dialog → 8 hr 開不起來。

### 1.4 Feasible（可行性假設）
**核心問句**：在 demo 時程內能做完且不破壞既有嗎？
- 8-24 hr 時間箱 vs 5 必修動作（M1-M5 合計 8 hr 直接做、剩 16 hr 給驗證+部署+迭代）。
- Zeabur deploy 又卡的風險（v2 已踩 webhook stall）。
- **反例**：「順手把 BE 也補 GET /system/config」→ 動 BE = 動 schema + 動 perm test = 拖 8 hr。

### 1.5 假設分類規約

每條假設只標 1 個**主要**類別（最大風險面向），用 `+` 標附加次要類別（最多 1 個）。例如 `V+U`、`B+F`、`B+V`。

---

## Section 2: redesign v3 範疇內的 30+ 假設清單

> **欄位定義**：
> - **信心度 1-5**：1 = 我們完全不知道（純猜測），5 = 已有強證據驗過
> - **風險嚴重度 1-5**：1 = 即使這條錯了，demo 影響可忽略；5 = 這條錯了會直接讓 v3 失敗
> - **finding 引用**：H-x（ux-research Home 痛點）/ D-x（Dashboard）/ DM-x（Data Mgmt）/ A-x（Analytics）/ R-x（Realtime）/ S-x（Admin）/ P0-x（pm-strategy 優先級）/ O-Px-x（codebase-audit open issue）

| ID | 假設陳述 | VUBF | 信心 1-5 | 風險 1-5 | 驗證方法 | 對應 finding |
|---|---|---|---|---|---|---|
| **VA-1** | 評審 5 秒內能在 Home 頁找到「測試帳號 admin/user/viewer」三組，不用回頭翻 README | V+U | 2 | 5 | 用 Eric persona（沒看過系統）開 Home URL 計時，看點擊路徑是否 ≤ 5 秒 | H-1, pm-strategy §4.2 方案 C |
| **VA-2** | 評審 demo 結束後能說出「這套系統有 RBAC 三角色設計」 | V | 2 | 5 | demo 後問評審 narrative 重點，看是否提到 RBAC | P0-1, pm-strategy §6.1 narrative #1 |
| **VA-3** | viewer 登入 30 秒內能說出「我能做什麼 / 不能做什麼」 | V+U | 2 | 5 | 找 1 個沒看過系統的人扮 viewer，計時 + 訪談 | D-1, pm-strategy §6.2 K1 |
| **VA-4** | 加「角色權限矩陣固定卡」到 Dashboard 頂部，不會破壞既有 v2 的 `1_儀表板.py:81-93` system status header layout | B+F | 3 | 4 | 改完後跑 Chrome MCP 截圖 3 角色 × 看 layout 完整性 | pm-strategy §4.3 實作步驟 1-2 |
| **VA-5** | 5 頁 onboarding micro-copy 每頁 ≤ 80 字，1 hr 內 5 頁全寫完 + push | B+F | 4 | 3 | 寫第 1 頁計時，估外推 5 頁 | P0-2, pm-strategy §5.1 M2 |
| **VA-6** | 加 `st.caption()` 不會跟既有 `st.markdown("---")` divider 或 system status header 衝突 | B | 4 | 2 | 在 1 頁試貼後本機跑 streamlit run + Chrome MCP 截圖 | P0-2 |
| **VA-7** | 評審 5 分鐘 demo 內，手動 inject anomaly 按鈕能讓告警卡 / 紅字 cell / 異常 marker 全部觸發 | V+U | 3 | 5 | 加 FE-only mock anomaly 後手動按 3 次 → 截圖驗 anomaly UX 三層全 fire | P0-3, pm-strategy §5.1 M3, §8 mitigation row 2 |
| **VA-8** | 「FE-only mock anomaly」（不打 BE）能讓 buffer 出現假 snapshot，且 anomaly_flags 觸發 Pandas Styler 淡粉紅 row 渲染 | B+F | 2 | 5 | 寫 1 個 mock injector 後印 buffer 內容驗 schema 一致 + 跑 Styler 看 row 是否變粉紅 | P0-3, R-1 |
| **VA-9** | 即時監控頁 fetch `/admin/settings` 拿動態閾值不會踩 viewer/user 角色 403（admin endpoint 守衛）| B | 1 | 5 | curl viewer JWT 打 `/admin/settings` 看 403 還是 200 | R-2, O-P0-1 |
| **VA-10** | 用 plotly `make_subplots(rows=5, cols=1, shared_xaxes=True)` 改即時監控折線圖不會破壞既有 anomaly circle-open red marker 標記邏輯 | B+F | 3 | 4 | 改完後 60 秒實機跑 + 截圖看 anomaly marker 是否在正確 metric subplot 上 | R-1, ux-research Top 10 #2, pm-strategy §1.2 V2 |
| **VA-11** | 5 個 metric 改成 5 張 small multiples subplots 後，整體高度不會超出單屏 → user 不用 scroll 看完整圖 | U | 2 | 3 | Chrome MCP 1080p 截圖看 viewport 內是否完整顯示 5 圖 | R-1 |
| **VA-12** | 把「角色矩陣」從 `5_系統管理.py:88-105` 抽成 `auth.py:render_role_matrix(role)` helper，不會破壞既有 admin tab 的 expander 展示 | B | 4 | 3 | 抽完後 admin 進系統管理頁看矩陣仍能渲染 | pm-strategy §4.3 步驟 1, S-2 |
| **VA-13** | 「Dashboard 頂部當前角色那欄高亮」用 HTML `<td style="background:#fff3cd">` 能在 Streamlit 1.39 `st.markdown(unsafe_allow_html=True)` 正常渲染（不會被 sanitize） | B | 3 | 3 | 寫 1 行測試 HTML → streamlit run → 看是否高亮 | pm-strategy §4.2 方案 A Cons, §8 mitigation row 3 |
| **VA-14** | 修 `delta_color="inverse"` 反語意（4_即時監控.py:196）不會影響其他頁面或測試 | B | 4 | 2 | grep `delta_color="inverse"` 全 repo，逐處 audit | pm-strategy §5.1 M5, R-1 |
| **VA-15** | Pandas Styler 不靜默 fallback 改成 log exception + raise 不會在邊界資料（buffer 空 / 全異常）crash | B | 3 | 3 | 跑 60 秒 + 跑空 buffer 場景 | pm-strategy §5.1 M5, P1-2 |
| **VA-16** | Home 加 3 顆「以 Admin/User/Viewer 登入」按鈕 + auto-submit，不會破壞註冊 tab 既有邏輯 | B+U | 3 | 4 | 加完後本機跑 + 3 顆 + 註冊各跑 1 次 | H-1, ux-research Top 10 #1 |
| **VA-17** | Streamlit 1.39 `st.form_submit_button` 可以用 `st.session_state` 預填 email/password 後 programmatic submit | B | 2 | 4 | 寫 spike：button on_click → set session_state → submit。**不行就改成「點按鈕後自動帶入 email/密碼到 form 欄位，使用者再按一次 submit」**（降為 2-click） | VA-16 同 finding |
| **VA-18** | 評審用 viewer 角色 demo 5 分鐘後，能說出 4/5 大模組名稱（使用者管理 / 資料管理 / 即時監控 / 資料分析 / 系統管理）| V | 2 | 4 | demo 後問 narrative recall test | pm-strategy §6.2 K3 |
| **VA-19** | 即時監控頁預設 multiselect 只選 2-3 條 metric 線（不要全選 5 條）能讓評審第一眼看清楚個別曲線 | U | 3 | 3 | Chrome MCP 截圖預設狀態 vs 5 條全選看視覺差異 | R-1, pm-strategy §2-P1-2 |
| **VA-20** | Zeabur webhook 不會在 v3 push 時又卡住（v2 已踩過） | F | 2 | 5 | M1 完成立刻 push 測 1 次 deploy；若卡用 `ZEABUR_API_TOKEN` + redeployService 自助 | pm-strategy §8 mitigation row 1, feedback_zeabur_push_active_check |
| **VA-21** | 8 hr M1-M5 工時估算正確（不含 Zeabur deploy 等待 + sub-agent 視覺驗收） | F | 3 | 4 | 每 phase 結束計時 + Discord 回報實際耗時 | pm-strategy §7 施工順序 |
| **VA-22** | 加 M4「角色 demo banner」（建議動線提示）能讓評審知道接下來看哪頁，不會被誤解為「app 在強迫導覽」| V+U | 2 | 3 | 寫完後找 1 人測，看是否能 follow 動線 | pm-strategy §5.1 M4 |
| **VA-23** | 「demo banner」用 `st.info()` 而非 modal，不會干擾 admin 反覆操作（admin 已熟系統不需要 banner） | U | 3 | 2 | 加「不要再顯示」checkbox 寫入 session_state | VA-22 |
| **VA-24** | 角色權限矩陣高亮（當前角色）用 markdown bold `**✓**` fallback 對 evaluator 來說仍夠醒目（如果 HTML 高亮失敗）| V+U | 3 | 2 | A/B 截圖人眼判斷 | pm-strategy §8 mitigation row 3 |
| **VA-25** | viewer 在 Dashboard 看到「您是 viewer，建議去即時監控 + 分析報表」會願意 follow（不會反感被引導）| V | 2 | 2 | demo 後訪談 1-2 人 | pm-strategy §6.1 narrative |
| **VA-26** | 既有 v2 33 個 perm test + 41 條需求覆蓋（codebase-audit Section 3）在 v3 動完不會跑紅 | F+B | 3 | 5 | M1-M5 動完後跑 `pytest -v --cov=app` 全綠 | pm-strategy §7 驗證閘 row 1, codebase-audit 需求覆蓋 |
| **VA-27** | v2 已修的 8 個 round 1 bug（codebase-audit Section 6）在 v3 不會 regress | F+B | 4 | 5 | 跑 round 1 fixes 對應的 endpoint curl smoke test | codebase-audit Section 6 |
| **VA-28** | sub-agent 視覺驗收（截圖 5 頁 × 3 角色 = 15 張）可在 1.5 hr 內完成 | F | 3 | 3 | 派 sub-agent 跑 + 計時 | pm-strategy §7 施工順序 hour 8-12, feedback_v6_full_closed_loop |
| **VA-29** | 修 P1-1「Dashboard 重新整理按鈕位置」（從底部移到頂部）值得這 30 min 工時 → ROI 比修 P0 高 | V | 2 | 1 | 跳過此項看評審是否抱怨 | D-4, pm-strategy §2-P1-1 |
| **VA-30** | 修 P1-1「Dashboard 帳號設定 expander 移到右上角 user menu」不會撞到 Streamlit sidebar 衝突 | B | 2 | 2 | spike 1 個 user menu component | D-5 |
| **VA-31** | 灰色地帶 G1「補 DELETE user UI」（5.3 需求缺口）對評審加分 < 1 hr 工時投資 | V+B | 2 | 1 | 跳過此項驗 V-2 是否仍成立 | pm-strategy §5.3 G1, codebase-audit 5.3 |
| **VA-32** | Demo 後評審不會抱怨「分析報表時間趨勢 source=realtime 變成 bar chart」（即不必修 A-2） | V | 2 | 3 | demo 後問 1 個評審 hint「你看 analytics realtime 那張圖正常嗎」 | A-2, ux-research Top 10 #7 |
| **VA-33** | 改密碼 form 兩個入口（Dashboard `1_儀表板.py:222-262` + Admin `5_系統管理.py:208-259`）保留不會被評審當成 bug | V | 3 | 2 | demo 後問 1 個評審「兩個改密碼入口你覺得怪嗎」 | D-5, S-3, ux-research Top 10 不在 |
| **VA-34** | 在 24 hr 時間箱內可以完整跑完 Phase 0-Phase 12（PM/UX/builder/QA/視覺驗收） | F | 3 | 4 | 每 phase 計時實際耗時 vs 預估 | v6.1 Mode A 加強版 SOP |
| **VA-35** | CSV preview / dry-run（ux-research Top 10 #4）在 v3 範疇砍掉，評審不會因為 user persona「上傳 CSV 麻煩」扣分（因為他不會親自試上傳）| V | 4 | 1 | demo 觀察評審是否走 CSV upload 路徑 | DM-1, ux-research Top 10 #4 |
| **VA-36** | 「資料來源」三處 selector 不同步（A-1）在 v3 範疇砍掉，評審不會深入 analytics 三個 toggle | V | 3 | 2 | demo 觀察評審是否在 analytics 頁停超過 2 分鐘 | A-1, ux-research Top 10 #6 |
| **VA-37** | M3 demo 控制 panel 工時 3 hr 不會 overrun 到 6 hr（最大風險項） | F+B | 2 | 4 | 切 sub-tasks 計時，2 hr 過半 escalate 懷特 | pm-strategy §5.1 M3, §7 hour 2.5-5.5 |
| **VA-38** | sub-agent Read 截圖檢視能抓到 v2 既有 UX bug（例如「voltage 線扁成貼底」是不是真的存在於 deploy 環境） | F+V | 3 | 3 | 截 1 張即時監控頁 → sub-agent 描述「voltage 在哪」看是否 detect 出 R-1 | feedback_v6_full_closed_loop, ux-research R-1 |
| **VA-39** | 8 hr 工時切 5 phase（M1-M5）能讓懷特即時看到 phase-by-phase 進度（avoid「8 hr 後一次 PR」） | F | 4 | 2 | 每 phase 完 Discord 通知 + push CC 儀表板 | feedback_self_drive_no_per_phase_approval, pm-strategy §7 |
| **VA-40** | M5 修「delta_color inverse」+ 「Styler fallback」 1 hr 內完成，不會牽動其他 metric / table | B | 3 | 2 | grep 影響範圍 → 改 → 跑 60 秒實機 | P1-1, P1-2, pm-strategy §5.1 M5 |

**合計 40 條假設**（30+ 達標）。

---

## Section 3: 風險優先級矩陣（4 象限）

```
                  ┌─────────────────────┬─────────────────────┐
                  │  信心高（4-5）       │ 信心低（1-3）        │
                  ├─────────────────────┼─────────────────────┤
  風險高（4-5）   │  C 監控               │ A 立即驗              │
                  │                       │                       │
                  ├─────────────────────┼─────────────────────┤
  風險低（1-3）   │  D 略過               │ B 規劃驗              │
                  │                       │                       │
                  └─────────────────────┴─────────────────────┘
```

### A 象限（信心低 + 風險高）— 立即驗（共 16 條）

> 動工前先 spike / curl / 訪談 / 截圖驗，**驗失敗就重排優先級或直接砍**。

- **VA-1**「評審 5 秒內能在 Home 找到測試帳號」（信心 2 / 風險 5）
- **VA-2**「評審 demo 後能說 RBAC」（信心 2 / 風險 5）
- **VA-3**「viewer 30 秒內能說自己能做什麼」（信心 2 / 風險 5）
- **VA-7**「inject anomaly 按鈕能讓告警 / 紅字 / marker 三層 fire」（信心 3 / 風險 5）
- **VA-8**「FE-only mock anomaly 能觸發 Pandas Styler 渲染」（信心 2 / 風險 5）
- **VA-9**「viewer/user 能 fetch `/admin/settings`」（信心 1 / 風險 5）⚠️ **最關鍵**
- **VA-20**「Zeabur webhook 不卡」（信心 2 / 風險 5）
- **VA-26**「v2 33 perm test + 41 需求不 regress」（信心 3 / 風險 5）
- **VA-4**「角色矩陣固定卡不破壞 status header layout」（信心 3 / 風險 4）
- **VA-10**「plotly subplots 不破壞 anomaly marker」（信心 3 / 風險 4）
- **VA-16**「Home 3 顆登入按鈕不破壞註冊 tab」（信心 3 / 風險 4）
- **VA-17**「programmatic form submit 在 Streamlit 1.39 可行」（信心 2 / 風險 4）
- **VA-18**「viewer demo 後能說 4/5 模組」（信心 2 / 風險 4）
- **VA-21**「8 hr 估算正確」（信心 3 / 風險 4）
- **VA-34**「24 hr 跑完 12 phase」（信心 3 / 風險 4）
- **VA-37**「M3 demo panel 3 hr 不 overrun 6 hr」（信心 2 / 風險 4）

### B 象限（信心低 + 風險低）— 規劃驗（共 12 條）

> 動工途中順便驗、不另外排前置 spike，**驗失敗影響可吸收**。

- **VA-5**「5 頁 micro-copy 1 hr 寫完」（信心 4 / 風險 3）→ 實際信心高，挪 D
- **VA-11**「small multiples 不超單屏」（信心 2 / 風險 3）
- **VA-13**「HTML 高亮 Streamlit 不 sanitize」（信心 3 / 風險 3）
- **VA-15**「Styler 不靜默 fallback 在邊界 case 不 crash」（信心 3 / 風險 3）
- **VA-19**「multiselect 預設 2-3 條讓評審看清」（信心 3 / 風險 3）
- **VA-22**「demo banner 不會被誤解為強迫導覽」（信心 2 / 風險 3）
- **VA-28**「sub-agent 視覺驗收 1.5 hr 完成」（信心 3 / 風險 3）
- **VA-32**「不修 A-2 評審不抱怨」（信心 2 / 風險 3）
- **VA-38**「sub-agent Read 截圖能 detect UX bug」（信心 3 / 風險 3）
- **VA-12**「render_role_matrix helper 不破壞 admin tab」（信心 4 / 風險 3）→ 信心高，挪 D
- **VA-24**「markdown bold fallback 夠醒目」（信心 3 / 風險 2）
- **VA-25**「viewer 不反感被引導」（信心 2 / 風險 2）

### C 象限（信心高 + 風險高）— 監控（共 1 條）

> 信心高但風險高 = 動工途中要持續 sanity check，不要假設「過去沒事就不會出事」。

- **VA-27**「8 個 round 1 bug 不 regress」（信心 4 / 風險 5）→ M1-M5 後跑 round 1 smoke test

### D 象限（信心高 + 風險低）— 略過（共 11 條）

> 不額外驗，動工中順手。

- **VA-5**（micro-copy 1 hr）— 經驗值
- **VA-6**（`st.caption` 不撞 divider）
- **VA-12**（render_role_matrix helper）
- **VA-14**（`delta_color="inverse"` 修補不影響他處）
- **VA-23**（`st.info()` 而非 modal）
- **VA-29**（「重新整理」按鈕位置 ROI 低）
- **VA-30**（user menu 不撞 sidebar）
- **VA-31**（DELETE user UI 加分有限）
- **VA-33**（兩個改密碼入口可接受）
- **VA-35**（評審不會試 CSV upload）
- **VA-36**（評審不會深入 analytics toggle）
- **VA-39**（phase-by-phase Discord 通知）
- **VA-40**（M5 1 hr 完成）

**象限分布**：A:16 / B:12 / C:1 / D:13（共 42 含重複分類）。實際 40 條假設。

---

## Section 4: De-risk 行動建議（Top 10 A 象限「立即驗」）

> 按「驗失敗的傷害 × 驗證成本」排序，從動工前最該先驗的開始。

### #1 — VA-9「viewer/user 能 fetch `/admin/settings`」（信心 1 / 風險 5）

- **為什麼最高優先**：信心最低（1）+ 風險最高（5）的單一假設。R-2「閾值寫死前端」是 M3 demo panel 核心修補項，若 `/admin/settings` 對非 admin 角色直接 403，整個動態閾值同步方案就崩盤。
- **驗證實驗**：
  1. 取 viewer 角色 JWT（用 seed `viewer@example.com / viewer123` 登入）
  2. `curl -H "Authorization: Bearer $JWT" https://<zeabur-url>/api/v1/admin/settings`
  3. 看回傳是 200 / 403 / 401
- **預估工時**：15 分鐘
- **失敗退場方案**：
  - 若 403 → BE 新增 `/api/v1/system/config`（不含 admin-only fields）唯讀 endpoint 給 viewer/user 用 → 此舉動 BE → 違反「不動 BE」原則 → 需懷特核可
  - 替代方案：FE hardcode 仍保留但加 caption「閾值來自系統設定（admin 改設定後 1 分鐘生效）」，30 秒重新整理時 admin 才 fetch refresh

### #2 — VA-20「Zeabur webhook 不卡」（信心 2 / 風險 5）

- **為什麼**：v2 已踩過 webhook stall 卡 30 分鐘，再卡會吃掉 24 hr 時間箱 1/4。
- **驗證實驗**：
  1. M1（角色矩陣卡片 + Home 試用帳號）完成後立刻 git push
  2. 5 分鐘內查 Zeabur dashboard 看是否新 deployment running
  3. 若沒 fire → 用 `$ZEABUR_API_TOKEN` + `redeployService` 自助觸發（依 `reference_zeabur_api_self_service`）
- **預估工時**：5 分鐘驗 + （若卡）10 分鐘自助
- **失敗退場方案**：Discord 升級懷特手動 redeploy；同時 M2-M5 繼續 local dev 不被 block

### #3 — VA-1「評審 5 秒內能找到測試帳號」+ VA-16「Home 3 顆登入按鈕」+ VA-17「programmatic submit」（合併驗）

- **為什麼**：3 條相互依賴（VA-16 / VA-17 是 VA-1 的實作 dependency），驗 1 條等於驗 3 條。
- **驗證實驗**：
  1. spike：在本地 `Home.py` 加 3 顆按鈕 + on_click 設 session_state + `st.rerun()` 觸發 form
  2. Chrome MCP 開 Home → 截圖 → 看 3 顆按鈕是否在 form 上方第一屏
  3. 點「以 Admin 登入」→ 觀察是否自動跳到 Dashboard（成功 = 全自動，降級 = 帶入 email/密碼後再點 submit）
- **預估工時**：30 分鐘
- **失敗退場方案**：
  - 若 programmatic submit Streamlit 1.39 不支援 → 降級為「按鈕點下去自動填 email/密碼到 form 欄位 + Snackbar 提示『請按 Sign In』」（2-click，仍比看 README 快）

### #4 — VA-8「FE-only mock anomaly 觸發 Styler」+ VA-7「三層 anomaly UX 全 fire」

- **為什麼**：M3 核心方案 demo panel 的可行性依賴這條。若 FE-only mock 無法觸發 Pandas Styler，就要動 BE inject anomaly endpoint → 違反「不動 BE」。
- **驗證實驗**：
  1. 寫 1 個 `_mock_anomaly_snapshot()` helper 構造 fake snapshot 塞進 buffer：
     ```python
     fake = {
         "schema_version": "v2",
         "ts": datetime.utcnow().isoformat() + "Z",
         "metrics": {"temperature": 200.0, "humidity": 50.0, ...},
         "anomaly_flags": {"temperature": True, ...},
     }
     st.session_state.realtime_buffer.appendleft(fake)
     ```
  2. 跑 streamlit run 後手動按 inject → 看 (1) 告警卡是否 fire (2) Styler 淡粉紅 row (3) 折線圖 anomaly circle marker
- **預估工時**：45 分鐘
- **失敗退場方案**：
  - 若 Styler 不認 mock snapshot → 改成「即時監控頁加 demo 模式 toggle，按下後 anomaly_threshold 暫時調超低（前端模擬），讓真實 simulator tick 都觸發異常」
  - 若三層 UX 都 fire 但太假（時間戳是未來）→ 用 `datetime.utcnow() - timedelta(seconds=1)`

### #5 — VA-10「plotly subplots 不破壞 anomaly marker」

- **為什麼**：ux-research Top 10 #2 致命傷修補的核心，若改成 small multiples 後 anomaly circle-open red marker 跑掉 / 失準，等於修一個破一個。
- **驗證實驗**：
  1. spike：複製 `4_即時監控.py:214-264` 到一個 mini script
  2. 改成 `make_subplots(rows=5, cols=1, shared_xaxes=True)`
  3. 加 anomaly marker（`scatter_kwargs = dict(mode="markers", marker_symbol="circle-open", marker_color="red")`）
  4. 跑 60 秒模擬資料看 marker 是否在對應 subplot 上
- **預估工時**：1 hr
- **失敗退場方案**：
  - 若 anomaly marker 在 subplot 內錯位 → 降級為 dual y-axis（只 split 出 pressure 獨立軸，其他 4 個共軸）
  - 或保持單張圖但 normalize 到 0-100 + 加 yaxis_title 註明「已正規化」

### #6 — VA-26「v2 33 perm test + 41 需求不 regress」+ VA-27「8 個 round 1 bug 不 regress」（合併）

- **為什麼**：迴歸風險是 v3 最大威脅。
- **驗證實驗**：
  1. M1-M5 動完後跑 `pytest -v --cov=app` 全綠
  2. curl smoke test round 1 8 個 bug 對應 endpoint：
     - `/auth/login` w/ short password（D-block-1）
     - `/realtime/history`（D-block-2）
     - `/analytics/unified-summary`（D-block-3）
     - `/ws/realtime`（BUG #6）
     - `/admin/logs`（D-HIGH-2）
     - `/admin/realtime-history`（D-HIGH-5）
- **預估工時**：30 分鐘
- **失敗退場方案**：
  - 若 pytest 紅 → 立刻 git diff M1-M5 看哪個改動破了 perm test，rollback 或修
  - 若 smoke test 紅 → 對應 endpoint 個別調

### #7 — VA-2「評審 demo 後能說 RBAC」+ VA-3「viewer 30 秒能說自己權限」（合併）

- **為什麼**：M1 角色矩陣卡片的核心 V 假設。
- **驗證實驗**：
  1. M1 完成後找 1 個沒看過系統的人（懷特同事 / 朋友）扮 viewer 登入
  2. 計時 30 秒 → 問「你看到這頁，你覺得自己能做什麼 / 不能做什麼？」
  3. 同時問「這系統有幾個角色？」
- **預估工時**：10 分鐘（含 onboarding 給測試者）
- **失敗退場方案**：
  - 若 30 秒內說不出來 → 把矩陣卡片從 markdown table 改成「視覺 chip badge」（綠勾/紅叉大 emoji）
  - 若說「系統只有一個角色」 → 加 onboarding modal 在第一次登入時彈

### #8 — VA-21「8 hr M1-M5 估算正確」+ VA-37「M3 demo panel 3 hr 不 overrun」

- **為什麼**：時間箱風險。M3 是最複雜項（FE-only mock + secondary y-axis + 動態閾值 fetch + 預設線數），3 hr 估算最容易爆。
- **驗證實驗**：
  1. M3 切 4 sub-task：(a) mock anomaly injector 45 min (b) plotly subplots 1 hr (c) `/admin/settings` fetch + cache 30 min (d) 預設線數 + audit 15 min
  2. 每 sub-task 完成計時 → 過 2 hr 完成不到 50% → Discord 升級懷特
- **預估工時**：3 hr（含監控本身）
- **失敗退場方案**：
  - 若 M3 over 4 hr → 砍 (b) plotly subplots（保留 v2 共軸）只做 (a)+(c)+(d)
  - 若 over 5 hr → 全砍 M3，靠 M1+M2+M4+M5 撐

### #9 — VA-4「角色矩陣固定卡不破壞 status header layout」+ VA-13「HTML 高亮 Streamlit 不 sanitize」（合併）

- **為什麼**：M1 實作層風險。
- **驗證實驗**：
  1. 寫 1 行 `st.markdown("<table><tr><td style='background:#fff3cd'>test</td></tr></table>", unsafe_allow_html=True)` 看高亮是否渲染
  2. 把 render_role_matrix() 插入 1_儀表板.py:41 之後、43 之前看 status header 是否完整
  3. Chrome MCP 截圖 3 角色 × 看 layout
- **預估工時**：20 分鐘
- **失敗退場方案**：
  - 若 HTML 被 sanitize → 用 markdown bold `**✓**` 當高亮（VA-24 已備案）
  - 若 status header 被擠壓 → 角色矩陣放 `1_儀表板.py:78` 之前（status header 之上）

### #10 — VA-34「24 hr 跑完 12 phase」+ VA-39「phase-by-phase Discord 通知」（合併）

- **為什麼**：整體時程 + 透明度風險。
- **驗證實驗**：
  1. 每 phase 完 Discord 通知（不只「done」，含實際耗時 vs 預估）
  2. CC 儀表板 push phase status
  3. Phase 4 結束時若已超預估 1.5x → 重新評估剩餘 phase 是否砍項
- **預估工時**：phase 完計時，每次 5 分鐘
- **失敗退場方案**：超時就砍灰色地帶 G1-G3 + 砍 M5 中的 Styler fallback fix（保留 delta_color fix 即可）

---

## Section 5: 不會驗的「接受性假設」

> 明列「我們接受不驗、出狀況再說」的假設，並說明為何接受。

### AC-1 — 接受「Streamlit autorefresh 1 秒 rerun 造成 hover tooltip 閃爍」

- **為什麼接受**：v2 已踩過、加 `uirevision`（design.md:262）已部分緩解，再深入要改用 Plotly Dash / React → 違反「保留 Streamlit」原則。
- **退場條件**：若評審 demo 中 explicit 抱怨「圖一直閃」才考慮 v4 處理。

### AC-2 — 接受「即時監控頁與系統管理 Tab 4『即時資料歷史』邏輯重複」

- **為什麼接受**：抽 shared component 需要 ≥ 2 hr，v3 範疇 ROI 太低；評審不太會同時打開兩頁對比。
- **退場條件**：若評審指出 → 紀錄為 v4 maintenance debt。

### AC-3 — 接受「Excel 匯出兩步點擊（準備 → 下載）」

- **為什麼接受**：Streamlit `download_button` 必須 pre-load data（框架限制），改 on-demand fetch 用 callback 是 v1.39 實驗性 API，1 hr 內難穩定。
- **退場條件**：v4 升 Streamlit 後再優化。

### AC-4 — 接受「資料管理 inline edit 沒 dirty state，切頁丟資料」

- **為什麼接受**：navigation away 確認 dialog 在 Streamlit 需 hack JS components（≥ 1 day 工時）。
- **退場條件**：若評審試 inline edit 後切頁抱怨「我改的怎麼沒了」→ v4 補。

### AC-5 — 接受「CSV upload 沒 preview / dry-run」

- **為什麼接受**：B user persona 的 pain，但**評審 Eric persona 不會試上傳 CSV**（demo 5-10 分鐘窗口不會走這條 path）。
- **退場條件**：若評審 explicit 試 → 紀錄為 v4 補。

### AC-6 — 接受「分析報表 source=realtime 變成 bar chart（語意不符）」

- **為什麼接受**：A-2 修補要動 backend 加 realtime time-range bucket API（≥ 1 day），ROI 太低。
- **退場條件**：若評審指出 → 改 subheader 為「分佈圖」字串修補（5 min fix），不動圖表類型。

### AC-7 — 接受「Plotly 截圖會抓到 toolbar（viewer 截圖貼週報 friction）」

- **為什麼接受**：viewer persona 不是評審。`config={"displayModeBar": False}` 改動低風險但 ROI 在 v3 demo 場景幾乎 0。
- **退場條件**：v4 加 config 一行修補。

### AC-8 — 接受「DB pool status 沒 baseline 紅黃綠」

- **為什麼接受**：admin persona 的 pain，但 demo 場景評審不會深入到 DB pool tab。
- **退場條件**：v4 補 derived metric「使用率 %」。

### AC-9 — 接受「系統設定 5 個 setting 各自獨立 form」

- **為什麼接受**：admin 月度調參才會踩，demo 場景不會。
- **退場條件**：v4 整合為單一 form。

### AC-10 — 接受「DELETE user UI 缺口」（5.3 需求差）

- **為什麼接受**：BE endpoint 已有，FE 加 button + confirmation modal 要 ≥ 1 hr。灰色地帶 G1。
- **退場條件**：若 M1-M5 在 6 hr 內結束 + 還有時間 → 灰色地帶開做。

---

## Section 6: 跨假設依賴鏈

> A 才能驗 B 的 dependency；驗證順序錯了會白費工。

### 鏈 1: M3 demo panel 可行性鏈

```
VA-9 (viewer 能 fetch /admin/settings)
   └─→ VA-8 (FE-only mock anomaly 觸發 Styler)
          └─→ VA-7 (三層 anomaly UX 全 fire)
                 └─→ VA-37 (M3 3 hr 不 overrun)
                        └─→ VA-21 (8 hr M1-M5 估算正確)
                               └─→ VA-34 (24 hr 完整跑完)
```

**驗證順序**：必須 VA-9 先（curl 一發），失敗就改設計；過了才驗 VA-8（spike mock injector）；過了才動 VA-7 整合；最後 VA-37/21/34 是時間箱監控。

### 鏈 2: M1 角色矩陣卡片可行性鏈

```
VA-13 (HTML 高亮 Streamlit 不 sanitize)
   └─→ VA-4 (角色矩陣固定卡不破壞 status header)
          └─→ VA-12 (render_role_matrix helper 不破壞 admin tab)
                 └─→ VA-3 (viewer 30 秒能說自己權限)
                        └─→ VA-2 (評審 demo 後能說 RBAC)
```

**驗證順序**：VA-13 是技術層 prerequisite（1 行 spike），失敗用 VA-24 markdown bold fallback；VA-4 是 layout 層；VA-3/VA-2 是 user testing 層必須等實作完才驗。

### 鏈 3: Home 試用帳號可行性鏈

```
VA-17 (Streamlit 1.39 programmatic submit 可行)
   └─→ VA-16 (3 顆登入按鈕不破壞註冊 tab)
          └─→ VA-1 (評審 5 秒能找到測試帳號)
                 └─→ VA-18 (viewer demo 後能說 4/5 模組)
```

**驗證順序**：VA-17 是技術層 prerequisite，失敗降級 2-click；VA-16 layout 層；VA-1 是 user testing 層。

### 鏈 4: 即時監控 plotly subplots 鏈

```
VA-10 (plotly subplots 不破壞 anomaly marker)
   └─→ VA-11 (small multiples 不超單屏)
          └─→ VA-19 (預設 multiselect 2-3 條讓評審看清)
```

**驗證順序**：VA-10 先 spike，失敗降級為 dual y-axis；過了才考慮 VA-11/VA-19。

### 鏈 5: 部署驗收鏈

```
VA-20 (Zeabur webhook 不卡)
   └─→ VA-26 (v2 perm test + 41 需求不 regress)
          └─→ VA-27 (8 個 round 1 bug 不 regress)
                 └─→ VA-28 (sub-agent 視覺驗收 1.5 hr 完成)
                        └─→ VA-38 (sub-agent Read 截圖能 detect UX bug)
```

**驗證順序**：VA-20 早期驗（M1 push 後）；VA-26/27 全程跑（每 phase 後 pytest）；VA-28/38 deploy 後驗。

---

## Section 7: 給懷特的決策清單

> 需要懷特拍板的二選一決策，每個附選項 + 對應假設 + 我的建議 + 理由。

### Q1: M3 demo panel「FE-only mock anomaly」vs「BE 加 inject endpoint」

- **選項 A（推薦）**：FE-only，加 `_mock_anomaly_snapshot()` helper 塞進 session_state buffer
- **選項 B**：BE 加 `POST /admin/inject-anomaly` endpoint（admin only），更真實
- **對應假設**：VA-7 / VA-8 / VA-9 / VA-26
- **我的建議**：**選 A**
- **Why**：選 B 動 BE = 動 perm test = VA-26 風險飆高 + 動 schema 可能讓既有 round 1 修補 regress（VA-27）。選 A 雖然較假但 demo 視覺效果一樣，且不影響 BE 完整性。pm-strategy §8 mitigation row 2 已建議 A。

### Q2: 角色矩陣顯示位置「Dashboard 頂部固定卡片」vs「全頁面 sidebar 永久顯示」

- **選項 A（推薦）**：方案 A，Dashboard 頂部 `st.container(border=True)` + 加 Home 試用帳號 expander
- **選項 B**：方案 B，全頁面 sidebar 永久顯示 chip badge
- **對應假設**：VA-2 / VA-3 / VA-4 / VA-12 / VA-13
- **我的建議**：**選 A**
- **Why**：pm-strategy §4.3 已論述 sidebar 不可靠（Streamlit Cloud 行動裝置預設收起）；A 加上 C 部分（Home 試用帳號 expander）能 cover「未登入評審看不到 RBAC」+「登入後三角色都看到」雙重目標。

### Q3: 工時箱「8 hr 直接動」vs「先用 1.5 hr 驗 Top 10 A 象限假設再動」

- **選項 A**：直接 M1-M5 動，遇到問題現修
- **選項 B（推薦）**：先用 1.5 hr 驗 Section 4 Top 5 A 假設（VA-9 + VA-20 + VA-1/16/17 + VA-8/7 + VA-10），驗過了才動
- **對應假設**：VA-21 / VA-34 / VA-37 / Section 4 全部
- **我的建議**：**選 B**
- **Why**：投資 1.5 hr de-risk vs 動到一半發現 VA-9 失敗（`/admin/settings` viewer 403）整個 M3 設計重做要 6 hr+。提前驗的 ROI 是 4x。pm-strategy §7 hour 0-1.5 原本就是 M1，可改成 hour 0-1.5 = 驗證 + M1 sub-task spike，**整體不會延遲**。

### Q4: 砍項策略「先動全部 M1-M5 後砍」vs「動工前先砍 M5」

- **選項 A**：M1-M5 全動，超時再砍
- **選項 B**：動工前砍 M5（delta_color + Styler fix），M1-M4 集中火力
- **對應假設**：VA-21 / VA-40 / AC-7
- **我的建議**：**選 A，但 M5 sub-tasks 拆細**
- **Why**：M5 1 hr 工時不算多，且 `delta_color="inverse"` 是 P1-1 評審第一印象殺手「為什麼 +50 是綠色」（pm-strategy §6.3 反指標）。砍掉風險高。但內部把 M5 拆成 (a) delta_color 30 min (b) Styler logging 30 min，到時間箱壓力大就砍 (b)。

### Q5: 灰色地帶 G1-G3「補」vs「不補」

- **選項 A**：若 M1-M5 在 6 hr 內完 → 補 G1（DELETE user UI）+ G2（secondary y-axis） + G3（改密碼 UI 二合一）
- **選項 B（推薦）**：M1-M5 完不超時的話，補 G2 only（plotly secondary y-axis），G1 / G3 留 v4
- **對應假設**：VA-31 / VA-33 / VA-37
- **我的建議**：**選 B**
- **Why**：G2 是 R-1 致命傷的延伸修補（VA-10 若驗失敗的 fallback path），ROI 高；G1 對 V 假設加分有限（VA-31 風險 1）；G3 兩個改密碼入口可接受（VA-33 風險 2）。

---

## §結語：給 builder 的「動工順序」（基於本 assumption mapping）

```
Hour 0 - 1.5：先驗 Top 10 A 象限假設（Section 4 #1-#5）
   ├─ VA-9 (15 min)：curl viewer JWT /admin/settings
   ├─ VA-20 (5 min)：先 push 一個 trivial commit 看 Zeabur webhook
   ├─ VA-1/16/17 (30 min)：Home 3 顆按鈕 spike
   ├─ VA-8/7 (45 min)：FE-only mock anomaly spike
   └─ VA-10 (1 hr)：plotly subplots + anomaly marker spike

Hour 1.5 - 3：M1（角色矩陣卡 + Home 試用帳號 expander）
   ├─ Section 4 #9 同時驗（VA-4 + VA-13）

Hour 3 - 4：M2（5 頁 micro-copy，並行 sub-agent）

Hour 4 - 7：M3（demo panel + secondary y-axis + 預設線數）
   ├─ Section 4 #8 同時監控（VA-21 + VA-37）

Hour 7 - 8.5：M4（角色 demo banner）

Hour 8.5 - 9.5：M5（delta_color + Styler logging）

Hour 9.5 - 11：Section 4 #6 驗收（pytest + smoke test）+ VA-27 round 1 不 regress

Hour 11 - 12.5：Section 4 #7 user testing（VA-2 / VA-3）

Hour 12.5 - 14：sub-agent 視覺驗收（VA-28 / VA-38）

Hour 14 - 24：迭代 + Zeabur deploy 確認 + 灰色地帶 G2 + Discord 回報懷特
```

**核心訊息**：投 1.5 hr 驗最關鍵 5 條假設，能讓後續 22.5 hr 減少 ~50% 重做風險。

---

ASSUMPTION MAPPING DONE
