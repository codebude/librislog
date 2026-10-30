#!/usr/bin/env python3
"""Generate docs/guide/database-layout.md from SQLModel metadata.

Usage:
    uv run --directory backend python scripts/gen_db_docs.py
"""

import sys
from pathlib import Path
from datetime import datetime
from enum import Enum as PyEnum

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import sqlalchemy as sa
from sqlalchemy import TypeDecorator
from sqlmodel import SQLModel
from app import models  # noqa: E402
from app.models import UtcDateTime

OUTPUT = Path(BACKEND_DIR).parent / "docs" / "guide" / "database-layout.md"
NOW = datetime.now().strftime("%Y-%m-%d")


def _model_for_table(name: str):
    for obj in models.__dict__.values():
        if isinstance(obj, type) and issubclass(obj, SQLModel) and hasattr(obj, '__tablename__'):
            if obj.__tablename__ == name:
                return obj
    return None


def _resolve_type(col: sa.Column) -> str:
    t = col.type
    if isinstance(t, UtcDateTime):
        return "DATETIME"
    if isinstance(t, sa.Enum):
        return "VARCHAR"
    return str(t).upper()


def _resolve_constraints(col: sa.Column) -> str:
    parts = []
    if col.primary_key:
        parts.append("PK")
    for fk in col.foreign_keys:
        parts.append(f"FK → {fk.column.table.name}.{fk.column.name}")
    if col.unique and not col.primary_key:
        parts.append("UNIQUE")
    if not col.nullable and not col.primary_key:
        parts.append("NOT NULL")
    if col.index and not col.primary_key and not col.unique:
        parts.append("INDEX")
    return ", ".join(parts)


def _field_metadata(col: sa.Column):
    model = _model_for_table(col.table.name)
    if model and col.name in (model.model_fields or {}):
        return model.model_fields[col.name]
    return None


def _resolve_notes(col: sa.Column) -> str:
    note_parts = []

    if isinstance(col.type, UtcDateTime):
        note_parts.append("UTC")

    single_pk = len(col.table.primary_key.columns) == 1
    if col.primary_key and single_pk and isinstance(col.type, sa.Integer):
        note_parts.append("Auto-increment")

    # default value
    if col.default is not None:
        arg = getattr(col.default, "arg", None)
        if arg is not None and not callable(arg):
            if isinstance(arg, PyEnum):
                note_parts.append(f"default `{arg.value}`")
            elif isinstance(arg, str):
                note_parts.append(f"default `{arg}`")
            else:
                note_parts.append(f"default {arg}")

    # ge / le from pydantic field metadata
    field = _field_metadata(col)
    if field:
        for item in field.metadata:
            cls_name = type(item).__name__
            if cls_name == "Ge":
                note_parts.append(f"≥ {item.ge}")
            elif cls_name == "Le":
                note_parts.append(f"≤ {item.le}")

    return "; ".join(note_parts) if note_parts else ""


def _cardinality(col: sa.Column) -> str:
    if col.unique:
        return "o|" if col.nullable else "||"
    return "o{" if col.nullable else "|{"


def _generate_er_diagram(tables) -> str:
    lines = ["```mermaid", "erDiagram", ""]
    rels = []
    seen = set()
    for table in tables:
        for col in table.columns:
            for fk in col.foreign_keys:
                parent = fk.column.table.name
                child = table.name
                key = (parent, child)
                if key not in seen:
                    seen.add(key)
                    rels.append((parent, child, col))
    card_map = {"||": "1:1", "|{": "1:N", "o|": "0..1", "o{": "0..N"}
    for parent, child, col in rels:
        card = _cardinality(col)
        label = card_map.get(card, card)
        lines.append(f'    {parent} ||--{card} {child} : "{label}"')
    lines.append("")
    for table in tables:
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            typ = _resolve_type(col).lower()
            name = col.name
            key_flag = "PK" if col.primary_key else ("UK" if col.unique else "")
            parts = [typ, name]
            if key_flag:
                parts.append(key_flag)
            lines.append(f"        {' '.join(parts)}")
        lines.append("    }")
        lines.append("")
    lines.append("```")
    return "\n".join(lines)


def _generate_table_docs(tables) -> str:
    lines = ["## Tables", ""]
    for table in tables:
        model = _model_for_table(table.name)
        doc = (model.__doc__ or "").strip() if model else ""

        lines.append(f"### `{table.name}`")
        lines.append("")
        if doc:
            lines.append(doc)
            lines.append("")

        lines.append("| Column | Type | Constraints | Notes |")
        lines.append("|--------|------|-------------|-------|")
        for col in table.columns:
            typ = _resolve_type(col)
            cnst = _resolve_constraints(col)
            notes = _resolve_notes(col)
            lines.append(f"| `{col.name}` | `{typ}` | {cnst} | {notes} |")

        ucs = [uc for uc in table.constraints
               if isinstance(uc, sa.UniqueConstraint)
               and not any(c.unique for c in uc.columns)]
        if ucs:
            lines.append("")
            for uc in ucs:
                col_names = ", ".join(c.name for c in uc.columns)
                lines.append(f"**Unique constraint:** `({col_names})`: {uc.name}")

        lines.append("")
    return "\n".join(lines)


def _generate_enum_docs() -> str:
    lines = ["## Enums", ""]
    for name in dir(models):
        cls = getattr(models, name)
        if isinstance(cls, type) and issubclass(cls, PyEnum) and cls.__module__ == models.__name__:
            lines.append(f"### `{name}`")
            lines.append("")
            lines.append("| Value | Meaning |")
            lines.append("|-------|---------|")
            for member in cls:
                lines.append(f"| `{member.value}` | {member.value.replace('_', ' ').title()} |")
            lines.append("")
    return "\n".join(lines)


def main():
    tables = list(SQLModel.metadata.sorted_tables)

    content = f"""# Database Layout

> _Auto-generated from SQLModel metadata on {NOW}._

This page documents the LibrisLog database schema. It is intended for
developers who need to understand the data model, write queries, or extend
the application.

{_generate_er_diagram(tables)}

{_generate_table_docs(tables)}

{_generate_enum_docs()}

## Conventions

- **Timestamps** are stored as UTC via the `UtcDateTime` type decorator.
  Values are stored as naive UTC in SQLite and returned as timezone-aware
  `datetime` objects by the application.
- **Soft deletes** — `ApiKey` and `EmbedToken` use a `revoked_at` timestamp
  instead of `DELETE`. Revoked entries are excluded from all queries.
- **Foreign keys** — all user-owned tables reference `user.id` via foreign
  key constraints. Cascading behavior is handled in application code (not
  at the database level).
- **Unique constraints**: compound constraints like `(user_id, isbn)` on
  `book` and `(user_id, name)` on `tag` enforce per-user uniqueness without
  restricting other users.
"""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content)
    print(f"✓ Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
