from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from queue import Empty as QueueEmpty

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.ws_manager import realtime_queue
from app.db.session import AsyncSessionLocal
from app.models.realtime_metric import RealtimeMetric

logger = structlog.get_logger(__name__)


class BatchWriter:
    """
    APScheduler AsyncIOScheduler 驅動的批次寫入器。
    每 M 秒 drain asyncio.Queue，一次性 add_all + commit 至 RealtimeMetric。
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._flush_seconds: int = 5
        self._running = False

    async def _flush(self) -> None:
        """Drain queue 並批次寫入 DB。"""
        ticks: list = []
        # asyncio.Queue 沒有 Empty exception，用 get_nowait + try/while 取盡
        while True:
            try:
                tick = realtime_queue.get_nowait()
                ticks.append(tick)
            except asyncio.QueueEmpty:
                break

        if not ticks:
            return

        metrics = [
            RealtimeMetric(
                value=Decimal(str(round(tick.value, 4))),
                category=tick.category,
                ts=datetime.now(tz=timezone.utc),
                source="simulator",
                is_anomaly=tick.is_anomaly,
            )
            for tick in ticks
        ]

        try:
            async with AsyncSessionLocal() as session:
                session.add_all(metrics)
                await session.commit()
            logger.info("batch_writer: flush 完成", count=len(metrics))
        except Exception as exc:
            logger.error("batch_writer: flush 失敗", error=str(exc))

    async def start(self, flush_seconds: int = 5) -> None:
        """啟動 APScheduler 排程。"""
        if self._running:
            return
        self._flush_seconds = flush_seconds
        self._scheduler.add_job(
            self._flush,
            "interval",
            seconds=self._flush_seconds,
            id="batch_flush",
            replace_existing=True,
        )
        self._scheduler.start()
        self._running = True
        logger.info("batch_writer: 啟動", flush_seconds=flush_seconds)

    def shutdown(self) -> None:
        """關閉 APScheduler。"""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("batch_writer: 關閉")


# 全域單例
batch_writer = BatchWriter()
