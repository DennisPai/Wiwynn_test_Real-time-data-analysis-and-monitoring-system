"""
C5: tests for GET /api/v1/analytics/unified-summary
C6: tests for GET /api/v1/analytics/realtime-categories
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
async def seed_wide_rows(db_session: AsyncSession) -> list[RealtimeMetricWide]:
    """Plant 3 wide snapshots."""
    rows = []
    for i in range(3):
        row = RealtimeMetricWide(
            ts=datetime.now(tz=timezone.utc),
            temperature=Decimal(str(20.0 + i)),
            humidity=Decimal(str(55.0 + i)),
            pressure=Decimal("1013.0000"),
            voltage=Decimal("12.0000"),
            cpu_usage=Decimal(str(30.0 + i)),
            anomaly_flags={
                "temperature": i == 2,  # 最後一筆 temperature 異常
                "humidity": False,
                "pressure": False,
                "voltage": False,
                "cpu_usage": False,
            },
            source="simulator",
        )
        db_session.add(row)
        rows.append(row)
    await db_session.commit()
    for r in rows:
        await db_session.refresh(r)
    return rows


# ══ C5: unified-summary ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_unified_summary_both_source(
    client: AsyncClient, admin_token: str, seed_wide_rows: list
) -> None:
    """GET /analytics/unified-summary?source=both 回傳完整結構。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary?source=both",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "both"
    assert "realtime" in body
    assert "records" in body
    assert "combined" in body
    if body["realtime"]:
        assert "total" in body["realtime"]
        assert "anomaly_count" in body["realtime"]
        assert "metrics" in body["realtime"]
    if body["combined"]:
        assert "total" in body["combined"]
        assert "anomaly_count" in body["combined"]


@pytest.mark.asyncio
async def test_unified_summary_realtime_only(
    client: AsyncClient, admin_token: str, seed_wide_rows: list
) -> None:
    """source=realtime 只有 realtime 部分，records=None。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary?source=realtime",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "realtime"
    assert body["realtime"] is not None
    assert body["records"] is None


@pytest.mark.asyncio
async def test_unified_summary_records_only(
    client: AsyncClient, admin_token: str
) -> None:
    """source=records 只有 records 部分，realtime=None。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary?source=records",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "records"
    assert body["records"] is not None
    assert body["realtime"] is None


@pytest.mark.asyncio
async def test_unified_summary_viewer_allowed(
    client: AsyncClient, viewer_token: str
) -> None:
    """viewer 可讀 unified-summary。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unified_summary_no_token(client: AsyncClient) -> None:
    """未登入 → 401/403。"""
    resp = await client.get("/api/v1/analytics/unified-summary")
    assert resp.status_code in (401, 403)


# ══ C6: realtime-categories ══════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_realtime_categories_shape(
    client: AsyncClient, admin_token: str, seed_wide_rows: list
) -> None:
    """GET /analytics/realtime-categories 回傳 5 個 metric 統計。"""
    resp = await client.get(
        "/api/v1/analytics/realtime-categories",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "metrics" in body
    assert isinstance(body["metrics"], list)
    # 應有 5 個 metric
    metric_names = {m["metric"] for m in body["metrics"]}
    assert "temperature" in metric_names
    assert "humidity" in metric_names
    assert "pressure" in metric_names
    assert "voltage" in metric_names
    assert "cpu_usage" in metric_names
    # 確認每個 metric 有 count / avg / anomaly_count
    for m in body["metrics"]:
        assert "metric" in m
        assert "count" in m
        assert "avg" in m
        assert "anomaly_count" in m


@pytest.mark.asyncio
async def test_realtime_categories_viewer_allowed(
    client: AsyncClient, viewer_token: str
) -> None:
    """viewer 可讀 realtime-categories。"""
    resp = await client.get(
        "/api/v1/analytics/realtime-categories",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_realtime_categories_no_token(client: AsyncClient) -> None:
    """未登入 → 401/403。"""
    resp = await client.get("/api/v1/analytics/realtime-categories")
    assert resp.status_code in (401, 403)
