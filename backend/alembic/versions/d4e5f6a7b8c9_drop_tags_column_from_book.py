"""drop tags column from book

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-05-12 15:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.drop_column("tags")


def downgrade() -> None:
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags", sa.String(), nullable=True))
