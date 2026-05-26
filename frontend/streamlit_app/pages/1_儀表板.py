"""
儀表板頁面：系統狀態標頭 + 統計 metric cards + 最近資料 tabs + 帳號設定。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from api_client import APIClient
from auth import current_role, current_user, logout, require_auth

st.set_page_config(
    page_title="儀表板 — 即時資料分析與監控系統",
    page_icon=None,
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
    st.title("儀表板")
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

# ── D2-4 System status header ─────────────────────────────────────────────────
@st.cache_data(ttl=10)
def _fetch_realtime_history_for_status() -> list[dict]:
    """取得最近 60 秒即時資料供 system status header 使用。"""
    resp = client.get("/realtime/history", params={"seconds": 60})
    if resp.status_code == 200:
        return resp.json().get("snapshots", [])
    return []


def _count_active_alerts(snapshots: list[dict]) -> int:
    """計算最近 60 秒快照中有異常 flag 的數量。"""
    count = 0
    for snap in snapshots:
        flags = snap.get("anomaly_flags", {})
        if any(flags.values()):
            count += 1
    return count


try:
    rt_snapshots = _fetch_realtime_history_for_status()
    active_alert_count = _count_active_alerts(rt_snapshots)
    last_snap = rt_snapshots[-1] if rt_snapshots else None
    last_update_str = ""
    if last_snap:
        try:
            ts = pd.to_datetime(last_snap.get("ts", ""), utc=True, format="ISO8601").tz_convert("Asia/Taipei")
            last_update_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            last_update_str = str(last_snap.get("ts", ""))
    ws_connected = len(rt_snapshots) > 0
except Exception:
    rt_snapshots = []
    active_alert_count = 0
    last_update_str = ""
    ws_connected = False

status_col1, status_col2, status_col3 = st.columns(3)
with status_col1:
    if ws_connected:
        st.markdown("**串流狀態：● 連線中**")
    else:
        st.markdown("**串流狀態：○ 重連中**")
with status_col2:
    st.markdown(f"**最後更新：{last_update_str if last_update_str else '—'}**")
with status_col3:
    if active_alert_count > 0:
        st.error(f"活躍告警：{active_alert_count} 筆")
    else:
        st.success("活躍告警：無")

st.markdown("---")

# ── D2-5: Metric cards 改打 /analytics/unified-summary ────────────────────────
@st.cache_data(ttl=30)
def _fetch_unified_summary() -> dict:
    """從 /analytics/unified-summary 取得統一摘要統計。"""
    now_utc = datetime.now(tz=timezone.utc)
    params = {
        "date_from": (now_utc - timedelta(days=30)).isoformat(),
        "date_to": now_utc.isoformat(),
        "source": "both",
    }
    resp = client.get("/analytics/unified-summary", params=params)
    if resp.status_code == 200:
        return resp.json()
    return {}


@st.cache_data(ttl=30)
def _fetch_recent_realtime(n: int = 10) -> list[dict]:
    """取得最近 N 筆即時資料快照。"""
    resp = client.get("/realtime/history", params={"seconds": 3600})
    if resp.status_code == 200:
        snaps = resp.json().get("snapshots", [])
        return snaps[-n:][::-1]
    return []


@st.cache_data(ttl=30)
def _fetch_recent_records(n: int = 10) -> list[dict]:
    """取得最近 N 筆錄入資料。"""
    resp = client.get(
        "/data",
        params={"page": 1, "size": n, "sort_by": "recorded_at", "sort_order": "desc"},
    )
    if resp.status_code == 200:
        return resp.json().get("items", [])
    return []


with st.spinner("載入統計資料..."):
    try:
        unified = _fetch_unified_summary()
    except Exception as exc:
        st.error(f"無法取得統計資料：{exc}")
        unified = {}

# 顯示 metric cards
combined = unified.get("combined", {})
realtime_info = unified.get("realtime", {})
records_info = unified.get("records", {})

col1, col2, col3, col4 = st.columns(4)
col1.metric("合計資料筆數", combined.get("total", "—"))
col2.metric("即時資料筆數", realtime_info.get("total", "—"))
col3.metric("錄入資料筆數", records_info.get("total", "—"))
col4.metric(
    "異常筆數（合計）",
    combined.get("anomaly_count", "—"),
    delta_color="inverse",
)

st.markdown("---")

# ── D2-6: 最近 10 筆改 tabs（即時/錄入）─────────────────────────────────────────
st.subheader("最近資料")

tab_realtime, tab_records = st.tabs(["即時", "錄入"])

with tab_realtime:
    with st.spinner("載入即時資料..."):
        try:
            recent_rt = _fetch_recent_realtime(10)
        except Exception as exc:
            st.error(f"無法取得即時資料：{exc}")
            recent_rt = []

    if recent_rt:
        df_rt = pd.DataFrame(recent_rt)
        display_cols_rt = {
            "ts": "時間（台北）",
            "temperature": "溫度(C)",
            "humidity": "濕度(%)",
            "pressure": "氣壓(hPa)",
            "voltage": "電壓(V)",
            "cpu_usage": "CPU(%)",
        }
        available_rt = [c for c in display_cols_rt if c in df_rt.columns]
        df_rt_show = df_rt[available_rt].rename(columns=display_cols_rt).copy()
        if "時間（台北）" in df_rt_show.columns:
            df_rt_show["時間（台北）"] = pd.to_datetime(
                df_rt_show["時間（台北）"], utc=True, format="ISO8601"
            ).dt.tz_convert("Asia/Taipei").dt.strftime("%Y-%m-%d %H:%M:%S")
        st.dataframe(df_rt_show, use_container_width=True, hide_index=True)
    else:
        st.info("目前尚無即時資料記錄。")

with tab_records:
    with st.spinner("載入錄入資料..."):
        try:
            recent_rec = _fetch_recent_records(10)
        except Exception as exc:
            st.error(f"無法取得錄入資料：{exc}")
            recent_rec = []

    if recent_rec:
        df_rec = pd.DataFrame(recent_rec)
        display_cols_rec = {
            "id": "ID",
            "title": "標題",
            "value": "數值",
            "category": "類別",
            "recorded_at": "記錄時間",
            "is_anomaly": "異常",
        }
        available_rec = [c for c in display_cols_rec if c in df_rec.columns]
        df_rec_show = df_rec[available_rec].rename(columns=display_cols_rec).copy()
        if "異常" in df_rec_show.columns:
            df_rec_show["異常"] = df_rec_show["異常"].apply(lambda v: "是" if v else "否")
        if "記錄時間" in df_rec_show.columns:
            df_rec_show["記錄時間"] = pd.to_datetime(df_rec_show["記錄時間"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df_rec_show, use_container_width=True, hide_index=True)
    else:
        st.info("目前尚無錄入資料記錄。")

# ── D2-8: 帳號設定 expander（user/viewer 改自己密碼）────────────────────────────
st.markdown("---")
with st.expander("帳號設定"):
    st.subheader("修改密碼")
    st.caption("請輸入舊密碼以驗證身份，再設定新密碼（至少 8 個字元）。")

    with st.form("change_password_form_dashboard"):
        cp_old = st.text_input("舊密碼", type="password", key="dash_cp_old")
        cp_new = st.text_input("新密碼（至少 8 個字元）", type="password", key="dash_cp_new")
        cp_new2 = st.text_input("確認新密碼", type="password", key="dash_cp_new2")
        cp_submitted = st.form_submit_button("修改密碼", use_container_width=True)

    if cp_submitted:
        errors: list[str] = []
        if not cp_old:
            errors.append("請輸入舊密碼。")
        if not cp_new:
            errors.append("請輸入新密碼。")
        elif len(cp_new) < 8:
            errors.append("新密碼至少需要 8 個字元。")
        if cp_new != cp_new2:
            errors.append("兩次新密碼輸入不一致。")

        if errors:
            for err in errors:
                st.error(err)
        else:
            uid = user.get("id")
            if uid:
                resp = client.patch(
                    f"/users/{uid}/password",
                    json={"new_password": cp_new, "old_password": cp_old},
                )
                if resp.status_code == 200:
                    st.success("密碼已成功修改。")
                else:
                    try:
                        detail = resp.json().get("detail", "修改失敗")
                    except Exception:
                        detail = f"修改失敗（HTTP {resp.status_code}）"
                    st.error(f"修改失敗：{detail}")
            else:
                st.error("無法取得使用者 ID，請重新登入。")

# ── 頁面底部：重新整理 ───────────────────────────────────────────────────────────
st.markdown("---")
if st.button("重新整理", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
