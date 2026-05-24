# ── builder 階段：編譯 wheel ─────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libssl-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt


# ── runtime 階段：安裝 wheel + 複製應用程式 ──────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# 只複製預建的 wheel，不需要 gcc
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# 複製應用程式原始碼
COPY streamlit_app/ ./streamlit_app/

# Streamlit 設定：關閉遙測、不自動開瀏覽器
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501

# BACKEND_URL 由 docker-compose 注入
ENV BACKEND_URL=http://backend:8000

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app/Home.py", "--server.port=8501", "--server.headless=true"]
