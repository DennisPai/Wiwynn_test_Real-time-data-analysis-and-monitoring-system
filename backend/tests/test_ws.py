from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.core.security import create_access_token
from app.core.ws_manager import ws_manager
from app.models.user import Role, User
from tests.conftest import get_token

# 設定 TESTING=1 避免 APScheduler 啟動
os.environ.setdefault("TESTING", "1")


# ──────────────────────────────────────────
# 同步 WebSocket 測試（用 FastAPI TestClient）
# ──────────────────────────────────────────

def test_ws_no_token_rejected() -> None:
    """無 token 連線應收到 close code 1008（政策錯誤）。"""
    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/realtime") as ws:
            ws.receive_text()


def test_ws_invalid_token_rejected() -> None:
    """無效 token 應被拒絕。"""
    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/realtime?token=invalidtoken") as ws:
            ws.receive_text()


def test_ws_expired_token_rejected() -> None:
    """過期 token 應被 decode_access_token 拒絕（JWTError）。"""
    from datetime import datetime, timedelta, timezone
    from jose import jwt, JWTError
    from app.config import settings
    from app.core.security import decode_access_token

    # 建立過期 token
    payload = {
        "sub": "1",
        "email": "test@example.com",
        "role": "admin",
        "iat": datetime.now(tz=timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(tz=timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(JWTError):
        decode_access_token(expired_token)


# ──────────────────────────────────────────
# 非同步 ConnectionManager 單元測試
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_manager_connect_adds_to_active() -> None:
    """connect 後 ws 應在 active set 中。"""

    class FakeWS:
        def __init__(self):
            self.messages: list[str] = []
            self.accepted = False

        async def accept(self):
            self.accepted = True

        async def send_text(self, msg: str):
            self.messages.append(msg)

        async def close(self):
            pass

    fake = FakeWS()
    await ws_manager.connect(fake, 1)
    assert fake in ws_manager._active
    assert fake.accepted

    # 清理
    await ws_manager.disconnect(fake)


@pytest.mark.asyncio
async def test_ws_manager_disconnect_removes_from_active() -> None:
    """disconnect 後連線不再在 active set 中。"""

    class SimpleWS:
        async def accept(self):
            pass

        async def send_text(self, msg: str):
            pass

        async def close(self):
            pass

    ws = SimpleWS()
    await ws_manager.connect(ws, 2)
    assert ws in ws_manager._active

    await ws_manager.disconnect(ws)
    assert ws not in ws_manager._active


@pytest.mark.asyncio
async def test_ws_manager_broadcast_sends_to_all() -> None:
    """broadcast 應送給所有已連線客戶端。"""

    class RecordWS:
        def __init__(self):
            self.messages: list[str] = []

        async def accept(self):
            pass

        async def send_text(self, msg: str):
            self.messages.append(msg)

        async def close(self):
            pass

    ws1 = RecordWS()
    ws2 = RecordWS()
    await ws_manager.connect(ws1, 10)
    await ws_manager.connect(ws2, 11)

    await ws_manager.broadcast('{"event": "test"}')

    assert '{"event": "test"}' in ws1.messages
    assert '{"event": "test"}' in ws2.messages

    await ws_manager.disconnect(ws1)
    await ws_manager.disconnect(ws2)


@pytest.mark.asyncio
async def test_ws_manager_broadcast_removes_dead_connections() -> None:
    """broadcast 時死亡連線應自動移除。"""

    class DeadWS:
        async def accept(self):
            pass

        async def send_text(self, msg: str):
            raise RuntimeError("connection dead")

        async def close(self):
            pass

    dead = DeadWS()
    await ws_manager.connect(dead, 999)
    assert dead in ws_manager._active

    # broadcast 應移除失敗連線
    await ws_manager.broadcast("ping")
    assert dead not in ws_manager._active


@pytest.mark.asyncio
async def test_ws_token_jwt_decode(admin_user: User) -> None:
    """JWT token 解碼正常（單元測試 decode_access_token）。"""
    from app.core.security import decode_access_token

    token = create_access_token(
        sub=str(admin_user.id),
        email=admin_user.email,
        role=admin_user.role.value,
    )
    payload = decode_access_token(token)
    assert payload["sub"] == str(admin_user.id)
    assert payload["email"] == admin_user.email
    assert payload["role"] == Role.admin.value
