"""test_analytics.py — wide schema analytics endpoint tests (Phase 5 rewrite).

Covers:
- GET /analytics/summary: per-metric breakdown structure, RBAC
- GET /analytics/timerange: bucket per-metric aggregate
- GET /analytics/categories: per-metric breakdown (P2 endpoint name preserved)
- GET /analytics/export: wide Excel (Summary/TimeRange/Sources sheets)
"""
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


async def _seed_wide_records(client: AsyncClient, token: str, count: int = 6) -> None:
    """建立多筆 wide schema 資料用於分析測試。"""
    for i in range(count):
        resp = await client.post(
            "/api/v1/data",
            json={
                "ts": f"2024-06-{i + 1:02d}T10:00:00Z",
                "temperature": 20.0 + i,
                "humidity": 60.0 + i,
                "pressure": 1013.0,
                "voltage": 12.0,
                "cpu_usage": 40.0 + i * 5,
                "source": "user",
            },
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
async def viewer_token(client: AsyncClient, viewer_user: User) -> str:
    return await get_token(client, viewer_user.email, "viewer12")


# ──────────────────────────────────────────
# GET /analytics/summary — wide per-metric breakdown
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_summary_wide_structure(client: AsyncClient, admin_token: str) -> None:
    """T5.6: summary 回傳 wide per-metric breakdown 結構。"""
    await _seed_wide_records(client, admin_token)

    resp = await client.get(
        "/api/v1/analytics/summary",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # top-level 欄位
    assert "total" in body
    assert "anomaly_count" in body
    assert "anomaly_rate" in body
    assert "per_metric" in body
    assert isinstance(body["total"], int)
    assert isinstance(body["anomaly_rate"], float)

    # per_metric 必須含 5 個 metric key
    per_metric = body["per_metric"]
    for metric in ("temperature", "humidity", "pressure", "voltage", "cpu_usage"):
        assert metric in per_metric, f"per_metric 缺少 {metric}"
        stat = per_metric[metric]
        assert "avg" in stat
        assert "min" in stat
        assert "max" in stat
        assert "std" in stat
        assert "anomaly_count" in stat


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


@pytest.mark.asyncio
async def test_summary_date_filter(client: AsyncClient, admin_token: str) -> None:
    """summary 支援 date_from/date_to 過濾。"""
    await _seed_wide_records(client, admin_token)

    resp = await client.get(
        "/api/v1/analytics/summary?date_from=2024-06-01T00:00:00&date_to=2024-06-03T23:59:59",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_summary_sources_filter(client: AsyncClient, admin_token: str) -> None:
    """T5.6: summary 支援 sources multiselect 過濾。"""
    await _seed_wide_records(client, admin_token)

    resp = await client.get(
        "/api/v1/analytics/summary?sources=user",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "per_metric" in body


# ──────────────────────────────────────────
# GET /analytics/timerange — wide per-metric aggregate
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_timerange_wide_structure(client: AsyncClient, admin_token: str) -> None:
    """T5.6: timerange bucket 含 per-metric aggregate。"""
    await _seed_wide_records(client, admin_token)

    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2024-06-01T00:00:00"
        "&date_to=2024-06-06T23:59:59"
        "&bucket=hour",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucket"] == "hour"
    assert isinstance(body["buckets"], list)

    for b in body["buckets"]:
        assert "ts" in b
        assert "count" in b
        assert "anomaly_count" in b
        assert "per_metric" in b
        # per_metric 含 5 metric key
        for metric in ("temperature", "humidity", "pressure", "voltage", "cpu_usage"):
            assert metric in b["per_metric"], f"bucket per_metric 缺少 {metric}"
            pm = b["per_metric"][metric]
            assert "count" in pm
            assert "anomaly_count" in pm


@pytest.mark.asyncio
async def test_timerange_day_bucket(client: AsyncClient, admin_token: str) -> None:
    """timerange day 桶正常回傳。"""
    await _seed_wide_records(client, admin_token)

    resp = await client.get(
        "/api/v1/analytics/timerange"
        "?date_from=2024-06-01T00:00:00"
        "&date_to=2024-06-06T23:59:59"
        "&bucket=day",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucket"] == "day"


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
# GET /analytics/categories — per-metric breakdown
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_categories_wide_structure(client: AsyncClient, admin_token: str) -> None:
    """T5.6: categories 回傳 per-metric breakdown（endpoint 名稱保留）。"""
    await _seed_wide_records(client, admin_token)

    resp = await client.get(
        "/api/v1/analytics/categories"
        "?date_from=2024-06-01T00:00:00"
        "&date_to=2024-06-06T23:59:59",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # T5.6 wide schema：改為 per-metric breakdown
    assert "metrics" in body
    assert isinstance(body["metrics"], list)
    metrics_found = {m["metric"] for m in body["metrics"]}
    for expected in ("temperature", "humidity", "pressure", "voltage", "cpu_usage"):
        assert expected in metrics_found, f"per-metric breakdown 缺少 {expected}"

    for m in body["metrics"]:
        assert "count" in m
        assert "avg" in m
        assert "min" in m
        assert "max" in m
        assert "anomaly_count" in m


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
# GET /analytics/export — wide Excel（Sources sheet）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_xlsx_wide(client: AsyncClient, admin_token: str) -> None:
    """T5.11: export 回傳 xlsx，Content-Disposition 含 attachment + .xlsx。"""
    await _seed_wide_records(client, admin_token)

    resp = await client.get(
        "/api/v1/analytics/export",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200

    content_type = resp.headers.get("content-type", "")
    assert "spreadsheetml" in content_type or "openxmlformats" in content_type

    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert ".xlsx" in disposition

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
