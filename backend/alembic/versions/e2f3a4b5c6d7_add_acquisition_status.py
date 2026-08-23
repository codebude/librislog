"""add acquisition status to books

Revision ID: e2f3a4b5c6d7
Revises: 1a2b3c4d5e6f
Create Date: 2026-08-22 20:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "784de5d2bf69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.add_column(sa.Column("acquisition_status", sa.String(length=32), nullable=True))
    op.execute("UPDATE book SET acquisition_status = 'owned' WHERE acquisition_status IS NULL")
    with op.batch_alter_table("book") as batch_op:
        batch_op.alter_column("acquisition_status", nullable=False)
        batch_op.create_index("ix_book_acquisition_status", ["acquisition_status"])


def downgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.drop_index("ix_book_acquisition_status")
        batch_op.drop_column("acquisition_status")
