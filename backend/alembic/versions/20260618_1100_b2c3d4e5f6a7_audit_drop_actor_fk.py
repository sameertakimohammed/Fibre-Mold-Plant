"""audit_log: drop the actor_id foreign key (immutable-log fix)

The data-integrity wave created audit_log.actor_id as a foreign key to users.id
with ON DELETE SET NULL, AND a BEFORE UPDATE/DELETE trigger that makes the table
append-only. Those two are in direct conflict: deleting a user who has ANY audit
rows (everyone has at least login events) makes Postgres attempt to NULL their
actor_id in audit_log, which the trigger blocks -> the user delete fails with a
500. Separately, actor_id is part of the SHA-256 hash chain, so a SET NULL would
also silently break tamper-evidence verification.

Fix: drop the foreign key entirely. actor_id remains as a plain integer
reference captured at write time; actor_username is already denormalized as the
durable record of who acted, so the trail still survives user deletion. An
immutable audit log must never be mutated by a cascade.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-18 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # Only Postgres created the named FK constraint (the SQLite test path builds
    # audit_log from the model, which no longer declares the FK at all).
    if _is_postgres():
        op.execute("ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_actor_id_fkey")


def downgrade() -> None:
    # Recreate the FK as ON DELETE SET NULL (the original, conflicting state).
    if _is_postgres():
        op.create_foreign_key(
            "audit_log_actor_id_fkey",
            "audit_log",
            "users",
            ["actor_id"],
            ["id"],
            ondelete="SET NULL",
        )
