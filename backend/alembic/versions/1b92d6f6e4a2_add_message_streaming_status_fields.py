"""add message streaming status fields

Revision ID: 1b92d6f6e4a2
Revises: 97f3b3d2a1a1
Create Date: 2026-04-18 16:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1b92d6f6e4a2"
down_revision: Union[str, Sequence[str], None] = "97f3b3d2a1a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {
        column["name"] for column in inspector.get_columns("messages")
    }
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("messages")
    }
    has_reply_fk = any(
        "reply_to_message_id" in (fk.get("constrained_columns") or [])
        for fk in inspector.get_foreign_keys("messages")
    )

    added_status = "status" not in existing_columns
    added_updated_at = "updated_at" not in existing_columns

    with op.batch_alter_table("messages", schema=None) as batch_op:
        if added_status:
            batch_op.add_column(
                sa.Column(
                    "status",
                    sa.String(length=20),
                    nullable=False,
                    server_default="completed",
                )
            )
        if "reply_to_message_id" not in existing_columns:
            batch_op.add_column(
                sa.Column("reply_to_message_id", sa.Integer(), nullable=True)
            )
        if "prompt_version" not in existing_columns:
            batch_op.add_column(
                sa.Column("prompt_version", sa.String(length=50), nullable=True)
            )
        if "error_code" not in existing_columns:
            batch_op.add_column(sa.Column("error_code", sa.Integer(), nullable=True))
        if "error_message" not in existing_columns:
            batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        if added_updated_at:
            batch_op.add_column(
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
            )

        if "ix_messages_status" not in existing_indexes:
            batch_op.create_index(
                batch_op.f("ix_messages_status"),
                ["status"],
                unique=False,
            )
        if "ix_messages_reply_to_message_id" not in existing_indexes:
            batch_op.create_index(
                batch_op.f("ix_messages_reply_to_message_id"),
                ["reply_to_message_id"],
                unique=False,
            )
        if not has_reply_fk:
            batch_op.create_foreign_key(
                "fk_messages_reply_to_message_id_messages",
                "messages",
                ["reply_to_message_id"],
                ["id"],
                ondelete="SET NULL",
            )

    op.execute("UPDATE messages SET status = 'completed' WHERE status IS NULL")
    op.execute("UPDATE messages SET updated_at = created_at WHERE updated_at IS NULL")

    if added_updated_at:
        with op.batch_alter_table("messages", schema=None) as batch_op:
            batch_op.alter_column(
                "updated_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
            )
    if added_status:
        with op.batch_alter_table("messages", schema=None) as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=sa.String(length=20),
                server_default=None,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {
        column["name"] for column in inspector.get_columns("messages")
    }
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("messages")
    }
    existing_fks = {
        fk.get("name")
        for fk in inspector.get_foreign_keys("messages")
        if fk.get("name")
    }

    with op.batch_alter_table("messages", schema=None) as batch_op:
        if "fk_messages_reply_to_message_id_messages" in existing_fks:
            batch_op.drop_constraint(
                "fk_messages_reply_to_message_id_messages",
                type_="foreignkey",
            )
        if "ix_messages_reply_to_message_id" in existing_indexes:
            batch_op.drop_index(batch_op.f("ix_messages_reply_to_message_id"))
        if "ix_messages_status" in existing_indexes:
            batch_op.drop_index(batch_op.f("ix_messages_status"))
        if "updated_at" in existing_columns:
            batch_op.drop_column("updated_at")
        if "error_message" in existing_columns:
            batch_op.drop_column("error_message")
        if "error_code" in existing_columns:
            batch_op.drop_column("error_code")
        if "prompt_version" in existing_columns:
            batch_op.drop_column("prompt_version")
        if "reply_to_message_id" in existing_columns:
            batch_op.drop_column("reply_to_message_id")
        if "status" in existing_columns:
            batch_op.drop_column("status")
