from __future__ import annotations

# WebSocket 連線管理器（Phase B3 實作）
# 此檔由 Phase B1 建立作為 placeholder，B3 補完邏輯。

import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """管理所有已連線的 WebSocket 客戶端。"""

    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._active:
            self._active.remove(ws)

    async def broadcast(self, data: Any) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._active):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# 全域單例
ws_manager = ConnectionManager()

# 即時資料 queue（asyncio.Queue，in-memory）
realtime_queue: asyncio.Queue = asyncio.Queue()
