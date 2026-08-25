"""Tests for the author parsing and relation helpers."""

from sqlmodel import Session, col, select

from app.models import Author, BookAuthor
from app.services.authors import (
    authors_list_for_book,
    join_authors,
    normalize_author_list,
    normalize_author_name,
    parse_authors,
    parse_legacy_author,
    resolve_authors_payload,
    split_author_string,
    sync_book_authors,
)


# ── normalization ──────────────────────────────────────────────────────────────

def test_normalize_author_name_collapses_whitespace() -> None:
    assert normalize_author_name("  Isaac   Asimov ") == "Isaac Asimov"


def test_normalize_author_name_empty_returns_none() -> None:
    assert normalize_author_name("   ") is None


def test_normalize_author_list_dedupes_case_insensitively() -> None:
    assert normalize_author_list(["Isaac Asimov", "isaac asimov", "Robert A. Heinlein"]) == [
        "Isaac Asimov",
        "Robert A. Heinlein",
    ]


def test_normalize_author_list_drops_blank_entries() -> None:
    assert normalize_author_list(["  ", "Asimov, Isaac"]) == ["Asimov, Isaac"]


# ── parsing ───────────────────────────────────────────────────────────────────

def test_parse_legacy_author_splits_on_commas() -> None:
    assert parse_legacy_author("Isaac Asimov, Robert A. Heinlein") == [
        "Isaac Asimov",
        "Robert A. Heinlein",
    ]


def test_parse_legacy_author_blank_pieces_skipped() -> None:
    assert parse_legacy_author("Isaac Asimov, , Robert A. Heinlein") == [
        "Isaac Asimov",
        "Robert A. Heinlein",
    ]


def test_parse_authors_string_is_single_author() -> None:
    """A file-import string without a separator becomes one author."""
    assert parse_authors("Asimov, Isaac") == ["Asimov, Isaac"]
    assert parse_authors("Frank Herbert") == ["Frank Herbert"]


def test_parse_authors_string_splits_on_semicolon() -> None:
    """Strings may encode several authors with `;` (CSV export round-trip)."""
    assert parse_authors("Frank Herbert; Brian Herbert") == ["Frank Herbert", "Brian Herbert"]


def test_parse_authors_list_is_one_per_entry() -> None:
    assert parse_authors(["Frank Herbert", "Brian Herbert"]) == [
        "Frank Herbert",
        "Brian Herbert",
    ]


def test_parse_authors_none_returns_empty() -> None:
    assert parse_authors(None) == []


# ── hybrid payload resolution ─────────────────────────────────────────────────

def test_resolve_authors_payload_authors_takes_precedence() -> None:
    assert resolve_authors_payload(author="A, B", authors=["C", "D"]) == ["C", "D"]


def test_resolve_authors_payload_empty_list_clears() -> None:
    assert resolve_authors_payload(author="A", authors=[]) == []


def test_resolve_authors_payload_falls_back_to_legacy() -> None:
    assert resolve_authors_payload(author="A, B") == ["A", "B"]


def test_resolve_authors_payload_none_means_not_provided() -> None:
    assert resolve_authors_payload() is None


# ── external splitter ─────────────────────────────────────────────────────────

def test_split_author_string_preserves_comma_names() -> None:
    assert split_author_string("Asimov, Isaac") == ["Asimov, Isaac"]


def test_split_author_string_splits_on_semicolon() -> None:
    assert split_author_string("Asimov, Isaac; Clarke, Arthur") == [
        "Asimov, Isaac",
        "Clarke, Arthur",
    ]


def test_split_author_string_splits_on_ampersand() -> None:
    assert split_author_string("Frank Herbert & Brian Herbert") == [
        "Frank Herbert",
        "Brian Herbert",
    ]


def test_split_author_string_splits_on_and() -> None:
    assert split_author_string("Terry Pratchett and Neil Gaiman") == [
        "Terry Pratchett",
        "Neil Gaiman",
    ]


def test_split_author_string_empty_returns_empty() -> None:
    assert split_author_string(None) == []
    assert split_author_string("   ") == []


# ── sync / query ──────────────────────────────────────────────────────────────

def test_sync_book_authors_creates_rows_and_links(session: Session) -> None:
    user_id = 1
    book_id = 1
    sync_book_authors(session, user_id, book_id, ["Isaac Asimov", "Frank Herbert"])
    session.commit()

    names = authors_list_for_book(session, book_id)
    assert names == ["Frank Herbert", "Isaac Asimov"]  # alphabetical

    authors = session.exec(select(Author).where(Author.user_id == user_id)).all()
    assert {a.name for a in authors} == {"Isaac Asimov", "Frank Herbert"}


def test_sync_book_authors_reuses_existing_author(session: Session) -> None:
    user_id = 1
    sync_book_authors(session, user_id, 1, ["Isaac Asimov"])
    session.commit()
    first_id = session.exec(
        select(Author.id).where(Author.user_id == user_id, Author.name == "Isaac Asimov")
    ).one()

    sync_book_authors(session, user_id, 2, ["Isaac Asimov", "Frank Herbert"])
    session.commit()

    second_id = session.exec(
        select(Author.id).where(Author.user_id == user_id, Author.name == "Isaac Asimov")
    ).one()
    assert first_id == second_id

    link_count = session.exec(
        select(col(BookAuthor.author_id)).where(BookAuthor.author_id == second_id)
    ).all()
    assert len(link_count) == 2


def test_sync_book_authors_removes_stale_links(session: Session) -> None:
    user_id = 1
    sync_book_authors(session, user_id, 1, ["Isaac Asimov", "Frank Herbert"])
    session.commit()

    sync_book_authors(session, user_id, 1, ["Frank Herbert"])
    session.commit()

    names = authors_list_for_book(session, 1)
    assert names == ["Frank Herbert"]


def test_sync_book_authors_empty_clears_links(session: Session) -> None:
    user_id = 1
    sync_book_authors(session, user_id, 1, ["Isaac Asimov"])
    session.commit()

    sync_book_authors(session, user_id, 1, [])
    session.commit()

    assert authors_list_for_book(session, 1) == []


# ── join ──────────────────────────────────────────────────────────────────────

def test_join_authors() -> None:
    assert join_authors(["A", "B"]) == "A, B"
    assert join_authors([]) is None
    assert join_authors(None) is None