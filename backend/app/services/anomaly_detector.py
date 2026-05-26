"""anomaly_detector.py — 全系統共用 anomaly 偵測 service，含 cache TTL 30s。

使用方式：
  from app.services.anomaly_detector import AnomalyDetector

  # 在 async endpoint / service 內：
  flags = await AnomalyDetector.compute_anomaly_flags(db, snapshot_dict)

  # PATCH /admin/settings 後主動 invalidate：
  AnomalyDetector.invalidate_cache()

design.md §8 規格完整實作。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.app_setting import AppSetting

logger = logging.getLogger(__name__)

_METRICS = ("temperature", "humidity", "pressure", "voltage", "cpu_usage")


class AnomalyDetector:
    """全系統共用 anomaly 偵測 service，含 in-memory cache TTL 30s。

    全部方法為 classmethod，不需要實例化。
    cache 為 module-level class attribute，在同一 process 內共享。
    """

    _cache: dict[str, dict[str, float]] = {}  # metric -> {"high": float, "low": float}
    _cache_ts: float = 0.0
    _CACHE_TTL_SECONDS: float = 30.0

    @classmethod
    async def get_thresholds(cls, db: AsyncSession) -> dict[str, dict[str, float]]:
        """從 DB AppSetting 取 5 metric × 2 threshold，cache 30s。

        AppSetting key 格式：anomaly_threshold.<metric>
        value 欄位為 JSON string，例如 '{"high": 80, "low": 10}'。
        若 DB 無對應 key，fallback 到 settings.DEFAULT_ANOMALY_THRESHOLDS。
        若 DB query 失敗，fallback 並寫 error log（不 crash）。

        Returns:
            dict: 例如 {"temperature": {"high": 80.0, "low": 10.0}, ...}
        """
        now = time.monotonic()
        if cls._cache and (now - cls._cache_ts) < cls._CACHE_TTL_SECONDS:
            return cls._cache

        # cache 過期或尚未填充，從 DB re-fetch
        thresholds: dict[str, dict[str, float]] = {}
        try:
            keys = [f"anomaly_threshold.{m}" for m in _METRICS]
            result = await db.execute(
                select(AppSetting).where(AppSetting.key.in_(keys))
            )
            rows: list[AppSetting] = list(result.scalars().all())
            rows_by_key = {r.key: r for r in rows}

            for metric in _METRICS:
                db_key = f"anomaly_threshold.{metric}"
                if db_key in rows_by_key:
                    try:
                        parsed: dict[str, Any] = json.loads(rows_by_key[db_key].value)
                        thresholds[metric] = {
                            "high": float(parsed["high"]),
                            "low": float(parsed["low"]),
                        }
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                        logger.error(
                            "anomaly_detector: failed to parse AppSetting key=%s value=%r: %s",
                            db_key,
                            rows_by_key[db_key].value,
                            exc,
                        )
                        thresholds[metric] = cls._fallback(metric)
                else:
                    thresholds[metric] = cls._fallback(metric)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "anomaly_detector: DB query failed, falling back to defaults: %s", exc
            )
            for metric in _METRICS:
                thresholds[metric] = cls._fallback(metric)

        cls._cache = thresholds
        cls._cache_ts = time.monotonic()
        return cls._cache

    @classmethod
    def _fallback(cls, metric: str) -> dict[str, float]:
        """從 settings.DEFAULT_ANOMALY_THRESHOLDS 取 fallback threshold。"""
        defaults: dict[str, dict] = settings.DEFAULT_ANOMALY_THRESHOLDS
        t = defaults.get(metric, {"high": 80.0, "low": 10.0})
        return {"high": float(t["high"]), "low": float(t["low"])}

    @classmethod
    async def is_anomaly(
        cls, db: AsyncSession, metric: str, value: Any
    ) -> bool:
        """單一 metric 異常判定。

        Args:
            db: async DB session
            metric: metric 名稱（temperature / humidity / pressure / voltage / cpu_usage）
            value: 數值（None 表示未提供，直接回傳 False）

        Returns:
            bool: True 若 value > high 或 value < low
        """
        if value is None:
            return False
        if metric not in _METRICS:
            logger.warning("anomaly_detector: unknown metric=%r, returning False", metric)
            return False
        thresholds = await cls.get_thresholds(db)
        t = thresholds[metric]
        try:
            v = float(value)
        except (TypeError, ValueError):
            logger.warning(
                "anomaly_detector: non-numeric value=%r for metric=%r, returning False",
                value,
                metric,
            )
            return False
        return v > t["high"] or v < t["low"]

    @classmethod
    async def compute_anomaly_flags(
        cls, db: AsyncSession, snapshot: dict[str, Any]
    ) -> dict[str, bool]:
        """給含 5 metric key 的 dict，回傳完整 5 key anomaly_flags dict。

        Args:
            db: async DB session
            snapshot: 含 temperature / humidity / pressure / voltage / cpu_usage 的 dict
                      （key 缺失視為 None，不會 crash）

        Returns:
            dict: {"temperature": bool, "humidity": bool, "pressure": bool,
                   "voltage": bool, "cpu_usage": bool}
        """
        result: dict[str, bool] = {}
        for metric in _METRICS:
            result[metric] = await cls.is_anomaly(db, metric, snapshot.get(metric))
        return result

    @classmethod
    def invalidate_cache(cls) -> None:
        """主動清空 cache，強制下次呼叫 get_thresholds() 重新從 DB fetch。

        觸發點：PATCH /api/v1/admin/settings 更新任何 anomaly_threshold key 後。
        """
        cls._cache = {}
        cls._cache_ts = 0.0
