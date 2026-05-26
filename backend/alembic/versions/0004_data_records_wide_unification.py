"""data_records wide unification (Scope A — only alter data_records)

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-26 00:00:00.000000

Scope 限縮（懷特 2026-05-26 拍板選項 A）：
  - 只 ALTER data_records 表（long → wide format）
  - 保留 realtime_metrics_wide / realtime_metrics 表不動
  - 不插入 realtime 資料進 data_records

upgrade() 步驟：
  Step 0: 確保 admin user id=1 存在
  Step 1: ADD COLUMNS (ts, 5 metric, anomaly_flags, source, note)
  Step 2: BACKFILL ts = recorded_at
  Step 3: BACKFILL long → wide aggregate (GROUP BY minute + owner_id)
  Step 4: DELETE 已被聚合的 non-keep long rows (全 NULL metric rows)
  Step 5: DROP old columns (title, value, category, is_anomaly, recorded_at)
  Step 6: ALTER ts NOT NULL
  Step 7: ADD CHECK constraint ck_data_records_at_least_one_metric
  Step 8: UPDATE source 'records' → 'user' (cleanup)
  Step 9: DROP old indices (category_recorded_at, owner_id_created_at)
  Step 10: CREATE new indices (ts, source, owner_id_ts)

downgrade(): schema 還原只（不還原資料，依賴 mysqldump）
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Helper: dialect-aware SQL fragments
# ---------------------------------------------------------------------------


def _is_mariadb_or_mysql(conn) -> bool:  # noqa: ANN001
    return conn.dialect.name in ("mysql", "mariadb")


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    conn = op.get_bind()
    is_mysql = _is_mariadb_or_mysql(conn)

    # ------------------------------------------------------------------
    # Step 0: 確保 admin user (id=1) 存在（idempotent）
    # ------------------------------------------------------------------
    if is_mysql:
        conn.execute(
            sa.text(
                "INSERT INTO users "
                "(id, email, password_hash, role, display_name, is_active, created_at, updated_at) "
                "VALUES (1, 'admin@example.com', '$2b$12$placeholder_hash_for_migration', "
                "'admin', 'System Admin', 1, NOW(), NOW()) "
                "ON DUPLICATE KEY UPDATE id=id"
            )
        )
    else:
        # SQLite (dev / CI)
        conn.execute(
            sa.text(
                "INSERT OR IGNORE INTO users "
                "(id, email, password_hash, role, display_name, is_active, created_at, updated_at) "
                "VALUES (1, 'admin@example.com', '$2b$12$placeholder_hash_for_migration', "
                "'admin', 'System Admin', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    # ------------------------------------------------------------------
    # Step 1: ADD new wide columns to data_records
    #         All nullable initially so existing rows don't violate constraints.
    # ------------------------------------------------------------------
    op.add_column("data_records", sa.Column("ts", sa.DateTime(timezone=True), nullable=True))
    op.add_column("data_records", sa.Column("temperature", sa.Numeric(18, 4), nullable=True))
    op.add_column("data_records", sa.Column("humidity", sa.Numeric(18, 4), nullable=True))
    op.add_column("data_records", sa.Column("pressure", sa.Numeric(18, 4), nullable=True))
    op.add_column("data_records", sa.Column("voltage", sa.Numeric(18, 4), nullable=True))
    op.add_column("data_records", sa.Column("cpu_usage", sa.Numeric(18, 4), nullable=True))
    op.add_column(
        "data_records",
        sa.Column("anomaly_flags", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "data_records",
        sa.Column("source", sa.String(50), nullable=False, server_default="user"),
    )
    op.add_column("data_records", sa.Column("note", sa.String(200), nullable=True))

    # ------------------------------------------------------------------
    # Step 2: BACKFILL ts = recorded_at
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("UPDATE data_records SET ts = recorded_at WHERE ts IS NULL")
    )

    # ------------------------------------------------------------------
    # Step 3: BACKFILL long → wide aggregate (GROUP BY minute + owner_id)
    #
    # Strategy:
    #   - Per (minute_bucket, owner_id) group, pick the MIN(id) row as the
    #     "keeper" wide row.
    #   - Fill all 5 metric columns + anomaly_flags on that keeper row.
    #   - Other rows in the same group will have all metric columns NULL
    #     and will be deleted in Step 4.
    #
    # MariaDB supports multi-table UPDATE; SQLite does not.
    # For SQLite we do a two-phase approach: collect aggregates in Python
    # then apply per-row updates.
    # ------------------------------------------------------------------
    if is_mysql:
        conn.execute(
            sa.text(
                """
                UPDATE data_records dr
                JOIN (
                    SELECT
                        MIN(dr2.id) AS keep_id,
                        DATE_FORMAT(dr2.recorded_at, '%Y-%m-%d %H:%i:00') AS minute_bucket,
                        dr2.owner_id,
                        MAX(CASE WHEN dr2.category='temperature' THEN dr2.value END) AS t_val,
                        MAX(CASE WHEN dr2.category='humidity'    THEN dr2.value END) AS h_val,
                        MAX(CASE WHEN dr2.category='pressure'   THEN dr2.value END) AS p_val,
                        MAX(CASE WHEN dr2.category='voltage'    THEN dr2.value END) AS v_val,
                        MAX(CASE WHEN dr2.category='cpu_usage'  THEN dr2.value END) AS c_val,
                        MAX(CASE WHEN dr2.category='temperature' AND dr2.is_anomaly=1 THEN 1 ELSE 0 END) AS t_a,
                        MAX(CASE WHEN dr2.category='humidity'    AND dr2.is_anomaly=1 THEN 1 ELSE 0 END) AS h_a,
                        MAX(CASE WHEN dr2.category='pressure'   AND dr2.is_anomaly=1 THEN 1 ELSE 0 END) AS p_a,
                        MAX(CASE WHEN dr2.category='voltage'    AND dr2.is_anomaly=1 THEN 1 ELSE 0 END) AS v_a,
                        MAX(CASE WHEN dr2.category='cpu_usage'  AND dr2.is_anomaly=1 THEN 1 ELSE 0 END) AS c_a,
                        GROUP_CONCAT(DISTINCT dr2.title SEPARATOR ' / ') AS note_concat
                    FROM data_records dr2
                    WHERE (dr2.source = 'user' OR dr2.source IS NULL)
                    GROUP BY DATE_FORMAT(dr2.recorded_at, '%Y-%m-%d %H:%i:00'), dr2.owner_id
                ) agg ON dr.id = agg.keep_id
                SET
                    dr.temperature  = agg.t_val,
                    dr.humidity     = agg.h_val,
                    dr.pressure     = agg.p_val,
                    dr.voltage      = agg.v_val,
                    dr.cpu_usage    = agg.c_val,
                    dr.anomaly_flags = JSON_OBJECT(
                        'temperature', IF(agg.t_a=1, TRUE, FALSE),
                        'humidity',    IF(agg.h_a=1, TRUE, FALSE),
                        'pressure',    IF(agg.p_a=1, TRUE, FALSE),
                        'voltage',     IF(agg.v_a=1, TRUE, FALSE),
                        'cpu_usage',   IF(agg.c_a=1, TRUE, FALSE)
                    ),
                    dr.source = 'user',
                    dr.note   = LEFT(agg.note_concat, 200)
                """
            )
        )
    else:
        # SQLite path: Python-side aggregation
        rows = conn.execute(
            sa.text(
                """
                SELECT
                    MIN(id) AS keep_id,
                    strftime('%Y-%m-%d %H:%M:00', recorded_at) AS minute_bucket,
                    owner_id,
                    MAX(CASE WHEN category='temperature' THEN value END) AS t_val,
                    MAX(CASE WHEN category='humidity'    THEN value END) AS h_val,
                    MAX(CASE WHEN category='pressure'   THEN value END) AS p_val,
                    MAX(CASE WHEN category='voltage'    THEN value END) AS v_val,
                    MAX(CASE WHEN category='cpu_usage'  THEN value END) AS c_val,
                    MAX(CASE WHEN category='temperature' AND is_anomaly=1 THEN 1 ELSE 0 END) AS t_a,
                    MAX(CASE WHEN category='humidity'    AND is_anomaly=1 THEN 1 ELSE 0 END) AS h_a,
                    MAX(CASE WHEN category='pressure'   AND is_anomaly=1 THEN 1 ELSE 0 END) AS p_a,
                    MAX(CASE WHEN category='voltage'    AND is_anomaly=1 THEN 1 ELSE 0 END) AS v_a,
                    MAX(CASE WHEN category='cpu_usage'  AND is_anomaly=1 THEN 1 ELSE 0 END) AS c_a,
                    GROUP_CONCAT(DISTINCT title) AS note_concat
                FROM data_records
                WHERE (source = 'user' OR source IS NULL)
                GROUP BY strftime('%Y-%m-%d %H:%M:00', recorded_at), owner_id
                """
            )
        ).fetchall()

        import json as _json

        for row in rows:
            flags = _json.dumps({
                "temperature": bool(row.t_a),
                "humidity":    bool(row.h_a),
                "pressure":    bool(row.p_a),
                "voltage":     bool(row.v_a),
                "cpu_usage":   bool(row.c_a),
            })
            note_val = (row.note_concat or "")[:200] if row.note_concat else None
            conn.execute(
                sa.text(
                    "UPDATE data_records SET "
                    "  temperature   = :t_val, "
                    "  humidity      = :h_val, "
                    "  pressure      = :p_val, "
                    "  voltage       = :v_val, "
                    "  cpu_usage     = :c_val, "
                    "  anomaly_flags = :flags, "
                    "  source        = 'user', "
                    "  note          = :note  "
                    "WHERE id = :keep_id"
                ),
                {
                    "t_val":   row.t_val,
                    "h_val":   row.h_val,
                    "p_val":   row.p_val,
                    "v_val":   row.v_val,
                    "c_val":   row.c_val,
                    "flags":   flags,
                    "note":    note_val,
                    "keep_id": row.keep_id,
                },
            )

    # ------------------------------------------------------------------
    # Step 3b: BACKFILL non-whitelist category rows → preserve to note
    #
    # For long rows where category is NOT in the 5-metric whitelist,
    # the GROUP BY aggregate in Step 3 would ignore them (category=None).
    # We must preserve the data in the note column before they get deleted.
    # Only process rows that still have the old category column data.
    # ------------------------------------------------------------------
    if is_mysql:
        conn.execute(
            sa.text(
                """
                UPDATE data_records
                SET note = LEFT(CONCAT(
                    COALESCE(note, ''),
                    IF(note IS NOT NULL AND note != '', ' | ', ''),
                    'original_category=', category, ', value=', COALESCE(CAST(value AS CHAR), 'NULL')
                ), 200),
                temperature = CASE WHEN category = 'temperature' THEN value ELSE temperature END,
                humidity    = CASE WHEN category = 'humidity'    THEN value ELSE humidity    END,
                pressure    = CASE WHEN category = 'pressure'    THEN value ELSE pressure    END,
                voltage     = CASE WHEN category = 'voltage'     THEN value ELSE voltage     END,
                cpu_usage   = CASE WHEN category = 'cpu_usage'   THEN value ELSE cpu_usage   END
                WHERE category NOT IN ('temperature', 'humidity', 'pressure', 'voltage', 'cpu_usage')
                  AND (source = 'user' OR source IS NULL)
                  AND temperature IS NULL
                  AND humidity    IS NULL
                  AND pressure    IS NULL
                  AND voltage     IS NULL
                  AND cpu_usage   IS NULL
                """
            )
        )
    else:
        # SQLite: process non-whitelist rows in Python
        non_wl_rows = conn.execute(
            sa.text(
                """
                SELECT id, category, value, note
                FROM data_records
                WHERE category NOT IN ('temperature', 'humidity', 'pressure', 'voltage', 'cpu_usage')
                  AND (source = 'user' OR source IS NULL)
                  AND temperature IS NULL
                  AND humidity    IS NULL
                  AND pressure    IS NULL
                  AND voltage     IS NULL
                  AND cpu_usage   IS NULL
                """
            )
        ).fetchall()

        for nwl_row in non_wl_rows:
            prefix = (nwl_row.note or "").strip()
            sep = " | " if prefix else ""
            new_note = (
                prefix + sep
                + f"original_category={nwl_row.category}, value={nwl_row.value}"
            )[:200]
            conn.execute(
                sa.text(
                    "UPDATE data_records SET note = :note "
                    "WHERE id = :row_id"
                ),
                {"note": new_note, "row_id": nwl_row.id},
            )

    # ------------------------------------------------------------------
    # Step 4: DELETE non-keeper rows.
    #
    # Delete rows where ALL metric columns are NULL AND note IS NULL.
    # This ensures:
    #   - Secondary (non-keeper) long rows are deleted (they were merged into keeper)
    #   - Non-whitelist category rows with data preserved in note are NOT deleted
    #   - Only user/NULL source rows are targeted (simulator rows untouched)
    # ------------------------------------------------------------------
    conn.execute(
        sa.text(
            "DELETE FROM data_records "
            "WHERE temperature IS NULL "
            "  AND humidity    IS NULL "
            "  AND pressure    IS NULL "
            "  AND voltage     IS NULL "
            "  AND cpu_usage   IS NULL "
            "  AND note        IS NULL "
            "  AND (source = 'user' OR source IS NULL)"
        )
    )

    # ------------------------------------------------------------------
    # Step 5: DROP old long-format columns
    #
    # SQLite does not support DROP COLUMN before version 3.35.
    # Use batch_alter_table for cross-dialect support.
    # ------------------------------------------------------------------
    with op.batch_alter_table("data_records", recreate="auto") as batch_op:
        batch_op.drop_column("title")
        batch_op.drop_column("value")
        batch_op.drop_column("category")
        batch_op.drop_column("is_anomaly")
        batch_op.drop_column("recorded_at")

    # ------------------------------------------------------------------
    # Step 6: ALTER ts NOT NULL
    # ------------------------------------------------------------------
    with op.batch_alter_table("data_records", recreate="auto") as batch_op:
        batch_op.alter_column("ts", nullable=False, existing_type=sa.DateTime(timezone=True))

    # ------------------------------------------------------------------
    # Step 7: CHECK constraint ck_data_records_at_least_one_metric
    #
    # SQLite does not support ADD CONSTRAINT after table creation via
    # ALTER TABLE. batch_alter_table with recreate="always" handles this.
    # MariaDB supports it natively via op.create_check_constraint.
    # ------------------------------------------------------------------
    if is_mysql:
        op.create_check_constraint(
            "ck_data_records_at_least_one_metric",
            "data_records",
            "temperature IS NOT NULL OR humidity IS NOT NULL OR "
            "pressure IS NOT NULL OR voltage IS NOT NULL OR cpu_usage IS NOT NULL",
        )
    else:
        # SQLite: recreate table with constraint embedded
        with op.batch_alter_table(
            "data_records",
            recreate="always",
            table_kwargs={
                "sqlite_autoincrement": False,
            },
        ) as batch_op:
            batch_op.create_check_constraint(
                "ck_data_records_at_least_one_metric",
                "temperature IS NOT NULL OR humidity IS NOT NULL OR "
                "pressure IS NOT NULL OR voltage IS NOT NULL OR cpu_usage IS NOT NULL",
            )

    # ------------------------------------------------------------------
    # Step 8: UPDATE source 'records' → 'user' (clean up any legacy values)
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("UPDATE data_records SET source='user' WHERE source='records'")
    )

    # ------------------------------------------------------------------
    # Step 9: DROP old indices
    #
    # These indices were created in migration 0001.
    # Some may not exist if the DB was created fresh after 0001 was
    # updated — use try/except to be idempotent.
    # ------------------------------------------------------------------
    old_indices = [
        ("ix_data_records_category_recorded_at", "data_records"),
        ("ix_data_records_owner_id_created_at", "data_records"),
        # also drop the single-column indices that are now superseded
        ("ix_data_records_category", "data_records"),
        ("ix_data_records_recorded_at", "data_records"),
    ]
    for idx_name, tbl_name in old_indices:
        try:
            op.drop_index(idx_name, table_name=tbl_name)
        except Exception:  # noqa: BLE001 — index may not exist
            pass

    # ------------------------------------------------------------------
    # Step 10: CREATE new indices
    # ------------------------------------------------------------------
    op.create_index("ix_data_records_ts", "data_records", ["ts"])
    op.create_index("ix_data_records_source", "data_records", ["source"])
    op.create_index("ix_data_records_owner_id_ts", "data_records", ["owner_id", "ts"])


# ---------------------------------------------------------------------------
# downgrade — schema-only reversal (data loss is accepted; restore from mysqldump)
# ---------------------------------------------------------------------------


def downgrade() -> None:
    conn = op.get_bind()
    is_mysql = _is_mariadb_or_mysql(conn)

    # Drop new indices
    for idx_name in (
        "ix_data_records_owner_id_ts",
        "ix_data_records_source",
        "ix_data_records_ts",
    ):
        try:
            op.drop_index(idx_name, table_name="data_records")
        except Exception:  # noqa: BLE001
            pass

    # Drop CHECK constraint
    if is_mysql:
        try:
            op.drop_constraint(
                "ck_data_records_at_least_one_metric", "data_records", type_="check"
            )
        except Exception:  # noqa: BLE001
            pass

    # Re-add old long-format columns + indices via batch_alter (cross-dialect)
    with op.batch_alter_table("data_records", recreate="auto") as batch_op:
        # Restore ts back to nullable
        batch_op.alter_column("ts", nullable=True, existing_type=sa.DateTime(timezone=True))
        # Re-add old columns
        batch_op.add_column(
            sa.Column("recorded_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "is_anomaly",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "category",
                sa.String(50),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column(
                "value",
                sa.Numeric(18, 4),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "title",
                sa.String(200),
                nullable=False,
                server_default="",
            )
        )

    # Backfill recorded_at = ts for existing rows
    conn.execute(sa.text("UPDATE data_records SET recorded_at = ts"))

    # Drop new wide columns
    with op.batch_alter_table("data_records", recreate="auto") as batch_op:
        batch_op.drop_column("note")
        batch_op.drop_column("source")
        batch_op.drop_column("anomaly_flags")
        batch_op.drop_column("cpu_usage")
        batch_op.drop_column("voltage")
        batch_op.drop_column("pressure")
        batch_op.drop_column("humidity")
        batch_op.drop_column("temperature")
        batch_op.drop_column("ts")

    # Restore old indices
    op.create_index("ix_data_records_category", "data_records", ["category"])
    op.create_index("ix_data_records_recorded_at", "data_records", ["recorded_at"])
    op.create_index("ix_data_records_owner_id", "data_records", ["owner_id"])
    op.create_index(
        "ix_data_records_category_recorded_at",
        "data_records",
        ["category", "recorded_at"],
    )
    op.create_index(
        "ix_data_records_owner_id_created_at",
        "data_records",
        ["owner_id", "created_at"],
    )
