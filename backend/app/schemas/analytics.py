from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Summary（per-metric breakdown）────────────────────────────
class MetricStat(BaseModel):
    """單一 metric 的統計資料（T5.6）。"""
    avg: float
    min: float
    max: float
    std: float
    anomaly_count: int


class SummaryResponse(BaseModel):
    """GET /api/v1/analytics/summary 回傳格式（T5.6 wide schema）。"""
    total: int
    anomaly_count: int
    anomaly_rate: float
    per_metric: dict[str, MetricStat]


# ── TimeRange（per-metric aggregate）─────────────────────────
class TimeBucketMetric(BaseModel):
    """單一 bucket 單一 metric 的聚合（T5.6）。"""
    avg: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    count: int = 0
    anomaly_count: int = 0


class TimeBucket(BaseModel):
    """GET /api/v1/analytics/timerange bucket（T5.6 wide schema）。"""
    ts: datetime
    count: int
    anomaly_count: int
    per_metric: dict[str, TimeBucketMetric]


class TimeRangeResponse(BaseModel):
    buckets: list[TimeBucket]
    bucket: str  # "hour" or "day"


# ── Categories（per-metric breakdown，endpoint 名稱保留對齊 P2）──
class MetricBreakdown(BaseModel):
    """單一 metric 的 breakdown（T5.6 categories endpoint）。"""
    metric: str
    count: int
    avg: float
    min: float
    max: float
    anomaly_count: int


class CategoriesResponse(BaseModel):
    """GET /api/v1/analytics/categories 回傳格式（T5.6：改為 per-metric breakdown）。"""
    metrics: list[MetricBreakdown]


# ── Unified summary（per-source breakdown，T5.6）──────────────
class SourceStat(BaseModel):
    """單一 source 的統計（T5.6 unified-summary）。"""
    count: int
    anomaly_count: int


class UnifiedSummaryResponse(BaseModel):
    """GET /api/v1/analytics/unified-summary（T5.6：per-source breakdown + realtime_metric_wide 雙軌）。"""
    user: Optional[SourceStat] = None
    simulator_data_records: Optional[SourceStat] = None  # data_records source='simulator'
    realtime: Optional[SourceStat] = None  # realtime_metric_wide（不動）
    total: int = 0
    anomaly_count: int = 0


# ── Realtime categories（查 realtime_metric_wide，T5.6 保留）───
class RealtimeMetricStat(BaseModel):
    avg: float
    min: float
    max: float
    anomaly_count: int


class RealtimeSummary(BaseModel):
    total: int
    anomaly_count: int
    metrics: dict[str, RealtimeMetricStat]


class RecordsSummary(BaseModel):
    total: int
    anomaly_count: int
    categories: list[str]


class CombinedSummary(BaseModel):
    total: int
    anomaly_count: int


class RealtimeMetricCategory(BaseModel):
    metric: str
    count: int
    avg: float
    anomaly_count: int


class RealtimeCategoriesResponse(BaseModel):
    metrics: list[RealtimeMetricCategory]
