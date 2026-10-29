"""Tests for tag listing and batch tag endpoints."""

import pytest
from sqlmodel import Session, col, select

from app.models import Book, BookTag, Tag, User
from app.services.tags import apply_batch_tags, list_tags_with_counts, parse_tags


def _make_book(session: Session, user_id: int, title: str = "Book", tags: str | None = None) -> Book:
    book = Book(title=title, user_id=user_id, reading_status="want_to_read")
    session.add(book)
    session.commit()
    session.refresh(book)
    if tags and book.id is not None:
        from app.services.tags import sync_book_tags

        sync_book_tags(session, user_id, book.id, tags)
        session.commit()
        session.refresh(book)
    return book


class TestParseTags:
    def test_basic(self):
        assert parse_tags("a, b ,a") == ["a", "b"]

    def test_list_mode(self):
        assert parse_tags(["x", " y ", "x"]) == ["x", "y"]

    def test_empty(self):
        assert parse_tags(None) == []
        assert parse_tags("") == []


class TestListTagsWithCounts:
    def test_counts_and_ordering(self, session: Session):
        user = User(firstname="U", lastname="X", email="u@x.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        b1 = _make_book(session, user.id, "B1", "sci-fi, cars")
        b2 = _make_book(session, user.id, "B2", "sci-fi")
        rows, total = list_tags_with_counts(session, user.id)
        assert total == 2
        assert rows[0] == ("sci-fi", 2)
        assert rows[1] == ("cars", 1)

    def test_filter_q(self, session: Session):
        user = User(firstname="U", lastname="X", email="u2@x.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        _make_book(session, user.id, "B1", "alpha, beta")
        rows, total = list_tags_with_counts(session, user.id, q="alp")
        assert total == 1
        assert rows == [("alpha", 1)]


class TestApplyBatchTags:
    def test_add_and_remove(self, session: Session):
        user = User(firstname="U", lastname="X", email="u3@x.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        b1 = _make_book(session, user.id, "B1", "cars")
        b2 = _make_book(session, user.id, "B2")
        assert b1.id is not None and b2.id is not None
        result = apply_batch_tags(session, user.id, [b1, b2], ["sci-fi"], ["cars"])
        session.commit()
        assert result.books_changed == 2
        assert result.links_added == 2  # both get sci-fi (b1 already? no, new)
        assert result.links_removed == 1  # cars removed from b1
        assert "sci-fi" in result.created_tags
        assert "cars" in result.deleted_tags
        # verify
        tags_b1 = session.exec(
            select(Tag.name).join(BookTag, col(BookTag.tag_id) == col(Tag.id)).where(BookTag.book_id == b1.id)
        ).all()
        assert "sci-fi" in tags_b1 and "cars" not in tags_b1

    def test_idempotent(self, session: Session):
        user = User(firstname="U", lastname="X", email="u4@x.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        b1 = _make_book(session, user.id, "B1", "sci-fi")
        assert b1.id is not None
        result = apply_batch_tags(session, user.id, [b1], ["sci-fi"], [])
        session.commit()
        assert result.links_added == 0
        assert result.books_changed == 0


class TestTagEndpoints:
    def test_list_tags(self, client):
        # create a book with a tag via direct API? use books create
        client.post("/api/books", json={"title": "B", "author": "A", "page_count": 10, "tags": "hello"})
        r = client.get("/api/tags")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert any(t["name"] == "hello" for t in data["tags"])

    def test_batch_add_remove(self, client):
        r1 = client.post("/api/books", json={"title": "B1", "author": "A", "page_count": 10, "tags": "cars"})
        r2 = client.post("/api/books", json={"title": "B2", "author": "A", "page_count": 10})
        id1 = r1.json()["id"]
        id2 = r2.json()["id"]
        r = client.post("/api/tags/batch", json={"book_ids": [id1, id2], "add": ["sci-fi"], "remove": ["cars"]})
        assert r.status_code == 200
        data = r.json()
        assert data["books_changed"] == 2
        # verify tags
        b1 = client.get(f"/api/books/{id1}").json()
        assert "sci-fi" in (b1["tags"] or "")
        assert "cars" not in (b1["tags"] or "")

    def test_unknown_book_404(self, client):
        r = client.post("/api/tags/batch", json={"book_ids": [999999], "add": ["x"]})
        assert r.status_code == 404

    def test_empty_ids_422(self, client):
        r = client.post("/api/tags/batch", json={"book_ids": [], "add": ["x"]})
        assert r.status_code == 422

    def test_too_many_422(self, client):
        r = client.post("/api/tags/batch", json={"book_ids": list(range(1, 502)), "add": ["x"]})
        assert r.status_code == 422

    def test_overlap_422(self, client):
        r = client.post("/api/books", json={"title": "O", "author": "A", "page_count": 10})
        bid = r.json()["id"]
        r2 = client.post("/api/tags/batch", json={"book_ids": [bid], "add": ["X"], "remove": ["x"]})
        assert r2.status_code == 422

    def test_no_tags_422(self, client):
        r = client.post("/api/tags/batch", json={"book_ids": [1], "add": [], "remove": []})
        assert r.status_code == 422

    def test_ids_endpoint_filters(self, client):
        client.post("/api/books", json={"title": "Tagged", "author": "A", "page_count": 10, "tags": "special"})
        client.post("/api/books", json={"title": "Untagged", "author": "A", "page_count": 10})
        r = client.get("/api/books/ids?tag=special")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        # exclude
        r2 = client.get("/api/books/ids?exclude_tag=special")
        assert r2.status_code == 200

    def test_books_list_tag_filter(self, client):
        r = client.get("/api/books?tag=special")
        assert r.status_code == 200
        assert "books" in r.json()


class TestTagOwnership:
    def test_foreign_book_not_accessible(self, client, create_user_with_key, session):
        other, other_key = create_user_with_key(email="other@x.com")
        # create a book as other user directly
        other_book = Book(title="OtherBook", user_id=other.id, reading_status="want_to_read")
        session.add(other_book)
        session.commit()
        session.refresh(other_book)
        assert other_book.id is not None
        r = client.post("/api/tags/batch", json={"book_ids": [other_book.id], "add": ["x"]})
        assert r.status_code == 404


class TestLegacyTagServices:
    def test_parse_tags_whitespace_and_dedupe(self):
        assert parse_tags("  fantasy  ,  sci   fi  , fantasy") == ["fantasy", "sci fi"]

    def test_parse_tags_skips_empty(self):
        assert parse_tags("a,, ,b") == ["a", "b"]

    def test_parse_tags_case_insensitive_dedupe(self):
        assert parse_tags("Foo, foo, FOO") == ["Foo"]

    def test_sync_book_tags_clear_on_none(self, session: Session):
        user = User(firstname="U", lastname="X", email="legacy1@x.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        book = _make_book(session, user.id, "B", "a, b")
        assert book.id is not None
        from app.services.tags import sync_book_tags

        sync_book_tags(session, user.id, book.id, None)
        session.commit()
        tags = session.exec(
            select(Tag.name).join(BookTag, col(BookTag.tag_id) == col(Tag.id)).where(BookTag.book_id == book.id)
        ).all()
        assert tags == []

    def test_sync_book_tags_reuses_existing(self, session: Session):
        user = User(firstname="U", lastname="X", email="legacy2@x.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        b1 = _make_book(session, user.id, "B1", "shared")
        b2 = _make_book(session, user.id, "B2")
        assert b1.id is not None and b2.id is not None
        from app.services.tags import sync_book_tags

        sync_book_tags(session, user.id, b2.id, "shared")
        session.commit()
        tag_rows = session.exec(select(Tag).where(Tag.user_id == user.id, Tag.name == "shared")).all()
        assert len(tag_rows) == 1

    def test_cleanup_orphan_tags_removes_unused(self, session: Session):
        user = User(firstname="U", lastname="X", email="legacy3@x.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        book = _make_book(session, user.id, "B", "orphan")
        assert book.id is not None
        from app.services.tags import sync_book_tags

        sync_book_tags(session, user.id, book.id, None)
        session.commit()
        from app.services.tags import cleanup_orphan_tags

        cleanup_orphan_tags(session, user.id)
        session.commit()
        remaining = session.exec(select(Tag).where(Tag.user_id == user.id, Tag.name == "orphan")).all()
        assert remaining == []

    def test_load_tags_batch(self, session: Session):
        user = User(firstname="U", lastname="X", email="legacy4@x.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        b1 = _make_book(session, user.id, "B1", "t1, t2")
        b2 = _make_book(session, user.id, "B2")
        assert b1.id is not None and b2.id is not None
        from app.services.tags import load_tags_batch

        result = load_tags_batch(session, [b1.id, b2.id])
        assert result.get(b1.id) == "t1, t2"
        assert result.get(b2.id) is None

    def test_tags_text_for_book(self, session: Session):
        user = User(firstname="U", lastname="X", email="legacy5@x.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        book = _make_book(session, user.id, "B", "zeta, alpha")
        assert book.id is not None
        from app.services.tags import tags_text_for_book

        text = tags_text_for_book(session, book.id)
        assert text == "alpha, zeta"