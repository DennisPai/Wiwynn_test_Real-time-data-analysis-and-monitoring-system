from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


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
