from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """管理所有已連線的 WebSocket 客戶端。"""

    def __init__(self) -> None:
        self._active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket, user_id: int) -> None:
        """接受 WebSocket 連線並加入集合。"""
        await ws.accept()
        self._active.add(ws)
        logger.info("ws: 使用者連線 user_id=%s total=%s", user_id, len(self._active))

    async def disconnect(self, ws: WebSocket) -> None:
        """移除 WebSocket 連線並嘗試關閉。"""
        self._active.discard(ws)
        try:
            await ws.close()
        except Exception:
            pass
        logger.info("ws: 使用者斷線 total=%s", len(self._active))

    async def broadcast(self, payload: str) -> None:
        """廣播字串 payload 給所有已連線客戶端；失敗的自動 disconnect。"""
        dead: list[WebSocket] = []
        for ws in list(self._active):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)


# 全域單例
ws_manager = ConnectionManager()

# 即時資料 queue（asyncio.Queue，in-memory）
realtime_queue: asyncio.Queue = asyncio.Queue()
