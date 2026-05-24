"""
首頁：登入 / 註冊 Tab。
"""
from __future__ import annotations

import streamlit as st

from auth import current_role, current_user, login

st.set_page_config(
    page_title="即時資料分析與監控系統",
    page_icon="📊",
    layout="centered",
)

# 若已登入，直接轉到 Dashboard
if st.session_state.get("token"):
    st.switch_page("pages/1_📊_Dashboard.py")

st.title("即時資料分析與監控系統")
st.markdown("---")

tab_login, tab_register = st.tabs(["登入", "註冊"])

# ── 登入 Tab ─────────────────────────────────────────────────────────────────
with tab_login:
    st.subheader("帳號登入")
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="user@example.com")
        password = st.text_input("密碼", type="password", placeholder="至少 8 個字元")
        submitted = st.form_submit_button("登入", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("請填寫 Email 和密碼。")
        else:
            with st.spinner("登入中..."):
                success, message = login(email, password)
            if success:
                st.success("登入成功，正在跳轉...")
                st.switch_page("pages/1_📊_Dashboard.py")
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
