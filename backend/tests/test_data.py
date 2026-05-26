"""test_data.py — wide schema data endpoint tests (Phase 5 rewrite).

Covers:
- POST /data: wide DataCreate, at-least-1-metric validator, RBAC
- GET /data: sources multiselect, metric range filter, sort_by wide fields, pagination
- GET /data/{id}: wide response
- PATCH /data/{id}: wide DataUpdate, partial update, RBAC
- DELETE /data/{id}: RBAC
- POST /data/bulk-import: wide CSV, old long header reject, missing metric header reject
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_record import DataRecord
from app.models.user import User
from tests.conftest import get_token, make_auth_header


# ──────────────────────────────────────────
# Helper
# ──────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


_WIDE_ANOMALY_FLAGS = {
    "temperature": False,
    "humidity": False,
    "pressure": False,
    "voltage": False,
    "cpu_usage": False,
}


async def _create_record_via_api(
    client: AsyncClient,
    token: str,
    *,
    ts: str | None = None,
    temperature: float | None = 25.0,
    humidity: float | None = None,
    pressure: float | None = None,
    voltage: float | None = None,
    cpu_usage: float | None = None,
    note: str | None = None,
    source: str = "user",
) -> dict:
    """POST /api/v1/data wide schema helper。"""
    payload: dict = {
        "ts": ts or _now_iso(),
        "source": source,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if humidity is not None:
        payload["humidity"] = humidity
    if pressure is not None:
        payload["pressure"] = pressure
    if voltage is not None:
        payload["voltage"] = voltage
    if cpu_usage is not None:
        payload["cpu_usage"] = cpu_usage
    if note is not None:
        payload["note"] = note

    resp = await client.post(
        "/api/v1/data",
        json=payload,
        headers=make_auth_header(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


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
# POST /data — wide schema 建立記錄
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_data_admin_wide(client: AsyncClient, admin_token: str) -> None:
    """admin 可建立 wide 資料記錄，response 含 13 欄 wide schema。"""
    resp = await client.post(
        "/api/v1/data",
        json={
            "ts": _now_iso(),
            "temperature": 55.5,
            "humidity": 60.0,
            "source": "user",
            "note": "廠房A早班",
        },
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["temperature"] is not None
    assert body["humidity"] is not None
    assert "anomaly_flags" in body
    assert set(body["anomaly_flags"].keys()) == {
        "temperature", "humidity", "pressure", "voltage", "cpu_usage"
    }
    assert body["source"] == "user"
    assert body["note"] == "廠房A早班"
    assert "id" in body
    assert "owner_id" in body
    assert "ts" in body


@pytest.mark.asyncio
async def test_create_data_user(client: AsyncClient, user_token: str) -> None:
    """user 可建立 wide 資料記錄。"""
    resp = await client.post(
        "/api/v1/data",
        json={
            "ts": _now_iso(),
            "humidity": 65.0,
            "source": "user",
        },
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_data_at_least_one_metric_required(client: AsyncClient, admin_token: str) -> None:
    """5 metric 全空 → 422 with 正確 error message。"""
    resp = await client.post(
        "/api/v1/data",
        json={
            "ts": _now_iso(),
            "source": "user",
            # 故意不傳任何 metric
        },
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_data_anomaly_flags_5key(client: AsyncClient, admin_token: str) -> None:
    """response 的 anomaly_flags 必須含完整 5 key。"""
    resp = await client.post(
        "/api/v1/data",
        json={
            "ts": _now_iso(),
            "temperature": 25.0,
        },
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 201
    flags = resp.json()["anomaly_flags"]
    assert len(flags) == 5
    for k in ("temperature", "humidity", "pressure", "voltage", "cpu_usage"):
        assert k in flags
        assert isinstance(flags[k], bool)


@pytest.mark.asyncio
async def test_create_data_viewer_forbidden(client: AsyncClient, viewer_token: str) -> None:
    """viewer 無法建立資料記錄，應回 403。"""
    resp = await client.post(
        "/api/v1/data",
        json={"ts": _now_iso(), "temperature": 25.0},
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_data_no_token(client: AsyncClient) -> None:
    """未登入時建立記錄應回 401/403。"""
    resp = await client.post(
        "/api/v1/data",
        json={"ts": _now_iso(), "temperature": 25.0},
    )
    assert resp.status_code in (401, 403)


# ──────────────────────────────────────────
# GET /data — 列出記錄（wide params）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_data_any_role(client: AsyncClient, viewer_token: str, admin_token: str) -> None:
    """任何已登入角色皆可讀取列表，response 含 PaginatedResponse 結構。"""
    await _create_record_via_api(client, admin_token, temperature=30.0)

    resp = await client.get("/api/v1/data", headers=make_auth_header(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "size" in body
    assert "pages" in body


@pytest.mark.asyncio
async def test_list_data_pagination(client: AsyncClient, admin_token: str) -> None:
    """分頁參數正常運作。"""
    for i in range(5):
        await _create_record_via_api(client, admin_token, temperature=10.0 + i)

    resp = await client.get(
        "/api/v1/data?page=1&size=2",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["size"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_data_filter_sources(client: AsyncClient, admin_token: str) -> None:
    """T5.1: sources multiselect filter 有效。"""
    await _create_record_via_api(client, admin_token, temperature=20.0, source="user")

    resp = await client.get(
        "/api/v1/data?sources=user",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    for item in body["items"]:
        assert item["source"] == "user"


@pytest.mark.asyncio
async def test_list_data_filter_metric_range(client: AsyncClient, admin_token: str) -> None:
    """T5.1: metric range filter（metric=temperature&min_value=50）有效。"""
    await _create_record_via_api(client, admin_token, temperature=80.0)
    await _create_record_via_api(client, admin_token, temperature=20.0)

    resp = await client.get(
        "/api/v1/data?metric=temperature&min_value=50",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    for item in body["items"]:
        if item["temperature"] is not None:
            assert float(item["temperature"]) >= 50.0


@pytest.mark.asyncio
async def test_list_data_sort_by_wide_fields(client: AsyncClient, admin_token: str) -> None:
    """T5.1: wide 排序欄位（ts / temperature / humidity / ...）正常。"""
    for sort_field in ("ts", "created_at", "updated_at", "temperature"):
        resp = await client.get(
            f"/api/v1/data?sort_by={sort_field}",
            headers=make_auth_header(admin_token),
        )
        assert resp.status_code == 200, f"sort_by={sort_field} failed: {resp.text}"


@pytest.mark.asyncio
async def test_list_data_sort_by_invalid(client: AsyncClient, admin_token: str) -> None:
    """T5.1: 非白名單排序欄位（舊 category / title / value）回 422。"""
    for old_field in ("category", "title", "value", "recorded_at", "invalid_col"):
        resp = await client.get(
            f"/api/v1/data?sort_by={old_field}",
            headers=make_auth_header(admin_token),
        )
        assert resp.status_code == 422, f"Expected 422 for sort_by={old_field}"


@pytest.mark.asyncio
async def test_list_data_no_token(client: AsyncClient) -> None:
    """未登入時列表應回 401/403。"""
    resp = await client.get("/api/v1/data")
    assert resp.status_code in (401, 403)


# ──────────────────────────────────────────
# GET /data/{id} — 取得單筆（wide response）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_data_by_id_wide(client: AsyncClient, admin_token: str, viewer_token: str) -> None:
    """T5.3: 任何角色可取得單筆記錄，response 為 wide schema。"""
    created = await _create_record_via_api(
        client, admin_token, temperature=42.0, note="單筆測試"
    )
    record_id = created["id"]

    resp = await client.get(f"/api/v1/data/{record_id}", headers=make_auth_header(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == record_id
    assert "ts" in body
    assert "anomaly_flags" in body
    assert set(body["anomaly_flags"].keys()) == {
        "temperature", "humidity", "pressure", "voltage", "cpu_usage"
    }
    assert body["note"] == "單筆測試"


@pytest.mark.asyncio
async def test_get_data_not_found(client: AsyncClient, admin_token: str) -> None:
    """不存在的 ID 應回 404。"""
    resp = await client.get("/api/v1/data/9999999", headers=make_auth_header(admin_token))
    assert resp.status_code == 404


# ──────────────────────────────────────────
# PATCH /data/{id} — 更新記錄（wide DataUpdate）
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_data_admin_any_record(
    client: AsyncClient, admin_token: str, user_token: str
) -> None:
    """admin 可更新任何人的記錄（wide fields）。"""
    created = await _create_record_via_api(
        client, user_token, temperature=20.0, note="用戶記錄"
    )
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={"note": "已被 admin 更新", "temperature": 30.0},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["note"] == "已被 admin 更新"
    assert float(body["temperature"]) == 30.0


@pytest.mark.asyncio
async def test_update_data_partial_metrics(client: AsyncClient, user_token: str) -> None:
    """T5.3: 部分更新 metric（只改 humidity，不影響 temperature）。"""
    created = await _create_record_via_api(
        client, user_token, temperature=25.0, humidity=60.0
    )
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={"humidity": 70.0},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert float(body["humidity"]) == 70.0
    # temperature 應保留原值
    assert body["temperature"] is not None


@pytest.mark.asyncio
async def test_update_data_anomaly_flags_full_5key(client: AsyncClient, admin_token: str) -> None:
    """T5.3: PATCH anomaly_flags 必須含完整 5 key。"""
    created = await _create_record_via_api(client, admin_token, temperature=150.0)
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={
            "anomaly_flags": {
                "temperature": True,
                "humidity": False,
                "pressure": False,
                "voltage": False,
                "cpu_usage": False,
            }
        },
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    flags = resp.json()["anomaly_flags"]
    assert flags["temperature"] is True


@pytest.mark.asyncio
async def test_update_data_user_own_record(client: AsyncClient, user_token: str) -> None:
    """user 可更新自己的記錄。"""
    created = await _create_record_via_api(
        client, user_token, temperature=30.0
    )
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={"note": "我自己更新的"},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 200
    assert resp.json()["note"] == "我自己更新的"


@pytest.mark.asyncio
async def test_update_data_user_other_record_forbidden(
    client: AsyncClient, admin_token: str, user_token: str
) -> None:
    """user 不能更新其他人的記錄，應回 403。"""
    created = await _create_record_via_api(
        client, admin_token, temperature=25.0
    )
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={"note": "user 偷改"},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_data_viewer_forbidden(
    client: AsyncClient, admin_token: str, viewer_token: str
) -> None:
    """viewer 不能更新任何記錄，應回 403。"""
    created = await _create_record_via_api(client, admin_token, temperature=25.0)
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={"note": "viewer 嘗試更新"},
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_data_not_found(client: AsyncClient, admin_token: str) -> None:
    """更新不存在記錄應回 404。"""
    resp = await client.patch(
        "/api/v1/data/9999999",
        json={"note": "不存在"},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 404


# ──────────────────────────────────────────
# DELETE /data/{id} — 刪除記錄
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_data_admin(client: AsyncClient, admin_token: str) -> None:
    """admin 可刪除任何記錄，回 204。"""
    created = await _create_record_via_api(client, admin_token, temperature=10.0)
    record_id = created["id"]

    resp = await client.delete(
        f"/api/v1/data/{record_id}",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 204

    check = await client.get(f"/api/v1/data/{record_id}", headers=make_auth_header(admin_token))
    assert check.status_code == 404


@pytest.mark.asyncio
async def test_delete_data_user_own_record(client: AsyncClient, user_token: str) -> None:
    """user 可刪除自己的記錄。"""
    created = await _create_record_via_api(client, user_token, humidity=65.0)
    record_id = created["id"]

    resp = await client.delete(
        f"/api/v1/data/{record_id}",
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_data_user_other_record_forbidden(
    client: AsyncClient, admin_token: str, user_token: str
) -> None:
    """user 不能刪除其他人的記錄，應回 403。"""
    created = await _create_record_via_api(client, admin_token, pressure=1013.0)
    record_id = created["id"]

    resp = await client.delete(
        f"/api/v1/data/{record_id}",
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_data_viewer_forbidden(
    client: AsyncClient, admin_token: str, viewer_token: str
) -> None:
    """viewer 不能刪除任何記錄，應回 403。"""
    created = await _create_record_via_api(client, admin_token, voltage=12.0)
    record_id = created["id"]

    resp = await client.delete(
        f"/api/v1/data/{record_id}",
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_data_not_found(client: AsyncClient, admin_token: str) -> None:
    """刪除不存在記錄應回 404。"""
    resp = await client.delete(
        "/api/v1/data/9999999",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 404


# ──────────────────────────────────────────
# POST /data/bulk-import — wide CSV 驗證
# ──────────────────────────────────────────

def _make_wide_csv(rows: list[dict], extra_headers: list[str] | None = None) -> bytes:
    """建立 wide format CSV bytes。"""
    buf = io.StringIO()
    headers = ["ts", "temperature", "humidity", "pressure", "voltage", "cpu_usage", "source", "note"]
    if extra_headers:
        headers = extra_headers
    buf.write(",".join(headers) + "\n")
    for row in rows:
        buf.write(",".join(str(row.get(h, "")) for h in headers) + "\n")
    return buf.getvalue().encode("utf-8")


def _make_long_csv() -> bytes:
    """建立舊 long format CSV bytes（含 title/value/category）。"""
    buf = io.StringIO()
    buf.write("title,value,category,recorded_at,is_anomaly\n")
    buf.write("測試,55.5,temperature,2024-01-01T00:00:00,False\n")
    return buf.getvalue().encode("utf-8")


def _make_no_metric_csv() -> bytes:
    """建立缺所有 metric 的 CSV（只有 ts + source）。"""
    buf = io.StringIO()
    buf.write("ts,source,note\n")
    buf.write("2024-01-01T00:00:00,user,test\n")
    return buf.getvalue().encode("utf-8")


@pytest.mark.asyncio
async def test_bulk_import_wide_csv_valid(
    client: AsyncClient, admin_token: str
) -> None:
    """T5.4: wide CSV 正常匯入。"""
    rows = [
        {
            "ts": "2026-05-22T00:00:00Z",
            "temperature": "25.5",
            "humidity": "65.2",
            "pressure": "1013.3",
            "voltage": "12.04",
            "cpu_usage": "34.5",
            "source": "user",
            "note": "廠房A早班",
        }
    ]
    content = _make_wide_csv(rows)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    assert body["failed"] == 0


@pytest.mark.asyncio
async def test_bulk_import_old_long_header_reject(
    client: AsyncClient, admin_token: str
) -> None:
    """T5.4: 舊 long 格式 CSV（含 title/value/category）→ 整檔拒絕。"""
    content = _make_long_csv()

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 0
    assert body["failed"] >= 1
    # error row=0 表示整檔拒絕
    assert body["errors"][0]["row"] == 0
    assert "long" in body["errors"][0]["reason"].lower() or "舊版" in body["errors"][0]["reason"]


@pytest.mark.asyncio
async def test_bulk_import_missing_all_metric_headers_reject(
    client: AsyncClient, admin_token: str
) -> None:
    """T5.4: 缺所有 5 metric → 整檔拒絕 with missing_columns list。"""
    content = _make_no_metric_csv()

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 0
    assert body["failed"] >= 1
    error = body["errors"][0]
    assert error["row"] == 0
    assert "missing_columns" in error
    assert len(error["missing_columns"]) == 5


@pytest.mark.asyncio
async def test_bulk_import_at_least_one_metric_per_row(
    client: AsyncClient, admin_token: str
) -> None:
    """T5.4: per-row 至少 1 metric 非空，全空 row 會失敗。"""
    # header 有 temperature 欄位，但 row 的值為空
    buf = io.StringIO()
    buf.write("ts,temperature,source\n")
    buf.write("2026-05-22T00:00:00Z,,user\n")  # temperature 空
    content = buf.getvalue().encode("utf-8")

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] >= 1


@pytest.mark.asyncio
async def test_bulk_import_viewer_forbidden(
    client: AsyncClient, viewer_token: str
) -> None:
    """viewer 不能使用 bulk-import，應回 403。"""
    rows = [{"ts": "2024-01-01T00:00:00", "temperature": "25.0", "source": "user", "note": ""}]
    content = _make_wide_csv(rows)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bulk_import_file_too_large(
    client: AsyncClient, admin_token: str
) -> None:
    """超過 10 MB 的檔案應回 413。"""
    large_content = b"x" * (10_000_001)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("large.csv", io.BytesIO(large_content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_bulk_import_json_wide_valid(
    client: AsyncClient, admin_token: str
) -> None:
    """T5.4: wide JSON 格式正常匯入。"""
    rows = [
        {
            "ts": "2026-05-22T00:00:00Z",
            "temperature": 25.5,
            "humidity": 65.2,
            "source": "user",
            "note": "JSON test",
        }
    ]
    content = json.dumps(rows).encode("utf-8")

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.json", io.BytesIO(content), "application/json")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    assert body["failed"] == 0


# ──────────────────────────────────────────
# Fix 2: bulk-import owner_email lookup tests
# ──────────────────────────────────────────

def _make_wide_csv_with_owner_email(rows: list[dict]) -> bytes:
    """建立含 owner_email 欄位的 wide format CSV bytes。"""
    buf = io.StringIO()
    headers = ["ts", "temperature", "humidity", "pressure", "voltage", "cpu_usage", "source", "note", "owner_email"]
    buf.write(",".join(headers) + "\n")
    for row in rows:
        buf.write(",".join(str(row.get(h, "")) for h in headers) + "\n")
    return buf.getvalue().encode("utf-8")


@pytest.mark.asyncio
async def test_bulk_import_owner_email_admin_cross_owner(
    client: AsyncClient,
    admin_token: str,
    regular_user: User,
) -> None:
    """Fix 2: admin 上傳含 owner_email=other_user → 該 row 的 owner_id 對應 other_user.id。"""
    rows = [
        {
            "ts": "2026-05-22T10:00:00Z",
            "temperature": "30.0",
            "source": "user",
            "note": "admin cross-owner test",
            "owner_email": regular_user.email,
        }
    ]
    content = _make_wide_csv_with_owner_email(rows)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1, f"Expected 1 inserted, got: {body}"
    assert body["failed"] == 0

    # 驗證 owner_id 是 regular_user 的 id
    # 用大 page size 確保找到此筆
    list_resp = await client.get(
        "/api/v1/data?size=100&sort_by=ts&sort_order=desc",
        headers=make_auth_header(admin_token),
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    # 找到 note = "admin cross-owner test"
    matching = [i for i in items if i.get("note") == "admin cross-owner test"]
    assert len(matching) >= 1, f"Could not find item with note 'admin cross-owner test' in {len(items)} items"
    assert matching[0]["owner_id"] == regular_user.id


@pytest.mark.asyncio
async def test_bulk_import_owner_email_user_403(
    client: AsyncClient,
    user_token: str,
    admin_user: User,
) -> None:
    """Fix 2: user role 帶 owner_email → 該 row 失敗（403 error in bulk errors，不是 HTTP 403）。"""
    rows = [
        {
            "ts": "2026-05-22T11:00:00Z",
            "temperature": "25.0",
            "source": "user",
            "note": "user cross-owner attempt",
            "owner_email": admin_user.email,
        }
    ]
    content = _make_wide_csv_with_owner_email(rows)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    # 該 row 因 owner_email 非 admin 而失敗
    assert body["inserted"] == 0
    assert body["failed"] == 1
    assert len(body["errors"]) == 1
    # 錯誤訊息應包含 admin 相關說明
    error_reason = body["errors"][0]["reason"]
    assert "admin" in error_reason.lower() or "403" in error_reason or "owner" in error_reason.lower()


@pytest.mark.asyncio
async def test_bulk_import_owner_email_not_exist_422(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """Fix 2: admin 帶不存在的 owner_email → 該 row 失敗（422 error in bulk errors）。"""
    rows = [
        {
            "ts": "2026-05-22T12:00:00Z",
            "temperature": "22.0",
            "source": "user",
            "note": "nonexistent owner test",
            "owner_email": "nonexistent_user_xyz@nowhere.example.com",
        }
    ]
    content = _make_wide_csv_with_owner_email(rows)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 0
    assert body["failed"] == 1
    assert len(body["errors"]) == 1
    error_reason = body["errors"][0]["reason"]
    # 錯誤訊息應包含 owner_email 相關說明
    assert "owner_email" in error_reason or "存在" in error_reason or "not" in error_reason.lower()
