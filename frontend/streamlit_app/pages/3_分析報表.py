"""
分析報表頁面：統一摘要 + 時間趨勢圖（Q7 fix）+ 類別分佈 + source toggle + Excel 匯出。
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

st.caption("您可以在這裡查看資料分析報表：即時 + 錄入資料的統計摘要、時間趨勢圖、類別分布長條圖。可切換資料來源（兩者 / 僅即時 / 僅錄入）、調整時間粒度（小時 / 日），並可匯出 Excel 檔。")

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
source_label = st.selectbox(
    "資料來源",
    list(_SOURCE_OPTIONS.keys()),
    index=0,
    key="summary_source",
    help="兩者 = 即時 + 錄入合併統計；僅即時 = simulator 自動推送的軌道；僅錄入 = 使用者手動匯入的軌道。共用同 5 metric category 可跨軌比較。",
)
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
trend_source_label = st.selectbox(
    "趨勢圖資料來源",
    list(_TREND_SOURCE_OPTIONS.keys()),
    index=0,
    key="trend_source",
    help="即時軌（realtime）= simulator 每秒自動推送的 wide-format 快照，顯示過去 60 分鐘；錄入軌（data_records）= 使用者手動匯入的 long-format 歷史資料，支援 30 天跨期趨勢。共用同 5 metric category 可跨軌比較。",
)
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


@st.cache_data(ttl=10)
def _fetch_realtime_history_trend() -> list[dict]:
    """取得最近 60 分鐘即時資料 wide snapshots（BE 最大 3600 秒）。"""
    resp = client.get("/realtime/history", params={"seconds": 3600})
    if resp.status_code == 200:
        return resp.json().get("snapshots", [])
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

        # 主折線（avg_value）— 視覺強化：線粗 3、marker 變大、填充陰影
        if "avg_value" in df_time.columns:
            fig_line.add_trace(go.Scatter(
                x=df_time["ts_tw"],
                y=df_time["avg_value"],
                mode="lines+markers",
                name="平均值",
                line={"color": "royalblue", "width": 3},
                marker={"size": 10, "symbol": "circle"},
                fill="tozeroy",
                fillcolor="rgba(65,105,225,0.15)",
            ))

            # 在每個 marker 上方加 count 筆數 annotation
            if "count" in df_time.columns and not df_time.empty:
                for _, row in df_time.iterrows():
                    if pd.notna(row["avg_value"]) and pd.notna(row.get("count")):
                        fig_line.add_annotation(
                            x=row["ts_tw"], y=row["avg_value"],
                            text=f"{int(row['count'])} 筆", showarrow=False,
                            yshift=15, font=dict(size=10, color="gray"),
                        )

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
        st.caption(f"{'day' if f_bucket == 'day' else 'hour'} bucket：每{'日' if f_bucket == 'day' else '小時'} 1 點；如資料少請改 {'hour 粒度' if f_bucket == 'day' else 'day 粒度'}看更{'詳細' if f_bucket == 'day' else '匯總'}。")
    else:
        st.info("此區間內無時間趨勢資料。")
else:
    # 即時資料：真正的時間趨勢折線圖（過去 60 分鐘，5 metric 各自獨立 Y 軸）
    _RT_METRIC_KEYS = ["temperature", "humidity", "pressure", "voltage", "cpu_usage"]
    _RT_METRIC_ZH = {
        "temperature": "溫度(C)",
        "humidity": "濕度(%)",
        "pressure": "氣壓(hPa)",
        "voltage": "電壓(V)",
        "cpu_usage": "CPU(%)",
    }
    _RT_METRIC_COLORS = {
        "temperature": "royalblue",
        "humidity": "green",
        "pressure": "orange",
        "voltage": "purple",
        "cpu_usage": "teal",
    }

    with st.spinner("載入即時資料趨勢..."):
        try:
            rt_snapshots = _fetch_realtime_history_trend()
        except Exception as exc:
            st.error(f"無法取得即時資料趨勢：{exc}")
            rt_snapshots = []

    if rt_snapshots:
        df_rt_hist = pd.DataFrame(rt_snapshots)
        # 轉換時間軸為台北時間
        if "ts" in df_rt_hist.columns and not df_rt_hist.empty:
            try:
                df_rt_hist["ts_tw"] = pd.to_datetime(df_rt_hist["ts"], utc=True, format="ISO8601").dt.tz_convert("Asia/Taipei")
            except Exception:
                df_rt_hist["ts_tw"] = df_rt_hist["ts"]
        else:
            df_rt_hist["ts_tw"] = pd.Series(dtype="object")

        # 取交集（只顯示 DataFrame 中實際存在的 metric 欄位）
        available_metrics = [m for m in _RT_METRIC_KEYS if m in df_rt_hist.columns]
        n_selected = len(available_metrics)

        if n_selected > 0:
            # 使用 spike-results.md A.5 公式：height=min(180*n, 900)、shared_xaxes=True
            fig_rt_trend = make_subplots(
                rows=n_selected,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.04,
                subplot_titles=[_RT_METRIC_ZH.get(m, m) for m in available_metrics],
            )

            for idx, metric_key in enumerate(available_metrics, start=1):
                df_rt_hist[f"{metric_key}_float"] = pd.to_numeric(df_rt_hist[metric_key], errors="coerce")

                fig_rt_trend.add_trace(
                    go.Scatter(
                        x=df_rt_hist["ts_tw"],
                        y=df_rt_hist[f"{metric_key}_float"],
                        mode="lines",
                        name=_RT_METRIC_ZH.get(metric_key, metric_key),
                        line={"color": _RT_METRIC_COLORS.get(metric_key, "gray"), "width": 2},
                        showlegend=False,
                    ),
                    row=idx, col=1,
                )

                # 異常點標記
                if "anomaly_flags" in df_rt_hist.columns:
                    anom_mask = df_rt_hist.apply(
                        lambda r, mk=metric_key: bool(
                            r.get("anomaly_flags", {}).get(mk, False)
                            if isinstance(r.get("anomaly_flags"), dict)
                            else False
                        ),
                        axis=1,
                    )
                    anom_df = df_rt_hist[anom_mask]
                    if not anom_df.empty:
                        fig_rt_trend.add_trace(
                            go.Scatter(
                                x=anom_df["ts_tw"],
                                y=anom_df[f"{metric_key}_float"],
                                mode="markers",
                                marker={
                                    "color": "red",
                                    "size": 10,
                                    "symbol": "circle-open",
                                    "line": {"width": 2, "color": "red"},
                                },
                                showlegend=False,
                            ),
                            row=idx, col=1,
                        )

            fig_rt_trend.update_layout(
                title="即時資料趨勢（過去 60 分鐘）",
                height=min(180 * n_selected, 900),
                margin={"l": 60, "r": 20, "t": 60, "b": 40},
                uirevision="rt_trend_chart",
                showlegend=False,
            )
            fig_rt_trend.update_xaxes(title_text="時間（台北）", row=n_selected, col=1)

            st.plotly_chart(fig_rt_trend, use_container_width=True)
            st.caption("即時資料時間趨勢顯示過去 60 分鐘；如需更長範圍請看「錄入資料」source（支援 30 天）。")
        else:
            st.info("即時資料欄位不足，無法繪製趨勢圖。")
    else:
        st.info("此時間內無即時資料，或後端尚未啟動 simulator（等待 simulator 預熱後重新整理）。")

st.markdown("---")

# ── D4-6: 類別分佈（source toggle）─────────────────────────────────────────────
st.subheader("類別分佈")

_CAT_SOURCE_OPTIONS = {
    "錄入資料（data_records）": "records",
    "即時資料（realtime）": "realtime",
}
cat_source_label = st.selectbox(
    "分佈資料來源",
    list(_CAT_SOURCE_OPTIONS.keys()),
    index=0,
    key="cat_source",
    help="即時軌（realtime）= simulator 自動推送的各 metric 分佈統計；錄入軌（data_records）= 使用者手動匯入的各 category 分佈統計。兩軌共用同 5 metric category，切換可比較兩軌資料分佈差異。",
)
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
