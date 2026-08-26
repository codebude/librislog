"""create author and book_author tables and backfill

Revision ID: c7a8d9e1f2a3
Revises: e2f3a4b5c6d7
Create Date: 2026-08-24 21:00:00
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c7a8d9e1f2a3"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("author"):
        op.create_table(
            "author",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.UniqueConstraint("user_id", "name", name="uq_author_user_id_name"),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_author_indexes = {idx["name"] for idx in inspector.get_indexes("author")}
    if "ix_author_user_id" not in existing_author_indexes:
        op.create_index("ix_author_user_id", "author", ["user_id"], unique=False)
    if "ix_author_name" not in existing_author_indexes:
        op.create_index("ix_author_name", "author", ["name"], unique=False)

    if not inspector.has_table("book_author"):
        op.create_table(
            "book_author",
            sa.Column("book_id", sa.Integer(), nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["book_id"], ["book.id"]),
            sa.ForeignKeyConstraint(["author_id"], ["author.id"]),
            sa.PrimaryKeyConstraint("book_id", "author_id"),
        )

    existing_book_author_indexes = {idx["name"] for idx in inspector.get_indexes("book_author")}
    if "ix_book_author_book_id" not in existing_book_author_indexes:
        op.create_index("ix_book_author_book_id", "book_author", ["book_id"], unique=False)
    if "ix_book_author_author_id" not in existing_book_author_indexes:
        op.create_index("ix_book_author_author_id", "book_author", ["author_id"], unique=False)

    # Backfill authors from the legacy book.author column. Each legacy value is
    # treated as a single author name so names like "Asimov, Isaac" are preserved.
    rows = bind.execute(
        sa.text("SELECT id, user_id, author FROM book WHERE author IS NOT NULL AND author <> ''")
    ).fetchall()

    for book_id, user_id, raw in rows:
        name = " ".join(raw.strip().split())
        if not name:
            continue

        author_id = bind.execute(
            sa.text("SELECT id FROM author WHERE user_id = :user_id AND name = :name"),
            {"user_id": user_id, "name": name},
        ).scalar()
        if author_id is None:
            author_id = bind.execute(
                sa.text("INSERT INTO author (user_id, name) VALUES (:user_id, :name) RETURNING id"),
                {"user_id": user_id, "name": name},
            ).scalar_one()

        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO book_author (book_id, author_id) VALUES (:book_id, :author_id)"
            ),
            {"book_id": book_id, "author_id": author_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("book_author"):
        existing_book_author_indexes = {idx["name"] for idx in inspector.get_indexes("book_author")}
        if "ix_book_author_author_id" in existing_book_author_indexes:
            op.drop_index("ix_book_author_author_id", table_name="book_author")
        if "ix_book_author_book_id" in existing_book_author_indexes:
            op.drop_index("ix_book_author_book_id", table_name="book_author")
        op.drop_table("book_author")

    if inspector.has_table("author"):
        existing_author_indexes = {idx["name"] for idx in inspector.get_indexes("author")}
        if "ix_author_name" in existing_author_indexes:
            op.drop_index("ix_author_name", table_name="author")
        if "ix_author_user_id" in existing_author_indexes:
            op.drop_index("ix_author_user_id", table_name="author")
        op.drop_table("author")