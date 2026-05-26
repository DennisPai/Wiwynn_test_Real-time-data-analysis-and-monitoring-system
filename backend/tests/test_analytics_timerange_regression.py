"""
C3: regression test for GET /api/v1/analytics/timerange (Q7)
Verifies tz-aware datetime input does not return empty buckets.
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


async def _seed_records(client: AsyncClient, token: str, category: str) -> None:
    """Build 3 records for timerange testing."""
    for i in range(3):
        await client.post(
            "/api/v1/data",
            json={
                "title": f"tr_reg_{i}",
                "value": 10.0 * (i + 1),
                "category": category,
                "recorded_at": f"2025-01-0{i + 1}T10:00:00",
                "is_anomaly": False,
            },
            headers=make_auth_header(token),
        )


# ── happy path (regression: tz-aware Z suffix should not produce empty buckets) ──

@pytest.mark.asyncio
async def test_timerange_tz_aware_input_not_empty(
    client: AsyncClient, admin_token: str
) -> None:
    """
    Q7 regression: tz-aware datetime (Z suffix) should not produce empty buckets.
    C3-2 fix normalises tz-aware → naive UTC before passing to service.
    """
    category = "tz_regression_test"
    await _seed_records(client, admin_token, category)

    # Send tz-aware datetime (Z suffix)
    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2025-01-01T00:00:00Z"
        "&date_to=2025-01-31T23:59:59Z"
        "&bucket=day"
        f"&category={category}",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # Should have data, not empty buckets
    assert body["bucket"] == "day"
    assert isinstance(body["buckets"], list)
    assert len(body["buckets"]) == 3, f"Expected 3 buckets, got {len(body['buckets'])} — Q7 regression"


@pytest.mark.asyncio
async def test_timerange_naive_datetime_still_works(
    client: AsyncClient, admin_token: str
) -> None:
    """Naive datetime (no tz suffix) should still work after fix."""
    category = "naive_dt_regression"
    await _seed_records(client, admin_token, category)

    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2025-01-01T00:00:00"
        "&date_to=2025-01-31T23:59:59"
        "&bucket=day"
        f"&category={category}",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["buckets"]) == 3


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
