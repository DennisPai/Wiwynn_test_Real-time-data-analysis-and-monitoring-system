from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceEnum(str, Enum):
    """data_records.source 欄位的合法值（懷特 5/26 拍板 2 值）。"""

    user = "user"
    simulator = "simulator"


class AnomalyFlags(BaseModel):
    """per-metric 異常標記，5 key 完整、不得多 key。"""

    temperature: bool = False
    humidity: bool = False
    pressure: bool = False
    voltage: bool = False
    cpu_usage: bool = False

    model_config = ConfigDict(extra="forbid")


class DataCreate(BaseModel):
    """POST /api/v1/data + bulk-import 共用：至少 1 個 metric 非 None。"""

    ts: datetime
    temperature: Optional[Decimal] = None
    humidity: Optional[Decimal] = None
    pressure: Optional[Decimal] = None
    voltage: Optional[Decimal] = None
    cpu_usage: Optional[Decimal] = None
    anomaly_flags: AnomalyFlags = Field(default_factory=AnomalyFlags)
    source: SourceEnum = SourceEnum.user
    note: Optional[str] = Field(default=None, max_length=200)
    owner_email: Optional[str] = None  # bulk-import admin 模式指定 owner

    @model_validator(mode="after")
    def at_least_one_metric(self) -> "DataCreate":
        metrics = (
            self.temperature,
            self.humidity,
            self.pressure,
            self.voltage,
            self.cpu_usage,
        )
        if all(m is None for m in metrics):
            raise ValueError(
                "至少需填 1 個 metric（temperature / humidity / pressure / voltage / cpu_usage）"
            )
        return self


class DataUpdate(BaseModel):
    """PATCH /api/v1/data/{id}：全部欄位 optional；前端可部分更新。"""

    ts: Optional[datetime] = None
    temperature: Optional[Decimal] = None
    humidity: Optional[Decimal] = None
    pressure: Optional[Decimal] = None
    voltage: Optional[Decimal] = None
    cpu_usage: Optional[Decimal] = None
    anomaly_flags: Optional[AnomalyFlags] = None
    source: Optional[SourceEnum] = None
    note: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def no_all_metrics_null_if_any_metric_specified(self) -> "DataUpdate":
        """若 DataUpdate 同時指定了所有 5 個 metric 且均為 None，拒絕（資料庫層 CHECK constraint 也會擋）。
        僅在所有 5 個欄位都明確傳入且全為 None 時才報錯；若只傳部分欄位則後端與現有 DB 值合併後再做判斷。
        注意：DataUpdate 是 partial update，此 validator 僅驗證欄位全被設成 None 的極端情況。
        實際「至少 1 metric」的強制在 data_service.update_record() 做 merge 後驗證。
        """
        # 若 5 個都明確傳 None，前端一定在清空全部 metric，直接拒絕
        all_sent = all(
            f in (self.model_fields_set if hasattr(self, "model_fields_set") else set())
            for f in ("temperature", "humidity", "pressure", "voltage", "cpu_usage")
        )
        if all_sent:
            metrics = (
                self.temperature,
                self.humidity,
                self.pressure,
                self.voltage,
                self.cpu_usage,
            )
            if all(m is None for m in metrics):
                raise ValueError(
                    "至少需保留 1 個 metric 非 NULL"
                )
        return self


class DataRecordResponse(BaseModel):
    """GET /api/v1/data + GET /api/v1/data/{id} + PATCH response：13 欄完整 wide schema。"""

    id: int
    ts: datetime
    temperature: Optional[Decimal] = None
    humidity: Optional[Decimal] = None
    pressure: Optional[Decimal] = None
    voltage: Optional[Decimal] = None
    cpu_usage: Optional[Decimal] = None
    anomaly_flags: AnomalyFlags
    source: SourceEnum
    note: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkImportError(BaseModel):
    """bulk-import 單行錯誤，新增 missing_columns 欄位（design.md §5 AC）。"""

    row: int
    reason: str
    missing_columns: list[str] = []


class BulkImportResponse(BaseModel):
    """POST /api/v1/data/bulk-import response shape（不變）。"""

    inserted: int
    failed: int
    errors: list[BulkImportError]
