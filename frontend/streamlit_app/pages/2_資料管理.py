"""
資料管理頁面：inline edit + 篩選分頁 + CSV/JSON 批量匯入。
角色權限：
  - viewer：只讀，st.data_editor 全欄位 disabled
  - user：可新增/編輯自己的記錄
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
    page_icon=None,
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
    st.title("資料管理")
with col_user:
    st.markdown(
        f"**{user.get('display_name', '未知')}**  \n"
        f"角色：`{role}`",
    )
    if st.button("登出", key="logout_btn", use_container_width=True):
        logout()
        st.switch_page("Home.py")

st.caption("您可以在這裡管理資料：上傳 CSV / JSON 批量匯入、用篩選條件搜尋已有資料、inline 編輯欄位後一次儲存。Viewer 角色為唯讀，User 只能編輯自己的資料，Admin 可編輯所有資料。")

st.markdown("---")


# ── 篩選 Widget ───────────────────────────────────────────────────────────────
with st.expander("篩選條件", expanded=True):
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
    """呼叫 GET /data，回傳 (items, total, pages)。"""
    resp = client.get("/data", params=params)
    if resp.status_code == 200:
        body = resp.json()
        return body.get("items", []), body.get("total", 0), body.get("pages", 1)
    st.error(f"無法取得資料（HTTP {resp.status_code}）")
    return [], 0, 1


params = _build_params()
items, total, total_pages = _fetch_data(params)

st.markdown(f"**共 {total} 筆，第 {int(page_num)}/{total_pages} 頁**")

st.markdown("---")

# ── D3-3: 移除「逐筆操作」，D3-4~D3-5: st.data_editor inline edit ───────────────
st.subheader("資料列表（可直接編輯）")

if role == "viewer":
    st.info("Viewer 角色為唯讀，無法編輯資料。")

if items:
    df = pd.DataFrame(items)

    # 建立顯示用 DataFrame（保留 id / owner_id 供 diff 使用）
    display_cols = {
        "id": "ID",
        "title": "標題",
        "value": "數值",
        "category": "類別",
        "recorded_at": "記錄時間",
        "is_anomaly": "異常",
        "owner_id": "擁有者 ID",
        "created_at": "建立時間",
        "updated_at": "更新時間",
    }
    available = [c for c in display_cols if c in df.columns]
    df_show = df[available].rename(columns=display_cols).copy()

    # 格式化記錄時間
    if "記錄時間" in df_show.columns:
        df_show["記錄時間"] = pd.to_datetime(df_show["記錄時間"]).dt.strftime("%Y-%m-%d %H:%M")
    if "建立時間" in df_show.columns:
        df_show["建立時間"] = pd.to_datetime(df_show["建立時間"]).dt.strftime("%Y-%m-%d %H:%M")
    if "更新時間" in df_show.columns:
        df_show["更新時間"] = pd.to_datetime(df_show["更新時間"]).dt.strftime("%Y-%m-%d %H:%M")

    # viewer 全欄 disabled
    all_cols_disabled = list(df_show.columns)
    editor_disabled = all_cols_disabled if role == "viewer" else ["ID", "擁有者 ID", "建立時間", "更新時間"]

    edited_df = st.data_editor(
        df_show,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic" if role in ("admin", "user") else "fixed",
        disabled=editor_disabled,
        column_config={
            "標題": st.column_config.TextColumn(required=True, max_chars=200),
            "數值": st.column_config.NumberColumn(format="%.4f", required=True),
            "類別": st.column_config.SelectboxColumn(
                options=["temperature", "humidity", "pressure", "voltage", "cpu_usage", "其他"],
                required=True,
            ),
            "記錄時間": st.column_config.TextColumn(),
            "異常": st.column_config.CheckboxColumn(),
        },
        key="data_editor",
    )

    # ── D3-6: Diff 提交 ───────────────────────────────────────────────────────
    if role in ("admin", "user"):
        if st.button("儲存變更", key="save_changes_btn", type="primary"):
            orig_ids = set(df_show["ID"].tolist()) if "ID" in df_show.columns else set()
            edited_ids = set(edited_df["ID"].tolist()) if "ID" in edited_df.columns else set()

            deleted_ids = orig_ids - edited_ids
            success_count = 0
            fail_count = 0

            # 刪除缺少的 row
            for del_id in deleted_ids:
                orig_row = df[df["id"] == del_id].iloc[0] if not df[df["id"] == del_id].empty else None
                if orig_row is None:
                    continue
                rec_owner = orig_row.get("owner_id") if isinstance(orig_row, dict) else orig_row["owner_id"]
                can_delete = (role == "admin") or (role == "user" and rec_owner == current_uid)
                if not can_delete:
                    st.toast(f"沒有權限刪除 ID {del_id}", icon=None)
                    fail_count += 1
                    continue
                resp = client.delete(f"/data/{del_id}")
                if resp.status_code == 204:
                    success_count += 1
                else:
                    fail_count += 1

            # 更新修改的 row
            for _, edited_row in edited_df.iterrows():
                row_id = edited_row.get("ID")
                if pd.isna(row_id) or row_id not in orig_ids:
                    # 新增 row（data_editor 新增的）
                    if role not in ("admin", "user"):
                        continue
                    try:
                        new_payload: dict[str, Any] = {
                            "title": str(edited_row.get("標題", "")),
                            "value": float(edited_row.get("數值", 0)),
                            "category": str(edited_row.get("類別", "")),
                            "is_anomaly": bool(edited_row.get("異常", False)),
                            "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
                        }
                        if new_payload["title"] and new_payload["category"]:
                            resp = client.post("/data", json=new_payload)
                            if resp.status_code == 201:
                                success_count += 1
                            else:
                                fail_count += 1
                    except Exception:
                        fail_count += 1
                    continue

                # 找對應原 row
                orig_rows = df[df["id"] == int(row_id)]
                if orig_rows.empty:
                    continue
                orig_row = orig_rows.iloc[0]
                rec_owner = orig_row.get("owner_id")
                can_modify = (role == "admin") or (role == "user" and rec_owner == current_uid)
                if not can_modify:
                    st.toast(f"沒有權限修改 ID {int(row_id)}", icon=None)
                    fail_count += 1
                    continue

                # 計算 diff
                patch_payload: dict[str, Any] = {}
                if str(edited_row.get("標題", "")) != str(orig_row.get("title", "")):
                    patch_payload["title"] = str(edited_row.get("標題", ""))
                try:
                    if abs(float(edited_row.get("數值", 0)) - float(orig_row.get("value", 0))) > 1e-10:
                        patch_payload["value"] = float(edited_row.get("數值", 0))
                except (ValueError, TypeError):
                    pass
                if str(edited_row.get("類別", "")) != str(orig_row.get("category", "")):
                    patch_payload["category"] = str(edited_row.get("類別", ""))
                edited_anom = bool(edited_row.get("異常", False))
                orig_anom = bool(orig_row.get("is_anomaly", False))
                if edited_anom != orig_anom:
                    patch_payload["is_anomaly"] = edited_anom

                if patch_payload:
                    resp = client.patch(f"/data/{int(row_id)}", json=patch_payload)
                    if resp.status_code == 200:
                        success_count += 1
                    elif resp.status_code == 403:
                        st.toast(f"沒有權限修改 ID {int(row_id)}", icon=None)
                        fail_count += 1
                    else:
                        fail_count += 1

            if success_count > 0:
                st.success(f"成功更新 {success_count} 筆資料。")
            if fail_count > 0:
                st.warning(f"有 {fail_count} 筆操作失敗或無權限。")
            if success_count > 0 or fail_count == 0:
                st.rerun()

else:
    st.info("目前沒有符合條件的資料。")

# ── D3-7: CSV/JSON 批量匯入（admin/user 可用，去 emoji）─────────────────────────
st.markdown("---")
if role in ("admin", "user"):
    st.subheader("批量匯入 CSV / JSON")
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
                            error_df.columns = (
                                ["行號", "原因"]
                                if list(error_df.columns) == ["row", "reason"]
                                else error_df.columns
                            )
                            st.dataframe(error_df, use_container_width=True, hide_index=True)
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
