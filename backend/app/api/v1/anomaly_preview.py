"""anomaly_preview.py — T5.10: GET /api/v1/anomaly-preview endpoint。

design.md §5: FE inline edit 預設值用。
query：temperature=80&humidity=60&...
response：{anomaly_flags: {temperature: false, ...}}
任何 role 可呼叫。
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AnyRole, get_db
from app.models.user import User
from app.schemas.data_record import AnomalyFlags
from app.services.anomaly_detector import AnomalyDetector

router = APIRouter(prefix="/anomaly-preview", tags=["anomaly-preview"])


class AnomalyPreviewResponse:
    """response schema 使用 dict 直接回傳（Pydantic model inline）。"""
    pass


@router.get("", response_model=dict)
async def anomaly_preview(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    temperature: Optional[float] = Query(None, description="溫度 °C"),
    humidity: Optional[float] = Query(None, description="濕度 %"),
    pressure: Optional[float] = Query(None, description="壓力 kPa"),
    voltage: Optional[float] = Query(None, description="電壓 V"),
    cpu_usage: Optional[float] = Query(None, description="CPU 使用率 %"),
) -> dict:
    """
    T5.10: FE inline edit 預設值用。任何 role 可呼叫。
    query 傳入 5 metric 值（全 optional），回傳 anomaly_flags per-metric bool dict。
    使用 AnomalyDetector 統一判定邏輯（禁 inline if/else）。
    """
    snapshot = {
        "temperature": temperature,
        "humidity": humidity,
        "pressure": pressure,
        "voltage": voltage,
        "cpu_usage": cpu_usage,
    }

    flags = await AnomalyDetector.compute_anomaly_flags(db, snapshot)

    return {"anomaly_flags": flags}
