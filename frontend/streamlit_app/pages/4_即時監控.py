"""
即時監控頁面：頁面進入時 REST history 預載 + WS subscribe + 告警卡 delta + 60 筆表格 + 淡粉紅。

策略（Q2 Snapshot + Delta）：
  1. 進頁面先 REST /realtime/history?seconds=60 預載 buffer（不再「點進去才累積」）
  2. WS background thread 訂閱後續每秒新 wide snapshot
  3. st_autorefresh 每秒 rerun 讀 buffer 重繪

所有角色（admin/user/viewer）皆可使用。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from api_client import APIClient
from auth import current_role, current_user, logout, require_auth
from ws_client import run_ws_in_background

st.set_page_config(
    page_title="即時監控 — 即時資料分析與監控系統",
    page_icon=None,
    layout="wide",
)

# 認證守衛
require_auth()

client = APIClient()
user = current_user()
role = current_role()

_token: str = st.session_state.get("token", "")

# ── D5-4: metric_zh mapping + 顏色 ───────────────────────────────────────────
_METRIC_KEYS = ["temperature", "humidity", "pressure", "voltage", "cpu_usage"]
_METRIC_ZH = {
    "temperature": "溫度(C)",
    "humidity": "濕度(%)",
    "pressure": "氣壓(hPa)",
    "voltage": "電壓(V)",
    "cpu_usage": "CPU(%)",
}
_METRIC_COLORS = {
    "temperature": "royalblue",
    "humidity": "green",
    "pressure": "orange",
    "voltage": "purple",
    "cpu_usage": "teal",
}
# 閾值（從 simulator profile；正式環境可改打 /admin/settings）
_METRIC_HIGH_THRESHOLD = {
    "temperature": 100.0,
    "humidity": 95.0,
    "pressure": 1080.0,
    "voltage": 22.0,
    "cpu_usage": 90.0,
}
_METRIC_LOW_THRESHOLD = {
    "temperature": -10.0,
    "humidity": 5.0,
    "pressure": 920.0,
    "voltage": 2.0,
    "cpu_usage": 0.0,
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
    st.title("即時監控")
with col_user:
    st.markdown(
        f"**{user.get('display_name', '未知')}**  \n"
        f"角色：`{role}`",
    )
    if st.button("登出", key="logout_btn", use_container_width=True):
        logout()
        st.switch_page("Home.py")

# ── D5-3: 頁面進入時 REST /realtime/history?seconds=60 預載 buffer（Q2）────────
ws_client = run_ws_in_background(_token, on_tick=lambda _tick: None)

if not st.session_state.get("rt_history_loaded"):
    try:
        resp_hist = client.get("/realtime/history", params={"seconds": 60})
        if resp_hist.status_code == 200:
            for snap in resp_hist.json().get("snapshots", []):
                ws_client.push_tick(snap)
    except Exception:
        pass
    st.session_state["rt_history_loaded"] = True

# ── 自動刷新（每 1000 ms = 1 秒）────────────────────────────────────────────
refresh_count = st_autorefresh(interval=1000, key="realtime_autorefresh")

st.markdown("---")

# ── D5-5: System status header（連線狀態 + last update + active alerts）────────
all_ticks: list[dict] = ws_client.get_buffer()

# 計算 active alerts（最近 5 筆 snapshot 中有 anomaly flag 的 metrics）
recent_5_snaps = all_ticks[-5:] if len(all_ticks) >= 5 else all_ticks

active_alert_metrics: list[tuple[str, float, dict]] = []
for snap in recent_5_snaps:
    flags = snap.get("anomaly_flags", {})
    for metric_key in _METRIC_KEYS:
        if flags.get(metric_key, False):
            value = snap.get(metric_key, 0.0)
            if value is not None:
                active_alert_metrics.append((metric_key, float(value), snap))

last_snap = all_ticks[-1] if all_ticks else None
last_update_str = format_ts(last_snap.get("ts") if last_snap else None)

status_col1, status_col2, status_col3 = st.columns(3)
with status_col1:
    if ws_client.is_connected():
        st.markdown("**串流狀態：● 連線中**")
    else:
        st.markdown("**串流狀態：○ 重連中**")
with status_col2:
    st.markdown(f"**最後更新：{last_update_str if last_update_str else '—'}**")
with status_col3:
    if active_alert_metrics:
        st.error(f"活躍告警：{len(active_alert_metrics)} 個 metric 異常")
    else:
        st.success("活躍告警：無")

# ── D5-10: 移除類別 selectbox，改「顯示哪些線」multiselect ──────────────────────
ctrl_col1, ctrl_col2 = st.columns([2, 2])
with ctrl_col1:
    selected_metrics = st.multiselect(
        "顯示哪些線",
        options=_METRIC_KEYS,
        default=_METRIC_KEYS,
        format_func=lambda m: _METRIC_ZH.get(m, m),
        key="rt_metrics_select",
    )
with ctrl_col2:
    if st.button("清空緩衝區", key="clear_buffer"):
        ws_client.clear()
        st.session_state.pop("rt_history_loaded", None)
        st.rerun()

st.markdown("---")

# ── D5-6: 告警卡（最近 5 筆 snapshot 有異常 + delta 數值）Q4 ──────────────────────
# 去重：每個 metric 只取最新一筆
seen_metrics: set[str] = set()
dedup_alert_metrics: list[tuple[str, float, dict]] = []
for snap in reversed(recent_5_snaps):
    flags = snap.get("anomaly_flags", {})
    for metric_key in _METRIC_KEYS:
        if flags.get(metric_key, False) and metric_key not in seen_metrics:
            value = snap.get(metric_key, 0.0)
            if value is not None:
                dedup_alert_metrics.append((metric_key, float(value), snap))
                seen_metrics.add(metric_key)

if dedup_alert_metrics:
    total_anom_count = len([
        1 for snap in all_ticks
        for mk in _METRIC_KEYS
        if snap.get("anomaly_flags", {}).get(mk, False)
    ])
    st.error(f"告警：偵測到異常（最近 5 筆快照共 {len(dedup_alert_metrics)} 個 metric 異常）")
    alert_cols = st.columns(min(len(dedup_alert_metrics), 5))
    for i, (metric_key, value, snap) in enumerate(dedup_alert_metrics[:5]):
        high_thr = _METRIC_HIGH_THRESHOLD.get(metric_key, 100.0)
        low_thr = _METRIC_LOW_THRESHOLD.get(metric_key, 0.0)
        threshold = high_thr if value > high_thr else low_thr
        delta_val = value - threshold
        sign = "+" if delta_val > 0 else ""
        with alert_cols[i]:
            st.metric(
                label=f"{_METRIC_ZH.get(metric_key, metric_key)} 異常",
                value=f"{value:.2f}",
                delta=f"{sign}{delta_val:.2f}（閾值 {threshold}）",
                delta_color="inverse",
            )
else:
    st.success("目前無異常告警")

st.markdown("---")

# ── D5-7: 折線圖改 5 條線 + 異常點 circle-open red marker ─────────────────────
st.subheader("即時資料串流（最新 60 點）")

if all_ticks:
    df_rt = pd.DataFrame(all_ticks)
    # 轉換時間戳
    if "ts" in df_rt.columns:
        df_rt["ts_tw"] = pd.to_datetime(df_rt["ts"], utc=True, format="ISO8601").dt.tz_convert("Asia/Taipei")
    else:
        df_rt["ts_tw"] = pd.Series(dtype="object")

    fig_rt = go.Figure()

    # 每 metric 一條線 + 異常點 circle-open red marker
    metrics_to_show = selected_metrics if selected_metrics else _METRIC_KEYS
    for metric_key in metrics_to_show:
        if metric_key not in df_rt.columns:
            continue
        df_rt[f"{metric_key}_float"] = pd.to_numeric(df_rt[metric_key], errors="coerce")

        # 正常折線
        fig_rt.add_trace(go.Scatter(
            x=df_rt["ts_tw"],
            y=df_rt[f"{metric_key}_float"],
            mode="lines",
            name=_METRIC_ZH.get(metric_key, metric_key),
            line={"color": _METRIC_COLORS.get(metric_key, "gray"), "width": 2},
        ))

        # 異常點：circle-open red marker
        if "anomaly_flags" in df_rt.columns:
            def _is_anom(row: pd.Series, mk: str = metric_key) -> bool:
                flags = row.get("anomaly_flags", {})
                if isinstance(flags, dict):
                    return bool(flags.get(mk, False))
                return False
            anom_mask = df_rt.apply(_is_anom, axis=1)
            anom_df = df_rt[anom_mask]
            if not anom_df.empty:
                fig_rt.add_trace(go.Scatter(
                    x=anom_df["ts_tw"],
                    y=anom_df[f"{metric_key}_float"],
                    mode="markers",
                    name=f"{_METRIC_ZH.get(metric_key, metric_key)} 異常",
                    marker={
                        "color": "red",
                        "size": 12,
                        "symbol": "circle-open",
                        "line": {"width": 2, "color": "red"},
                    },
                    showlegend=True,
                ))

    fig_rt.update_layout(
        title="即時資料（最新 60 點）",
        xaxis_title="時間（台北）",
        yaxis_title="數值",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 40, "r": 20, "t": 50, "b": 80},
        uirevision="realtime_chart",
    )
    st.plotly_chart(fig_rt, use_container_width=True)

    # ── D5-8 & D5-9: 表格 60 列 + Pandas Styler 淡粉紅 row + 紅字 cell ──────────
    st.subheader("最新 60 筆資料")

    # 取最新 60 筆倒序顯示（最新在最上）
    recent_60 = all_ticks[-60:][::-1]
    df_display_src = pd.DataFrame(recent_60)

    if not df_display_src.empty:
        # 建立展示 DataFrame
        display_rows = []
        for _, row in df_display_src.iterrows():
            ts_str = format_ts(row.get("ts"))
            flags = row.get("anomaly_flags", {})
            if not isinstance(flags, dict):
                flags = {}
            display_rows.append({
                "時間（台北）": ts_str,
                "溫度(C)": row.get("temperature"),
                "濕度(%)": row.get("humidity"),
                "氣壓(hPa)": row.get("pressure"),
                "電壓(V)": row.get("voltage"),
                "CPU(%)": row.get("cpu_usage"),
                "_anom_temperature": flags.get("temperature", False),
                "_anom_humidity": flags.get("humidity", False),
                "_anom_pressure": flags.get("pressure", False),
                "_anom_voltage": flags.get("voltage", False),
                "_anom_cpu_usage": flags.get("cpu_usage", False),
            })

        df_display = pd.DataFrame(display_rows)

        # 分離 anomaly 欄位用於 styling
        anom_cols = [c for c in df_display.columns if c.startswith("_anom_")]
        metric_display_cols = ["溫度(C)", "濕度(%)", "氣壓(hPa)", "電壓(V)", "CPU(%)"]
        anom_col_map = {
            "溫度(C)": "_anom_temperature",
            "濕度(%)": "_anom_humidity",
            "氣壓(hPa)": "_anom_pressure",
            "電壓(V)": "_anom_voltage",
            "CPU(%)": "_anom_cpu_usage",
        }

        df_visible = df_display.drop(columns=anom_cols)

        # Pandas Styler：淡粉紅 row 背景
        def _style_row(row: pd.Series) -> list[str]:
            idx = row.name
            if idx >= len(df_display):
                return [""] * len(row)
            has_any_anom = any(
                df_display.iloc[idx].get(ac, False)
                for ac in anom_cols
            )
            if has_any_anom:
                return ["background-color: #fde8e8"] * len(row)
            return [""] * len(row)

        # Pandas Styler：紅字 cell（按 metric 欄位）
        def _style_cell(val: object, col_name: str, df_src: pd.DataFrame) -> str:
            # col_name 是已重命名的顯示名稱；需找到對應 row idx
            # 這個 function 用於 applymap，所以要用 df_visible 的 loc
            return ""  # placeholder，用 apply 版本處理

        def _style_metric_col(col_series: pd.Series, col_name: str) -> list[str]:
            """對單一 metric 欄位，依異常 flag 套紅字。"""
            anom_col = anom_col_map.get(col_name)
            styles = []
            for idx in range(len(col_series)):
                if anom_col and idx < len(df_display):
                    is_anom = df_display.iloc[idx].get(anom_col, False)
                    if is_anom:
                        styles.append("color: #c0392b; font-weight: bold")
                    else:
                        styles.append("")
                else:
                    styles.append("")
            return styles

        try:
            styled = df_visible.style.apply(_style_row, axis=1)
            for m_col in metric_display_cols:
                if m_col in df_visible.columns:
                    styled = styled.apply(
                        lambda s, c=m_col: _style_metric_col(s, c),
                        subset=[m_col],
                        axis=0,
                    )
            styled = styled.format({
                c: "{:.2f}" for c in metric_display_cols if c in df_visible.columns
            })
            st.dataframe(styled, use_container_width=True, hide_index=True)
        except Exception:
            # fallback：無 styler
            st.dataframe(df_visible, use_container_width=True, hide_index=True)

else:
    st.info("尚未收到即時資料，等待伺服器推送...")
    st.caption("系統模擬器每 1 秒生成一筆資料，請稍候...")

# ── 頁面底部資訊 ──────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"自動刷新次數：{refresh_count} | "
    f"緩衝區：{len(all_ticks)} 筆 | "
    f"最後更新：{format_ts(datetime.now(tz=timezone.utc).isoformat())}"
)
