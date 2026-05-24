# 即時資料分析與監控系統

完整 SaaS 雛形：FastAPI 後端 + Streamlit 前端 + MariaDB + Docker Compose，五大模組涵蓋使用者管理、資料 CRUD、即時 WebSocket 推送、分析報表、系統管理。

## 功能模組

| 模組 | 重點功能 |
|---|---|
| 使用者管理 | 註冊 / 登入（JWT）/ 登出 / 個人資料；3 級角色（Admin / User / Viewer）+ RBAC |
| 資料管理 | CRUD（含分頁 / 篩選 / 排序）/ CSV + JSON 批量導入（含逐行錯誤回報）/ 權限：擁有者或 Admin |
| 即時監控 | APScheduler 每秒生成模擬資料 → WebSocket 即時推送 → 前端 Plotly 折線圖即時更新 / 超閾值異常標記 |
| 資料分析 | 統計（總計 / 平均 / 最大 / 最小）/ 時間範圍查詢（小時 / 日 bucket）/ 分類聚合 / Excel 匯出 |
| 系統管理（Admin）| 使用者列表 / 系統日誌 / DB 連線池狀態 / 即時資料歷史查詢 / 動態調整異常閾值 |

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

## 快速開始（Docker Compose）

### 1. 必備

- Docker 24+
- Docker Compose v2
- （非必要）本機 Python 3.12 用於開發測試

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env：至少改 JWT_SECRET_KEY（openssl rand -hex 32）與 DB 密碼
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
| `/api/v1/data/*` | 資料 CRUD + 批量匯入 |
| `/api/v1/analytics/*` | 統計分析 + Excel 匯出 |
| `/api/v1/admin/*` | 系統管理（日誌 / DB 狀態 / 設定 / 即時歷史）|
| `/ws/realtime` | WebSocket 即時推送（query string 帶 `token=<JWT>`）|
| `/health` | 健康檢查（給 docker healthcheck）|

## 範例資料

匯入流程：登入 → Data 頁面 → 上傳 CSV → 選 `docs/sample_data.csv`（60 筆，5 個 category，跨 7 天，含 9 筆高異常 + 5 筆低異常）。

CSV 欄位：`title,value,category,recorded_at`

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

## 授權

MIT
