from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
from fastapi.responses import StreamingResponse

from app.schemas.analytics import CategoriesResponse, SummaryResponse, TimeRangeResponse


def _make_filename(export_date: date | None = None) -> str:
    """產生 Excel 匯出檔名：data_YYYY-MM-DD.xlsx。"""
    d = export_date or datetime.utcnow().date()
    return f"data_{d.isoformat()}.xlsx"


def build_excel_response(
    summary: SummaryResponse,
    timerange: TimeRangeResponse,
    categories: CategoriesResponse,
    export_date: date | None = None,
) -> StreamingResponse:
    """
    將分析資料打包成 Excel 檔（三個 sheet），
    回傳 StreamingResponse 附帶 Content-Disposition attachment。
    """
    filename = _make_filename(export_date)

    # 建立 Summary sheet
    summary_data = {
        "total_records": [summary.total_records],
        "anomaly_count": [summary.anomaly_count],
        "avg_value": [summary.avg_value],
        "min_value": [summary.min_value],
        "max_value": [summary.max_value],
        "categories": [", ".join(summary.categories)],
    }
    df_summary = pd.DataFrame(summary_data)

    # 建立 TimeRange sheet
    if timerange.buckets:
        df_timerange = pd.DataFrame(
            [
                {
                    "ts": b.ts.isoformat(),
                    "count": b.count,
                    "avg_value": b.avg_value,
                    "anomaly_count": b.anomaly_count,
                }
                for b in timerange.buckets
            ]
        )
    else:
        df_timerange = pd.DataFrame(columns=["ts", "count", "avg_value", "anomaly_count"])

    # 建立 Categories sheet
    if categories.categories:
        df_categories = pd.DataFrame(
            [
                {
                    "category": c.category,
                    "count": c.count,
                    "avg_value": c.avg_value,
                    "anomaly_count": c.anomaly_count,
                }
                for c in categories.categories
            ]
        )
    else:
        df_categories = pd.DataFrame(
            columns=["category", "count", "avg_value", "anomaly_count"]
        )

    # 用 openpyxl 引擎寫入 BytesIO
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Summary", index=False)
        df_timerange.to_excel(writer, sheet_name="TimeRange", index=False)
        df_categories.to_excel(writer, sheet_name="Categories", index=False)

    buffer.seek(0)

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    return StreamingResponse(
        iter([buffer.read()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
