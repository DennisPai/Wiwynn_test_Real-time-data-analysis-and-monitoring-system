from __future__ import annotations

from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal, get_db
from app.models.user import Role, User

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> User:
    """從 Bearer token 解出使用者；token 無效或使用者不存在則 401。"""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無效憑證",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(creds.credentials)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise exc
    except JWTError:
        raise exc

    result = await db.execute(select(User).where(User.id == int(user_id_str)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise exc
    return user


def require_role(*roles: Role):
    """回傳一個 Depends，確認 current_user.role 在允許清單內。"""

    async def _check(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="權限不足",
            )
        return current_user

    return Depends(_check)


# 常用快捷
AdminOnly = require_role(Role.admin)
AnyRole = Depends(get_current_user)
