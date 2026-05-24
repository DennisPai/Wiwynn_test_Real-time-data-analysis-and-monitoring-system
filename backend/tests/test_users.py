from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.user import Role, User
from tests.conftest import get_token, make_auth_header


@pytest.mark.asyncio
async def test_list_users_admin(client: AsyncClient, admin_user: User) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.get("/api/v1/users", headers=make_auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "pages" in data
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_users_non_admin_forbidden(
    client: AsyncClient, regular_user: User
) -> None:
    token = await get_token(client, regular_user.email, "user1234")
    resp = await client.get("/api/v1/users", headers=make_auth_header(token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_viewer_forbidden(
    client: AsyncClient, viewer_user: User
) -> None:
    token = await get_token(client, viewer_user.email, "viewer12")
    resp = await client.get("/api/v1/users", headers=make_auth_header(token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_filter_by_role(
    client: AsyncClient, admin_user: User
) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.get(
        "/api/v1/users", headers=make_auth_header(token), params={"role": "admin"}
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["role"] == "admin"


@pytest.mark.asyncio
async def test_get_user_by_id_admin(
    client: AsyncClient, admin_user: User, regular_user: User
) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.get(
        f"/api/v1/users/{regular_user.id}", headers=make_auth_header(token)
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == regular_user.id


@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient, admin_user: User) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.get("/api/v1/users/99999", headers=make_auth_header(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_user_admin(
    client: AsyncClient, admin_user: User, regular_user: User
) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.patch(
        f"/api/v1/users/{regular_user.id}",
        headers=make_auth_header(token),
        json={"display_name": "Updated Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_user_role(
    client: AsyncClient, admin_user: User, viewer_user: User
) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.patch(
        f"/api/v1/users/{viewer_user.id}",
        headers=make_auth_header(token),
        json={"role": "user"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "user"


@pytest.mark.asyncio
async def test_update_user_non_admin_forbidden(
    client: AsyncClient, regular_user: User, viewer_user: User
) -> None:
    token = await get_token(client, regular_user.email, "user1234")
    resp = await client.patch(
        f"/api/v1/users/{viewer_user.id}",
        headers=make_auth_header(token),
        json={"display_name": "Hack"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_admin(
    client: AsyncClient, admin_user: User, db_session
) -> None:
    import uuid
    from app.core.security import hash_password
    from app.models.user import User as UserModel

    to_delete = UserModel(
        email=f"todelete_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("todelete1"),
        role=Role.viewer,
        display_name="To Delete",
        is_active=True,
    )
    db_session.add(to_delete)
    await db_session.commit()
    await db_session.refresh(to_delete)

    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.delete(
        f"/api/v1/users/{to_delete.id}", headers=make_auth_header(token)
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_user_non_admin_forbidden(
    client: AsyncClient, regular_user: User, viewer_user: User
) -> None:
    token = await get_token(client, regular_user.email, "user1234")
    resp = await client.delete(
        f"/api/v1/users/{viewer_user.id}", headers=make_auth_header(token)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_not_found(client: AsyncClient, admin_user: User) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.delete("/api/v1/users/99999", headers=make_auth_header(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, admin_user: User) -> None:
    token = await get_token(client, admin_user.email, "admin123")
    resp = await client.get(
        "/api/v1/users",
        headers=make_auth_header(token),
        params={"page": 1, "size": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["size"] == 2
