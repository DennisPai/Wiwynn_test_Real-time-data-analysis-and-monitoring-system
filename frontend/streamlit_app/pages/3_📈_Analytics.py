"""
Analytics 頁面：聚合分析 + Plotly 圖表 + Excel 下載。
- 日期區間 selector（預設過去 7 天）
- 類別 selector + bucket selector（hour/day）
- /analytics/summary → 4 個 metric cards
- /analytics/timerange → Plotly 折線圖（anomaly_threshold_high 標紅）
- /analytics/categories → Plotly 長條圖
- /analytics/export → Excel 下載
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
    page_title="Analytics — 即時資料分析與監控系統",
    page_icon="📈",
    layout="wide",
)

# 認證守衛
require_auth()

client = APIClient()
user = current_user()
role = current_role()

# ── 時間輔助函式 ───────────────────────────────────────────────────────────────

def format_ts(iso_str: str | None) -> str:
    """
    將後端 UTC ISO8601 字串轉換為台北時間（Asia/Taipei）並格式化輸出。
    若 iso_str 為 None 或無法解析，回傳空字串。
    """
    if not iso_str:
        return ""
    try:
        dt = pd.to_datetime(iso_str, utc=True).tz_convert("Asia/Taipei")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(iso_str)


# ── 右上角：使用者資訊 + 登出 ─────────────────────────────────────────────────
col_title, col_user = st.columns([3, 1])
with col_title:
    st.title("📈 Analytics")
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
with st.expander("🔍 查詢條件", expanded=True):
    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        now_utc = datetime.now(tz=timezone.utc)
        default_from = (now_utc - timedelta(days=7)).date()
        default_to = now_utc.date()
        f_date_from = st.date_input("起始日期", value=default_from, key="analytics_date_from")
        f_date_to = st.date_input("結束日期", value=default_to, key="analytics_date_to")

    with filter_col2:
        # 類別選單：從已知類別或使用者輸入
        _KNOWN_CATEGORIES = ["（全部）", "temperature", "humidity", "pressure", "vibration", "power"]
        f_category_label = st.selectbox("類別篩選", _KNOWN_CATEGORIES, index=0)
        f_category: str | None = None if f_category_label == "（全部）" else f_category_label

    with filter_col3:
        _BUCKET_MAP = {"小時（hour）": "hour", "天（day）": "day"}
        f_bucket_label = st.selectbox("時間粒度", list(_BUCKET_MAP.keys()), index=1)
        f_bucket = _BUCKET_MAP[f_bucket_label]


def _build_date_params() -> dict[str, str]:
    """組裝通用日期查詢參數（UTC ISO8601）。"""
    return {
        "date_from": f_date_from.isoformat() + "T00:00:00Z",
        "date_to": f_date_to.isoformat() + "T23:59:59Z",
    }


# ── 取得異常閾值（供 highlight 使用）─────────────────────────────────────────

@st.cache_data(ttl=60)
def _fetch_anomaly_threshold() -> float:
    """從 /admin/settings 取得 anomaly_threshold_high；非 admin 無法取得時使用預設值 80.0。"""
    if role == "admin":
        resp = client.get("/admin/settings")
        if resp.status_code == 200:
            settings = resp.json()
            for item in settings:
                if item.get("key") == "anomaly_threshold_high":
                    try:
                        return float(item["value"])
                    except (ValueError, KeyError):
                        pass
    return 80.0


anomaly_threshold = _fetch_anomaly_threshold()

# ── /analytics/summary → 4 個 metric cards ────────────────────────────────────

st.subheader("摘要統計")

@st.cache_data(ttl=30)
def _fetch_summary(date_from: str, date_to: str, category: str | None) -> dict:
    params: dict = {"date_from": date_from, "date_to": date_to}
    if category:
        params["category"] = category
    resp = client.get("/analytics/summary", params=params)
    if resp.status_code == 200:
        return resp.json()
    return {}


with st.spinner("載入摘要統計..."):
    try:
        dp = _build_date_params()
        summary = _fetch_summary(dp["date_from"], dp["date_to"], f_category)
    except Exception as exc:
        st.error(f"無法取得摘要統計：{exc}")
        summary = {}

if summary:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("總筆數", summary.get("count", "—"))
    m2.metric("合計", f"{summary.get('sum', 0):.2f}" if summary.get("sum") is not None else "—")
    m3.metric("平均值", f"{summary.get('avg', 0):.2f}" if summary.get("avg") is not None else "—")
    m4.metric("最大值", f"{summary.get('max', 0):.2f}" if summary.get("max") is not None else "—")

    anomaly_count = summary.get("anomaly_count", 0)
    if anomaly_count and anomaly_count > 0:
        st.warning(f"⚠️ 期間內共有 **{anomaly_count}** 筆異常資料（閾值：{anomaly_threshold}）")
else:
    st.info("查詢區間內沒有資料，或後端暫時無法回應。")

st.markdown("---")

# ── /analytics/timerange → 折線圖 ─────────────────────────────────────────────

st.subheader("時間趨勢圖")

@st.cache_data(ttl=30)
def _fetch_timerange(date_from: str, date_to: str, bucket: str, category: str | None) -> list[dict]:
    params: dict = {"date_from": date_from, "date_to": date_to, "bucket": bucket}
    if category:
        params["category"] = category
    resp = client.get("/analytics/timerange", params=params)
    if resp.status_code == 200:
        return resp.json().get("buckets", [])
    return []


with st.spinner("載入時間趨勢..."):
    try:
        dp = _build_date_params()
        buckets = _fetch_timerange(dp["date_from"], dp["date_to"], f_bucket, f_category)
    except Exception as exc:
        st.error(f"無法取得時間趨勢資料：{exc}")
        buckets = []

if buckets:
    df_time = pd.DataFrame(buckets)
    # 轉換時間戳（UTC → 台北）
    if "ts" in df_time.columns:
        df_time["ts_tw"] = pd.to_datetime(df_time["ts"], utc=True).dt.tz_convert("Asia/Taipei")
    else:
        df_time["ts_tw"] = pd.Series(dtype="object")

    fig_line = go.Figure()

    # 主折線（avg）
    fig_line.add_trace(go.Scatter(
        x=df_time["ts_tw"],
        y=df_time.get("avg", []),
        mode="lines+markers",
        name="平均值",
        line={"color": "royalblue"},
    ))

    # 合計值（sum）次要折線
    if "sum" in df_time.columns:
        fig_line.add_trace(go.Scatter(
            x=df_time["ts_tw"],
            y=df_time["sum"],
            mode="lines",
            name="合計",
            line={"color": "green", "dash": "dot"},
            visible="legendonly",
        ))

    # 異常閾值參考線（anomaly_threshold_high）
    fig_line.add_hline(
        y=anomaly_threshold,
        line_dash="dash",
        line_color="red",
        annotation_text=f"異常閾值 {anomaly_threshold}",
        annotation_position="bottom right",
    )

    # 標記超過閾值的點（紅色）
    if "avg" in df_time.columns:
        anomaly_mask = df_time["avg"] > anomaly_threshold
        anomaly_df = df_time[anomaly_mask]
        if not anomaly_df.empty:
            fig_line.add_trace(go.Scatter(
                x=anomaly_df["ts_tw"],
                y=anomaly_df["avg"],
                mode="markers",
                name="異常點",
                marker={"color": "red", "size": 10, "symbol": "x"},
            ))

    fig_line.update_layout(
        title=f"時間趨勢（{f_bucket_label}）{'— ' + f_category if f_category else '— 全類別'}",
        xaxis_title="時間（台北）",
        yaxis_title="數值",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 40, "r": 20, "t": 50, "b": 80},
    )
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("此區間內無時間趨勢資料。")

st.markdown("---")

# ── /analytics/categories → 長條圖 ────────────────────────────────────────────

st.subheader("類別分佈")

@st.cache_data(ttl=30)
def _fetch_categories(date_from: str, date_to: str) -> list[dict]:
    params: dict = {"date_from": date_from, "date_to": date_to}
    resp = client.get("/analytics/categories", params=params)
    if resp.status_code == 200:
        return resp.json().get("items", [])
    return []


with st.spinner("載入類別分佈..."):
    try:
        dp = _build_date_params()
        cat_items = _fetch_categories(dp["date_from"], dp["date_to"])
    except Exception as exc:
        st.error(f"無法取得類別分佈資料：{exc}")
        cat_items = []

if cat_items:
    df_cat = pd.DataFrame(cat_items)
    # 依合計值降冪排序
    if "sum" in df_cat.columns and "category" in df_cat.columns:
        df_cat = df_cat.sort_values("sum", ascending=False)

    bar_col1, bar_col2 = st.columns(2)

    with bar_col1:
        # 合計長條圖
        fig_bar_sum = go.Figure(go.Bar(
            x=df_cat.get("category", []),
            y=df_cat.get("sum", []),
            marker_color="steelblue",
        ))
        fig_bar_sum.update_layout(
            title="各類別合計值",
            xaxis_title="類別",
            yaxis_title="合計",
            margin={"l": 40, "r": 20, "t": 50, "b": 40},
        )
        st.plotly_chart(fig_bar_sum, use_container_width=True)

    with bar_col2:
        # 平均長條圖
        fig_bar_avg = go.Figure(go.Bar(
            x=df_cat.get("category", []),
            y=df_cat.get("avg", []),
            marker_color="darkorange",
        ))
        fig_bar_avg.update_layout(
            title="各類別平均值",
            xaxis_title="類別",
            yaxis_title="平均",
            margin={"l": 40, "r": 20, "t": 50, "b": 40},
        )
        st.plotly_chart(fig_bar_avg, use_container_width=True)

    # 類別詳細表格
    st.subheader("類別詳細資料")
    display_df = df_cat.copy()
    rename_map = {"category": "類別", "sum": "合計", "avg": "平均", "count": "筆數"}
    display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("此區間內無類別分佈資料。")

st.markdown("---")

# ── /analytics/export → Excel 下載 ────────────────────────────────────────────

st.subheader("匯出資料")

dl_col1, dl_col2 = st.columns([2, 2])

with dl_col1:
    st.markdown(
        "點擊下方按鈕匯出目前篩選條件的資料為 **Excel (.xlsx)** 格式。  \n"
        f"篩選：{f_date_from} ~ {f_date_to}"
        + (f"，類別：{f_category}" if f_category else "，類別：全部"),
    )

with dl_col2:
    if st.button("📥 準備 Excel 下載", key="prepare_export", type="primary"):
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
                    # 從 Content-Disposition 取出檔名
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

# 若有準備好的 Excel，顯示下載按鈕
if st.session_state.get("export_data"):
    st.download_button(
        label="⬇️ 下載 Excel",
        data=st.session_state["export_data"],
        file_name=st.session_state.get("export_filename", "data_export.xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_excel_btn",
    )
