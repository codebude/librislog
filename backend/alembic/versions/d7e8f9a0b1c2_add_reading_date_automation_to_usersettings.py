"""add reading date automation settings

Revision ID: d7e8f9a0b1c2
Revises: 0a1b2c3d4e5f
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usersettings",
        sa.Column("auto_set_date_started", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "usersettings",
        sa.Column("auto_set_date_finished", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("usersettings", "auto_set_date_finished")
    op.drop_column("usersettings", "auto_set_date_started")
