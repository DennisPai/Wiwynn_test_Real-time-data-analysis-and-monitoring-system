from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AnyRole, get_db
from app.models.realtime_metric_wide import RealtimeMetricWide
from app.models.user import User
from app.schemas.realtime import RealtimeHistoryResponse, RealtimeSnapshotResponse

router = APIRouter(prefix="/realtime", tags=["realtime"])


@router.get("/history", response_model=RealtimeHistoryResponse)
async def realtime_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    seconds: int = Query(60, ge=1, le=3600),
) -> RealtimeHistoryResponse:
    """
    取得最近 N 秒的 wide snapshot 歷史（任何已登入角色可讀）。
    預設 seconds=60，最大 3600。
    回傳 wide rows 陣列（ts + 5 metric value + anomaly_flags）。
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(seconds=seconds)
    stmt = (
        select(RealtimeMetricWide)
        .where(RealtimeMetricWide.ts >= cutoff)
        .order_by(RealtimeMetricWide.ts.asc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    snapshots = [RealtimeSnapshotResponse.model_validate(r) for r in rows]
    return RealtimeHistoryResponse(snapshots=snapshots, count=len(snapshots))
