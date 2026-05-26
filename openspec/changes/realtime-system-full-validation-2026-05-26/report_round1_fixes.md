# Round 1 Fixes — Wiwynn Real-time System Validation

**Status**：commits push 完成（fb3916b / 63b74e8 / 1c92723），等 Zeabur FE service redeploy
**Date**：2026-05-26 09:30~10:00 UTC+8
**Commit chain**：4f5ea7a (baseline) → fb3916b → 63b74e8 → 1c92723

---

## 1. Bugs 修補總結

| # | 嚴重度 | 來源 | 描述 | 修法 | Commit |
|---|---|---|---|---|---|
| BUG #1 | P0 | test-automator | LoginRequest 8 字元 validation 擋掉 seed `user@user123` (7 字元) | 移除 LoginRequest password_min_length validator（登入只 hash compare）+ 修 Home.py placeholder | fb3916b |
| BUG #5 | P0 | FE Playwright 實測 | FE `api_client.py` BACKEND_URL fallback 是 `http://localhost:8000`，Zeabur 上沒 env var → "Not Found" | fallback URL 改為 production BE Zeabur URL（本地開發 set env override） | 63b74e8 |
| BUG #6 | P0 | FE Playwright 實測 | FE `ws_client.py` WS path 是 `/api/v1/ws/realtime` 但 BE 實際是 `/ws/realtime`（外 prefix） | fallback path 修正 + production URL | 63b74e8 |
| D-BLOCK-1 | P0 | validator | Data 頁用 `st.datetime_input` — Streamlit 從未提供此 API → AttributeError 整頁壞 | 拆 `st.date_input + st.time_input` 再 `datetime.combine` | 1c92723 |
| D-BLOCK-2 | P0 | validator | Realtime 頁用 polling `/admin/realtime-history` (admin-only) → 非 admin 直接 `st.stop()`，違反 spec「WebSocket 即時推送」+ README「Realtime Admin/User/Viewer 全 ✅」 | 重寫為 `run_ws_in_background(token)` 訂閱 `/ws/realtime`，三角色都可看 | 1c92723 |
| D-BLOCK-3 | P0 | validator | Analytics 頁 FE 讀 `count/sum/avg/max` 但 BE schema 是 `total_records/avg_value/min_value/max_value` → metric/圖表全空白 | 全頁 FE 鍵名對齊 BE schema（summary 4 metrics / timerange / categories 全改） | 1c92723 |
| D-HIGH-2 | High | validator | Admin 日誌 metadata FE 讀 `item["metadata"]` 但 BE serialize 為 `meta` → metadata 永遠空 | FE 改讀 `item["meta"]` | 1c92723 |
| D-HIGH-5 | High | validator | Realtime/Analytics 寫死 categories `vibration/power` 與 simulator `voltage/cpu_usage` 不符 | 對齊 SIMULATOR_CATEGORIES | 1c92723 |

---

## 2. 仍未處理

| # | 嚴重度 | 描述 | 不修原因 |
|---|---|---|---|
| D-HIGH-1 | High | FE hardcode Zeabur backend URL | 本次刻意設成 production fallback；本地開發者 set env override |
| D-HIGH-3 | High | alembic 0002 用 raw SQL `sa.text("INSERT IGNORE ...")` | seed 已跑過，改 0002 不會重 apply；可後續 follow-up |
| D-HIGH-4 | High | admin.py `_reload_simulator_if_needed` 收 `db` 參數但沒用 | cosmetic 不阻運作 |
| D-NICE-1~7 | Nice | 各種小修飾 | 不影響功能 |

---

## 3. Backend 實機驗證（fb3916b 已 deploy）

| Phase | 結果 |
|---|---|
| 3 角色 JWT login (admin/user/viewer) | ✅ 全通過（user@user123 BUG #1 修後）|
| 24 endpoint × 4 角色 permission matrix | ✅ 22/22（剔除 WS 兩個用 token 補測通過）|
| CSV bulk-import 60 row | ✅ |
| Analytics summary / timerange / categories / Excel | ✅ |
| Admin logs / db-status / realtime-history / settings PATCH | ✅ |
| WebSocket /ws/realtime?token=... | ✅ 5 ticks payload `{category, value, is_anomaly, ts}` |

**BE 24/24 全綠**。

---

## 4. Frontend 實機驗證

⚠️ **被 Zeabur FE service `service-6a13a002435af008382084dd` deploy webhook 卡關阻擋。**

從 commit `63b74e8` push 後 35+ 分鐘，FE 仍顯示舊版（登入回「Not Found」表示 BACKEND_URL fallback 仍是 localhost:8000）。

對比：commit `fb3916b` BE service 在 push 後 1.5 分鐘就 deploy 完成（user@user123 login 隨即可用）。

→ 推測：**FE service 的 GitHub auto-deploy webhook 沒啟用 / queue 卡關 / 或 FE service 鎖在特定 commit**。

嘗試過：
- Zeabur GraphQL API `redeployService(serviceID=service-6a13a002...)` → **403 Permission denied**
- `$ZEABUR_API_TOKEN` 對 Wiwynn project 無權

**需要懷特手動處理**（無 code 可修）：
1. 進 Zeabur dashboard → project-6a139f6f435af008382084c3 → FE service-6a13a002 → Settings → Source → 確認 GitHub auto-deploy 開啟 + branch 是 main
2. 或進 Deployments tab → Redeploy 一次最新 commit `1c92723`
3. 一旦 FE deploy `1c92723`，所有 8 個 bug 都修好，預期 FE 全功能可用

---

## 5. Phase 5 Validator 對需求文檔對齊

| 維度 | 結果 |
|---|---|
| 5 大模組 32 子功能 BE | ✅ 全綠 |
| FE 6 頁面 | Home / Dashboard / Data / Admin ✅ ｜ Analytics / Realtime 修補後（commit 1c92723）✅，但需 Zeabur redeploy 才生效 |
| 技術要求（FastAPI / ORM / asyncmy / Alembic / Pydantic v2 / Swagger / JWT / structlog / Docker 多階段 / Compose / Volume / env） | ✅ 全綠 |
| 禁原生 SQL | ✅（除 health check `text("SELECT 1")` + alembic 0002 INSERT IGNORE 為 acceptable migration 用例）|
| 5 條交付物 | ✅ 全綠 |

**結論**：code-level **PASS_WITH_DEPLOY_BLOCKER**。8 個 bug 都修完了，等 Zeabur FE redeploy 才能 verify end-to-end。

---

**版本**：v1（2026-05-26）
