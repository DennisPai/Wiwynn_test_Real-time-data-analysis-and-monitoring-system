from __future__ import annotations

import os
import subprocess
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router, ws_router
from app.config import settings
from app.db.session import engine
from app.logging_config import configure_logging

configure_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    應用啟動：
    1. alembic upgrade head（非 TESTING 環境）
    2. 啟動 realtime_simulator 與 batch_writer（非 TESTING 環境）
    應用關閉：shutdown scheduler + dispose engine。
    """
    is_testing = os.environ.get("TESTING") == "1"

    if not is_testing:
        logger.info("startup: 執行 alembic upgrade head")
        try:
            subprocess.run(
                ["alembic", "upgrade", "head"],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("startup: migration 完成")
        except subprocess.CalledProcessError as e:
            logger.error("startup: migration 失敗", stderr=e.stderr)
            raise

        # 從 DB 讀取 tick / flush seconds 設定
        try:
            from sqlalchemy import select
            from app.models.app_setting import AppSetting

            async with engine.connect() as conn:
                # 使用原生 select，因為這是 lifespan 初始化，session 尚未就緒
                from sqlalchemy.ext.asyncio import AsyncSession
                from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as sess:
                from sqlalchemy import select as sa_select
                result = await sess.execute(
                    sa_select(AppSetting).where(
                        AppSetting.key.in_([
                            "realtime_tick_seconds",
                            "batch_flush_seconds",
                            "anomaly_threshold_high",
                            "anomaly_threshold_low",
                        ])
                    )
                )
                setting_map = {s.key: s.value for s in result.scalars().all()}

            tick_seconds = int(setting_map.get("realtime_tick_seconds", "1"))
            flush_seconds = int(setting_map.get("batch_flush_seconds", "5"))
            high = float(setting_map.get("anomaly_threshold_high", "80.0"))
            low = float(setting_map.get("anomaly_threshold_low", "10.0"))
        except Exception as exc:
            logger.warning("startup: 讀取設定失敗，使用預設值", error=str(exc))
            tick_seconds = settings.REALTIME_TICK
            flush_seconds = settings.BATCH_FLUSH
            high = settings.ANOMALY_THRESHOLD_HIGH
            low = settings.ANOMALY_THRESHOLD_LOW

        # 啟動 realtime_simulator
        from app.services.realtime_service import realtime_simulator
        realtime_simulator.reload_thresholds(high=high, low=low)
        await realtime_simulator.start(tick_seconds=tick_seconds)

        # 啟動 batch_writer
        from app.services.batch_writer import batch_writer
        await batch_writer.start(flush_seconds=flush_seconds)

        logger.info(
            "startup: scheduler 啟動",
            tick_seconds=tick_seconds,
            flush_seconds=flush_seconds,
        )
    else:
        logger.info("startup: TESTING 模式，跳過 migration + scheduler")

    yield

    logger.info("shutdown: 釋放資源")

    if not is_testing:
        from app.services.realtime_service import realtime_simulator
        from app.services.batch_writer import batch_writer
        realtime_simulator.shutdown()
        batch_writer.shutdown()

    await engine.dispose()


app = FastAPI(
    title="即時資料分析與監控系統 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
# WS endpoint：/ws/realtime（不走 /api/v1 prefix）
app.include_router(ws_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """健康檢查：驗證 DB 連線（#25）。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        logger.error("health check db error", error=str(exc))
        db_status = "error"

    return {"status": "ok", "db": db_status}
