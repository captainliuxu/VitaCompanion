"""add phase11 context memory tables

Revision ID: 7c0d2e7a91b4
Revises: 1b92d6f6e4a2
Create Date: 2026-04-19 15:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c0d2e7a91b4"
down_revision: Union[str, Sequence[str], None] = "1b92d6f6e4a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUMMARY_PROMPT_VERSION = "phase11.summary.v1"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "conversation_summaries" not in existing_tables:
        _create_conversation_summaries_table()
    else:
        _upgrade_existing_conversation_summaries(inspector)

    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "user_memories" not in existing_tables:
        _create_user_memories_table()
    else:
        _upgrade_existing_user_memories(inspector)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_memories_status"), table_name="user_memories")
    op.drop_index(op.f("ix_user_memories_memory_type"), table_name="user_memories")
    op.drop_index(op.f("ix_user_memories_user_id"), table_name="user_memories")
    op.drop_index(op.f("ix_user_memories_id"), table_name="user_memories")
    op.drop_table("user_memories")

    op.drop_index(
        op.f("ix_conversation_summaries_last_message_id"),
        table_name="conversation_summaries",
    )
    op.drop_index(
        op.f("ix_conversation_summaries_conversation_id"),
        table_name="conversation_summaries",
    )
    op.drop_index(
        op.f("ix_conversation_summaries_user_id"),
        table_name="conversation_summaries",
    )
    op.drop_index(
        op.f("ix_conversation_summaries_id"),
        table_name="conversation_summaries",
    )
    op.drop_table("conversation_summaries")


def _create_conversation_summaries_table() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "prompt_version",
            sa.String(length=50),
            nullable=False,
            server_default=SUMMARY_PROMPT_VERSION,
        ),
        sa.Column("source_message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            name="uq_conversation_summaries_conversation_id",
        ),
    )
    _ensure_index("conversation_summaries", ["id"])
    _ensure_index("conversation_summaries", ["user_id"])
    _ensure_index("conversation_summaries", ["conversation_id"])
    _ensure_index("conversation_summaries", ["last_message_id"])


def _upgrade_existing_conversation_summaries(inspector) -> None:
    columns = _column_names(inspector, "conversation_summaries")

    with op.batch_alter_table("conversation_summaries", schema=None) as batch_op:
        if "summary" not in columns and "summary_text" in columns:
            batch_op.alter_column(
                "summary_text",
                new_column_name="summary",
                existing_type=sa.Text(),
                existing_nullable=False,
            )
        if "user_id" not in columns:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))

    if "user_id" not in columns:
        op.execute(
            """
            UPDATE conversation_summaries
            SET user_id = (
                SELECT conversations.user_id
                FROM conversations
                WHERE conversations.id = conversation_summaries.conversation_id
            )
            WHERE user_id IS NULL
            """
        )
        op.execute("DELETE FROM conversation_summaries WHERE user_id IS NULL")
        with op.batch_alter_table("conversation_summaries", schema=None) as batch_op:
            batch_op.alter_column(
                "user_id",
                existing_type=sa.Integer(),
                nullable=False,
            )

    inspector = sa.inspect(op.get_bind())
    _ensure_index("conversation_summaries", ["user_id"], inspector=inspector)
    _ensure_index("conversation_summaries", ["conversation_id"], inspector=inspector)
    _ensure_index("conversation_summaries", ["last_message_id"], inspector=inspector)

    fks = inspector.get_foreign_keys("conversation_summaries")
    if not _has_fk(fks, ["user_id"]):
        with op.batch_alter_table("conversation_summaries", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_conversation_summaries_user_id_users",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )


def _create_user_memories_table() -> None:
    op.create_table(
        "user_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(length=30), nullable=False, server_default="profile"),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _ensure_index("user_memories", ["id"])
    _ensure_index("user_memories", ["user_id"])
    _ensure_index("user_memories", ["memory_type"])
    _ensure_index("user_memories", ["status"])


def _upgrade_existing_user_memories(inspector) -> None:
    columns = _column_names(inspector, "user_memories")

    with op.batch_alter_table("user_memories", schema=None) as batch_op:
        if "importance" not in columns and "priority" in columns:
            batch_op.alter_column(
                "priority",
                new_column_name="importance",
                existing_type=sa.Integer(),
                existing_nullable=False,
            )
        if "status" not in columns:
            batch_op.add_column(
                sa.Column("status", sa.String(length=20), nullable=True)
            )

    if "status" not in columns:
        if "enabled" in columns:
            op.execute(
                """
                UPDATE user_memories
                SET status = CASE WHEN enabled = 1 THEN 'active' ELSE 'archived' END
                WHERE status IS NULL
                """
            )
        else:
            op.execute("UPDATE user_memories SET status = 'active' WHERE status IS NULL")

        with op.batch_alter_table("user_memories", schema=None) as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=sa.String(length=20),
                nullable=False,
            )

    inspector = sa.inspect(op.get_bind())
    _ensure_index("user_memories", ["user_id"], inspector=inspector)
    _ensure_index("user_memories", ["memory_type"], inspector=inspector)
    _ensure_index("user_memories", ["status"], inspector=inspector)


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _ensure_index(
    table_name: str,
    columns: list[str],
    inspector=None,
) -> None:
    inspector = inspector or sa.inspect(op.get_bind())
    index_name = op.f(f"ix_{table_name}_{'_'.join(columns)}")
    if index_name in _index_names(inspector, table_name):
        return
    op.create_index(index_name, table_name, columns, unique=False)


def _has_fk(fks, columns: list[str]) -> bool:
    return any((fk.get("constrained_columns") or []) == columns for fk in fks)
