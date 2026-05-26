"""analytics_service.py — T5.6: wide schema 分析服務全重寫。

design.md §5 endpoint 表 + §8 anomaly_detector 規格：
- get_summary()：per-metric breakdown（5 metric 各 avg/min/max/std/anomaly_count）
- get_timerange()：bucket 內含 per-metric aggregate
- get_categories()：沿用 endpoint 名但回傳 per-metric breakdown
- get_unified_summary()：per-source breakdown（user / simulator from data_records + realtime_metric_wide 雙軌）
- get_realtime_categories()：查 realtime_metric_wide（不動）
- _count_realtime_anomaly()：查 realtime_metric_wide anomaly_flags（JSON_EXTRACT 或 Python）
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_record import DataRecord
from app.models.realtime_metric_wide import RealtimeMetricWide
from app.schemas.analytics import (
    CategoriesResponse,
    CombinedSummary,
    MetricBreakdown,
    MetricStat,
    RealtimeCategoriesResponse,
    RealtimeMetricCategory,
    RealtimeMetricStat,
    RealtimeSummary,
    RecordsSummary,
    SourceStat,
    SummaryResponse,
    TimeBucket,
    TimeBucketMetric,
    TimeRangeResponse,
    UnifiedSummaryResponse,
)

_METRICS = ("temperature", "humidity", "pressure", "voltage", "cpu_usage")


# ── helper: anomaly_flags JSON 判定 ─────────────────────────────────────────

def _row_is_anomaly(flags: Any) -> bool:
    """判斷整筆 row 是否有任一 metric 異常（anomaly_flags dict）。"""
    if not isinstance(flags, dict):
        return False
    return any(flags.get(m, False) for m in _METRICS)


def _count_anomaly_from_flags(flags_list: list[Any]) -> int:
    """從 anomaly_flags list 統計有異常的 row 數。"""
    return sum(1 for f in flags_list if _row_is_anomaly(f))


def _metric_is_anomaly(flags: Any, metric: str) -> bool:
    """判斷單一 metric 是否異常。"""
    if not isinstance(flags, dict):
        return False
    return bool(flags.get(metric, False))


# ── get_summary ─────────────────────────────────────────────────────────────

async def get_summary(
    db: AsyncSession,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sources: list[str] | None = None,
) -> SummaryResponse:
    """
    T5.6: per-metric breakdown + top-level total/anomaly_count/anomaly_rate。
    查 data_records（wide schema）。
    """
    # 基礎 filter
    stmt_base = select(DataRecord)
    if date_from is not None:
        stmt_base = stmt_base.where(DataRecord.ts >= date_from)
    if date_to is not None:
        stmt_base = stmt_base.where(DataRecord.ts <= date_to)
    if sources:
        stmt_base = stmt_base.where(DataRecord.source.in_(sources))

    # 取全部 row 的 anomaly_flags + metric 值（Python 端聚合，避免 dialect 差異）
    flags_stmt = select(DataRecord.anomaly_flags)
    if date_from is not None:
        flags_stmt = flags_stmt.where(DataRecord.ts >= date_from)
    if date_to is not None:
        flags_stmt = flags_stmt.where(DataRecord.ts <= date_to)
    if sources:
        flags_stmt = flags_stmt.where(DataRecord.source.in_(sources))
    flags_result = await db.execute(flags_stmt)
    all_flags = flags_result.scalars().all()
    total = len(all_flags)
    anomaly_count = _count_anomaly_from_flags(all_flags)
    anomaly_rate = anomaly_count / total if total > 0 else 0.0

    # per-metric 聚合（avg/min/max/std 用 SQL；anomaly_count 用 Python）
    per_metric: dict[str, MetricStat] = {}
    for metric in _METRICS:
        metric_col = getattr(DataRecord, metric)

        # SQL 聚合
        agg_stmt = select(
            func.avg(metric_col).label("avg"),
            func.min(metric_col).label("min_v"),
            func.max(metric_col).label("max_v"),
        )
        if date_from is not None:
            agg_stmt = agg_stmt.where(DataRecord.ts >= date_from)
        if date_to is not None:
            agg_stmt = agg_stmt.where(DataRecord.ts <= date_to)
        if sources:
            agg_stmt = agg_stmt.where(DataRecord.source.in_(sources))

        agg_row = (await db.execute(agg_stmt)).one()
        avg_val = float(agg_row.avg or 0.0)
        min_val = float(agg_row.min_v or 0.0)
        max_val = float(agg_row.max_v or 0.0)

        # std：從 metric 值手算（DB 端的 STDDEV 方言差異大）
        vals_stmt = select(metric_col).where(metric_col.isnot(None))
        if date_from is not None:
            vals_stmt = vals_stmt.where(DataRecord.ts >= date_from)
        if date_to is not None:
            vals_stmt = vals_stmt.where(DataRecord.ts <= date_to)
        if sources:
            vals_stmt = vals_stmt.where(DataRecord.source.in_(sources))
        vals_result = await db.execute(vals_stmt)
        vals = [float(v) for v in vals_result.scalars().all()]
        if len(vals) > 1:
            mean = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            std_val = math.sqrt(variance)
        else:
            std_val = 0.0

        # metric anomaly_count：從 anomaly_flags Python 計算
        metric_anomaly = sum(1 for f in all_flags if _metric_is_anomaly(f, metric))

        per_metric[metric] = MetricStat(
            avg=avg_val,
            min=min_val,
            max=max_val,
            std=std_val,
            anomaly_count=metric_anomaly,
        )

    return SummaryResponse(
        total=total,
        anomaly_count=anomaly_count,
        anomaly_rate=anomaly_rate,
        per_metric=per_metric,
    )


# ── get_timerange ────────────────────────────────────────────────────────────

async def get_timerange(
    db: AsyncSession,
    date_from: datetime,
    date_to: datetime,
    bucket: str = "hour",
    sources: list[str] | None = None,
) -> TimeRangeResponse:
    """
    T5.6: 按時間桶聚合，bucket 內含 per-metric aggregate。
    SQLite 測試環境：func.strftime；MariaDB 生產：func.date_format。
    """
    # 取 dialect 名稱
    bind = db.get_bind()
    dialect_name: str = bind.dialect.name if bind is not None else "mysql"

    if dialect_name == "sqlite":
        if bucket == "hour":
            truncated = func.strftime("%Y-%m-%dT%H:00:00", DataRecord.ts)
        else:
            truncated = func.strftime("%Y-%m-%dT00:00:00", DataRecord.ts)
    else:
        if bucket == "hour":
            truncated = func.date_format(DataRecord.ts, "%Y-%m-%dT%H:00:00")
        else:
            truncated = func.date_format(DataRecord.ts, "%Y-%m-%dT00:00:00")

    # 取 bucket 分組的 count + anomaly_flags
    base_stmt = (
        select(
            truncated.label("ts_str"),
            DataRecord.anomaly_flags.label("flags"),
        )
        .where(DataRecord.ts >= date_from)
        .where(DataRecord.ts <= date_to)
        .order_by("ts_str")
    )
    if sources:
        base_stmt = base_stmt.where(DataRecord.source.in_(sources))

    base_result = await db.execute(base_stmt)
    base_rows = base_result.all()

    # 依 bucket 分組
    from collections import defaultdict
    bucket_flags: dict[str, list[Any]] = defaultdict(list)
    for row in base_rows:
        bucket_flags[row.ts_str].append(row.flags)

    # 對每個 bucket 做 per-metric 聚合（需要 metric 值，再跑一次查詢）
    # 為效率起見：一次取所有 metric 值 + bucket label
    agg_metric_stmt = select(
        truncated.label("ts_str"),
        DataRecord.temperature.label("temperature"),
        DataRecord.humidity.label("humidity"),
        DataRecord.pressure.label("pressure"),
        DataRecord.voltage.label("voltage"),
        DataRecord.cpu_usage.label("cpu_usage"),
        DataRecord.anomaly_flags.label("flags"),
    ).where(DataRecord.ts >= date_from).where(DataRecord.ts <= date_to)
    if sources:
        agg_metric_stmt = agg_metric_stmt.where(DataRecord.source.in_(sources))

    all_rows_result = await db.execute(agg_metric_stmt)
    all_rows = all_rows_result.all()

    # Python 端 bucket 聚合
    # 結構：{ bucket_ts_str: { metric: [values], flags: [flags] } }
    from collections import defaultdict as dd
    bucket_data: dict[str, dict[str, list]] = dd(lambda: {m: [] for m in _METRICS} | {"flags": []})

    for row in all_rows:
        key = row.ts_str
        for m in _METRICS:
            val = getattr(row, m)
            if val is not None:
                bucket_data[key][m].append(float(val))
        bucket_data[key]["flags"].append(row.flags)

    buckets: list[TimeBucket] = []
    for ts_str in sorted(bucket_data.keys()):
        bdata = bucket_data[ts_str]
        flags_list = bdata["flags"]
        bucket_count = len(flags_list)
        bucket_anomaly = _count_anomaly_from_flags(flags_list)

        per_metric: dict[str, TimeBucketMetric] = {}
        for m in _METRICS:
            vals = bdata[m]
            metric_anomaly = sum(1 for f in flags_list if _metric_is_anomaly(f, m))
            if vals:
                per_metric[m] = TimeBucketMetric(
                    avg=sum(vals) / len(vals),
                    min=min(vals),
                    max=max(vals),
                    count=len(vals),
                    anomaly_count=metric_anomaly,
                )
            else:
                per_metric[m] = TimeBucketMetric(
                    avg=None,
                    min=None,
                    max=None,
                    count=0,
                    anomaly_count=0,
                )

        try:
            ts_dt = datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            ts_dt = date_from  # fallback

        buckets.append(TimeBucket(
            ts=ts_dt,
            count=bucket_count,
            anomaly_count=bucket_anomaly,
            per_metric=per_metric,
        ))

    return TimeRangeResponse(buckets=buckets, bucket=bucket)


# ── get_categories ───────────────────────────────────────────────────────────

async def get_categories(
    db: AsyncSession,
    date_from: datetime,
    date_to: datetime,
    sources: list[str] | None = None,
) -> CategoriesResponse:
    """
    T5.6: 沿用 endpoint 名但回傳 per-metric breakdown（對齊 P2 字面）。
    5 metric 各自統計 count / avg / min / max / anomaly_count。
    """
    # 取所有 row 的 metric 值 + anomaly_flags
    stmt = (
        select(
            DataRecord.temperature,
            DataRecord.humidity,
            DataRecord.pressure,
            DataRecord.voltage,
            DataRecord.cpu_usage,
            DataRecord.anomaly_flags,
        )
        .where(DataRecord.ts >= date_from)
        .where(DataRecord.ts <= date_to)
    )
    if sources:
        stmt = stmt.where(DataRecord.source.in_(sources))

    result = await db.execute(stmt)
    rows = result.all()

    breakdowns: list[MetricBreakdown] = []
    for metric in _METRICS:
        vals = []
        metric_anomaly = 0
        for row in rows:
            val = getattr(row, metric)
            flags = row.anomaly_flags
            if val is not None:
                vals.append(float(val))
            if _metric_is_anomaly(flags, metric):
                metric_anomaly += 1

        if vals:
            avg_val = sum(vals) / len(vals)
            min_val = min(vals)
            max_val = max(vals)
            count = len(vals)
        else:
            avg_val = 0.0
            min_val = 0.0
            max_val = 0.0
            count = 0

        breakdowns.append(MetricBreakdown(
            metric=metric,
            count=count,
            avg=avg_val,
            min=min_val,
            max=max_val,
            anomaly_count=metric_anomaly,
        ))

    return CategoriesResponse(metrics=breakdowns)


# ── get_unified_summary ───────────────────────────────────────────────────────

async def get_unified_summary(
    db: AsyncSession,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sources: list[str] | None = None,
) -> UnifiedSummaryResponse:
    """
    T5.6: per-source breakdown（user / simulator from data_records + realtime_metric_wide 雙軌）。
    保留「即時資料 (realtime_metric_wide) vs 資料記錄 (data_records)」雙軌 unified-summary。

    sources (list[str] | None):
      - None or [] → both（全列 user / simulator_data_records / realtime）
      - ["user"]   → 只回 user SourceStat（simulator_data_records = 0, realtime = None）
      - ["simulator"] → 只回 simulator_data_records（user = 0, realtime = None）
      - can also include "realtime" to query realtime_metric_wide
    response shape: {user: {count, anomaly_count}, simulator_data_records: {count, anomaly_count}, realtime: {count, anomaly_count}}
    """
    # 正規化：None / 空 list → "both" 行為；其他按清單決定
    _sources = set(sources) if sources else {"user", "simulator", "realtime"}

    user_stat: SourceStat | None = None
    simulator_data_stat: SourceStat | None = None
    realtime_stat: SourceStat | None = None

    if "user" in _sources:
        user_stat = await _get_data_records_source_stat(db, "user", date_from, date_to)
    if "simulator" in _sources:
        simulator_data_stat = await _get_data_records_source_stat(db, "simulator", date_from, date_to)
    if "realtime" in _sources:
        # realtime_metric_wide（不動）
        realtime_stat = await _get_realtime_stat(db, date_from, date_to)

    total = 0
    anomaly_count = 0
    if user_stat:
        total += user_stat.count
        anomaly_count += user_stat.anomaly_count
    if simulator_data_stat:
        total += simulator_data_stat.count
        anomaly_count += simulator_data_stat.anomaly_count
    if realtime_stat:
        total += realtime_stat.count
        anomaly_count += realtime_stat.anomaly_count

    return UnifiedSummaryResponse(
        user=user_stat,
        simulator_data_records=simulator_data_stat,
        realtime=realtime_stat,
        total=total,
        anomaly_count=anomaly_count,
    )


async def _get_data_records_source_stat(
    db: AsyncSession,
    source_value: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> SourceStat:
    """從 data_records 統計指定 source 的 count + anomaly_count。"""
    flags_stmt = select(DataRecord.anomaly_flags).where(DataRecord.source == source_value)
    if date_from is not None:
        flags_stmt = flags_stmt.where(DataRecord.ts >= date_from)
    if date_to is not None:
        flags_stmt = flags_stmt.where(DataRecord.ts <= date_to)
    flags_result = await db.execute(flags_stmt)
    all_flags = flags_result.scalars().all()
    count = len(all_flags)
    anomaly_count = _count_anomaly_from_flags(all_flags)
    return SourceStat(count=count, anomaly_count=anomaly_count)


async def _get_realtime_stat(
    db: AsyncSession,
    date_from: datetime | None,
    date_to: datetime | None,
) -> SourceStat:
    """從 realtime_metric_wide 統計 count + anomaly_count。"""
    flags_stmt = select(RealtimeMetricWide.anomaly_flags)
    if date_from is not None:
        flags_stmt = flags_stmt.where(RealtimeMetricWide.ts >= date_from)
    if date_to is not None:
        flags_stmt = flags_stmt.where(RealtimeMetricWide.ts <= date_to)
    flags_result = await db.execute(flags_stmt)
    all_flags = flags_result.scalars().all()
    count = len(all_flags)
    anomaly_count = _count_anomaly_from_flags(all_flags)
    return SourceStat(count=count, anomaly_count=anomaly_count)


# ── get_realtime_categories（查 realtime_metric_wide，保留不動）──────────────

async def get_realtime_categories(
    db: AsyncSession,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> RealtimeCategoriesResponse:
    """
    T5.6: 即時資料各 metric 分佈統計。
    查 realtime_metric_wide（保留不動，scope 限縮 A）。
    """
    metrics_result: list[RealtimeMetricCategory] = []

    for metric_name in _METRICS:
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

        metrics_result.append(
            RealtimeMetricCategory(
                metric=metric_name,
                count=count,
                avg=avg_val,
                anomaly_count=anomaly_count,
            )
        )

    return RealtimeCategoriesResponse(metrics=metrics_result)


async def _count_realtime_anomaly(
    db: AsyncSession,
    metric_name: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> int:
    """
    T5.6: 計算 realtime_metric_wide 中某 metric 的異常數。
    Python 端讀取 anomaly_flags，避免 dialect 差異。
    """
    stmt = select(RealtimeMetricWide.anomaly_flags)
    if date_from is not None:
        stmt = stmt.where(RealtimeMetricWide.ts >= date_from)
    if date_to is not None:
        stmt = stmt.where(RealtimeMetricWide.ts <= date_to)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return sum(1 for flags in rows if _metric_is_anomaly(flags, metric_name))
