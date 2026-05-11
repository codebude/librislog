"""add oidc link table

Revision ID: c3f4d7a9b2e1
Revises: b0b8f41f6b20
Create Date: 2026-05-11 23:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3f4d7a9b2e1"
down_revision: Union[str, Sequence[str], None] = "b0b8f41f6b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oidclink",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(), nullable=False),
        sa.Column("oidc_sub", sa.String(), nullable=False),
        sa.Column("oidc_email", sa.String(), nullable=True),
        sa.Column("oidc_name", sa.String(), nullable=True),
        sa.Column("linked_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("oidc_sub"),
    )
    op.create_index(op.f("ix_oidclink_user_id"), "oidclink", ["user_id"], unique=False)
    op.create_index(op.f("ix_oidclink_provider_name"), "oidclink", ["provider_name"], unique=False)
    op.create_index(op.f("ix_oidclink_oidc_sub"), "oidclink", ["oidc_sub"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_oidclink_oidc_sub"), table_name="oidclink")
    op.drop_index(op.f("ix_oidclink_provider_name"), table_name="oidclink")
    op.drop_index(op.f("ix_oidclink_user_id"), table_name="oidclink")
    op.drop_table("oidclink")
