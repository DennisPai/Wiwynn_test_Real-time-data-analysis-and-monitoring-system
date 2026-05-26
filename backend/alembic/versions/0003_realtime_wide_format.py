"""realtime wide format

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-26 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "realtime_metrics_wide",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature", sa.Numeric(18, 4), nullable=True),
        sa.Column("humidity", sa.Numeric(18, 4), nullable=True),
        sa.Column("pressure", sa.Numeric(18, 4), nullable=True),
        sa.Column("voltage", sa.Numeric(18, 4), nullable=True),
        sa.Column("cpu_usage", sa.Numeric(18, 4), nullable=True),
        sa.Column("anomaly_flags", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="simulator"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_realtime_metrics_wide_ts_desc", "realtime_metrics_wide", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_realtime_metrics_wide_ts_desc", table_name="realtime_metrics_wide")
    op.drop_table("realtime_metrics_wide")
