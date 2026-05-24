from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DataRecordResponse(BaseModel):
    id: int
    title: str
    value: float  # R7: Decimal in / float out
    category: str
    recorded_at: datetime
    is_anomaly: bool
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataCreate(BaseModel):
    title: str
    value: Decimal  # R7: Pydantic 自動 coerce
    category: str
    recorded_at: datetime
    is_anomaly: bool = False


class DataUpdate(BaseModel):
    title: str | None = None
    value: Decimal | None = None
    category: str | None = None
    recorded_at: datetime | None = None
    is_anomaly: bool | None = None


class BulkImportError(BaseModel):
    row: int
    reason: str


class BulkImportResponse(BaseModel):
    inserted: int
    failed: int
    errors: list[BulkImportError]
