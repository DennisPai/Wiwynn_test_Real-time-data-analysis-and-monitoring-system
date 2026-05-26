"""
API Client：封裝對後端 HTTP 請求。

BACKEND_URL 優先順序：
1. 環境變數 BACKEND_URL（所有部署環境皆推薦顯式設定）
2. fallback：http://localhost:8000（本地 docker compose 預設 BE port）

本地開發者：`cp .env.example .env` + `docker compose up -d --build` 即可，
  docker-compose.yml 已將容器間通訊設為 BACKEND_URL=http://backend:8000，
  .env.example 預設 BACKEND_URL=http://backend:8000，因此本 fallback 僅作安全網。

雲端部署（Zeabur / Heroku / Railway 等）：**必須**設 BACKEND_URL env var 為後端公開 HTTPS URL，
  例如 BACKEND_URL=https://your-backend.zeabur.app
  若未設定，連線將嘗試 localhost:8000，雲端環境必然失敗。
"""
from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

_BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "http://localhost:8000",
).rstrip("/")  # 防禦：移除末尾斜線避免拼接成 //api/v1 雙斜線
_API_PREFIX = "/api/v1"


def _get_token() -> str | None:
    """從 session_state 取出 JWT token。"""
    return st.session_state.get("token")


def _build_headers() -> dict[str, str]:
    """組裝請求 header，有 token 就帶 Authorization: Bearer。"""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = _get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _handle_401(response: httpx.Response) -> None:
    """若收到 401，自動清除 session_state 並強制 re-run（logout）。"""
    if response.status_code == 401:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.error("登入已逾時，請重新登入。")
        st.rerun()


class APIClient:
    """
    封裝 httpx.Client，提供 post / get / patch / delete 方法。
    base_url 從環境變數 BACKEND_URL 讀取（預設 http://localhost:8000）。
    所有請求自動帶 Authorization: Bearer <token>（若 session_state 有 token）。
    收到 401 時自動登出並 st.rerun()。
    """

    def __init__(self) -> None:
        self.base_url = f"{_BACKEND_URL}{_API_PREFIX}"
        # timeout 設定：連線 5 秒、讀取 30 秒
        self._timeout = httpx.Timeout(30.0, connect=5.0)

    def _headers(self, content_type: str = "application/json") -> dict[str, str]:
        headers: dict[str, str] = {}
        if content_type:
            headers["Content-Type"] = content_type
        token = _get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def post(
        self,
        path: str,
        json: Any = None,
        files: Any = None,
        data: Any = None,
    ) -> httpx.Response:
        """HTTP POST。
        json= 時帶 application/json；files= 時 multipart（不帶 Content-Type，讓 httpx 自動設定 boundary）。
        """
        url = f"{self.base_url}{path}"
        token = _get_token()
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        with httpx.Client(timeout=self._timeout) as client:
            if files is not None:
                # multipart/form-data：不設 Content-Type，讓 httpx 自動加 boundary
                resp = client.post(url, files=files, data=data, headers=headers)
            else:
                headers["Content-Type"] = "application/json"
                resp = client.post(url, json=json, headers=headers)

        _handle_401(resp)
        return resp

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """HTTP GET，params 會自動 URL-encode。"""
        url = f"{self.base_url}{path}"
        headers = self._headers(content_type="")
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(url, params=params, headers=headers)
        _handle_401(resp)
        return resp

    def patch(
        self,
        path: str,
        json: Any = None,
    ) -> httpx.Response:
        """HTTP PATCH，帶 JSON body。"""
        url = f"{self.base_url}{path}"
        headers = self._headers()
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.patch(url, json=json, headers=headers)
        _handle_401(resp)
        return resp

    def delete(
        self,
        path: str,
    ) -> httpx.Response:
        """HTTP DELETE。"""
        url = f"{self.base_url}{path}"
        headers = self._headers(content_type="")
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.delete(url, headers=headers)
        _handle_401(resp)
        return resp


# 模組層級單例（Streamlit re-run 不保留，每次 re-run 都重建，符合 httpx.Client 短連線設計）
api = APIClient()
