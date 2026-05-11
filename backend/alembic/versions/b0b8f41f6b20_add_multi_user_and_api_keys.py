"""add multi-user and api key support

Revision ID: b0b8f41f6b20
Revises: a31c9e2f7b44
Create Date: 2026-05-11 14:30:00.000000

"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.auth import encrypt_api_key, generate_api_key, get_api_key_prefix, get_password_hash, hash_api_key


revision: str = "b0b8f41f6b20"
down_revision: Union[str, Sequence[str], None] = "a31c9e2f7b44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("firstname", sa.String(), nullable=False),
        sa.Column("lastname", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.Enum("admin", "user", name="userrole"), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=False)
    op.create_index(op.f("ix_user_role"), "user", ["role"], unique=False)

    op.create_table(
        "usersettings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_usersettings_user_id"), "usersettings", ["user_id"], unique=False)

    op.create_table(
        "apikey",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("key_encrypted", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(op.f("ix_apikey_user_id"), "apikey", ["user_id"], unique=False)
    op.create_index(op.f("ix_apikey_key_prefix"), "apikey", ["key_prefix"], unique=False)
    op.create_index(op.f("ix_apikey_key_hash"), "apikey", ["key_hash"], unique=False)
    op.create_index(op.f("ix_apikey_is_primary"), "apikey", ["is_primary"], unique=False)

    with op.batch_alter_table("book") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_index(op.f("ix_book_user_id"), ["user_id"], unique=False)
        batch_op.create_foreign_key("fk_book_user_id_user", "user", ["user_id"], ["id"])

    now = datetime.now(timezone.utc)
    conn = op.get_bind()
    book_count = conn.execute(sa.text("SELECT COUNT(*) FROM book")).scalar_one()
    if book_count > 0:
        default_password = "admin"
        primary_api_key = generate_api_key()
        conn.execute(
            sa.text(
                """
                INSERT INTO user (firstname, lastname, email, role, hashed_password, created_at, updated_at)
                VALUES (:firstname, :lastname, :email, :role, :hashed_password, :created_at, :updated_at)
                """
            ),
            {
                "firstname": "Admin",
                "lastname": "User",
                "email": "admin@librislog.local",
                "role": "admin",
                "hashed_password": get_password_hash(default_password),
                "created_at": now,
                "updated_at": now,
            },
        )
        admin_id = conn.execute(sa.text("SELECT id FROM user WHERE email = 'admin@librislog.local' LIMIT 1")).scalar_one()
        conn.execute(sa.text("UPDATE book SET user_id = :uid WHERE user_id IS NULL"), {"uid": admin_id})
        conn.execute(
            sa.text("INSERT INTO usersettings (user_id, language) VALUES (:uid, 'en')"),
            {"uid": admin_id},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO apikey
                    (user_id, key_prefix, key_hash, key_encrypted, description, is_primary, created_at, last_used_at, revoked_at)
                VALUES
                    (:user_id, :key_prefix, :key_hash, :key_encrypted, :description, :is_primary, :created_at, :last_used_at, :revoked_at)
                """
            ),
            {
                "user_id": admin_id,
                "key_prefix": get_api_key_prefix(primary_api_key),
                "key_hash": hash_api_key(primary_api_key),
                "key_encrypted": encrypt_api_key(primary_api_key),
                "description": "Primary app key",
                "is_primary": True,
                "created_at": now,
                "last_used_at": None,
                "revoked_at": None,
            },
        )

    with op.batch_alter_table("book") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.drop_constraint("fk_book_user_id_user", type_="foreignkey")
        batch_op.drop_index(op.f("ix_book_user_id"))
        batch_op.drop_column("user_id")

    op.drop_index(op.f("ix_apikey_is_primary"), table_name="apikey")
    op.drop_index(op.f("ix_apikey_key_hash"), table_name="apikey")
    op.drop_index(op.f("ix_apikey_key_prefix"), table_name="apikey")
    op.drop_index(op.f("ix_apikey_user_id"), table_name="apikey")
    op.drop_table("apikey")

    op.drop_index(op.f("ix_usersettings_user_id"), table_name="usersettings")
    op.drop_table("usersettings")

    op.drop_index(op.f("ix_user_role"), table_name="user")
    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")

    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS userrole")
