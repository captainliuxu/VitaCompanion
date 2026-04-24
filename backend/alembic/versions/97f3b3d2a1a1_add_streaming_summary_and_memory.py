"""restore missing historical revision placeholder

Revision ID: 97f3b3d2a1a1
Revises: 6d9e0c8c88f7
Create Date: 2026-04-18 16:50:00.000000

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "97f3b3d2a1a1"
down_revision: Union[str, Sequence[str], None] = "6d9e0c8c88f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This revision existed in local history but the source file was missing.
    # Keep it as a no-op to preserve upgrade continuity for existing databases.
    pass


def downgrade() -> None:
    pass
