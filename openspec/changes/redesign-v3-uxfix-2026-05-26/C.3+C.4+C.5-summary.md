# Frontend Summary — C.3+C.4+C.5 Sprint 2（Story #5 + #7 + #8a）

**Date**：2026-05-26
**Agent**：frontend-engineer sub-agent
**Worktree**：`.claude/worktrees/agent-a46f49da896639b4c`
**Tasks completed**：C.3（Story #5 動態閾值）/ C.4（Story #7 Demo Banner）/ C.5a（Story #8 拆分 a delta_color 修復）

---

## 改動的 component / page / state

### C.4 — auth.py：新增 render_demo_banner() helper

**File**：`frontend/streamlit_app/auth.py`
**改動位置**：line 139–167（append 29 行在 render_role_matrix() 之後）

新增 `render_demo_banner(role: str) -> None` helper：

- 若 `st.session_state.get(f"hide_banner_{role}", False)` 為 True → 直接 return（「不再顯示」已勾選）
- `routes` dict 三角色建議動線：
  - viewer：`儀表板 → 即時監控 → 分析報表`
  - user：`儀表板 → 資料管理（上傳 CSV）→ 分析報表 → 即時監控`
  - admin：`儀表板 → 即時監控（試觸發異常）→ 系統管理（改閾值 / 看 Audit log）→ 分析報表（匯出 Excel）`
- 未知 role fallback：`儀表板 → 即時監控`
- `st.info(f"**建議 {role_label} demo 動線：** {msg}")` 顯示 banner（VA-22：用 info 非 modal，避免強迫導覽感）
- `st.checkbox("不再顯示此提示（本次 session）", key=f"hide_banner_check_{role}")` checkbox（VA-23：Admin 反覆看不耐煩時可關閉）
- 勾選後寫 `st.session_state[f"hide_banner_{role}"] = True` + `st.rerun()`

設計選擇：
- session_state key 依 role 分離（`hide_banner_admin` / `hide_banner_user` / `hide_banner_viewer`），三角色間不互相影響
- 未動 render_role_matrix()，只在其後 append（Story #2 Sprint 1 已完成的 helper 完整保留）

### C.4 — 1_儀表板.py：import render_demo_banner + 呼叫

**File**：`frontend/streamlit_app/pages/1_儀表板.py`
**改動位置 1**：line 12，import 加 `render_demo_banner`
**改動位置 2**：line 49，在 `with st.container(border=True): render_role_matrix(role)` 之後插入

```python
# Story #7：角色 Demo Banner 建議動線（緊接矩陣卡片之後）
render_demo_banner(role)
```

Layout 保全：
- Banner 在矩陣卡片之後、D2-4 System status header 之前
- 不遮蓋任何功能操作元件（AC-5）

### C.3 — 4_即時監控.py：fetch_dynamic_thresholds() + 動態閾值使用

**File**：`frontend/streamlit_app/pages/4_即時監控.py`
**改動位置 1**：line 72–109（在 `_METRIC_LOW_THRESHOLD` dict 之後新增 38 行）

新增 `@st.cache_data(ttl=30)` 裝飾的 `fetch_dynamic_thresholds(role: str) -> tuple[dict, dict, bool]`：

```
回傳 (high_dict, low_dict, is_dynamic)
```

VA-9 BLOCKER 已驗（spike-results.md §A.1）：viewer/user 打 /admin/settings → 403（AdminOnly 守衛），故：
- `role != "admin"` → 直接 return hardcode fallback（不打 endpoint，避免 403 noise log）
- `role == "admin"` → GET `/admin/settings`：
  - 200 → parse `{s["key"]: s["value"]}` dict → 取 `anomaly_threshold_high` / `anomaly_threshold_low` float → 套用 5 metric → return `(high, low, True)`
  - 403 → fallback（admin 拿到 403 不預期，但仍安全 fallback）
  - Exception → fallback

**改動位置 2**：line 188–189，在 status header 之後、multiselect 之前

```python
_dyn_high, _dyn_low, _is_dynamic = fetch_dynamic_thresholds(role)
```

**改動位置 3**：ctrl_col 區段擴展為三列，新增「重新整理閾值」按鈕（line 192–210）：

```python
ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 1, 1])
# ctrl_col3: if st.button("重新整理閾值"): st.cache_data.clear(); st.rerun()
```

**改動位置 4**：line 212–216，閾值來源提示：
- `not _is_dynamic and role != "admin"` → `st.caption("閾值為預設值（唯讀，僅 Admin 可在系統管理 → 系統設定中調整）")`
- `not _is_dynamic and role == "admin"` → `st.warning("無法取得動態閾值，使用預設值（請檢查後端連線）")`

**改動位置 5**：line 243–244，告警卡 threshold 計算改讀動態 dict：

```python
high_thr = _dyn_high.get(metric_key, 100.0)  # 改自 _METRIC_HIGH_THRESHOLD
low_thr = _dyn_low.get(metric_key, 0.0)      # 改自 _METRIC_LOW_THRESHOLD
```

hardcode `_METRIC_HIGH_THRESHOLD` / `_METRIC_LOW_THRESHOLD` dict 保留完整（fallback 必須）。

### C.5a — 4_即時監控.py：delta_color="inverse" → "normal"

**File**：`frontend/streamlit_app/pages/4_即時監控.py`
**改動位置**：line 255

```python
# Story #8a: delta_color normal — 異常 +N 應顯示紅色（+N = 超閾值更多 = 更糟）
# inverse 會讓 +N 顯示綠色（升高=好），語意與異常告警相反
delta_color="normal",
```

修復語意：`"inverse"` 讓正偏差 delta（+50 超閾值）顯示**綠色**（升高=好），與「超閾值=異常=壞」的語意完全相反。改 `"normal"` 後 +N 顯示紅色符合直覺。

### C.5a — 1_儀表板.py：delta_color="inverse" → "normal"

**File**：`frontend/streamlit_app/pages/1_儀表板.py`
**改動位置**：line 162–164

```python
# Story #8a: delta_color normal — 異常數升高應顯示紅色（normal: +N = red 符合語意）
# 此欄無 delta 值，故 delta_color 設定無視覺差；但改 normal 確保語意一致，避免未來加 delta 時出錯
delta_color="normal",
```

此 metric card（異常筆數合計）目前無設 `delta=` 值，故 `delta_color` 無視覺影響。但改為 `normal` 確保若未來加 delta 值，顏色語意仍正確。

---

## Backend API 使用（cross-reference backend-summary）

Story #5 admin flow（design.md Section 4 Story #5 端對端 5 段）：

| 段 | 內容 |
|---|---|
| FE 送 | GET `/api/v1/admin/settings` + Authorization: Bearer {jwt}（admin only） |
| BE 收 | `backend/app/api/v1/admin.py:169-177` `list_settings()` 走 `AdminOnly`（deps.py:60） |
| DB 存 | （只讀）`app_settings` table SELECT * |
| BE 回 | `list[AppSettingResponse]` JSON：`[{"key": "anomaly_threshold_high", "value": "100.0", ...}]` |
| FE 顯示 | parse settings dict → 套用 5 metric high/low → 告警卡顯示「閾值 XX.X」反映新值 |

Story #5 viewer/user flow（VA-9 fallback path）：

- FE **不打** `/admin/settings`（VA-9 已驗 403）
- 直接使用 hardcode `_METRIC_HIGH_THRESHOLD` / `_METRIC_LOW_THRESHOLD`
- 頁面顯示 `st.caption("閾值為預設值（唯讀，僅 Admin 可在系統管理 → 系統設定中調整）")`

Story #7 render_demo_banner：純前端渲染，無 API call，讀 `role` 參數（已登入後從 session_state["user"]["role"] 取得）

---

## 處理的 edge case / 失敗 path

1. **VA-9 403 fallback**：viewer/user 的 role 判斷完全繞開 `/admin/settings`，不製造 403 noise log
2. **admin /admin/settings 網路失敗**：`except Exception: pass` → fallback hardcode + `st.warning`
3. **admin 拿到非預期 403**：`elif resp.status_code == 403: fallback`（安全降級，不 crash）
4. **settings JSON schema 不符**（key 不存在）：`settings.get("anomaly_threshold_high", 100.0)` fallback 預設值
5. **重新整理閾值按鈕 → st.cache_data.clear()**：清掉所有 cache（包含 `fetch_dynamic_thresholds`），下次 rerun 重新取閾值
6. **Demo Banner 不再顯示**：session_state key 依 role 分離，三角色獨立控制
7. **unknown role**：`routes.get(role, "儀表板 → 即時監控")` fallback，不 crash
8. **Story #8a delta_color**：告警卡 `_is_dynamic` 會影響 `high_thr` / `low_thr`，`threshold` 計算邏輯不變，只 delta_color 從 inverse → normal

---

## Grep 驗證結果

```
rg 'delta_color\s*=\s*"inverse"' worktree/frontend/streamlit_app/
→ No instances found ✓ （兩處全改完）

grep "def render_demo_banner" auth.py
→ 139: def render_demo_banner(role: str) -> None: ✓

grep "render_demo_banner(role)" 1_儀表板.py
→ 49: render_demo_banner(role) ✓

grep "@st.cache_data(ttl=30)" 4_即時監控.py
→ 76: @st.cache_data(ttl=30) (fetch_dynamic_thresholds) ✓

grep "_dyn_high\|_dyn_low" 4_即時監控.py
→ 189, 243, 244 ✓

grep "重新整理閾值" 4_即時監控.py
→ 208: if st.button("重新整理閾值", key="refresh_thresholds"): ✓
```

---

## Python 語法驗證

```
python3 -m py_compile auth.py              → OK
python3 -m py_compile 1_儀表板.py          → OK
python3 -m py_compile 4_即時監控.py        → OK
```

---

## 端對端資料流追蹤（5/23 嚴令）

**Story #5 admin flow 完整追蹤**：
1. Admin 在系統管理頁 PATCH `/admin/settings` `anomaly_threshold_high=60`（BE 已處理）
2. Admin 切到即時監控頁 → `fetch_dynamic_thresholds("admin")` 被呼叫 → cache TTL=30 秒可能命中舊值
3. Admin 點「重新整理閾值」→ `st.cache_data.clear()` + `st.rerun()`
4. 重新渲染 → `fetch_dynamic_thresholds("admin")` cache miss → GET `/admin/settings` → 200 → `{"anomaly_threshold_high": "60.0"}` → high=60 for all metrics → `is_dynamic=True`
5. 告警卡 `high_thr = _dyn_high.get("cpu_usage", 100.0)` = 60.0 → 顯示「閾值 60.0」

**Story #5 viewer flow 完整追蹤**：
1. Viewer 進入即時監控頁 → `fetch_dynamic_thresholds("viewer")` → `role != "admin"` → 直接 return hardcode + False
2. `_is_dynamic = False`，`role != "admin"` → `st.caption("閾值為預設值（唯讀）...")` 顯示
3. 告警卡使用 hardcode `_METRIC_HIGH_THRESHOLD`

---

C.3+C.4+C.5 DONE
