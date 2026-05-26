from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting
from app.models.audit_log import AuditLog
from app.models.realtime_metric import RealtimeMetric
from app.models.realtime_metric_wide import RealtimeMetricWide
from app.models.user import User
from tests.conftest import get_token, make_auth_header

# 設定 TESTING=1 避免 APScheduler 啟動
os.environ.setdefault("TESTING", "1")


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


@pytest_asyncio.fixture
async def seed_settings(db_session: AsyncSession) -> None:
    """植入 app_settings 測試資料。"""
    keys = [
        ("anomaly_threshold_high", "80.0", "異常上限"),
        ("anomaly_threshold_low", "10.0", "異常下限"),
        ("realtime_tick_seconds", "1", "即時 tick 間隔（秒）"),
        ("batch_flush_seconds", "5", "批次寫入間隔（秒）"),
    ]
    for key, value, desc in keys:
        from sqlalchemy import select
        result = await db_session.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            db_session.add(AppSetting(key=key, value=value, description=desc))
    await db_session.commit()


@pytest_asyncio.fixture
async def seed_audit_log(db_session: AsyncSession, admin_user: User) -> AuditLog:
    """植入一筆 audit_log。"""
    log = AuditLog(
        user_id=admin_user.id,
        action="test_action",
        target_type="test",
        target_id="1",
        meta={"key": "val"},
        ts=datetime.now(tz=timezone.utc),
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)
    return log


@pytest_asyncio.fixture
async def seed_realtime_metric(db_session: AsyncSession) -> RealtimeMetric:
    """植入一筆 realtime_metric（long format，供相容性 fixture 使用）。"""
    from decimal import Decimal
    metric = RealtimeMetric(
        value=Decimal("55.1234"),
        category="temperature",
        ts=datetime.now(tz=timezone.utc),
        source="simulator",
        is_anomaly=False,
    )
    db_session.add(metric)
    await db_session.commit()
    await db_session.refresh(metric)
    return metric


@pytest_asyncio.fixture
async def seed_realtime_wide(db_session: AsyncSession) -> RealtimeMetricWide:
    """植入一筆 realtime_metric_wide（wide format）。"""
    from decimal import Decimal
    wide = RealtimeMetricWide(
        ts=datetime.now(tz=timezone.utc),
        temperature=Decimal("25.1234"),
        humidity=Decimal("60.0000"),
        pressure=Decimal("1013.0000"),
        voltage=Decimal("12.0000"),
        cpu_usage=Decimal("40.0000"),
        anomaly_flags={"temperature": False, "humidity": False, "pressure": False, "voltage": False, "cpu_usage": False},
        source="simulator",
    )
    db_session.add(wide)
    await db_session.commit()
    await db_session.refresh(wide)
    return wide


# ──────────────────────────────────────────
# GET /admin/logs（#19）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_logs_admin_access(
    client: AsyncClient, admin_token: str, seed_audit_log: AuditLog
) -> None:
    """admin 可查詢 audit_logs。"""
    resp = await client.get("/api/v1/admin/logs", headers=make_auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_admin_logs_user_forbidden(client: AsyncClient, user_token: str) -> None:
    """user 不能查詢 audit_logs，應回 403。"""
    resp = await client.get("/api/v1/admin/logs", headers=make_auth_header(user_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_logs_viewer_forbidden(client: AsyncClient, viewer_token: str) -> None:
    """viewer 不能查詢 audit_logs，應回 403。"""
    resp = await client.get("/api/v1/admin/logs", headers=make_auth_header(viewer_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_logs_no_token(client: AsyncClient) -> None:
    """未登入應回 403/401。"""
    resp = await client.get("/api/v1/admin/logs")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_logs_filter_action(
    client: AsyncClient, admin_token: str, seed_audit_log: AuditLog
) -> None:
    """action filter 有效。"""
    resp = await client.get(
        "/api/v1/admin/logs?action=test_action",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    for item in body["items"]:
        assert item["action"] == "test_action"


@pytest.mark.asyncio
async def test_admin_logs_filter_user_id(
    client: AsyncClient, admin_token: str, admin_user: User, seed_audit_log: AuditLog
) -> None:
    """user_id filter 有效。"""
    resp = await client.get(
        f"/api/v1/admin/logs?user_id={admin_user.id}",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    for item in body["items"]:
        assert item["user_id"] == admin_user.id


# ──────────────────────────────────────────
# GET /admin/db-status（#20）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_db_status_admin(client: AsyncClient, admin_token: str) -> None:
    """admin 可查詢 DB 狀態。"""
    resp = await client.get("/api/v1/admin/db-status", headers=make_auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "ok" in body
    assert body["ok"] is True
    assert "pool" in body
    assert "tables" in body
    pool = body["pool"]
    assert "size" in pool
    assert "checked_out" in pool
    assert "overflow" in pool
    tables = body["tables"]
    assert isinstance(tables, list)
    assert len(tables) > 0
    # 確認每個 table 有 name 和 row_count
    for t in tables:
        assert "name" in t
        assert "row_count" in t


@pytest.mark.asyncio
async def test_admin_db_status_user_forbidden(client: AsyncClient, user_token: str) -> None:
    """user 不能查詢 DB 狀態。"""
    resp = await client.get("/api/v1/admin/db-status", headers=make_auth_header(user_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_db_status_viewer_forbidden(client: AsyncClient, viewer_token: str) -> None:
    """viewer 不能查詢 DB 狀態。"""
    resp = await client.get("/api/v1/admin/db-status", headers=make_auth_header(viewer_token))
    assert resp.status_code == 403


# ──────────────────────────────────────────
# GET /admin/realtime-history（#21）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_realtime_history_admin(
    client: AsyncClient, admin_token: str, seed_realtime_wide: RealtimeMetricWide
) -> None:
    """admin 可查詢即時指標歷史（wide format）。"""
    resp = await client.get(
        "/api/v1/admin/realtime-history",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["total"] >= 1
    # 確認 wide response shape
    if body["items"]:
        item = body["items"][0]
        assert "ts" in item
        assert "temperature" in item
        assert "humidity" in item
        assert "pressure" in item
        assert "voltage" in item
        assert "cpu_usage" in item
        assert "anomaly_flags" in item
        assert "schema_version" in item
        assert item["schema_version"] == "v2"


@pytest.mark.asyncio
async def test_admin_realtime_history_user_forbidden(client: AsyncClient, user_token: str) -> None:
    """user 不能查詢即時指標歷史。"""
    resp = await client.get(
        "/api/v1/admin/realtime-history",
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_realtime_history_viewer_forbidden(
    client: AsyncClient, viewer_token: str
) -> None:
    """viewer 不能查詢即時指標歷史。"""
    resp = await client.get(
        "/api/v1/admin/realtime-history",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_realtime_history_pagination(
    client: AsyncClient, admin_token: str, seed_realtime_wide: RealtimeMetricWide
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


# ──────────────────────────────────────────
# GET /admin/settings（#22）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_settings_list_admin(
    client: AsyncClient, admin_token: str, seed_settings: None
) -> None:
    """admin 可列出所有 settings。"""
    resp = await client.get("/api/v1/admin/settings", headers=make_auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 4
    # 確認 response shape
    for item in body:
        assert "id" in item
        assert "key" in item
        assert "value" in item
        assert "updated_at" in item


@pytest.mark.asyncio
async def test_admin_settings_user_forbidden(client: AsyncClient, user_token: str) -> None:
    """user 不能查詢 settings。"""
    resp = await client.get("/api/v1/admin/settings", headers=make_auth_header(user_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_settings_viewer_forbidden(client: AsyncClient, viewer_token: str) -> None:
    """viewer 不能查詢 settings。"""
    resp = await client.get("/api/v1/admin/settings", headers=make_auth_header(viewer_token))
    assert resp.status_code == 403


# ──────────────────────────────────────────
# PATCH /admin/settings/{key}（#23）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_settings_patch_admin(
    client: AsyncClient, admin_token: str, seed_settings: None
) -> None:
    """admin 可更新 settings，回傳更新後值。"""
    resp = await client.patch(
        "/api/v1/admin/settings/anomaly_threshold_high",
        json={"value": "85.0"},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "anomaly_threshold_high"
    assert body["value"] == "85.0"


@pytest.mark.asyncio
async def test_admin_settings_patch_user_forbidden(
    client: AsyncClient, user_token: str, seed_settings: None
) -> None:
    """user 不能更新 settings。"""
    resp = await client.patch(
        "/api/v1/admin/settings/anomaly_threshold_high",
        json={"value": "90.0"},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_settings_patch_viewer_forbidden(
    client: AsyncClient, viewer_token: str, seed_settings: None
) -> None:
    """viewer 不能更新 settings。"""
    resp = await client.patch(
        "/api/v1/admin/settings/anomaly_threshold_high",
        json={"value": "90.0"},
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_settings_patch_not_found(
    client: AsyncClient, admin_token: str
) -> None:
    """更新不存在的 key 應回 404。"""
    resp = await client.patch(
        "/api/v1/admin/settings/nonexistent_key",
        json={"value": "99"},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_settings_patch_creates_audit_log(
    client: AsyncClient, admin_token: str, admin_user: User, seed_settings: None
) -> None:
    """PATCH settings 應在 audit_logs 留下記錄。"""
    resp = await client.patch(
        "/api/v1/admin/settings/anomaly_threshold_low",
        json={"value": "5.0"},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200

    # 查詢 audit_log 是否有此操作
    logs_resp = await client.get(
        f"/api/v1/admin/logs?action=update_setting&user_id={admin_user.id}",
        headers=make_auth_header(admin_token),
    )
    assert logs_resp.status_code == 200
    logs_body = logs_resp.json()
    assert logs_body["total"] >= 1
    found = any(
        item["action"] == "update_setting" and item["target_id"] == "anomaly_threshold_low"
        for item in logs_body["items"]
    )
    assert found, "應找到 update_setting audit_log"


# ──────────────────────────────────────────
# GET /health（#25）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    """/health 不需認證，應回 {status, db}。"""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "db" in body
    assert body["status"] == "ok"


# ──────────────────────────────────────────
# Audit log 留存（login / register 操作）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_log_from_login(
    client: AsyncClient, admin_token: str, admin_user: User
) -> None:
    """login 操作應在 audit_logs 留下記錄。"""
    # admin_user 在 fixture 建立時已 login 取 token
    resp = await client.get(
        f"/api/v1/admin/logs?action=login&user_id={admin_user.id}",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # login audit_log 由 get_token → /auth/login 觸發
    # 由於 test function scope，至少有 1 筆
    assert body["total"] >= 1


# ──────────────────────────────────────────
# T5.9: PATCH /admin/settings（anomaly threshold）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_patch_anomaly_threshold_admin(
    client: AsyncClient, admin_token: str
) -> None:
    """T5.9: admin 可 PATCH anomaly threshold，response 含 updated_keys + anomaly_threshold。"""
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={
            "anomaly_threshold": {
                "temperature": {"high": 85.0, "low": 5.0},
                "humidity": {"high": 90.0, "low": 15.0},
            }
        },
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "updated_keys" in body
    assert "anomaly_threshold" in body
    assert "anomaly_threshold.temperature" in body["updated_keys"]
    assert "anomaly_threshold.humidity" in body["updated_keys"]
    assert body["anomaly_threshold"]["temperature"]["high"] == 85.0
    assert body["anomaly_threshold"]["temperature"]["low"] == 5.0


@pytest.mark.asyncio
async def test_admin_patch_anomaly_threshold_upsert(
    client: AsyncClient, admin_token: str
) -> None:
    """T5.9: PATCH 兩次同 metric 應 UPSERT（不重複建立）。"""
    payload = {
        "anomaly_threshold": {"pressure": {"high": 1060.0, "low": 940.0}}
    }
    resp1 = await client.patch(
        "/api/v1/admin/settings",
        json=payload,
        headers=make_auth_header(admin_token),
    )
    assert resp1.status_code == 200

    resp2 = await client.patch(
        "/api/v1/admin/settings",
        json={"anomaly_threshold": {"pressure": {"high": 1070.0, "low": 930.0}}},
        headers=make_auth_header(admin_token),
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["anomaly_threshold"]["pressure"]["high"] == 1070.0


@pytest.mark.asyncio
async def test_admin_patch_anomaly_threshold_user_forbidden(
    client: AsyncClient, user_token: str
) -> None:
    """T5.9: user 不能 PATCH anomaly threshold，應回 403。"""
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"anomaly_threshold": {"temperature": {"high": 80.0, "low": 10.0}}},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_patch_anomaly_threshold_viewer_forbidden(
    client: AsyncClient, viewer_token: str
) -> None:
    """T5.9: viewer 不能 PATCH anomaly threshold，應回 403。"""
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"anomaly_threshold": {"temperature": {"high": 80.0, "low": 10.0}}},
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_patch_anomaly_threshold_invalid_metric(
    client: AsyncClient, admin_token: str
) -> None:
    """T5.9: 不合法的 metric 名稱應回 422。"""
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"anomaly_threshold": {"disk_usage": {"high": 90.0, "low": 10.0}}},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_patch_anomaly_threshold_creates_audit_log(
    client: AsyncClient, admin_token: str, admin_user: User
) -> None:
    """T5.9: PATCH anomaly threshold 應在 audit_logs 留下記錄。"""
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"anomaly_threshold": {"voltage": {"high": 14.0, "low": 10.5}}},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200

    logs_resp = await client.get(
        f"/api/v1/admin/logs?action=patch_anomaly_threshold&user_id={admin_user.id}",
        headers=make_auth_header(admin_token),
    )
    assert logs_resp.status_code == 200
    logs_body = logs_resp.json()
    assert logs_body["total"] >= 1


@pytest.mark.asyncio
async def test_audit_log_paginated(
    client: AsyncClient, admin_token: str, seed_audit_log: AuditLog
) -> None:
    """audit_logs 分頁正常。"""
    resp = await client.get(
        "/api/v1/admin/logs?page=1&size=5",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["size"] == 5
    assert "pages" in body
    assert len(body["items"]) <= 5


# ──────────────────────────────────────────
# Fix 4: PATCH /admin/settings high <= low validation
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_settings_high_le_low_422(
    client: AsyncClient, admin_token: str
) -> None:
    """Fix 4: PATCH anomaly threshold where high <= low → 422 validation error。"""
    # high < low: high=10, low=80 → 應 422
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={
            "anomaly_threshold": {
                "temperature": {"high": 10.0, "low": 80.0},
            }
        },
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422, f"Expected 422 for high <= low, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_patch_settings_high_equal_low_422(
    client: AsyncClient, admin_token: str
) -> None:
    """Fix 4: PATCH anomaly threshold where high == low → 422 validation error。"""
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={
            "anomaly_threshold": {
                "humidity": {"high": 50.0, "low": 50.0},
            }
        },
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422, f"Expected 422 for high == low, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_patch_settings_high_gt_low_valid(
    client: AsyncClient, admin_token: str
) -> None:
    """Fix 4: PATCH anomaly threshold where high > low → 200 OK。"""
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={
            "anomaly_threshold": {
                "cpu_usage": {"high": 90.0, "low": 5.0},
            }
        },
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200, f"Expected 200 for valid threshold, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["anomaly_threshold"]["cpu_usage"]["high"] == 90.0
    assert body["anomaly_threshold"]["cpu_usage"]["low"] == 5.0
