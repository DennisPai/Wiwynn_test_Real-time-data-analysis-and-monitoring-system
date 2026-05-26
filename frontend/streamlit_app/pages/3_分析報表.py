"""
分析報表頁面：統一摘要 + 時間趨勢圖（Q7 fix）+ 類別分佈 + source toggle + Excel 匯出。
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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

st.markdown("---")

# ── 篩選 Widget ───────────────────────────────────────────────────────────────
with st.expander("查詢條件", expanded=True):
    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        now_utc = datetime.now(tz=timezone.utc)
        default_from = (now_utc - timedelta(days=7)).date()
        default_to = now_utc.date()
        f_date_from = st.date_input("起始日期", value=default_from, key="analytics_date_from")
        f_date_to = st.date_input("結束日期", value=default_to, key="analytics_date_to")

    with filter_col2:
        _KNOWN_CATEGORIES = ["（全部）", "temperature", "humidity", "pressure", "voltage", "cpu_usage"]
        f_category_label = st.selectbox("類別篩選（錄入資料）", _KNOWN_CATEGORIES, index=0)
        f_category: str | None = None if f_category_label == "（全部）" else f_category_label

    with filter_col3:
        _BUCKET_MAP = {"小時（hour）": "hour", "天（day）": "day"}
        f_bucket_label = st.selectbox("時間粒度", list(_BUCKET_MAP.keys()), index=1)
        f_bucket = _BUCKET_MAP[f_bucket_label]


def _build_date_params() -> dict[str, str]:
    """組裝通用日期查詢參數（UTC ISO8601 帶 Z）。"""
    return {
        "date_from": f_date_from.isoformat() + "T00:00:00Z",
        "date_to": f_date_to.isoformat() + "T23:59:59Z",
    }


# ── D4-4: Metric cards 改打 unified-summary ──────────────────────────────────
st.subheader("統合摘要統計")

_SOURCE_OPTIONS = {"兩者（即時+錄入）": "both", "僅即時資料": "realtime", "僅錄入資料": "records"}
source_label = st.selectbox("資料來源", list(_SOURCE_OPTIONS.keys()), index=0, key="summary_source")
source_val = _SOURCE_OPTIONS[source_label]


@st.cache_data(ttl=30)
def _fetch_unified_summary(date_from: str, date_to: str, source: str) -> dict:
    params: dict = {"date_from": date_from, "date_to": date_to, "source": source}
    resp = client.get("/analytics/unified-summary", params=params)
    if resp.status_code == 200:
        return resp.json()
    return {}


with st.spinner("載入統合摘要..."):
    try:
        dp = _build_date_params()
        unified = _fetch_unified_summary(dp["date_from"], dp["date_to"], source_val)
    except Exception as exc:
        st.error(f"無法取得統合摘要：{exc}")
        unified = {}

if unified:
    combined = unified.get("combined", {})
    realtime_info = unified.get("realtime", {})
    records_info = unified.get("records", {})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("合計筆數", combined.get("total", "—"))
    m2.metric("合計異常", combined.get("anomaly_count", "—"))
    m3.metric("即時資料筆數", realtime_info.get("total", "—"))
    m4.metric("錄入資料筆數", records_info.get("total", "—"))

    # 即時資料 metric 詳情
    rt_metrics = realtime_info.get("metrics", {})
    if rt_metrics:
        st.subheader("即時資料各 Metric 摘要")
        metric_zh = {
            "temperature": "溫度(C)",
            "humidity": "濕度(%)",
            "pressure": "氣壓(hPa)",
            "voltage": "電壓(V)",
            "cpu_usage": "CPU(%)",
        }
        rows = []
        for m_key, m_data in rt_metrics.items():
            rows.append({
                "Metric": metric_zh.get(m_key, m_key),
                "平均": f"{m_data.get('avg', 0):.2f}" if m_data.get("avg") is not None else "—",
                "最小": f"{m_data.get('min', 0):.2f}" if m_data.get("min") is not None else "—",
                "最大": f"{m_data.get('max', 0):.2f}" if m_data.get("max") is not None else "—",
                "異常筆數": m_data.get("anomaly_count", 0),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("查詢區間內沒有資料，或後端暫時無法回應。")

st.markdown("---")

# ── D4-3 / D4-5 時間趨勢圖（Q7 fix：正確渲染 buckets）──────────────────────────
st.subheader("時間趨勢圖")

# D4-5: source toggle
_TREND_SOURCE_OPTIONS = {
    "錄入資料（data_records）": "records",
    "即時資料（realtime）": "realtime",
}
trend_source_label = st.selectbox("趨勢圖資料來源", list(_TREND_SOURCE_OPTIONS.keys()), index=0, key="trend_source")
trend_source = _TREND_SOURCE_OPTIONS[trend_source_label]


@st.cache_data(ttl=30)
def _fetch_timerange(date_from: str, date_to: str, bucket: str, category: str | None) -> list[dict]:
    params: dict = {"date_from": date_from, "date_to": date_to, "bucket": bucket}
    if category:
        params["category"] = category
    resp = client.get("/analytics/timerange", params=params)
    if resp.status_code == 200:
        return resp.json().get("buckets", [])
    return []


@st.cache_data(ttl=30)
def _fetch_realtime_categories(date_from: str, date_to: str) -> list[dict]:
    params: dict = {"date_from": date_from, "date_to": date_to}
    resp = client.get("/analytics/realtime-categories", params=params)
    if resp.status_code == 200:
        return resp.json().get("metrics", [])
    return []


with st.spinner("載入時間趨勢..."):
    try:
        dp = _build_date_params()
        if trend_source == "records":
            buckets = _fetch_timerange(dp["date_from"], dp["date_to"], f_bucket, f_category)
        else:
            # 即時資料用 realtime-categories 的彙總，展示各 metric 分佈
            buckets = []
    except Exception as exc:
        st.error(f"無法取得時間趨勢資料：{exc}")
        buckets = []

if trend_source == "records":
    if buckets:
        df_time = pd.DataFrame(buckets)
        # Q7 fix：確保 ts 欄位存在且能正確解析
        if "ts" in df_time.columns and not df_time.empty:
            try:
                df_time["ts_tw"] = pd.to_datetime(df_time["ts"], utc=True, format="ISO8601").dt.tz_convert("Asia/Taipei")
            except Exception:
                # fallback：直接用原始字串
                df_time["ts_tw"] = df_time["ts"]
        else:
            df_time["ts_tw"] = pd.Series(dtype="object")

        fig_line = go.Figure()

        # 主折線（avg_value）
        if "avg_value" in df_time.columns:
            fig_line.add_trace(go.Scatter(
                x=df_time["ts_tw"],
                y=df_time["avg_value"],
                mode="lines+markers",
                name="平均值",
                line={"color": "royalblue"},
            ))

        # 筆數（count）次要折線
        if "count" in df_time.columns:
            fig_line.add_trace(go.Scatter(
                x=df_time["ts_tw"],
                y=df_time["count"],
                mode="lines",
                name="筆數",
                line={"color": "green", "dash": "dot"},
                yaxis="y2",
                visible="legendonly",
            ))

        # 標記異常 bucket
        if "anomaly_count" in df_time.columns:
            anomaly_df = df_time[df_time["anomaly_count"] > 0]
            if not anomaly_df.empty and "avg_value" in anomaly_df.columns:
                fig_line.add_trace(go.Scatter(
                    x=anomaly_df["ts_tw"],
                    y=anomaly_df["avg_value"],
                    mode="markers",
                    name="含異常",
                    marker={"color": "red", "size": 12, "symbol": "x"},
                    hovertext=anomaly_df["anomaly_count"].apply(lambda c: f"{c} 筆異常"),
                ))

        fig_line.update_layout(
            title=f"時間趨勢（{f_bucket_label}）{'— ' + f_category if f_category else '— 全類別'}（錄入資料）",
            xaxis_title="時間（台北）",
            yaxis_title="數值",
            legend={"orientation": "h", "y": -0.2},
            margin={"l": 40, "r": 20, "t": 50, "b": 80},
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("此區間內無時間趨勢資料。")
else:
    # 即時資料：顯示各 metric 彙總長條
    with st.spinner("載入即時資料 metrics..."):
        try:
            dp = _build_date_params()
            rt_cat_items = _fetch_realtime_categories(dp["date_from"], dp["date_to"])
        except Exception as exc:
            st.error(f"無法取得即時資料 metrics：{exc}")
            rt_cat_items = []

    if rt_cat_items:
        df_rt_cat = pd.DataFrame(rt_cat_items)
        metric_zh = {
            "temperature": "溫度(C)",
            "humidity": "濕度(%)",
            "pressure": "氣壓(hPa)",
            "voltage": "電壓(V)",
            "cpu_usage": "CPU(%)",
        }
        if "metric" in df_rt_cat.columns:
            df_rt_cat["metric_zh"] = df_rt_cat["metric"].apply(lambda m: metric_zh.get(m, m))

        fig_rt_bar = go.Figure(go.Bar(
            x=df_rt_cat.get("metric_zh", df_rt_cat.get("metric", [])),
            y=df_rt_cat.get("avg", []),
            marker_color="steelblue",
            name="平均值",
        ))
        fig_rt_bar.update_layout(
            title="即時資料各 Metric 平均值（選定日期範圍）",
            xaxis_title="Metric",
            yaxis_title="平均值",
            margin={"l": 40, "r": 20, "t": 50, "b": 40},
        )
        st.plotly_chart(fig_rt_bar, use_container_width=True)
    else:
        st.info("此區間內無即時資料。")

st.markdown("---")

# ── D4-6: 類別分佈（source toggle）─────────────────────────────────────────────
st.subheader("類別分佈")

_CAT_SOURCE_OPTIONS = {
    "錄入資料（data_records）": "records",
    "即時資料（realtime）": "realtime",
}
cat_source_label = st.selectbox("分佈資料來源", list(_CAT_SOURCE_OPTIONS.keys()), index=0, key="cat_source")
cat_source = _CAT_SOURCE_OPTIONS[cat_source_label]


@st.cache_data(ttl=30)
def _fetch_categories(date_from: str, date_to: str) -> list[dict]:
    params: dict = {"date_from": date_from, "date_to": date_to}
    resp = client.get("/analytics/categories", params=params)
    if resp.status_code == 200:
        return resp.json().get("categories", [])
    return []


with st.spinner("載入類別分佈..."):
    try:
        dp = _build_date_params()
        if cat_source == "records":
            cat_items = _fetch_categories(dp["date_from"], dp["date_to"])
            cat_col_name = "category"
            cat_label = "類別"
        else:
            cat_items = _fetch_realtime_categories(dp["date_from"], dp["date_to"])
            cat_col_name = "metric"
            cat_label = "Metric"
    except Exception as exc:
        st.error(f"無法取得類別分佈資料：{exc}")
        cat_items = []
        cat_col_name = "category"
        cat_label = "類別"

if cat_items:
    df_cat = pd.DataFrame(cat_items)
    if "count" in df_cat.columns and cat_col_name in df_cat.columns:
        df_cat = df_cat.sort_values("count", ascending=False)

    bar_col1, bar_col2 = st.columns(2)

    with bar_col1:
        fig_bar_count = go.Figure(go.Bar(
            x=df_cat.get(cat_col_name, []),
            y=df_cat.get("count", []),
            marker_color="steelblue",
        ))
        fig_bar_count.update_layout(
            title=f"各{cat_label}筆數",
            xaxis_title=cat_label,
            yaxis_title="筆數",
            margin={"l": 40, "r": 20, "t": 50, "b": 40},
        )
        st.plotly_chart(fig_bar_count, use_container_width=True)

    with bar_col2:
        avg_col = "avg_value" if cat_source == "records" else "avg"
        if avg_col in df_cat.columns:
            fig_bar_avg = go.Figure(go.Bar(
                x=df_cat.get(cat_col_name, []),
                y=df_cat.get(avg_col, []),
                marker_color="darkorange",
            ))
            fig_bar_avg.update_layout(
                title=f"各{cat_label}平均值",
                xaxis_title=cat_label,
                yaxis_title="平均",
                margin={"l": 40, "r": 20, "t": 50, "b": 40},
            )
            st.plotly_chart(fig_bar_avg, use_container_width=True)

    # 類別詳細表格
    st.subheader("類別詳細資料")
    display_df = df_cat.copy()
    if cat_source == "records":
        rename_map = {"category": "類別", "count": "筆數", "avg_value": "平均值", "anomaly_count": "異常筆數"}
    else:
        rename_map = {"metric": "Metric", "count": "筆數", "avg": "平均值", "anomaly_count": "異常筆數"}
    display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("此區間內無類別分佈資料。")

st.markdown("---")

# ── 匯出資料 ──────────────────────────────────────────────────────────────────
st.subheader("匯出資料")

dl_col1, dl_col2 = st.columns([2, 2])

with dl_col1:
    st.markdown(
        "點擊下方按鈕匯出目前篩選條件的資料為 **Excel (.xlsx)** 格式。  \n"
        f"篩選：{f_date_from} ~ {f_date_to}"
        + (f"，類別：{f_category}" if f_category else "，類別：全部"),
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
                if f_category:
                    export_params["category"] = f_category

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
