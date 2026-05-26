"""
首頁：登入 / 註冊 Tab。
"""
from __future__ import annotations

import streamlit as st

from auth import current_role, current_user, login

st.set_page_config(
    page_title="即時資料分析與監控系統",
    page_icon=None,
    layout="centered",
)

# 試用帳號對應表（Plan B query_params zero-click 路徑）
_DEMO_ACCOUNTS: dict[str, tuple[str, str]] = {
    "admin": ("admin@example.com", "admin123"),
    "user": ("user@example.com", "user123"),
    "viewer": ("viewer@example.com", "viewer123"),
}

# ── Plan B: query_params demo_login 自動登入（spike A.3 結論：走 Plan B）──────
# VA-17 programmatic submit 不可行，改用 st.query_params 繞過 form，zero-click
_demo_login_role = st.query_params.get("demo_login")
if _demo_login_role in _DEMO_ACCOUNTS:
    _demo_email, _demo_password = _DEMO_ACCOUNTS[_demo_login_role]
    # 清除 query_params 避免重複觸發
    st.query_params.clear()
    with st.spinner(f"正在以 {_demo_login_role} 登入..."):
        _success, _message = login(_demo_email, _demo_password)
    if _success:
        st.switch_page("pages/1_儀表板.py")
    else:
        st.error(f"登入失敗：{_message}")

# 若已登入，直接轉到 Dashboard
if st.session_state.get("token"):
    st.switch_page("pages/1_儀表板.py")

st.title("即時資料分析與監控系統")
st.markdown("---")

# ── 試用帳號 expander（在 st.tabs 之前，登入/註冊共用區）────────────────────────
# 評審 5 秒內看到三組帳號 + 一鍵登入（Story #1 AC-1 ~ AC-4）
# 密碼明文顯示為 demo 便利性設計（AC edge case 5 已接受）
with st.expander("試用帳號（Demo 用，點按鈕直接登入）", expanded=True):
    st.caption("點擊下方按鈕，系統將自動帶入對應帳號並登入，無需手動輸入。")
    st.markdown(
        "| 角色 | Email | 密碼 |\n"
        "|---|---|---|\n"
        "| **Admin**（系統管理員）| admin@example.com | admin123 |\n"
        "| **User**（一般使用者）| user@example.com | user123 |\n"
        "| **Viewer**（一般訪客）| viewer@example.com | viewer123 |"
    )
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    with btn_col1:
        if st.button("以 Admin 登入", key="login_as_admin", use_container_width=True):
            st.query_params.update(demo_login="admin")
            st.rerun()
    with btn_col2:
        if st.button("以 User 登入", key="login_as_user", use_container_width=True):
            st.query_params.update(demo_login="user")
            st.rerun()
    with btn_col3:
        if st.button("以 Viewer 登入", key="login_as_viewer", use_container_width=True):
            st.query_params.update(demo_login="viewer")
            st.rerun()

tab_login, tab_register = st.tabs(["登入", "註冊"])

# ── 登入 Tab ─────────────────────────────────────────────────────────────────
with tab_login:
    st.subheader("帳號登入")
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="user@example.com")
        password = st.text_input("密碼", type="password", placeholder="輸入密碼")
        submitted = st.form_submit_button("登入", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("請填寫 Email 和密碼。")
        else:
            with st.spinner("登入中..."):
                success, message = login(email, password)
            if success:
                st.success("登入成功，正在跳轉...")
                st.switch_page("pages/1_儀表板.py")
            else:
                st.error(f"登入失敗：{message}")

# ── 註冊 Tab ─────────────────────────────────────────────────────────────────
with tab_register:
    st.subheader("建立新帳號")
    st.info("新帳號預設角色為 **Viewer**（瀏覽者），需由管理員提升權限。")

    with st.form("register_form"):
        reg_display_name = st.text_input("顯示名稱", placeholder="您的姓名")
        reg_email = st.text_input("Email", placeholder="user@example.com", key="reg_email")
        reg_password = st.text_input(
            "密碼",
            type="password",
            placeholder="至少 8 個字元",
            key="reg_password",
        )
        reg_password_confirm = st.text_input(
            "確認密碼",
            type="password",
            placeholder="再次輸入密碼",
            key="reg_password_confirm",
        )
        reg_submitted = st.form_submit_button("註冊", use_container_width=True)

    if reg_submitted:
        errors: list[str] = []
        if not reg_display_name:
            errors.append("請填寫顯示名稱。")
        if not reg_email:
            errors.append("請填寫 Email。")
        if not reg_password:
            errors.append("請填寫密碼。")
        elif len(reg_password) < 8:
            errors.append("密碼至少需要 8 個字元。")
        if reg_password != reg_password_confirm:
            errors.append("兩次密碼輸入不一致。")

        if errors:
            for err in errors:
                st.error(err)
        else:
            from api_client import APIClient

            client = APIClient()
            with st.spinner("註冊中..."):
                resp = client.post(
                    "/auth/register",
                    json={
                        "email": reg_email,
                        "password": reg_password,
                        "display_name": reg_display_name,
                    },
                )

            if resp.status_code == 201:
                st.success("註冊成功！請切換到「登入」頁面登入。")
            elif resp.status_code == 409:
                st.error("此 Email 已被使用，請使用其他 Email 或直接登入。")
            else:
                try:
                    detail = resp.json().get("detail", "註冊失敗")
                except Exception:
                    detail = f"註冊失敗（HTTP {resp.status_code}）"
                st.error(f"註冊失敗：{detail}")
