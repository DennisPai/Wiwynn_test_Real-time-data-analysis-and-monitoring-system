from __future__ import annotations

import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from app.schemas.data_record import BulkImportError, DataCreate


def _parse_row(row_index: int, row: dict[str, Any]) -> DataCreate | BulkImportError:
    """
    驗證單筆 row，成功回傳 DataCreate，失敗回傳 BulkImportError。
    必要欄位：title, value, category, recorded_at。
    選填：is_anomaly（預設 False）。
    """
    # 1. 必要欄位存在檢查
    for field in ("title", "value", "category", "recorded_at"):
        if field not in row or (isinstance(row[field], float) and pd.isna(row[field])):
            return BulkImportError(row=row_index, reason=f"缺少必要欄位：{field}")

    # 2. title 字串且非空
    title = str(row["title"]).strip()
    if not title:
        return BulkImportError(row=row_index, reason="title 不得為空")
    if len(title) > 200:
        return BulkImportError(row=row_index, reason="title 超過 200 字元")

    # 3. value 數值
    try:
        value = Decimal(str(row["value"]))
    except (InvalidOperation, ValueError, TypeError):
        return BulkImportError(row=row_index, reason=f"value 非有效數值：{row['value']!r}")

    # 4. category 字串且非空
    category = str(row["category"]).strip()
    if not category:
        return BulkImportError(row=row_index, reason="category 不得為空")
    if len(category) > 50:
        return BulkImportError(row=row_index, reason="category 超過 50 字元")

    # 5. recorded_at 時間解析
    raw_ts = row["recorded_at"]
    try:
        if isinstance(raw_ts, datetime):
            recorded_at = raw_ts
        elif isinstance(raw_ts, pd.Timestamp):
            recorded_at = raw_ts.to_pydatetime()
        else:
            recorded_at = datetime.fromisoformat(str(raw_ts).strip())
    except (ValueError, TypeError):
        return BulkImportError(
            row=row_index, reason=f"recorded_at 格式不符（ISO 8601）：{raw_ts!r}"
        )

    # 6. is_anomaly 選填布林
    raw_anomaly = row.get("is_anomaly", False)
    if pd.isna(raw_anomaly) if isinstance(raw_anomaly, float) else False:
        is_anomaly = False
    elif isinstance(raw_anomaly, bool):
        is_anomaly = raw_anomaly
    elif isinstance(raw_anomaly, (int, float)):
        is_anomaly = bool(raw_anomaly)
    else:
        str_val = str(raw_anomaly).strip().lower()
        is_anomaly = str_val in ("true", "1", "yes")

    return DataCreate(
        title=title,
        value=value,
        category=category,
        recorded_at=recorded_at,
        is_anomaly=is_anomaly,
    )


def parse_csv(content: bytes) -> tuple[list[DataCreate], list[BulkImportError]]:
    """
    解析 CSV bytes，逐行驗證。
    回傳 (有效列表, 錯誤列表)。
    """
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str)
    except Exception as exc:
        return [], [BulkImportError(row=0, reason=f"CSV 解析失敗：{exc}")]

    # 欄位名稱 strip
    df.columns = [c.strip() for c in df.columns]

    valid: list[DataCreate] = []
    errors: list[BulkImportError] = []

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # row 1 = header，從 2 開始計
        result = _parse_row(row_num, row.to_dict())
        if isinstance(result, BulkImportError):
            errors.append(result)
        else:
            valid.append(result)

    return valid, errors


def parse_json(content: bytes) -> tuple[list[DataCreate], list[BulkImportError]]:
    """
    解析 JSON bytes（array of objects），逐筆驗證。
    回傳 (有效列表, 錯誤列表)。
    """
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [], [BulkImportError(row=0, reason=f"JSON 解析失敗：{exc}")]

    if not isinstance(data, list):
        return [], [BulkImportError(row=0, reason="JSON 必須為陣列格式")]

    valid: list[DataCreate] = []
    errors: list[BulkImportError] = []

    for idx, item in enumerate(data):
        row_num = idx + 1
        if not isinstance(item, dict):
            errors.append(BulkImportError(row=row_num, reason="每筆資料必須為物件格式"))
            continue
        result = _parse_row(row_num, item)
        if isinstance(result, BulkImportError):
            errors.append(result)
        else:
            valid.append(result)

    return valid, errors
