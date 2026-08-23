"""Tests for tag parsing and management."""

from sqlmodel import Session, select

from app.models import Book, BookTag, Tag
from app.services.tags import (
    cleanup_orphan_tags,
    parse_tags,
    sync_book_tags,
    tags_text_for_book,
)


def test_parse_tags_empty_and_none() -> None:
    """None and empty strings should produce an empty list."""
    assert parse_tags(None) == []
    assert parse_tags("") == []
    assert parse_tags("   ") == []


def test_parse_tags_single() -> None:
    """A single tag should be returned as a one-element list."""
    assert parse_tags("fantasy") == ["fantasy"]


def test_parse_tags_multiple() -> None:
    """Comma-separated tags should be split into a list."""
    assert parse_tags("fantasy, sci-fi") == ["fantasy", "sci-fi"]


def test_parse_tags_strips_whitespace_and_collapses_spaces() -> None:
    """Leading/trailing whitespace should be stripped; internal spaces preserved."""
    assert parse_tags("  fantasy  ,  sci   fi  ") == ["fantasy", "sci fi"]


def test_parse_tags_skips_empty_pieces() -> None:
    """Empty elements between consecutive commas should be skipped."""
    assert parse_tags("fantasy, , sci-fi") == ["fantasy", "sci-fi"]


def test_parse_tags_deduplicates_case_insensitive() -> None:
    """Duplicate tags differing only in case should keep the first occurrence."""
    assert parse_tags("Fantasy, fantasy, FANTASY") == ["Fantasy"]


def test_sync_book_tags_adds_new_tags(session: Session) -> None:
    """New tags should be created and linked to the book."""
    user_id = 1
    book = Book(title="Test", user_id=user_id)
    session.add(book)
    session.flush()
    assert book.id is not None

    sync_book_tags(session, user_id, book.id, "fantasy, sci-fi")

    tags = session.exec(select(Tag).where(Tag.user_id == user_id)).all()
    assert len(tags) == 2
    tag_names = {t.name for t in tags}
    assert tag_names == {"fantasy", "sci-fi"}

    links = session.exec(select(BookTag).where(BookTag.book_id == book.id)).all()
    assert len(links) == 2


def test_sync_book_tags_removes_removed_tags(session: Session) -> None:
    """Tags removed from the string should be unlinked."""
    user_id = 1
    book = Book(title="Test", user_id=user_id)
    session.add(book)
    session.flush()
    assert book.id is not None

    sync_book_tags(session, user_id, book.id, "fantasy, sci-fi")
    sync_book_tags(session, user_id, book.id, "fantasy")

    links = session.exec(select(BookTag).where(BookTag.book_id == book.id)).all()
    assert len(links) == 1
    tag_names = [
        session.exec(select(Tag.name).where(Tag.id == link.tag_id)).one()
        for link in links
    ]
    assert tag_names == ["fantasy"]


def test_sync_book_tags_clears_all_when_empty(session: Session) -> None:
    """Passing None should clear all tag links."""
    user_id = 1
    book = Book(title="Test", user_id=user_id)
    session.add(book)
    session.flush()
    assert book.id is not None

    sync_book_tags(session, user_id, book.id, "fantasy, sci-fi")
    sync_book_tags(session, user_id, book.id, None)

    links = session.exec(select(BookTag).where(BookTag.book_id == book.id)).all()
    assert len(links) == 0


def test_sync_book_tags_reuses_existing_tags(session: Session) -> None:
    """Existing tags should be reused rather than duplicated."""
    user_id = 1
    existing = Tag(user_id=user_id, name="fantasy")
    session.add(existing)
    session.flush()

    book = Book(title="Test", user_id=user_id)
    session.add(book)
    session.flush()
    assert book.id is not None

    sync_book_tags(session, user_id, book.id, "fantasy")

    all_tags = session.exec(select(Tag).where(Tag.user_id == user_id)).all()
    assert len(all_tags) == 1
    assert all_tags[0].id == existing.id


def test_cleanup_orphan_tags_removes_unused(session: Session) -> None:
    """Tags not linked to any book should be deleted."""
    user_id = 1
    tag = Tag(user_id=user_id, name="orphan")
    session.add(tag)
    session.flush()

    cleanup_orphan_tags(session, user_id)

    remaining = session.exec(select(Tag).where(Tag.user_id == user_id)).all()
    assert len(remaining) == 0


def test_cleanup_orphan_tags_keeps_linked(session: Session) -> None:
    """Tags linked to at least one book should be preserved."""
    user_id = 1
    tag = Tag(user_id=user_id, name="used")
    session.add(tag)
    book = Book(title="Test", user_id=user_id)
    session.add(book)
    session.flush()
    assert book.id is not None
    assert tag.id is not None
    session.add(BookTag(book_id=book.id, tag_id=tag.id))
    session.flush()

    cleanup_orphan_tags(session, user_id)

    remaining = session.exec(select(Tag).where(Tag.user_id == user_id)).all()
    assert len(remaining) == 1


def test_tags_text_for_book_returns_none_for_no_tags(session: Session) -> None:
    """A book with no tags should return None."""
    user_id = 1
    book = Book(title="Test", user_id=user_id)
    session.add(book)
    session.flush()
    assert book.id is not None

    assert tags_text_for_book(session, book.id) is None


def test_tags_text_for_book_returns_comma_separated(session: Session) -> None:
    """Multiple tags should be returned as a comma-separated string, sorted."""
    user_id = 1
    book = Book(title="Test", user_id=user_id)
    session.add(book)
    session.flush()
    assert book.id is not None
    for name in ("fantasy", "sci-fi"):
        tag = Tag(user_id=user_id, name=name)
        session.add(tag)
        session.flush()
        assert tag.id is not None
        session.add(BookTag(book_id=book.id, tag_id=tag.id))
    session.flush()

    result = tags_text_for_book(session, book.id)
    assert result == "fantasy, sci-fi"
