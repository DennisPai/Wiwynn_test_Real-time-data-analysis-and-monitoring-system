# 即時資料分析與監控系統

完整 SaaS 雛形：FastAPI 後端 + Streamlit 前端 + MariaDB + Docker Compose，五大模組涵蓋使用者管理、資料 CRUD、即時 WebSocket 推送、分析報表、系統管理。

## 資料模型設計（Wide Schema）

每筆 `data_records` row 同時承載 5 個 metric 的 snapshot（temperature / humidity / pressure / voltage / cpu_usage），搭配 `anomaly_flags` JSON 欄位記錄 per-metric 異常標記。設計重點：

- **單筆 row = 一個時間點的多 metric snapshot**：避免長表 join 開銷，分析查詢直接走單表聚合
- **`anomaly_flags` 為 per-metric bool dict**：5 key（temperature / humidity / pressure / voltage / cpu_usage）完整、不得多 key；單筆 row 可同時標記多個 metric 異常
- **CHECK constraint 強制至少 1 metric 非 NULL**：DB 層阻擋空 row，搭配 Pydantic `at_least_one_metric` validator 雙重保險
- **`source` 區分資料來源**：`user`（人工 / CSV import）vs `simulator`（即時模擬器）
- **Design Evolution**：long format（title / value / category 單 metric per row）→ unified wide schema（多 metric per row + per-metric anomaly breakdown），便於多 metric 同時段比對與閾值微調

## 功能模組

| 模組 | 重點功能 |
|---|---|
| 使用者管理 | 註冊 / 登入（JWT）/ 登出 / 個人資料；3 級角色（Admin / User / Viewer）+ RBAC |
| 資料管理 | Wide schema CRUD（含分頁 / 來源 / metric range 篩選 / 排序）/ CSV + JSON 批量匯入（含逐行錯誤回報 + missing_columns 細項）/ 權限：擁有者或 Admin |
| 即時監控 | APScheduler 每秒生成模擬資料 → WebSocket 即時推送 → 前端 Plotly 折線圖即時更新 / per-metric 異常閾值標記 |
| 資料分析 | 統計（總計 / 平均 / 最大 / 最小）/ 時間範圍查詢（小時 / 日 bucket）/ per-metric 聚合 / Excel 匯出 |
| 系統管理（Admin）| 使用者列表 / 系統日誌 / DB 連線池狀態 / 即時資料歷史查詢 / 動態調整 per-metric 異常閾值 |

## 技術棧

| 層 | 技術 |
|---|---|
| 後端 | FastAPI 0.115 / SQLAlchemy 2.0 async / asyncmy / Alembic / Pydantic v2 / APScheduler / python-jose（JWT）/ passlib bcrypt / structlog |
| 前端 | Streamlit 1.39 / Plotly 5.24 / httpx / websockets |
| 資料庫 | MariaDB 11.7 |
| 容器 | Docker 多階段建置 + Docker Compose v2（healthcheck + volume + 私網）|
| 程式語言 | Python 3.12 |

## 系統架構

詳見 [docs/architecture.md](docs/architecture.md)（mermaid 拓樸圖、序列圖、ER 圖、Docker 結構）。

## 快速開始（本地 Docker Compose）

> **預設部署方式**：本地 docker compose。三個指令啟動全部服務，無需設定雲端帳號。

### 1. 必備

- Docker 24+
- Docker Compose v2
- （非必要）本機 Python 3.12 用於開發測試

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env：至少改 JWT_SECRET_KEY（openssl rand -hex 32）與 DB 密碼
# 其餘欄位使用 .env.example 預設值即可在本地運作
```

### 3. 啟動

```bash
docker compose up -d --build
```

### 4. 等待服務就緒

```bash
docker compose ps
# 等三個 service 都顯示 healthy（約 30-60 秒）
```

### 5. 開啟介面

| 介面 | URL |
|---|---|
| 前端 Streamlit | http://localhost:8501 |
| 後端 Swagger UI | http://localhost:8000/docs |
| 後端 ReDoc | http://localhost:8000/redoc |
| 健康檢查 | http://localhost:8000/health |

> docker-compose.yml 已設定容器間通訊（backend service name = `backend`），
> 前端容器自動以 `http://backend:8000` 連接後端，本地開發者不需手動設 BACKEND_URL。

## 測試帳號

首次啟動 alembic seed 自動建立：

| 角色 | Email | 密碼 |
|---|---|---|
| Admin | admin@example.com | admin123 |
| User | user@example.com | user123 |
| Viewer | viewer@example.com | viewer123 |

正式環境部署請務必先改密碼。

## API 文件

完整 API 規格自動產生在 http://localhost:8000/docs（Swagger UI）與 http://localhost:8000/redoc（ReDoc）。

主要 endpoint 分類：

| Prefix | 用途 |
|---|---|
| `/api/v1/auth/*` | 註冊 / 登入 / 登出 / 取得個人資料 |
| `/api/v1/users/*` | 使用者管理（admin 限定） |
| `/api/v1/data/*` | Wide schema 資料 CRUD + 批量匯入 + anomaly preview |
| `/api/v1/analytics/*` | 統計分析 + Excel 匯出 |
| `/api/v1/admin/*` | 系統管理（日誌 / DB 狀態 / per-metric 閾值設定 / 即時歷史）|
| `/ws/realtime` | WebSocket 即時推送（query string 帶 `token=<JWT>`）|
| `/health` | 健康檢查（給 docker healthcheck）|

### 常用 endpoint 速查（curl 範例）

```bash
# Login → 拿 token
TOKEN=$(curl -s -X POST $BE/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin123"}' | jq -r .access_token)

# 建立單筆資料（wide schema：ts 必填、5 metric 至少 1 個非 null）
# anomaly_flags 不傳時，後端 anomaly_detector 會依目前閾值自動填 per-metric bool
curl -X POST $BE/api/v1/data \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "ts": "2026-05-26T08:00:00Z",
    "temperature": 25.3,
    "humidity": 67.8,
    "pressure": 1014.2,
    "voltage": 12.05,
    "cpu_usage": 48.6,
    "source": "user",
    "note": "manual sample"
  }'

# 回傳 (wide schema 13 欄)：
# {
#   "id": 1,
#   "ts": "2026-05-26T08:00:00Z",
#   "temperature": "25.3000",
#   "humidity": "67.8000",
#   "pressure": "1014.2000",
#   "voltage": "12.0500",
#   "cpu_usage": "48.6000",
#   "anomaly_flags": {"temperature": false, "humidity": false, "pressure": false, "voltage": false, "cpu_usage": false},
#   "source": "user",
#   "note": "manual sample",
#   "owner_id": 1,
#   "created_at": "2026-05-26T08:00:01Z",
#   "updated_at": "2026-05-26T08:00:01Z"
# }

# 列出資料（wide schema query params：sources / metric range / 時間範圍）
curl "$BE/api/v1/data?sources=user&sources=simulator&metric=temperature&min_value=80&max_value=120&sort_by=ts&sort_order=desc&page=1&size=20" \
  -H "Authorization: Bearer $TOKEN"

# CSV 批量匯入（wide CSV，端點是 bulk-import 不是 import）
curl -X POST $BE/api/v1/data/bulk-import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@docs/sample_data.csv"

# Anomaly preview：上傳 CSV 預覽哪幾列在現有閾值下會被標記，不寫入 DB
curl -X POST $BE/api/v1/data/anomaly-preview \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@docs/sample_data.csv"

# Analytics 時間範圍查詢（參數是 date_from / date_to，ISO8601）
curl "$BE/api/v1/analytics/timerange?date_from=2026-05-01T00:00:00&date_to=2026-05-31T23:59:59" \
  -H "Authorization: Bearer $TOKEN"

# Admin 動態調整 per-metric 異常閾值（key 名為 anomaly_{metric}_high / anomaly_{metric}_low）
curl -X PATCH $BE/api/v1/admin/settings/anomaly_temperature_high \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"value":"80.0"}'

# WebSocket 即時推送（token 走 query string）
# wss://<BE_HOST>/ws/realtime?token=<JWT>
```

## 範例資料

匯入流程：登入 → Data 頁面 → 上傳 CSV → 選 `docs/sample_data.csv`（wide format，跨多日，含 per-metric 異常範例）。

**CSV 欄位**（wide schema）：

```
ts,temperature,humidity,pressure,voltage,cpu_usage,anomaly_flags,source,note,owner_email
```

| 欄位 | 必填 | 說明 |
|---|:-:|---|
| `ts` | ✅ | UTC 時間戳（ISO8601，建議帶 `Z` 或 `+00:00`）|
| `temperature` / `humidity` / `pressure` / `voltage` / `cpu_usage` | 5 取 1 | 5 個 metric，至少 1 個非空。空白會被視為 NULL |
| `anomaly_flags` | 選填 | JSON 字串（5 key bool dict）。**留空時後端 anomaly_detector 會依目前閾值自動計算** |
| `source` | 選填 | `user`（預設）或 `simulator` |
| `note` | 選填 | 自由文字備註，最長 200 字 |
| `owner_email` | 選填 | 僅 admin 可指定；user 角色填了會被擋。空白時 owner = 登入者 |

> JSON 批量匯入也支援（副檔名 `.json`），結構為 `[{...}, {...}]` 一行一筆。
> bulk-import 偵測到舊 long header（`title,value,category,...`）會整檔拒絕，避免誤匯入。

## 本地開發（不走 Docker）

```bash
# 後端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 啟 MariaDB（用 Docker 跑）
docker run --rm -d --name maria11 -e MARIADB_ROOT_PASSWORD=root -e MARIADB_DATABASE=monitoring \
    -e MARIADB_USER=app_user -e MARIADB_PASSWORD=apppw -p 3306:3306 mariadb:11.7

# 設環境變數
export DATABASE_URL=mysql+asyncmy://app_user:apppw@127.0.0.1:3306/monitoring
export JWT_SECRET_KEY=$(openssl rand -hex 32)

# 跑 migration + 啟 server
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 另開 terminal 跑前端
cd frontend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BACKEND_URL=http://localhost:8000 BACKEND_WS_URL=ws://localhost:8000
streamlit run streamlit_app/Home.py
```

## 執行測試

```bash
cd backend
pytest -v --cov=app
```

## 資料庫遷移

```bash
cd backend
alembic revision --autogenerate -m "add new column"   # 自動產生
alembic upgrade head                                   # 套用未跑的
alembic downgrade -1                                   # 退回上一版
```

## 角色權限矩陣摘要

| 動作 | Admin | User | Viewer |
|---|:-:|:-:|:-:|
| 看資料 | ✅ | ✅ | ✅ |
| 建立 / 匯入資料 | ✅ | ✅ | ❌ |
| 改 / 刪資料 | ✅（任何）| ✅（僅自己）| ❌ |
| 看分析報表 / 匯出 | ✅ | ✅ | ✅ |
| 系統管理 / 日誌 / 設定 | ✅ | ❌ | ❌ |
| 即時 WebSocket | ✅ | ✅ | ✅ |

## 目錄結構

```
.
├── README.md
├── .env.example
├── docker-compose.yml
├── docs/
│   ├── architecture.md
│   └── sample_data.csv
├── backend/                  # FastAPI + SQLAlchemy + Alembic
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini, alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── api/v1/
│   │   ├── core/
│   │   ├── services/
│   │   └── utils/
│   └── tests/
└── frontend/                 # Streamlit
    ├── Dockerfile
    ├── requirements.txt
    └── streamlit_app/
        ├── Home.py
        ├── pages/
        ├── api_client.py
        ├── auth.py
        └── ws_client.py
```

## 部署考量

- 預設使用 `uvicorn --workers 1`，因 APScheduler 採 in-process 排程，水平擴展需改 Redis-backed scheduler
- JWT secret 須以 `openssl rand -hex 32` 產生，啟動時若長度 < 32 直接 raise
- CORS 預設只允許 `http://localhost:8501`，部署到其他網域需更新 `CORS_ORIGINS`
- 時間欄位一律 UTC 存 + ISO8601 帶 timezone，前端顯示時 `tz_convert("Asia/Taipei")`

## 雲端部署（進階選用）

> 本節為選用章節。主要使用情境：本地 docker compose 已驗證正常後，要將系統部署到雲端服務。
> 以 Zeabur 為範例，其他平台（Render / Railway / Fly.io）概念相同。

### 後端（Zeabur / Render / Railway / Fly.io 等容器平台）

服務根目錄選 `/backend`，build 使用 `backend/Dockerfile`。**必填** env 變數：

| Env | 範例值 | 說明 |
|---|---|---|
| `DATABASE_URL` | `mysql+asyncmy://user:pass@mariadb.internal:3306/monitoring` | 完整連線字串。`mysql://` 與 `mariadb://` 開頭會自動補 `+asyncmy` driver。**有設此變數時 DB_HOST/DB_PORT 等會被忽略** |
| `JWT_SECRET_KEY` | （`openssl rand -hex 32` 產生）| 至少 32 字元，否則啟動 raise |
| `CORS_ORIGINS` | `https://your-frontend-domain.zeabur.app` | 改成你前端部署網域，逗號分隔可多個 |
| `APP_ENV` | `production` | |
| `LOG_LEVEL` | `INFO` | |

選填（有預設值）：`JWT_EXPIRE_MINUTES` / `REALTIME_TICK_SECONDS` / `BATCH_FLUSH_SECONDS` / `ANOMALY_THRESHOLD_HIGH` / `ANOMALY_THRESHOLD_LOW` / `SEED_*`。

#### Zeabur 特別注意

1. **必先 deploy MariaDB 服務**（Zeabur Templates 找 MariaDB 或 MySQL 8）
2. backend 服務的 env 設 `DATABASE_URL`，引用 MariaDB 服務的內部 DNS：
   ```
   DATABASE_URL=mysql+asyncmy://${MARIADB_USERNAME}:${MARIADB_PASSWORD}@${MARIADB_HOST}:${MARIADB_PORT}/${MARIADB_DATABASE}
   ```
   （Zeabur 會把連結的 MariaDB 服務變數注入 env，名稱依模板可能是 `MYSQL_*` 或 `MARIADB_*`，依實際提示調整）
3. backend 容器啟動會自動跑 `alembic upgrade head` 建表 + seed 三個測試帳號
4. backend 對外 port 8000，需要在 Zeabur 開放 HTTP 路由

### 前端（Zeabur 第二個服務）

服務根目錄選 `/frontend`，build 使用 `frontend/Dockerfile`。

**前端雲端部署必填 env 變數（缺少將導致連線失敗）：**

| Env | 範例值 | 說明 |
|---|---|---|
| `BACKEND_URL` | `https://your-backend.zeabur.app` | 後端公開 URL（HTTPS）|
| `BACKEND_WS_URL` | `wss://your-backend.zeabur.app` | WebSocket URL（注意是 `wss://` 不是 `ws://`）|

> **重要**：前端程式碼若未設 `BACKEND_URL` 和 `BACKEND_WS_URL`，
> fallback 為 `http://localhost:8000` 和 `ws://localhost:8000`。
> 雲端環境中 localhost 指向容器本身（非後端服務），因此**這兩個 env var 在雲端環境為必填**。

前端對外 port 8501（Streamlit 預設）。

## 授權

MIT
