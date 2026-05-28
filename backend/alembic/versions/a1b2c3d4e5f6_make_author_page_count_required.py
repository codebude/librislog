"""Make author and page_count required with defaults.

Revision ID: a1b2c3d4e5f6
Revises: f4c2b8a1d9e3
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'bfe919c8b47b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Set defaults for existing NULLs
    op.execute("UPDATE book SET author = '' WHERE author IS NULL")
    op.execute("UPDATE book SET page_count = 0 WHERE page_count IS NULL")

    with op.batch_alter_table('book') as batch_op:
        batch_op.alter_column('author',
                              existing_type=sa.String(),
                              nullable=False,
                              server_default='')
        batch_op.alter_column('page_count',
                              existing_type=sa.Integer(),
                              nullable=False,
                              server_default='0')


def downgrade() -> None:
    with op.batch_alter_table('book') as batch_op:
        batch_op.alter_column('author',
                              existing_type=sa.String(),
                              nullable=True,
                              server_default=None)
        batch_op.alter_column('page_count',
                              existing_type=sa.Integer(),
                              nullable=True,
                              server_default=None)
