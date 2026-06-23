"""kpi_targets table: management targets compared vs actuals

Adds a small table holding one row per KPI target (avg_per_day, fuel_eff,
downtime_pct, repulp_rate). Targets are rates, so they compare across any date
range. The dashboard reads them to draw "vs target" on the KPI cards; manager+
sets them. Additive — installs with no targets, and the dashboard simply omits
the markers until targets are set.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-21 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kpi_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_kpi_targets_metric", "kpi_targets", ["metric"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_kpi_targets_metric", table_name="kpi_targets")
    op.drop_table("kpi_targets")
