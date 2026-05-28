"""nest_import_mapping_config

Revision ID: 86fa9b4f6d61
Revises: c31124664378
Create Date: 2026-05-25 22:51:25.715478

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision: str = '86fa9b4f6d61'
down_revision: Union[str, Sequence[str], None] = 'c31124664378'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


import_mapping = table(
    "import_mapping",
    column("id", sa.Integer),
    column("mapping_json", sa.String),
)


def upgrade() -> None:
    """Nest flat source strings into ImportFieldConfig objects."""
    conn = op.get_bind()
    rows = conn.execute(sa.select(import_mapping.c.id, import_mapping.c.mapping_json)).fetchall()
    for row_id, mapping_json in rows:
        if not mapping_json:
            continue
        mapping = json.loads(mapping_json)
        nested = {
            target: {"source": source, "transform": None}
            for target, source in mapping.items()
        }
        conn.execute(
            import_mapping.update().where(import_mapping.c.id == row_id),
            {"mapping_json": json.dumps(nested)},
        )


def downgrade() -> None:
    """Flatten nested ImportFieldConfig objects back to source strings."""
    conn = op.get_bind()
    rows = conn.execute(sa.select(import_mapping.c.id, import_mapping.c.mapping_json)).fetchall()
    for row_id, mapping_json in rows:
        if not mapping_json:
            continue
        mapping = json.loads(mapping_json)
        flat = {
            target: config["source"]
            for target, config in mapping.items()
        }
        conn.execute(
            import_mapping.update().where(import_mapping.c.id == row_id),
            {"mapping_json": json.dumps(flat)},
        )
