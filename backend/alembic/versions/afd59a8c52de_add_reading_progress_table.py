"""add reading_progress table

Revision ID: afd59a8c52de
Revises: d4e5f6a7b8c9
Create Date: 2026-05-14 00:31:44.376106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'afd59a8c52de'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('reading_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('page', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['book.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reading_progress_book_id'), 'reading_progress', ['book_id'], unique=False)
    op.create_index(op.f('ix_reading_progress_user_id'), 'reading_progress', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reading_progress_user_id'), table_name='reading_progress')
    op.drop_index(op.f('ix_reading_progress_book_id'), table_name='reading_progress')
    op.drop_table('reading_progress')
