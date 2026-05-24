"""
Admin 頁面：系統管理（僅 admin 角色可存取）。

5 個 tab：
  1. 使用者列表    — GET /users，PATCH /users/{id}（role / is_active）
  2. 系統日誌      — GET /admin/logs，篩選 + DataFrame
  3. DB 狀態       — GET /admin/db-status，pool 卡 + tables 表格
  4. 即時資料歷史  — GET /admin/realtime-history，分頁 DataFrame + 圖表
  5. 系統設定      — GET /admin/settings，每 setting 一個 number_input，PATCH 即時生效

非 admin → st.error + st.stop()。
時間均 tz_convert("Asia/Taipei") 後顯示。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from api_client import APIClient
from auth import current_role, current_user, logout, require_auth

st.set_page_config(
    page_title="Admin — 即時資料分析與監控系統",
    page_icon="⚙️",
    layout="wide",
)

# 認證守衛
require_auth()

client = APIClient()
user = current_user()
role = current_role()

# ── 角色檢查：非 admin 直接擋住 ──────────────────────────────────────────────
if role != "admin":
    st.error(f"存取拒絕：此頁面僅限 **admin** 角色。您目前的角色為 `{role}`。")
    st.info("如需管理功能，請洽系統管理員提升權限，或改以 admin 帳號登入。")
    st.stop()

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
    st.title("⚙️ 系統管理")
with col_user:
    st.markdown(
        f"**{user.get('display_name', '未知')}**  \n"
        f"角色：`{role}`",
    )
    if st.button("登出", key="logout_btn", use_container_width=True):
        logout()
        st.switch_page("Home.py")

st.markdown("---")

# ── 5 個 Tab ──────────────────────────────────────────────────────────────────
tab_users, tab_logs, tab_db, tab_rt_hist, tab_settings = st.tabs([
    "👥 使用者列表",
    "📋 系統日誌",
    "🗄️ DB 狀態",
    "📡 即時資料歷史",
    "🔧 系統設定",
])


# ════════════════════════════════════════════════════════════════════════════════
# Tab 1：使用者列表
# ════════════════════════════════════════════════════════════════════════════════

with tab_users:
    st.subheader("使用者管理")

    # 分頁控制
    u_col1, u_col2 = st.columns([1, 3])
    with u_col1:
        u_page_size = st.selectbox("每頁筆數", [10, 20, 50], index=0, key="u_page_size")
    with u_col2:
        u_page = st.number_input("頁碼", min_value=1, value=1, step=1, key="u_page_num")

    u_role_filter_label = st.selectbox(
        "角色篩選",
        ["（全部）", "admin", "user", "viewer"],
        index=0,
        key="u_role_filter",
    )
    u_role_filter = None if u_role_filter_label == "（全部）" else u_role_filter_label

    # 取得使用者列表
    @st.cache_data(ttl=15)
    def _fetch_users(page: int, size: int, role_filter: str | None) -> tuple[list[dict], int, int]:
        params: dict = {"page": page, "size": size}
        if role_filter:
            params["role"] = role_filter
        resp = client.get("/users", params=params)
        if resp.status_code == 200:
            body = resp.json()
            return body.get("items", []), body.get("total", 0), body.get("pages", 1)
        return [], 0, 1

    with st.spinner("載入使用者列表..."):
        try:
            u_items, u_total, u_pages = _fetch_users(int(u_page), int(u_page_size), u_role_filter)
        except Exception as exc:
            st.error(f"無法取得使用者列表：{exc}")
            u_items, u_total, u_pages = [], 0, 1

    st.markdown(f"**共 {u_total} 筆，第 {int(u_page)}/{u_pages} 頁**")

    if u_items:
        # 顯示總覽 DataFrame
        df_u = pd.DataFrame(u_items)
        display_map = {
            "id": "ID",
            "email": "Email",
            "display_name": "顯示名稱",
            "role": "角色",
            "is_active": "啟用",
            "created_at": "建立時間",
        }
        available = [c for c in display_map if c in df_u.columns]
        df_u_show = df_u[available].rename(columns=display_map).copy()
        if "啟用" in df_u_show.columns:
            df_u_show["啟用"] = df_u_show["啟用"].apply(lambda v: "✅" if v else "❌")
        if "建立時間" in df_u_show.columns:
            df_u_show["建立時間"] = df_u_show["建立時間"].apply(format_ts)
        st.dataframe(df_u_show, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("編輯使用者")

        # 選擇使用者
        user_options = {f"[{u['id']}] {u.get('email', '')} ({u.get('role', '')})": u for u in u_items}
        selected_label = st.selectbox("選擇使用者", list(user_options.keys()), key="u_edit_select")
        selected_user = user_options.get(selected_label)

        if selected_user:
            edit_col1, edit_col2 = st.columns(2)
            with edit_col1:
                new_role = st.selectbox(
                    "角色",
                    ["admin", "user", "viewer"],
                    index=["admin", "user", "viewer"].index(selected_user.get("role", "user")),
                    key="u_edit_role",
                )
            with edit_col2:
                new_is_active = st.checkbox(
                    "啟用帳號",
                    value=bool(selected_user.get("is_active", True)),
                    key="u_edit_active",
                )

            if st.button("更新使用者", key="u_edit_btn", type="primary"):
                patch_payload: dict = {}
                if new_role != selected_user.get("role"):
                    patch_payload["role"] = new_role
                if new_is_active != bool(selected_user.get("is_active", True)):
                    patch_payload["is_active"] = new_is_active

                if patch_payload:
                    resp = client.patch(f"/users/{selected_user['id']}", json=patch_payload)
                    if resp.status_code == 200:
                        st.success("使用者資料已更新。")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        try:
                            detail = resp.json().get("detail", "更新失敗")
                        except Exception:
                            detail = f"更新失敗（HTTP {resp.status_code}）"
                        st.error(f"更新失敗：{detail}")
                else:
                    st.info("沒有任何變更。")
    else:
        st.info("目前沒有符合條件的使用者。")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 2：系統日誌
# ════════════════════════════════════════════════════════════════════════════════

with tab_logs:
    st.subheader("稽核日誌")

    # 篩選條件
    with st.expander("🔍 篩選條件", expanded=True):
        log_col1, log_col2, log_col3 = st.columns(3)
        with log_col1:
            log_page_size = st.selectbox("每頁筆數", [20, 50, 100], index=0, key="log_size")
            log_page = st.number_input("頁碼", min_value=1, value=1, step=1, key="log_page")
        with log_col2:
            log_user_id = st.text_input("使用者 ID（選填）", placeholder="留空表示全部", key="log_uid")
            log_action = st.text_input("動作關鍵字（選填）", placeholder="例如：login, create", key="log_action")
        with log_col3:
            now_utc = datetime.now(tz=timezone.utc)
            log_date_from = st.date_input(
                "起始日期",
                value=(now_utc - timedelta(days=7)).date(),
                key="log_date_from",
            )
            log_date_to = st.date_input(
                "結束日期",
                value=now_utc.date(),
                key="log_date_to",
            )

    # 取得日誌
    @st.cache_data(ttl=15)
    def _fetch_logs(
        page: int, size: int, user_id: str | None,
        action: str | None, date_from: str | None, date_to: str | None,
    ) -> tuple[list[dict], int, int]:
        params: dict = {"page": page, "size": size}
        if user_id:
            try:
                params["user_id"] = int(user_id)
            except ValueError:
                pass
        if action:
            params["action"] = action
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        resp = client.get("/admin/logs", params=params)
        if resp.status_code == 200:
            body = resp.json()
            return body.get("items", []), body.get("total", 0), body.get("pages", 1)
        return [], 0, 1

    with st.spinner("載入系統日誌..."):
        try:
            log_items, log_total, log_pages = _fetch_logs(
                page=int(log_page),
                size=int(log_page_size),
                user_id=log_user_id.strip() if log_user_id.strip() else None,
                action=log_action.strip() if log_action.strip() else None,
                date_from=log_date_from.isoformat() + "T00:00:00Z" if log_date_from else None,
                date_to=log_date_to.isoformat() + "T23:59:59Z" if log_date_to else None,
            )
        except Exception as exc:
            st.error(f"無法取得系統日誌：{exc}")
            log_items, log_total, log_pages = [], 0, 1

    st.markdown(f"**共 {log_total} 筆，第 {int(log_page)}/{log_pages} 頁**")

    if log_items:
        df_logs = pd.DataFrame(log_items)
        rename_map = {
            "id": "ID",
            "user_id": "使用者 ID",
            "action": "動作",
            "target_type": "目標類型",
            "target_id": "目標 ID",
            "ts": "時間（台北）",
        }
        available = [c for c in rename_map if c in df_logs.columns]
        df_logs_show = df_logs[available].rename(columns=rename_map).copy()
        if "時間（台北）" in df_logs_show.columns:
            df_logs_show["時間（台北）"] = df_logs_show["時間（台北）"].apply(format_ts)
        st.dataframe(df_logs_show, use_container_width=True, hide_index=True)

        # metadata 展開
        if "metadata" in df_logs.columns:
            with st.expander("查看 metadata 詳情"):
                for item in log_items[:10]:
                    if item.get("metadata"):
                        st.json(item["metadata"])
    else:
        st.info("查詢區間內沒有日誌記錄。")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 3：DB 狀態
# ════════════════════════════════════════════════════════════════════════════════

with tab_db:
    st.subheader("資料庫狀態")

    if st.button("🔄 重新整理 DB 狀態", key="refresh_db"):
        st.cache_data.clear()

    @st.cache_data(ttl=10)
    def _fetch_db_status() -> dict:
        resp = client.get("/admin/db-status")
        if resp.status_code == 200:
            return resp.json()
        return {}

    with st.spinner("取得 DB 狀態..."):
        try:
            db_status = _fetch_db_status()
        except Exception as exc:
            st.error(f"無法取得 DB 狀態：{exc}")
            db_status = {}

    if db_status:
        # 整體狀態
        is_ok = db_status.get("ok", False)
        if is_ok:
            st.success("● 資料庫連線正常")
        else:
            st.error("● 資料庫連線異常")

        # Pool 狀態卡片
        pool = db_status.get("pool", {})
        if pool:
            st.subheader("連線池狀態")
            pool_col1, pool_col2, pool_col3 = st.columns(3)
            pool_col1.metric("Pool 大小", pool.get("size", "—"))
            pool_col2.metric("已借出（checked_out）", pool.get("checked_out", "—"))
            pool_col3.metric("溢出（overflow）", pool.get("overflow", "—"))

        # 資料表格
        tables = db_status.get("tables", [])
        if tables:
            st.subheader("資料表統計")
            df_tables = pd.DataFrame(tables)
            rename_map = {"name": "表名", "row_count": "筆數"}
            df_tables = df_tables.rename(columns={k: v for k, v in rename_map.items() if k in df_tables.columns})
            st.dataframe(df_tables, use_container_width=True, hide_index=True)
    else:
        st.warning("無法取得 DB 狀態資料。")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 4：即時資料歷史
# ════════════════════════════════════════════════════════════════════════════════

with tab_rt_hist:
    st.subheader("即時資料歷史")

    # 篩選條件
    with st.expander("🔍 篩選條件", expanded=True):
        rth_col1, rth_col2, rth_col3 = st.columns(3)
        with rth_col1:
            now_utc = datetime.now(tz=timezone.utc)
            rth_date_from = st.date_input(
                "起始日期",
                value=(now_utc - timedelta(hours=1)).date(),
                key="rth_date_from",
            )
            rth_date_to = st.date_input(
                "結束日期",
                value=now_utc.date(),
                key="rth_date_to",
            )
        with rth_col2:
            _KNOWN_CATEGORIES = ["（全部）", "temperature", "humidity", "pressure", "vibration", "power"]
            rth_cat_label = st.selectbox("類別", _KNOWN_CATEGORIES, index=0, key="rth_cat")
            rth_category: str | None = None if rth_cat_label == "（全部）" else rth_cat_label
        with rth_col3:
            rth_page_size = st.selectbox("每頁筆數", [20, 50, 100], index=0, key="rth_size")
            rth_page = st.number_input("頁碼", min_value=1, value=1, step=1, key="rth_page")

    @st.cache_data(ttl=10)
    def _fetch_rt_history(
        date_from: str, date_to: str, category: str | None, page: int, size: int,
    ) -> tuple[list[dict], int, int]:
        params: dict = {"date_from": date_from, "date_to": date_to, "page": page, "size": size}
        if category:
            params["category"] = category
        resp = client.get("/admin/realtime-history", params=params)
        if resp.status_code == 200:
            body = resp.json()
            return body.get("items", []), body.get("total", 0), body.get("pages", 1)
        return [], 0, 1

    with st.spinner("載入即時資料歷史..."):
        try:
            rth_items, rth_total, rth_pages = _fetch_rt_history(
                date_from=rth_date_from.isoformat() + "T00:00:00Z",
                date_to=rth_date_to.isoformat() + "T23:59:59Z",
                category=rth_category,
                page=int(rth_page),
                size=int(rth_page_size),
            )
        except Exception as exc:
            st.error(f"無法取得即時資料歷史：{exc}")
            rth_items, rth_total, rth_pages = [], 0, 1

    st.markdown(f"**共 {rth_total} 筆，第 {int(rth_page)}/{rth_pages} 頁**")

    if rth_items:
        df_rth = pd.DataFrame(rth_items)

        # ── 趨勢圖 ──────────────────────────────────────────────────────────
        if "ts" in df_rth.columns and "value" in df_rth.columns:
            df_rth["ts_tw"] = pd.to_datetime(df_rth["ts"], utc=True).dt.tz_convert("Asia/Taipei")
            df_rth["value_float"] = pd.to_numeric(df_rth["value"], errors="coerce")

            fig_rth = go.Figure()
            fig_rth.add_trace(go.Scatter(
                x=df_rth["ts_tw"],
                y=df_rth["value_float"],
                mode="lines+markers",
                name="數值",
                line={"color": "purple"},
            ))

            # 標記異常點
            if "is_anomaly" in df_rth.columns:
                anomaly_rth = df_rth[df_rth["is_anomaly"].fillna(False)]
                if not anomaly_rth.empty:
                    fig_rth.add_trace(go.Scatter(
                        x=anomaly_rth["ts_tw"],
                        y=anomaly_rth["value_float"],
                        mode="markers",
                        name="異常",
                        marker={"color": "red", "size": 10, "symbol": "x"},
                    ))

            fig_rth.update_layout(
                title=f"即時資料歷史趨勢{'（' + rth_category + '）' if rth_category else '（全類別）'}",
                xaxis_title="時間（台北）",
                yaxis_title="數值",
                margin={"l": 40, "r": 20, "t": 50, "b": 40},
            )
            st.plotly_chart(fig_rth, use_container_width=True)

        # ── DataFrame ────────────────────────────────────────────────────────
        rename_map = {
            "id": "ID",
            "value": "數值",
            "category": "類別",
            "ts": "時間（台北）",
            "source": "來源",
            "is_anomaly": "異常",
        }
        available = [c for c in rename_map if c in df_rth.columns]
        df_rth_show = df_rth[available].rename(columns=rename_map).copy()
        if "時間（台北）" in df_rth_show.columns:
            df_rth_show["時間（台北）"] = df_rth_show["時間（台北）"].apply(format_ts)
        if "異常" in df_rth_show.columns:
            df_rth_show["異常"] = df_rth_show["異常"].apply(lambda v: "⚠️ 是" if v else "正常")
        st.dataframe(df_rth_show, use_container_width=True, hide_index=True)
    else:
        st.info("查詢區間內沒有即時資料歷史。")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 5：系統設定
# ════════════════════════════════════════════════════════════════════════════════

with tab_settings:
    st.subheader("系統設定")
    st.caption("修改設定後點擊「儲存」即時生效。設定值存放於資料庫 app_settings 表。")

    @st.cache_data(ttl=30)
    def _fetch_settings() -> list[dict]:
        resp = client.get("/admin/settings")
        if resp.status_code == 200:
            return resp.json()
        return []

    with st.spinner("載入系統設定..."):
        try:
            settings_list = _fetch_settings()
        except Exception as exc:
            st.error(f"無法取得系統設定：{exc}")
            settings_list = []

    if settings_list:
        for setting in settings_list:
            key = setting.get("key", "")
            current_val = setting.get("value", "")
            description = setting.get("description", "")
            updated_at = format_ts(setting.get("updated_at"))

            with st.expander(f"🔧 {key}", expanded=True):
                st.caption(description)
                st.caption(f"最後更新：{updated_at}" if updated_at else "尚未更新")

                setting_col1, setting_col2 = st.columns([3, 1])

                with setting_col1:
                    # 嘗試以數字 input 顯示（numeric settings）
                    try:
                        current_num = float(current_val)
                        new_val_num = st.number_input(
                            f"{key} 的值",
                            value=current_num,
                            format="%.4f",
                            key=f"setting_input_{key}",
                        )
                        new_val_str = str(new_val_num)
                        value_changed = abs(new_val_num - current_num) > 1e-10
                    except (ValueError, TypeError):
                        # 非數字：使用文字 input
                        new_val_str = st.text_input(
                            f"{key} 的值",
                            value=current_val,
                            key=f"setting_input_{key}",
                        )
                        value_changed = new_val_str != current_val

                with setting_col2:
                    st.markdown("&nbsp;", unsafe_allow_html=True)  # 垂直對齊用
                    if st.button(
                        "儲存",
                        key=f"setting_save_{key}",
                        type="primary",
                        use_container_width=True,
                    ):
                        if value_changed:
                            resp = client.patch(
                                f"/admin/settings/{key}",
                                json={"value": new_val_str},
                            )
                            if resp.status_code == 200:
                                st.success(f"✅ `{key}` 已更新為 `{new_val_str}`")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                try:
                                    detail = resp.json().get("detail", "更新失敗")
                                except Exception:
                                    detail = f"更新失敗（HTTP {resp.status_code}）"
                                st.error(f"更新失敗：{detail}")
                        else:
                            st.info("數值未變更。")
    else:
        st.warning("無法取得系統設定，或設定列表為空。")

    st.markdown("---")
    if st.button("🔄 重新載入設定", key="reload_settings"):
        st.cache_data.clear()
        st.rerun()
