from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.user import Role, User
from tests.conftest import get_token, make_auth_header


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    import uuid
    email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "display_name": "New User",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == email
    assert data["role"] == Role.viewer.value
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, admin_user: User) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": admin_user.email,
            "password": "password123",
            "display_name": "Dup",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient) -> None:
    import uuid
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"shortpw_{uuid.uuid4().hex[:8]}@example.com",
            "password": "short",
            "display_name": "Short",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user: User) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "admin123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, admin_user: User) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "wrongpw1"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_email(client: AsyncClient) -> None:
    import uuid
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": f"nobody_{uuid.uuid4().hex[:8]}@example.com", "password": "password1"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_success(client: AsyncClient, admin_user: User) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.get("/api/v1/auth/me", headers=make_auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == admin_user.email
    assert data["role"] == Role.admin.value
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"}
    )
    # 無效 token -> 401 Unauthorized
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, admin_user: User) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.post("/api/v1/auth/logout", headers=make_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db_session, viewer_user: User) -> None:
    """停用帳號登入應回 403。"""
    from sqlalchemy import select
    from app.models.user import User as UserModel
    result = await db_session.execute(select(UserModel).where(UserModel.id == viewer_user.id))
    u = result.scalar_one()
    u.is_active = False
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": viewer_user.email, "password": "viewer12"},
    )
    assert resp.status_code == 403
