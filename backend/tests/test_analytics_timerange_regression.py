"""test_analytics_timerange_regression.py — T5.6: timerange regression tests (rewrite).

Q7 regression: tz-aware datetime input should not produce empty buckets.
Wide schema: uses wide DataCreate + per-metric aggregate structure.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import get_token, make_auth_header


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user: User) -> str:
    return await get_token(client, admin_user.email, "admin123")


@pytest_asyncio.fixture
async def viewer_token(client: AsyncClient, viewer_user: User) -> str:
    return await get_token(client, viewer_user.email, "viewer12")


async def _seed_wide_records(client: AsyncClient, token: str, ts_dates: list[str]) -> None:
    """Build wide records with given ts values."""
    for ts in ts_dates:
        resp = await client.post(
            "/api/v1/data",
            json={
                "ts": ts,
                "temperature": 25.0,
                "humidity": 60.0,
                "source": "user",
            },
            headers=make_auth_header(token),
        )
        assert resp.status_code == 201, resp.text


# ── happy path (regression: tz-aware Z suffix should not produce empty buckets) ──

@pytest.mark.asyncio
async def test_timerange_tz_aware_input_not_empty(
    client: AsyncClient, admin_token: str
) -> None:
    """
    Q7 regression: tz-aware datetime (Z suffix) should not produce empty buckets.
    T5.6 wide schema: bucket contains per-metric aggregate.
    """
    ts_dates = [
        "2025-01-01T10:00:00Z",
        "2025-01-02T10:00:00Z",
        "2025-01-03T10:00:00Z",
    ]
    await _seed_wide_records(client, admin_token, ts_dates)

    # Send tz-aware datetime (Z suffix)
    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2025-01-01T00:00:00Z"
        "&date_to=2025-01-31T23:59:59Z"
        "&bucket=day",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucket"] == "day"
    assert isinstance(body["buckets"], list)
    assert len(body["buckets"]) >= 3, (
        f"Expected ≥3 buckets, got {len(body['buckets'])} — Q7 regression. "
        f"tz-aware input may be causing empty buckets."
    )


@pytest.mark.asyncio
async def test_timerange_naive_datetime_still_works(
    client: AsyncClient, admin_token: str
) -> None:
    """Naive datetime (no tz suffix) should still work after fix."""
    ts_dates = [
        "2025-02-01T10:00:00Z",
        "2025-02-02T10:00:00Z",
        "2025-02-03T10:00:00Z",
    ]
    await _seed_wide_records(client, admin_token, ts_dates)

    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2025-02-01T00:00:00"
        "&date_to=2025-02-28T23:59:59"
        "&bucket=day",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["buckets"]) >= 3


@pytest.mark.asyncio
async def test_timerange_wide_bucket_per_metric(client: AsyncClient, admin_token: str) -> None:
    """T5.6: 確認 bucket 含 per_metric dict（5 metric key）。"""
    ts_dates = ["2025-03-01T10:00:00Z", "2025-03-01T11:00:00Z"]
    await _seed_wide_records(client, admin_token, ts_dates)

    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2025-03-01T00:00:00Z"
        "&date_to=2025-03-01T23:59:59Z"
        "&bucket=hour",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["buckets"]) >= 2
    for b in body["buckets"]:
        assert "per_metric" in b
        for metric in ("temperature", "humidity", "pressure", "voltage", "cpu_usage"):
            assert metric in b["per_metric"]


# ── error cases ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timerange_invalid_bucket_422(
    client: AsyncClient, admin_token: str
) -> None:
    """非法 bucket 值 → 422。"""
    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2025-01-01T00:00:00"
        "&date_to=2025-01-31T23:59:59"
        "&bucket=week",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_timerange_missing_date_from_422(client: AsyncClient, admin_token: str) -> None:
    """缺少 date_from → 422。"""
    resp = await client.get(
        "/api/v1/analytics/timerange?date_to=2025-01-31T23:59:59",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_timerange_no_token_401(client: AsyncClient) -> None:
    """未登入 → 401/403。"""
    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2025-01-01T00:00:00"
        "&date_to=2025-01-31T23:59:59",
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_timerange_viewer_allowed(client: AsyncClient, viewer_token: str) -> None:
    """viewer 可讀 timerange。"""
    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2025-01-01T00:00:00"
        "&date_to=2025-01-31T23:59:59"
        "&bucket=day",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200
