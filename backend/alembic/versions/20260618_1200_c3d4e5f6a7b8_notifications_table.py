"""notifications: proactive-alert / notification table

Adds the `notifications` table backing the AUTOMATION + PROACTIVE-ALERTING wave.
Rows are written by services/alerts.evaluate (after a shift write and from the
daily scheduler job) and read by the /api/notifications endpoints.

severity and category are plain strings (not DB enums) so new categories never
need a migration. dedup_key is indexed and used to suppress re-inserting the
SAME issue every run. acknowledged_by is a plain integer (NO foreign key) —
mirroring audit_log.actor_id — so it survives user deletion with no cascade.

The schema is created from the model's column definitions and works on both
Postgres (production) and SQLite (the throwaway test path), so no
dialect-specific branches are needed here.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-18 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("dedup_key", sa.String(length=160), nullable=True),
        sa.Column(
            "acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("acknowledged_by", sa.Integer(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_dedup_key", "notifications", ["dedup_key"])


def downgrade() -> None:
    op.drop_index("ix_notifications_dedup_key", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_table("notifications")
