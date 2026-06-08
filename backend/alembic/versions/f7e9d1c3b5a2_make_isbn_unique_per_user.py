"""make isbn unique per user instead of globally

Revision ID: f7e9d1c3b5a2
Revises: 86fa9b4f6d61
Create Date: 2026-06-08 07:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7e9d1c3b5a2"
down_revision: Union[str, Sequence[str], None] = "86fa9b4f6d61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _recreate_book_table(conn, *, global_unique: bool) -> None:
    """Recreate the book table with either a global or per-user ISBN unique constraint."""
    old_cols = []
    for col in sa.inspect(conn).get_columns("book"):
        old_cols.append(col)

    col_names = [c["name"] for c in old_cols]
    pk_cols = [c["name"] for c in old_cols if c.get("primary_key")]
    pk_name = pk_cols[0] if pk_cols else "id"

    col_defs = []
    for c in old_cols:
        typ = str(c["type"])
        nullable = "NOT NULL" if not c.get("nullable", True) else ""
        col_defs.append(f"  {c['name']} {typ} {nullable}".strip())

    extras = [f"PRIMARY KEY ({pk_name})"]
    for fk in sa.inspect(conn).get_foreign_keys("book"):
        extras.append(
            f"FOREIGN KEY({fk['constrained_columns'][0]}) REFERENCES {fk['referred_table']}({fk['referred_columns'][0]})"
        )
    extras.append("UNIQUE (isbn)" if global_unique else "UNIQUE (user_id, isbn)")

    col_list = ", ".join(col_names)
    extra_sql = ",\n  ".join(extras)

    sql = f"""CREATE TABLE book__new (
  {',\n  '.join(col_defs)},
  {extra_sql}
)"""
    conn.execute(sa.text(sql))
    conn.execute(sa.text(f"INSERT INTO book__new ({col_list}) SELECT {col_list} FROM book"))

    for idx in sa.inspect(conn).get_indexes("book"):
        idx_name = idx["name"]
        if idx_name:
            cols = ", ".join(idx["column_names"])
            unique = "UNIQUE " if idx.get("unique") else ""
            conn.execute(sa.text(f"CREATE {unique}INDEX IF NOT EXISTS {idx_name} ON book__new ({cols})"))

    conn.execute(sa.text("DROP TABLE book"))
    conn.execute(sa.text("ALTER TABLE book__new RENAME TO book"))


def upgrade() -> None:
    _recreate_book_table(op.get_bind(), global_unique=False)


def downgrade() -> None:
    _recreate_book_table(op.get_bind(), global_unique=True)
