"""
系統管理頁面（僅 admin 角色可存取）。

5 個 tab（去 emoji）：
  1. 使用者列表   — GET /users、角色權限矩陣、改密碼
  2. 系統日誌     — GET /admin/logs
  3. 資料庫狀態   — GET /admin/db-status
  4. 即時資料歷史 — GET /admin/realtime-history（wide format）+ 5 條折線（保留）
  5. 系統設定     — GET/PATCH /admin/settings + 異常閾值設定（PATCH /admin/settings）

非 admin → st.error + st.stop()。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from api_client import APIClient
from auth import current_role, current_user, logout, require_auth

st.set_page_config(
    page_title="系統管理 — 即時資料分析與監控系統",
    page_icon=None,
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
    st.title("系統管理")
with col_user:
    st.markdown(
        f"**{user.get('display_name', '未知')}**  \n"
        f"角色：`{role}`",
    )
    if st.button("登出", key="logout_btn", use_container_width=True):
        logout()
        st.switch_page("Home.py")

st.caption("您是 Admin 角色，可以在這裡管理整個系統：使用者列表（改角色 / 啟用 / 刪除 / 改密碼）、查看 Audit log、檢視 DB 連線池與表統計、即時資料歷史查詢、動態調整異常閾值與 tick 間隔。")

st.markdown("---")

# ── D6-3: 5 個 tab label 全去 emoji ────────────────────────────────────────────
tab_users, tab_logs, tab_db, tab_rt_hist, tab_settings = st.tabs([
    "使用者列表",
    "系統日誌",
    "資料庫狀態",
    "即時資料歷史",
    "系統設定",
])


# ════════════════════════════════════════════════════════════════════════════════
# Tab 1：使用者列表
# ════════════════════════════════════════════════════════════════════════════════

with tab_users:
    st.subheader("使用者管理")

    # D6-4: 角色權限說明 markdown table（v3 預設展開，配合 Story #2）
    with st.expander("角色權限說明", expanded=True):
        st.markdown("""
| 操作 | admin | user | viewer |
|---|---|---|---|
| 登入系統 | ✓ | ✓ | ✓ |
| 查看儀表板 | ✓ | ✓ | ✓ |
| 查看即時監控 | ✓ | ✓ | ✓ |
| 查看分析報表 | ✓ | ✓ | ✓ |
| 查看資料管理 | ✓ | ✓ | ✓（唯讀）|
| 新增資料 | ✓ | ✓ | ✗ |
| 編輯自己的資料 | ✓ | ✓ | ✗ |
| 編輯他人資料 | ✓ | ✗ | ✗ |
| 刪除自己的資料 | ✓ | ✓ | ✗ |
| 刪除他人資料 | ✓ | ✗ | ✗ |
| 批量匯入 CSV/JSON | ✓ | ✓ | ✗ |
| 存取系統管理 | ✓ | ✗ | ✗ |
| 管理使用者角色 | ✓ | ✗ | ✗ |
""")

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
            df_u_show["啟用"] = df_u_show["啟用"].apply(lambda v: "是" if v else "否")
        if "建立時間" in df_u_show.columns:
            df_u_show["建立時間"] = df_u_show["建立時間"].apply(format_ts)
        st.dataframe(df_u_show, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("編輯使用者")

        user_options = {f"[{u['id']}] {u.get('email', '')} ({u.get('role', '')})": u for u in u_items}
        selected_label = st.selectbox("選擇使用者", list(user_options.keys()), key="u_edit_select")
        selected_user_item = user_options.get(selected_label)

        if selected_user_item:
            edit_col1, edit_col2 = st.columns(2)
            with edit_col1:
                new_role_val = st.selectbox(
                    "角色",
                    ["admin", "user", "viewer"],
                    index=["admin", "user", "viewer"].index(selected_user_item.get("role", "user")),
                    key="u_edit_role",
                )
            with edit_col2:
                new_is_active = st.checkbox(
                    "啟用帳號",
                    value=bool(selected_user_item.get("is_active", True)),
                    key="u_edit_active",
                )

            if st.button("更新使用者", key="u_edit_btn", type="primary"):
                patch_payload: dict = {}
                if new_role_val != selected_user_item.get("role"):
                    patch_payload["role"] = new_role_val
                if new_is_active != bool(selected_user_item.get("is_active", True)):
                    patch_payload["is_active"] = new_is_active

                if patch_payload:
                    resp = client.patch(f"/users/{selected_user_item['id']}", json=patch_payload)
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

            # v3 Story #11 AC-3：刪除使用者（DELETE /users/{id}）
            st.markdown("---")
            st.subheader("刪除選定使用者")

            _selected_uid = selected_user_item.get("id")
            _current_uid = user.get("id")
            _is_self = (_selected_uid == _current_uid)

            if _is_self:
                st.warning("不可刪除自己的帳號。請選擇其他使用者。")
                st.button(
                    "刪除選定使用者",
                    key="u_delete_btn",
                    type="secondary",
                    disabled=True,
                )
            else:
                # 確認 checkbox + 刪除按鈕
                _confirm_delete = st.checkbox(
                    f"確認刪除 {selected_user_item.get('email', '')}（不可復原）",
                    key="u_delete_confirm",
                )
                if st.button(
                    "刪除選定使用者",
                    key="u_delete_btn",
                    type="secondary",
                    disabled=not _confirm_delete,
                ):
                    _del_resp = client.delete(f"/users/{_selected_uid}")
                    if _del_resp.status_code in (200, 204):
                        st.success(f"已刪除使用者 {selected_user_item.get('email', '')}。")
                        st.cache_data.clear()
                        st.rerun()
                    elif _del_resp.status_code == 404:
                        st.error("此使用者已被刪除。")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        try:
                            _detail = _del_resp.json().get("detail", "刪除失敗")
                        except Exception:
                            _detail = f"刪除失敗（HTTP {_del_resp.status_code}）"
                        st.error(f"刪除失敗：{_detail}")

        st.markdown("---")

        # D6-5: 改密碼表單（admin 改任意人，改自己需 old_password）
        st.subheader("修改密碼")
        st.caption("Admin 改自己需提供舊密碼；Admin 改他人無需舊密碼。")

        # 選擇要改密碼的對象
        pw_target_options = {f"[{u['id']}] {u.get('email', '')} ({u.get('role', '')})": u for u in u_items}
        pw_target_label = st.selectbox("選擇要修改密碼的使用者", list(pw_target_options.keys()), key="pw_target_select")
        pw_target = pw_target_options.get(pw_target_label)

        if pw_target:
            is_self_pw = (pw_target.get("id") == user.get("id"))
            with st.form("admin_change_password_form"):
                pw_old = st.text_input(
                    "舊密碼（改自己時必填）",
                    type="password",
                    key="admin_pw_old",
                )
                pw_new = st.text_input("新密碼（至少 8 個字元）", type="password", key="admin_pw_new")
                pw_new2 = st.text_input("確認新密碼", type="password", key="admin_pw_new2")
                pw_submitted = st.form_submit_button("修改密碼", use_container_width=True)

            if pw_submitted:
                pw_errors: list[str] = []
                if not pw_new:
                    pw_errors.append("請輸入新密碼。")
                elif len(pw_new) < 8:
                    pw_errors.append("新密碼至少需要 8 個字元。")
                if pw_new != pw_new2:
                    pw_errors.append("兩次新密碼輸入不一致。")

                if pw_errors:
                    for err in pw_errors:
                        st.error(err)
                else:
                    target_uid = pw_target.get("id")
                    body: dict = {"new_password": pw_new}
                    if is_self_pw:
                        if not pw_old:
                            st.error("修改自己密碼必須提供舊密碼。")
                        else:
                            body["old_password"] = pw_old
                    # admin 改他人：不送 old_password

                    if not (is_self_pw and not pw_old):
                        resp = client.patch(f"/users/{target_uid}/password", json=body)
                        if resp.status_code == 200:
                            st.success(f"已成功修改 {pw_target.get('email', '')} 的密碼。")
                        else:
                            try:
                                detail = resp.json().get("detail", "修改失敗")
                            except Exception:
                                detail = f"修改失敗（HTTP {resp.status_code}）"
                            st.error(f"修改失敗：{detail}")
    else:
        st.info("目前沒有符合條件的使用者。")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 2：系統日誌
# ════════════════════════════════════════════════════════════════════════════════

with tab_logs:
    st.subheader("稽核日誌")

    st.caption("Audit log 預設顯示前 50 筆。若需更早記錄請使用上方日期篩選縮小範圍。")

    with st.expander("篩選條件", expanded=True):
        log_col1, log_col2, log_col3 = st.columns(3)
        with log_col1:
            log_page_size = st.selectbox("每頁筆數", [20, 50, 100], index=1, key="log_size")
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

        if "meta" in df_logs.columns:
            with st.expander("查看 metadata 詳情"):
                for item in log_items[:10]:
                    if item.get("meta"):
                        st.json(item["meta"])
    else:
        st.info("查詢區間內沒有日誌記錄。")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 3：資料庫狀態
# ════════════════════════════════════════════════════════════════════════════════

with tab_db:
    st.subheader("資料庫狀態")

    if st.button("重新整理 DB 狀態", key="refresh_db"):
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
        is_ok = db_status.get("ok", False)
        if is_ok:
            st.success("資料庫連線正常")
        else:
            st.error("資料庫連線異常")

        pool = db_status.get("pool", {})
        if pool:
            st.subheader("連線池狀態")
            pool_col1, pool_col2, pool_col3 = st.columns(3)
            pool_col1.metric("Pool 大小", pool.get("size", "—"))
            pool_col2.metric("已借出（checked_out）", pool.get("checked_out", "—"))
            pool_col3.metric("溢出（overflow）", pool.get("overflow", "—"))

        tables = db_status.get("tables", [])
        if tables:
            st.subheader("資料表統計")
            df_tables = pd.DataFrame(tables)
            rename_map = {"name": "表名", "row_count": "筆數"}
            df_tables = df_tables.rename(
                columns={k: v for k, v in rename_map.items() if k in df_tables.columns}
            )
            st.dataframe(df_tables, use_container_width=True, hide_index=True)
    else:
        st.warning("無法取得 DB 狀態資料。")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 4：即時資料歷史（D6-6: wide format）
# ════════════════════════════════════════════════════════════════════════════════

_ADMIN_METRIC_KEYS = ["temperature", "humidity", "pressure", "voltage", "cpu_usage"]
_ADMIN_METRIC_ZH = {
    "temperature": "溫度(C)",
    "humidity": "濕度(%)",
    "pressure": "氣壓(hPa)",
    "voltage": "電壓(V)",
    "cpu_usage": "CPU(%)",
}
_ADMIN_METRIC_COLORS = {
    "temperature": "royalblue",
    "humidity": "green",
    "pressure": "orange",
    "voltage": "purple",
    "cpu_usage": "teal",
}

with tab_rt_hist:
    st.subheader("即時資料歷史")

    # D6-8: 移除類別 selectbox（wide format 無需 category 篩選）
    with st.expander("篩選條件", expanded=True):
        rth_col1, rth_col2 = st.columns(2)
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
            rth_page_size = st.selectbox("每頁筆數", [20, 50, 100], index=0, key="rth_size")
            rth_page = st.number_input("頁碼", min_value=1, value=1, step=1, key="rth_page")

    @st.cache_data(ttl=10)
    def _fetch_rt_history_wide(
        date_from: str, date_to: str, page: int, size: int,
    ) -> tuple[list[dict], int, int]:
        # D6-6: 不帶 category 參數（wide API 已移除）
        params: dict = {"date_from": date_from, "date_to": date_to, "page": page, "size": size}
        resp = client.get("/admin/realtime-history", params=params)
        if resp.status_code == 200:
            body = resp.json()
            return body.get("items", []), body.get("total", 0), body.get("pages", 1)
        return [], 0, 1

    with st.spinner("載入即時資料歷史..."):
        try:
            rth_items, rth_total, rth_pages = _fetch_rt_history_wide(
                date_from=rth_date_from.isoformat() + "T00:00:00Z",
                date_to=rth_date_to.isoformat() + "T23:59:59Z",
                page=int(rth_page),
                size=int(rth_page_size),
            )
        except Exception as exc:
            st.error(f"無法取得即時資料歷史：{exc}")
            rth_items, rth_total, rth_pages = [], 0, 1

    st.markdown(f"**共 {rth_total} 筆，第 {int(rth_page)}/{rth_pages} 頁**")

    if rth_items:
        df_rth = pd.DataFrame(rth_items)

        # D6-7: 折線圖 5 條線
        if "ts" in df_rth.columns:
            df_rth["ts_tw"] = pd.to_datetime(df_rth["ts"], utc=True, format="ISO8601").dt.tz_convert("Asia/Taipei")

            fig_rth = go.Figure()
            for metric_key in _ADMIN_METRIC_KEYS:
                if metric_key in df_rth.columns:
                    df_rth[f"{metric_key}_float"] = pd.to_numeric(df_rth[metric_key], errors="coerce")
                    fig_rth.add_trace(go.Scatter(
                        x=df_rth["ts_tw"],
                        y=df_rth[f"{metric_key}_float"],
                        mode="lines",
                        name=_ADMIN_METRIC_ZH.get(metric_key, metric_key),
                        line={"color": _ADMIN_METRIC_COLORS.get(metric_key, "gray"), "width": 2},
                    ))

                    # 異常點
                    if "anomaly_flags" in df_rth.columns:
                        def _is_anom_rth(row: pd.Series, mk: str = metric_key) -> bool:
                            flags = row.get("anomaly_flags", {})
                            if isinstance(flags, dict):
                                return bool(flags.get(mk, False))
                            return False
                        anom_mask_rth = df_rth.apply(_is_anom_rth, axis=1)
                        anom_rth = df_rth[anom_mask_rth]
                        if not anom_rth.empty:
                            fig_rth.add_trace(go.Scatter(
                                x=anom_rth["ts_tw"],
                                y=anom_rth[f"{metric_key}_float"],
                                mode="markers",
                                name=f"{_ADMIN_METRIC_ZH.get(metric_key, metric_key)} 異常",
                                marker={
                                    "color": "red",
                                    "size": 10,
                                    "symbol": "circle-open",
                                    "line": {"width": 2, "color": "red"},
                                },
                                showlegend=True,
                            ))

            fig_rth.update_layout(
                title="即時資料歷史趨勢（5 條 metric 線）",
                xaxis_title="時間（台北）",
                yaxis_title="數值",
                legend={"orientation": "h", "y": -0.3},
                margin={"l": 40, "r": 20, "t": 50, "b": 100},
            )
            st.plotly_chart(fig_rth, use_container_width=True)

        # Wide format DataFrame：ts + 5 metric column + anomaly_flags 拆 5 boolean
        display_rows_rth = []
        for _, row in df_rth.iterrows():
            flags = row.get("anomaly_flags", {})
            if not isinstance(flags, dict):
                flags = {}
            display_rows_rth.append({
                "時間（台北）": format_ts(row.get("ts")),
                "溫度(C)": row.get("temperature"),
                "濕度(%)": row.get("humidity"),
                "氣壓(hPa)": row.get("pressure"),
                "電壓(V)": row.get("voltage"),
                "CPU(%)": row.get("cpu_usage"),
                "溫度異常": "是" if flags.get("temperature", False) else "否",
                "濕度異常": "是" if flags.get("humidity", False) else "否",
                "氣壓異常": "是" if flags.get("pressure", False) else "否",
                "電壓異常": "是" if flags.get("voltage", False) else "否",
                "CPU 異常": "是" if flags.get("cpu_usage", False) else "否",
                "來源": row.get("source", "simulator"),
            })
        df_rth_show = pd.DataFrame(display_rows_rth)
        st.dataframe(df_rth_show, use_container_width=True, hide_index=True)
    else:
        st.info("查詢區間內沒有即時資料歷史。")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 5：系統設定（D6-9: 去 emoji）
# ════════════════════════════════════════════════════════════════════════════════

with tab_settings:
    st.subheader("系統設定")
    st.caption("修改設定後點擊「儲存」即時生效。設定值存放於資料庫 app_settings 表。")

    # ── T7.5: 異常閾值設定區塊（PATCH /api/v1/admin/settings）────────────────
    st.subheader("異常閾值設定")
    st.caption(
        "設定各指標的異常判定閾值。當指標數值超出 [低閾值, 高閾值] 範圍時，系統將標記為異常。"
        "儲存後 30 秒內全系統生效（anomaly_detector cache TTL）。"
    )

    _THRESHOLD_METRICS = [
        ("temperature", "溫度 °C"),
        ("humidity", "濕度 %"),
        ("pressure", "壓力 kPa"),
        ("voltage", "電壓 V"),
        ("cpu_usage", "CPU %"),
    ]
    # 預設值（對應 settings.py DEFAULT_ANOMALY_THRESHOLDS）
    _DEFAULT_THRESHOLDS = {
        "temperature": {"high": 80.0, "low": 10.0},
        "humidity": {"high": 85.0, "low": 20.0},
        "pressure": {"high": 1050.0, "low": 950.0},
        "voltage": {"high": 13.5, "low": 11.0},
        "cpu_usage": {"high": 90.0, "low": 5.0},
    }

    # 從 DB 取現有 threshold（parse app_settings key: anomaly_threshold.<metric>）
    @st.cache_data(ttl=30)
    def _fetch_thresholds() -> dict[str, dict]:
        """從 /admin/settings 取出 anomaly_threshold.* key，回傳 {metric: {high, low}}。"""
        import json as _json
        resp = client.get("/admin/settings")
        result: dict[str, dict] = {}
        if resp.status_code == 200:
            for setting in resp.json():
                key_str = setting.get("key", "")
                if key_str.startswith("anomaly_threshold."):
                    metric_name = key_str.replace("anomaly_threshold.", "")
                    try:
                        val = _json.loads(setting.get("value", "{}"))
                        result[metric_name] = val
                    except Exception:
                        pass
        return result

    with st.spinner("載入閾值設定..."):
        try:
            existing_thresholds = _fetch_thresholds()
        except Exception:
            existing_thresholds = {}

    threshold_inputs: dict[str, dict] = {}
    for mk, zh_label in _THRESHOLD_METRICS:
        defaults = existing_thresholds.get(mk) or _DEFAULT_THRESHOLDS.get(mk, {"high": 100.0, "low": 0.0})
        with st.expander(f"{zh_label}（{mk}）閾值", expanded=False):
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                high_val = st.number_input(
                    "高閾值（超過此值標記異常）",
                    value=float(defaults.get("high", 100.0)),
                    format="%.4f",
                    key=f"threshold_high_{mk}",
                )
            with t_col2:
                low_val = st.number_input(
                    "低閾值（低於此值標記異常）",
                    value=float(defaults.get("low", 0.0)),
                    format="%.4f",
                    key=f"threshold_low_{mk}",
                )
            if high_val <= low_val:
                st.warning(f"警告：高閾值（{high_val}）應大於低閾值（{low_val}），請確認設定。")
            threshold_inputs[mk] = {"high": high_val, "low": low_val}

    if st.button("儲存異常閾值設定", key="save_thresholds_btn", type="primary"):
        # 驗證：任何 high <= low 直接拒絕
        invalid_metrics = [
            zh_label
            for mk, zh_label in _THRESHOLD_METRICS
            if threshold_inputs[mk]["high"] <= threshold_inputs[mk]["low"]
        ]
        if invalid_metrics:
            st.error(f"以下指標高閾值必須大於低閾值：{', '.join(invalid_metrics)}")
        else:
            with st.spinner("儲存中..."):
                resp_thresh = client.patch_admin_settings(threshold_inputs)
            if resp_thresh.status_code == 200:
                st.toast("已儲存，30 秒內生效")
                st.cache_data.clear()
                st.rerun()
            else:
                try:
                    detail = resp_thresh.json().get("detail", "儲存失敗")
                except Exception:
                    detail = f"儲存失敗（HTTP {resp_thresh.status_code}）"
                st.error(f"閾值儲存失敗：{detail}")

    st.markdown("---")

    # ── 原有設定項目列表 ─────────────────────────────────────────────────────
    st.subheader("其他設定項目")

    # Settings expander toggle（v3 Story #11 AC-2）
    if "settings_all_expanded" not in st.session_state:
        st.session_state["settings_all_expanded"] = False

    toggle_label = "收合全部" if st.session_state["settings_all_expanded"] else "展開全部設定"
    if st.button(toggle_label, key="settings_toggle_expand"):
        st.session_state["settings_all_expanded"] = not st.session_state["settings_all_expanded"]
        st.rerun()

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

            with st.expander(f"設定項目：{key}", expanded=st.session_state.get("settings_all_expanded", False)):
                st.caption(description)
                st.caption(f"最後更新：{updated_at}" if updated_at else "尚未更新")

                setting_col1, setting_col2 = st.columns([3, 1])

                with setting_col1:
                    try:
                        current_num = float(current_val)
                        new_val_num = st.number_input(
                            f"{key} 的值",
                            value=current_num,
                            format="%.4f",
                            key=f"setting_input_{key}",
                            label_visibility="collapsed",
                        )
                        new_val_str = str(new_val_num)
                        value_changed = abs(new_val_num - current_num) > 1e-10
                    except (ValueError, TypeError):
                        new_val_str = st.text_input(
                            f"{key} 的值",
                            value=current_val,
                            key=f"setting_input_{key}",
                            label_visibility="collapsed",
                        )
                        value_changed = new_val_str != current_val

                with setting_col2:
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
                                st.success(f"`{key}` 已更新為 `{new_val_str}`")
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
    if st.button("重新載入設定", key="reload_settings"):
        st.cache_data.clear()
        st.rerun()
