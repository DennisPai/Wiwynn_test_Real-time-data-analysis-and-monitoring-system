from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AnyRole, get_db
from app.models.user import User
from app.schemas.analytics import (
    CategoriesResponse,
    RealtimeCategoriesResponse,
    SummaryResponse,
    TimeRangeResponse,
    UnifiedSummaryResponse,
)
from app.services import analytics_service
from app.utils.excel_exporter import build_excel_response

router = APIRouter(prefix="/analytics", tags=["analytics"])

_VALID_BUCKETS = {"hour", "day"}


def _to_naive_utc(dt: datetime) -> datetime:
    """
    把任意 datetime 轉成 naive UTC（去掉 tzinfo）。
    防止 tz-aware FE input vs naive DB column 的比對全 false（Q7 root cause B 防衛）。
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


@router.get("/summary", response_model=SummaryResponse)
async def analytics_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    category: str | None = Query(None),
) -> SummaryResponse:
    """
    聚合統計（任何已登入角色可讀）。
    回傳：total_records / anomaly_count / avg_value / min_value / max_value / categories。
    """
    return await analytics_service.get_summary(
        db, date_from=date_from, date_to=date_to, category=category
    )


@router.get("/timerange", response_model=TimeRangeResponse)
async def analytics_timerange(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    bucket: str = Query("hour", description="時間桶大小：hour 或 day"),
    category: str | None = Query(None),
) -> TimeRangeResponse:
    """
    按時間桶聚合（任何已登入角色可讀）。
    bucket 接受 hour 或 day，其他值回 422。
    C3-2: 轉 naive UTC 防止 tz-aware vs naive DB column 比對全 false（Q7 root cause B 防衛）。
    """
    if bucket not in _VALID_BUCKETS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bucket 只接受 hour 或 day",
        )
    return await analytics_service.get_timerange(
        db,
        date_from=_to_naive_utc(date_from),
        date_to=_to_naive_utc(date_to),
        bucket=bucket,
        category=category,
    )


@router.get("/categories", response_model=CategoriesResponse)
async def analytics_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
) -> CategoriesResponse:
    """
    依 category 分組聚合（任何已登入角色可讀）。
    回傳各 category 的 count / avg_value / anomaly_count。
    """
    return await analytics_service.get_categories(db, date_from=date_from, date_to=date_to)


@router.get("/export")
async def analytics_export(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    category: str | None = Query(None),
) -> StreamingResponse:
    """
    匯出 Excel 分析報告（任何已登入角色可下載）。
    包含 Summary / TimeRange（day 桶）/ Categories 三個 sheet。
    Content-Disposition: attachment; filename="data_YYYY-MM-DD.xlsx"
    """
    # 取得各分析資料
    summary = await analytics_service.get_summary(
        db, date_from=date_from, date_to=date_to, category=category
    )

    # export 用 day 桶
    effective_from = date_from or datetime(2000, 1, 1)
    effective_to = date_to or datetime(2100, 12, 31)

    timerange = await analytics_service.get_timerange(
        db,
        date_from=effective_from,
        date_to=effective_to,
        bucket="day",
        category=category,
    )

    categories_resp = await analytics_service.get_categories(
        db, date_from=effective_from, date_to=effective_to
    )

    return build_excel_response(
        summary=summary,
        timerange=timerange,
        categories=categories_resp,
        export_date=datetime.utcnow().date(),
    )


@router.get("/unified-summary", response_model=UnifiedSummaryResponse)
async def analytics_unified_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    source: str = Query("both", description="both | realtime | records"),
) -> UnifiedSummaryResponse:
    """
    統一 realtime + records 兩 source 的摘要（Q8）。任何已登入角色可讀。
    source 可選 both / realtime / records。
    """
    return await analytics_service.get_unified_summary(
        db,
        date_from=date_from,
        date_to=date_to,
        source=source,
    )


@router.get("/realtime-categories", response_model=RealtimeCategoriesResponse)
async def analytics_realtime_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> RealtimeCategoriesResponse:
    """
    即時資料各 metric 分佈統計（Q11）。任何已登入角色可讀。
    回傳 5 個 metric 的 count / avg / anomaly_count。
    """
    return await analytics_service.get_realtime_categories(
        db,
        date_from=date_from,
        date_to=date_to,
    )
