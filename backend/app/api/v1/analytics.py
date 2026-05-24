from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AnyRole, get_db
from app.models.user import User
from app.schemas.analytics import CategoriesResponse, SummaryResponse, TimeRangeResponse
from app.services import analytics_service
from app.utils.excel_exporter import build_excel_response

router = APIRouter(prefix="/analytics", tags=["analytics"])

_VALID_BUCKETS = {"hour", "day"}


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
    """
    if bucket not in _VALID_BUCKETS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bucket 只接受 hour 或 day",
        )
    return await analytics_service.get_timerange(
        db, date_from=date_from, date_to=date_to, bucket=bucket, category=category
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
