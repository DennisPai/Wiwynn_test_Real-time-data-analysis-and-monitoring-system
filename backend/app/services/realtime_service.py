from __future__ import annotations

import asyncio
import os
import random
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.ws_manager import realtime_queue, ws_manager
from app.schemas.realtime import RealtimeSnapshot

logger = structlog.get_logger(__name__)

# B3-1: 每個 metric 的 baseline / sigma / min / max [Q5]
_METRIC_PROFILES: dict[str, dict] = {
    "temperature": {"baseline": 25.0, "sigma": 1.5, "min": -20.0, "max": 120.0, "unit": "C"},
    "humidity":    {"baseline": 60.0, "sigma": 3.0, "min": 0.0,   "max": 100.0, "unit": "%"},
    "pressure":    {"baseline": 1013.0, "sigma": 5.0, "min": 900.0, "max": 1100.0, "unit": "hPa"},
    "voltage":     {"baseline": 12.0, "sigma": 0.3, "min": 0.0,   "max": 24.0,  "unit": "V"},
    "cpu_usage":   {"baseline": 40.0, "sigma": 8.0, "min": 0.0,   "max": 100.0, "unit": "%"},
}

_METRIC_NAMES = list(_METRIC_PROFILES.keys())


# B3-2: 純函式 random_walk_step
def random_walk_step(
    prev: float, sigma: float, low: float, high: float, rng: random.Random
) -> float:
    """Random walk 單步：gauss delta，clamp 至 [low, high]。"""
    delta = rng.gauss(0, sigma)
    new_value = prev + delta
    return max(low, min(high, new_value))


class RealtimeSimulator:
    """
    APScheduler AsyncIOScheduler 驅動的即時資料模擬器。
    每 N 秒生成 wide snapshot（5 個 metric 全部），廣播給 WS 客戶端並送入批次寫入 queue。
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        # B3-3: 每 metric 上一個 value 的內部狀態
        self._state: dict[str, float] = {
            name: profile["baseline"] for name, profile in _METRIC_PROFILES.items()
        }
        self._rng = random.Random()
        # 從 DB 讀取的 threshold
        self._high: float = 80.0
        self._low: float = 10.0
        self._tick_seconds: int = 1
        self._running = False
        # B3-7: 異常注入週期
        self._anomaly_injection_period: int = int(
            os.environ.get("ANOMALY_INJECTION_PERIOD", "60")
        )
        self._tick_count: int = 0

    # B3-4: 改 _make_tick → _make_snapshot 回 wide snapshot [Q2,Q5]
    def _make_snapshot(self) -> RealtimeSnapshot:
        """每次 tick 對 5 個 metric 各 random_walk 一次，回傳 wide snapshot。"""
        ts = datetime.now(tz=timezone.utc)
        values: dict[str, float] = {}
        anomaly_flags: dict[str, bool] = {}

        for name, profile in _METRIC_PROFILES.items():
            new_val = random_walk_step(
                prev=self._state[name],
                sigma=profile["sigma"],
                low=profile["min"],
                high=profile["max"],
                rng=self._rng,
            )
            self._state[name] = new_val
            values[name] = round(new_val, 4)
            anomaly_flags[name] = False

        # B3-7: 異常注入：每 ANOMALY_INJECTION_PERIOD tick 對隨機 metric 一次性偏移 2σ
        period = self._anomaly_injection_period
        if period > 0 and self._tick_count % period == 0 and self._tick_count > 0:
            inject_metric = self._rng.choice(_METRIC_NAMES)
            profile = _METRIC_PROFILES[inject_metric]
            spike = self._rng.choice([-1, 1]) * 2 * profile["sigma"]
            injected = max(profile["min"], min(profile["max"], values[inject_metric] + spike))
            values[inject_metric] = round(injected, 4)
            self._state[inject_metric] = injected

        # 使用異常閾值判斷（temperature 等 per-metric 範疇不同，用統一 high/low 百分比近似）
        # 各 metric 依自身閾值判斷異常
        for name, val in values.items():
            profile = _METRIC_PROFILES[name]
            metric_range = profile["max"] - profile["min"]
            # 若值超過範圍上 80% 或低於範圍下 10% 視為異常
            high_thresh = profile["min"] + metric_range * (self._high / 100.0)
            low_thresh = profile["min"] + metric_range * (self._low / 100.0)
            anomaly_flags[name] = val > high_thresh or val < low_thresh

        return RealtimeSnapshot(
            schema_version="v2",
            ts=ts,
            temperature=values["temperature"],
            humidity=values["humidity"],
            pressure=values["pressure"],
            voltage=values["voltage"],
            cpu_usage=values["cpu_usage"],
            anomaly_flags=anomaly_flags,
        )

    # B3-5: 改 _tick broadcast snapshot.model_dump_json() + enqueue
    async def _tick(self) -> None:
        """每次排程觸發：生成 snapshot → broadcast → enqueue。"""
        try:
            self._tick_count += 1
            snapshot = self._make_snapshot()
            payload = snapshot.model_dump_json()
            await ws_manager.broadcast(payload)
            await realtime_queue.put(snapshot)
        except Exception as exc:
            logger.error("realtime_service: tick 失敗", error=str(exc))

    # B3-6: startup 讀 wide table 最後一筆作初始 _state
    async def _load_initial_state_from_db(self) -> None:
        """從 DB wide table 最後一筆讀取初始狀態，沒有則用 baseline。"""
        try:
            from sqlalchemy import select
            from app.db.session import AsyncSessionLocal
            from app.models.realtime_metric_wide import RealtimeMetricWide

            async with AsyncSessionLocal() as sess:
                result = await sess.execute(
                    select(RealtimeMetricWide)
                    .order_by(RealtimeMetricWide.ts.desc())
                    .limit(1)
                )
                last_row = result.scalar_one_or_none()

            if last_row is not None:
                for name in _METRIC_NAMES:
                    val = getattr(last_row, name, None)
                    if val is not None:
                        self._state[name] = float(val)
                logger.info("realtime_service: 從 DB 載入初始狀態", state=self._state)
            else:
                logger.info("realtime_service: DB 無歷史資料，使用 baseline 初始狀態")
        except Exception as exc:
            logger.warning("realtime_service: 載入初始狀態失敗，使用 baseline", error=str(exc))

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
        # 從 DB 讀取初始狀態
        await self._load_initial_state_from_db()
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
