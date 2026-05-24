"""
資料管理頁面：CRUD + 篩選分頁 + CSV 批量匯入。
角色權限：
  - viewer：只讀，隱藏新增/編輯/刪除按鈕
  - user：可新增；編輯/刪除只能操作自己的記錄
  - admin：全功能
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from api_client import APIClient
from auth import current_role, current_user, logout, require_auth

st.set_page_config(
    page_title="資料管理 — 即時資料分析與監控系統",
    page_icon="📁",
    layout="wide",
)

# 認證守衛
require_auth()

client = APIClient()
user = current_user()
role = current_role()
current_uid = user.get("id")

# 可用的 sort_by 欄位（對齊後端白名單）
_SORT_FIELDS = ["recorded_at", "created_at", "title", "value", "category"]
_SORT_ORDERS = {"新到舊 (desc)": "desc", "舊到新 (asc)": "asc"}

# ── 右上角：使用者資訊 + 登出 ─────────────────────────────────────────────────
col_title, col_user = st.columns([3, 1])
with col_title:
    st.title("📁 資料管理")
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
with st.expander("🔍 篩選條件", expanded=True):
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        f_category = st.text_input("類別", placeholder="留空表示全部")
        f_search = st.text_input("標題關鍵字搜尋", placeholder="模糊搜尋")
    with f_col2:
        f_date_from = st.date_input("起始日期", value=None, key="date_from")
        f_date_to = st.date_input("結束日期", value=None, key="date_to")
    with f_col3:
        f_sort_by = st.selectbox("排序欄位", _SORT_FIELDS, index=0)
        f_sort_order_label = st.selectbox("排序方向", list(_SORT_ORDERS.keys()), index=0)
        f_sort_order = _SORT_ORDERS[f_sort_order_label]

# ── 分頁設定 ──────────────────────────────────────────────────────────────────
pg_col1, pg_col2 = st.columns([1, 3])
with pg_col1:
    page_size = st.selectbox("每頁筆數", [10, 20, 50, 100], index=1)
with pg_col2:
    # 先用 placeholder，取到 total 後更新
    page_num = st.number_input("頁碼", min_value=1, value=1, step=1, key="page_num_input")


def _build_params() -> dict[str, Any]:
    """組裝 GET /data 的查詢參數。"""
    params: dict[str, Any] = {
        "page": int(page_num),
        "size": int(page_size),
        "sort_by": f_sort_by,
        "sort_order": f_sort_order,
    }
    if f_category:
        params["category"] = f_category
    if f_search:
        params["search"] = f_search
    if f_date_from:
        params["date_from"] = f_date_from.isoformat() + "T00:00:00"
    if f_date_to:
        params["date_to"] = f_date_to.isoformat() + "T23:59:59"
    return params


# ── 取得資料 ──────────────────────────────────────────────────────────────────
def _fetch_data(params: dict[str, Any]) -> tuple[list[dict], int, int]:
    """
    呼叫 GET /data，回傳 (items, total, pages)。
    """
    resp = client.get("/data", params=params)
    if resp.status_code == 200:
        body = resp.json()
        return body.get("items", []), body.get("total", 0), body.get("pages", 1)
    st.error(f"無法取得資料（HTTP {resp.status_code}）")
    return [], 0, 1


params = _build_params()
items, total, total_pages = _fetch_data(params)

st.markdown(f"**共 {total} 筆，第 {int(page_num)}/{total_pages} 頁**")

# ── 新增按鈕（viewer 隱藏）────────────────────────────────────────────────────
if role in ("admin", "user"):
    if st.button("➕ 新增資料", key="add_btn"):
        st.session_state["show_add_form"] = True

# ── 新增表單 ──────────────────────────────────────────────────────────────────
if st.session_state.get("show_add_form") and role in ("admin", "user"):
    with st.form("add_data_form"):
        st.subheader("新增資料")
        a_title = st.text_input("標題 *", placeholder="資料標題")
        a_value = st.number_input("數值 *", value=0.0, format="%.4f")
        a_category = st.text_input("類別 *", placeholder="例如：temperature")
        a_recorded_at = st.datetime_input(
            "記錄時間 *",
            value=datetime.now(tz=timezone.utc),
        )
        a_is_anomaly = st.checkbox("標記為異常")
        col_submit, col_cancel = st.columns(2)
        submitted = col_submit.form_submit_button("儲存", use_container_width=True)
        cancelled = col_cancel.form_submit_button("取消", use_container_width=True)

    if submitted:
        if not a_title or not a_category:
            st.error("標題和類別為必填欄位。")
        else:
            payload = {
                "title": a_title,
                "value": a_value,
                "category": a_category,
                "recorded_at": a_recorded_at.isoformat(),
                "is_anomaly": a_is_anomaly,
            }
            resp = client.post("/data", json=payload)
            if resp.status_code == 201:
                st.success("資料新增成功！")
                st.session_state["show_add_form"] = False
                st.rerun()
            else:
                try:
                    detail = resp.json().get("detail", "新增失敗")
                except Exception:
                    detail = f"新增失敗（HTTP {resp.status_code}）"
                st.error(f"新增失敗：{detail}")
    if cancelled:
        st.session_state["show_add_form"] = False
        st.rerun()

st.markdown("---")

# ── 資料列表 ──────────────────────────────────────────────────────────────────
if not items:
    st.info("目前沒有符合條件的資料。")
else:
    # 顯示 DataFrame 總覽
    df = pd.DataFrame(items)
    display_cols = {
        "id": "ID",
        "title": "標題",
        "value": "數值",
        "category": "類別",
        "recorded_at": "記錄時間",
        "is_anomaly": "異常",
        "owner_id": "擁有者 ID",
    }
    available = [c for c in display_cols if c in df.columns]
    df_show = df[available].rename(columns=display_cols).copy()
    if "異常" in df_show.columns:
        df_show["異常"] = df_show["異常"].apply(lambda v: "⚠️ 是" if v else "正常")
    if "記錄時間" in df_show.columns:
        df_show["記錄時間"] = pd.to_datetime(df_show["記錄時間"]).dt.strftime("%Y-%m-%d %H:%M")

    st.dataframe(df_show, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("逐筆操作")

    # ── 每筆資料的編輯 / 刪除 ────────────────────────────────────────────────
    for record in items:
        rec_id = record["id"]
        rec_owner = record.get("owner_id")
        is_mine = (rec_owner == current_uid)

        # 判斷此筆是否可編輯/刪除
        can_modify = (role == "admin") or (role == "user" and is_mine)

        with st.expander(
            f"[#{rec_id}] {record.get('title', '—')} | {record.get('category', '—')} | "
            f"數值: {record.get('value', 0):.4f} | "
            f"{'⚠️ 異常' if record.get('is_anomaly') else '正常'}",
            expanded=False,
        ):
            # 詳細資訊
            det_col1, det_col2, det_col3 = st.columns(3)
            det_col1.write(f"**ID：** {rec_id}")
            det_col1.write(f"**標題：** {record.get('title', '')}")
            det_col2.write(f"**類別：** {record.get('category', '')}")
            det_col2.write(f"**數值：** {record.get('value', 0):.4f}")
            det_col3.write(f"**記錄時間：** {record.get('recorded_at', '')}")
            det_col3.write(f"**擁有者 ID：** {rec_owner}")

            if not can_modify:
                st.caption("（您沒有修改此筆資料的權限）")
            else:
                # ── 編輯表單 ─────────────────────────────────────────────────
                edit_key = f"edit_{rec_id}"
                if st.button("✏️ 編輯此筆", key=f"edit_btn_{rec_id}"):
                    st.session_state[edit_key] = True

                if st.session_state.get(edit_key):
                    with st.form(f"edit_form_{rec_id}"):
                        e_title = st.text_input(
                            "標題",
                            value=record.get("title", ""),
                            key=f"e_title_{rec_id}",
                        )
                        e_value = st.number_input(
                            "數值",
                            value=float(record.get("value", 0)),
                            format="%.4f",
                            key=f"e_value_{rec_id}",
                        )
                        e_category = st.text_input(
                            "類別",
                            value=record.get("category", ""),
                            key=f"e_category_{rec_id}",
                        )
                        e_is_anomaly = st.checkbox(
                            "標記為異常",
                            value=bool(record.get("is_anomaly", False)),
                            key=f"e_anomaly_{rec_id}",
                        )
                        e_submit, e_cancel = st.columns(2)
                        e_submitted = e_submit.form_submit_button("更新", use_container_width=True)
                        e_cancelled = e_cancel.form_submit_button("取消", use_container_width=True)

                    if e_submitted:
                        patch_payload: dict[str, Any] = {}
                        if e_title != record.get("title"):
                            patch_payload["title"] = e_title
                        if abs(float(e_value) - float(record.get("value", 0))) > 1e-10:
                            patch_payload["value"] = e_value
                        if e_category != record.get("category"):
                            patch_payload["category"] = e_category
                        if e_is_anomaly != bool(record.get("is_anomaly", False)):
                            patch_payload["is_anomaly"] = e_is_anomaly

                        if patch_payload:
                            resp = client.patch(f"/data/{rec_id}", json=patch_payload)
                            if resp.status_code == 200:
                                st.success("更新成功！")
                                st.session_state[edit_key] = False
                                st.rerun()
                            else:
                                try:
                                    detail = resp.json().get("detail", "更新失敗")
                                except Exception:
                                    detail = f"更新失敗（HTTP {resp.status_code}）"
                                st.error(f"更新失敗：{detail}")
                        else:
                            st.info("沒有任何變更。")
                            st.session_state[edit_key] = False

                    if e_cancelled:
                        st.session_state[edit_key] = False
                        st.rerun()

                # ── 刪除確認 Modal ─────────────────────────────────────────────
                del_confirm_key = f"del_confirm_{rec_id}"
                if not st.session_state.get(del_confirm_key):
                    if st.button(
                        "🗑️ 刪除此筆",
                        key=f"del_btn_{rec_id}",
                        type="secondary",
                    ):
                        st.session_state[del_confirm_key] = True
                        st.rerun()
                else:
                    st.warning(f"確定要刪除「{record.get('title', '')}」（ID {rec_id}）？此操作無法復原。")
                    c_yes, c_no = st.columns(2)
                    if c_yes.button("確定刪除", key=f"del_yes_{rec_id}", type="primary"):
                        resp = client.delete(f"/data/{rec_id}")
                        if resp.status_code == 204:
                            st.success("刪除成功！")
                            st.session_state[del_confirm_key] = False
                            st.rerun()
                        else:
                            try:
                                detail = resp.json().get("detail", "刪除失敗")
                            except Exception:
                                detail = f"刪除失敗（HTTP {resp.status_code}）"
                            st.error(f"刪除失敗：{detail}")
                    if c_no.button("取消", key=f"del_no_{rec_id}"):
                        st.session_state[del_confirm_key] = False
                        st.rerun()

# ── CSV 批量匯入（admin/user 可用）────────────────────────────────────────────
st.markdown("---")
if role in ("admin", "user"):
    st.subheader("📂 批量匯入 CSV / JSON")
    st.caption(
        "CSV 欄位格式：title, value, category, recorded_at（ISO8601）。"
        "JSON 格式：物件陣列，欄位同上。單檔上限 10 MB。"
    )

    uploaded_file = st.file_uploader(
        "選擇 CSV 或 JSON 檔案",
        type=["csv", "json"],
        key="bulk_upload",
    )

    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / 1_000_000
        st.info(f"已選擇檔案：**{uploaded_file.name}**（{file_size_mb:.2f} MB）")

        if file_size_mb > 10:
            st.error("檔案超過 10 MB，請分批匯入。")
        else:
            if st.button("開始匯入", key="import_btn", type="primary"):
                with st.spinner("匯入中..."):
                    # multipart/form-data 上傳：files 參數格式為 {欄位名: (檔名, 內容, MIME type)}
                    file_bytes = uploaded_file.getvalue()
                    mime = "text/csv" if uploaded_file.name.endswith(".csv") else "application/json"
                    files = {"file": (uploaded_file.name, file_bytes, mime)}
                    resp = client.post("/data/bulk-import", files=files)

                if resp.status_code == 200:
                    result = resp.json()
                    inserted = result.get("inserted", 0)
                    failed = result.get("failed", 0)
                    errors = result.get("errors", [])

                    st.success(f"匯入完成：成功 **{inserted}** 筆，失敗 **{failed}** 筆。")

                    if errors:
                        st.subheader("失敗明細")
                        error_df = pd.DataFrame(errors)
                        if not error_df.empty:
                            error_df.columns = ["行號", "原因"] if list(error_df.columns) == ["row", "reason"] else error_df.columns
                            st.dataframe(error_df, use_container_width=True, hide_index=True)
                    # 匯入成功後重新整理資料列表
                    if inserted > 0:
                        st.rerun()
                elif resp.status_code == 413:
                    st.error("檔案超過伺服器限制（10 MB）。")
                else:
                    try:
                        detail = resp.json().get("detail", "匯入失敗")
                    except Exception:
                        detail = f"匯入失敗（HTTP {resp.status_code}）"
                    st.error(f"匯入失敗：{detail}")
else:
    st.info("Viewer 角色無法進行批量匯入。")
