"""add gamification enabled to usersettings

Revision ID: a1b2c3d4e5f7
Revises: 9a8b7c6d5e4f
Create Date: 2026-08-26 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = '9a8b7c6d5e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'usersettings',
        sa.Column('gamification_enabled', sa.Boolean(), nullable=False, server_default=sa.true())
    )


def downgrade() -> None:
    op.drop_column('usersettings', 'gamification_enabled')