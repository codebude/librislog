"""Field-specific search query parsing and SQL filter building.

Search queries may contain field prefixes of the form ``<field>:value`` (or
``<field>:"multi word value"``) to restrict a term to a single field. Any search
part may be negated by prefixing it with ``-``. Unprefixed text is collapsed
into a single phrase that is matched across the default search fields,
preserving the previous behaviour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlmodel import col, or_, select

from app.models import AcquisitionStatus, Book, BookTag, Tag

# Fields that can be targeted with a prefix. The keys are the canonical,
# always-English prefix names; the values are the book model columns.
FIELD_COLUMNS: dict[str, Any] = {
    "author": Book.author,
    "title": Book.title,
    "publisher": Book.publisher,
    "language": Book.language,
    "notes": Book.notes,
    "description": Book.blurb,
}

# Availability is a special case: it maps to an exact enum comparison.
AVAILABILITY_PREFIX = "availability"
TAG_PREFIX = "tag"

SUPPORTED_PREFIXES: frozenset[str] = frozenset(
    [*FIELD_COLUMNS.keys(), AVAILABILITY_PREFIX, TAG_PREFIX]
)

# Default fields searched by an unprefixed term (unchanged from the previous
# single-pattern search).
DEFAULT_SEARCH_COLUMNS: tuple[str, ...] = ("title", "subtitle", "author", "blurb")

# ``<field>:value`` — value is either a quoted string or a non-space token.
_FIELD_TERM_RE = re.compile(r"^([a-zA-Z_]+):(\"(?:\\.|[^\"\\])*\"|\S+)")
_QUOTED_PHRASE_RE = re.compile(r'^"((?:\\.|[^"\\])*)"')
_TOKEN_RE = re.compile(r"^\S+")


@dataclass(frozen=True)
class SearchTerm:
    """A single parsed search term.

    ``field`` is ``None`` for unprefixed terms. ``negated`` indicates a leading
    ``-`` on the term.
    """

    field: str | None
    value: str
    negated: bool = False


def _clean_value(raw: str) -> str:
    """Strip surrounding quotes from a raw value and unescape inner quotes."""
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    elif raw.startswith('"'):
        # Forgiving handling for unclosed quotes: strip the leading quote.
        raw = raw[1:]
    # Unescape backslashes first so an escaped quote after an escaped backslash
    # is not consumed by the wrong pair.
    return raw.replace("\\\\", "\\").replace('\\"', '"')


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def parse_search_query(query: str) -> list[SearchTerm]:
    """Split a search query into field-specific and unprefixed terms.

    Unknown prefixes, malformed quotes, and plain tokens are kept as unprefixed
    terms so the previous cross-field search behaviour is preserved.
    """
    terms: list[SearchTerm] = []
    rest = query.strip()
    while rest:
        negated = False
        if rest.startswith("-"):
            negated = True
            rest = rest[1:].lstrip()
            if not rest:
                break

        match = _FIELD_TERM_RE.match(rest)
        if match:
            prefix, raw_value = match.group(1), match.group(2)
            if prefix.lower() in SUPPORTED_PREFIXES:
                value = _clean_value(raw_value)
                if value:
                    terms.append(SearchTerm(field=prefix.lower(), value=value, negated=negated))
                rest = rest[match.end():].lstrip()
                continue

        match = _QUOTED_PHRASE_RE.match(rest)
        if match:
            value = _clean_value(match.group(1))
            if value:
                terms.append(SearchTerm(field=None, value=value, negated=negated))
            rest = rest[match.end():].lstrip()
            continue

        match = _TOKEN_RE.match(rest)
        if match:
            token = match.group(0)
            if token:
                terms.append(SearchTerm(field=None, value=token, negated=negated))
            rest = rest[match.end():].lstrip()
            continue

        # Unrecognised leading character — skip it and continue.
        rest = rest[1:].lstrip()

    return terms


def _ilike(column: Any, value: str) -> Any:
    """Case-insensitive substring match that never yields NULL.

    ``NOT`` over ``LIKE`` on a NULL column produces NULL, which excludes the row.
    Coalescing to false keeps NULLable fields (subtitle, blurb, publisher, …)
    behaving as "no match" under negation. LIKE wildcards in the value are
    escaped so user input is matched literally.
    """
    escaped = _escape_like(value)
    return sa.func.coalesce(col(column).ilike(f"%{escaped}%", escape="\\"), sa.false())


def _tag_condition(value: str, user_id: int) -> Any:
    """Return a condition matching books that have a tag containing *value*."""
    escaped = _escape_like(value)
    matching_tag_book_ids = (
        select(BookTag.book_id)
        .join(Tag, col(Tag.id) == BookTag.tag_id)
        .where(Tag.user_id == user_id, col(Tag.name).ilike(f"%{escaped}%", escape="\\"))
    )
    return col(Book.id).in_(matching_tag_book_ids)


def _unprefixed_condition(value: str, user_id: int) -> Any:
    """Build the cross-field substring condition for an unprefixed term."""
    return or_(
        *[_ilike(getattr(Book, column), value) for column in DEFAULT_SEARCH_COLUMNS],
        _tag_condition(value, user_id),
    )


def _availability_condition(value: str) -> Any | None:
    """Build the exact acquisition-status condition, or ``None`` if invalid."""
    normalized = value.strip().lower().replace(" ", "_")
    try:
        status = AcquisitionStatus(normalized)
    except ValueError:
        return None
    return Book.acquisition_status == status


def _field_condition(field: str, value: str, user_id: int) -> Any | None:
    """Build the condition for a single field-specific term."""
    if field == AVAILABILITY_PREFIX:
        return _availability_condition(value)
    if field == TAG_PREFIX:
        return _tag_condition(value, user_id)
    column = FIELD_COLUMNS[field]
    return _ilike(column, value)


def apply_search_filter(statement: Any, query: str, user_id: int) -> Any:
    """Return a book SELECT statement restricted by the parsed search query.

    All terms are combined with AND. Negated terms become ``AND NOT(condition)``.
    Positive unprefixed text is collapsed into a single cross-field phrase.
    """
    terms = parse_search_query(query)

    conditions: list[Any] = []

    positive_unprefixed = [term.value for term in terms if term.field is None and not term.negated]
    if positive_unprefixed:
        conditions.append(_unprefixed_condition(" ".join(positive_unprefixed), user_id))

    for term in terms:
        if term.field is None:
            if term.negated:
                conditions.append(sa.not_(_unprefixed_condition(term.value, user_id)))
            continue

        condition = _field_condition(term.field, term.value, user_id)
        if condition is None:
            # Invalid availability value: positive yields no rows, negated is a no-op.
            conditions.append(sa.false() if not term.negated else sa.true())
        elif term.negated:
            conditions.append(sa.not_(condition))
        else:
            conditions.append(condition)

    if conditions:
        return statement.where(sa.and_(*conditions))
    return statement