from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel

from app.core.ws_manager import realtime_queue, ws_manager

logger = structlog.get_logger(__name__)

_CATEGORIES = ["temperature", "humidity", "pressure", "voltage", "cpu_usage"]


class RealtimeTick(BaseModel):
    """即時資料模擬 tick（廣播 payload）。"""
    category: str
    value: float
    is_anomaly: bool
    ts: str  # ISO8601 UTC


class RealtimeSimulator:
    """
    APScheduler AsyncIOScheduler 驅動的即時資料模擬器。
    每 N 秒生成一筆隨機資料，廣播給 WS 客戶端並送入批次寫入 queue。
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        # 從 DB 讀取的 threshold（初始預設值，之後由 reload_thresholds 更新）
        self._high: float = 80.0
        self._low: float = 10.0
        self._tick_seconds: int = 1
        self._running = False

    def _make_tick(self) -> RealtimeTick:
        category = random.choice(_CATEGORIES)
        # 隨機產生 Decimal(0-100) 再轉 float
        raw = Decimal(str(round(random.uniform(0, 100), 4)))
        value = float(raw)
        is_anomaly = value > self._high or value < self._low
        ts = datetime.now(tz=timezone.utc).isoformat()
        return RealtimeTick(category=category, value=value, is_anomaly=is_anomaly, ts=ts)

    async def _tick(self) -> None:
        """每次排程觸發：生成 tick → broadcast → enqueue。"""
        try:
            tick = self._make_tick()
            payload = tick.model_dump_json()
            await ws_manager.broadcast(payload)
            await realtime_queue.put(tick)
        except Exception as exc:
            logger.error("realtime_service: tick 失敗", error=str(exc))

    def reload_thresholds(self, high: float, low: float, tick_seconds: int | None = None) -> None:
        """由 admin settings PATCH 觸發，立即更新閾值與 tick 間隔。"""
        self._high = high
        self._low = low
        if tick_seconds is not None and tick_seconds > 0:
            self._tick_seconds = tick_seconds
        logger.info(
            "realtime_service: 閾值更新",
            high=self._high,
            low=self._low,
            tick_seconds=self._tick_seconds,
        )

    async def start(self, tick_seconds: int = 1) -> None:
        """啟動 APScheduler 排程。"""
        if self._running:
            return
        self._tick_seconds = tick_seconds
        self._scheduler.add_job(
            self._tick,
            "interval",
            seconds=self._tick_seconds,
            id="realtime_tick",
            replace_existing=True,
        )
        self._scheduler.start()
        self._running = True
        logger.info("realtime_service: 啟動", tick_seconds=tick_seconds)

    def shutdown(self) -> None:
        """關閉 APScheduler。"""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("realtime_service: 關閉")


# 全域單例
realtime_simulator = RealtimeSimulator()
