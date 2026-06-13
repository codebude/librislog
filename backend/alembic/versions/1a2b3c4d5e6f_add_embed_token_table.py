"""add embed_token table for scoped embed tokens

Revision ID: 1a2b3c4d5e6f
Revises: f7e9d1c3b5a2
Create Date: 2026-06-13 23:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "f7e9d1c3b5a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if "embed_token" not in tables:
        op.create_table(
            "embed_token",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("token_prefix", sa.String(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("scopes", sa.String(), nullable=False, server_default="embed:stats:read"),
            sa.Column("allowed_origins", sa.String(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_embed_token_user_id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_embed_token_token_hash"),
        )
        op.create_index(op.f("ix_embed_token_token_prefix"), "embed_token", ["token_prefix"])
        op.create_index(op.f("ix_embed_token_user_id"), "embed_token", ["user_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if "embed_token" in tables:
        op.drop_table("embed_token")
