from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_record import DataRecord
from app.models.user import Role, User
from app.schemas.data_record import DataCreate, DataRecordResponse, DataUpdate

# 排序欄位白名單，防止 SQL injection 風險
_SORT_WHITELIST: dict[str, Any] = {
    "recorded_at": DataRecord.recorded_at,
    "created_at": DataRecord.created_at,
    "updated_at": DataRecord.updated_at,
    "title": DataRecord.title,
    "value": DataRecord.value,
    "category": DataRecord.category,
}

_DEFAULT_SORT_COL = DataRecord.recorded_at


async def list_records(
    db: AsyncSession,
    *,
    page: int = 1,
    size: int = 20,
    category: str | None = None,
    owner_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    sort_by: str = "recorded_at",
    sort_order: str = "desc",
) -> dict:
    """列出資料記錄，支援分頁、過濾、排序。回傳 {items, total, page, size, pages}。"""
    stmt = select(DataRecord)

    # 過濾條件
    if category:
        stmt = stmt.where(DataRecord.category == category)
    if owner_id is not None:
        stmt = stmt.where(DataRecord.owner_id == owner_id)
    if date_from is not None:
        stmt = stmt.where(DataRecord.recorded_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(DataRecord.recorded_at <= date_to)
    if search:
        stmt = stmt.where(DataRecord.title.ilike(f"%{search}%"))

    # 計算總數
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    # 排序
    sort_col = _SORT_WHITELIST.get(sort_by, _DEFAULT_SORT_COL)
    if sort_order.lower() == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())

    # 分頁
    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)

    result = await db.execute(stmt)
    records = result.scalars().all()

    pages = ceil(total / size) if size > 0 else 0

    return {
        "items": [DataRecordResponse.model_validate(r) for r in records],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


async def get_record(db: AsyncSession, record_id: int) -> DataRecord | None:
    """依 ID 取得單筆資料記錄。"""
    result = await db.execute(select(DataRecord).where(DataRecord.id == record_id))
    return result.scalar_one_or_none()


async def create_record(
    db: AsyncSession, body: DataCreate, owner_id: int
) -> DataRecord:
    """建立新資料記錄，owner_id 為當前使用者。"""
    record = DataRecord(
        title=body.title,
        value=body.value,
        category=body.category,
        recorded_at=body.recorded_at,
        is_anomaly=body.is_anomaly,
        owner_id=owner_id,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_record(
    db: AsyncSession,
    record: DataRecord,
    body: DataUpdate,
    current_user: User,
) -> DataRecord:
    """更新資料記錄（owner 或 admin 才可執行，deps 層已檢查）。"""
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)
    await db.flush()
    await db.refresh(record)
    return record


async def delete_record(
    db: AsyncSession,
    record: DataRecord,
) -> None:
    """刪除資料記錄（owner 或 admin 才可執行，deps 層已檢查）。"""
    await db.delete(record)
    await db.flush()


def check_can_modify(record: DataRecord, current_user: User) -> bool:
    """檢查是否有權限修改/刪除：admin 任何人；user 僅自己；viewer 禁止。"""
    if current_user.role == Role.admin:
        return True
    if current_user.role == Role.user and record.owner_id == current_user.id:
        return True
    return False
