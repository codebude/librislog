"""create tag and book_tag tables and backfill

Revision ID: c1d2e3f4a5b6
Revises: b7a4d2e9c1f0
Create Date: 2026-05-12 15:05:00
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "b7a4d2e9c1f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("tag"):
        op.create_table(
            "tag",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.UniqueConstraint("user_id", "name", name="uq_tag_user_id_name"),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_tag_indexes = {idx["name"] for idx in inspector.get_indexes("tag")}
    if "ix_tag_user_id" not in existing_tag_indexes:
        op.create_index("ix_tag_user_id", "tag", ["user_id"], unique=False)
    if "ix_tag_name" not in existing_tag_indexes:
        op.create_index("ix_tag_name", "tag", ["name"], unique=False)

    if not inspector.has_table("book_tag"):
        op.create_table(
            "book_tag",
            sa.Column("book_id", sa.Integer(), nullable=False),
            sa.Column("tag_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["book_id"], ["book.id"]),
            sa.ForeignKeyConstraint(["tag_id"], ["tag.id"]),
            sa.PrimaryKeyConstraint("book_id", "tag_id"),
        )

    existing_book_tag_indexes = {idx["name"] for idx in inspector.get_indexes("book_tag")}
    if "ix_book_tag_book_id" not in existing_book_tag_indexes:
        op.create_index("ix_book_tag_book_id", "book_tag", ["book_id"], unique=False)
    if "ix_book_tag_tag_id" not in existing_book_tag_indexes:
        op.create_index("ix_book_tag_tag_id", "book_tag", ["tag_id"], unique=False)

    rows = bind.execute(sa.text("SELECT id, user_id, tags FROM book WHERE tags IS NOT NULL AND tags <> ''")).fetchall()

    for book_id, user_id, raw_tags in rows:
        tags = []
        seen = set()
        for part in raw_tags.split(","):
            name = " ".join(part.strip().split())
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            tags.append(name)

        for name in tags:
            tag_id = bind.execute(
                sa.text("SELECT id FROM tag WHERE user_id = :user_id AND name = :name"),
                {"user_id": user_id, "name": name},
            ).scalar()
            if tag_id is None:
                tag_id = bind.execute(
                    sa.text("INSERT INTO tag (user_id, name) VALUES (:user_id, :name) RETURNING id"),
                    {"user_id": user_id, "name": name},
                ).scalar_one()

            bind.execute(
                sa.text(
                    "INSERT OR IGNORE INTO book_tag (book_id, tag_id) VALUES (:book_id, :tag_id)"
                ),
                {"book_id": book_id, "tag_id": tag_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("book_tag"):
        existing_book_tag_indexes = {idx["name"] for idx in inspector.get_indexes("book_tag")}
        if "ix_book_tag_tag_id" in existing_book_tag_indexes:
            op.drop_index("ix_book_tag_tag_id", table_name="book_tag")
        if "ix_book_tag_book_id" in existing_book_tag_indexes:
            op.drop_index("ix_book_tag_book_id", table_name="book_tag")
        op.drop_table("book_tag")

    if inspector.has_table("tag"):
        existing_tag_indexes = {idx["name"] for idx in inspector.get_indexes("tag")}
        if "ix_tag_name" in existing_tag_indexes:
            op.drop_index("ix_tag_name", table_name="tag")
        if "ix_tag_user_id" in existing_tag_indexes:
            op.drop_index("ix_tag_user_id", table_name="tag")
        op.drop_table("tag")
