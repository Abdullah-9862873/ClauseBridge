"""change reasons column to TEXT in anomalies

Revision ID: e5f6a7b8c9d0
Revises: b25f7dfa5e74
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence

from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "b25f7dfa5e74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE anomalies ALTER COLUMN reasons TYPE TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE anomalies ALTER COLUMN reasons TYPE VARCHAR(20)")