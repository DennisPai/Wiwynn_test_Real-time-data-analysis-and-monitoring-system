from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import Role, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.audit_log_service import write_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """新增帳號（預設角色 viewer）。email 已存在則 409。"""
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email 已被使用")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=Role.viewer,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # 寫入 audit_log
    await write_audit_log(
        db,
        action="register",
        user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        meta={"email": user.email},
    )

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """驗證 email + password，回傳 JWT access token。"""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email 或密碼錯誤",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="帳號已停用",
        )

    # 寫入 audit_log
    await write_audit_log(
        db,
        action="login",
        user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        meta={"email": user.email},
    )

    token = create_access_token(
        sub=str(user.id), email=user.email, role=user.role.value
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """回傳當前使用者資訊。"""
    return UserResponse.model_validate(current_user)


@router.post("/logout", response_model=dict)
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],  # noqa: ARG001
) -> dict:
    """登出（stateless JWT，僅回傳 ok）。"""
    return {"ok": True}
