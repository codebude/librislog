"""drop author column from book

Revision ID: f1b2c3d4e5a6
Revises: c7a8d9e1f2a3
Create Date: 2026-08-24 21:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1b2c3d4e5a6"
down_revision = "c7a8d9e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.drop_column("author")


def downgrade() -> None:
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.add_column(sa.Column("author", sa.String(), nullable=True, server_default=""))

    # Re-populate book.author from the relation tables before the author tables
    # are dropped by the previous revision's downgrade.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE book SET author = (
                SELECT group_concat(a.name, ', ')
                FROM book_author ba
                JOIN author a ON ba.author_id = a.id
                WHERE ba.book_id = book.id
            )
            """
        )
    )