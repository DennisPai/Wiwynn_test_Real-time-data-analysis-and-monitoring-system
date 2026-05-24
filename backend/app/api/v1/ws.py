from __future__ import annotations

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.security import decode_access_token
from app.core.ws_manager import ws_manager

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/realtime")
async def ws_realtime(ws: WebSocket, token: str | None = None) -> None:
    """
    WebSocket 即時資料串流（Endpoint #24）。
    query string 帶 token=<JWT>；驗證失敗回 close code 1008。
    """
    # 驗證 token
    if not token:
        await ws.close(code=1008)
        return

    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            await ws.close(code=1008)
            return
        user_id = int(user_id_str)
    except (JWTError, ValueError, Exception):
        await ws.close(code=1008)
        return

    # 連線成功
    await ws_manager.connect(ws, user_id)
    try:
        while True:
            # 保持連線存活；client 送任何訊息都忽略
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(ws)
