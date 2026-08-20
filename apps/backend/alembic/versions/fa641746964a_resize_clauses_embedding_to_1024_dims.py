"""resize clauses embedding to 1024 dims

Revision ID: fa641746964a
Revises: 4de0fe2028b1
Create Date: 2026-08-20 17:33:39.380212

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fa641746964a"
down_revision: str | Sequence[str] | None = "4de0fe2028b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE clauses ALTER COLUMN embedding TYPE vector(1024)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE clauses ALTER COLUMN embedding TYPE vector(1536)")
