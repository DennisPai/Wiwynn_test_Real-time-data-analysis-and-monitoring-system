from __future__ import annotations

import asyncio
from decimal import Decimal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.ws_manager import realtime_queue
from app.db.session import AsyncSessionLocal
from app.models.realtime_metric import RealtimeMetric
from app.models.realtime_metric_wide import RealtimeMetricWide
from app.schemas.realtime import RealtimeSnapshot

logger = structlog.get_logger(__name__)


class BatchWriter:
    """
    APScheduler AsyncIOScheduler 驅動的批次寫入器。
    每 M 秒 drain asyncio.Queue，一次性 add_all + commit 至 RealtimeMetricWide（wide）
    及 RealtimeMetric（long，過渡相容期）。
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._flush_seconds: int = 5
        self._running = False

    async def _flush(self) -> None:
        """Drain queue 並批次寫入 DB（wide + long 雙 table）。"""
        snapshots: list[RealtimeSnapshot] = []
        # asyncio.Queue 沒有 Empty exception，用 get_nowait + try/while 取盡
        while True:
            try:
                snapshot = realtime_queue.get_nowait()
                snapshots.append(snapshot)
            except asyncio.QueueEmpty:
                break

        if not snapshots:
            return

        # B4-1/B4-2: 建立 wide + long rows
        wide_rows = [
            RealtimeMetricWide(
                ts=s.ts,
                temperature=Decimal(str(s.temperature)),
                humidity=Decimal(str(s.humidity)),
                pressure=Decimal(str(s.pressure)),
                voltage=Decimal(str(s.voltage)),
                cpu_usage=Decimal(str(s.cpu_usage)),
                anomaly_flags=s.anomaly_flags,
                source="simulator",
            )
            for s in snapshots
        ]

        # long rows：從 snapshot 拆 5 筆（過渡相容，q v3 再 drop）
        long_rows: list[RealtimeMetric] = []
        for s in snapshots:
            for metric_name in ["temperature", "humidity", "pressure", "voltage", "cpu_usage"]:
                long_rows.append(
                    RealtimeMetric(
                        value=Decimal(str(getattr(s, metric_name))),
                        category=metric_name,
                        ts=s.ts,
                        source="simulator",
                        is_anomaly=s.anomaly_flags.get(metric_name, False),
                    )
                )

        # B4-3: session.add_all(wide_rows + long_rows) + commit
        try:
            async with AsyncSessionLocal() as session:
                session.add_all(wide_rows)
                session.add_all(long_rows)
                await session.commit()
            # B4-4: logger 紀錄筆數
            logger.info(
                "batch_writer: flush 完成",
                wide_count=len(wide_rows),
                long_count=len(long_rows),
            )
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
