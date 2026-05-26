"""test_analytics_unified.py — T5.6: unified-summary + realtime-categories tests (rewrite).

Covers:
- GET /analytics/unified-summary: per-source breakdown (user/simulator_data_records/realtime)
- GET /analytics/realtime-categories: 5 metric stats from realtime_metric_wide
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
    """Plant 3 realtime_metric_wide snapshots（不動 scope 限縮 A）。"""
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


# ══ C5: unified-summary (T5.6 wide schema) ══════════════════════════════════

@pytest.mark.asyncio
async def test_unified_summary_both_source(
    client: AsyncClient, admin_token: str, seed_wide_rows: list
) -> None:
    """T5.6: GET /analytics/unified-summary（無 sources param）回傳 per-source breakdown 結構。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # T5.6 新 schema：per-source breakdown
    assert "total" in body
    assert "anomaly_count" in body
    assert isinstance(body["total"], int)


@pytest.mark.asyncio
async def test_unified_summary_realtime_only(
    client: AsyncClient, admin_token: str, seed_wide_rows: list
) -> None:
    """Fix 3: sources=realtime 只查 realtime_metric_wide。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary?sources=realtime",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # realtime source 查 realtime_metric_wide（seed_wide_rows 有 3 筆）
    assert "realtime" in body
    # user/simulator_data_records 應為 None（沒有 data_records 查詢）
    assert body.get("user") is None
    assert body.get("simulator_data_records") is None


@pytest.mark.asyncio
async def test_unified_summary_records_only(
    client: AsyncClient, admin_token: str
) -> None:
    """Fix 3: sources=user&sources=simulator 查 data_records（user + simulator）。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary?sources=user&sources=simulator",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # records source：查 data_records
    assert "user" in body
    assert "simulator_data_records" in body
    # realtime 應為 None
    assert body.get("realtime") is None


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


# ══ C6: realtime-categories（查 realtime_metric_wide，保留不動）══════════════

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
    metric_names = {m["metric"] for m in body["metrics"]}
    assert "temperature" in metric_names
    assert "humidity" in metric_names
    assert "pressure" in metric_names
    assert "voltage" in metric_names
    assert "cpu_usage" in metric_names
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


# ══ Fix 3: unified-summary sources list[str] filter ══════════════════════════

@pytest.mark.asyncio
async def test_unified_summary_sources_filter_user_only(
    client: AsyncClient, admin_token: str, seed_wide_rows: list
) -> None:
    """Fix 3: sources=["user"] → 只回 user SourceStat，simulator_data_records=None，realtime=None。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary?sources=user",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # sources=["user"] → user stat 應存在（即使 count=0）
    assert "user" in body
    assert body["user"] is not None
    assert "count" in body["user"]
    assert "anomaly_count" in body["user"]
    # simulator_data_records 和 realtime 不應回傳（沒有被選）
    assert body.get("simulator_data_records") is None
    assert body.get("realtime") is None


@pytest.mark.asyncio
async def test_unified_summary_sources_filter_simulator_only(
    client: AsyncClient, admin_token: str, seed_wide_rows: list
) -> None:
    """Fix 3: sources=["simulator"] → 只回 simulator_data_records SourceStat。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary?sources=simulator",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # simulator_data_records 應存在
    assert "simulator_data_records" in body
    assert body["simulator_data_records"] is not None
    # user 和 realtime 不應回傳
    assert body.get("user") is None
    assert body.get("realtime") is None


@pytest.mark.asyncio
async def test_unified_summary_sources_empty_returns_all(
    client: AsyncClient, admin_token: str, seed_wide_rows: list
) -> None:
    """Fix 3: sources 留空（不帶 param）→ 全列（user + simulator_data_records + realtime）。"""
    resp = await client.get(
        "/api/v1/analytics/unified-summary",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # 全列 → 3 個 key 全部存在
    assert "user" in body
    assert "simulator_data_records" in body
    assert "realtime" in body
    # total 應是合計
    assert isinstance(body["total"], int)
    assert body["total"] >= 0
