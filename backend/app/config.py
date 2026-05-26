from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    # DATABASE_URL（若設定）優先於下方 DB_* 拼裝；Zeabur / Heroku 等平台慣例
    # 範例：mysql+asyncmy://user:pass@host:3306/dbname
    DATABASE_URL: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "monitoring"
    DB_USER: str = "app_user"
    DB_PASSWORD: str = "apppw"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # JWT
    JWT_SECRET_KEY: str = "changeme_changeme_changeme_changeme_32chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:8501,http://localhost:3000"

    # Realtime / batch
    REALTIME_TICK: int = 1
    BATCH_FLUSH: int = 5
    ANOMALY_THRESHOLD_HIGH: float = 80.0
    ANOMALY_THRESHOLD_LOW: float = 10.0

    # Per-metric anomaly threshold fallback values (used when DB AppSetting is absent)
    DEFAULT_ANOMALY_THRESHOLDS: dict = {
        "temperature": {"high": 80, "low": 10},
        "humidity": {"high": 85, "low": 20},
        "pressure": {"high": 1050, "low": 950},
        "voltage": {"high": 13.5, "low": 11.0},
        "cpu_usage": {"high": 90, "low": 5},
    }

    # Seed accounts
    SEED_ADMIN_EMAIL: str = "admin@example.com"
    SEED_ADMIN_PASSWORD: str = "admin123"
    SEED_USER_EMAIL: str = "user@example.com"
    SEED_USER_PASSWORD: str = "user123"
    SEED_VIEWER_EMAIL: str = "viewer@example.com"
    SEED_VIEWER_PASSWORD: str = "viewer123"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def jwt_secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @property
    def database_url(self) -> str:
        # 1) 完整 DATABASE_URL 優先（Zeabur / Heroku / Railway 等平台慣例）
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # 自動補 async driver：mysql:// → mysql+asyncmy://
            if url.startswith("mysql://"):
                url = "mysql+asyncmy://" + url[len("mysql://") :]
            elif url.startswith("mariadb://"):
                url = "mysql+asyncmy://" + url[len("mariadb://") :]
            return url
        # 2) Fallback：從 DB_HOST/PORT/USER/PASSWORD/NAME 拼裝
        return (
            f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
