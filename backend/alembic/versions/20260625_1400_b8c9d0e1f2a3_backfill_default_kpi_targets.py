"""Backfill the supervisor's default KPI targets on existing installs

services.seed.ensure_default_targets() only seeds an EMPTY kpi_targets table, so
an install that already had a target row (folded to period='monthly' by the
previous migration) never received the new per-cadence defaults — the /targets
grid and the dashboard's "vs target" markers for prod_30 / prod_12 / diesel and
the daily/weekly cells stay blank. This one-time migration inserts each default
(metric, period) only where it is ABSENT, so it:

  * fills the gap on an already-deployed DB,
  * respects any value a manager already set (present pairs are skipped),
  * being one-shot, never resurrects a target the manager later deletes.

Values are inlined (not imported from app code) so the migration stays frozen
against future edits to routers.targets.DEFAULT_TARGETS. It also drops the
orphaned legacy 'avg_per_day' target row (that metric was renamed away).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-25 14:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy of routers.targets.DEFAULT_TARGETS at this point in time.
DEFAULTS: dict[str, dict[str, float]] = {
    "prod_30":      {"daily": 30450, "weekly": 144468, "monthly": 619150},
    "prod_12":      {"daily": 33600, "weekly": 68320,  "monthly": 292800},
    "diesel":       {"daily": 735,   "weekly": 4916,   "monthly": 21070},
    "fuel_eff":     {"daily": 23.1,  "weekly": 23.1,   "monthly": 23.1},
    "downtime_pct": {"daily": 12.5,  "weekly": 12.5,   "monthly": 12.5},
    "repulp_rate":  {"daily": 2.0,   "weekly": 2.0,    "monthly": 2.0},
}


def upgrade() -> None:
    bind = op.get_bind()
    # Existing (metric, period) pairs — skip these so manager edits are kept.
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

    # Drop the orphaned legacy target metric (renamed to prod_30/prod_12).
    op.execute(sa.text("DELETE FROM kpi_targets WHERE metric = 'avg_per_day'"))


def downgrade() -> None:
    # Data-only backfill — nothing to reverse. (Deleting the seeded rows could
    # remove values a manager has since adjusted, so this is intentionally a
    # no-op.)
    pass
