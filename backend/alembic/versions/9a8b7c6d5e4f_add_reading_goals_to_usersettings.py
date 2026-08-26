"""add reading goals to usersettings

Revision ID: 9a8b7c6d5e4f
Revises: f1b2c3d4e5a6
Create Date: 2026-08-26 13:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a8b7c6d5e4f'
down_revision: Union[str, Sequence[str], None] = 'f1b2c3d4e5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('usersettings', sa.Column('goal_pages_per_day_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('usersettings', sa.Column('goal_pages_per_day', sa.Integer(), nullable=False, server_default='20'))
    op.add_column('usersettings', sa.Column('goal_pages_per_month_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('usersettings', sa.Column('goal_pages_per_month', sa.Integer(), nullable=False, server_default='300'))
    op.add_column('usersettings', sa.Column('goal_books_per_month_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('usersettings', sa.Column('goal_books_per_month', sa.Integer(), nullable=False, server_default='2'))
    op.add_column('usersettings', sa.Column('goal_books_per_year_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('usersettings', sa.Column('goal_books_per_year', sa.Integer(), nullable=False, server_default='25'))


def downgrade() -> None:
    op.drop_column('usersettings', 'goal_books_per_year')
    op.drop_column('usersettings', 'goal_books_per_year_enabled')
    op.drop_column('usersettings', 'goal_books_per_month')
    op.drop_column('usersettings', 'goal_books_per_month_enabled')
    op.drop_column('usersettings', 'goal_pages_per_month')
    op.drop_column('usersettings', 'goal_pages_per_month_enabled')
    op.drop_column('usersettings', 'goal_pages_per_day')
    op.drop_column('usersettings', 'goal_pages_per_day_enabled')