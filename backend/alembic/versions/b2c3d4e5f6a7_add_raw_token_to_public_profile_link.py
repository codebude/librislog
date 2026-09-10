"""add raw token to public_profile_link

Revision ID: b2c3d4e5f6a7
Revises: c9a4b7d8e3f1
Create Date: 2026-09-10 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "c9a4b7d8e3f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("public_profile_link") as batch_op:
        batch_op.add_column(sa.Column("token", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("public_profile_link") as batch_op:
        batch_op.drop_column("token")
