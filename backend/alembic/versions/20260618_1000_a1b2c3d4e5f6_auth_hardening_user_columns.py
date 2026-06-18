"""auth hardening: login-lockout + token-revocation columns on users

Adds the AUTHENTICATION-HARDENING wave's new User columns in one revision on top
of the data-integrity layer (859c6c1804c4):

  1. failed_login_count   INT NOT NULL DEFAULT 0  — consecutive failed logins.
  2. locked_until         TIMESTAMPTZ NULL        — account locked until this UTC
                                                    instant (brute-force / AD
                                                    account-protection lockout).
  3. last_login_at        TIMESTAMPTZ NULL        — last successful login.
  4. password_changed_at  TIMESTAMPTZ NULL        — used for token revocation:
                                                    tokens issued (iat) BEFORE
                                                    this instant are rejected.

BACKFILL: password_changed_at is backfilled to each row's created_at (falling
back to now() if created_at is somehow NULL) so that the moment this column goes
live, EXISTING valid tokens are NOT invalidated en masse — a token's iat will be
newer than the user's created_at, so it stays valid until its normal expiry.

failed_login_count is added with a server_default of 0 so existing rows get 0
without a separate UPDATE; the server_default is then dropped on Postgres so the
column matches the model (app-side default), mirroring how the ORM manages it.
The timestamptz columns are nullable, so they need no backfill except (4).

SQLite (test path) has no server-side now()/ALTER nuances we depend on here; the
column adds work on both backends, and the backfill uses a portable UPDATE.

Revision ID: a1b2c3d4e5f6
Revises: 859c6c1804c4
Create Date: 2026-06-18 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '859c6c1804c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    is_pg = _is_postgres()

    # --- 1. failed_login_count ---------------------------------------------
    # server_default="0" so the column is populated on existing rows without a
    # table-rewriting UPDATE; NOT NULL is then satisfied immediately.
    op.add_column(
        "users",
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # --- 2/3/4. nullable timestamptz columns -------------------------------
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))

    # --- BACKFILL password_changed_at = created_at (fallback now()) ---------
    # Existing tokens carry an iat newer than the user's created_at, so seeding
    # password_changed_at from created_at means none of them are invalidated by
    # this migration. COALESCE guards the (unlikely) NULL created_at case.
    if is_pg:
        op.execute(
            "UPDATE users "
            "SET password_changed_at = COALESCE(created_at, now()) "
            "WHERE password_changed_at IS NULL"
        )
        # Drop the server_default so the column matches the model (the app sets
        # the default of 0 on insert). Existing rows keep their 0 value.
        op.alter_column("users", "failed_login_count", server_default=None)
    else:
        # SQLite (throwaway test DB): CURRENT_TIMESTAMP is portable here.
        op.execute(
            "UPDATE users "
            "SET password_changed_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
            "WHERE password_changed_at IS NULL"
        )
        # SQLite can't ALTER a column default in place; the test DB is rebuilt
        # from the models anyway, so leaving the server_default is harmless.


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
