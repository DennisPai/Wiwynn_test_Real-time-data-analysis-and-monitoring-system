from __future__ import annotations

import os
from datetime import datetime
from math import ceil
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminOnly, get_db
from app.models.app_setting import AppSetting
from app.models.audit_log import AuditLog
from app.models.data_record import DataRecord
from app.models.realtime_metric import RealtimeMetric
from app.models.user import User
from app.schemas.admin import (
    AppSettingResponse,
    AppSettingUpdate,
    AuditLogResponse,
    DBStatusResponse,
    PoolInfo,
    RealtimeMetricResponse,
    TableInfo,
)
from app.schemas.user import PaginatedResponse
from app.services.audit_log_service import write_audit_log

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/logs", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> PaginatedResponse[AuditLogResponse]:
    """列出 audit_log（#19）。admin 限定。"""
    stmt = select(AuditLog)

    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from is not None:
        stmt = stmt.where(AuditLog.ts >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.ts <= date_to)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(AuditLog.ts.desc())
    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)

    result = await db.execute(stmt)
    logs = result.scalars().all()
    pages = ceil(total / size) if size > 0 else 0

    return PaginatedResponse[AuditLogResponse](
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/db-status", response_model=DBStatusResponse)
async def db_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
) -> DBStatusResponse:
    """
    DB 連線池狀態 + 各 table row count（#20）。admin 限定。
    pool stats 從 sync pool 物件讀取（SQLAlchemy async engine 底層）。
    table row count 走 ORM select(func.count()).select_from(Model)。
    """
    from app.db.session import engine

    # pool stats（async engine 底層是 sync pool）
    sync_engine = engine.sync_engine
    pool = sync_engine.pool
    try:
        pool_size = pool.size()
        checked_out = pool.checkedout()
        overflow = pool.overflow()
    except Exception:
        # aiosqlite / NullPool 沒有這些方法，fallback 為 0
        pool_size = 0
        checked_out = 0
        overflow = 0

    # table row counts（ORM，禁 raw SQL）
    table_models = [
        ("users", User),
        ("data_records", DataRecord),
        ("audit_logs", AuditLog),
        ("realtime_metrics", RealtimeMetric),
        ("app_settings", AppSetting),
    ]
    tables: list[TableInfo] = []
    for name, model in table_models:
        count = (
            await db.execute(select(func.count()).select_from(model))
        ).scalar_one()
        tables.append(TableInfo(name=name, row_count=count))

    return DBStatusResponse(
        ok=True,
        pool=PoolInfo(size=pool_size, checked_out=checked_out, overflow=overflow),
        tables=tables,
    )


@router.get("/realtime-history", response_model=PaginatedResponse[RealtimeMetricResponse])
async def realtime_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    category: str | None = Query(None),
) -> PaginatedResponse[RealtimeMetricResponse]:
    """列出即時指標歷史（#21）。admin 限定。"""
    stmt = select(RealtimeMetric)

    if category:
        stmt = stmt.where(RealtimeMetric.category == category)
    if date_from is not None:
        stmt = stmt.where(RealtimeMetric.ts >= date_from)
    if date_to is not None:
        stmt = stmt.where(RealtimeMetric.ts <= date_to)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(RealtimeMetric.ts.desc())
    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)

    result = await db.execute(stmt)
    metrics = result.scalars().all()
    pages = ceil(total / size) if size > 0 else 0

    return PaginatedResponse[RealtimeMetricResponse](
        items=[RealtimeMetricResponse.model_validate(m) for m in metrics],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/settings", response_model=list[AppSettingResponse])
async def list_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
) -> list[AppSettingResponse]:
    """列出所有 app_settings（#22）。admin 限定。"""
    result = await db.execute(select(AppSetting).order_by(AppSetting.key))
    settings = result.scalars().all()
    return [AppSettingResponse.model_validate(s) for s in settings]


@router.patch("/settings/{key}", response_model=AppSettingResponse)
async def update_setting(
    key: str,
    body: AppSettingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
) -> AppSettingResponse:
    """
    更新 app_settings 的 value（#23）。admin 限定。
    更新後即時觸發 realtime_simulator.reload_thresholds。
    """
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"設定 {key!r} 不存在",
        )

    setting.value = body.value
    await db.flush()
    await db.refresh(setting)

    # 寫入 audit_log
    await write_audit_log(
        db,
        action="update_setting",
        user_id=current_user.id,
        target_type="app_setting",
        target_id=key,
        meta={"new_value": body.value},
    )

    # 若是 threshold / tick 相關設定，立即更新 realtime_simulator
    # 只在非 TESTING 環境下更新（測試時 simulator 未啟動）
    if os.environ.get("TESTING") != "1":
        _reload_simulator_if_needed(db, key, body.value)

    return AppSettingResponse.model_validate(setting)


def _reload_simulator_if_needed(db: AsyncSession, changed_key: str, new_value: str) -> None:
    """
    當 threshold 相關 key 被修改時，非同步更新 realtime_simulator。
    此函式不做 DB 查詢（避免重入 session），直接用 changed_key 判斷。
    """
    threshold_keys = {
        "anomaly_threshold_high",
        "anomaly_threshold_low",
        "realtime_tick_seconds",
    }
    if changed_key not in threshold_keys:
        return

    try:
        from app.services.realtime_service import realtime_simulator

        # 無法在此直接做 DB 查詢，改用 cache 的 _high/_low 更新
        # 若只改了其中一個，其他保持不變
        if changed_key == "anomaly_threshold_high":
            realtime_simulator.reload_thresholds(
                high=float(new_value),
                low=realtime_simulator._low,
            )
        elif changed_key == "anomaly_threshold_low":
            realtime_simulator.reload_thresholds(
                high=realtime_simulator._high,
                low=float(new_value),
            )
        elif changed_key == "realtime_tick_seconds":
            realtime_simulator.reload_thresholds(
                high=realtime_simulator._high,
                low=realtime_simulator._low,
                tick_seconds=int(new_value),
            )
    except Exception as exc:
        logger.warning("admin: reload_thresholds 失敗", error=str(exc))
