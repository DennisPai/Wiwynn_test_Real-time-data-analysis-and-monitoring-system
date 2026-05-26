from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# SQLite 不支援 BIGINT 自動遞增；使用 with_variant 在測試環境降級為 INTEGER
_BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class RealtimeMetricWide(Base):
    """Wide format 即時指標快照，每筆 row 含全部 5 個 metric 的 snapshot。"""

    __tablename__ = "realtime_metrics_wide"
    __table_args__ = (
        Index("ix_realtime_metrics_wide_ts_desc", "ts"),
    )

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    humidity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    pressure: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    voltage: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cpu_usage: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    anomaly_flags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="simulator")
