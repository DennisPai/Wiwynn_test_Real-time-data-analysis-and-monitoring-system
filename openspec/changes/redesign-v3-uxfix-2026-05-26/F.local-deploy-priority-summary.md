# F. Local Deploy Priority — Frontend Summary

**Date**: 2026-05-26
**Agent**: frontend-engineer
**Status**: DONE

---

## 改動清單

### 1. `frontend/streamlit_app/api_client.py`

**改動位置**: line 1-17（module docstring + fallback URL 定義）

**Before**:
```python
"""
API Client：封裝對後端 HTTP 請求。
"""
...
_BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "https://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app",
).rstrip("/")
# 本地開發者請設 BACKEND_URL=http://localhost:8000 override
```

**After**:
```python
"""
API Client：封裝對後端 HTTP 請求。

BACKEND_URL 優先順序：
1. 環境變數 BACKEND_URL（所有部署環境皆推薦顯式設定）
2. fallback：http://localhost:8000（本地 docker compose 預設 BE port）
...雲端必設 BACKEND_URL env var 說明...
"""
...
_BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "http://localhost:8000",
).rstrip("/")
```

**原因**: Round 1 BUG #5 修補時改成 Zeabur production URL，違反「本地部屬為主」原則。
Zeabur 生產環境有設 BACKEND_URL env var，故改回 localhost 不影響 production。

---

### 2. `frontend/streamlit_app/ws_client.py`

**改動位置**: line 1-53（module docstring + `_resolve_ws_url()` fallback 邏輯）

**Before**:
```python
def _resolve_ws_url() -> str:
    """...都沒有則使用 production fallback"""
    raw = os.environ.get("BACKEND_WS_URL") or os.environ.get("WS_URL")
    if not raw:
        return "wss://wiwynn-test-real-time-data-analysis-and-monitoring-backend.zeabur.app/ws/realtime"
```

**After**:
```python
def _resolve_ws_url() -> str:
    """...都沒有則使用本地 localhost fallback（本地 docker compose 預設）"""
    raw = os.environ.get("BACKEND_WS_URL") or os.environ.get("WS_URL")
    if not raw:
        return "ws://localhost:8000/ws/realtime"
```

**原因**: 同 api_client.py。ws_client.py fallback 從 wss://zeabur.app 改回 ws://localhost:8000。
Zeabur 生產環境有設 BACKEND_WS_URL=wss://...，故此改動不影響 production。

---

### 3. `.env.example`

**改動**: 完整重寫，本地方式 B 在前、雲端方式 A 在後。

**Before 結構**:
- line 1-4: 方式 A（DATABASE_URL 完整 URL，標為雲端慣例）在前，但被 comment 掉
- line 5-12: 方式 B（拆欄位）在後
- 沒有明確標示哪種是「主要」
- 沒有 BACKEND_URL / BACKEND_WS_URL 本地值

**After 結構**:
- 頂部明確說明「本地開發者只需 3 步驟」
- 方式 B（拆欄位）標為「本地部屬預設（推薦）」在前
- 新增 `BACKEND_URL=http://localhost:8000`、`BACKEND_WS_URL=ws://localhost:8000`、`STREAMLIT_SERVER_PORT=8501` 本地值
- 方式 A（完整 URL）標為「雲端部屬選用」在後，全部 comment 掉
- 明確警告：雲端環境 BACKEND_URL/BACKEND_WS_URL 為必填，否則連線失敗

---

### 4. `README.md`

**改動位置**: 兩個章節標題與內文

**「快速開始」章節** (原 line 29):
- 標題由「快速開始（Docker Compose）」改為「快速開始（本地 Docker Compose）」
- 加副標題「預設部署方式：本地 docker compose」
- step 2 說明更清楚：「其餘欄位使用 .env.example 預設值即可在本地運作」
- 章節底部加說明：docker-compose.yml 容器間通訊機制，本地開發者不需手動設 BACKEND_URL

**「雲端部署」章節** (原 line 225):
- 標題由「雲端部署（前後端分開）」改為「雲端部署（進階選用）」
- 加副標題：「本節為選用章節，主要使用情境：本地 docker compose 已驗證後再部署到雲端」
- 前端環境變數表格後加重要提示：
  > BACKEND_URL 和 BACKEND_WS_URL 在雲端環境為必填，fallback 為 localhost，雲端必然失敗

---

## docker-compose.yml 確認（無需修改）

已確認 docker-compose.yml 本地容器間通訊正確：
- `backend.environment.DB_HOST: mariadb` — 容器間 DB 連線走 service name
- `backend.environment.DATABASE_URL: mysql+asyncmy://${DB_USER}:${DB_PASSWORD}@mariadb:3306/${DB_NAME}` — 覆寫任何 .env 中可能的值
- `frontend.environment.BACKEND_URL: http://backend:8000` — 覆寫 .env 中的 localhost 值
- `frontend.environment.BACKEND_WS_URL: ws://backend:8000` — 覆寫 .env 中的 localhost 值

三層覆寫關係：`docker-compose environment` > `.env` > `程式碼 fallback`，本地 docker compose 全程走容器間 service name，不受 .env fallback 影響。

---

## 驗收標準對齊

| 標準 | 結果 |
|---|---|
| `cp .env.example .env` + 改密碼 + `docker compose up -d --build` → 本地全 service running | 架構正確：compose 覆寫容器間通訊，.env.example 已有所有必要欄位 |
| README「快速開始」第一節是本地部屬 | 是，標題「快速開始（本地 Docker Compose）」 |
| README「雲端部屬」是後置 Advanced 章節 | 是，標題「雲端部署（進階選用）」 |
| `grep wiwynn-test-real-time-data` 在 api_client/ws_client/.env.example 為 0 | 通過，grep 結果 ZERO MATCHES |
| Zeabur 生產環境因已設 BACKEND_URL/BACKEND_WS_URL，改不 break production | 正確：生產 env var 優先，不受 fallback 影響 |

---

## Edge Case 處理

1. **非 compose 場景（直接 `streamlit run`）**: fallback 到 `localhost:8000`，符合開發者直接跑 backend + frontend 時的期望
2. **compose 場景**: docker-compose.yml `environment` 段覆寫，frontend 用 `http://backend:8000`（service name），不走 fallback
3. **Zeabur 雲端**: 平台後台 env var 覆寫，完全不受 fallback 影響
4. **WS URL 路徑自動補全**: `_resolve_ws_url()` 邏輯保留，只給 base URL 會自動補 `/ws/realtime`
