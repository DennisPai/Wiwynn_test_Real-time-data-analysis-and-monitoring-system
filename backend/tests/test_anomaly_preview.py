"""test_anomaly_preview.py — T5.10: GET /api/v1/anomaly-preview endpoint tests.

Covers:
- response contains anomaly_flags with 5 key bool dict
- anomaly detection uses threshold (high/low)
- any role can call
- no token → 401/403
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


@pytest.mark.asyncio
async def test_anomaly_preview_normal_values(client: AsyncClient, admin_token: str) -> None:
    """T5.10: 正常值時所有 anomaly_flags 應為 False。"""
    resp = await client.get(
        "/api/v1/anomaly-preview?temperature=25.0&humidity=65.0&pressure=1013.0&voltage=12.0&cpu_usage=40.0",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "anomaly_flags" in body
    flags = body["anomaly_flags"]
    assert set(flags.keys()) == {"temperature", "humidity", "pressure", "voltage", "cpu_usage"}
    # 正常值：使用預設 threshold（temperature high=80），25.0 < 80 → False
    assert flags["temperature"] is False
    assert flags["humidity"] is False
    assert flags["pressure"] is False
    assert flags["voltage"] is False
    assert flags["cpu_usage"] is False


@pytest.mark.asyncio
async def test_anomaly_preview_high_temperature(client: AsyncClient, admin_token: str) -> None:
    """T5.10: 溫度超過 high threshold（預設 80）→ temperature anomaly_flags=True。"""
    resp = await client.get(
        "/api/v1/anomaly-preview?temperature=150.0",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    flags = body["anomaly_flags"]
    assert flags["temperature"] is True
    assert flags["humidity"] is False
    assert flags["pressure"] is False


@pytest.mark.asyncio
async def test_anomaly_preview_partial_metrics(client: AsyncClient, admin_token: str) -> None:
    """T5.10: 只傳部分 metric，未傳的 metric 視為 None → False。"""
    resp = await client.get(
        "/api/v1/anomaly-preview?humidity=95.0",  # humidity high=85 → 95.0 > 85 = True
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    flags = body["anomaly_flags"]
    assert flags["humidity"] is True
    assert flags["temperature"] is False  # not provided → None → False


@pytest.mark.asyncio
async def test_anomaly_preview_viewer_allowed(client: AsyncClient, viewer_token: str) -> None:
    """T5.10: viewer 可呼叫 anomaly-preview。"""
    resp = await client.get(
        "/api/v1/anomaly-preview?temperature=25.0",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_anomaly_preview_no_token(client: AsyncClient) -> None:
    """T5.10: 未登入應回 401/403。"""
    resp = await client.get("/api/v1/anomaly-preview?temperature=25.0")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_anomaly_preview_no_params(client: AsyncClient, admin_token: str) -> None:
    """T5.10: 不傳任何 metric，所有 flags 應為 False（全 None）。"""
    resp = await client.get(
        "/api/v1/anomaly-preview",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    flags = body["anomaly_flags"]
    assert all(v is False for v in flags.values())
    assert len(flags) == 5


@pytest.mark.asyncio
async def test_anomaly_preview_response_shape(client: AsyncClient, admin_token: str) -> None:
    """T5.10: response shape 驗證：{anomaly_flags: {temperature, humidity, pressure, voltage, cpu_usage}}。"""
    resp = await client.get(
        "/api/v1/anomaly-preview?cpu_usage=95.0",  # cpu_usage high=90 → 95 > 90 = True
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert list(body.keys()) == ["anomaly_flags"]
    flags = body["anomaly_flags"]
    for k in ("temperature", "humidity", "pressure", "voltage", "cpu_usage"):
        assert k in flags
        assert isinstance(flags[k], bool)
    assert flags["cpu_usage"] is True
