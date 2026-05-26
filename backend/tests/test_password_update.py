"""
C2: tests for PATCH /api/v1/users/{user_id}/password
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
async def user_token(client: AsyncClient, regular_user: User) -> str:
    return await get_token(client, regular_user.email, "user1234")


@pytest_asyncio.fixture
async def viewer_token(client: AsyncClient, viewer_user: User) -> str:
    return await get_token(client, viewer_user.email, "viewer12")


# ── happy path ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_change_other_user_password(
    client: AsyncClient,
    admin_token: str,
    regular_user: User,
) -> None:
    """admin 可改其他人密碼（不需 old_password）。"""
    resp = await client.patch(
        f"/api/v1/users/{regular_user.id}/password",
        json={"new_password": "newpassword123"},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "updated_at" in body


@pytest.mark.asyncio
async def test_user_change_own_password(
    client: AsyncClient,
    regular_user: User,
    user_token: str,
) -> None:
    """user 改自己密碼（需 old_password）。"""
    resp = await client.patch(
        f"/api/v1/users/{regular_user.id}/password",
        json={"new_password": "newpass456789", "old_password": "user1234"},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True


@pytest.mark.asyncio
async def test_viewer_change_own_password(
    client: AsyncClient,
    viewer_user: User,
    viewer_token: str,
) -> None:
    """viewer 改自己密碼（需 old_password）。"""
    resp = await client.patch(
        f"/api/v1/users/{viewer_user.id}/password",
        json={"new_password": "newviewerpass", "old_password": "viewer12"},
        headers=make_auth_header(viewer_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True


# ── error cases ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_change_other_user_password_forbidden(
    client: AsyncClient,
    user_token: str,
    admin_user: User,
) -> None:
    """user 不能改別人密碼 → 403。"""
    resp = await client.patch(
        f"/api/v1/users/{admin_user.id}/password",
        json={"new_password": "hacking123456"},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_change_own_password_missing_old_password(
    client: AsyncClient,
    regular_user: User,
    user_token: str,
) -> None:
    """改自己密碼但未提供 old_password → 400。"""
    resp = await client.patch(
        f"/api/v1/users/{regular_user.id}/password",
        json={"new_password": "newpassword123"},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_own_password_wrong_old_password(
    client: AsyncClient,
    regular_user: User,
    user_token: str,
) -> None:
    """改自己密碼但 old_password 錯誤 → 400。"""
    resp = await client.patch(
        f"/api/v1/users/{regular_user.id}/password",
        json={"new_password": "newpassword123", "old_password": "wrongpassword"},
        headers=make_auth_header(user_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password_no_token(
    client: AsyncClient,
    regular_user: User,
) -> None:
    """未登入 → 401 或 403。"""
    resp = await client.patch(
        f"/api/v1/users/{regular_user.id}/password",
        json={"new_password": "newpassword123"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_change_password_user_not_found(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """user_id 不存在 → 404。"""
    resp = await client.patch(
        "/api/v1/users/999999/password",
        json={"new_password": "newpassword123"},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_change_password_too_short(
    client: AsyncClient,
    admin_token: str,
    regular_user: User,
) -> None:
    """new_password 長度不足 8 → 422。"""
    resp = await client.patch(
        f"/api/v1/users/{regular_user.id}/password",
        json={"new_password": "short"},
        headers=make_auth_header(admin_token),
    )
    assert resp.status_code == 422
