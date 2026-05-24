# 系統架構

## 整體拓樸

```mermaid
flowchart LR
  subgraph Client
    U[使用者瀏覽器]
  end
  subgraph Frontend [Streamlit :8501]
    S[多頁面 App<br/>Home / Dashboard / Data / Analytics / Realtime / Admin]
  end
  subgraph Backend [FastAPI :8000]
    R["REST /api/v1/*<br/>auth / users / data / analytics / admin"]
    W["WebSocket /ws/realtime"]
    SCH["APScheduler<br/>tick 1s + flush 5s"]
    Q[(asyncio.Queue)]
  end
  subgraph Data
    DB[(MariaDB 11.7)]
  end
  U -->|HTTPS| S
  S -->|httpx + JWT Bearer| R
  S -->|websockets + JWT query| W
  R <-->|SQLAlchemy async + asyncmy| DB
  SCH -->|generate tick| W
  SCH -->|enqueue| Q
  Q -->|batch flush| DB
  W -.broadcast.-> S
```

## 角色與資料流

```mermaid
sequenceDiagram
  autonumber
  actor Admin
  actor User
  participant Frontend
  participant Backend
  participant DB as MariaDB
  participant Scheduler as APScheduler

  User->>Frontend: 開啟登入頁
  Frontend->>Backend: POST /api/v1/auth/login
  Backend->>DB: SELECT user WHERE email
  Backend-->>Frontend: JWT + user role
  Frontend->>Frontend: 存 session_state.token

  User->>Frontend: 上傳 CSV (bulk import)
  Frontend->>Backend: POST /api/v1/data/bulk-import multipart
  Backend->>Backend: csv_importer 逐行 validate
  Backend->>DB: INSERT valid records
  Backend-->>Frontend: {inserted, failed, errors}

  Scheduler-->>Backend: tick (每 1 秒)
  Backend->>Backend: 隨機生成 RealtimeTick + 判斷 anomaly
  Backend->>Frontend: WebSocket broadcast tick
  Frontend->>Frontend: Plotly 即時更新

  Scheduler-->>Backend: flush (每 5 秒)
  Backend->>DB: BATCH INSERT realtime_metrics

  Admin->>Frontend: 改異常閾值
  Frontend->>Backend: PATCH /api/v1/admin/settings/anomaly_threshold_high
  Backend->>DB: UPDATE app_settings
  Backend->>Backend: realtime_service.reload_thresholds()
  Note over Scheduler,Backend: 下一個 tick 即生效
```

## 資料庫 Schema（ER）

```mermaid
erDiagram
    USERS ||--o{ DATA_RECORDS : "owns"
    USERS ||--o{ AUDIT_LOGS : "performs"

    USERS {
        int id PK
        string email UK
        string password_hash
        enum role "admin/user/viewer"
        string display_name
        bool is_active
        datetime created_at
        datetime updated_at
    }
    DATA_RECORDS {
        int id PK
        string title
        decimal value
        string category
        datetime recorded_at
        bool is_anomaly
        int owner_id FK
        datetime created_at
        datetime updated_at
    }
    REALTIME_METRICS {
        bigint id PK
        decimal value
        string category
        datetime ts
        string source
        bool is_anomaly
    }
    AUDIT_LOGS {
        bigint id PK
        int user_id FK
        string action
        string target_type
        string target_id
        json meta
        datetime ts
    }
    APP_SETTINGS {
        int id PK
        string key UK
        string value
        string description
        datetime updated_at
    }
```

## Docker 拓樸

```mermaid
flowchart TB
  subgraph compose [docker-compose]
    direction TB
    M[mariadb:11.7<br/>healthcheck]
    B[backend<br/>multi-stage Dockerfile<br/>uvicorn --workers 1]
    F[frontend<br/>multi-stage Dockerfile<br/>streamlit]
  end
  V[(volume<br/>mariadb_data)]
  N[network<br/>app_network bridge]
  M -.uses.-> V
  M -.attaches.-> N
  B -.attaches.-> N
  F -.attaches.-> N
  B -->|depends_on healthy| M
  F -->|depends_on healthy| B
```

## 模組責任邊界

| 模組 | 入口 | 主要檔案 | 對外 |
|---|---|---|---|
| 使用者管理 | `/api/v1/auth/*` + `/api/v1/users/*` | `app/services/auth_service.py` | JWT token + UserResponse |
| 資料管理 | `/api/v1/data/*` | `app/services/data_service.py` + `app/utils/csv_importer.py` | CRUD / bulk import |
| 即時監控 | `/ws/realtime` + `/api/v1/admin/realtime-history` | `app/services/realtime_service.py` + `app/core/ws_manager.py` + `app/services/batch_writer.py` | WebSocket push + DB 批次寫入 |
| 資料分析 | `/api/v1/analytics/*` | `app/services/analytics_service.py` + `app/utils/excel_exporter.py` | 統計 JSON + Excel 串流 |
| 系統管理 | `/api/v1/admin/*` | `app/api/v1/admin.py` | 使用者 / 日誌 / DB 狀態 / 設定 |
