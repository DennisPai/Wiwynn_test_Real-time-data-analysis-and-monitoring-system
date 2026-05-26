"""
分析報表頁面：wide schema 統計摘要 + 時間趨勢 + 5-metric breakdown + anomaly distribution。
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from api_client import APIClient
from auth import current_role, current_user, logout, require_auth

st.set_page_config(
    page_title="分析報表 — 即時資料分析與監控系統",
    page_icon=None,
    layout="wide",
)

# 認證守衛
require_auth()

client = APIClient()
user = current_user()
role = current_role()

_METRICS = ["temperature", "humidity", "pressure", "voltage", "cpu_usage"]
_METRIC_ZH = {
    "temperature": "溫度 °C",
    "humidity": "濕度 %",
    "pressure": "壓力 kPa",
    "voltage": "電壓 V",
    "cpu_usage": "CPU %",
}
_METRIC_COLORS = {
    "temperature": "royalblue",
    "humidity": "green",
    "pressure": "orange",
    "voltage": "purple",
    "cpu_usage": "teal",
}


def format_ts(iso_str: str | None) -> str:
    """將後端 UTC ISO8601 字串轉換為台北時間並格式化。"""
    if not iso_str:
        return ""
    try:
        dt = pd.to_datetime(iso_str, utc=True, format="ISO8601").tz_convert("Asia/Taipei")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(iso_str)


# ── 右上角：使用者資訊 + 登出 ─────────────────────────────────────────────────
col_title, col_user = st.columns([3, 1])
with col_title:
    st.title("分析報表")
with col_user:
    st.markdown(
        f"**{user.get('display_name', '未知')}**  \n"
        f"角色：`{role}`",
    )
    if st.button("登出", key="logout_btn", use_container_width=True):
        logout()
        st.switch_page("Home.py")

st.caption(
    "查看資料分析報表：KPI 摘要、5-metric breakdown、異常分布圖、時間趨勢。"
    "可透過查詢條件篩選來源與日期範圍，並匯出 Excel。"
)

st.markdown("---")

# ── 篩選 Widget ───────────────────────────────────────────────────────────────
with st.expander("查詢條件", expanded=True):
    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        now_utc = datetime.now(tz=timezone.utc)
        default_from = (now_utc - timedelta(days=7)).date()
        default_to = now_utc.date()
        f_date_from = st.date_input("起始日期", value=default_from, key="analytics_date_from")
        f_date_to = st.date_input("結束日期", value=default_to, key="analytics_date_to")

    with filter_col2:
        _BUCKET_MAP = {"小時（hour）": "hour", "天（day）": "day"}
        f_bucket_label = st.selectbox("時間粒度", list(_BUCKET_MAP.keys()), index=1)
        f_bucket = _BUCKET_MAP[f_bucket_label]


def _build_date_params() -> dict[str, str]:
    """組裝通用日期查詢參數（UTC ISO8601 帶 Z）。"""
    return {
        "date_from": f_date_from.isoformat() + "T00:00:00Z",
        "date_to": f_date_to.isoformat() + "T23:59:59Z",
    }


# ── T7.3: 4 個 KPI cards（打 summary endpoint）────────────────────────────────
st.subheader("資料摘要")


@st.cache_data(ttl=30)
def _fetch_summary(date_from: str, date_to: str, sources_key: str) -> dict:
    params: dict = {"date_from": date_from, "date_to": date_to}
    if sources_key:
        params["sources"] = sources_key.split(",")
    resp = client.get("/analytics/summary", params=params)
    if resp.status_code == 200:
        return resp.json()
    return {}


# Phase 11.4: source filter removed — scope A data_records only has source='user'.
# Pass empty string to all fetch functions (no source filter applied).
sources_cache_key = ""

with st.spinner("載入統計摘要..."):
    try:
        dp = _build_date_params()
        summary_data = _fetch_summary(dp["date_from"], dp["date_to"], sources_cache_key)
    except Exception as exc:
        st.error(f"無法取得統計摘要：{exc}")
        summary_data = {}

if summary_data:
    total_count = summary_data.get("total", 0)
    anomaly_count = summary_data.get("anomaly_count", 0)
    anomaly_rate = summary_data.get("anomaly_rate", 0.0)

    # 時間範圍天數
    try:
        days_delta = (f_date_to - f_date_from).days + 1
    except Exception:
        days_delta = "—"

    # T7.3: 4 個 KPI cards
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    kpi_col1.metric("總資料筆數", total_count)
    kpi_col2.metric("含異常筆數", anomaly_count)
    kpi_col3.metric(
        "異常率（%）",
        f"{anomaly_rate * 100:.1f}%" if isinstance(anomaly_rate, (int, float)) else "—",
    )
    kpi_col4.metric("時間範圍（天）", days_delta)
else:
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    kpi_col1.metric("總資料筆數", "—")
    kpi_col2.metric("含異常筆數", "—")
    kpi_col3.metric("異常率（%）", "—")
    kpi_col4.metric("時間範圍（天）", "—")
    st.info("查詢區間內沒有資料，或後端暫時無法回應。")

st.markdown("---")

# ── T7.3: 5-metric breakdown 表格（5 row × 5 col）────────────────────────────
st.subheader("各指標統計（5-Metric Breakdown）")

if summary_data:
    per_metric = summary_data.get("per_metric", {})
    if per_metric:
        breakdown_rows = []
        for mk in _METRICS:
            m_data = per_metric.get(mk, {})
            breakdown_rows.append({
                "指標": _METRIC_ZH.get(mk, mk),
                "平均": f"{m_data.get('avg', 0):.4f}" if m_data.get("avg") is not None else "—",
                "最小": f"{m_data.get('min', 0):.4f}" if m_data.get("min") is not None else "—",
                "最大": f"{m_data.get('max', 0):.4f}" if m_data.get("max") is not None else "—",
                "標準差": f"{m_data.get('std', 0):.4f}" if m_data.get("std") is not None else "—",
                "異常筆數": m_data.get("anomaly_count", 0),
            })
        st.dataframe(pd.DataFrame(breakdown_rows), use_container_width=True, hide_index=True)
    else:
        st.info("此區間內無 per-metric 統計資料。")
else:
    st.info("統計資料載入中或無資料。")

st.markdown("---")

# ── T7.3: anomaly distribution bar chart（5 metric 異常筆數對比）──────────────
st.subheader("異常分布（各指標異常筆數）")

if summary_data:
    per_metric = summary_data.get("per_metric", {})
    if per_metric:
        anom_metrics = [_METRIC_ZH.get(mk, mk) for mk in _METRICS]
        anom_counts = [per_metric.get(mk, {}).get("anomaly_count", 0) for mk in _METRICS]
        anom_colors = [_METRIC_COLORS.get(mk, "gray") for mk in _METRICS]

        fig_anom = go.Figure(go.Bar(
            x=anom_metrics,
            y=anom_counts,
            marker_color=anom_colors,
            text=anom_counts,
            textposition="outside",
        ))
        fig_anom.update_layout(
            title="各指標異常筆數對比",
            xaxis_title="指標",
            yaxis_title="異常筆數",
            margin={"l": 40, "r": 20, "t": 50, "b": 40},
        )
        st.plotly_chart(fig_anom, use_container_width=True)
    else:
        st.info("此區間內無異常分布資料。")
else:
    st.info("統計資料載入中或無資料。")

st.markdown("---")

# ── 時間趨勢圖（per-metric，來自 timerange endpoint）─────────────────────────
st.subheader("時間趨勢圖")


@st.cache_data(ttl=30)
def _fetch_timerange(date_from: str, date_to: str, bucket: str, sources_key: str) -> list[dict]:
    params: dict = {"date_from": date_from, "date_to": date_to, "bucket": bucket}
    if sources_key:
        params["sources"] = sources_key.split(",")
    resp = client.get("/analytics/timerange", params=params)
    if resp.status_code == 200:
        return resp.json().get("buckets", [])
    return []


with st.spinner("載入時間趨勢..."):
    try:
        dp = _build_date_params()
        buckets = _fetch_timerange(dp["date_from"], dp["date_to"], f_bucket, sources_cache_key)
    except Exception as exc:
        st.error(f"無法取得時間趨勢資料：{exc}")
        buckets = []

if buckets:
    df_time = pd.DataFrame(buckets)
    if "ts" in df_time.columns and not df_time.empty:
        try:
            df_time["ts_tw"] = pd.to_datetime(df_time["ts"], utc=True, format="ISO8601").dt.tz_convert("Asia/Taipei")
        except Exception:
            df_time["ts_tw"] = df_time["ts"]
    else:
        df_time["ts_tw"] = pd.Series(dtype="object")

    # per-metric 子圖
    available_metrics = [mk for mk in _METRICS if "per_metric" in df_time.columns or any(
        isinstance(b.get("per_metric"), dict) and mk in b.get("per_metric", {})
        for b in buckets
    )]
    # 從 buckets 解壓 per-metric avg
    metric_series: dict[str, list] = {mk: [] for mk in _METRICS}
    for b in buckets:
        pm = b.get("per_metric") or {}
        for mk in _METRICS:
            metric_series[mk].append(pm.get(mk, {}).get("avg") if isinstance(pm.get(mk), dict) else None)

    ts_vals = df_time["ts_tw"].tolist()
    plotted_metrics = [mk for mk in _METRICS if any(v is not None for v in metric_series[mk])]

    if plotted_metrics:
        n = len(plotted_metrics)
        fig_trend = make_subplots(
            rows=n,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=[_METRIC_ZH.get(mk, mk) for mk in plotted_metrics],
        )
        for idx, mk in enumerate(plotted_metrics, start=1):
            fig_trend.add_trace(
                go.Scatter(
                    x=ts_vals,
                    y=metric_series[mk],
                    mode="lines+markers",
                    name=_METRIC_ZH.get(mk, mk),
                    line={"color": _METRIC_COLORS.get(mk, "gray"), "width": 2},
                    marker={"size": 6},
                    showlegend=False,
                ),
                row=idx,
                col=1,
            )
            # 異常 bucket 標記
            anom_y = []
            anom_x = []
            for i, b in enumerate(buckets):
                pm = b.get("per_metric") or {}
                mk_data = pm.get(mk, {})
                if isinstance(mk_data, dict) and mk_data.get("anomaly_count", 0) > 0:
                    anom_x.append(ts_vals[i])
                    anom_y.append(metric_series[mk][i])
            if anom_x:
                fig_trend.add_trace(
                    go.Scatter(
                        x=anom_x,
                        y=anom_y,
                        mode="markers",
                        marker={"color": "red", "size": 10, "symbol": "x"},
                        showlegend=False,
                    ),
                    row=idx,
                    col=1,
                )

        fig_trend.update_layout(
            title=f"各指標時間趨勢（{f_bucket_label}）",
            height=min(180 * n, 900),
            margin={"l": 60, "r": 20, "t": 60, "b": 40},
            uirevision="trend_chart",
        )
        fig_trend.update_xaxes(title_text="時間（台北）", row=n, col=1)
        st.plotly_chart(fig_trend, use_container_width=True)
        st.caption(
            f"{'day' if f_bucket == 'day' else 'hour'} bucket：每{'日' if f_bucket == 'day' else '小時'} 1 點；"
            "紅叉 = 含異常。"
        )
    else:
        st.info("此區間內無時間趨勢資料。")
else:
    st.info("此區間內無時間趨勢資料。")

st.markdown("---")

# ── T7.3: per-metric breakdown（取代「分類聚合」）────────────────────────────
st.subheader("各指標彙整（Per-Metric Breakdown）")


@st.cache_data(ttl=30)
def _fetch_categories(date_from: str, date_to: str, sources_key: str) -> list[dict]:
    params: dict = {"date_from": date_from, "date_to": date_to}
    if sources_key:
        params["sources"] = sources_key.split(",")
    resp = client.get("/analytics/categories", params=params)
    if resp.status_code == 200:
        return resp.json().get("metrics", [])
    return []


with st.spinner("載入指標彙整..."):
    try:
        dp = _build_date_params()
        metric_items = _fetch_categories(dp["date_from"], dp["date_to"], sources_cache_key)
    except Exception as exc:
        st.error(f"無法取得指標彙整資料：{exc}")
        metric_items = []

if metric_items:
    df_metrics = pd.DataFrame(metric_items)
    rename_map = {
        "metric": "指標",
        "count": "筆數",
        "avg": "平均值",
        "min": "最小值",
        "max": "最大值",
        "anomaly_count": "異常筆數",
    }
    # 顯示用中文指標名稱
    if "metric" in df_metrics.columns:
        df_metrics["metric"] = df_metrics["metric"].apply(lambda m: _METRIC_ZH.get(m, m))
    df_metrics_show = df_metrics.rename(columns={k: v for k, v in rename_map.items() if k in df_metrics.columns})
    st.dataframe(df_metrics_show, use_container_width=True, hide_index=True)

    # 筆數 + 異常數 bar chart
    if "指標" in df_metrics_show.columns or "metric" in df_metrics.columns:
        x_vals = df_metrics_show.get("指標", df_metrics.get("metric", pd.Series())).tolist()
        cnt_vals = df_metrics.get("count", pd.Series([0] * len(x_vals))).tolist()
        anom_vals = df_metrics.get("anomaly_count", pd.Series([0] * len(x_vals))).tolist()

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            fig_bc = go.Figure(go.Bar(x=x_vals, y=cnt_vals, marker_color="steelblue"))
            fig_bc.update_layout(title="各指標筆數", xaxis_title="指標", yaxis_title="筆數", margin={"l": 40, "r": 20, "t": 50, "b": 40})
            st.plotly_chart(fig_bc, use_container_width=True)
        with chart_col2:
            fig_ac = go.Figure(go.Bar(x=x_vals, y=anom_vals, marker_color="crimson"))
            fig_ac.update_layout(title="各指標異常筆數", xaxis_title="指標", yaxis_title="異常筆數", margin={"l": 40, "r": 20, "t": 50, "b": 40})
            st.plotly_chart(fig_ac, use_container_width=True)
else:
    st.info("此區間內無指標彙整資料。")

st.markdown("---")

# ── T7.3: 保留 user / simulator / realtime 三 source unified-summary ────
st.subheader("即時 vs 錄入 資料總覽")


@st.cache_data(ttl=30)
def _fetch_unified_summary(date_from: str, date_to: str, sources_key: str) -> dict:
    params: dict = {"date_from": date_from, "date_to": date_to}
    if sources_key:
        params["sources"] = sources_key.split(",")
    resp = client.get("/analytics/unified-summary", params=params)
    if resp.status_code == 200:
        return resp.json()
    return {}


with st.spinner("載入來源總覽..."):
    try:
        dp = _build_date_params()
        unified = _fetch_unified_summary(dp["date_from"], dp["date_to"], sources_cache_key)
    except Exception as exc:
        st.error(f"無法取得來源總覽：{exc}")
        unified = {}

if unified:
    total_unified = unified.get("total", 0)
    anomaly_unified = unified.get("anomaly_count", 0)

    # per-source breakdown（user / simulator_data_records / realtime）
    user_stat = unified.get("user") or {}
    sim_stat = unified.get("simulator_data_records") or {}
    rt_stat = unified.get("realtime") or {}

    u_col1, u_col2, u_col3, u_col4 = st.columns(4)
    u_col1.metric("合計筆數", total_unified)
    u_col2.metric("合計異常", anomaly_unified)
    u_col3.metric(
        "錄入資料筆數",
        user_stat.get("count", "—"),
    )
    u_col4.metric(
        "即時資料筆數（串流）",
        rt_stat.get("count", "—"),
    )

    # source breakdown 表
    src_rows = []
    if user_stat:
        src_rows.append({
            "來源": "錄入資料（手動輸入 / CSV 匯入）",
            "筆數": user_stat.get("count", 0),
            "異常筆數": user_stat.get("anomaly_count", 0),
        })
    if sim_stat:
        src_rows.append({
            "來源": "即時資料（已歸檔）",
            "筆數": sim_stat.get("count", 0),
            "異常筆數": sim_stat.get("anomaly_count", 0),
        })
    if rt_stat:
        src_rows.append({
            "來源": "即時資料（串流中）",
            "筆數": rt_stat.get("count", 0),
            "異常筆數": rt_stat.get("anomaly_count", 0),
        })
    if src_rows:
        st.dataframe(pd.DataFrame(src_rows), use_container_width=True, hide_index=True)
else:
    st.info("查詢區間內沒有來源資料，或後端暫時無法回應。")

st.markdown("---")

# ── 匯出資料 ──────────────────────────────────────────────────────────────────
st.subheader("匯出資料")

dl_col1, dl_col2 = st.columns([2, 2])

with dl_col1:
    st.markdown(
        "點擊下方按鈕匯出目前篩選條件的資料為 **Excel (.xlsx)** 格式。  \n"
        f"篩選：{f_date_from} ~ {f_date_to}，來源：全部",
    )

with dl_col2:
    if st.button("準備 Excel 下載", key="prepare_export", type="primary"):
        with st.spinner("正在從後端取得 Excel 檔案..."):
            try:
                export_params: dict = {
                    "date_from": f_date_from.isoformat() + "T00:00:00Z",
                    "date_to": f_date_to.isoformat() + "T23:59:59Z",
                    "format": "xlsx",
                }

                resp_export = client.get("/analytics/export", params=export_params)

                if resp_export.status_code == 200:
                    content_disposition = resp_export.headers.get("content-disposition", "")
                    filename = "data_export.xlsx"
                    if "filename=" in content_disposition:
                        try:
                            filename = content_disposition.split("filename=")[-1].strip('"').strip()
                        except Exception:
                            pass

                    st.session_state["export_data"] = resp_export.content
                    st.session_state["export_filename"] = filename
                    st.success(f"Excel 已準備完畢（{filename}），請點擊下方下載按鈕。")
                else:
                    try:
                        detail = resp_export.json().get("detail", "匯出失敗")
                    except Exception:
                        detail = f"匯出失敗（HTTP {resp_export.status_code}）"
                    st.error(f"匯出失敗：{detail}")
            except Exception as exc:
                st.error(f"匯出時發生錯誤：{exc}")

if st.session_state.get("export_data"):
    st.download_button(
        label="下載 Excel",
        data=st.session_state["export_data"],
        file_name=st.session_state.get("export_filename", "data_export.xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_excel_btn",
    )
