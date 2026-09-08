"""add statistics range to usersettings

Revision ID: f3a5b7c9d1e2
Revises: c3d4e5f6a7b8
Create Date: 2026-09-08 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a5b7c9d1e2'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('usersettings', sa.Column('statistics_range', sa.String(length=20), nullable=False, server_default='alltime'))
    op.add_column('usersettings', sa.Column('statistics_custom_from', sa.Date(), nullable=True))
    op.add_column('usersettings', sa.Column('statistics_custom_to', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('usersettings', 'statistics_custom_to')
    op.drop_column('usersettings', 'statistics_custom_from')
    op.drop_column('usersettings', 'statistics_range')
