"""seed default users and settings

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24 00:01:00.000000

"""
from __future__ import annotations

import os
import sys
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_hashed_password(plain: str) -> str:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return ctx.hash(plain)


def upgrade() -> None:
    conn = op.get_bind()

    # 從環境變數取 seed 帳號（有 .env 時 pydantic-settings 已載入）
    # 直接從環境變數讀取，fallback 到 brief 預設值
    admin_email = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
    admin_pw = os.environ.get("SEED_ADMIN_PASSWORD", "admin123")
    user_email = os.environ.get("SEED_USER_EMAIL", "user@example.com")
    user_pw = os.environ.get("SEED_USER_PASSWORD", "user123")
    viewer_email = os.environ.get("SEED_VIEWER_EMAIL", "viewer@example.com")
    viewer_pw = os.environ.get("SEED_VIEWER_PASSWORD", "viewer123")

    users_table = sa.table(
        "users",
        sa.column("email", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("role", sa.String),
        sa.column("display_name", sa.String),
        sa.column("is_active", sa.Boolean),
    )

    seed_users = [
        {
            "email": admin_email,
            "password_hash": _get_hashed_password(admin_pw),
            "role": "admin",
            "display_name": "Administrator",
            "is_active": True,
        },
        {
            "email": user_email,
            "password_hash": _get_hashed_password(user_pw),
            "role": "user",
            "display_name": "Regular User",
            "is_active": True,
        },
        {
            "email": viewer_email,
            "password_hash": _get_hashed_password(viewer_pw),
            "role": "viewer",
            "display_name": "Viewer",
            "is_active": True,
        },
    ]

    for u in seed_users:
        # INSERT IGNORE（email UNIQUE 衝突時跳過，避免重跑 migration 時重複）
        conn.execute(
            sa.text(
                "INSERT IGNORE INTO users (email, password_hash, role, display_name, is_active) "
                "VALUES (:email, :password_hash, :role, :display_name, :is_active)"
            ),
            u,
        )

    # --- app_settings seed ---
    settings_table = sa.table(
        "app_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.String),
        sa.column("description", sa.String),
    )

    seed_settings = [
        {
            "key": "anomaly_threshold_high",
            "value": "80.0",
            "description": "高異常門檻（數值超過此值視為異常）",
        },
        {
            "key": "anomaly_threshold_low",
            "value": "10.0",
            "description": "低異常門檻（數值低於此值視為異常）",
        },
        {
            "key": "realtime_tick_seconds",
            "value": "1",
            "description": "即時資料生成間隔（秒）",
        },
        {
            "key": "batch_flush_seconds",
            "value": "5",
            "description": "批次寫入 flush 間隔（秒）",
        },
    ]

    for s in seed_settings:
        conn.execute(
            sa.text(
                "INSERT IGNORE INTO app_settings (key, value, description) "
                "VALUES (:key, :value, :description)"
            ),
            s,
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM app_settings WHERE key IN "
            "('anomaly_threshold_high','anomaly_threshold_low',"
            "'realtime_tick_seconds','batch_flush_seconds')"
        )
    )
    admin_email = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
    user_email = os.environ.get("SEED_USER_EMAIL", "user@example.com")
    viewer_email = os.environ.get("SEED_VIEWER_EMAIL", "viewer@example.com")
    conn.execute(
        sa.text("DELETE FROM users WHERE email IN (:a, :u, :v)"),
        {"a": admin_email, "u": user_email, "v": viewer_email},
    )
