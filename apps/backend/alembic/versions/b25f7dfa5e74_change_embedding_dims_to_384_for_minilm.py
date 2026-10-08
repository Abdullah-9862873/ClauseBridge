"""change embedding dims to 384 for MiniLM

Revision ID: b25f7dfa5e74
Revises: d2e3f4a5b6c7
Create Date: 2026-09-06 23:12:30.130666

"""
from typing import Sequence, Union

import pgvector.sqlalchemy
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b25f7dfa5e74'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM anomalies")
    op.execute("DELETE FROM clauses")
    op.execute("DELETE FROM reference_chunks")
    op.alter_column('clauses', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=1024),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               existing_nullable=True)
    op.alter_column('reference_chunks', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=1024),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               existing_nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM anomalies")
    op.execute("DELETE FROM clauses")
    op.execute("DELETE FROM reference_chunks")
    op.alter_column('reference_chunks', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=1024),
               existing_nullable=True)
    op.alter_column('clauses', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=1024),
               existing_nullable=True)
