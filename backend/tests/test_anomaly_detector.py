"""test_anomaly_detector.py — AnomalyDetector service unit tests.

Covers:
- get_thresholds fallback to DEFAULT_ANOMALY_THRESHOLDS
- get_thresholds from DB AppSetting
- cache TTL 30s hit/miss
- cache invalidation
- is_anomaly boundary conditions (high/low) for all 5 metrics
- compute_anomaly_flags with partial snapshot
"""
from __future__ import annotations

import json
from unittest import mock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.app_setting import AppSetting
from app.services.anomaly_detector import AnomalyDetector


@pytest_asyncio.fixture(autouse=True)
async def reset_cache():
    """Reset AnomalyDetector cache before each test."""
    AnomalyDetector._cache = {}
    AnomalyDetector._cache_ts = 0.0
    yield
    # Clean up after test
    AnomalyDetector._cache = {}
    AnomalyDetector._cache_ts = 0.0


@pytest.mark.asyncio
async def test_get_thresholds_fallback_to_settings(db_session: AsyncSession) -> None:
    """Test: AppSetting table empty → get_thresholds fallback to settings.DEFAULT_ANOMALY_THRESHOLDS.

    Verifies all 5 metrics return correct fallback values from config.
    """
    from sqlalchemy import delete

    # 清理所有 anomaly_threshold.* key 確保 fallback 路徑
    await db_session.execute(
        delete(AppSetting).where(AppSetting.key.like("anomaly_threshold.%"))
    )
    await db_session.commit()

    # 重設 cache
    AnomalyDetector.invalidate_cache()

    # AppSetting 表為空，應 fallback
    result = await AnomalyDetector.get_thresholds(db_session)

    # 驗證回傳 5 個 metric 的 threshold dict
    assert set(result.keys()) == {
        "temperature",
        "humidity",
        "pressure",
        "voltage",
        "cpu_usage",
    }

    # 驗證每個 metric 的 fallback 值與 settings 一致
    assert result["temperature"]["high"] == 80.0
    assert result["temperature"]["low"] == 10.0

    assert result["humidity"]["high"] == 85.0
    assert result["humidity"]["low"] == 20.0

    assert result["pressure"]["high"] == 1050.0
    assert result["pressure"]["low"] == 950.0

    assert result["voltage"]["high"] == 13.5
    assert result["voltage"]["low"] == 11.0

    assert result["cpu_usage"]["high"] == 90.0
    assert result["cpu_usage"]["low"] == 5.0


@pytest.mark.asyncio
async def test_get_thresholds_from_db(db_session: AsyncSession) -> None:
    """Test: AppSetting 表有資料 → get_thresholds 從 DB 取值（不 fallback）。

    寫入自訂 threshold 後驗證 get_thresholds 回傳 DB 值。
    """
    from sqlalchemy import delete

    # 清理舊資料
    await db_session.execute(
        delete(AppSetting).where(AppSetting.key.like("anomaly_threshold.%"))
    )
    await db_session.commit()

    # 重設 cache
    AnomalyDetector.invalidate_cache()

    # 寫入自訂 threshold 到 DB
    custom_thresholds = {
        "temperature": {"high": 75.0, "low": 5.0},
        "humidity": {"high": 80.0, "low": 15.0},
        "pressure": {"high": 1040.0, "low": 960.0},
        "voltage": {"high": 14.0, "low": 10.5},
        "cpu_usage": {"high": 85.0, "low": 10.0},
    }

    for metric, thresholds in custom_thresholds.items():
        setting = AppSetting(
            key=f"anomaly_threshold.{metric}",
            value=json.dumps(thresholds),
            description=f"Custom threshold for {metric}",
        )
        db_session.add(setting)

    await db_session.commit()

    # 重新 reset cache 確保讀取 DB
    AnomalyDetector._cache = {}
    AnomalyDetector._cache_ts = 0.0

    # 呼叫 get_thresholds，應從 DB 取值
    result = await AnomalyDetector.get_thresholds(db_session)

    # 驗證回傳 DB 自訂值而非 fallback
    assert result["temperature"]["high"] == 75.0
    assert result["temperature"]["low"] == 5.0

    assert result["humidity"]["high"] == 80.0
    assert result["humidity"]["low"] == 15.0

    assert result["pressure"]["high"] == 1040.0
    assert result["pressure"]["low"] == 960.0

    assert result["voltage"]["high"] == 14.0
    assert result["voltage"]["low"] == 10.5

    assert result["cpu_usage"]["high"] == 85.0
    assert result["cpu_usage"]["low"] == 10.0


@pytest.mark.asyncio
async def test_get_thresholds_cache_hit_within_ttl(db_session: AsyncSession) -> None:
    """Test: cache TTL 30s 內第二次呼叫 cache hit（不重新 fetch）。

    Mock time.monotonic() 驗證：
    - 第一次呼叫 → 填充 cache
    - 同時間內呼叫 → 直接回傳 cache（DB call count 不增加）
    """
    from sqlalchemy import delete

    # 清理舊資料（確保乾淨狀態）
    await db_session.execute(
        delete(AppSetting).where(AppSetting.key == "anomaly_threshold.temperature")
    )
    await db_session.commit()

    # 準備 DB 資料
    custom_threshold = {"high": 99.0, "low": 1.0}
    setting = AppSetting(
        key="anomaly_threshold.temperature",
        value=json.dumps(custom_threshold),
        description="Test threshold",
    )
    db_session.add(setting)
    await db_session.commit()

    # 重設 cache
    AnomalyDetector.invalidate_cache()

    # 第一次呼叫，填充 cache
    result1 = await AnomalyDetector.get_thresholds(db_session)
    assert result1["temperature"]["high"] == 99.0

    # Mock time.monotonic() 回傳相同時間（模擬 TTL 內呼叫）
    with mock.patch("app.services.anomaly_detector.time.monotonic") as mock_time:
        # 設定時間為同一刻（cache 應 hit）
        mock_time.return_value = AnomalyDetector._cache_ts + 10.0  # 10s 後，< 30s TTL

        # 記錄 DB query 次數
        # 由於 cache hit，不應執行 DB query
        # 我們透過檢查 cache_ts 是否改變來驗證
        old_cache_ts = AnomalyDetector._cache_ts

        result2 = await AnomalyDetector.get_thresholds(db_session)

        # cache_ts 應未改變（表示沒有重新 fetch）
        assert AnomalyDetector._cache_ts == old_cache_ts
        # 結果應相同
        assert result2 is result1  # 同一 dict object


@pytest.mark.asyncio
async def test_get_thresholds_cache_expire_after_ttl(db_session: AsyncSession) -> None:
    """Test: cache 超過 30s TTL → re-fetch from DB。

    Mock time.monotonic() 驗證：
    - 第一次呼叫 → 填充 cache at t=0
    - 第二次呼叫 at t>30s → cache 過期，重新 fetch
    - 時間戳應更新
    """
    from sqlalchemy import delete

    # 清理舊資料
    await db_session.execute(
        delete(AppSetting).where(
            AppSetting.key == "anomaly_threshold.temperature"
        )
    )
    await db_session.commit()

    # 準備初始 DB 資料
    initial_threshold = {"high": 50.0, "low": 30.0}
    setting = AppSetting(
        key="anomaly_threshold.temperature",
        value=json.dumps(initial_threshold),
        description="Initial threshold",
    )
    db_session.add(setting)
    await db_session.commit()

    # 重設 cache
    AnomalyDetector.invalidate_cache()

    # 第一次呼叫，填充 cache
    result1 = await AnomalyDetector.get_thresholds(db_session)
    assert result1["temperature"]["high"] == 50.0
    first_cache_ts = AnomalyDetector._cache_ts

    # 更新 DB 資料（模擬管理員改 threshold）
    # 先刪除舊的
    await db_session.execute(
        delete(AppSetting).where(
            AppSetting.key == "anomaly_threshold.temperature"
        )
    )
    await db_session.commit()

    # 新增更新的值
    updated_threshold = {"high": 60.0, "low": 25.0}
    setting2 = AppSetting(
        key="anomaly_threshold.temperature",
        value=json.dumps(updated_threshold),
        description="Updated threshold",
    )
    db_session.add(setting2)
    await db_session.commit()

    # Mock time.monotonic() 超過 TTL
    with mock.patch("app.services.anomaly_detector.time.monotonic") as mock_time:
        # 第一次呼叫時間：0s
        # 現在時間：35s（> 30s TTL）
        mock_time.return_value = first_cache_ts + 35.0

        # 呼叫 get_thresholds，應重新 fetch
        result2 = await AnomalyDetector.get_thresholds(db_session)

        # 應回傳更新後的值
        assert result2["temperature"]["high"] == 60.0
        assert result2["temperature"]["low"] == 25.0

        # cache_ts 應更新（> first_cache_ts）
        assert AnomalyDetector._cache_ts > first_cache_ts


@pytest.mark.asyncio
async def test_invalidate_cache_clears_immediately(db_session: AsyncSession) -> None:
    """Test: invalidate_cache() 清空 cache，下次 get_thresholds 重新 fetch。

    呼叫 invalidate_cache() → cache 應清空 → 下次呼叫重新 fetch
    """
    # 填充初始 cache
    result1 = await AnomalyDetector.get_thresholds(db_session)
    assert len(AnomalyDetector._cache) > 0  # cache 應被填充

    # 呼叫 invalidate_cache
    AnomalyDetector.invalidate_cache()

    # 驗證 cache 清空
    assert AnomalyDetector._cache == {}
    assert AnomalyDetector._cache_ts == 0.0

    # 再次呼叫 get_thresholds，應重新 fetch（會用 fallback）
    result2 = await AnomalyDetector.get_thresholds(db_session)
    assert len(AnomalyDetector._cache) > 0  # cache 應重新填充
    assert AnomalyDetector._cache_ts > 0.0


@pytest.mark.asyncio
async def test_is_anomaly_high_boundary(db_session: AsyncSession) -> None:
    """Test: is_anomaly 高值邊界檢查。

    驗證所有 5 metric 的 high threshold：
    - value > high → True
    - value == high → False (boundary exclusive)
    - value < high → False
    """
    from sqlalchemy import delete

    # 確保 DB 沒有自訂 threshold（清理所有 anomaly_threshold.* key）
    await db_session.execute(
        delete(AppSetting).where(AppSetting.key.like("anomaly_threshold.%"))
    )
    await db_session.commit()

    # 重設 cache 確保使用預設 threshold
    AnomalyDetector.invalidate_cache()

    # 使用預設 threshold
    # temperature high=80
    assert await AnomalyDetector.is_anomaly(db_session, "temperature", 81.0) is True
    assert await AnomalyDetector.is_anomaly(db_session, "temperature", 80.0) is False
    assert await AnomalyDetector.is_anomaly(db_session, "temperature", 79.9) is False

    # humidity high=85
    assert await AnomalyDetector.is_anomaly(db_session, "humidity", 86.0) is True
    assert await AnomalyDetector.is_anomaly(db_session, "humidity", 85.0) is False
    assert await AnomalyDetector.is_anomaly(db_session, "humidity", 84.9) is False

    # pressure high=1050
    assert await AnomalyDetector.is_anomaly(db_session, "pressure", 1051.0) is True
    assert await AnomalyDetector.is_anomaly(db_session, "pressure", 1050.0) is False
    assert await AnomalyDetector.is_anomaly(db_session, "pressure", 1049.9) is False

    # voltage high=13.5
    assert await AnomalyDetector.is_anomaly(db_session, "voltage", 13.6) is True
    assert await AnomalyDetector.is_anomaly(db_session, "voltage", 13.5) is False
    assert await AnomalyDetector.is_anomaly(db_session, "voltage", 13.4) is False

    # cpu_usage high=90
    assert await AnomalyDetector.is_anomaly(db_session, "cpu_usage", 91.0) is True
    assert await AnomalyDetector.is_anomaly(db_session, "cpu_usage", 90.0) is False
    assert await AnomalyDetector.is_anomaly(db_session, "cpu_usage", 89.9) is False


@pytest.mark.asyncio
async def test_is_anomaly_low_boundary(db_session: AsyncSession) -> None:
    """Test: is_anomaly 低值邊界檢查。

    驗證所有 5 metric 的 low threshold：
    - value < low → True
    - value == low → False (boundary inclusive at low)
    - value > low → False
    """
    from sqlalchemy import delete

    # 確保 DB 沒有自訂 threshold（清理所有 anomaly_threshold.* key）
    await db_session.execute(
        delete(AppSetting).where(AppSetting.key.like("anomaly_threshold.%"))
    )
    await db_session.commit()

    # 重設 cache 確保使用預設 threshold
    AnomalyDetector.invalidate_cache()

    # 使用預設 threshold
    # temperature low=10
    assert await AnomalyDetector.is_anomaly(db_session, "temperature", 9.9) is True
    assert await AnomalyDetector.is_anomaly(db_session, "temperature", 10.0) is False
    assert await AnomalyDetector.is_anomaly(db_session, "temperature", 10.1) is False

    # humidity low=20
    assert await AnomalyDetector.is_anomaly(db_session, "humidity", 19.9) is True
    assert await AnomalyDetector.is_anomaly(db_session, "humidity", 20.0) is False
    assert await AnomalyDetector.is_anomaly(db_session, "humidity", 20.1) is False

    # pressure low=950
    assert await AnomalyDetector.is_anomaly(db_session, "pressure", 949.9) is True
    assert await AnomalyDetector.is_anomaly(db_session, "pressure", 950.0) is False
    assert await AnomalyDetector.is_anomaly(db_session, "pressure", 950.1) is False

    # voltage low=11.0
    assert await AnomalyDetector.is_anomaly(db_session, "voltage", 10.9) is True
    assert await AnomalyDetector.is_anomaly(db_session, "voltage", 11.0) is False
    assert await AnomalyDetector.is_anomaly(db_session, "voltage", 11.1) is False

    # cpu_usage low=5
    assert await AnomalyDetector.is_anomaly(db_session, "cpu_usage", 4.9) is True
    assert await AnomalyDetector.is_anomaly(db_session, "cpu_usage", 5.0) is False
    assert await AnomalyDetector.is_anomaly(db_session, "cpu_usage", 5.1) is False


@pytest.mark.asyncio
async def test_compute_anomaly_flags_full_5_key(db_session: AsyncSession) -> None:
    """Test: compute_anomaly_flags 傳入 partial snapshot → 回傳完整 5 key dict。

    測試情境：
    1. snapshot 只有 temperature (80.5 > high=80) → temperature=True，其他 None→False
    2. snapshot 只有 humidity (50.0 < low=20 false，> high=85 false) → humidity=False
    3. snapshot 為空 {} → 所有 metric 都 None → 全 False
    4. snapshot 含所有 5 metric（部分異常）→ 驗證對應 flag
    """
    # Case 1: 只有 temperature（異常）
    snapshot1 = {"temperature": 81.0}
    result1 = await AnomalyDetector.compute_anomaly_flags(db_session, snapshot1)
    assert set(result1.keys()) == {
        "temperature",
        "humidity",
        "pressure",
        "voltage",
        "cpu_usage",
    }
    assert result1["temperature"] is True  # 81 > 80
    assert result1["humidity"] is False  # None
    assert result1["pressure"] is False  # None
    assert result1["voltage"] is False  # None
    assert result1["cpu_usage"] is False  # None

    # Case 2: 只有 humidity（正常）
    snapshot2 = {"humidity": 50.0}
    result2 = await AnomalyDetector.compute_anomaly_flags(db_session, snapshot2)
    assert result2["humidity"] is False  # 20 < 50 < 85
    assert result2["temperature"] is False  # None
    assert result2["pressure"] is False  # None
    assert result2["voltage"] is False  # None
    assert result2["cpu_usage"] is False  # None

    # Case 3: 空 snapshot
    snapshot3 = {}
    result3 = await AnomalyDetector.compute_anomaly_flags(db_session, snapshot3)
    assert all(v is False for v in result3.values())
    assert len(result3) == 5

    # Case 4: 所有 5 metric（部分異常）
    snapshot4 = {
        "temperature": 85.0,  # > 80 → True
        "humidity": 30.0,  # 20 < 30 < 85 → False
        "pressure": 949.0,  # < 950 → True
        "voltage": 13.4,  # 11 < 13.4 < 13.5 → False
        "cpu_usage": 95.0,  # > 90 → True
    }
    result4 = await AnomalyDetector.compute_anomaly_flags(db_session, snapshot4)
    assert result4["temperature"] is True
    assert result4["humidity"] is False
    assert result4["pressure"] is True
    assert result4["voltage"] is False
    assert result4["cpu_usage"] is True
