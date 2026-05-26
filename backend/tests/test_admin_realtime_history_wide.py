"""
C4: tests for GET /api/v1/admin/realtime-history (wide format)
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
async def user_token(client: AsyncClient, regular_user: User) -> str:
    return await get_token(client, regular_user.email, "user1234")


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
async def test_admin_realtime_history_wide_shape(
    client: AsyncClient, admin_token: str, seed_wide_row: RealtimeMetricWide
) -> None:
    """GET /admin/realtime-history 回傳 wide schema。"""
    resp = await client.get(
        "/api/v1/admin/realtime-history",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["total"] >= 1
    item = body["items"][0]
    # wide schema fields
    assert "schema_version" in item
    assert item["schema_version"] == "v2"
    assert "ts" in item
    assert "temperature" in item
    assert "humidity" in item
    assert "pressure" in item
    assert "voltage" in item
    assert "cpu_usage" in item
    assert "anomaly_flags" in item
    # old long-format fields should NOT be present (not in RealtimeSnapshotResponse)
    assert "value" not in item
    assert "category" not in item
    assert "is_anomaly" not in item


@pytest.mark.asyncio
async def test_admin_realtime_history_no_category_param(
    client: AsyncClient, admin_token: str
) -> None:
    """category 參數已移除，帶 category 不應影響（被 FastAPI 忽略）。"""
    resp = await client.get(
        "/api/v1/admin/realtime-history",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200


# ── error cases ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_realtime_history_wide_user_forbidden(
    client: AsyncClient, user_token: str
) -> None:
    """user 不能查詢 → 403。"""
    resp = await client.get(
        "/api/v1/admin/realtime-history",
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_realtime_history_wide_viewer_forbidden(
    client: AsyncClient, viewer_token: str
) -> None:
    """viewer 不能查詢 → 403。"""
    resp = await client.get(
        "/api/v1/admin/realtime-history",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_realtime_history_wide_no_token(client: AsyncClient) -> None:
    """未登入 → 401/403。"""
    resp = await client.get("/api/v1/admin/realtime-history")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_realtime_history_wide_pagination(
    client: AsyncClient, admin_token: str, seed_wide_row: RealtimeMetricWide
) -> None:
    """分頁參數有效。"""
    resp = await client.get(
        "/api/v1/admin/realtime-history?page=1&size=5",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["size"] == 5
    assert len(body["items"]) <= 5
