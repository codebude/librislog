"""add_credentials_version_to_user

Revision ID: 784de5d2bf69
Revises: 1a2b3c4d5e6f
Create Date: 2026-06-22 10:01:24.732359

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "784de5d2bf69"
down_revision: Union[str, Sequence[str], None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("credentials_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("user", "credentials_version")
