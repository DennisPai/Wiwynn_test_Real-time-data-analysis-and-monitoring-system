from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SummaryResponse(BaseModel):
    total_records: int
    anomaly_count: int
    avg_value: float
    min_value: float
    max_value: float
    categories: list[str]


class TimeBucket(BaseModel):
    ts: datetime
    count: int
    avg_value: float
    anomaly_count: int


class TimeRangeResponse(BaseModel):
    buckets: list[TimeBucket]
    bucket: str  # "hour" or "day"


class CategoryStat(BaseModel):
    category: str
    count: int
    avg_value: float
    anomaly_count: int


class CategoriesResponse(BaseModel):
    categories: list[CategoryStat]


# ── Unified summary（Q8）──────────────────────────────────────

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


class UnifiedSummaryResponse(BaseModel):
    source: str  # "both" | "realtime" | "records"
    realtime: RealtimeSummary | None = None
    records: RecordsSummary | None = None
    combined: CombinedSummary | None = None


# ── Realtime categories（Q11）────────────────────────────────

class RealtimeMetricCategory(BaseModel):
    metric: str
    count: int
    avg: float
    anomaly_count: int


class RealtimeCategoriesResponse(BaseModel):
    metrics: list[RealtimeMetricCategory]
