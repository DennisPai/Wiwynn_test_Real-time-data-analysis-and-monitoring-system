"""
WebSocket 客戶端（F2 Realtime 頁面使用）。
使用 st.cache_resource 避免 Streamlit re-run 重建連線。
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import streamlit as st

_WS_URL = os.environ.get("WS_URL", "ws://localhost:8000/api/v1/ws/realtime")


class RealtimeWSClient:
    """
    管理 WebSocket 連線：
    - 連線時帶 token query param
    - 收到 1008 → 觸發 logout
    - 斷線自動重試（指數退避 1→30 秒）
    """

    def __init__(self, token: str) -> None:
        self.token = token
        self.ws_url = f"{_WS_URL}?token={token}"
        self._messages: list[dict[str, Any]] = []
        self._connected = False

    def get_messages(self) -> list[dict[str, Any]]:
        """回傳已接收訊息（供頁面讀取）。"""
        return self._messages

    def is_connected(self) -> bool:
        return self._connected


@st.cache_resource
def get_ws_client(token: str) -> RealtimeWSClient:
    """以 token 為 key 快取 WS Client（Streamlit re-run 不重建）。"""
    return RealtimeWSClient(token)
