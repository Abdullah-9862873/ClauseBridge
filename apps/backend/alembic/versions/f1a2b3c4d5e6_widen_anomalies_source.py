"""widen anomalies source column to 50 chars

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-09-07 03:30:00.000000

"""
from typing import Sequence

from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE anomalies ALTER COLUMN source TYPE VARCHAR(50)")


def downgrade() -> None:
    op.execute("ALTER TABLE anomalies ALTER COLUMN source TYPE VARCHAR(20)")