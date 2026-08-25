"""Author parsing, synchronization, and query helpers.

Authors are stored per-user in the ``author`` table and linked to books through
the ``book_author`` relation table, mirroring how tags work. The public API keeps
an ``author`` joined-string field for backward compatibility alongside the new
``authors`` list field.
"""

import re

from sqlmodel import Session, col, select

from app.models import Author, Book, BookAuthor
from app.time_utils import utcnow


def normalize_author_name(name: str) -> str | None:
    """Trim whitespace and collapse internal whitespace in an author name."""
    cleaned = " ".join(name.strip().split())
    return cleaned or None


def normalize_author_list(names: list[str] | None) -> list[str]:
    """Normalize a list of author names from the API or UI.

    Trims whitespace, collapses internal whitespace, and deduplicates
    case-insensitively while preserving the first-cased spelling seen.
    """
    if not names:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        cleaned = normalize_author_name(name)
        if cleaned is None:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def parse_legacy_author(raw: str | None) -> list[str]:
    """Parse a legacy comma-separated author string (for BookCreate/Update.author).

    Mirrors tag parsing: split on commas, trim, collapse whitespace, deduplicate.
    """
    if not raw:
        return []
    seen: set[str] = set()
    parsed: list[str] = []
    for piece in raw.split(","):
        cleaned = normalize_author_name(piece)
        if cleaned is None:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        parsed.append(cleaned)
    return parsed


def parse_authors(raw: str | list[str] | None) -> list[str]:
    """Normalize an author value from a file import.

    A list contributes one author per entry. A string is passed through
    ``split_author_string``: it stays a single author unless it contains a
    ``;``, `` & ``, or `` and `` separator (how the CSV export writes the
    ``authors`` column), so it can round-trip. Commas inside a name like
    ``"Asimov, Isaac"`` are always preserved. The result is deduplicated
    case-insensitively while preserving the first spelling seen.
    """
    if raw is None:
        return []
    pieces = split_author_string(raw) if isinstance(raw, str) else raw
    seen: set[str] = set()
    result: list[str] = []
    for piece in pieces:
        name = normalize_author_name(piece)
        if name is None:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


def resolve_authors_payload(
    author: str | None = None,
    authors: list[str] | None = None,
) -> list[str] | None:
    """Resolve the hybrid create/update payload.

    * If ``authors`` is provided (including ``[]``), use it.
    * Otherwise fall back to parsing the legacy ``author`` string.
    * If neither is provided, return None so the caller can treat it as
      "not provided" (for updates) or "empty" (for creates).
    """
    if authors is not None:
        return normalize_author_list(authors)
    if author is not None:
        return parse_legacy_author(author)
    return None


# Conservative separator regex used only when an external source returns a
# single delimited string. Never splits on commas.
_AUTHOR_SEPARATOR_RE = re.compile(
    r"\s*;\s*|\s+&\s+|\s+and\s+",
    flags=re.IGNORECASE,
)


def split_author_string(value: str | None) -> list[str]:
    """Split a single author string from an external source.

    Only semicolons, ``" & "``, and ``" and "`` are treated as separators, so
    names containing commas (e.g. ``"Asimov, Isaac"``) are preserved.
    If no known separator is found, the whole string is returned as one author.
    """
    if not value:
        return []
    if not _AUTHOR_SEPARATOR_RE.search(value):
        name = normalize_author_name(value)
        return [name] if name else []
    parts = _AUTHOR_SEPARATOR_RE.split(value)
    return [name for name in (normalize_author_name(p) for p in parts) if name]


def sync_book_authors(
    session: Session, user_id: int, book_id: int, names: list[str] | None
) -> None:
    """Set the authors for a book to *names*, creating Author rows as needed."""
    parsed = normalize_author_list(names)

    existing_links = list(
        session.exec(select(BookAuthor).where(BookAuthor.book_id == book_id)).all()
    )
    existing_author_ids = {link.author_id for link in existing_links}

    if not parsed:
        for link in existing_links:
            session.delete(link)
        return

    existing_authors = list(
        session.exec(
            select(Author).where(Author.user_id == user_id, col(Author.name).in_(parsed))
        ).all()
    )
    name_to_author = {author.name: author for author in existing_authors}

    for name in parsed:
        if name in name_to_author:
            continue
        author = Author(user_id=user_id, name=name, created_at=utcnow())
        session.add(author)
        session.flush()
        name_to_author[name] = author

    target_ids: set[int] = set()
    for name in parsed:
        author_id = name_to_author[name].id
        if author_id is not None:
            target_ids.add(author_id)

    for author_id in target_ids - existing_author_ids:
        session.add(BookAuthor(book_id=book_id, author_id=author_id))

    for link in existing_links:
        if link.author_id not in target_ids:
            session.delete(link)


def cleanup_orphan_authors(session: Session, user_id: int) -> None:
    """Delete authors of this user that are no longer linked to any book."""
    linked_ids = set(
        session.exec(
            select(BookAuthor.author_id).where(
                col(BookAuthor.author_id).in_(
                    select(Author.id).where(Author.user_id == user_id)
                )
            )
        ).all()
    )
    authors = list(session.exec(select(Author).where(Author.user_id == user_id)).all())
    for author in authors:
        if author.id not in linked_ids:
            session.delete(author)


def authors_list_for_book(session: Session, book_id: int | None) -> list[str]:
    """Return ordered author names for a book."""
    if book_id is None:
        return []
    names = list(
        session.exec(
            select(Author.name)
            .join(BookAuthor, col(BookAuthor.author_id) == col(Author.id))
            .where(BookAuthor.book_id == book_id)
            .order_by(col(Author.name).asc())
        ).all()
    )
    return names


def load_authors_batch(session: Session, book_ids: list[int]) -> dict[int, list[str]]:
    """Batch-load author lists for many book IDs."""
    if not book_ids:
        return {}
    rows = session.exec(
        select(BookAuthor.book_id, Author.name)
        .join(Author, col(Author.id) == col(BookAuthor.author_id))
        .where(col(BookAuthor.book_id).in_(book_ids))
        .order_by(col(BookAuthor.book_id), col(Author.name).asc())
    ).all()
    result: dict[int, list[str]] = {}
    for book_id, name in rows:
        result.setdefault(book_id, []).append(name)
    return {bid: names for bid, names in result.items()}


def join_authors(names: list[str] | None) -> str | None:
    """Join author names for the legacy ``author`` response field."""
    if not names:
        return None
    return ", ".join(names)