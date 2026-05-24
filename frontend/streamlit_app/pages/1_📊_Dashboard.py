"""
Dashboard 頁面：總覽 metric cards + 最近 10 筆資料 + 使用者資訊。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from api_client import APIClient
from auth import current_role, current_user, logout, require_auth

st.set_page_config(
    page_title="Dashboard — 即時資料分析與監控系統",
    page_icon="📊",
    layout="wide",
)

# 認證守衛
require_auth()

client = APIClient()
user = current_user()
role = current_role()

# ── 右上角：使用者資訊 + 登出 ─────────────────────────────────────────────────
col_title, col_user = st.columns([3, 1])
with col_title:
    st.title("📊 Dashboard")
with col_user:
    st.markdown(
        f"**{user.get('display_name', '未知')}**  \n"
        f"角色：`{role}`  \n"
        f"Email：{user.get('email', '')}",
    )
    if st.button("登出", key="logout_btn", use_container_width=True):
        logout()
        st.switch_page("Home.py")

st.markdown("---")


# ── 取得 metric 所需資料 ────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _fetch_data_stats() -> dict:
    """
    從 /data 及 /analytics/summary 取得統計數字。
    回傳 dict: total / mine / today_count / anomaly_count。
    """
    now_utc = datetime.now(tz=timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    # 總筆數（page=1, size=1，從 total 取值）
    resp_total = client.get("/data", params={"page": 1, "size": 1})
    total = 0
    if resp_total.status_code == 200:
        total = resp_total.json().get("total", 0)

    # 我的資料筆數（以 owner_id 篩選）
    my_id = user.get("id")
    mine = 0
    if my_id:
        resp_mine = client.get("/data", params={"page": 1, "size": 1, "owner_id": my_id})
        if resp_mine.status_code == 200:
            mine = resp_mine.json().get("total", 0)

    # 今日新增（date_from = 今天 00:00 UTC）
    resp_today = client.get(
        "/data",
        params={
            "page": 1,
            "size": 1,
            "date_from": today_start.isoformat(),
        },
    )
    today_count = 0
    if resp_today.status_code == 200:
        today_count = resp_today.json().get("total", 0)

    # 異常筆數：透過 analytics/summary（全時間段）
    anomaly_count = 0
    resp_summary = client.get("/analytics/summary", params={
        "date_from": "2000-01-01T00:00:00",
        "date_to": now_utc.isoformat(),
    })
    if resp_summary.status_code == 200:
        anomaly_count = resp_summary.json().get("anomaly_count", 0)

    return {
        "total": total,
        "mine": mine,
        "today_count": today_count,
        "anomaly_count": anomaly_count,
    }


@st.cache_data(ttl=30)
def _fetch_recent_data() -> list[dict]:
    """取得最近 10 筆 data（依 recorded_at desc）。"""
    resp = client.get(
        "/data",
        params={"page": 1, "size": 10, "sort_by": "recorded_at", "sort_order": "desc"},
    )
    if resp.status_code == 200:
        return resp.json().get("items", [])
    return []


# ── Metric Cards ──────────────────────────────────────────────────────────────
with st.spinner("載入統計資料..."):
    try:
        stats = _fetch_data_stats()
    except Exception as exc:
        st.error(f"無法取得統計資料：{exc}")
        stats = {"total": "—", "mine": "—", "today_count": "—", "anomaly_count": "—"}

col1, col2, col3, col4 = st.columns(4)
col1.metric("總資料筆數", stats["total"])
col2.metric("我的資料", stats["mine"])
col3.metric("今日新增", stats["today_count"])
col4.metric(
    "異常筆數",
    stats["anomaly_count"],
    delta=None,
    delta_color="inverse" if isinstance(stats["anomaly_count"], int) and stats["anomaly_count"] > 0 else "off",
)

st.markdown("---")

# ── 最近 10 筆資料 ────────────────────────────────────────────────────────────
st.subheader("最近 10 筆資料")

with st.spinner("載入資料..."):
    try:
        recent_items = _fetch_recent_data()
    except Exception as exc:
        st.error(f"無法取得資料：{exc}")
        recent_items = []

if recent_items:
    df = pd.DataFrame(recent_items)
    # 選擇要顯示的欄位 + 重新命名
    display_cols = {
        "id": "ID",
        "title": "標題",
        "value": "數值",
        "category": "類別",
        "recorded_at": "記錄時間",
        "is_anomaly": "異常",
        "owner_id": "擁有者 ID",
    }
    available_cols = [c for c in display_cols if c in df.columns]
    df_display = df[available_cols].rename(columns=display_cols)

    # 將 is_anomaly bool 轉為易讀文字
    if "異常" in df_display.columns:
        df_display["異常"] = df_display["異常"].apply(lambda v: "⚠️ 是" if v else "正常")

    # 格式化時間
    if "記錄時間" in df_display.columns:
        df_display["記錄時間"] = pd.to_datetime(df_display["記錄時間"]).dt.strftime("%Y-%m-%d %H:%M")

    st.dataframe(df_display, use_container_width=True, hide_index=True)
else:
    st.info("目前尚無資料記錄。")

# ── 頁面底部：快速導航 ─────────────────────────────────────────────────────────
st.markdown("---")
nav_col1, nav_col2 = st.columns(2)
with nav_col1:
    if st.button("前往資料管理 →", use_container_width=True):
        st.switch_page("pages/2_📁_Data.py")
with nav_col2:
    if st.button("重新整理", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
