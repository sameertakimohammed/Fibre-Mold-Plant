"""data integrity layer: audit trail, soft-delete, FK safety, CHECK constraints

Adds the whole DATA-INTEGRITY wave in one revision on top of the baseline:

  1. audit_log table (append-only, tamper-evident) + indexes + a Postgres
     BEFORE UPDATE/DELETE trigger that refuses any mutation of audit rows.
  2. Soft-delete columns (deleted_at, deleted_by) on the five business tables,
     with deleted_by FK ON DELETE SET NULL.
  3. created_by FKs re-pointed to ON DELETE SET NULL so deleting a user can't
     orphan/break business rows.
  4. Duplicate-shift protection moved from the plain uq_date_shift
     UniqueConstraint to a PARTIAL unique index on (work_date, shift) WHERE
     deleted_at IS NULL — a soft-deleted shift no longer blocks re-entry.
  5. Non-negativity CHECK constraints added as NOT VALID, so they enforce on
     NEW/updated rows WITHOUT validating (and possibly rejecting) the existing
     90 shifts / 44 deliveries at migration time.

Postgres-only constructs (JSONB, partial index predicate, NOT VALID, trigger)
are guarded behind a dialect check so the SQLite test path still works.

Revision ID: 859c6c1804c4
Revises: 736cd65ce774
Create Date: 2026-06-18 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '859c6c1804c4'
down_revision: Union[str, None] = '736cd65ce774'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Business tables that gain soft-delete + created_by FK SET NULL.
_SOFT_DELETE_TABLES = [
    "production_shifts",
    "deliveries",
    "bale_receipts",
    "fuel_dips",
    "monthly_stock",
]

# created_by FK lives on all of the above except monthly_stock.
_CREATED_BY_TABLES = [
    "production_shifts",
    "deliveries",
    "bale_receipts",
    "fuel_dips",
]

# Non-negativity CHECK constraints: (table, constraint_name, sql_expr).
_CHECKS = [
    ("production_shifts", "ck_production_shifts_qty_nonneg", "qty >= 0"),
    ("production_shifts", "ck_production_shifts_fuel_use_nonneg", "fuel_use >= 0"),
    ("production_shifts", "ck_production_shifts_repulped_nonneg", "repulped >= 0"),
    ("production_shifts", "ck_production_shifts_downtime_nonneg", "downtime_min >= 0"),
    ("production_shifts", "ck_production_shifts_sched_hours_range", "sched_hours >= 0 AND sched_hours <= 24"),
    ("production_shifts", "ck_production_shifts_prod_hours_range", "prod_hours >= 0 AND prod_hours <= 24"),
    ("deliveries", "ck_deliveries_tray30_nonneg", "tray30 >= 0"),
    ("deliveries", "ck_deliveries_tray12n_nonneg", "tray12n >= 0"),
    ("deliveries", "ck_deliveries_tray12ff_nonneg", "tray12ff >= 0"),
    ("deliveries", "ck_deliveries_pallets_nonneg", "pallets >= 0"),
    ("bale_receipts", "ck_bale_receipts_weight_nonneg", "weight_kg >= 0"),
    ("bale_receipts", "ck_bale_receipts_quantity_nonneg", "quantity >= 0"),
    ("fuel_dips", "ck_fuel_dips_actual_usage_nonneg", "actual_usage >= 0"),
    ("fuel_dips", "ck_fuel_dips_received_nonneg", "received >= 0"),
    ("monthly_stock", "ck_monthly_stock_diesel_nonneg", "diesel_eom >= 0"),
    ("monthly_stock", "ck_monthly_stock_bales_used_nonneg", "bales_used >= 0"),
    ("monthly_stock", "ck_monthly_stock_bales_purchased_nonneg", "bales_purchased >= 0"),
]


# created_by FK names differ by table; alembic auto-named them at baseline as
# fk_<table>_created_by_users OR an unnamed constraint. Postgres assigned a
# default name like "<table>_created_by_fkey". We drop by the conventional
# auto-name and recreate with an explicit name + ON DELETE SET NULL.
_CREATED_BY_FK_NAMES = {
    "production_shifts": "production_shifts_created_by_fkey",
    "deliveries": "deliveries_created_by_fkey",
    "bale_receipts": "bale_receipts_created_by_fkey",
    "fuel_dips": "fuel_dips_created_by_fkey",
}


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    is_pg = _is_postgres()
    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_pg else sa.JSON()

    # --- 1. audit_log -------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(length=60), nullable=True),
        sa.Column("changes", json_type, nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"], unique=False)
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"], unique=False)

    # --- 2. soft-delete columns + deleted_by FK (ON DELETE SET NULL) --------
    for table in _SOFT_DELETE_TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("deleted_by", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_deleted_by_users", table, "users",
            ["deleted_by"], ["id"], ondelete="SET NULL",
        )

    # --- 3. created_by FK -> ON DELETE SET NULL -----------------------------
    # SQLite can't ALTER constraints; the test DB is created fresh from models
    # anyway, so only do this on Postgres.
    if is_pg:
        for table in _CREATED_BY_TABLES:
            op.drop_constraint(_CREATED_BY_FK_NAMES[table], table, type_="foreignkey")
            op.create_foreign_key(
                f"fk_{table}_created_by_users", table, "users",
                ["created_by"], ["id"], ondelete="SET NULL",
            )

    # --- 4. duplicate-shift protection: drop UC, add partial unique index ---
    if is_pg:
        op.drop_constraint("uq_date_shift", "production_shifts", type_="unique")
        op.create_index(
            "uq_date_shift_active", "production_shifts",
            ["work_date", "shift"], unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )
    else:
        # SQLite path (test/local) — emulate with a partial unique index too;
        # SQLite supports partial indexes since 3.8.
        op.drop_constraint("uq_date_shift", "production_shifts", type_="unique")
        op.create_index(
            "uq_date_shift_active", "production_shifts",
            ["work_date", "shift"], unique=True,
            sqlite_where=sa.text("deleted_at IS NULL"),
        )

    # --- 5. non-negativity CHECK constraints (NOT VALID on Postgres) --------
    # NOT VALID means: enforce on every NEW/updated row, but DO NOT scan/validate
    # the existing 90 shifts / 44 deliveries now (so the migration can't fail on
    # any pre-existing odd value). A later `VALIDATE CONSTRAINT` can backfill the
    # check once data is confirmed clean (see commented helper at bottom).
    if is_pg:
        for table, name, expr in _CHECKS:
            op.execute(
                f'ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expr}) NOT VALID'
            )
    else:
        # SQLite has no NOT VALID and can't ADD CHECK via ALTER; batch-recreate
        # is overkill for the throwaway test DB, so checks are skipped there.
        pass

    # --- 6. tamper-resistance trigger on audit_log (Postgres only) ----------
    # Refuse UPDATE/DELETE on audit_log at the DB layer, so even direct SQL from
    # the app role cannot rewrite history. A fully separate INSERT-only DB role
    # is an optional future hardening (would require provisioning a second role
    # in docker-compose / Postgres and granting it INSERT-only on audit_log).
    if is_pg:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION audit_log_no_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_audit_log_no_mutation
            BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutation();
            """
        )


def downgrade() -> None:
    is_pg = _is_postgres()

    # --- 6. trigger ---------------------------------------------------------
    if is_pg:
        op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_mutation ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS audit_log_no_mutation()")

    # --- 5. CHECK constraints ----------------------------------------------
    if is_pg:
        for table, name, _expr in _CHECKS:
            op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}')

    # --- 4. partial unique index -> back to plain UniqueConstraint ----------
    op.drop_index("uq_date_shift_active", table_name="production_shifts")
    op.create_unique_constraint("uq_date_shift", "production_shifts", ["work_date", "shift"])

    # --- 3. created_by FK -> back to default (no ON DELETE action) ----------
    if is_pg:
        for table in _CREATED_BY_TABLES:
            op.drop_constraint(f"fk_{table}_created_by_users", table, type_="foreignkey")
            op.create_foreign_key(
                _CREATED_BY_FK_NAMES[table], table, "users",
                ["created_by"], ["id"],
            )

    # --- 2. soft-delete columns + deleted_by FK -----------------------------
    for table in _SOFT_DELETE_TABLES:
        op.drop_constraint(f"fk_{table}_deleted_by_users", table, type_="foreignkey")
        op.drop_column(table, "deleted_by")
        op.drop_column(table, "deleted_at")

    # --- 1. audit_log -------------------------------------------------------
    op.drop_index("ix_audit_log_ts", table_name="audit_log")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_table("audit_log")


# To validate the CHECK constraints against existing rows AFTER confirming the
# data is clean, run (one per constraint), e.g.:
#   ALTER TABLE production_shifts VALIDATE CONSTRAINT ck_production_shifts_qty_nonneg;
