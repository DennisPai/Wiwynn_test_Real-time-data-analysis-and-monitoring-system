from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, EmailStr, Field

from app.models.user import Role

T = TypeVar("T")


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: Role
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None


class PasswordUpdateRequest(BaseModel):
    """改密碼 request body（PATCH /users/{id}/password）。"""

    new_password: str = Field(..., min_length=8)
    old_password: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int
