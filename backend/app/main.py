from __future__ import annotations

import subprocess
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.config import settings
from app.db.session import engine
from app.logging_config import configure_logging

configure_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """應用啟動時執行 alembic upgrade head；關閉時釋放連線池。"""
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

    # APScheduler placeholder（Phase B3 補完）
    logger.info("startup: APScheduler placeholder（B3 補完）")

    yield

    logger.info("shutdown: 釋放 DB 連線池")
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


@app.get("/health", tags=["health"])
async def health() -> dict:
    """健康檢查：驗證 DB 連線。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        logger.error("health check db error", error=str(exc))
        db_status = "error"

    return {"status": "ok", "db": db_status}
