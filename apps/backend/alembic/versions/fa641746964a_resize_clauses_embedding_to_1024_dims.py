"""resize clauses embedding to 1024 dims

Revision ID: fa641746964a
Revises: 4de0fe2028b1
Create Date: 2026-08-20 17:33:39.380212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa641746964a'
down_revision: Union[str, Sequence[str], None] = '4de0fe2028b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "ALTER TABLE clauses ALTER COLUMN embedding TYPE vector(1024)"
    )
def downgrade() -> None:
    """Downgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "ALTER TABLE clauses ALTER COLUMN embedding TYPE vector(1536)"
    )