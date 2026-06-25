"""Add Saturday KPI targets and switch weekly to a Monday–Friday basis

The supervisor's workbook runs Saturday as a reduced shift, so it gets its own
target cadence (e.g. 30's 23,200 vs the normal-day 30,450). Weekly is redefined
as Monday–Friday (5 normal days = 5 × daily) instead of the earlier 7/30
pro-rate. This migration, on an already-deployed DB:

  * inserts the new 'saturday' row for each metric (idempotent — only where
    absent), and
  * corrects each weekly row that still holds the previous pro-rated seed value
    to the new Mon–Fri figure, leaving any value a manager has changed alone.

Values are inlined (frozen) rather than imported from app code.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-25 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Full current default set (frozen copy of routers.targets.DEFAULT_TARGETS).
DEFAULTS: dict[str, dict[str, float]] = {
    "prod_30":      {"daily": 30450, "weekly": 152250, "saturday": 23200, "monthly": 619150},
    "prod_12":      {"daily": 33600, "weekly": 168000, "saturday": 25600, "monthly": 292800},
    "diesel":       {"daily": 735,   "weekly": 3675,   "saturday": 490,   "monthly": 21070},
    "fuel_eff":     {"daily": 23.1,  "weekly": 23.1,   "saturday": 23.1,  "monthly": 23.1},
    "downtime_pct": {"daily": 12.5,  "weekly": 12.5,   "saturday": 12.5,  "monthly": 12.5},
    "repulp_rate":  {"daily": 2.0,   "weekly": 2.0,    "saturday": 2.0,   "monthly": 2.0},
}

# Weekly values the previous backfill (b8c9d0e1f2a3) seeded — used to detect an
# untouched weekly cell so we don't clobber a manager's edit.
PREV_WEEKLY: dict[str, float] = {
    "prod_30": 144468, "prod_12": 68320, "diesel": 4916,
    "fuel_eff": 23.1, "downtime_pct": 12.5, "repulp_rate": 2.0,
}


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Correct still-default weekly seeds (old 7/30 pro-rate) to the Mon–Fri
    #    basis; an untouched cell equals the previous seed value, so a manager's
    #    own value is left as-is.
    for metric, new_weekly in {m: DEFAULTS[m]["weekly"] for m in DEFAULTS}.items():
        op.execute(
            sa.text(
                "UPDATE kpi_targets SET value = :new "
                "WHERE metric = :m AND period = 'weekly' AND value = :old"
            ).bindparams(new=float(new_weekly), m=metric, old=float(PREV_WEEKLY[metric]))
        )

    # 2) Insert any missing (metric, period) — the new 'saturday' rows (and any
    #    other gap), without overwriting existing values.
    existing = {
        (r[0], r[1])
        for r in bind.execute(sa.text("SELECT metric, period FROM kpi_targets"))
    }
    rows = [
        {"metric": m, "period": p, "value": float(v)}
        for m, by_period in DEFAULTS.items()
        for p, v in by_period.items()
        if (m, p) not in existing
    ]
    if rows:
        kpi = sa.table(
            "kpi_targets",
            sa.column("metric", sa.String),
            sa.column("period", sa.String),
            sa.column("value", sa.Float),
        )
        op.bulk_insert(kpi, rows)


def downgrade() -> None:
    # Data-only migration — nothing to reverse (removing the Saturday rows could
    # drop values a manager has since set).
    pass
