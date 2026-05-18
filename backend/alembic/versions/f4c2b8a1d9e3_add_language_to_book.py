"""add language to book

Revision ID: f4c2b8a1d9e3
Revises: e7f8a9b0c1d2
Create Date: 2026-05-18 10:05:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4c2b8a1d9e3"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.add_column(sa.Column("language", sa.String(length=2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.drop_column("language")
