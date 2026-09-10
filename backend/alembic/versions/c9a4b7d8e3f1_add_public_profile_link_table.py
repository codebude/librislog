"""add public_profile_link table for shareable public profiles

Revision ID: c9a4b7d8e3f1
Revises: 7a8b9c0d1e2f
Create Date: 2026-09-09 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9a4b7d8e3f1"
down_revision: Union[str, Sequence[str], None] = "7a8b9c0d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the public_profile_link table."""
    op.create_table(
        "public_profile_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token_prefix", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("audience", sa.String(length=32), nullable=False),
        sa.Column("visibility_config_json", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_public_profile_link_user_id", "public_profile_link", ["user_id"], unique=False)
    op.create_index("ix_public_profile_link_token_prefix", "public_profile_link", ["token_prefix"], unique=False)
    op.create_index("ix_public_profile_link_token_hash", "public_profile_link", ["token_hash"], unique=True)


def downgrade() -> None:
    """Drop the public_profile_link table."""
    op.drop_index("ix_public_profile_link_token_hash", table_name="public_profile_link")
    op.drop_index("ix_public_profile_link_token_prefix", table_name="public_profile_link")
    op.drop_index("ix_public_profile_link_user_id", table_name="public_profile_link")
    op.drop_table("public_profile_link")