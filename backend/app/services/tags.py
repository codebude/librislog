from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import Book, BookTag, Tag
from app.schemas import BookRead


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []

    seen: set[str] = set()
    parsed: list[str] = []
    for piece in raw_tags.split(","):
        normalized = " ".join(piece.strip().split())
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        parsed.append(normalized)
    return parsed


def sync_book_tags(session: Session, user_id: int, book_id: int, raw_tags: str | None) -> None:
    parsed = parse_tags(raw_tags)

    existing_links = list(session.exec(select(BookTag).where(BookTag.book_id == book_id)).all())
    existing_tag_ids = {link.tag_id for link in existing_links}

    if not parsed:
        for link in existing_links:
            session.delete(link)
        return

    existing_tags = list(
        session.exec(select(Tag).where(Tag.user_id == user_id, Tag.name.in_(parsed))).all()
    )
    name_to_tag = {tag.name: tag for tag in existing_tags}

    for name in parsed:
        if name in name_to_tag:
            continue
        tag = Tag(user_id=user_id, name=name, created_at=_utcnow())
        session.add(tag)
        session.flush()
        name_to_tag[name] = tag

    target_tag_ids = {name_to_tag[name].id for name in parsed if name_to_tag[name].id is not None}

    for tag_id in target_tag_ids - existing_tag_ids:
        session.add(BookTag(book_id=book_id, tag_id=tag_id))

    for link in existing_links:
        if link.tag_id not in target_tag_ids:
            session.delete(link)


def cleanup_orphan_tags(session: Session, user_id: int) -> None:
    tags = list(session.exec(select(Tag).where(Tag.user_id == user_id)).all())
    for tag in tags:
        has_link = session.exec(select(BookTag).where(BookTag.tag_id == tag.id)).first()
        if has_link is None:
            session.delete(tag)


def tags_text_for_book(session: Session, book_id: int) -> str | None:
    names = list(
        session.exec(
            select(Tag.name)
            .join(BookTag, BookTag.tag_id == Tag.id)
            .where(BookTag.book_id == book_id)
            .order_by(Tag.name.asc())
        ).all()
    )
    if not names:
        return None
    return ", ".join(names)


def build_book_read(session: Session, book: Book) -> BookRead:
    payload = book.model_dump()
    payload.pop("user_id", None)
    payload["tags"] = tags_text_for_book(session, book.id) if book.id is not None else None
    return BookRead.model_validate(payload)
