"""monthly_stock.detail JSON: full End-of-Month Report payload

Adds a nullable JSON column to monthly_stock holding the complete, parsed
"End of Month Report" (the 10-section management template the plant emails every
month): diesel reading, goods produced, balance stock by colour, toner, label
brands on hand / used / received, pallets local vs export, bales used/purchased.

The existing flat columns (diesel_eom, bal_*, pallets_wrapped, bales_*,
labels_used) remain the digest used by dashboards and the KPI report; `detail`
preserves everything the printed Month End Report needs to be reproduced
faithfully. Additive and nullable, so it is backwards compatible — rows without
a detail payload simply render from the digest + computed production figures.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-19 09:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("monthly_stock", sa.Column("detail", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("monthly_stock", "detail")
