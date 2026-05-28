"""flip_import_mapping_direction

Revision ID: c31124664378
Revises: a1b2c3d4e5f6
Create Date: 2026-05-25 18:49:51.798647

"""
import logging
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# revision identifiers, used by Alembic.
revision: str = 'c31124664378'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _flip_mapping_json(mapping_json: str, mapping_id: int) -> str:
    """Flip mapping from {source: target} to {target: source}."""
    mapping = json.loads(mapping_json)
    # Warn if duplicate source→target mappings will lose data
    seen: set[str] = set()
    for k, v in mapping.items():
        if v in seen:
            logger.warning(
                "Import mapping %d: multiple sources map to target '%s'. "
                "Only the last source ('%s') will be preserved after flip.",
                mapping_id, v, k,
            )
        seen.add(v)
    flipped = {v: k for k, v in mapping.items()}
    return json.dumps(flipped)


def upgrade() -> None:
    """Flip all import mapping directions from source→target to target→source."""
    conn = op.get_bind()
    session = Session(conn)
    
    # Get all import mappings
    rows = conn.execute(sa.text("SELECT id, mapping_json FROM import_mapping")).fetchall()
    
    for row_id, mapping_json in rows:
        if not mapping_json:
            continue
        flipped = _flip_mapping_json(mapping_json, row_id)
        conn.execute(
            sa.text("UPDATE import_mapping SET mapping_json = :mapping WHERE id = :id"),
            {"mapping": flipped, "id": row_id}
        )
    
    session.commit()


def downgrade() -> None:
    """Flip all import mapping directions back from target→source to source→target."""
    conn = op.get_bind()
    session = Session(conn)
    
    # Applying the same inversion restores the original format
    rows = conn.execute(sa.text("SELECT id, mapping_json FROM import_mapping")).fetchall()
    
    for row_id, mapping_json in rows:
        if not mapping_json:
            continue
        flipped = _flip_mapping_json(mapping_json, row_id)
        conn.execute(
            sa.text("UPDATE import_mapping SET mapping_json = :mapping WHERE id = :id"),
            {"mapping": flipped, "id": row_id}
        )
    
    session.commit()
