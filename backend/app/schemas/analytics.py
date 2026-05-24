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
