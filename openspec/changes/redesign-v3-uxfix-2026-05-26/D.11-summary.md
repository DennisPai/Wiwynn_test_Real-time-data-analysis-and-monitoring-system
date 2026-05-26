# D.11-summary — Story #11 系統管理頁面 4 個 P1 痛點修補

**Date**: 2026-05-26
**Agent**: frontend-engineer
**File**: `frontend/streamlit_app/pages/5_系統管理.py`

---

## 修補清單

### 修補 1 — Audit log limit 從 20 → 50（預設）+ caption

**file:line**: `5_系統管理.py:317` (caption) + `5_系統管理.py:322` (selectbox index)

**Before**:
```python
# No caption above expander
log_page_size = st.selectbox("每頁筆數", [20, 50, 100], index=0, key="log_size")
# index=0 → default 20
```

**After**:
```python
st.caption("Audit log 預設顯示前 50 筆。若需更早記錄請使用上方日期篩選縮小範圍。")
# ...expander...
log_page_size = st.selectbox("每頁筆數", [20, 50, 100], index=1, key="log_size")
# index=1 → default 50
```

**說明**: Backend `GET /admin/logs` 接受 `size` 參數（`size: int = Query(20, ge=1, le=100)`），FE 已透過 `_fetch_logs(page, size, ...)` 傳遞，只需更改 selectbox default index。Caption 加在 expander 上方。

---

### 修補 2 — Settings expander 預設折疊 + 展開全部 toggle button

**file:line**: `5_系統管理.py:610-617` (toggle block) + `5_系統管理.py:640` (expander)

**Before**:
```python
# No toggle button
with st.expander(f"設定項目：{key}", expanded=True):
```

**After**:
```python
# Settings expander toggle（v3 Story #11 AC-2）
if "settings_all_expanded" not in st.session_state:
    st.session_state["settings_all_expanded"] = False

toggle_label = "收合全部" if st.session_state["settings_all_expanded"] else "展開全部設定"
if st.button(toggle_label, key="settings_toggle_expand"):
    st.session_state["settings_all_expanded"] = not st.session_state["settings_all_expanded"]
    st.rerun()
# ...
with st.expander(f"設定項目：{key}", expanded=st.session_state.get("settings_all_expanded", False)):
```

**說明**: `session_state["settings_all_expanded"]` 初始為 `False`（全部折疊）。toggle button 切換時呼叫 `st.rerun()` 以反映 expander 狀態。按鈕標籤依狀態動態顯示「展開全部設定」/「收合全部」。

---

### 修補 3 — DELETE user UI

**file:line**: `5_系統管理.py:207-249`（新增區塊）

**Before**: 無 DELETE 功能，僅有「更新使用者」button。

**After**:
```python
# v3 Story #11 AC-3：刪除使用者（DELETE /users/{id}）
st.markdown("---")
st.subheader("刪除選定使用者")

_selected_uid = selected_user_item.get("id")
_current_uid = user.get("id")
_is_self = (_selected_uid == _current_uid)

if _is_self:
    st.warning("不可刪除自己的帳號。請選擇其他使用者。")
    st.button("刪除選定使用者", key="u_delete_btn", type="secondary", disabled=True)
else:
    _confirm_delete = st.checkbox(
        f"確認刪除 {selected_user_item.get('email', '')}（不可復原）",
        key="u_delete_confirm",
    )
    if st.button("刪除選定使用者", key="u_delete_btn", type="secondary", disabled=not _confirm_delete):
        _del_resp = client.delete(f"/users/{_selected_uid}")
        if _del_resp.status_code in (200, 204):
            st.success(f"已刪除使用者 {selected_user_item.get('email', '')}。")
            st.cache_data.clear()
            st.rerun()
        elif _del_resp.status_code == 404:
            st.error("此使用者已被刪除。")
            st.cache_data.clear()
            st.rerun()
        else:
            ...
            st.error(f"刪除失敗：{_detail}")
```

**端對端資料流**:
- FE 送: `DELETE /api/v1/users/{id}` + Authorization Bearer JWT
- BE 收: `backend/app/api/v1/users.py:93-106` `delete_user()` → AdminOnly guard
- DB: `users` table DELETE row
- BE 回: 204 No Content（或 404 若不存在）
- FE 顯示: 204 → `st.success` + `st.cache_data.clear()` + `st.rerun()`

**守衛邏輯**:
- `_is_self = (_selected_uid == _current_uid)` → 自己時 button `disabled=True` + warning
- 他人時需勾選確認 checkbox 才 enable 刪除按鈕
- 404 → `st.error("此使用者已被刪除")` + 清快取重跑

---

### 修補 4 — 確認 Sprint 1 改動仍在

**file:line**: `5_系統管理.py:90`

```python
# D6-4: 角色權限說明 markdown table（v3 預設展開，配合 Story #2）
with st.expander("角色權限說明", expanded=True):
```

Sprint 1 改動完整保留，`expanded=True` 未倒退。

---

## 使用 backend API endpoints

| Endpoint | 位置 | 用途 |
|---|---|---|
| `GET /admin/logs?size=50` | admin.py:38-78 | Audit log 分頁（預設 50 筆） |
| `DELETE /users/{id}` | users.py:93-106 | 刪除使用者 |
| `GET /admin/settings` | admin.py:169-177 | 系統設定列表（既有） |
| `PATCH /admin/settings/{key}` | admin.py:180+ | 更新設定值（既有） |

---

## Edge Cases 處理

| Edge Case | 處理方式 |
|---|---|
| 刪除自己 | `_is_self` guard → button disabled + `st.warning` |
| 404（已被他人刪） | `st.error("此使用者已被刪除")` + cache clear + rerun |
| 其他 HTTP 錯誤 | try/except json.get("detail") + `st.error` |
| Settings expander 狀態 | session_state 初始 False，toggle 切換後 rerun 同步 |
| Audit log 選項 | selectbox `[20, 50, 100]` 保留靈活性，default 改為 50 |

---

## 測試結果

- Sprint 1 既有改動確認未倒退：`expanded=True` 角色矩陣 expander 在 line 90，完整保留
- BE `DELETE /users/{id}` endpoint 確認存在：`users.py:93-106`，返回 204，已有 AdminOnly guard
- BE `GET /admin/logs` 確認支援 `size` param：`admin.py:44`，`size: int = Query(20, ge=1, le=100)`，最高 100
- `client.delete()` 方法確認存在：`api_client.py:118-128`
- 無新 endpoint 發明，全部 cross-reference backend-summary endpoints

---

D.11 DONE
