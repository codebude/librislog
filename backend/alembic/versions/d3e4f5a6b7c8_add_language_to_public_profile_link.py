"""add language to public_profile_link

Revision ID: d3e4f5a6b7c8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-10 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("public_profile_link") as batch_op:
        batch_op.add_column(sa.Column("language", sa.String(length=10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("public_profile_link") as batch_op:
        batch_op.drop_column("language")
