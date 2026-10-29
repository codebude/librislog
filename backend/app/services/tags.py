"""Tag parsing, synchronization, and query helpers."""

from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, col, func, select, delete

from app.models import Book, BookTag, Tag
from app.schemas import BookRead
from app.services.authors import authors_list_for_book, join_authors
from app.time_utils import utcnow


def parse_tags(raw_tags: str | list[str] | None) -> list[str]:
    """Parse and deduplicate tag names.

    Accepts a comma-separated string (legacy/CSV) or a list of names (JSON
    export/import). A list contributes one tag per entry.

    Returns:
        A list of normalized, unique tag name strings.
    """
    if not raw_tags:
        return []

    pieces: list[str] = raw_tags if isinstance(raw_tags, list) else raw_tags.split(",")

    seen: set[str] = set()
    parsed: list[str] = []
    for piece in pieces:
        normalized = " ".join(str(piece).strip().split())
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        parsed.append(normalized)
    return parsed


def sync_book_tags(
    session: Session, user_id: int, book_id: int, raw_tags: str | list[str] | None
) -> None:
    """Synchronize the tag associations for a book to match *raw_tags*.

    Creates new tags as needed and removes stale BookTag links.

    Args:
        session: Active database session.
        user_id: Owner of the tags.
        book_id: Target book.
        raw_tags: Comma-separated tag names, a list of names, or None (clears all tags).
    """
    parsed = parse_tags(raw_tags)

    existing_links = list(session.exec(select(BookTag).where(BookTag.book_id == book_id)).all())
    existing_tag_ids = {link.tag_id for link in existing_links}

    if not parsed:
        for link in existing_links:
            session.delete(link)
        return

    existing_tags = list(
        session.exec(select(Tag).where(Tag.user_id == user_id, col(Tag.name).in_(parsed))).all()
    )
    name_to_tag = {tag.name: tag for tag in existing_tags}

    for name in parsed:
        if name in name_to_tag:
            continue
        tag = Tag(user_id=user_id, name=name, created_at=utcnow())
        session.add(tag)
        session.flush()
        name_to_tag[name] = tag

    target_tag_ids: set[int] = set()
    for name in parsed:
        tag_id = name_to_tag[name].id
        if tag_id is not None:
            target_tag_ids.add(tag_id)

    for tag_id in target_tag_ids - existing_tag_ids:
        session.add(BookTag(book_id=book_id, tag_id=tag_id))

    for link in existing_links:
        if link.tag_id not in target_tag_ids:
            session.delete(link)


def cleanup_orphan_tags(session: Session, user_id: int) -> None:
    """Delete tags that are no longer associated with any book for this user."""
    tags = list(session.exec(select(Tag).where(Tag.user_id == user_id)).all())
    for tag in tags:
        has_link = session.exec(select(BookTag).where(BookTag.tag_id == tag.id)).first()
        if has_link is None:
            session.delete(tag)


def tags_list_for_book(session: Session, book_id: int | None) -> list[str]:
    """Return the sorted tag names for a given book, or an empty list."""
    if book_id is None:
        return []
    return list(
        session.exec(
            select(Tag.name)
            .join(BookTag, col(BookTag.tag_id) == col(Tag.id))
            .where(BookTag.book_id == book_id)
            .order_by(col(Tag.name).asc())
        ).all()
    )


def tags_text_for_book(session: Session, book_id: int) -> str | None:
    """Return a comma-separated tag string for a given book, or None."""
    names = tags_list_for_book(session, book_id)
    if not names:
        return None
    return ", ".join(names)


def load_tags_batch(session: Session, book_ids: list[int]) -> dict[int, str | None]:
    """Batch-load comma-separated tag strings for all given book IDs.

    Returns a dict mapping each book_id to its tags string (or None).
    """
    if not book_ids:
        return {}
    rows = session.exec(
        select(BookTag.book_id, Tag.name)
        .join(Tag, col(Tag.id) == col(BookTag.tag_id))
        .where(col(BookTag.book_id).in_(book_ids))
        .order_by(col(BookTag.book_id), col(Tag.name).asc())
    ).all()
    result: dict[int, list[str]] = {}
    for book_id, tag_name in rows:
        result.setdefault(book_id, []).append(tag_name)
    return {bid: ", ".join(names) if names else None for bid, names in result.items()}


def build_book_read(session: Session, book: Book) -> BookRead:
    """Build a BookRead response schema from a Book model, populating tags."""
    if book.id is not None:
        session.refresh(book)
    payload = book.model_dump()
    payload.pop("user_id", None)
    payload["tags"] = tags_text_for_book(session, book.id) if book.id is not None else None
    authors = authors_list_for_book(session, book.id)
    payload["authors"] = authors
    payload["author"] = join_authors(authors)
    from app.services.reading_sessions import session_counts

    counts = session_counts(session, [book.id or 0]).get(book.id or 0, {})
    payload["session_count"] = counts.get("session_count", 0)
    payload["read_count"] = counts.get("read_count", 0)
    return BookRead.model_validate(payload)


@dataclass
class BatchTagResult:
    """Outcome of a batch tag update."""
    matched_books: int = 0
    books_changed: int = 0
    links_added: int = 0
    links_removed: int = 0
    unchanged_books: int = 0
    created_tags: list[str] = field(default_factory=list)
    deleted_tags: list[str] = field(default_factory=list)


def list_tags_with_counts(
    session: Session, user_id: int, q: Optional[str] = None, limit: int = 500, offset: int = 0
) -> tuple[list[tuple[str, int]], int]:
    """Return (tag, count) rows for a user, optionally filtered by substring."""
    base = (
        select(Tag.name, func.count(col(BookTag.book_id)).label("cnt"))
        .join(BookTag, col(BookTag.tag_id) == col(Tag.id))
        .join(Book, col(Book.id) == col(BookTag.book_id))
        .where(Tag.user_id == user_id, Book.user_id == user_id)
        .group_by(col(Tag.id))
    )
    if q and q.strip():
        from app.services.search import _escape_like

        pattern = f"%{_escape_like(q.strip())}%"
        base = base.where(col(Tag.name).ilike(pattern, escape="\\"))
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    rows = session.exec(
        base.order_by(func.count(col(BookTag.book_id)).desc(), col(Tag.name).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [(name, int(count)) for name, count in rows], int(total)


def apply_batch_tags(
    session: Session, user_id: int, books: list[Book], add: list[str], remove: list[str]
) -> BatchTagResult:
    """Apply add/remove tag operations to the given books in one transaction."""
    result = BatchTagResult(matched_books=len(books))

    add_names = parse_tags(add)
    remove_names = parse_tags(remove)

    existing_tags: dict[str, Tag] = {}
    all_names = add_names + remove_names
    if all_names:
        tags = list(
            session.exec(
                select(Tag).where(Tag.user_id == user_id, col(Tag.name).in_(all_names))
            ).all()
        )
        existing_tags = {tag.name: tag for tag in tags}

    created_tags: list[str] = []
    add_tag_ids: dict[str, int] = {}
    for name in add_names:
        tag = existing_tags.get(name)
        if tag is None:
            tag = Tag(user_id=user_id, name=name, created_at=utcnow())
            session.add(tag)
            session.flush()
            existing_tags[name] = tag
            created_tags.append(name)
        if tag.id is not None:
            add_tag_ids[name] = tag.id

    remove_tag_ids: dict[str, int] = {}
    for name in remove_names:
        tag = existing_tags.get(name)
        if tag is not None and tag.id is not None:
            remove_tag_ids[name] = tag.id

    affected_tag_ids: set[int] = set(add_tag_ids.values()) | set(remove_tag_ids.values())

    existing_links: set[tuple[int, int]] = set()
    if affected_tag_ids and books:
        book_ids = [b.id for b in books if b.id is not None]
        rows = session.exec(
            select(BookTag.book_id, BookTag.tag_id).where(
                col(BookTag.book_id).in_(book_ids),
                col(BookTag.tag_id).in_(affected_tag_ids),
            )
        ).all()
        existing_links = {(bid, tid) for bid, tid in rows}

    target_links: set[tuple[int, int]] = set(existing_links)
    for book in books:
        if book.id is None:
            continue
        for tid in add_tag_ids.values():
            target_links.add((book.id, tid))
    for book in books:
        if book.id is None:
            continue
        for tid in remove_tag_ids.values():
            target_links.discard((book.id, tid))

    to_insert = target_links - existing_links
    to_delete = existing_links - target_links
    result.links_added = len(to_insert)
    result.links_removed = len(to_delete)

    # Apply as set-based statements: remove all affected existing links, then
    # insert the full target set. Rows that survive unchanged are deleted and
    # re-inserted, which keeps the final state correct and avoids per-pair SQL.
    if existing_links:
        session.exec(
            delete(BookTag).where(
                col(BookTag.book_id).in_({lnk[0] for lnk in existing_links}),
                col(BookTag.tag_id).in_({lnk[1] for lnk in existing_links}),
            )
        )
    if target_links:
        session.add_all([BookTag(book_id=bid, tag_id=tid) for bid, tid in target_links])

    deleted_tags: list[str] = []
    for name, tid in remove_tag_ids.items():
        remaining = session.exec(
            select(func.count()).select_from(BookTag).where(BookTag.tag_id == tid)
        ).one()
        if remaining == 0:
            tag = session.get(Tag, tid)
            if tag is not None:
                session.delete(tag)
                deleted_tags.append(name)
    result.deleted_tags = deleted_tags

    changed = 0
    for book in books:
        if book.id is None:
            continue
        before = {lnk for lnk in existing_links if lnk[0] == book.id}
        after = {lnk for lnk in target_links if lnk[0] == book.id}
        if before != after:
            changed += 1
    result.books_changed = changed
    result.unchanged_books = result.matched_books - changed
    result.created_tags = created_tags

    return result
