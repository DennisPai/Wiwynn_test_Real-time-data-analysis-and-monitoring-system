from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    # 登入不檢查密碼長度（只 hash compare）；強度檢查在 RegisterRequest


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密碼至少 8 個字元")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
