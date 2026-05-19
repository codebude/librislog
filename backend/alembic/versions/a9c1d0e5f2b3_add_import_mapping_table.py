"""add import mapping table

Revision ID: a9c1d0e5f2b3
Revises: f4c2b8a1d9e3
Create Date: 2026-05-18 15:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9c1d0e5f2b3"
down_revision: Union[str, Sequence[str], None] = "f4c2b8a1d9e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("schema_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_fields_json", sa.String(), nullable=False),
        sa.Column("mapping_json", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_import_mapping_user_id_name"),
    )
    op.create_index(op.f("ix_import_mapping_schema_fingerprint"), "import_mapping", ["schema_fingerprint"], unique=False)
    op.create_index(op.f("ix_import_mapping_user_id"), "import_mapping", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_import_mapping_user_id"), table_name="import_mapping")
    op.drop_index(op.f("ix_import_mapping_schema_fingerprint"), table_name="import_mapping")
    op.drop_table("import_mapping")
