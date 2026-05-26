from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RealtimeSnapshot(BaseModel):
    """即時資料 wide snapshot（廣播 payload + batch_writer enqueue）。"""

    schema_version: Literal["v2"] = "v2"
    ts: datetime  # tz-aware UTC
    temperature: float
    humidity: float
    pressure: float
    voltage: float
    cpu_usage: float
    anomaly_flags: dict[str, bool]


class RealtimeSnapshotResponse(BaseModel):
    """從 DB RealtimeMetricWide 讀出後回傳 FE 的 schema。"""

    schema_version: Literal["v2"] = "v2"
    ts: datetime
    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    voltage: float | None = None
    cpu_usage: float | None = None
    anomaly_flags: dict[str, bool]
    source: str = "simulator"

    model_config = {"from_attributes": True}


class RealtimeHistoryResponse(BaseModel):
    """GET /api/v1/realtime/history 回傳格式。"""

    snapshots: list[RealtimeSnapshotResponse]
    count: int
