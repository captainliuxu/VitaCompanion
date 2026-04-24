"""normalize phase11 legacy memory columns

Revision ID: b8f3c2d4e6a7
Revises: 7c0d2e7a91b4
Create Date: 2026-04-19 15:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8f3c2d4e6a7"
down_revision: Union[str, Sequence[str], None] = "7c0d2e7a91b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user_memories" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("user_memories")}
    with op.batch_alter_table("user_memories", schema=None) as batch_op:
        if "source" in columns and not columns["source"]["nullable"]:
            batch_op.alter_column(
                "source",
                existing_type=sa.String(length=50),
                nullable=True,
            )
        if "enabled" in columns:
            batch_op.drop_column("enabled")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user_memories" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("user_memories")}
    with op.batch_alter_table("user_memories", schema=None) as batch_op:
        if "enabled" not in columns:
            batch_op.add_column(
                sa.Column(
                    "enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                )
            )

    if "source" in columns:
        op.execute("UPDATE user_memories SET source = '' WHERE source IS NULL")

    with op.batch_alter_table("user_memories", schema=None) as batch_op:
        if "source" in columns:
            batch_op.alter_column(
                "source",
                existing_type=sa.String(length=50),
                nullable=False,
            )
