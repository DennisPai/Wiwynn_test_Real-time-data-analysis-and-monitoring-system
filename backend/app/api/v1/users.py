from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AnyRole, get_db, require_role
from app.core.security import hash_password, verify_password
from app.models.user import Role, User
from app.schemas.user import PaginatedResponse, PasswordUpdateRequest, UserResponse, UserUpdate
from app.services.audit_log_service import write_audit_log

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


@router.patch("/{user_id}/password")
async def update_password(
    user_id: int,
    body: PasswordUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
) -> dict:
    """
    改密碼（Q12）。
    - admin：可改任意人，不需 old_password
    - user/viewer：只能改自己，需 old_password
    回傳 {"ok": true, "updated_at": "..."}
    """
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="使用者不存在")

    is_self = (target.id == current_user.id)
    is_admin_acting_on_other = (current_user.role == Role.admin and not is_self)

    # 非 admin 且非自己：403
    if not is_self and not is_admin_acting_on_other:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="權限不足")

    # 改自己（含 admin 改自己）：需 old_password
    if is_self:
        if not body.old_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="改自己密碼需提供 old_password",
            )
        if not verify_password(body.old_password, target.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="舊密碼錯誤",
            )

    target.password_hash = hash_password(body.new_password)
    target.updated_at = datetime.now(tz=timezone.utc)
    await db.flush()
    await db.refresh(target)

    # C2-3: audit log
    await write_audit_log(
        db,
        action="update_password",
        user_id=current_user.id,
        target_type="user",
        target_id=str(target.id),
        meta={"is_self": is_self, "is_admin_change": is_admin_acting_on_other},
    )

    return {"ok": True, "updated_at": target.updated_at.isoformat()}
