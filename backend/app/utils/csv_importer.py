"""csv_importer.py — T5.4: wide format CSV/JSON 解析器。

design.md §6 完整規格實作：
1. header 偵測：缺所有 5 metric → reject 整檔 with missing_columns list
2. header 含 title/value/category/is_anomaly → reject 整檔（舊 long 格式）
3. per-row：至少 1 metric 非空、ts ISO8601、其他驗證
4. BulkImportError 含 missing_columns 欄位
"""
from __future__ import annotations

import io
import json
import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from app.schemas.data_record import AnomalyFlags, BulkImportError, DataCreate, SourceEnum

# 5 個 metric 欄位名稱（wide schema）
_METRIC_COLS = {"temperature", "humidity", "pressure", "voltage", "cpu_usage"}

# 舊 long 格式的欄位名稱（偵測用）
_LONG_FORMAT_COLS = {"title", "value", "category", "is_anomaly"}


def _is_na(val: Any) -> bool:
    """判斷是否為空值（NaN / None / 空字串）。"""
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _parse_decimal(val: Any, field_name: str, row_index: int) -> Decimal | BulkImportError:
    """解析 Decimal，NaN/inf/無效 → BulkImportError。"""
    try:
        d = Decimal(str(val).strip())
        if not d.is_finite():
            return BulkImportError(row=row_index, reason=f"{field_name} 不得為 NaN 或 inf")
        return d
    except (InvalidOperation, ValueError, TypeError):
        return BulkImportError(row=row_index, reason=f"{field_name} 非有效數值：{val!r}")


def _parse_ts(raw_ts: Any, row_index: int) -> datetime | BulkImportError:
    """解析 ISO8601 timestamp，無效 → BulkImportError。若無 tzinfo 視為 UTC。"""
    try:
        if isinstance(raw_ts, datetime):
            dt = raw_ts
        elif isinstance(raw_ts, pd.Timestamp):
            dt = raw_ts.to_pydatetime()
        else:
            dt = datetime.fromisoformat(str(raw_ts).strip().replace("Z", "+00:00"))
        # 若無 tzinfo，視為 UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return BulkImportError(
            row=row_index, reason=f"ts 格式不符（ISO 8601）：{raw_ts!r}"
        )


def _parse_anomaly_flags(raw: Any, row_index: int) -> AnomalyFlags | BulkImportError:
    """解析 anomaly_flags JSON 字串 / dict，需含完整 5 key bool。"""
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return BulkImportError(row=row_index, reason=f"anomaly_flags JSON 解析失敗：{exc}")
    elif isinstance(raw, dict):
        parsed = raw
    else:
        return BulkImportError(row=row_index, reason=f"anomaly_flags 格式不合法：{raw!r}")

    try:
        flags = AnomalyFlags(**parsed)
    except Exception as exc:
        return BulkImportError(row=row_index, reason=f"anomaly_flags key 不合法：{exc}")
    return flags


def _check_header(columns: set[str]) -> BulkImportError | None:
    """
    header 整檔驗證（design.md §6 步驟 1 + 步驟 3）。
    回傳 BulkImportError → 整檔拒絕；回傳 None → 通過。
    """
    # 步驟 3: 偵測舊 long 格式（含 title / value / category / is_anomaly 任一）
    long_detected = columns & _LONG_FORMAT_COLS
    if long_detected:
        return BulkImportError(
            row=0,
            reason=(
                "CSV 為舊版 long 格式（含 title/value/category 欄位），"
                "請下載新版 wide template 後重新上傳"
            ),
            missing_columns=[],
        )

    # 步驟 1: 偵測缺所有 5 metric
    present_metrics = columns & _METRIC_COLS
    if not present_metrics:
        missing = sorted(_METRIC_COLS)
        return BulkImportError(
            row=0,
            reason=(
                "CSV header 缺少所有 metric 欄位"
                "（需至少 temperature / humidity / pressure / voltage / cpu_usage 之一）"
            ),
            missing_columns=missing,
        )

    # ts 必要欄位
    if "ts" not in columns:
        return BulkImportError(
            row=0,
            reason="CSV header 缺少必要欄位：ts",
            missing_columns=["ts"],
        )

    return None


def _parse_wide_row(
    row_index: int,
    row: dict[str, Any],
    present_metrics: set[str],
) -> DataCreate | BulkImportError:
    """
    驗證單筆 wide row，成功回傳 DataCreate，失敗回傳 BulkImportError。
    design.md §6 per-row 驗證規則：
    - ts 必填 ISO8601
    - 5 metric 中至少 1 個非空
    - 任一 metric 若非空必須是有效 Decimal（NaN/inf 拒絕）
    - anomaly_flags（若有）：JSON、完整 5 key bool
    - source（若有）：必須 ∈ {user, simulator}；若無 → 預設 user
    - note（若有）：max 200 字元
    """
    # 1. ts 必填 + ISO8601
    raw_ts = row.get("ts")
    if _is_na(raw_ts):
        return BulkImportError(row=row_index, reason="ts 不得為空")
    ts_result = _parse_ts(raw_ts, row_index)
    if isinstance(ts_result, BulkImportError):
        return ts_result
    ts: datetime = ts_result

    # 2. 5 metric：至少 1 個非空；非空的必須是有效 Decimal
    metric_values: dict[str, Decimal | None] = {}
    for col in _METRIC_COLS:
        raw_val = row.get(col)
        if col not in present_metrics or _is_na(raw_val):
            metric_values[col] = None
        else:
            parsed = _parse_decimal(raw_val, col, row_index)
            if isinstance(parsed, BulkImportError):
                return parsed
            metric_values[col] = parsed

    if all(v is None for v in metric_values.values()):
        return BulkImportError(
            row=row_index,
            reason="至少需填 1 個 metric（temperature / humidity / pressure / voltage / cpu_usage）",
        )

    # 3. anomaly_flags（選填）
    raw_flags = row.get("anomaly_flags")
    if _is_na(raw_flags):
        # 未提供 → DataCreate 的 default_factory AnomalyFlags() 即全 false
        flags = AnomalyFlags()
    else:
        flags_result = _parse_anomaly_flags(raw_flags, row_index)
        if isinstance(flags_result, BulkImportError):
            return flags_result
        flags = flags_result

    # 4. source（選填，預設 user）
    raw_source = row.get("source")
    if _is_na(raw_source):
        source = SourceEnum.user
    else:
        source_str = str(raw_source).strip().lower()
        if source_str not in ("user", "simulator"):
            return BulkImportError(
                row=row_index,
                reason=f"source 不合法（必須是 user 或 simulator）：{raw_source!r}",
            )
        source = SourceEnum(source_str)

    # 5. note（選填，max 200）
    raw_note = row.get("note")
    if _is_na(raw_note):
        note: str | None = None
    else:
        note = str(raw_note).strip()
        if len(note) > 200:
            return BulkImportError(row=row_index, reason="note 超過 200 字元")
        if not note:
            note = None

    # 6. owner_email 選填（不在此處做 DB lookup，endpoint 決定 owner_id）
    # DataCreate 的 owner_email 欄位留給 endpoint 使用
    raw_owner_email = row.get("owner_email")
    owner_email: str | None = None
    if not _is_na(raw_owner_email):
        owner_email = str(raw_owner_email).strip() or None

    # 構造 DataCreate（不呼叫 at_least_one_metric validator，因為已在上面驗證）
    return DataCreate(
        ts=ts,
        temperature=metric_values["temperature"],
        humidity=metric_values["humidity"],
        pressure=metric_values["pressure"],
        voltage=metric_values["voltage"],
        cpu_usage=metric_values["cpu_usage"],
        anomaly_flags=flags,
        source=source,
        note=note,
        owner_email=owner_email,
    )


def parse_csv(content: bytes) -> tuple[list[DataCreate], list[BulkImportError]]:
    """
    T5.4: 解析 wide format CSV bytes，逐行驗證。
    design.md §6 規格：
    1. header 整檔驗證（舊 long 格式 / 缺所有 metric）
    2. per-row 驗證
    回傳 (有效列表, 錯誤列表)。
    """
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as exc:
        return [], [BulkImportError(row=0, reason=f"CSV 解析失敗：{exc}")]

    # 欄位名稱 strip
    df.columns = [c.strip() for c in df.columns]
    columns_set = set(df.columns)

    # header 整檔驗證
    header_error = _check_header(columns_set)
    if header_error is not None:
        return [], [header_error]

    present_metrics = columns_set & _METRIC_COLS

    valid: list[DataCreate] = []
    errors: list[BulkImportError] = []

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # row 1 = header，從 2 開始計
        result = _parse_wide_row(row_num, row.to_dict(), present_metrics)
        if isinstance(result, BulkImportError):
            errors.append(result)
        else:
            valid.append(result)

    return valid, errors


def parse_json(content: bytes) -> tuple[list[DataCreate], list[BulkImportError]]:
    """
    T5.4: 解析 wide format JSON bytes（array of objects），逐筆驗證。
    回傳 (有效列表, 錯誤列表)。
    """
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [], [BulkImportError(row=0, reason=f"JSON 解析失敗：{exc}")]

    if not isinstance(data, list):
        return [], [BulkImportError(row=0, reason="JSON 必須為陣列格式")]

    if not data:
        return [], []

    # 從第一筆取 header（key set），做整檔 header 驗證
    first_item = data[0] if isinstance(data[0], dict) else {}
    columns_set = set(first_item.keys())
    header_error = _check_header(columns_set)
    if header_error is not None:
        return [], [header_error]

    present_metrics = columns_set & _METRIC_COLS

    valid: list[DataCreate] = []
    errors: list[BulkImportError] = []

    for idx, item in enumerate(data):
        row_num = idx + 1
        if not isinstance(item, dict):
            errors.append(BulkImportError(row=row_num, reason="每筆資料必須為物件格式"))
            continue
        result = _parse_wide_row(row_num, item, present_metrics)
        if isinstance(result, BulkImportError):
            errors.append(result)
        else:
            valid.append(result)

    return valid, errors
