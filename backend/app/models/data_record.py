from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# SQLite 不支援 BIGINT 自動遞增；使用 with_variant 在測試環境降級為 INTEGER
_BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class DataRecord(Base):
    """Wide format 資料記錄，每筆 row 含 5 個 metric snapshot。

    欄位設計：
    - ts (DateTime tz-aware)：UTC 時間戳，取代舊 recorded_at
    - temperature/humidity/pressure/voltage/cpu_usage：5 metric，nullable，至少 1 個非 NULL
    - anomaly_flags (JSON)：per-metric bool dict，5 key 完整
    - source (String)：enum user / simulator，default "user"
    - note (String 200)：可選備註，對應 P2 docx「標題」業務語意
    """

    __tablename__ = "data_records"

    __table_args__ = (
        CheckConstraint(
            "temperature IS NOT NULL OR humidity IS NOT NULL OR pressure IS NOT NULL "
            "OR voltage IS NOT NULL OR cpu_usage IS NOT NULL",
            name="ck_data_records_at_least_one_metric",
        ),
        Index("ix_data_records_ts", "ts"),
        Index("ix_data_records_source", "source"),
        Index("ix_data_records_owner_id_ts", "owner_id", "ts"),
    )

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    humidity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    pressure: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    voltage: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cpu_usage: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    anomaly_flags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="user", server_default="user"
    )
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship("User", back_populates="data_records")  # noqa: F821
