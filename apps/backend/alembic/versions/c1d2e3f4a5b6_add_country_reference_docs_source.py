"""add country to documents, reference_documents, reference_chunks, source to anomalies

Revision ID: c1d2e3f4a5b6
Revises: b8c9d0e1f2a3
Create Date: 2026-09-06 00:00:00.000000

"""

from collections.abc import Sequence

import pgvector
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add country column to documents
    op.add_column("documents", sa.Column("country", sa.String(length=2), nullable=True))

    # Add country column to cases
    op.add_column("cases", sa.Column("country", sa.String(length=2), nullable=True))

    # Add source column to anomalies
    op.add_column(
        "anomalies",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="country_law"),
    )

    # Create reference_documents table
    op.create_table(
        "reference_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reference_documents_case_id"),
        "reference_documents",
        ["case_id"],
        unique=False,
    )

    # Create reference_chunks table
    op.create_table(
        "reference_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reference_document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reference_document_id"],
            ["reference_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reference_chunks_reference_document_id"),
        "reference_chunks",
        ["reference_document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_reference_chunks_reference_document_id"),
        table_name="reference_chunks",
    )
    op.drop_table("reference_chunks")
    op.drop_index(
        op.f("ix_reference_documents_case_id"),
        table_name="reference_documents",
    )
    op.drop_table("reference_documents")
    op.drop_column("anomalies", "source")
    op.drop_column("cases", "country")
    op.drop_column("documents", "country")
