from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import get_token, make_auth_header


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


async def _seed_records(client: AsyncClient, token: str, category: str = "analytics_cat") -> None:
    """建立多筆資料用於分析測試。"""
    records = [
        {
            "title": f"analytics_rec_{i}",
            "value": 10.0 * (i + 1),
            "category": category,
            "recorded_at": f"2024-06-{i + 1:02d}T10:00:00",
            "is_anomaly": (i % 3 == 0),
        }
        for i in range(6)
    ]
    for r in records:
        resp = await client.post(
            "/api/v1/data",
            json=r,
            headers=make_auth_header(token),
        )
        assert resp.status_code == 201, resp.text


# ──────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────

@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user: User) -> str:
    return await get_token(client, admin_user.email, "admin123")


@pytest_asyncio.fixture
async def user_token(client: AsyncClient, regular_user: User) -> str:
    return await get_token(client, regular_user.email, "user1234")


@pytest_asyncio.fixture
async def viewer_token(client: AsyncClient, viewer_user: User) -> str:
    return await get_token(client, viewer_user.email, "viewer12")


# ──────────────────────────────────────────
# GET /analytics/summary
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_summary_basic(client: AsyncClient, admin_token: str) -> None:
    """summary 回傳必要欄位。"""
    await _seed_records(client, admin_token, category="summary_basic_test")

    resp = await client.get(
        "/api/v1/analytics/summary",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "total_records" in body
    assert "anomaly_count" in body
    assert "avg_value" in body
    assert "min_value" in body
    assert "max_value" in body
    assert "categories" in body
    assert isinstance(body["total_records"], int)
    assert isinstance(body["avg_value"], float)


@pytest.mark.asyncio
async def test_summary_with_filters(client: AsyncClient, admin_token: str) -> None:
    """summary 支援 date_from / date_to / category 過濾。"""
    await _seed_records(client, admin_token, category="summary_filter_test")

    resp = await client.get(
        "/api/v1/analytics/summary"
        "?date_from=2024-06-01T00:00:00"
        "&date_to=2024-06-03T23:59:59"
        "&category=summary_filter_test",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # 6/1 ~ 6/3 應有 3 筆
    assert body["total_records"] == 3


@pytest.mark.asyncio
async def test_summary_viewer_allowed(client: AsyncClient, viewer_token: str) -> None:
    """viewer 可讀 summary。"""
    resp = await client.get(
        "/api/v1/analytics/summary",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_summary_no_token(client: AsyncClient) -> None:
    """未登入時 summary 應回 403。"""
    resp = await client.get("/api/v1/analytics/summary")
    assert resp.status_code in (401, 403)


# ──────────────────────────────────────────
# GET /analytics/timerange
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_timerange_hour_bucket(client: AsyncClient, admin_token: str) -> None:
    """timerange hour 桶正常回傳。"""
    await _seed_records(client, admin_token, category="timerange_hour_test")

    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2024-06-01T00:00:00"
        "&date_to=2024-06-06T23:59:59"
        "&bucket=hour"
        "&category=timerange_hour_test",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucket"] == "hour"
    assert isinstance(body["buckets"], list)
    assert len(body["buckets"]) == 6  # 6 筆各不同天/小時
    for b in body["buckets"]:
        assert "ts" in b
        assert "count" in b
        assert "avg_value" in b
        assert "anomaly_count" in b


@pytest.mark.asyncio
async def test_timerange_day_bucket(client: AsyncClient, admin_token: str) -> None:
    """timerange day 桶正常回傳。"""
    await _seed_records(client, admin_token, category="timerange_day_test")

    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2024-06-01T00:00:00"
        "&date_to=2024-06-06T23:59:59"
        "&bucket=day"
        "&category=timerange_day_test",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucket"] == "day"
    assert len(body["buckets"]) == 6


@pytest.mark.asyncio
async def test_timerange_invalid_bucket(client: AsyncClient, admin_token: str) -> None:
    """非法 bucket 值應回 422。"""
    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2024-01-01T00:00:00"
        "&date_to=2024-01-31T23:59:59"
        "&bucket=week",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_timerange_viewer_allowed(client: AsyncClient, viewer_token: str) -> None:
    """viewer 可讀 timerange。"""
    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2024-01-01T00:00:00"
        "&date_to=2024-01-31T23:59:59"
        "&bucket=day",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_timerange_missing_required_params(client: AsyncClient, admin_token: str) -> None:
    """缺少 date_from 應回 422。"""
    resp = await client.get(
        "/api/v1/analytics/timerange?date_to=2024-01-31T23:59:59",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


# ──────────────────────────────────────────
# GET /analytics/categories
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_categories_basic(client: AsyncClient, admin_token: str) -> None:
    """categories 回傳各類別聚合統計。"""
    # 建立兩個不同 category 的資料
    for cat in ("cat_group_a", "cat_group_b"):
        await _seed_records(client, admin_token, category=cat)

    resp = await client.get(
        "/api/v1/analytics/categories"
        "?date_from=2024-06-01T00:00:00"
        "&date_to=2024-06-06T23:59:59",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "categories" in body
    assert isinstance(body["categories"], list)
    cat_names = [c["category"] for c in body["categories"]]
    assert "cat_group_a" in cat_names
    assert "cat_group_b" in cat_names

    for c in body["categories"]:
        assert "count" in c
        assert "avg_value" in c
        assert "anomaly_count" in c


@pytest.mark.asyncio
async def test_categories_viewer_allowed(client: AsyncClient, viewer_token: str) -> None:
    """viewer 可讀 categories。"""
    resp = await client.get(
        "/api/v1/analytics/categories"
        "?date_from=2024-01-01T00:00:00"
        "&date_to=2024-12-31T23:59:59",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_categories_missing_required_params(client: AsyncClient, admin_token: str) -> None:
    """缺少 date_from 應回 422。"""
    resp = await client.get(
        "/api/v1/analytics/categories?date_to=2024-12-31T23:59:59",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


# ──────────────────────────────────────────
# GET /analytics/export
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_xlsx(client: AsyncClient, admin_token: str) -> None:
    """export 回傳 xlsx 二進位檔，Content-Disposition 含 attachment。"""
    await _seed_records(client, admin_token, category="export_test")

    resp = await client.get(
        "/api/v1/analytics/export",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200

    # 驗證 Content-Type 是 xlsx
    content_type = resp.headers.get("content-type", "")
    assert "spreadsheetml" in content_type or "openxmlformats" in content_type

    # 驗證 Content-Disposition 含 attachment
    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert ".xlsx" in disposition

    # 驗證非空二進位內容
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_export_viewer_allowed(client: AsyncClient, viewer_token: str) -> None:
    """viewer 可下載 export。"""
    resp = await client.get(
        "/api/v1/analytics/export",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_export_no_token(client: AsyncClient) -> None:
    """未登入時 export 應回 403。"""
    resp = await client.get("/api/v1/analytics/export")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_export_with_filters(client: AsyncClient, admin_token: str) -> None:
    """export 支援 date_from/date_to/category 過濾且正常產生檔案。"""
    await _seed_records(client, admin_token, category="export_filter_test")

    resp = await client.get(
        "/api/v1/analytics/export"
        "?date_from=2024-06-01T00:00:00"
        "&date_to=2024-06-06T23:59:59"
        "&category=export_filter_test",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert len(resp.content) > 0
