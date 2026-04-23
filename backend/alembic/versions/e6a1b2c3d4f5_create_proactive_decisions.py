"""create proactive decisions

Revision ID: e6a1b2c3d4f5
Revises: d4b9e8a7c3f2
Create Date: 2026-04-23 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6a1b2c3d4f5"
down_revision: Union[str, Sequence[str], None] = "d4b9e8a7c3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "proactive_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("trigger_rule_id", sa.Integer(), nullable=True),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("triggered", sa.Boolean(), nullable=False),
        sa.Column("ai_should_remind", sa.Boolean(), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("cooldown_hours", sa.Integer(), nullable=True),
        sa.Column("safety_label", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("blocked_reason", sa.String(length=200), nullable=True),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("ai_response_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trigger_rule_id"], ["trigger_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_proactive_decisions_created_at"), "proactive_decisions", ["created_at"], unique=False)
    op.create_index(op.f("ix_proactive_decisions_id"), "proactive_decisions", ["id"], unique=False)
    op.create_index(op.f("ix_proactive_decisions_status"), "proactive_decisions", ["status"], unique=False)
    op.create_index(op.f("ix_proactive_decisions_trigger_rule_id"), "proactive_decisions", ["trigger_rule_id"], unique=False)
    op.create_index(op.f("ix_proactive_decisions_trigger_type"), "proactive_decisions", ["trigger_type"], unique=False)
    op.create_index(op.f("ix_proactive_decisions_user_id"), "proactive_decisions", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_proactive_decisions_user_id"), table_name="proactive_decisions")
    op.drop_index(op.f("ix_proactive_decisions_trigger_type"), table_name="proactive_decisions")
    op.drop_index(op.f("ix_proactive_decisions_trigger_rule_id"), table_name="proactive_decisions")
    op.drop_index(op.f("ix_proactive_decisions_status"), table_name="proactive_decisions")
    op.drop_index(op.f("ix_proactive_decisions_id"), table_name="proactive_decisions")
    op.drop_index(op.f("ix_proactive_decisions_created_at"), table_name="proactive_decisions")
    op.drop_table("proactive_decisions")
