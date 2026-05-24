from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def write_audit_log(
    db: AsyncSession,
    *,
    action: str,
    user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    meta: Any | None = None,
) -> AuditLog:
    """
    寫入一筆 audit_log。
    注意：audit_log.meta 是 ORM 屬性名（DB 欄位為 metadata）。
    """
    log = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        meta=meta,
        ts=datetime.now(tz=timezone.utc),
    )
    db.add(log)
    await db.flush()
    return log
