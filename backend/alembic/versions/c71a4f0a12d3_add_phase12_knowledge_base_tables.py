"""add phase12 knowledge base tables

Revision ID: c71a4f0a12d3
Revises: b8f3c2d4e6a7
Create Date: 2026-04-19 16:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c71a4f0a12d3"
down_revision: Union[str, Sequence[str], None] = "b8f3c2d4e6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_bases_id"), "knowledge_bases", ["id"])
    op.create_index(op.f("ix_knowledge_bases_user_id"), "knowledge_bases", ["user_id"])
    op.create_index(op.f("ix_knowledge_bases_status"), "knowledge_bases", ["status"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_documents_id"), "knowledge_documents", ["id"])
    op.create_index(
        op.f("ix_knowledge_documents_knowledge_base_id"),
        "knowledge_documents",
        ["knowledge_base_id"],
    )
    op.create_index(
        op.f("ix_knowledge_documents_user_id"),
        "knowledge_documents",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_knowledge_documents_file_type"),
        "knowledge_documents",
        ["file_type"],
    )
    op.create_index(
        op.f("ix_knowledge_documents_content_hash"),
        "knowledge_documents",
        ["content_hash"],
    )
    op.create_index(
        op.f("ix_knowledge_documents_status"),
        "knowledge_documents",
        ["status"],
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=50), nullable=False),
        sa.Column("embedding_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_chunks_id"), "knowledge_chunks", ["id"])
    op.create_index(
        op.f("ix_knowledge_chunks_knowledge_base_id"),
        "knowledge_chunks",
        ["knowledge_base_id"],
    )
    op.create_index(
        op.f("ix_knowledge_chunks_document_id"),
        "knowledge_chunks",
        ["document_id"],
    )
    op.create_index(op.f("ix_knowledge_chunks_user_id"), "knowledge_chunks", ["user_id"])
    op.create_index(
        op.f("ix_knowledge_chunks_content_hash"),
        "knowledge_chunks",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_chunks_content_hash"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_user_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks")
    op.drop_index(
        op.f("ix_knowledge_chunks_knowledge_base_id"),
        table_name="knowledge_chunks",
    )
    op.drop_index(op.f("ix_knowledge_chunks_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    op.drop_index(op.f("ix_knowledge_documents_status"), table_name="knowledge_documents")
    op.drop_index(
        op.f("ix_knowledge_documents_content_hash"),
        table_name="knowledge_documents",
    )
    op.drop_index(op.f("ix_knowledge_documents_file_type"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_user_id"), table_name="knowledge_documents")
    op.drop_index(
        op.f("ix_knowledge_documents_knowledge_base_id"),
        table_name="knowledge_documents",
    )
    op.drop_index(op.f("ix_knowledge_documents_id"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

    op.drop_index(op.f("ix_knowledge_bases_status"), table_name="knowledge_bases")
    op.drop_index(op.f("ix_knowledge_bases_user_id"), table_name="knowledge_bases")
    op.drop_index(op.f("ix_knowledge_bases_id"), table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
