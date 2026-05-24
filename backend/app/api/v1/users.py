from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.user import Role, User
from app.schemas.user import PaginatedResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

_admin_dep = require_role(Role.admin)


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, _admin_dep],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: Role | None = Query(None),
) -> PaginatedResponse[UserResponse]:
    """列出所有使用者（分頁）。僅 admin 可用。"""
    q = select(User)
    count_q = select(func.count()).select_from(User)
    if role is not None:
        q = q.where(User.role == role)
        count_q = count_q.where(User.role == role)

    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    q = q.offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    users = result.scalars().all()

    return PaginatedResponse[UserResponse](
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
        pages=max(1, math.ceil(total / size)),
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, _admin_dep],
) -> UserResponse:
    """取得單一使用者。僅 admin 可用。"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="使用者不存在")
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, _admin_dep],
) -> UserResponse:
    """更新使用者資料。僅 admin 可用。"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="使用者不存在")

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, _admin_dep],
) -> Response:
    """刪除使用者。僅 admin 可用。回傳 204 No Content。"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="使用者不存在")
    await db.delete(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
