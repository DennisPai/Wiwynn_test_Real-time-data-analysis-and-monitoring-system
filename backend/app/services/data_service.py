from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_record import DataRecord
from app.models.user import Role, User
from app.schemas.data_record import AnomalyFlags, DataCreate, DataRecordResponse, DataUpdate
from app.services.anomaly_detector import AnomalyDetector

# 排序欄位白名單，防止 SQL injection 風險（T5.1 wide schema 欄位）
_SORT_WHITELIST: dict[str, Any] = {
    "ts": DataRecord.ts,
    "created_at": DataRecord.created_at,
    "updated_at": DataRecord.updated_at,
    "temperature": DataRecord.temperature,
    "humidity": DataRecord.humidity,
    "pressure": DataRecord.pressure,
    "voltage": DataRecord.voltage,
    "cpu_usage": DataRecord.cpu_usage,
}

_DEFAULT_SORT_COL = DataRecord.ts


async def list_records(
    db: AsyncSession,
    *,
    page: int = 1,
    size: int = 20,
    sources: list[str] | None = None,
    metric: str | None = None,
    min_value: Decimal | None = None,
    max_value: Decimal | None = None,
    owner_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = "ts",
    sort_order: str = "desc",
) -> dict:
    """列出資料記錄（wide schema），支援分頁、過濾、排序。
    回傳 {items, total, page, size, pages}。
    """
    stmt = select(DataRecord)

    # 過濾條件
    if sources:
        stmt = stmt.where(DataRecord.source.in_(sources))
    if owner_id is not None:
        stmt = stmt.where(DataRecord.owner_id == owner_id)
    if date_from is not None:
        stmt = stmt.where(DataRecord.ts >= date_from)
    if date_to is not None:
        stmt = stmt.where(DataRecord.ts <= date_to)
    if metric and metric in _SORT_WHITELIST:
        # 單一 metric range filter
        metric_col = _SORT_WHITELIST[metric]
        if min_value is not None:
            stmt = stmt.where(metric_col >= min_value)
        if max_value is not None:
            stmt = stmt.where(metric_col <= max_value)

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
    """建立新資料記錄（wide schema）。

    若 body.anomaly_flags 為預設（全 false），自動呼叫 AnomalyDetector.compute_anomaly_flags()
    以 threshold 計算正確的 anomaly_flags。
    """
    # 計算 anomaly_flags：若 body 的 anomaly_flags 是預設全 false，自動從 threshold 計算
    snapshot_dict = {
        "temperature": body.temperature,
        "humidity": body.humidity,
        "pressure": body.pressure,
        "voltage": body.voltage,
        "cpu_usage": body.cpu_usage,
    }
    # 使用 AnomalyDetector 計算 anomaly_flags（body 提供的 anomaly_flags 優先使用）
    # 若 body 提供的全是 False（即預設值），嘗試自動計算
    body_flags = body.anomaly_flags
    body_flags_all_false = not any(
        [
            body_flags.temperature,
            body_flags.humidity,
            body_flags.pressure,
            body_flags.voltage,
            body_flags.cpu_usage,
        ]
    )
    if body_flags_all_false:
        computed = await AnomalyDetector.compute_anomaly_flags(db, snapshot_dict)
        anomaly_flags_dict = computed
    else:
        anomaly_flags_dict = body_flags.model_dump()

    record = DataRecord(
        ts=body.ts,
        temperature=body.temperature,
        humidity=body.humidity,
        pressure=body.pressure,
        voltage=body.voltage,
        cpu_usage=body.cpu_usage,
        anomaly_flags=anomaly_flags_dict,
        source=body.source.value,
        note=body.note,
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
    """更新資料記錄（wide schema，owner 或 admin 才可執行，deps 層已檢查）。

    若 anomaly_flags 未在 body 指定，自動依 threshold 重算（只在有 metric 更新時重算）。
    """
    update_data = body.model_dump(exclude_unset=True)

    # 先應用所有非 anomaly_flags 欄位的更新
    for field, value in update_data.items():
        if field == "anomaly_flags":
            continue
        if field == "source" and value is not None:
            # SourceEnum value → str
            setattr(record, field, value.value if hasattr(value, "value") else value)
        else:
            setattr(record, field, value)

    # 驗證更新後至少 1 個 metric 非 NULL（service-level merge 驗證）
    metrics_after = [
        record.temperature,
        record.humidity,
        record.pressure,
        record.voltage,
        record.cpu_usage,
    ]
    if all(m is None for m in metrics_after):
        raise ValueError("至少需保留 1 個 metric 非 NULL")

    # 處理 anomaly_flags
    if "anomaly_flags" in update_data and update_data["anomaly_flags"] is not None:
        # body 明確指定 anomaly_flags → 使用 body 的值
        # model_dump(exclude_unset=True) 對 AnomalyFlags 子 model 會回傳 dict 或 AnomalyFlags
        raw_flags = update_data["anomaly_flags"]
        if isinstance(raw_flags, dict):
            record.anomaly_flags = raw_flags
        elif isinstance(raw_flags, AnomalyFlags):
            record.anomaly_flags = raw_flags.model_dump()
        else:
            record.anomaly_flags = dict(raw_flags)
    else:
        # 未指定 anomaly_flags 時，若 metric 有更新則自動重算
        metric_fields = {"temperature", "humidity", "pressure", "voltage", "cpu_usage"}
        if update_data.keys() & metric_fields:
            snapshot_dict = {
                "temperature": record.temperature,
                "humidity": record.humidity,
                "pressure": record.pressure,
                "voltage": record.voltage,
                "cpu_usage": record.cpu_usage,
            }
            record.anomaly_flags = await AnomalyDetector.compute_anomaly_flags(
                db, snapshot_dict
            )

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
