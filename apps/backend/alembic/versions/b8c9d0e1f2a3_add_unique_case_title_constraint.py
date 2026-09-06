"""add unique constraint on case firm_id + title

Revision ID: b8c9d0e1f2a3
Revises: a564213e9d80
Create Date: 2026-09-05 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a564213e9d80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM anomalies WHERE clause_id IN (
            SELECT c.id FROM clauses c
            JOIN documents d ON c.document_id = d.id
            JOIN cases cs ON d.case_id = cs.id
            WHERE cs.id NOT IN (
                SELECT DISTINCT ON (firm_id, title) id FROM cases ORDER BY firm_id, title, created_at
            )
        )
        """
    )
    op.execute(
        """
        DELETE FROM clauses WHERE document_id IN (
            SELECT d.id FROM documents d
            JOIN cases cs ON d.case_id = cs.id
            WHERE cs.id NOT IN (
                SELECT DISTINCT ON (firm_id, title) id FROM cases ORDER BY firm_id, title, created_at
            )
        )
        """
    )
    op.execute(
        """
        DELETE FROM documents WHERE case_id IN (
            SELECT id FROM cases WHERE id NOT IN (
                SELECT DISTINCT ON (firm_id, title) id FROM cases ORDER BY firm_id, title, created_at
            )
        )
        """
    )
    op.execute(
        """
        DELETE FROM cases WHERE id NOT IN (
            SELECT DISTINCT ON (firm_id, title) id FROM cases ORDER BY firm_id, title, created_at
        )
        """
    )
    op.create_unique_constraint(
        "uq_case_firm_title", "cases", ["firm_id", "title"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_case_firm_title", "cases", type_="unique")
