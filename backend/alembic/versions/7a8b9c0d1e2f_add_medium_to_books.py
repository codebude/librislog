"""add optional medium to books

Revision ID: 7a8b9c0d1e2f
Revises: f3a5b7c9d1e2
Create Date: 2026-09-08 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, Sequence[str], None] = "f3a5b7c9d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.add_column(sa.Column("medium", sa.String(length=32), nullable=True))
        batch_op.create_index("ix_book_medium", ["medium"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.drop_index("ix_book_medium")
        batch_op.drop_column("medium")
