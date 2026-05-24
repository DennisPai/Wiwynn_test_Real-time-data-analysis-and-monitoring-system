"""
認證模組：login / logout / require_auth / current_user。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from api_client import APIClient


def login(email: str, password: str) -> tuple[bool, str]:
    """
    呼叫 POST /auth/login 取得 JWT，再呼叫 GET /auth/me 取得 user 資訊。
    成功：存入 session_state，回傳 (True, "")。
    失敗：回傳 (False, 錯誤訊息)。
    """
    client = APIClient()

    # Step 1：取得 token
    resp = client.post("/auth/login", json={"email": email, "password": password})

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", "登入失敗")
        except Exception:
            detail = f"登入失敗（HTTP {resp.status_code}）"
        return False, detail

    token_data = resp.json()
    token = token_data.get("access_token")
    if not token:
        return False, "伺服器未回傳 access_token"

    # 先存 token，後續 /auth/me 才能帶 Authorization header
    st.session_state["token"] = token

    # Step 2：取得 user 資訊
    me_resp = client.get("/auth/me")
    if me_resp.status_code != 200:
        # token 取到了但 me 失敗，仍視為登入失敗，清掉 token
        del st.session_state["token"]
        try:
            detail = me_resp.json().get("detail", "無法取得使用者資訊")
        except Exception:
            detail = "無法取得使用者資訊"
        return False, detail

    user = me_resp.json()
    st.session_state["user"] = user
    return True, ""


def logout() -> None:
    """
    呼叫 POST /auth/logout（stateless，僅通知後端），清除 session_state。
    """
    client = APIClient()
    try:
        client.post("/auth/logout")
    except Exception:
        pass  # 登出時網路錯誤不阻擋清除 state

    for key in list(st.session_state.keys()):
        del st.session_state[key]


def require_auth() -> None:
    """
    若 session_state 沒有 token，顯示錯誤並 st.stop()。
    在每個需要認證的頁面最頂端呼叫。
    """
    if not st.session_state.get("token"):
        st.error("請先登入。請前往首頁登入。")
        st.stop()


def current_user() -> dict[str, Any]:
    """
    從 session_state 取出 user dict（含 id / email / role / display_name 等）。
    若不存在則回傳空 dict。
    """
    return st.session_state.get("user", {})


def current_role() -> str:
    """回傳目前使用者的角色字串（admin / user / viewer），未登入回傳空字串。"""
    user = current_user()
    return user.get("role", "")
