from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_record import DataRecord
from app.models.realtime_metric_wide import RealtimeMetricWide
from app.schemas.analytics import (
    CategoriesResponse,
    CategoryStat,
    CombinedSummary,
    RealtimeCategoriesResponse,
    RealtimeMetricCategory,
    RealtimeMetricStat,
    RealtimeSummary,
    RecordsSummary,
    SummaryResponse,
    TimeBucket,
    TimeRangeResponse,
    UnifiedSummaryResponse,
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


_REALTIME_METRICS = ["temperature", "humidity", "pressure", "voltage", "cpu_usage"]


async def get_unified_summary(
    db: AsyncSession,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    source: str = "both",
) -> UnifiedSummaryResponse:
    """
    統一 realtime + records 兩 source 的摘要（Q8 / §6.5）。
    source: "both" | "realtime" | "records"
    """
    realtime_summary: RealtimeSummary | None = None
    records_summary: RecordsSummary | None = None

    if source in ("both", "realtime"):
        realtime_summary = await _get_realtime_summary(db, date_from, date_to)

    if source in ("both", "records"):
        records_summary = await _get_records_summary(db, date_from, date_to)

    combined: CombinedSummary | None = None
    if source == "both" and realtime_summary is not None and records_summary is not None:
        combined = CombinedSummary(
            total=realtime_summary.total + records_summary.total,
            anomaly_count=realtime_summary.anomaly_count + records_summary.anomaly_count,
        )

    return UnifiedSummaryResponse(
        source=source,
        realtime=realtime_summary,
        records=records_summary,
        combined=combined,
    )


async def _get_realtime_summary(
    db: AsyncSession,
    date_from: datetime | None,
    date_to: datetime | None,
) -> RealtimeSummary:
    """從 realtime_metrics_wide 計算各 metric 的 avg/min/max/anomaly_count。"""
    # 總筆數
    count_stmt = select(func.count(RealtimeMetricWide.id))
    if date_from is not None:
        count_stmt = count_stmt.where(RealtimeMetricWide.ts >= date_from)
    if date_to is not None:
        count_stmt = count_stmt.where(RealtimeMetricWide.ts <= date_to)
    total = (await db.execute(count_stmt)).scalar_one() or 0

    # 各 metric 聚合
    metrics_stats: dict[str, RealtimeMetricStat] = {}
    total_anomaly = 0

    for metric_name in _REALTIME_METRICS:
        metric_col = getattr(RealtimeMetricWide, metric_name)
        agg_stmt = select(
            func.avg(metric_col).label("avg"),
            func.min(metric_col).label("min"),
            func.max(metric_col).label("max"),
        )
        if date_from is not None:
            agg_stmt = agg_stmt.where(RealtimeMetricWide.ts >= date_from)
        if date_to is not None:
            agg_stmt = agg_stmt.where(RealtimeMetricWide.ts <= date_to)
        agg_row = (await db.execute(agg_stmt)).one()

        # anomaly_count：從 anomaly_flags JSON 欄位統計（JSON path 在 SQLite/MariaDB 不同）
        # 改用 Python 計算避免 dialect 差異
        anomaly_count = await _count_realtime_anomaly(db, metric_name, date_from, date_to)
        total_anomaly += anomaly_count

        metrics_stats[metric_name] = RealtimeMetricStat(
            avg=float(agg_row.avg or 0.0),
            min=float(agg_row.min or 0.0),
            max=float(agg_row.max or 0.0),
            anomaly_count=anomaly_count,
        )

    return RealtimeSummary(
        total=total,
        anomaly_count=total_anomaly,
        metrics=metrics_stats,
    )


async def _count_realtime_anomaly(
    db: AsyncSession,
    metric_name: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> int:
    """
    計算 realtime_metrics_wide 中某 metric 的異常數。
    anomaly_flags 是 JSON 欄位，Python 端讀取後計算，避免 dialect 差異。
    """
    stmt = select(RealtimeMetricWide.anomaly_flags)
    if date_from is not None:
        stmt = stmt.where(RealtimeMetricWide.ts >= date_from)
    if date_to is not None:
        stmt = stmt.where(RealtimeMetricWide.ts <= date_to)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return sum(1 for flags in rows if flags and flags.get(metric_name, False))


async def _get_records_summary(
    db: AsyncSession,
    date_from: datetime | None,
    date_to: datetime | None,
) -> RecordsSummary:
    """從 data_records 計算摘要。"""
    agg_stmt = select(
        func.count(DataRecord.id),
        func.sum(case((DataRecord.is_anomaly == True, 1), else_=0)),  # noqa: E712
    )
    if date_from is not None:
        agg_stmt = agg_stmt.where(DataRecord.recorded_at >= date_from)
    if date_to is not None:
        agg_stmt = agg_stmt.where(DataRecord.recorded_at <= date_to)

    row = (await db.execute(agg_stmt)).one()
    total = row[0] or 0
    anomaly_count = int(row[1] or 0)

    cat_stmt = select(DataRecord.category).distinct()
    if date_from is not None:
        cat_stmt = cat_stmt.where(DataRecord.recorded_at >= date_from)
    if date_to is not None:
        cat_stmt = cat_stmt.where(DataRecord.recorded_at <= date_to)
    cat_result = await db.execute(cat_stmt)
    categories = [r[0] for r in cat_result.all()]

    return RecordsSummary(total=total, anomaly_count=anomaly_count, categories=categories)


async def get_realtime_categories(
    db: AsyncSession,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> RealtimeCategoriesResponse:
    """
    即時資料各 metric 分佈統計（Q11 / §6.6）。
    對 RealtimeMetricWide 跑 5 個 metric 聚合：count / avg / anomaly_count。
    """
    metrics: list[RealtimeMetricCategory] = []

    for metric_name in _REALTIME_METRICS:
        metric_col = getattr(RealtimeMetricWide, metric_name)
        agg_stmt = select(
            func.count(metric_col).label("count"),
            func.avg(metric_col).label("avg"),
        )
        if date_from is not None:
            agg_stmt = agg_stmt.where(RealtimeMetricWide.ts >= date_from)
        if date_to is not None:
            agg_stmt = agg_stmt.where(RealtimeMetricWide.ts <= date_to)

        agg_row = (await db.execute(agg_stmt)).one()
        count = agg_row.count or 0
        avg_val = float(agg_row.avg or 0.0)

        anomaly_count = await _count_realtime_anomaly(db, metric_name, date_from, date_to)

        metrics.append(
            RealtimeMetricCategory(
                metric=metric_name,
                count=count,
                avg=avg_val,
                anomaly_count=anomaly_count,
            )
        )

    return RealtimeCategoriesResponse(metrics=metrics)
