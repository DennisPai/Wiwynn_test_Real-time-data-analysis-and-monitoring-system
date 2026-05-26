# Design — Redesign v2 技術設計（builder 可直接實作）

> 本文寫死所有架構決策、schema、API 契約、UI 規格。builder 不需再自行決策。
> 12 點懷特反饋（記為 Q1–Q12）每條都對應到下列段落。

---

## 0. 端對端資料流追蹤（5/23 嚴令）

**現況 long format**（v1）：

```
模擬器 (BE realtime_service._tick)
  ├─ 隨機選一個 category（5 選 1）
  ├─ random.uniform(0, 100) 一個值
  ├─ payload = {category, value, is_anomaly, ts}
  ├─ ws_manager.broadcast(payload JSON)        ← FE 收到
  └─ realtime_queue.put(tick)
       ↓
batch_writer._flush (每 5s)
  └─ INSERT realtime_metrics (id, value, category, ts, source, is_anomaly)
       ↓
GET /admin/realtime-history → 回傳 long rows
       ↓
FE 5_Admin.py「即時資料歷史」 tab：
  - df_rth = pd.DataFrame(items)
  - 折線圖以 value vs ts 畫（不分 category，亂線）   ← Q11 抱怨點
```

**Redesign v2 wide format**：

```
模擬器 (BE realtime_service._tick)
  ├─ 每秒對 5 個 category 各 random_walk 一次 → 5 個 value
  ├─ snapshot = {ts, temperature, humidity, pressure, voltage, cpu_usage,
  │              anomaly_flags: {temperature: false, ...}}
  ├─ ws_manager.broadcast(snapshot JSON)        ← FE 一秒收一筆全類別
  └─ realtime_queue.put(snapshot)
       ↓
batch_writer._flush (每 5s)
  └─ INSERT realtime_metrics_wide (
        id, ts, temperature, humidity, pressure, voltage, cpu_usage,
        anomaly_flags_json, source
     )
  └─ INSERT realtime_metrics (long, 共寫兩 table — 過渡相容)
       ↓
GET /api/v1/realtime/history?seconds=60  →  回傳 wide rows[]
GET /api/v1/admin/realtime-history       →  回傳 wide rows[] + pagination
       ↓
FE 4_即時監控.py：
  - 進頁面先 REST `/realtime/history?seconds=60` 拿 60 筆
  - WS subscribe 補後續每秒新 snapshot
  - 折線圖：5 條線（每 metric 一條）
  - 表格：60 列，異常 row 淡粉紅、異常 cell 紅字
```

**三層欄位 / type 對齊表**：

| 層 | 欄位 | type |
|---|---|---|
| BE `RealtimeSnapshot` Pydantic | `ts` | `datetime` (UTC, with tz) |
| | `temperature` | `float` |
| | `humidity` | `float` |
| | `pressure` | `float` |
| | `voltage` | `float` |
| | `cpu_usage` | `float` |
| | `anomaly_flags` | `dict[str, bool]` |
| | `schema_version` | `Literal["v2"]` |
| DB `realtime_metrics_wide` | `id` | `BigInteger PK` |
| | `ts` | `DateTime(timezone=True)` |
| | `temperature` | `Numeric(18,4)` nullable |
| | `humidity` | `Numeric(18,4)` nullable |
| | `pressure` | `Numeric(18,4)` nullable |
| | `voltage` | `Numeric(18,4)` nullable |
| | `cpu_usage` | `Numeric(18,4)` nullable |
| | `anomaly_flags` | `JSON` |
| | `source` | `String(50) default "simulator"` |
| FE WS payload parser | `ts` | string ISO8601 → `pd.to_datetime(utc=True)` |
| | metric fields | `float` |
| | `anomaly_flags` | `dict[str, bool]` |

**BLOCKER 警示**：若 BE Pydantic `ts` 是 tz-aware 但 DB column 是 naive，會發生「FE 送 ISO Z → BE parse tz-aware → DB 比較全 false」的 Q7 root cause B 重演。本 spec 強制 DB column 改 `DateTime(timezone=True)`。

---

## 1. 資料 Schema 改動

### 1.1 新增 table `realtime_metrics_wide`

**model**：`backend/app/models/realtime_metric_wide.py`（新檔）

```python
class RealtimeMetricWide(Base):
    __tablename__ = "realtime_metrics_wide"
    __table_args__ = (
        Index("ix_realtime_metrics_wide_ts_desc", "ts"),
    )
    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    humidity:    Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    pressure:    Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    voltage:     Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cpu_usage:   Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    anomaly_flags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source:      Mapped[str] = mapped_column(String(50), nullable=False, default="simulator")
```

**為什麼 nullable**：未來若新增 metric 但舊 row 沒填，nullable 不破舊資料。

### 1.2 修改 table `realtime_metrics`（long）

不動（保留作過渡相容 + audit）。`batch_writer` 共寫兩 table。

### 1.3 不影響 table `data_records`

完全不動。但**前端**整合 view 會同時 query 兩 source。

### 1.4 Alembic migration `0003_realtime_wide_format`

**檔案**：`backend/alembic/versions/0003_realtime_wide_format.py`

**內容**：用 `op.create_table` + `op.create_index` 走純 SQLAlchemy。**禁** `op.execute("CREATE TABLE ...")` 等 raw SQL。

**upgrade**：
- `op.create_table("realtime_metrics_wide", ...)` 對齊 model
- `op.create_index("ix_realtime_metrics_wide_ts_desc", "realtime_metrics_wide", ["ts"])`
- 不回填 long → wide（無法重組 snapshot；wide 從上線後才累積）

**downgrade**：`op.drop_index` + `op.drop_table`。

### 1.5 解 Q8 / Q10 跨頁互通：API 層 unified view

**不**合併 table（語意不同：realtime 高頻 sensor、data_records 低頻使用者錄入）。改在 API 層提供 unified summary（詳 §6.5）。

Dashboard + 分析報表頁顯示 unified data，用 source 區分配色 / 標籤（無 emoji，用文字「即時」/「錄入」）。

---

## 2. 採集與訂閱解耦（Q1, Q2）

### 2.1 確認 simulator 「不論 FE 開不開都跑」

**現況** `backend/app/main.py` lifespan：
```python
await realtime_simulator.start(tick_seconds=tick_seconds)
await batch_writer.start(flush_seconds=flush_seconds)
```
已是「BE 啟動就跑」設計，無關 FE。**驗證**：BE 啟動 30s 不開 FE，curl `/admin/realtime-history` 應有 ≥ 30 筆。若沒有是 simulator 沒啟動的 bug。

### 2.2 random walk 模擬器（取代純 random）

**檔案**：`backend/app/services/realtime_service.py` 改 `RealtimeSimulator`。

**每 metric 自己的 baseline + σ + range**：

```python
_METRIC_PROFILES: dict[str, dict] = {
    "temperature": {"baseline": 25.0, "sigma": 1.5, "min": -20.0, "max": 120.0, "unit": "C"},
    "humidity":    {"baseline": 60.0, "sigma": 3.0, "min": 0.0,   "max": 100.0, "unit": "%"},
    "pressure":    {"baseline": 1013.0, "sigma": 5.0, "min": 900.0, "max": 1100.0, "unit": "hPa"},
    "voltage":     {"baseline": 12.0, "sigma": 0.3, "min": 0.0,   "max": 24.0,  "unit": "V"},
    "cpu_usage":   {"baseline": 40.0, "sigma": 8.0, "min": 0.0,   "max": 100.0, "unit": "%"},
}
```

**RandomWalk function**（純函式）：

```python
def random_walk_step(prev: float, sigma: float, low: float, high: float, rng: random.Random) -> float:
    delta = rng.gauss(0, sigma)
    new_value = prev + delta
    return max(low, min(high, new_value))
```

**simulator 內部狀態**：`_state: dict[str, float]`（每 metric 上一個 value）。初始化從 DB wide table 最後一筆讀，沒有則用 baseline。

**異常注入**：每 60 tick 對隨機 metric 一次性偏移 2σ，驗證告警鏈路。env var `ANOMALY_INJECTION_PERIOD`（預設 60，0 關閉）。

### 2.3 每 tick payload schema

```python
class RealtimeSnapshot(BaseModel):
    schema_version: Literal["v2"] = "v2"
    ts: datetime  # tz-aware UTC
    temperature: float
    humidity: float
    pressure: float
    voltage: float
    cpu_usage: float
    anomaly_flags: dict[str, bool]
```

**廣播**：`ws_manager.broadcast(snapshot.model_dump_json())`（一秒一個 snapshot，所有 client 同時收全類別）。

**enqueue**：`realtime_queue.put(snapshot)`（給 batch_writer 寫 DB）。

### 2.4 batch_writer 寫雙 table

```python
async def _flush(self):
    snapshots: list[RealtimeSnapshot] = drain(realtime_queue)
    if not snapshots: return
    wide_rows = [RealtimeMetricWide(
        ts=s.ts,
        temperature=Decimal(str(s.temperature)),
        humidity=Decimal(str(s.humidity)),
        pressure=Decimal(str(s.pressure)),
        voltage=Decimal(str(s.voltage)),
        cpu_usage=Decimal(str(s.cpu_usage)),
        anomaly_flags=s.anomaly_flags,
        source="simulator",
    ) for s in snapshots]
    # long rows（過渡相容，從 snapshot 拆 5 筆）
    long_rows = []
    for s in snapshots:
        for metric_name in ["temperature","humidity","pressure","voltage","cpu_usage"]:
            long_rows.append(RealtimeMetric(
                value=Decimal(str(getattr(s, metric_name))),
                category=metric_name,
                ts=s.ts,
                source="simulator",
                is_anomaly=s.anomaly_flags.get(metric_name, False),
            ))
    async with AsyncSessionLocal() as session:
        session.add_all(wide_rows)
        session.add_all(long_rows)
        await session.commit()
```

---

## 3. 訂閱模式 = Snapshot + Delta（Q2）

### 3.1 FE Realtime 頁面進入流程

`frontend/streamlit_app/pages/4_即時監控.py`：

1. `require_auth()` 守衛
2. **REST 拉 snapshot**：`GET /api/v1/realtime/history?seconds=60` 拿 60 筆 wide row
3. 把 60 筆 push 到 `ws_client._buffer`
4. 啟動 WS background thread（`run_ws_in_background`）
5. 每秒 `st_autorefresh` rerun 讀 buffer 重繪

### 3.2 ws_client 改 wide payload parser

`frontend/streamlit_app/ws_client.py`：

```python
async for raw in ws:
    data = json.loads(raw)
    if data.get("schema_version") != "v2":
        logger.warning("ws: 收到非 v2 payload，忽略 %s", data)
        continue
    self._buffer.append(data)
    on_tick(data)
```

`_buffer` 內每筆 = wide snapshot dict。

### 3.3 為何不需要 monotonic seq + catchup

時程考量。重連時直接重打 history endpoint 重置 buffer。v3 再加 catchup。

---

## 4. 5 大頁面 redesign 細節

> **檔名中文化**：rename 5 個 page 檔為中文（Streamlit 側邊欄取檔名顯示，去 emoji 後若用英文檔名違反 Q6）。

| 舊 | 新 |
|---|---|
| `pages/1_📊_Dashboard.py` | `pages/1_儀表板.py` |
| `pages/2_📁_Data.py` | `pages/2_資料管理.py` |
| `pages/3_📈_Analytics.py` | `pages/3_分析報表.py` |
| `pages/4_🔴_Realtime.py` | `pages/4_即時監控.py` |
| `pages/5_⚙️_Admin.py` | `pages/5_系統管理.py` |

### 4.1 Dashboard 重設計

**檔案**：`pages/1_儀表板.py`

**改動**：
1. `st.set_page_config(page_title="儀表板 — 即時資料分析與監控系統", page_icon=None)`
2. `st.title("儀表板")`
3. **System status header**（頁面最上方）：last update / WS dot（●/○）/ active alert count
4. Metric cards 改打 `/analytics/unified-summary`（即時+錄入兩 source）
5. 「最近 10 筆」改 tabs（即時 / 錄入）切換
6. 加「帳號設定」expander：viewer/user 改自己密碼

### 4.2 資料管理重設計（Q9 inline edit）

**檔案**：`pages/2_資料管理.py`

**移除**：「逐筆操作」expander + 個別 record edit/delete modal

**改成**：

```python
edited_df = st.data_editor(
    df_show,
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic",
    disabled=["ID", "擁有者 ID", "建立時間", "更新時間"],
    column_config={
        "標題": st.column_config.TextColumn(required=True, max_chars=200),
        "數值": st.column_config.NumberColumn(format="%.4f", required=True),
        "類別": st.column_config.SelectboxColumn(
            options=["temperature","humidity","pressure","voltage","cpu_usage","其他"],
            required=True,
        ),
        "記錄時間": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
        "異常": st.column_config.CheckboxColumn(),
    },
    key="data_editor",
)
```

**Diff 提交**：按「儲存變更」→ diff orig vs edited → 逐筆 POST 新 row / PATCH 改 row / DELETE 缺 row + 權限 403 silent skip with toast。

**保留**：篩選 + 分頁 + CSV/JSON 批量匯入（全去 emoji）。

### 4.3 分析報表（原 Analytics）重設計

**檔案**：`pages/3_分析報表.py`

**改動**：
1. `set_page_config + title` 全中文
2. **修 timerange 圖空白 bug**（Q7）：

   **Builder 必先驗證 root cause**：
   ```bash
   TOKEN=$(curl -sX POST $BE/api/v1/auth/login -H 'Content-Type: application/json' \
     -d '{"email":"admin@example.com","password":"admin123"}' | jq -r .access_token)
   curl -s "$BE/api/v1/analytics/timerange?date_from=2026-05-20T00:00:00Z&date_to=2026-05-26T23:59:59Z&bucket=day" \
     -H "Authorization: Bearer $TOKEN" | jq .
   # buckets=[] → root cause B（tz mismatch）；buckets 有資料 → root cause C（FE 渲染）
   ```

   **預期 fix（B）**：endpoint 把 incoming datetime `.astimezone(timezone.utc).replace(tzinfo=None)` 後傳 service；或 DB column 改 `DateTime(timezone=True)` + alembic 0004。

3. **整合 unified view**（Q8）：
   - 改打 `/analytics/unified-summary`，metric cards 顯示 realtime/records/combined
   - 時間趨勢圖加 source toggle
   - 類別分佈：records 用 `/analytics/categories`；realtime 用新 `/analytics/realtime-categories`

4. 去 emoji 全清

### 4.4 即時監控重設計（Q1/Q2/Q4/Q5 核心）

**檔案**：`pages/4_即時監控.py`

1. `set_page_config + title("即時監控")` 去 emoji
2. **頁面進入即拉 history**（Q2）：
   ```python
   if not st.session_state.get("rt_history_loaded"):
       resp = client.get("/realtime/history", params={"seconds": 60})
       if resp.status_code == 200:
           for snap in resp.json().get("snapshots", []):
               ws_client.push_tick(snap)
       st.session_state["rt_history_loaded"] = True
   ```
3. **WS subscribe**（既有 `run_ws_in_background`，payload parser 對齊 wide schema）
4. **system status header**：連線狀態 + last update + active alerts
5. **告警卡（Q4，加 Δ）**：
   ```python
   for snap in recent_5:
       for metric, is_anom in snap["anomaly_flags"].items():
           if is_anom:
               value = snap[metric]
               threshold = high_threshold if value > high_threshold else low_threshold
               delta = value - threshold
               sign = "+" if delta > 0 else ""
               st.metric(
                   label=f"{metric_zh(metric)} 異常",
                   value=f"{value:.2f}",
                   delta=f"{sign}{delta:.2f}（閾值 {threshold}）",
                   delta_color="inverse",
               )
   ```
6. **折線圖（5 條線）**：每 metric 一條，異常點 circle-open red marker
7. **表格擴 60 筆 + 淡粉紅背景 + 紅字**（Q4）：
   ```python
   # Pandas Styler 套淡粉紅 row 背景
   def style_row(row):
       has_any_anom = anom_df.iloc[row.name].any()
       if has_any_anom:
           return ["background-color: #fde8e8"] * len(row)
       return [""] * len(row)
   # cell 紅字 if anomaly
   def style_cell(val, col_name, row_idx):
       if anom_df.iloc[row_idx][col_name]:
           return "color: #c0392b; font-weight: bold"
       return ""
   styled = df_display.style.apply(style_row, axis=1).apply(...)
   st.dataframe(styled, ...)
   ```
8. 移除類別 filter selectbox（wide 不需要 filter），改加「顯示哪些線」`st.multiselect`

### 4.5 系統管理（Admin）重設計（Q11, Q12）

**檔案**：`pages/5_系統管理.py`

1. `set_page_config + title` 中文化
2. 5 個 tab 去 emoji：「使用者列表 / 系統日誌 / 資料庫狀態 / 即時資料歷史 / 系統設定」

**Tab 1 使用者列表**：
- 加「角色權限說明」卡片 markdown table（admin / user / viewer × 13 個操作的 ✓/✗ 矩陣）
- 改密碼表單：admin 改任意人（不需 old）/ 改自己（含 admin）需 `old_password`

**Tab 4 即時資料歷史**：
- 改打 wide `/admin/realtime-history`
- 表格：一 row = ts + 5 metric column + anomaly_flags 拆 5 boolean
- 折線圖 5 條線（沿用 §4.4 邏輯，畫整個歷史區間）
- 移除類別 selectbox

### 4.6 Home

`Home.py`：`set_page_config(page_icon=None)`，標題保留中文。

---

## 5. UI 紀律（Q3, Q6）

### 5.1 Emoji 完全清除

**grep pattern**（builder 在 PR 前必跑）：

```bash
rg -nP '[\x{1F300}-\x{1F9FF}]|[\x{2600}-\x{27BF}]|[\x{2300}-\x{23FF}]' frontend/ backend/ \
  --glob '!*.pyc' --glob '!__pycache__'
```

**例外清單**：
- 表格內 `✓` (U+2713) / `✗` (U+2717) — 權限矩陣
- 純資料 column 名稱中文（不是 emoji）
- README / docstring 描述（不影響 UI）

**全清的位置**：set_page_config / title / subheader / header / tabs / button / expander / metric label / success / error / warning / info / caption / 「⚠️ 是」改「是」/「✅ 正常」改「正常」

### 5.2 中文標題對齊（Q6）

| 檔案 | page_title | st.title |
|---|---|---|
| `Home.py` | `即時資料分析與監控系統` | `即時資料分析與監控系統` |
| `pages/1_儀表板.py` | `儀表板 — 即時資料分析與監控系統` | `儀表板` |
| `pages/2_資料管理.py` | `資料管理 — 即時資料分析與監控系統` | `資料管理` |
| `pages/3_分析報表.py` | `分析報表 — 即時資料分析與監控系統` | `分析報表` |
| `pages/4_即時監控.py` | `即時監控 — 即時資料分析與監控系統` | `即時監控` |
| `pages/5_系統管理.py` | `系統管理 — 即時資料分析與監控系統` | `系統管理` |

### 5.3 顏色與配色（無 emoji 替代）

| 語意 | 替代 |
|---|---|
| 成功 | `st.success("...")` 綠色 callout |
| 警告 | `st.warning("...")` 黃色 callout |
| 錯誤 | `st.error("...")` 紅色 callout |
| 資訊 | `st.info("...")` 藍色 callout |
| WS 連線中 | `**串流狀態：● 連線中**`（全形圓點） |
| WS 離線 | `**串流狀態：○ 重連中**` |
| Anomaly row | Pandas Styler `background-color: #fde8e8` |
| Anomaly cell | Pandas Styler `color: #c0392b; font-weight: bold` |
| 表格 boolean | `"是"` / `"否"` 純文字 |

---

## 6. 新增 / 改動 API endpoint

### 6.1 新增 `GET /api/v1/realtime/history`

**檔案**：`backend/app/api/v1/realtime.py`（新檔）

**目的**：給任意已登入角色拿 wide snapshot 最近 N 秒歷史。

**Permission**：`AnyRole`（admin / user / viewer）

**Request**：
- `GET /api/v1/realtime/history?seconds=60`（query `seconds: int = Query(60, ge=1, le=3600)`）
- Headers: `Authorization: Bearer <JWT>`

**Response 200**：
```json
{
  "snapshots": [{"schema_version":"v2","ts":"...","temperature":25.3,"humidity":60.1,"pressure":1013.2,"voltage":12.0,"cpu_usage":42.5,"anomaly_flags":{...}}],
  "count": 60
}
```

**Errors**：401 未帶 / 422 seconds 超範圍

**實作**：
```python
@router.get("/history", response_model=RealtimeHistoryResponse)
async def realtime_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    seconds: int = Query(60, ge=1, le=3600),
) -> RealtimeHistoryResponse:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(seconds=seconds)
    stmt = (
        select(RealtimeMetricWide)
        .where(RealtimeMetricWide.ts >= cutoff)
        .order_by(RealtimeMetricWide.ts.asc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    snapshots = [RealtimeSnapshotResponse.model_validate(r) for r in rows]
    return RealtimeHistoryResponse(snapshots=snapshots, count=len(snapshots))
```

**Router**：在 `backend/app/api/v1/__init__.py` 加 `api_router.include_router(realtime_router)`。

### 6.2 新增 `PATCH /api/v1/users/{user_id}/password`（Q12）

**檔案**：`backend/app/api/v1/users.py`

**Permission**：
- admin：改任意人
- user/viewer：只能改自己

**Request**：
```json
{"new_password": "...", "old_password": "..."}
```
- `new_password` min 8
- admin 改自己 / 改別人都不需 `old_password`
- user/viewer 改自己需 `old_password`

**Schema**：
```python
class PasswordUpdateRequest(BaseModel):
    new_password: str = Field(..., min_length=8)
    old_password: str | None = None
```

**Response 200**：`{"ok": true, "updated_at": "..."}`

**Errors**：400 缺 old / 401 token / 403 非 admin 改別人 / 404 user 不存在 / 422 長度不足

**實作**（節錄）：
```python
@router.patch("/{user_id}/password")
async def update_password(user_id: int, body: PasswordUpdateRequest, db, current_user) -> dict:
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(404, "使用者不存在")
    is_self = (target.id == current_user.id)
    is_admin_acting_on_other = (current_user.role == Role.admin and not is_self)
    if not is_self and not is_admin_acting_on_other:
        raise HTTPException(403, "權限不足")
    if is_self:
        if not body.old_password:
            raise HTTPException(400, "改自己密碼需提供 old_password")
        if not verify_password(body.old_password, target.password_hash):
            raise HTTPException(400, "舊密碼錯誤")
    target.password_hash = hash_password(body.new_password)
    await db.flush()
    await db.refresh(target)
    await write_audit_log(db, action="update_password", user_id=current_user.id,
                         target_type="user", target_id=str(target.id),
                         meta={"is_self": is_self, "is_admin_change": is_admin_acting_on_other})
    return {"ok": True, "updated_at": target.updated_at.isoformat()}
```

### 6.3 修改 `GET /api/v1/admin/realtime-history`（改 wide）

**檔案**：`backend/app/api/v1/admin.py:126`

**改動**：
- query `RealtimeMetricWide`（不是 `RealtimeMetric`）
- Response 改 `PaginatedResponse[RealtimeSnapshotResponse]`
- 移除 `category` query param
- 保留 `date_from / date_to / page / size`

### 6.4 修 `GET /api/v1/analytics/timerange`（Q7）

**檔案**：`backend/app/api/v1/analytics.py:38` + `services/analytics_service.py:88`

**步驟**：
1. Builder 先 curl 驗 root cause
2. 預期 fix：incoming datetime `.astimezone(timezone.utc).replace(tzinfo=None)` 再傳 service
3. 或 `data_records.recorded_at` 改 tz-aware，加 migration 0004
4. 加 integration test

### 6.5 新增 `GET /api/v1/analytics/unified-summary`（Q8）

**目的**：統一 realtime + records 兩 source。

**Permission**：`AnyRole`

**Request**：`GET /api/v1/analytics/unified-summary?date_from=...&date_to=...&source=both|realtime|records`

**Response 200**：
```json
{
  "source": "both",
  "realtime": {"total":86400,"anomaly_count":234,"metrics":{"temperature":{"avg":25.3,"min":18.0,"max":35.1,"anomaly_count":50},...}},
  "records": {"total":200,"anomaly_count":5,"categories":[...]},
  "combined": {"total":86600,"anomaly_count":239}
}
```

**實作**：`analytics_service.get_unified_summary(db, date_from, date_to, source)` 分支 query 兩 table。

### 6.6 新增 `GET /api/v1/analytics/realtime-categories`

**目的**：給分析報表頁畫即時資料各 metric 分佈。

**Request**：`GET /api/v1/analytics/realtime-categories?date_from=...&date_to=...`

**Response 200**：
```json
{
  "metrics": [
    {"metric":"temperature","count":86400,"avg":25.3,"anomaly_count":50},
    ...
  ]
}
```

**實作**：對 `RealtimeMetricWide` 跑 5 個 metric 聚合（`func.count` / `func.avg` / `func.sum(case((flag, 1), 0))`）。

### 6.7 API contract 完整總覽

| Method | Path | Permission | Status |
|---|---|---|---|
| POST | `/auth/register` | public | 不動 |
| POST | `/auth/login` | public | 不動 |
| POST | `/auth/logout` | any | 不動 |
| GET | `/auth/me` | any | 不動 |
| GET | `/users` | admin | 不動 |
| GET | `/users/{id}` | admin | 不動 |
| PATCH | `/users/{id}` | admin | 不動 |
| DELETE | `/users/{id}` | admin | 不動 |
| **PATCH** | **`/users/{id}/password`** | **admin / self** | **新增（§6.2）** |
| GET | `/data` | any | 不動 |
| POST | `/data` | admin / user | 不動 |
| GET | `/data/{id}` | any | 不動 |
| PATCH | `/data/{id}` | admin / owner | 不動 |
| DELETE | `/data/{id}` | admin / owner | 不動 |
| POST | `/data/bulk-import` | admin / user | 不動 |
| GET | `/analytics/summary` | any | 不動 |
| **GET** | **`/analytics/timerange`** | **any** | **修 bug（§6.4）** |
| GET | `/analytics/categories` | any | 不動 |
| GET | `/analytics/export` | any | 不動 |
| **GET** | **`/analytics/unified-summary`** | **any** | **新增（§6.5）** |
| **GET** | **`/analytics/realtime-categories`** | **any** | **新增（§6.6）** |
| GET | `/admin/logs` | admin | 不動 |
| GET | `/admin/db-status` | admin | 不動 |
| **GET** | **`/admin/realtime-history`** | **admin** | **改 wide（§6.3）** |
| GET | `/admin/settings` | admin | 不動 |
| PATCH | `/admin/settings/{key}` | admin | 不動 |
| **GET** | **`/realtime/history`** | **any** | **新增（§6.1）** |
| WS | `/ws/realtime?token=...` | any | **payload 改 wide（§2.3）** |
| GET | `/health` | public | 不動 |

---

## 7. 紀律 / 編碼規範

### 7.1 禁 raw SQL

**Whitelist 例外**：
- `main.py:135` `/health` 用 `SELECT 1`
- `0002_seed_default_users_and_settings.py` 的 `INSERT IGNORE / INSERT OR IGNORE`（既有 seed migration）

**新 0003 / 0004 migration**：純 `op.create_table` / `op.add_column` / `op.alter_column`，禁 `op.execute("ALTER TABLE ...")`。

**PR check**：
```bash
rg -n 'text\(["\047].*(SELECT|INSERT|UPDATE|DELETE|ALTER|CREATE|DROP)' backend/app/ \
  --glob '!__pycache__'
# 預期 ≤ 1 match（main.py:135 /health）
```

### 7.2 禁 emoji

§5.1 grep 必跑 0 matches（除 whitelist）。

### 7.3 中文化

§5.2 表格全對齊。`pages/` 檔名用中文。

### 7.4 對齊需求文檔 5 個模組

- 模組 1 使用者管理 → §4.5 + §6.2
- 模組 2 資料管理 → §4.2
- 模組 3 即時監控 → §2, §3, §4.4, §6.1
- 模組 4 資料分析 → §4.3, §6.4–6.6
- 模組 5 系統管理 → §4.5, §6.3

### 7.5 testing 紀律

- Migration 0003/0004 必加 alembic test
- 新 endpoint 必加 pytest（happy + 4 種 error）
- WS 改 payload 必加 integration test
- FE `data_editor` 必加 Playwright smoke test
- `/analytics/timerange` 必加 integration test 防回歸

### 7.6 commit message 規範

格式：`<type>(<scope>): <subject> [Q<N>] [T<task#>]`

範例：
- `feat(backend): add realtime_metrics_wide table [Q5,Q10] [T-B1-1]`
- `fix(frontend): remove emoji from page titles [Q3] [T-D2-1]`
- `fix(backend): analytics_timerange tz-aware date filter [Q7] [T-C3-1]`
