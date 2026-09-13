"""normalize statistics range settings

Revision ID: 0a1b2c3d4e5f
Revises: d3e4f5a6b7c8
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The old rolling ranges have no direct equivalent in the calendar-based selector.
    op.execute(
        sa.text(
            "UPDATE usersettings "
            "SET statistics_range = 'alltime' "
            "WHERE statistics_range IN ('6months', '30days')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE usersettings "
            "SET statistics_range = 'this_year' "
            "WHERE statistics_range = '1year'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE usersettings "
            "SET statistics_range = '1year' "
            "WHERE statistics_range = 'this_year'"
        )
    )
