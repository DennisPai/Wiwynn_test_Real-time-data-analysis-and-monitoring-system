from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_record import DataRecord
from app.schemas.analytics import (
    CategoriesResponse,
    CategoryStat,
    SummaryResponse,
    TimeBucket,
    TimeRangeResponse,
)


def _base_stmt(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    category: str | None = None,
):
    """建立帶有日期/category 過濾的基礎 SELECT。"""
    stmt = select(DataRecord)
    if date_from is not None:
        stmt = stmt.where(DataRecord.recorded_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(DataRecord.recorded_at <= date_to)
    if category:
        stmt = stmt.where(DataRecord.category == category)
    return stmt


async def get_summary(
    db: AsyncSession,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    category: str | None = None,
) -> SummaryResponse:
    """
    聚合統計：total_records / anomaly_count / avg / min / max / categories 清單。
    使用 SQLAlchemy func.count / func.avg / func.min / func.max。
    """
    # 單次查詢取得所有聚合值
    agg_stmt = select(
        func.count(DataRecord.id),
        func.sum(case((DataRecord.is_anomaly == True, 1), else_=0)),  # noqa: E712
        func.avg(DataRecord.value),
        func.min(DataRecord.value),
        func.max(DataRecord.value),
    )
    if date_from is not None:
        agg_stmt = agg_stmt.where(DataRecord.recorded_at >= date_from)
    if date_to is not None:
        agg_stmt = agg_stmt.where(DataRecord.recorded_at <= date_to)
    if category:
        agg_stmt = agg_stmt.where(DataRecord.category == category)

    row = (await db.execute(agg_stmt)).one()
    total = row[0] or 0
    anomaly_count = int(row[1] or 0)
    avg_value = float(row[2] or 0.0)
    min_value = float(row[3] or 0.0)
    max_value = float(row[4] or 0.0)

    # 取 categories 清單（distinct）
    cat_stmt = select(DataRecord.category).distinct()
    if date_from is not None:
        cat_stmt = cat_stmt.where(DataRecord.recorded_at >= date_from)
    if date_to is not None:
        cat_stmt = cat_stmt.where(DataRecord.recorded_at <= date_to)
    if category:
        cat_stmt = cat_stmt.where(DataRecord.category == category)
    cat_result = await db.execute(cat_stmt)
    categories = [r[0] for r in cat_result.all()]

    return SummaryResponse(
        total_records=total,
        anomaly_count=anomaly_count,
        avg_value=avg_value,
        min_value=min_value,
        max_value=max_value,
        categories=categories,
    )


async def get_timerange(
    db: AsyncSession,
    date_from: datetime,
    date_to: datetime,
    bucket: str = "hour",
    category: str | None = None,
) -> TimeRangeResponse:
    """
    按時間桶聚合。
    - SQLite 測試環境：使用 func.strftime（SQLite 原生支援）
    - MariaDB 生產環境：使用 func.date_format（hour）或 func.date（day）

    偵測方式：檢查 engine dialect（由 db.bind / db.get_bind()），
    但 AsyncSession 不保證 bind，改用 try/except 或直接用 SQLAlchemy
    dialect-aware 語法。

    實作策略：先嘗試 MariaDB（date_format），若 dialect 是 sqlite 改用 strftime。
    為相容兩種 dialect，改用 func 的方式：
    - 統一用 SQLAlchemy func 讓 dialect 翻譯（date_format 在 sqlite 不存在）
    - 改用欄位擷取：func.strftime for sqlite / func.date_format for mysql

    最終選用：在 AsyncSession 取 dialect name，再分支。
    """
    # 取 dialect 名稱
    bind = db.get_bind()
    dialect_name: str = bind.dialect.name if bind is not None else "mysql"

    if dialect_name == "sqlite":
        # SQLite 測試環境
        if bucket == "hour":
            truncated = func.strftime("%Y-%m-%dT%H:00:00", DataRecord.recorded_at)
        else:
            truncated = func.strftime("%Y-%m-%dT00:00:00", DataRecord.recorded_at)
    else:
        # MariaDB / MySQL 生產環境
        if bucket == "hour":
            truncated = func.date_format(DataRecord.recorded_at, "%Y-%m-%dT%H:00:00")
        else:
            truncated = func.date_format(DataRecord.recorded_at, "%Y-%m-%dT00:00:00")

    stmt = (
        select(
            truncated.label("ts_str"),
            func.count(DataRecord.id).label("count"),
            func.avg(DataRecord.value).label("avg_value"),
            func.sum(case((DataRecord.is_anomaly == True, 1), else_=0)).label("anomaly_count"),  # noqa: E712
        )
        .where(DataRecord.recorded_at >= date_from)
        .where(DataRecord.recorded_at <= date_to)
        .group_by("ts_str")
        .order_by("ts_str")
    )
    if category:
        stmt = stmt.where(DataRecord.category == category)

    result = await db.execute(stmt)
    rows = result.all()

    buckets = [
        TimeBucket(
            ts=datetime.fromisoformat(row.ts_str),
            count=row.count,
            avg_value=float(row.avg_value or 0.0),
            anomaly_count=int(row.anomaly_count or 0),
        )
        for row in rows
    ]

    return TimeRangeResponse(buckets=buckets, bucket=bucket)


async def get_categories(
    db: AsyncSession,
    date_from: datetime,
    date_to: datetime,
) -> CategoriesResponse:
    """
    依 category 分組聚合：count / avg_value / anomaly_count。
    使用 SQLAlchemy func.count / func.avg / func.sum + case。
    """
    stmt = (
        select(
            DataRecord.category,
            func.count(DataRecord.id).label("count"),
            func.avg(DataRecord.value).label("avg_value"),
            func.sum(case((DataRecord.is_anomaly == True, 1), else_=0)).label("anomaly_count"),  # noqa: E712
        )
        .where(DataRecord.recorded_at >= date_from)
        .where(DataRecord.recorded_at <= date_to)
        .group_by(DataRecord.category)
        .order_by(DataRecord.category)
    )

    result = await db.execute(stmt)
    rows = result.all()

    categories = [
        CategoryStat(
            category=row.category,
            count=row.count,
            avg_value=float(row.avg_value or 0.0),
            anomaly_count=int(row.anomaly_count or 0),
        )
        for row in rows
    ]

    return CategoriesResponse(categories=categories)
