"""
資料管理頁面：13 欄 wide schema data_editor + 篩選分頁 + CSV 批量匯入。
角色權限：
  - viewer：只讀，data_editor 全欄位 disabled，隱藏匯入區塊
  - user：可新增 / 編輯自己的資料記錄，可批量匯入
  - admin：全功能，額外顯示 id / created_at / updated_at 欄位
"""
from __future__ import annotations

import io
import json
import os
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

# 排序欄位（wide schema）
_SORT_FIELDS = ["ts", "created_at", "updated_at", "temperature", "humidity", "pressure", "voltage", "cpu_usage"]
_SORT_ORDERS = {"新到舊 (desc)": "desc", "舊到新 (asc)": "asc"}
_METRICS = ["temperature", "humidity", "pressure", "voltage", "cpu_usage"]
_METRIC_ZH = {
    "temperature": "溫度 °C",
    "humidity": "濕度 %",
    "pressure": "壓力 kPa",
    "voltage": "電壓 V",
    "cpu_usage": "CPU %",
}

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

st.caption(
    "您可以在這裡管理資料：下載 CSV 範本後上傳批量匯入、以篩選條件搜尋已有資料、"
    "直接在表格 inline 編輯欄位後一次儲存。"
    "Viewer 角色為唯讀，User 只能編輯自己的資料，Admin 可編輯所有資料。"
)

st.markdown("---")

# ── 篩選 Widget ───────────────────────────────────────────────────────────────
with st.expander("篩選條件", expanded=True):
    f_col1, f_col2, f_col3 = st.columns(3)

    with f_col1:
        # T7.2: source multiselect 取代 v2 category text input
        f_sources = st.multiselect(
            "資料來源（留空 = 全部）",
            options=["user", "simulator"],
            default=[],
            key="f_sources",
            format_func=lambda x: {"user": "錄入資料", "simulator": "即時資料"}.get(x, x),
        )
        f_date_from = st.date_input("起始日期", value=None, key="date_from")
        f_date_to = st.date_input("結束日期", value=None, key="date_to")

    with f_col2:
        # T7.2: metric range filter
        f_metric = st.selectbox(
            "數值範圍篩選（Metric）",
            ["（不篩選）"] + [f"{_METRIC_ZH[m]}（{m}）" for m in _METRICS],
            index=0,
            key="f_metric_select",
        )
        # 從 label 取回 metric key
        f_metric_key: str | None = None
        if f_metric != "（不篩選）":
            for mk in _METRICS:
                if mk in f_metric:
                    f_metric_key = mk
                    break
        f_min_value = st.number_input(
            "最小值",
            value=None,
            key="f_min_value",
            disabled=(f_metric_key is None),
            format="%.4f",
        )
        f_max_value = st.number_input(
            "最大值",
            value=None,
            key="f_max_value",
            disabled=(f_metric_key is None),
            format="%.4f",
        )

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
    """組裝 GET /data 的查詢參數（wide schema）。"""
    params: dict[str, Any] = {
        "page": int(page_num),
        "size": int(page_size),
        "sort_by": f_sort_by,
        "sort_order": f_sort_order,
    }
    if f_sources:
        params["sources"] = f_sources
    if f_metric_key:
        params["metric"] = f_metric_key
        if f_min_value is not None:
            params["min_value"] = float(f_min_value)
        if f_max_value is not None:
            params["max_value"] = float(f_max_value)
    if f_date_from:
        params["date_from"] = f_date_from.isoformat() + "T00:00:00Z"
    if f_date_to:
        params["date_to"] = f_date_to.isoformat() + "T23:59:59Z"
    return params


# ── 取得資料 ──────────────────────────────────────────────────────────────────
def _fetch_data(params: dict[str, Any]) -> tuple[list[dict], int, int]:
    """呼叫 GET /data（wide schema），回傳 (items, total, pages)。"""
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

# ── 13 欄 wide data_editor ────────────────────────────────────────────────────
st.subheader("資料列表（可直接編輯）")

if role == "viewer":
    st.info("Viewer 角色為唯讀，無法編輯資料。")


def _build_display_df(raw_items: list[dict], is_admin: bool) -> pd.DataFrame:
    """
    將 API response items 轉為 display DataFrame。
    - 將 anomaly_flags dict 拆成 5 個 boolean 欄位（temperature_anomaly / ... ）
    - admin 才保留 id / created_at / updated_at
    """
    rows = []
    for item in raw_items:
        flags = item.get("anomaly_flags") or {}
        if isinstance(flags, str):
            try:
                flags = json.loads(flags)
            except Exception:
                flags = {}
        row: dict[str, Any] = {
            "id": item.get("id"),
            "ts": item.get("ts"),
            "temperature": item.get("temperature"),
            "humidity": item.get("humidity"),
            "pressure": item.get("pressure"),
            "voltage": item.get("voltage"),
            "cpu_usage": item.get("cpu_usage"),
            # 5 anomaly checkboxes
            "temperature_anomaly": bool(flags.get("temperature", False)),
            "humidity_anomaly": bool(flags.get("humidity", False)),
            "pressure_anomaly": bool(flags.get("pressure", False)),
            "voltage_anomaly": bool(flags.get("voltage", False)),
            "cpu_usage_anomaly": bool(flags.get("cpu_usage", False)),
            "source": item.get("source", "user"),
            "note": item.get("note") or "",
            "owner_id": item.get("owner_id"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }
        rows.append(row)

    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    return df


def _make_column_config(is_admin: bool, is_viewer: bool) -> dict:
    """構建 data_editor column_config（wide 13 欄）。"""
    cfg: dict[str, Any] = {
        "ts": st.column_config.DatetimeColumn(
            "時間",
            required=True,
            help="UTC 時間戳",
        ),
        "temperature": st.column_config.NumberColumn(
            "溫度 °C", format="%.4f", min_value=-50.0, max_value=200.0
        ),
        "humidity": st.column_config.NumberColumn(
            "濕度 %", format="%.4f", min_value=0.0, max_value=110.0
        ),
        "pressure": st.column_config.NumberColumn(
            "壓力 kPa", format="%.4f", min_value=800.0, max_value=1200.0
        ),
        "voltage": st.column_config.NumberColumn(
            "電壓 V", format="%.4f", min_value=0.0, max_value=30.0
        ),
        "cpu_usage": st.column_config.NumberColumn(
            "CPU %", format="%.4f", min_value=0.0, max_value=100.0
        ),
        "temperature_anomaly": st.column_config.CheckboxColumn("溫度異常"),
        "humidity_anomaly": st.column_config.CheckboxColumn("濕度異常"),
        "pressure_anomaly": st.column_config.CheckboxColumn("氣壓異常"),
        "voltage_anomaly": st.column_config.CheckboxColumn("電壓異常"),
        "cpu_usage_anomaly": st.column_config.CheckboxColumn("CPU 異常"),
        "source": st.column_config.SelectboxColumn(
            "來源", options=["user", "simulator"], required=True
        ),
        "note": st.column_config.TextColumn(
            "備註", max_chars=200, help="標題（可選）"
        ),
        "owner_id": st.column_config.NumberColumn("擁有者 ID", disabled=True),
    }
    if is_admin:
        cfg["id"] = st.column_config.NumberColumn("ID", disabled=True)
        cfg["created_at"] = st.column_config.DatetimeColumn("建立時間", disabled=True)
        cfg["updated_at"] = st.column_config.DatetimeColumn("更新時間", disabled=True)
    return cfg


def _get_disabled_cols(is_admin: bool, is_viewer: bool, df: pd.DataFrame) -> list[str] | bool:
    """viewer 全 disabled；非 viewer 只鎖 id / owner_id / created_at / updated_at。"""
    if is_viewer:
        return list(df.columns)
    locked = ["owner_id"]
    if is_admin:
        locked += ["id", "created_at", "updated_at"]
    return locked


def _get_display_cols(is_admin: bool, df: pd.DataFrame) -> list[str]:
    """決定要顯示的欄位順序（admin 才顯示 id / created_at / updated_at）。"""
    base_cols = [
        "ts",
        "temperature", "humidity", "pressure", "voltage", "cpu_usage",
        "temperature_anomaly", "humidity_anomaly", "pressure_anomaly",
        "voltage_anomaly", "cpu_usage_anomaly",
        "source", "note", "owner_id",
    ]
    if is_admin:
        base_cols = ["id"] + base_cols + ["created_at", "updated_at"]
    return [c for c in base_cols if c in df.columns]


is_admin = role == "admin"
is_viewer = role == "viewer"

if items:
    df_raw = pd.DataFrame(items)
    df_display = _build_display_df(items, is_admin)
    display_cols = _get_display_cols(is_admin, df_display)
    df_show = df_display[display_cols].copy()

    col_config = _make_column_config(is_admin, is_viewer)
    disabled_cols = _get_disabled_cols(is_admin, is_viewer, df_show)

    edited_df = st.data_editor(
        df_show,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic" if role in ("admin", "user") else "fixed",
        disabled=disabled_cols,
        column_config=col_config,
        key="data_editor",
    )

    # ── Diff 提交 ─────────────────────────────────────────────────────────────
    if role in ("admin", "user"):
        if st.button("儲存變更", key="save_changes_btn", type="primary"):
            # id 欄位存在時以 id 識別，否則用行索引
            orig_ids: set[int] = set()
            if "id" in df_show.columns:
                orig_ids = set(df_show["id"].dropna().astype(int).tolist())

            success_count = 0
            fail_count = 0

            # 刪除：在 orig 但不在 edited 的 row（通過 id）
            if "id" in edited_df.columns and orig_ids:
                edited_ids: set[int] = set(edited_df["id"].dropna().astype(int).tolist())
                deleted_ids = orig_ids - edited_ids
                for del_id in deleted_ids:
                    orig_raw = df_raw[df_raw["id"] == del_id]
                    if orig_raw.empty:
                        continue
                    rec_owner = int(orig_raw.iloc[0].get("owner_id", 0))
                    can_delete = (role == "admin") or (role == "user" and rec_owner == current_uid)
                    if not can_delete:
                        st.toast(f"沒有權限刪除 ID {del_id}")
                        fail_count += 1
                        continue
                    resp = client.delete(f"/data/{del_id}")
                    if resp.status_code == 204:
                        success_count += 1
                    else:
                        fail_count += 1

            # 更新 / 新增
            for _, edited_row in edited_df.iterrows():
                row_id_raw = edited_row.get("id")
                row_id: int | None = None
                try:
                    if row_id_raw is not None and not pd.isna(row_id_raw):
                        row_id = int(row_id_raw)
                except (ValueError, TypeError):
                    row_id = None

                if row_id is None or (orig_ids and row_id not in orig_ids):
                    # 新增 row（data_editor 新增的）
                    if role not in ("admin", "user"):
                        continue
                    try:
                        # 將 5 anomaly checkbox 合併回 anomaly_flags dict
                        new_flags = {
                            "temperature": bool(edited_row.get("temperature_anomaly", False)),
                            "humidity": bool(edited_row.get("humidity_anomaly", False)),
                            "pressure": bool(edited_row.get("pressure_anomaly", False)),
                            "voltage": bool(edited_row.get("voltage_anomaly", False)),
                            "cpu_usage": bool(edited_row.get("cpu_usage_anomaly", False)),
                        }
                        ts_val = edited_row.get("ts")
                        if ts_val is None or (isinstance(ts_val, float) and pd.isna(ts_val)):
                            ts_val = datetime.now(tz=timezone.utc).isoformat()
                        elif hasattr(ts_val, "isoformat"):
                            ts_val = ts_val.isoformat()
                        else:
                            ts_val = str(ts_val)

                        # 至少 1 metric 非空才送
                        metric_vals = {
                            mk: edited_row.get(mk)
                            for mk in _METRICS
                            if edited_row.get(mk) is not None
                            and not (isinstance(edited_row.get(mk), float) and pd.isna(edited_row.get(mk)))
                        }
                        if not metric_vals:
                            st.toast("新增資料至少需填 1 個 metric 數值")
                            fail_count += 1
                            continue

                        new_payload: dict[str, Any] = {
                            "ts": ts_val,
                            **{k: float(v) for k, v in metric_vals.items()},
                            "anomaly_flags": new_flags,
                            "source": str(edited_row.get("source", "user")),
                        }
                        note_val = edited_row.get("note")
                        if note_val and str(note_val).strip():
                            new_payload["note"] = str(note_val).strip()[:200]

                        resp = client.post("/data", json=new_payload)
                        if resp.status_code == 201:
                            success_count += 1
                        else:
                            fail_count += 1
                            try:
                                detail = resp.json().get("detail", "新增失敗")
                            except Exception:
                                detail = f"新增失敗（HTTP {resp.status_code}）"
                            st.toast(f"新增失敗：{detail}")
                    except Exception as exc:
                        st.toast(f"新增時發生錯誤：{exc}")
                        fail_count += 1
                    continue

                # 找對應原始 row
                orig_rows = df_raw[df_raw["id"] == row_id]
                if orig_rows.empty:
                    continue
                orig_row = orig_rows.iloc[0]
                rec_owner = int(orig_row.get("owner_id", 0))
                can_modify = (role == "admin") or (role == "user" and rec_owner == current_uid)
                if not can_modify:
                    st.toast(f"沒有權限修改 ID {row_id}")
                    fail_count += 1
                    continue

                # 計算 diff（只送有變動的欄位）
                patch_payload: dict[str, Any] = {}

                # 5 metric 欄位
                for mk in _METRICS:
                    edited_val = edited_row.get(mk)
                    orig_val = orig_row.get(mk)
                    # 處理 None / NaN
                    e_none = (edited_val is None) or (isinstance(edited_val, float) and pd.isna(edited_val))
                    o_none = (orig_val is None) or (isinstance(orig_val, float) and pd.isna(orig_val))
                    if e_none and o_none:
                        continue
                    if e_none != o_none:
                        patch_payload[mk] = None if e_none else float(edited_val)
                        continue
                    try:
                        if abs(float(edited_val) - float(orig_val)) > 1e-10:
                            patch_payload[mk] = float(edited_val)
                    except (ValueError, TypeError):
                        pass

                # anomaly_flags（從 5 checkbox 合併回 dict）
                edited_flags = {
                    "temperature": bool(edited_row.get("temperature_anomaly", False)),
                    "humidity": bool(edited_row.get("humidity_anomaly", False)),
                    "pressure": bool(edited_row.get("pressure_anomaly", False)),
                    "voltage": bool(edited_row.get("voltage_anomaly", False)),
                    "cpu_usage": bool(edited_row.get("cpu_usage_anomaly", False)),
                }
                orig_flags_raw = orig_row.get("anomaly_flags") or {}
                if isinstance(orig_flags_raw, str):
                    try:
                        orig_flags_raw = json.loads(orig_flags_raw)
                    except Exception:
                        orig_flags_raw = {}
                orig_flags = {
                    "temperature": bool(orig_flags_raw.get("temperature", False)),
                    "humidity": bool(orig_flags_raw.get("humidity", False)),
                    "pressure": bool(orig_flags_raw.get("pressure", False)),
                    "voltage": bool(orig_flags_raw.get("voltage", False)),
                    "cpu_usage": bool(orig_flags_raw.get("cpu_usage", False)),
                }
                if edited_flags != orig_flags:
                    patch_payload["anomaly_flags"] = edited_flags

                # source
                edited_source = str(edited_row.get("source", "user"))
                if edited_source != str(orig_row.get("source", "user")):
                    patch_payload["source"] = edited_source

                # note
                edited_note = str(edited_row.get("note", "") or "").strip()
                orig_note = str(orig_row.get("note", "") or "").strip()
                if edited_note != orig_note:
                    patch_payload["note"] = edited_note[:200] if edited_note else None

                if patch_payload:
                    resp = client.patch(f"/data/{row_id}", json=patch_payload)
                    if resp.status_code == 200:
                        success_count += 1
                    elif resp.status_code == 403:
                        st.toast(f"沒有權限修改 ID {row_id}")
                        fail_count += 1
                    elif resp.status_code == 422:
                        try:
                            detail = resp.json().get("detail", "驗證失敗")
                        except Exception:
                            detail = "驗證失敗"
                        st.toast(f"ID {row_id} 更新失敗：{detail}")
                        fail_count += 1
                    else:
                        fail_count += 1

            if success_count > 0:
                st.success(f"成功更新 {success_count} 筆資料。")
            if fail_count > 0:
                st.warning(f"有 {fail_count} 筆操作失敗或無權限。")
            if success_count > 0 or fail_count > 0:
                st.rerun()

else:
    st.info("目前沒有符合條件的資料。")

# ── CSV 批量匯入（admin / user 可用）────────────────────────────────────────────
st.markdown("---")
if role in ("admin", "user"):
    st.subheader("批量匯入 CSV")
    st.caption(
        "CSV 格式採 wide schema（11 欄）。請先下載範本參考格式，再上傳您的資料檔案。"
        "單檔上限 10 MB。"
    )

    # T7.2: sample download button 放在 file_uploader 上方
    _SAMPLE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs",
        "sample_data.csv",
    )
    if os.path.exists(_SAMPLE_PATH):
        with open(_SAMPLE_PATH, "rb") as _f:
            _sample_bytes = _f.read()
        st.download_button(
            label="下載 wide CSV template（200 筆範例）",
            data=_sample_bytes,
            file_name="wide_template.csv",
            mime="text/csv",
            key="download_sample_csv",
        )
    else:
        st.caption(
            "CSV 欄位：ts, temperature, humidity, pressure, voltage, cpu_usage, "
            "anomaly_flags, source, note, owner_email（共 10 欄，owner_email 可省略）。"
        )

    uploaded_file = st.file_uploader(
        "選擇 CSV 檔案",
        type=["csv"],
        key="bulk_upload",
    )

    # T7.2: 3 層 preview widget
    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / 1_000_000
        st.info(f"已選擇檔案：**{uploaded_file.name}**（{file_size_mb:.2f} MB）")

        if file_size_mb > 10:
            st.error("檔案超過 10 MB，請分批匯入。")
        else:
            # 讀取並 preview（不需要重新上傳）
            try:
                raw_bytes = uploaded_file.getvalue()
                df_preview = pd.read_csv(io.BytesIO(raw_bytes))

                # Layer 1: header 偵測
                st.markdown("**CSV 欄位偵測**")
                _REQUIRED_METRICS = ["temperature", "humidity", "pressure", "voltage", "cpu_usage"]
                _OPTIONAL_COLS = ["ts", "anomaly_flags", "source", "note", "owner_email"]
                _OLD_LONG_COLS = {"title", "value", "category", "is_anomaly"}
                actual_cols = set(df_preview.columns.tolist())

                is_old_format = bool(actual_cols & _OLD_LONG_COLS)
                detected_metrics = [m for m in _REQUIRED_METRICS if m in actual_cols]
                has_ts = "ts" in actual_cols

                col_status_parts = []
                for m in _REQUIRED_METRICS:
                    mark = "✓" if m in actual_cols else "✗"
                    col_status_parts.append(f"`{m}` {mark}")
                for oc in ["source", "note", "owner_email"]:
                    mark = "✓" if oc in actual_cols else "✗（可省略）"
                    col_status_parts.append(f"`{oc}` {mark}")

                if is_old_format:
                    st.error(
                        "偵測到舊版 long 格式（含 title / value / category / is_anomaly 欄位）。"
                        "請下載上方 wide CSV template 後重新上傳。"
                    )
                elif not has_ts:
                    st.error("CSV 缺少必要欄位 `ts`（時間戳），請確認格式後重新上傳。")
                elif not detected_metrics:
                    missing = ", ".join(_REQUIRED_METRICS)
                    st.error(f"CSV header 缺少所有 metric 欄位，至少需要其中一個：{missing}")
                else:
                    st.markdown("  ".join(col_status_parts))

                # Layer 2: 前 5 row preview
                st.markdown("**前 5 筆資料預覽**")
                st.dataframe(df_preview.head(5), use_container_width=True, hide_index=True)

                # Layer 3: 統計摘要
                st.markdown("**統計摘要**")
                total_rows = len(df_preview)

                # 異常筆數（anomaly_flags 欄位有 true 值）
                anomaly_count = 0
                if "anomaly_flags" in df_preview.columns:
                    for _, r in df_preview.iterrows():
                        try:
                            flags_raw = r["anomaly_flags"]
                            if isinstance(flags_raw, str):
                                flags_dict = json.loads(flags_raw.replace("'", '"'))
                                if any(flags_dict.values()):
                                    anomaly_count += 1
                        except Exception:
                            pass

                # 時間範圍
                time_range_str = "—"
                if "ts" in df_preview.columns:
                    try:
                        ts_series = pd.to_datetime(df_preview["ts"], utc=True, errors="coerce").dropna()
                        if not ts_series.empty:
                            ts_min = ts_series.min().strftime("%Y-%m-%d %H:%M")
                            ts_max = ts_series.max().strftime("%Y-%m-%d %H:%M")
                            time_range_str = f"{ts_min} ~ {ts_max}"
                    except Exception:
                        pass

                stat_cols = st.columns(4)
                stat_cols[0].metric("總筆數", total_rows)
                stat_cols[1].metric("含異常筆數", anomaly_count)
                stat_cols[2].metric("時間範圍", time_range_str)
                # per-metric avg
                metric_avg_parts = []
                for mk in detected_metrics:
                    try:
                        avg_v = pd.to_numeric(df_preview[mk], errors="coerce").mean()
                        if not pd.isna(avg_v):
                            metric_avg_parts.append(f"{_METRIC_ZH.get(mk, mk)}: {avg_v:.2f}")
                    except Exception:
                        pass
                stat_cols[3].markdown("**各指標平均**  \n" + "  \n".join(metric_avg_parts) if metric_avg_parts else "—")

            except Exception as exc:
                st.warning(f"預覽讀取失敗（{exc}），仍可嘗試匯入。")
                df_preview = None

            if st.button("開始匯入", key="import_btn", type="primary"):
                with st.spinner("匯入中..."):
                    file_bytes = uploaded_file.getvalue()
                    files = {"file": (uploaded_file.name, file_bytes, "text/csv")}
                    resp = client.post("/data/bulk-import", files=files)

                if resp.status_code == 200:
                    result = resp.json()
                    inserted = result.get("inserted", 0)
                    failed = result.get("failed", 0)
                    errors = result.get("errors", [])

                    st.success(f"匯入完成：成功 **{inserted}** 筆，失敗 **{failed}** 筆。")

                    if errors:
                        st.subheader("失敗明細")
                        # T7.2: 解析 missing_columns 欄位，顯示明確錯誤訊息
                        for err in errors[:20]:
                            row_num = err.get("row", "?")
                            reason = err.get("reason", "未知原因")
                            missing_cols = err.get("missing_columns", [])
                            if missing_cols:
                                missing_str = "、".join(missing_cols)
                                st.error(f"第 {row_num} 行：CSV header 缺少：{missing_str}")
                            else:
                                st.warning(f"第 {row_num} 行：{reason}")
                        if len(errors) > 20:
                            st.caption(f"（僅顯示前 20 筆，共 {len(errors)} 筆失敗）")

                    if inserted > 0:
                        st.rerun()
                elif resp.status_code == 413:
                    st.error("檔案超過伺服器限制（10 MB），請分批匯入。")
                else:
                    try:
                        detail = resp.json().get("detail", "匯入失敗")
                    except Exception:
                        detail = f"匯入失敗（HTTP {resp.status_code}）"
                    st.error(f"匯入失敗：{detail}")
else:
    st.info("Viewer 角色無法進行批量匯入。")
