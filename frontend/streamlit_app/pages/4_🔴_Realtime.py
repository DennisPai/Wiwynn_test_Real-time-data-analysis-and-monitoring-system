"""
Realtime 頁面：即時資料串流 + 異常告警。

策略：直接訂閱 BE WebSocket `/ws/realtime`（spec 核心要求）。
     - run_ws_in_background(token, on_tick) 啟動背景 thread 持續收 tick
     - WS client 內 deque buffer（maxlen=60）保留滾動視窗
     - st_autorefresh 每秒 rerun 讀 buffer 並重繪
     - 異常點以紅色 marker 顯示，並在頁面頂部列出最近 5 筆告警

所有角色（admin/user/viewer）皆可使用，因為 WS auth 走 JWT query token
而不是 RBAC require_role。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from auth import current_role, current_user, logout, require_auth
from ws_client import run_ws_in_background

st.set_page_config(
    page_title="Realtime — 即時資料分析與監控系統",
    page_icon="🔴",
    layout="wide",
)

# 認證守衛
require_auth()

user = current_user()
role = current_role()

# 從 session_state 取得 JWT token（require_auth 已保證存在）
_token: str = st.session_state.get("token", "")

# ── 時間輔助函式 ───────────────────────────────────────────────────────────────

def format_ts(iso_str: str | None) -> str:
    """將後端 UTC ISO8601 字串轉換為台北時間並格式化。"""
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
    st.title("🔴 即時資料監控")
with col_user:
    st.markdown(
        f"**{user.get('display_name', '未知')}**  \n"
        f"角色：`{role}`",
    )
    if st.button("登出", key="logout_btn", use_container_width=True):
        logout()
        st.switch_page("Home.py")

# ── 啟動 WebSocket 背景 thread（每個 rerun 都呼叫；run_ws_in_background 內部
#     用 @st.cache_resource 確保只啟動一次，重複呼叫直接拿到既有 client）─────
ws_client = run_ws_in_background(_token, on_tick=lambda _tick: None)

# ── 自動刷新（每 1000 ms = 1 秒）────────────────────────────────────────────
refresh_count = st_autorefresh(interval=1000, key="realtime_autorefresh")

# ── session_state 初始化 ──────────────────────────────────────────────────────
if "rt_category_filter" not in st.session_state:
    st.session_state["rt_category_filter"] = "（全部）"

st.markdown("---")

# ── 控制列：連線狀態 + 類別 filter ────────────────────────────────────────────
ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 2, 1])

with ctrl_col1:
    # WebSocket 連線狀態指示燈
    if ws_client.is_connected():
        st.success("● WS 串流中")
    else:
        st.warning("○ WS 連線中...")

with ctrl_col2:
    # 類別清單對齊 BE realtime_service.py 的 SIMULATOR_CATEGORIES
    _KNOWN_CATEGORIES = ["（全部）", "temperature", "humidity", "pressure", "voltage", "cpu_usage"]
    f_category_label = st.selectbox(
        "類別篩選",
        _KNOWN_CATEGORIES,
        index=_KNOWN_CATEGORIES.index(st.session_state.get("rt_category_filter", "（全部）")),
        key="rt_cat_selector",
    )
    st.session_state["rt_category_filter"] = f_category_label
    f_category: str | None = None if f_category_label == "（全部）" else f_category_label

with ctrl_col3:
    if st.button("清空緩衝區", key="clear_buffer"):
        ws_client.clear()
        st.rerun()

# ── 從 WS client 讀 buffer ────────────────────────────────────────────────────

all_ticks: list[dict] = ws_client.get_buffer()
# 套用類別 filter
if f_category:
    buf_list = [t for t in all_ticks if t.get("category") == f_category]
else:
    buf_list = list(all_ticks)

# ── 頂部告警卡：最近 5 筆異常 ─────────────────────────────────────────────────

anomaly_ticks = [t for t in buf_list if t.get("is_anomaly")]
# 依 ts 降序取最近 5 筆
anomaly_ticks.sort(key=lambda x: x.get("ts", ""), reverse=True)
recent_anomalies = anomaly_ticks[:5]

if recent_anomalies:
    st.error(f"⚠️ 告警：偵測到 {len(anomaly_ticks)} 筆異常（顯示最近 5 筆）")
    alert_cols = st.columns(min(len(recent_anomalies), 5))
    for i, a_tick in enumerate(recent_anomalies):
        with alert_cols[i]:
            st.metric(
                label=f"{a_tick.get('category', '—')}",
                value=f"{float(a_tick.get('value', 0)):.2f}",
                delta=format_ts(a_tick.get("ts")),
                delta_color="off",
            )
else:
    st.success("✅ 目前無異常告警")

st.markdown("---")

# ── 即時折線圖 ─────────────────────────────────────────────────────────────────

st.subheader("即時資料串流（最新 60 點）")

if buf_list:
    df_rt = pd.DataFrame(buf_list)
    # 轉換時間戳（UTC → 台北）
    if "ts" in df_rt.columns:
        df_rt["ts_tw"] = pd.to_datetime(df_rt["ts"], utc=True).dt.tz_convert("Asia/Taipei")
    else:
        df_rt["ts_tw"] = pd.Series(dtype="object")

    df_rt["value_float"] = pd.to_numeric(df_rt.get("value", pd.Series()), errors="coerce")

    fig_rt = go.Figure()

    # 正常點（is_anomaly == False 或不存在）
    normal_df = df_rt[~df_rt.get("is_anomaly", pd.Series([False] * len(df_rt), dtype=bool)).fillna(False)]
    anomaly_df = df_rt[df_rt.get("is_anomaly", pd.Series([False] * len(df_rt), dtype=bool)).fillna(False)]

    # 主折線（全資料，使用連續線）
    fig_rt.add_trace(go.Scatter(
        x=df_rt["ts_tw"],
        y=df_rt["value_float"],
        mode="lines",
        name="數值",
        line={"color": "royalblue", "width": 2},
    ))

    # 正常點
    if not normal_df.empty:
        fig_rt.add_trace(go.Scatter(
            x=normal_df["ts_tw"],
            y=normal_df["value_float"],
            mode="markers",
            name="正常",
            marker={"color": "royalblue", "size": 6},
        ))

    # 異常點（紅色 x marker）
    if not anomaly_df.empty:
        fig_rt.add_trace(go.Scatter(
            x=anomaly_df["ts_tw"],
            y=anomaly_df["value_float"],
            mode="markers",
            name="異常",
            marker={"color": "red", "size": 12, "symbol": "x"},
        ))

    # 類別文字資訊
    category_label = f"（類別：{f_category}）" if f_category else "（全類別）"

    fig_rt.update_layout(
        title=f"即時資料 {category_label}",
        xaxis_title="時間（台北）",
        yaxis_title="數值",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 40, "r": 20, "t": 50, "b": 80},
        uirevision="realtime_chart",  # 保持縮放狀態不因 rerun 重置
    )
    st.plotly_chart(fig_rt, use_container_width=True)

    # ── 即時資料表格（最新 10 筆）─────────────────────────────────────────────
    st.subheader("最新 10 筆資料")
    recent_10 = buf_list[-10:][::-1]  # 倒序：最新在最上
    df_recent = pd.DataFrame(recent_10)

    if not df_recent.empty:
        rename_map = {
            "ts": "時間（台北）",
            "value": "數值",
            "category": "類別",
            "source": "來源",
            "is_anomaly": "異常",
        }
        available = [c for c in rename_map if c in df_recent.columns]
        df_display = df_recent[available].rename(columns=rename_map).copy()

        if "時間（台北）" in df_display.columns:
            df_display["時間（台北）"] = df_display["時間（台北）"].apply(format_ts)
        if "異常" in df_display.columns:
            df_display["異常"] = df_display["異常"].apply(lambda v: "⚠️ 是" if v else "正常")

        st.dataframe(df_display, use_container_width=True, hide_index=True)

else:
    st.info("尚未收到即時資料，等待伺服器推送...")
    st.caption("系統模擬器每 1 秒生成一筆資料，請稍候...")

# ── 頁面底部資訊 ──────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(f"自動刷新次數：{refresh_count} | 緩衝區：{len(buf_list)} 筆 | 最後更新：{format_ts(datetime.now(tz=timezone.utc).isoformat())}")
