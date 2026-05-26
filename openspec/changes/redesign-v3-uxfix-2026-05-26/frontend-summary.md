# Frontend Summary — B.1+B.2 Sprint 1（Story #1 + Story #2）

**Date**：2026-05-26
**Agent**：frontend-engineer sub-agent
**Worktree**：`.claude/worktrees/agent-abb8c7748fca9d68b`
**Tasks completed**：B.1.1 / B.1.2 / B.2.1

---

## 改動的 component / page / state

### B.1.1 — auth.py：新增 render_role_matrix() helper

**File**：`frontend/streamlit_app/auth.py`
**改動位置**：line 93–136（append 44 行在 current_role() 之後）

新增 `render_role_matrix(role: str) -> None` pure function：

- 讀取 `role` 參數，對應中文角色描述（admin/user/viewer）
- `st.markdown(f"**您目前的角色：{role_display}**")` 顯示角色標題行
- 內部 `_c(col_role, mark)` helper：若 col_role == 當前 role，回傳 `**mark**`（粗體）否則原樣
- 完整 13 行 × 3 角色 markdown table，當前角色欄全 mark 用粗體顯示
- 13 項操作：登入/查看儀表板/即時監控/分析報表/資料管理/新增/編輯自己/編輯他人/刪除自己/刪除他人/批量匯入/存取系統管理/管理使用者角色

設計選擇（VA-13 spike 結論）：
- 禁 HTML `unsafe_allow_html` 注入（Streamlit sanitize 風險）
- 改用 markdown `**粗體 ✓**` 作安全 fallback 高亮

### B.1.1 — 5_系統管理.py：expander expanded=False → True

**File**：`frontend/streamlit_app/pages/5_系統管理.py`
**改動位置**：line 88

- `expanded=False` → `expanded=True`（不刪既有 expander，只改預設展開狀態）
- 對應 Story #2 AC-5：admin 進系統管理頁，矩陣 expander 預設展開

### B.1.2 — Home.py：試用帳號 expander + 3 顆按鈕（Plan B query_params）

**File**：`frontend/streamlit_app/Home.py`
**改動位置**：line 16–71（新增 55 行）

按 spike A.3 結論走 Plan B（query_params zero-click，而非 Plan A session_state programmatic submit）：

**`_DEMO_ACCOUNTS` dict**（line 17–21）：
- admin → admin@example.com / admin123
- user → user@example.com / user123
- viewer → viewer@example.com / viewer123

**query_params 自動登入邏輯**（line 23–35，在 require_auth 之前）：
- `st.query_params.get("demo_login")` 取角色名
- 若在 `_DEMO_ACCOUNTS` 中 → `st.query_params.clear()` 防重複觸發 → `login(email, password)` 直接呼叫 → 成功後 `st.switch_page("pages/1_儀表板.py")`
- 失敗顯示 `st.error`

**試用帳號 expander**（line 44–69，在 `st.tabs` 之前）：
- `st.expander("試用帳號（Demo 用，點按鈕直接登入）", expanded=True)`
- `st.caption("...")` 說明
- markdown table 顯示三組帳號（email + 密碼明文，AC edge case 5 已接受）
- `st.columns(3)` 內三顆按鈕：`key="login_as_admin/user/viewer"`
- 按鈕 on_click → `st.query_params.update(demo_login="admin/user/viewer")` + `st.rerun()`

AC 覆蓋：
- AC-1：expander 預設展開，列三組帳號 ✓
- AC-2：點按鈕 → query_params → rerun → 自動呼叫 login() → zero-click 等同按下登入 ✓
- AC-3：登入成功 → switch_page Dashboard ✓
- AC-4：原有 form 登入邏輯不動，expander 放 st.tabs 之前不干擾 ✓
- AC-5：密碼明文顯示（設計接受）✓
- Edge case 試用帳號不出現在註冊 tab：expander 在 st.tabs 之外 ✓

### B.2.1 — 1_儀表板.py：插入 render_role_matrix(role)

**File**：`frontend/streamlit_app/pages/1_儀表板.py`
**改動位置 1**：line 12，import 加 `render_role_matrix`
**改動位置 2**：line 43–46，在 `st.markdown("---")` 之後、`# D2-4 System status header` 之前插入

```python
with st.container(border=True):
    render_role_matrix(role)
```

Layout 保全：
- 矩陣卡片插在 `st.markdown("---")` 之後（line 41），status header 之前（line 48+）
- 既有 status_col1/2/3 + metric cards + data tabs 全部在矩陣下方正常顯示
- `border=True` 使矩陣視覺上有外框卡片感

---

## Backend API 使用（cross-reference backend-summary）

Story #1 query_params demo_login 端對端資料流（按 design.md Section 4 Story #1 5 段對照）：

| 段 | 內容 |
|---|---|
| FE 送 | POST `/api/v1/auth/login` body `{"email": "viewer@example.com", "password": "viewer123"}` |
| BE 收 | LoginRequest schema，驗 password hash（round 1 已移除 8 字元最小長度 validator） |
| DB 存 | （只讀）users table seed user |
| BE 回 | `{"access_token": "<jwt>", "token_type": "bearer"}` → 後續 GET `/auth/me` 回 user dict |
| FE 顯示 | auth.py:37,51 寫 session_state["token"] + ["user"] → st.switch_page Dashboard |

Story #2 render_role_matrix 端對端資料流：
- 純前端渲染，無 API call，讀 `st.session_state["user"]["role"]`（已存在於登入後 session）

---

## 處理的 edge case / 失敗 path

1. **VA-17 programmatic submit 失敗**：spike A.3 已確認，直接走 Plan B query_params，不依賴 form submit mechanism
2. **query_params 重複觸發**：`st.query_params.clear()` 在呼叫 login() 之前執行，防止 rerun 時再次觸發
3. **demo login 失敗**：顯示 `st.error(f"登入失敗：{_message}")`，不 silent fail（edge case AC-5）
4. **VA-13 HTML 高亮 sanitize 風險**：直接走 markdown bold fallback，不嘗試 HTML
5. **試用帳號出現在註冊 tab**：expander 放在 `st.tabs` 外部（公共區），兩個 tab 都看不到（只在 tabs 之前的公共區渲染）
6. **role 不在已知三值**：`_ROLE_ZH.get(role, role)` fallback 顯示原始 role 字串；`_c()` 不會高亮任何欄（三個 col_role 都不 match）

---

## Grep 驗證結果

```
grep "def render_role_matrix" auth.py            → 93: def render_role_matrix(role: str) -> None: ✓
grep "st.query_params" Home.py                   → lines 25, 29, 59, 63, 67 ✓
grep "render_role_matrix(role)" 1_儀表板.py       → line 46: render_role_matrix(role) ✓
grep "expanded=True" 5_系統管理.py 角色欄           → line 88: expanded=True ✓
```

---

## 跑的 test 結果

本次 Sprint 1 B.1+B.2 為純前端改動，不動 BE 任何程式碼：
- BE pytest 不受影響（不動 backend/ 目錄）
- Streamlit 本機 run 需 BACKEND_URL env（不強制 local run，設計文件 AC 已接受）
- 三個 grep 驗證全 pass（見上方）

---

B.1+B.2 DONE
