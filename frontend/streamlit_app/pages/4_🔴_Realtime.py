"""
Realtime 頁面：即時資料串流 + 異常告警。

策略：以輪詢 /admin/realtime-history 為主（避免 Streamlit 非同步 WS 踩雷）。
     - 每秒透過 streamlit-autorefresh 觸發 rerun
     - 呼叫 GET /admin/realtime-history 取最新 60 筆
     - 用 st.session_state.realtime_buffer（deque maxlen=60）維持滾動視窗
     - 異常點以紅色 marker 顯示，並在頁面頂部列出最近 5 筆告警

類別 filter（可選）：由使用者在側邊欄選擇，只顯示特定類別。

時間均以 UTC 存入 buffer，顯示時 tz_convert("Asia/Taipei")。
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from api_client import APIClient
from auth import current_role, current_user, logout, require_auth

st.set_page_config(
    page_title="Realtime — 即時資料分析與監控系統",
    page_icon="🔴",
    layout="wide",
)

# 認證守衛
require_auth()

client = APIClient()
user = current_user()
role = current_role()

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

# ── 自動刷新（每 1000 ms = 1 秒）────────────────────────────────────────────
# st_autorefresh 每隔 interval ms 觸發一次 Streamlit rerun
refresh_count = st_autorefresh(interval=1000, key="realtime_autorefresh")

# ── session_state 初始化 ──────────────────────────────────────────────────────
if "realtime_buffer" not in st.session_state:
    st.session_state["realtime_buffer"] = deque(maxlen=60)

if "rt_category_filter" not in st.session_state:
    st.session_state["rt_category_filter"] = "（全部）"

st.markdown("---")

# ── 控制列：連線狀態 + 類別 filter ────────────────────────────────────────────
ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 2, 1])

with ctrl_col1:
    # 連線狀態指示燈（polling 方式，只要能取到資料就算「連線中」）
    if st.session_state.get("rt_last_fetch_ok", False):
        st.success("● 串流中")
    else:
        st.warning("○ 等待資料...")

with ctrl_col2:
    _KNOWN_CATEGORIES = ["（全部）", "temperature", "humidity", "pressure", "vibration", "power"]
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
        st.session_state["realtime_buffer"] = deque(maxlen=60)
        st.session_state["rt_last_fetch_ok"] = False
        st.rerun()

# ── 取最新 60 筆 realtime 資料（polling） ─────────────────────────────────────

def _fetch_realtime(category: str | None) -> list[dict]:
    """
    呼叫 GET /admin/realtime-history，取最近 60 筆。
    非 admin 角色沒有 /admin/ 權限，改用 WebSocket 模式指示。
    """
    now_utc = datetime.now(tz=timezone.utc)
    # 只取最近 2 分鐘的資料，確保即時性
    since = now_utc - timedelta(minutes=2)

    params: dict = {
        "date_from": since.isoformat(),
        "date_to": now_utc.isoformat(),
        "page": 1,
        "size": 60,
    }
    if category:
        params["category"] = category

    try:
        resp = client.get("/admin/realtime-history", params=params)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            # 依 ts 升序排列（舊 → 新）
            items.sort(key=lambda x: x.get("ts", ""))
            return items
        elif resp.status_code == 403:
            # 非 admin：回傳特殊標記
            return [{"_no_permission": True}]
    except Exception:
        pass
    return []


# ── 執行 polling 並更新 buffer ────────────────────────────────────────────────

new_ticks = _fetch_realtime(f_category)

if new_ticks and new_ticks[0].get("_no_permission"):
    # 非 admin 使用者：顯示提示，無法使用 realtime-history API
    st.warning(
        "您的角色（`viewer` 或 `user`）沒有存取 `/admin/realtime-history` 的權限。  \n"
        "請聯絡管理員或使用 Admin 帳號登入以查看即時資料。"
    )
    st.stop()

elif new_ticks:
    st.session_state["rt_last_fetch_ok"] = True
    # 只加入尚未在 buffer 中的資料（依 ts 去重）
    buf: deque = st.session_state["realtime_buffer"]
    existing_ts = {item.get("ts") for item in buf}
    for tick in new_ticks:
        if tick.get("ts") not in existing_ts:
            buf.append(tick)
            existing_ts.add(tick.get("ts"))
else:
    # 取不到新資料：保持 buffer 現有內容
    pass

# ── 讀取 buffer 準備繪圖 ──────────────────────────────────────────────────────

buf_list: list[dict] = list(st.session_state["realtime_buffer"])

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
