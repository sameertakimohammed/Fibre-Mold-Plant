"""production_shifts: end-of-shift report sheet fields

Adds the rest of the Team Leader's paper log so the shift report can be rendered
and emailed automatically: supervisor, staff/casual counts, absenteeism, and
free-text stock/delivery notes, plus a `machines` JSON map for the per-machine
grid (hours, targets, operators, product detail) keyed by HGHY/HT1..HT6/LABEL.
Additive — all columns default to empty/0, existing rows keep their data.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-25 17:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("production_shifts", sa.Column("supervisor", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("production_shifts", sa.Column("staff_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("production_shifts", sa.Column("casual_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("production_shifts", sa.Column("absenteeism", sa.Text(), nullable=False, server_default=""))
    op.add_column("production_shifts", sa.Column("stock_notes", sa.Text(), nullable=False, server_default=""))
    op.add_column("production_shifts", sa.Column("delivery_notes", sa.Text(), nullable=False, server_default=""))
    # JSON per-machine grid; nullable so existing rows read as NULL (treated as {}).
    op.add_column("production_shifts", sa.Column("machines", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("production_shifts", "machines")
    op.drop_column("production_shifts", "delivery_notes")
    op.drop_column("production_shifts", "stock_notes")
    op.drop_column("production_shifts", "absenteeism")
    op.drop_column("production_shifts", "casual_count")
    op.drop_column("production_shifts", "staff_count")
    op.drop_column("production_shifts", "supervisor")
