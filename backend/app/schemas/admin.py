from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, model_validator


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    action: str
    target_type: str | None
    target_id: str | None
    meta: Any | None = None
    ts: datetime

    model_config = {"from_attributes": True}


class PoolInfo(BaseModel):
    size: int
    checked_out: int
    overflow: int


class TableInfo(BaseModel):
    name: str
    row_count: int


class DBStatusResponse(BaseModel):
    ok: bool
    pool: PoolInfo
    tables: list[TableInfo]


class RealtimeMetricResponse(BaseModel):
    """Legacy long-format response (kept for backward compat)."""

    id: int
    value: float
    category: str
    ts: datetime
    source: str
    is_anomaly: bool

    model_config = {"from_attributes": True}


class AppSettingResponse(BaseModel):
    id: int
    key: str
    value: str
    description: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class AppSettingUpdate(BaseModel):
    value: str


# T5.9: PATCH /api/v1/admin/settings（anomaly threshold）schema

class MetricThreshold(BaseModel):
    """單一 metric 的 high/low threshold。high 必須嚴格大於 low。"""
    high: float
    low: float

    @model_validator(mode="after")
    def high_must_be_greater_than_low(self) -> "MetricThreshold":
        if self.high <= self.low:
            raise ValueError(
                f"high（{self.high}）必須嚴格大於 low（{self.low}）"
            )
        return self


class AnomalyThresholdUpdate(BaseModel):
    """PATCH /api/v1/admin/settings body: anomaly_threshold per-metric dict。"""
    anomaly_threshold: dict[str, MetricThreshold]


class AnomalyThresholdResponse(BaseModel):
    """PATCH /api/v1/admin/settings response。"""
    updated_keys: list[str]
    anomaly_threshold: dict[str, MetricThreshold]
