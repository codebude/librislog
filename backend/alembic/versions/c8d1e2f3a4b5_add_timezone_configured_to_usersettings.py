"""add timezone_configured to usersettings

Revision ID: c8d1e2f3a4b5
Revises: b4c5d6e7f8a9
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usersettings",
        sa.Column(
            "timezone_configured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Preserve the old behaviour for existing accounts: a non-UTC value was
    # either picked by the user or already auto-detected, while the UTC default
    # still needs the one-time detection on the next login.
    op.execute("UPDATE usersettings SET timezone_configured = true WHERE timezone != 'UTC'")


def downgrade() -> None:
    # The explicit-choice bit cannot be reconstructed by a later upgrade:
    # UTC rows are treated as unconfigured again and re-detected once.
    op.drop_column("usersettings", "timezone_configured")
