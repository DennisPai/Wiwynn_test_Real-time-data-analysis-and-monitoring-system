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

  User->>Frontend: 上傳 wide CSV (bulk import)
  Frontend->>Backend: POST /api/v1/data/bulk-import multipart
  Backend->>Backend: csv_importer 解析 header<br/>偵測舊 long header → 整檔拒絕
  Backend->>Backend: 逐行 validate (ts 必填 + 5 metric 至少 1 非 NULL)
  Backend->>Backend: anomaly_detector 依目前閾值<br/>per-metric 自動填 anomaly_flags
  Backend->>DB: INSERT valid wide records
  Backend-->>Frontend: {inserted, failed, errors[{row, reason, missing_columns}]}

  Scheduler-->>Backend: tick (每 1 秒)
  Backend->>Backend: simulator 生成 5 metric snapshot<br/>+ anomaly_detector 判斷 per-metric flag
  Backend->>Frontend: WebSocket broadcast tick
  Frontend->>Frontend: Plotly 即時更新

  Scheduler-->>Backend: flush (每 5 秒)
  Backend->>DB: BATCH INSERT realtime_metric_wide

  Admin->>Frontend: 改 per-metric 異常閾值
  Frontend->>Backend: PATCH /api/v1/admin/settings/anomaly_temperature_high
  Backend->>DB: UPDATE app_settings
  Backend->>Backend: anomaly_detector.reload_thresholds()
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
        bigint id PK
        datetime_tz ts "UTC timestamp"
        decimal temperature "nullable"
        decimal humidity "nullable"
        decimal pressure "nullable"
        decimal voltage "nullable"
        decimal cpu_usage "nullable"
        json anomaly_flags "per-metric bool dict (5 keys)"
        string source "user / simulator"
        string note "nullable, max 200"
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
    REALTIME_METRIC_WIDE {
        bigint id PK
        datetime_tz ts "UTC timestamp"
        decimal temperature "nullable"
        decimal humidity "nullable"
        decimal pressure "nullable"
        decimal voltage "nullable"
        decimal cpu_usage "nullable"
        json anomaly_flags "per-metric bool dict (5 keys)"
        string source "simulator default"
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

> **Wide schema 設計重點**
> - `DATA_RECORDS` 採 wide format：每筆 row 同時承載 5 metric snapshot，搭配 `anomaly_flags` JSON 做 per-metric 異常標記。
> - **CHECK constraint `ck_data_records_at_least_one_metric`**：強制 `temperature / humidity / pressure / voltage / cpu_usage` 至少 1 個非 NULL，DB 層阻擋空 row。
> - `anomaly_flags` 為 5 key 完整 bool dict（temperature / humidity / pressure / voltage / cpu_usage），由 `anomaly_detector` 依 `APP_SETTINGS` 的 per-metric 閾值即時計算。
> - `REALTIME_METRICS` 為 scope A 既有單 metric buffer 表（保留相容）；`REALTIME_METRIC_WIDE` 為高頻 simulator buffer，與 `DATA_RECORDS` 共用欄位設計，後台批次 flush。
> - Design Evolution：long format（title / value / category 單 metric per row）→ unified wide schema（多 metric per row + per-metric anomaly breakdown）。

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
| 資料管理 | `/api/v1/data/*` | `app/services/data_service.py` + `app/utils/csv_importer.py` | Wide schema CRUD（13 欄）/ bulk import / per-row error breakdown |
| 異常偵測 | `anomaly_detector` 服務 + `POST /api/v1/data/anomaly-preview` | `app/services/anomaly_detector.py` | per-metric 閾值載入 + bool dict 計算（5 key 完整）+ CSV 預覽不寫入 DB |
| 即時監控 | `/ws/realtime` + `/api/v1/admin/realtime-history` | `app/services/realtime_service.py` + `app/core/ws_manager.py` + `app/services/batch_writer.py` | WebSocket push + DB 批次寫入 `realtime_metric_wide` |
| 資料分析 | `/api/v1/analytics/*` | `app/services/analytics_service.py` + `app/utils/excel_exporter.py` | 統計 JSON（per-metric 聚合）+ Excel 串流 |
| 系統管理 | `/api/v1/admin/*`（含 `PATCH /admin/settings/{key}`）| `app/api/v1/admin.py` | 使用者 / 日誌 / DB 狀態 / per-metric 閾值動態調整 |
