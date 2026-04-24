"""make knowledge base global

Revision ID: d4b9e8a7c3f2
Revises: c71a4f0a12d3
Create Date: 2026-04-20 18:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4b9e8a7c3f2"
down_revision: Union[str, Sequence[str], None] = "c71a4f0a12d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_knowledge_chunks_user_id"), table_name="knowledge_chunks")
    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.drop_column("user_id")

    op.drop_index(op.f("ix_knowledge_documents_user_id"), table_name="knowledge_documents")
    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.drop_column("user_id")

    op.drop_index(op.f("ix_knowledge_bases_user_id"), table_name="knowledge_bases")
    with op.batch_alter_table("knowledge_bases") as batch_op:
        batch_op.drop_column("user_id")


def downgrade() -> None:
    with op.batch_alter_table("knowledge_bases") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_knowledge_bases_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        op.f("ix_knowledge_bases_user_id"),
        "knowledge_bases",
        ["user_id"],
    )

    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_knowledge_documents_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        op.f("ix_knowledge_documents_user_id"),
        "knowledge_documents",
        ["user_id"],
    )

    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_knowledge_chunks_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        op.f("ix_knowledge_chunks_user_id"),
        "knowledge_chunks",
        ["user_id"],
    )
