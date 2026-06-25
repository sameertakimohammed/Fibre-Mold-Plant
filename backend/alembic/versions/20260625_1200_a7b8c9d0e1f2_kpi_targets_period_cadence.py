"""kpi_targets: add period cadence (daily/weekly/monthly)

Targets become per-(metric, period) instead of one row per metric. Adds a
``period`` column (existing rows fold into 'monthly'), swaps the unique index on
``metric`` for a composite unique on (metric, period), and indexes ``period``.
The dashboard compares each window against the target for its inferred cadence;
services.seed pre-loads the supervisor's daily/weekly/monthly figures into an
empty table. Additive — no data is lost.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-25 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing rows are monthly rates; server_default folds them in cleanly.
    op.add_column(
        "kpi_targets",
        sa.Column("period", sa.String(length=10), nullable=False, server_default="monthly"),
    )
    # metric alone is no longer unique — (metric, period) is.
    op.drop_index("ix_kpi_targets_metric", table_name="kpi_targets")
    op.create_index("ix_kpi_targets_metric", "kpi_targets", ["metric"], unique=False)
    op.create_index("ix_kpi_targets_period", "kpi_targets", ["period"], unique=False)
    op.create_unique_constraint(
        "uq_kpi_target_metric_period", "kpi_targets", ["metric", "period"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_kpi_target_metric_period", "kpi_targets", type_="unique")
    op.drop_index("ix_kpi_targets_period", table_name="kpi_targets")
    op.drop_index("ix_kpi_targets_metric", table_name="kpi_targets")
    # Best-effort restore of the old unique-on-metric index (only valid if at
    # most one period per metric remains).
    op.create_index("ix_kpi_targets_metric", "kpi_targets", ["metric"], unique=True)
    op.drop_column("kpi_targets", "period")
