from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RealtimeMetric(Base):
    __tablename__ = "realtime_metrics"

    __table_args__ = (
        Index("ix_realtime_metrics_ts_desc", "ts"),
        Index("ix_realtime_metrics_category_ts", "category", "ts"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="simulator")
    is_anomaly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
