"""excel_exporter.py — T5.11: wide schema Excel 匯出。

design.md §5 /analytics/export AC：
- Summary sheet：per-metric column
- TimeRange sheet：每 bucket per-metric column
- Sources sheet（改名自 Categories）：per-source breakdown
"""
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
    T5.11: 將 wide schema 分析資料打包成 Excel 檔（三個 sheet）。
    - Summary sheet：per-metric column（avg/min/max/std/anomaly_count）
    - TimeRange sheet：每 bucket 含 per-metric column
    - Sources sheet（原 Categories）：per-metric breakdown（metric/count/avg/min/max/anomaly_count）
    回傳 StreamingResponse 附帶 Content-Disposition attachment。
    """
    filename = _make_filename(export_date)

    # ── Summary sheet（per-metric column）────────────────────────────────────
    summary_rows = [
        {
            "指標": "total",
            "count": summary.total,
            "anomaly_count": summary.anomaly_count,
            "anomaly_rate": round(summary.anomaly_rate, 6),
            "avg": "",
            "min": "",
            "max": "",
            "std": "",
        }
    ]
    for metric_name, stat in summary.per_metric.items():
        summary_rows.append({
            "指標": metric_name,
            "count": "",
            "anomaly_count": stat.anomaly_count,
            "anomaly_rate": "",
            "avg": round(stat.avg, 4),
            "min": round(stat.min, 4),
            "max": round(stat.max, 4),
            "std": round(stat.std, 4),
        })
    df_summary = pd.DataFrame(summary_rows)

    # ── TimeRange sheet（每 bucket per-metric column）────────────────────────
    _METRICS = ("temperature", "humidity", "pressure", "voltage", "cpu_usage")
    if timerange.buckets:
        timerange_rows = []
        for b in timerange.buckets:
            row: dict = {
                "ts": b.ts.isoformat(),
                "count": b.count,
                "anomaly_count": b.anomaly_count,
            }
            for metric in _METRICS:
                pm = b.per_metric.get(metric)
                if pm:
                    row[f"{metric}_avg"] = round(pm.avg, 4) if pm.avg is not None else None
                    row[f"{metric}_min"] = round(pm.min, 4) if pm.min is not None else None
                    row[f"{metric}_max"] = round(pm.max, 4) if pm.max is not None else None
                    row[f"{metric}_count"] = pm.count
                    row[f"{metric}_anomaly"] = pm.anomaly_count
                else:
                    row[f"{metric}_avg"] = None
                    row[f"{metric}_min"] = None
                    row[f"{metric}_max"] = None
                    row[f"{metric}_count"] = 0
                    row[f"{metric}_anomaly"] = 0
            timerange_rows.append(row)
        df_timerange = pd.DataFrame(timerange_rows)
    else:
        # 空 DataFrame 含完整欄位
        cols = ["ts", "count", "anomaly_count"]
        for metric in _METRICS:
            cols += [
                f"{metric}_avg",
                f"{metric}_min",
                f"{metric}_max",
                f"{metric}_count",
                f"{metric}_anomaly",
            ]
        df_timerange = pd.DataFrame(columns=cols)

    # ── Sources sheet（改名自 Categories，per-metric breakdown）───────────────
    if categories.metrics:
        df_sources = pd.DataFrame(
            [
                {
                    "metric": m.metric,
                    "count": m.count,
                    "avg": round(m.avg, 4),
                    "min": round(m.min, 4),
                    "max": round(m.max, 4),
                    "anomaly_count": m.anomaly_count,
                }
                for m in categories.metrics
            ]
        )
    else:
        df_sources = pd.DataFrame(
            columns=["metric", "count", "avg", "min", "max", "anomaly_count"]
        )

    # 用 openpyxl 引擎寫入 BytesIO
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Summary", index=False)
        df_timerange.to_excel(writer, sheet_name="TimeRange", index=False)
        df_sources.to_excel(writer, sheet_name="Sources", index=False)

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
