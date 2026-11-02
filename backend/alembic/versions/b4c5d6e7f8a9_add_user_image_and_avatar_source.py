"""add user image table and avatar source

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column(
                "avatar_source",
                sa.Enum("animal", "oidc", "upload", name="avatarsource"),
                nullable=False,
                server_default="animal",
            )
        )
        batch_op.create_index(op.f("ix_user_avatar_source"), ["avatar_source"], unique=False)

    op.create_table(
        "user_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="avatar"),
        sa.Column("variant", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("external_url", sa.String(), nullable=True),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "kind",
            "variant",
            name="uq_user_image_user_kind_variant",
        ),
    )
    op.create_index(op.f("ix_user_image_user_id"), "user_image", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_image_kind"), "user_image", ["kind"], unique=False)
    op.create_index(op.f("ix_user_image_variant"), "user_image", ["variant"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_image_variant"), table_name="user_image")
    op.drop_index(op.f("ix_user_image_kind"), table_name="user_image")
    op.drop_index(op.f("ix_user_image_user_id"), table_name="user_image")
    op.drop_table("user_image")

    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index(op.f("ix_user_avatar_source"))
        batch_op.drop_column("avatar_source")
