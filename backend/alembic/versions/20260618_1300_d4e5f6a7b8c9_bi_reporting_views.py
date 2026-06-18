"""BI reporting views: Power BI-friendly read-only view layer + read-only role

Adds a stable, BI-friendly reporting layer for Power BI (and any SQL client) on
top of the existing tables. This is the BI-INTEGRATION wave:

  1. Four read-only views (CREATE OR REPLACE VIEW), ALL excluding soft-deleted
     rows (deleted_at IS NULL):
       - vw_daily_production : per work_date roll-up with derived KPIs
                               (fuel_eff, downtime_pct, reject_rate) computed
                               with the SAME formulas as routers/analytics.py so
                               Power BI numbers match the dashboard exactly.
       - vw_deliveries       : per-delivery, with total trays.
       - vw_fuel             : per fuel dip.
       - vw_downtime         : per shift, downtime + a classified cause that
                               mirrors analytics.classify_cause().
  2. A NOLOGIN read-only role `fmp_readonly` with USAGE on the schema and SELECT
     on the four views (idempotent — created in a DO block only if absent).

IMPORTANT (deliberate): NO password is set here. The admin enables login + sets
a password OUT OF BAND, e.g.
    ALTER ROLE fmp_readonly WITH LOGIN PASSWORD '...';
Keeping the password out of code/migrations is intentional. See README
("Power BI / BI reporting").

The views are the STABLE CONTRACT for BI: query them, not the base tables, so
column changes can be absorbed in the view without breaking reports, and
soft-deleted rows never leak into reporting.

Everything here is Postgres-only and guarded behind a dialect check, so the
SQLite throwaway test path is a no-op (it has no role system or CREATE VIEW
needs for tests).

KPI FORMULA NOTES (must match routers/analytics.py._aggregate):
  - total trays for KPIs uses the stored `qty` COLUMN (analytics sums s.qty),
    NOT the sum of the per-product columns. We expose both: `total_qty` (= the
    qty column, the dashboard's number) and `trays_from_products` (sum of the
    p* columns) for cross-checking, but every derived ratio below uses qty.
  - fuel_eff     = SUM(fuel_use) / SUM(qty) * 1000        (L per 1000 trays)
  - downtime_pct = SUM(downtime_min)/60 / SUM(sched_hours) * 100
  - reject_rate  = SUM(repulped) / SUM(qty) * 100         (= analytics repulp_rate)
  Division guarded with NULLIF(...,0) so zero-output days yield NULL, not an error.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-18 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Read-only role that Power BI / SQL clients connect as. Login + password are set
# by the admin out-of-band (see README); this migration never stores a password.
READONLY_ROLE = "fmp_readonly"

# The four views that make up the BI contract.
VIEWS = ["vw_daily_production", "vw_deliveries", "vw_fuel", "vw_downtime"]


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


# --- View SQL ---------------------------------------------------------------
# All views exclude soft-deleted rows (deleted_at IS NULL).

# Per work_date roll-up. KPIs replicate analytics.py exactly (qty column for
# totals/ratios; product columns surfaced individually + summed for cross-check).
VW_DAILY_PRODUCTION = """
CREATE OR REPLACE VIEW vw_daily_production AS
SELECT
    work_date,
    -- Headline total = the stored qty column, summed (matches analytics _aggregate).
    SUM(qty)                                   AS total_qty,
    -- Per-product-type totals.
    SUM(p30s)                                  AS p30s,
    SUM(p30l)                                  AS p30l,
    SUM(p20n)                                  AS p20n,
    SUM(p12n)                                  AS p12n,
    SUM(p12hf)                                 AS p12hf,
    SUM(p12ff)                                 AS p12ff,
    SUM(p4cup)                                 AS p4cup,
    SUM(p2cup)                                 AS p2cup,
    -- Sum of the product columns, for cross-checking against total_qty.
    SUM(p30s + p30l + p20n + p12n + p12hf + p12ff + p4cup + p2cup)
                                               AS trays_from_products,
    SUM(fuel_use)                              AS fuel_use,
    SUM(downtime_min)                          AS downtime_min,
    SUM(sched_hours)                           AS sched_hours,
    SUM(repulped)                              AS repulped,
    COUNT(*)                                   AS shift_count,
    -- Derived KPIs (same formulas as analytics.py; NULLIF guards divide-by-zero).
    SUM(fuel_use) / NULLIF(SUM(qty), 0) * 1000           AS fuel_eff,        -- L / 1000 trays
    SUM(downtime_min) / 60.0 / NULLIF(SUM(sched_hours), 0) * 100
                                                         AS downtime_pct,    -- % of scheduled
    SUM(repulped) / NULLIF(SUM(qty), 0) * 100            AS reject_rate      -- % re-pulped
FROM production_shifts
WHERE deleted_at IS NULL
GROUP BY work_date
"""

VW_DELIVERIES = """
CREATE OR REPLACE VIEW vw_deliveries AS
SELECT
    id,
    work_date,
    company,
    tray30,
    tray12n,
    tray12ff,
    pallets,
    (tray30 + tray12n + tray12ff)              AS total_trays,
    comment
FROM deliveries
WHERE deleted_at IS NULL
"""

VW_FUEL = """
CREATE OR REPLACE VIEW vw_fuel AS
SELECT
    id,
    work_date,
    shift,
    open_dip,
    close_dip,
    actual_usage,
    received,
    note
FROM fuel_dips
WHERE deleted_at IS NULL
"""

# Per-shift downtime with a classified cause that mirrors
# analytics.classify_cause(). Order of the CASE branches matches the Python
# function: mold/mesh change -> cleaning/washing -> maintenance/repairs ->
# Other (has a comment) -> Unlogged (blank).
VW_DOWNTIME = """
CREATE OR REPLACE VIEW vw_downtime AS
SELECT
    id,
    work_date,
    shift,
    downtime_min,
    comment,
    CASE
        WHEN lower(coalesce(comment, '')) LIKE '%mold%'
             AND (lower(coalesce(comment, '')) LIKE '%change%'
                  OR lower(coalesce(comment, '')) LIKE '%mesh%')
            THEN 'Mold / Mesh Change'
        WHEN lower(coalesce(comment, '')) LIKE '%wash%'
             OR lower(coalesce(comment, '')) LIKE '%clean%'
            THEN 'Cleaning / Washing'
        WHEN lower(coalesce(comment, '')) LIKE '%pmi%'
             OR lower(coalesce(comment, '')) LIKE '%maintenance%'
             OR lower(coalesce(comment, '')) LIKE '%valve%'
             OR lower(coalesce(comment, '')) LIKE '%pump%'
             OR lower(coalesce(comment, '')) LIKE '%bypass%'
             OR lower(coalesce(comment, '')) LIKE '%restart%'
             OR lower(coalesce(comment, '')) LIKE '%repair%'
            THEN 'Maintenance / Repairs'
        WHEN btrim(coalesce(comment, '')) <> ''
            THEN 'Other'
        ELSE 'Unlogged'
    END                                        AS cause
FROM production_shifts
WHERE deleted_at IS NULL
"""


def upgrade() -> None:
    if not _is_postgres():
        # SQLite test path: nothing to do. The BI layer is a Postgres-only
        # production concern (roles + reporting views).
        return

    # --- 1. Views -----------------------------------------------------------
    op.execute(VW_DAILY_PRODUCTION)
    op.execute(VW_DELIVERIES)
    op.execute(VW_FUEL)
    op.execute(VW_DOWNTIME)

    # --- 2. Read-only role (NOLOGIN, no password) ---------------------------
    # Idempotent: only create the role if it doesn't already exist. NOLOGIN +
    # no password by design — the admin enables login + sets a password out of
    # band (see README). We then (re)grant USAGE + SELECT every run so the
    # grants stay correct even if the role pre-existed.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{READONLY_ROLE}') THEN
                CREATE ROLE {READONLY_ROLE} NOLOGIN;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {READONLY_ROLE}")
    for view in VIEWS:
        op.execute(f"GRANT SELECT ON {view} TO {READONLY_ROLE}")


def downgrade() -> None:
    if not _is_postgres():
        return

    # Revoke grants before dropping (so the role is left clean if it's kept).
    for view in VIEWS:
        op.execute(f"REVOKE SELECT ON {view} FROM {READONLY_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {READONLY_ROLE}")

    # Drop the views.
    for view in VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")

    # NOTE: we intentionally do NOT DROP ROLE fmp_readonly here. The admin may
    # have enabled login + set a password on it out-of-band; dropping a role
    # the migration didn't fully own (and that may own other grants) is risky.
    # To remove it manually:  DROP ROLE IF EXISTS fmp_readonly;
