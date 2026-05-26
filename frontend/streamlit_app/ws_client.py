"""
WebSocket 客戶端（Realtime 頁面使用）。
- 使用 st.cache_resource 避免 Streamlit re-run 重建連線
- 指數退避重連（1→2→4→8→max 30 秒）
- close code 1008 → token 失效 → 拋出 TokenInvalidError
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from typing import Any, Callable

import streamlit as st

logger = logging.getLogger(__name__)

_WS_URL = os.environ.get(
    "WS_URL",
    "wss://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app/ws/realtime",
)
# 本地開發者請設 WS_URL=ws://localhost:8000/ws/realtime override
# 注意：BE 的 WS endpoint 是 /ws/realtime（不走 /api/v1 prefix）

_BACKOFF_INITIAL = 1      # 秒
_BACKOFF_MAX = 30         # 秒


class TokenInvalidError(Exception):
    """WebSocket close code 1008 — token 失效或未授權。"""


class RealtimeWSClient:
    """
    管理 WebSocket 連線：
    - 連線時帶 token query param（?token=<jwt>）
    - 收到 close code 1008 → 拋出 TokenInvalidError，頁面應引導使用者重新登入
    - 斷線自動重試：指數退避 1 → 2 → 4 → 8 → max 30 秒
    - 已接收的 tick 寫入固定大小的 deque（最多 60 筆，對應 60 秒滾動視窗）
    """

    def __init__(self, token: str, maxlen: int = 60) -> None:
        self.token = token
        self.ws_url = f"{_WS_URL}?token={token}"
        self._buffer: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._connected: bool = False
        self._running: bool = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]

    # ── 公開查詢介面 ──────────────────────────────────────────────────────────

    def get_buffer(self) -> list[dict[str, Any]]:
        """回傳目前 buffer 內的 tick 清單（最新在最後）。"""
        return list(self._buffer)

    def is_connected(self) -> bool:
        """回傳目前連線狀態。"""
        return self._connected

    def push_tick(self, tick: dict[str, Any]) -> None:
        """直接推入一筆 tick（供 polling fallback 或測試使用）。"""
        self._buffer.append(tick)

    def clear(self) -> None:
        """清空 buffer。"""
        self._buffer.clear()
        self._connected = False
        self._running = False

    # ── 非同步串流核心 ────────────────────────────────────────────────────────

    async def stream_ticks(self, on_tick: Callable[[dict[str, Any]], None]) -> None:
        """
        持續連線至 WS endpoint，每收到一筆 tick 即呼叫 on_tick(data)。
        - 自動重連：指數退避 1 → max 30 秒
        - close code 1008 → 拋出 TokenInvalidError（呼叫方應登出）
        - 其他斷線 → 等待後重試
        """
        # 延遲 import，避免在沒有安裝 websockets 的環境直接 crash
        try:
            import websockets
            from websockets.exceptions import ConnectionClosedError
        except ImportError as exc:
            raise RuntimeError("請確認 websockets 已安裝：pip install websockets") from exc

        backoff = _BACKOFF_INITIAL
        self._running = True

        while self._running:
            try:
                async with websockets.connect(self.ws_url) as ws:  # type: ignore[attr-defined]
                    self._connected = True
                    backoff = _BACKOFF_INITIAL  # 連線成功後重置退避時間
                    logger.info("WebSocket 連線成功：%s", self.ws_url)

                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            data: dict[str, Any] = json.loads(raw)
                        except json.JSONDecodeError:
                            logger.warning("收到非 JSON 訊息：%s", raw)
                            continue
                        self._buffer.append(data)
                        on_tick(data)

            except ConnectionClosedError as exc:
                self._connected = False
                # close code 1008 = Policy Violation（token 失效）
                if exc.code == 1008:
                    self._running = False
                    logger.error("WebSocket 被伺服器以 1008 關閉，token 已失效。")
                    raise TokenInvalidError("token 失效，請重新登入") from exc
                logger.warning("WebSocket 斷線（code=%s），%s 秒後重連", exc.code, backoff)

            except Exception as exc:
                self._connected = False
                logger.warning("WebSocket 連線錯誤（%s），%s 秒後重連", exc, backoff)

            if not self._running:
                break

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

        self._connected = False


# ── Streamlit cache_resource 包裝 ─────────────────────────────────────────────

@st.cache_resource
def get_ws_client(token: str) -> RealtimeWSClient:
    """
    以 token 為 key 快取 RealtimeWSClient。
    Streamlit re-run 不重建（@st.cache_resource 語義）。
    """
    return RealtimeWSClient(token)


def run_ws_in_background(token: str, on_tick: Callable[[dict[str, Any]], None]) -> RealtimeWSClient:
    """
    在背景 asyncio 事件迴圈啟動 stream_ticks。
    Streamlit 無法直接在同步脈絡中 await，所以建立獨立 Thread 的 event loop。
    回傳 client 供頁面讀取 buffer。

    注意：此函式設計為「只啟動一次」。呼叫前請確認 client.is_connected() 是否已經為 True。
    """
    import threading

    client = get_ws_client(token)

    def _run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.stream_ticks(on_tick))
        except TokenInvalidError:
            # token 失效：清除 session_state 的 token（下次 rerun 自動踢到登入頁）
            if "token" in st.session_state:
                del st.session_state["token"]
        finally:
            loop.close()

    if not client.is_connected() and not client._running:
        t = threading.Thread(target=_run, daemon=True)
        t.start()

    return client
