"""add did_not_finish reading status

Revision ID: 4d8b9a2c1e6f
Revises: 9e90ac72c767
Create Date: 2026-05-11 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d8b9a2c1e6f'
down_revision: Union[str, Sequence[str], None] = '9e90ac72c767'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_READING_STATUS = sa.Enum(
    'want_to_read',
    'currently_reading',
    'read',
    name='readingstatus',
)

NEW_READING_STATUS = sa.Enum(
    'want_to_read',
    'currently_reading',
    'read',
    'did_not_finish',
    name='readingstatus',
)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('book') as batch_op:
        batch_op.alter_column(
            'reading_status',
            existing_type=OLD_READING_STATUS,
            type_=NEW_READING_STATUS,
            existing_nullable=False,
            nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "UPDATE book SET reading_status = 'want_to_read' WHERE reading_status = 'did_not_finish'"
    )
    with op.batch_alter_table('book') as batch_op:
        batch_op.alter_column(
            'reading_status',
            existing_type=NEW_READING_STATUS,
            type_=OLD_READING_STATUS,
            existing_nullable=False,
            nullable=False,
        )
