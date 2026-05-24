from __future__ import annotations

import io
import csv
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


async def _create_record_via_api(
    client: AsyncClient,
    token: str,
    *,
    title: str = "測試記錄",
    value: float = 42.0,
    category: str = "temp",
    recorded_at: str | None = None,
    is_anomaly: bool = False,
) -> dict:
    """用 API POST 建立一筆記錄，回傳 JSON body。"""
    payload = {
        "title": title,
        "value": value,
        "category": category,
        "recorded_at": recorded_at or _now_iso(),
        "is_anomaly": is_anomaly,
    }
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
# POST /data — 建立記錄
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_data_admin(client: AsyncClient, admin_token: str) -> None:
    """admin 可建立資料記錄。"""
    resp = await client.post(
        "/api/v1/data",
        json={
            "title": "溫度測試",
            "value": 55.5,
            "category": "temperature",
            "recorded_at": _now_iso(),
            "is_anomaly": False,
        },
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "溫度測試"
    assert isinstance(body["value"], float)
    assert body["category"] == "temperature"
    assert body["is_anomaly"] is False
    assert "id" in body
    assert "owner_id" in body


@pytest.mark.asyncio
async def test_create_data_user(client: AsyncClient, user_token: str) -> None:
    """user 可建立資料記錄。"""
    resp = await client.post(
        "/api/v1/data",
        json={
            "title": "user 的記錄",
            "value": 10.0,
            "category": "humidity",
            "recorded_at": _now_iso(),
        },
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_data_viewer_forbidden(client: AsyncClient, viewer_token: str) -> None:
    """viewer 無法建立資料記錄，應回 403。"""
    resp = await client.post(
        "/api/v1/data",
        json={
            "title": "viewer 嘗試建立",
            "value": 1.0,
            "category": "test",
            "recorded_at": _now_iso(),
        },
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_data_no_token(client: AsyncClient) -> None:
    """未登入時建立記錄應回 403（HTTPBearer auto_error）。"""
    resp = await client.post(
        "/api/v1/data",
        json={
            "title": "未授權",
            "value": 1.0,
            "category": "x",
            "recorded_at": _now_iso(),
        },
    )
    assert resp.status_code in (401, 403)


# ──────────────────────────────────────────
# GET /data — 列出記錄
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_data_any_role(client: AsyncClient, viewer_token: str, admin_token: str) -> None:
    """任何已登入角色皆可讀取列表。"""
    # 先建立一筆資料
    await _create_record_via_api(client, admin_token, title="列表測試", category="list_test")

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
    # 建立 5 筆
    for i in range(5):
        await _create_record_via_api(client, admin_token, title=f"分頁記錄_{i}", category="pagination_test")

    resp = await client.get(
        "/api/v1/data?page=1&size=2&category=pagination_test",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 5


@pytest.mark.asyncio
async def test_list_data_filter_category(client: AsyncClient, admin_token: str) -> None:
    """category 過濾有效。"""
    await _create_record_via_api(client, admin_token, title="特定類別", category="filter_cat_unique")

    resp = await client.get(
        "/api/v1/data?category=filter_cat_unique",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["category"] == "filter_cat_unique"


@pytest.mark.asyncio
async def test_list_data_sort_by_whitelist(client: AsyncClient, admin_token: str) -> None:
    """非白名單排序欄位回 422。"""
    resp = await client.get(
        "/api/v1/data?sort_by=invalid_col",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_data_no_token(client: AsyncClient) -> None:
    """未登入時列表應回 403。"""
    resp = await client.get("/api/v1/data")
    assert resp.status_code in (401, 403)


# ──────────────────────────────────────────
# GET /data/{id} — 取得單筆
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_data_by_id(client: AsyncClient, admin_token: str, viewer_token: str) -> None:
    """任何角色可取得單筆記錄。"""
    created = await _create_record_via_api(
        client, admin_token, title="單筆測試", category="single_get"
    )
    record_id = created["id"]

    resp = await client.get(f"/api/v1/data/{record_id}", headers=make_auth_header(viewer_token))
    assert resp.status_code == 200
    assert resp.json()["id"] == record_id


@pytest.mark.asyncio
async def test_get_data_not_found(client: AsyncClient, admin_token: str) -> None:
    """不存在的 ID 應回 404。"""
    resp = await client.get("/api/v1/data/9999999", headers=make_auth_header(admin_token))
    assert resp.status_code == 404


# ──────────────────────────────────────────
# PATCH /data/{id} — 更新記錄
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_data_admin_any_record(
    client: AsyncClient, admin_token: str, user_token: str
) -> None:
    """admin 可更新任何人的記錄。"""
    created = await _create_record_via_api(
        client, user_token, title="用戶記錄", category="patch_test_admin"
    )
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={"title": "已被 admin 更新"},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "已被 admin 更新"


@pytest.mark.asyncio
async def test_update_data_user_own_record(
    client: AsyncClient, user_token: str
) -> None:
    """user 可更新自己的記錄。"""
    created = await _create_record_via_api(
        client, user_token, title="自己的記錄", category="patch_test_user_own"
    )
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={"title": "我自己更新的"},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "我自己更新的"


@pytest.mark.asyncio
async def test_update_data_user_other_record_forbidden(
    client: AsyncClient, admin_token: str, user_token: str
) -> None:
    """user 不能更新其他人的記錄，應回 403。"""
    created = await _create_record_via_api(
        client, admin_token, title="admin 的記錄", category="patch_test_cross"
    )
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={"title": "user 偷改"},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_data_viewer_forbidden(
    client: AsyncClient, admin_token: str, viewer_token: str
) -> None:
    """viewer 不能更新任何記錄，應回 403。"""
    created = await _create_record_via_api(
        client, admin_token, title="admin 記錄", category="patch_test_viewer"
    )
    record_id = created["id"]

    resp = await client.patch(
        f"/api/v1/data/{record_id}",
        json={"title": "viewer 嘗試更新"},
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_data_not_found(client: AsyncClient, admin_token: str) -> None:
    """更新不存在記錄應回 404。"""
    resp = await client.patch(
        "/api/v1/data/9999999",
        json={"title": "不存在"},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 404


# ──────────────────────────────────────────
# DELETE /data/{id} — 刪除記錄
# ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_data_admin(client: AsyncClient, admin_token: str) -> None:
    """admin 可刪除任何記錄，回 204。"""
    created = await _create_record_via_api(
        client, admin_token, title="待刪除 admin", category="delete_test_admin"
    )
    record_id = created["id"]

    resp = await client.delete(
        f"/api/v1/data/{record_id}",
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 204

    # 確認已刪除
    check = await client.get(f"/api/v1/data/{record_id}", headers=make_auth_header(admin_token))
    assert check.status_code == 404


@pytest.mark.asyncio
async def test_delete_data_user_own_record(client: AsyncClient, user_token: str) -> None:
    """user 可刪除自己的記錄。"""
    created = await _create_record_via_api(
        client, user_token, title="user 自己的待刪除", category="delete_test_user_own"
    )
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
    created = await _create_record_via_api(
        client, admin_token, title="admin 的記錄不能被 user 刪", category="delete_test_cross"
    )
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
    created = await _create_record_via_api(
        client, admin_token, title="viewer 不能刪", category="delete_test_viewer"
    )
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
# POST /data/bulk-import — 批量導入
# ──────────────────────────────────────────

def _make_csv(rows: list[dict]) -> bytes:
    """建立 CSV bytes。"""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["title", "value", "category", "recorded_at", "is_anomaly"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _make_json(rows: list[dict]) -> bytes:
    """建立 JSON bytes。"""
    return json.dumps(rows).encode("utf-8")


@pytest.mark.asyncio
async def test_bulk_import_csv_all_valid(
    client: AsyncClient, admin_token: str
) -> None:
    """全部有效的 CSV 正常匯入。"""
    rows = [
        {
            "title": f"bulk_normal_{i}",
            "value": 10.0 + i,
            "category": "bulk_normal",
            "recorded_at": "2024-01-01T00:00:00",
            "is_anomaly": False,
        }
        for i in range(3)
    ]
    content = _make_csv(rows)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 3
    assert body["failed"] == 0
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_bulk_import_csv_all_fail(
    client: AsyncClient, admin_token: str
) -> None:
    """全部無效的 CSV 全部失敗，inserted=0。"""
    # 故意讓 value 不是數字
    rows = [
        {
            "title": "bad_row_1",
            "value": "not_a_number",
            "category": "bulk_all_fail",
            "recorded_at": "2024-01-01T00:00:00",
            "is_anomaly": False,
        },
        {
            "title": "",  # title 空
            "value": 10.0,
            "category": "bulk_all_fail",
            "recorded_at": "2024-01-01T00:00:00",
            "is_anomaly": False,
        },
    ]
    content = _make_csv(rows)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 0
    assert body["failed"] == 2
    assert len(body["errors"]) == 2
    # 確認 errors 結構
    for err in body["errors"]:
        assert "row" in err
        assert "reason" in err


@pytest.mark.asyncio
async def test_bulk_import_csv_partial_fail(
    client: AsyncClient, user_token: str
) -> None:
    """部分失敗：有效列仍插入，失敗列收集錯誤。"""
    rows = [
        {
            "title": "有效記錄",
            "value": 99.9,
            "category": "partial_fail_test",
            "recorded_at": "2024-06-15T12:00:00",
            "is_anomaly": False,
        },
        {
            "title": "無效記錄",
            "value": "abc",  # 無效 value
            "category": "partial_fail_test",
            "recorded_at": "2024-06-15T12:00:00",
            "is_anomaly": False,
        },
    ]
    content = _make_csv(rows)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    assert body["failed"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["row"] == 3  # header=1, row1=2, row2=3


@pytest.mark.asyncio
async def test_bulk_import_json_all_valid(
    client: AsyncClient, admin_token: str
) -> None:
    """JSON 格式正常匯入。"""
    rows = [
        {
            "title": f"json_bulk_{i}",
            "value": 50.0 + i,
            "category": "json_bulk",
            "recorded_at": "2024-03-01T00:00:00",
            "is_anomaly": False,
        }
        for i in range(2)
    ]
    content = _make_json(rows)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("test.json", io.BytesIO(content), "application/json")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 2
    assert body["failed"] == 0


@pytest.mark.asyncio
async def test_bulk_import_viewer_forbidden(
    client: AsyncClient, viewer_token: str
) -> None:
    """viewer 不能使用 bulk-import，應回 403。"""
    rows = [{"title": "t", "value": 1.0, "category": "c", "recorded_at": "2024-01-01T00:00:00"}]
    content = _make_csv(rows)

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
    # 產生超過 10MB 的假內容
    large_content = b"x" * (10_000_001)

    resp = await client.post(
        "/api/v1/data/bulk-import",
        files={"file": ("large.csv", io.BytesIO(large_content), "text/csv")},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 413
