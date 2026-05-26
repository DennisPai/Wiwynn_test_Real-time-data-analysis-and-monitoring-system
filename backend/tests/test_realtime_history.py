"""
C1: tests for GET /api/v1/realtime/history
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.realtime_metric_wide import RealtimeMetricWide
from app.models.user import User
from tests.conftest import get_token, make_auth_header


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user: User) -> str:
    return await get_token(client, admin_user.email, "admin123")


@pytest_asyncio.fixture
async def viewer_token(client: AsyncClient, viewer_user: User) -> str:
    return await get_token(client, viewer_user.email, "viewer12")


@pytest_asyncio.fixture
async def seed_wide_row(db_session: AsyncSession) -> RealtimeMetricWide:
    """Plant a wide snapshot in DB."""
    row = RealtimeMetricWide(
        ts=datetime.now(tz=timezone.utc),
        temperature=Decimal("25.0000"),
        humidity=Decimal("60.0000"),
        pressure=Decimal("1013.0000"),
        voltage=Decimal("12.0000"),
        cpu_usage=Decimal("40.0000"),
        anomaly_flags={
            "temperature": False,
            "humidity": False,
            "pressure": False,
            "voltage": False,
            "cpu_usage": False,
        },
        source="simulator",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


# ── happy path ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_realtime_history_happy_path(
    client: AsyncClient, admin_token: str, seed_wide_row: RealtimeMetricWide
) -> None:
    """GET /realtime/history 回傳正確 wide schema。"""
    resp = await client.get(
        "/api/v1/realtime/history?seconds=60",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "snapshots" in body
    assert "count" in body
    assert isinstance(body["snapshots"], list)
    assert body["count"] >= 0
    # 確認每筆 snapshot shape
    if body["snapshots"]:
        snap = body["snapshots"][0]
        assert snap["schema_version"] == "v2"
        assert "ts" in snap
        assert "temperature" in snap
        assert "humidity" in snap
        assert "pressure" in snap
        assert "voltage" in snap
        assert "cpu_usage" in snap
        assert "anomaly_flags" in snap


@pytest.mark.asyncio
async def test_realtime_history_viewer_allowed(
    client: AsyncClient, viewer_token: str
) -> None:
    """viewer 角色可讀 realtime/history。"""
    resp = await client.get(
        "/api/v1/realtime/history",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_realtime_history_count_matches(
    client: AsyncClient, admin_token: str, seed_wide_row: RealtimeMetricWide
) -> None:
    """count 欄位與 snapshots 陣列長度一致。"""
    resp = await client.get(
        "/api/v1/realtime/history?seconds=3600",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == len(body["snapshots"])


# ── error cases ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_realtime_history_no_token(client: AsyncClient) -> None:
    """未登入 → 401 或 403。"""
    resp = await client.get("/api/v1/realtime/history")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_realtime_history_seconds_too_small(
    client: AsyncClient, admin_token: str
) -> None:
    """seconds=0 → 422。"""
    resp = await client.get(
        "/api/v1/realtime/history?seconds=0",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_realtime_history_seconds_too_large(
    client: AsyncClient, admin_token: str
) -> None:
    """seconds=3601 → 422。"""
    resp = await client.get(
        "/api/v1/realtime/history?seconds=3601",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_realtime_history_default_seconds(
    client: AsyncClient, admin_token: str
) -> None:
    """不帶 seconds 參數使用預設值 60，正常回傳。"""
    resp = await client.get(
        "/api/v1/realtime/history",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
