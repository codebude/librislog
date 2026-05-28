"""Tests for the data hygiene endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Book, ReadingStatus, User
from app.routers import hygiene as hygiene_router


def _create_book(session: Session, user_id: int, **overrides: object) -> Book:
    """Create a test book with sensible defaults."""
    defaults: dict = {
        "title": "Test Book",
        "author": "Test Author",
        "isbn": None,
        "publisher": "Test Publisher",
        "published_year": 2020,
        "page_count": 200,
        "language": "EN",
        "subtitle": None,
        "blurb": "A test book.",
        "cover_url": None,
        "reading_status": ReadingStatus.want_to_read,
        "user_id": user_id,
    }
    defaults.update(overrides)
    book = Book(**defaults)
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


class TestListMissing:
    def test_missing_no_filters(self, client: TestClient, session: Session) -> None:
        """Returns all books with any missing attribute."""
        user_id = 1
        _create_book(session, user_id, title="Complete Book", isbn="1111111111", blurb="desc", subtitle="sub", cover_url="/covers/x.jpg", language="EN", publisher="Pub", published_year=2020, page_count=200)
        _create_book(session, user_id, title="Missing Author", author="", isbn="2222222222", blurb="desc", subtitle="sub", cover_url="/covers/x.jpg", language="EN", publisher="Pub", published_year=2020, page_count=200)
        _create_book(session, user_id, title="Missing ISBN", author="Author", blurb="desc", subtitle="sub", cover_url="/covers/x.jpg", language="EN", publisher="Pub", published_year=2020, page_count=200)

        resp = client.get("/api/hygiene/missing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        titles = {b["title"] for b in data["books"]}
        assert "Missing Author" in titles
        assert "Missing ISBN" in titles
        assert "Complete Book" not in titles

    def test_missing_single_attribute(self, client: TestClient, session: Session) -> None:
        """Filter by one attribute only."""
        user_id = 1
        _create_book(session, user_id, title="Missing Author", author="", isbn="1234567890")
        _create_book(session, user_id, title="Missing ISBN", isbn=None, author="Author A")
        _create_book(session, user_id, title="Has Both", author="Author B", isbn="123")

        resp = client.get("/api/hygiene/missing?attributes=isbn&match=all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["books"][0]["title"] == "Missing ISBN"

    def test_missing_match_any(self, client: TestClient, session: Session) -> None:
        """match=any returns books missing ANY of the requested attributes."""
        user_id = 1
        _create_book(session, user_id, title="Missing Author", author="")
        _create_book(session, user_id, title="Missing Both", author="", isbn=None)

        resp = client.get("/api/hygiene/missing?attributes=author,isbn&match=any")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_missing_pagination(self, client: TestClient, session: Session) -> None:
        """offset and limit work correctly."""
        user_id = 1
        for i in range(5):
            _create_book(session, user_id, title=f"Missing {i}", author="", isbn=None)

        resp = client.get("/api/hygiene/missing?limit=2&offset=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["books"]) == 2
        assert data["total"] == 5

    def test_missing_total_counts(self, client: TestClient, session: Session) -> None:
        """total_missing_per_attribute accurately counts missing values."""
        user_id = 1
        _create_book(session, user_id, title="B1", author="", isbn="111")
        _create_book(session, user_id, title="B2", author="", isbn="222")
        _create_book(session, user_id, title="B3", isbn=None, author="Author")

        resp = client.get("/api/hygiene/missing?attributes=author,isbn")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_missing_per_attribute"]["author"] == 2
        assert data["total_missing_per_attribute"]["isbn"] == 1

    def test_missing_respects_user_scoping(self, client: TestClient, session: Session, create_user_with_key) -> None:
        """User A's missing books don't include user B's books."""
        user2, key2 = create_user_with_key(email="other@example.com")
        _create_book(session, 1, title="User1 Missing Author", author="")
        _create_book(session, user2.id, title="User2 Missing Author", author="")

        resp = client.get("/api/hygiene/missing?attributes=author")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["books"][0]["title"] == "User1 Missing Author"

    def test_missing_empty_author_treated_as_missing(self, client: TestClient, session: Session) -> None:
        """Empty string author is treated as missing."""
        user_id = 1
        _create_book(session, user_id, title="Empty Author", author="")
        _create_book(session, user_id, title="None Author", author=None)

        resp = client.get("/api/hygiene/missing?attributes=author")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_missing_page_count_zero_treated_as_missing(self, client: TestClient, session: Session) -> None:
        """page_count of 0 is treated as missing."""
        user_id = 1
        _create_book(session, user_id, title="Zero Pages", page_count=0, author="Author")
        _create_book(session, user_id, title="Has Pages", page_count=300, author="Author")

        resp = client.get("/api/hygiene/missing?attributes=page_count")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["books"][0]["title"] == "Zero Pages"


class TestBatchUpdate:
    def test_batch_update_single_field(self, client: TestClient, session: Session) -> None:
        """Happy path: updates multiple books."""
        user_id = 1
        b1 = _create_book(session, user_id, title="B1", author="Old")
        b2 = _create_book(session, user_id, title="B2", author="Old")

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id, b2.id],
            "field": "author",
            "value": "New Author",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 2
        assert data["skipped"] == 0

        session.refresh(b1)
        session.refresh(b2)
        assert b1.author == "New Author"
        assert b2.author == "New Author"

    def test_batch_update_too_many_ids(self, client: TestClient, session: Session) -> None:
        """Rejects more than 500 book IDs."""
        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": list(range(501)),
            "field": "author",
            "value": "X",
        })
        assert resp.status_code == 422
        assert "500" in resp.json()["detail"]

    def test_batch_update_empty_ids(self, client: TestClient, session: Session) -> None:
        """Rejects empty book_ids."""
        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [],
            "field": "author",
            "value": "X",
        })
        assert resp.status_code == 422

    def test_batch_update_invalid_field_type(self, client: TestClient, session: Session) -> None:
        """Rejects invalid value for published_year."""
        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [1],
            "field": "published_year",
            "value": "not-a-year",
        })
        assert resp.status_code == 422

    def test_batch_update_partial_skipped(self, client: TestClient, session: Session) -> None:
        """Books that already have the target value are reported as skipped."""
        user_id = 1
        b1 = _create_book(session, user_id, title="B1", author="Already Set")
        b2 = _create_book(session, user_id, title="B2", author="Old")

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id, b2.id],
            "field": "author",
            "value": "Already Set",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 1
        assert data["skipped"] == 1
        assert b1.id in data["skipped_ids"]

    def test_batch_update_unauthorized_book(self, client: TestClient, session: Session, create_user_with_key) -> None:
        """Trying to update a book owned by another user returns 404."""
        user2, _ = create_user_with_key(email="other@example.com")
        b2 = _create_book(session, user2.id, title="Other's Book", author="Old")

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b2.id],
            "field": "author",
            "value": "X",
        })
        assert resp.status_code == 404

    def test_batch_update_clears_field(self, client: TestClient, session: Session) -> None:
        """Setting value to null clears the field."""
        user_id = 1
        b1 = _create_book(session, user_id, title="B1", isbn="12345")

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "isbn",
            "value": None,
        })
        assert resp.status_code == 200
        session.refresh(b1)
        assert b1.isbn is None

    def test_batch_update_invalid_language(self, client: TestClient, session: Session) -> None:
        """Invalid language code returns 422."""
        user_id = 1
        b1 = _create_book(session, user_id, title="B1", language=None)

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "language",
            "value": "ABC",
        })
        assert resp.status_code == 422

    def test_batch_update_valid_language(self, client: TestClient, session: Session) -> None:
        """Valid language code is normalized to uppercase."""
        user_id = 1
        b1 = _create_book(session, user_id, title="B1", language=None)

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "language",
            "value": "de",
        })
        assert resp.status_code == 200
        session.refresh(b1)
        assert b1.language == "DE"

    def test_batch_update_page_count(self, client: TestClient, session: Session) -> None:
        """Setting page_count to a value requires non-negative integer."""
        user_id = 1
        b1 = _create_book(session, user_id, title="B1", page_count=0)

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "page_count",
            "value": -1,
        })
        assert resp.status_code == 422

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "page_count",
            "value": 250,
        })
        assert resp.status_code == 200
        session.refresh(b1)
        assert b1.page_count == 250

    def test_batch_update_cover_url_valid(self, client: TestClient, session: Session, monkeypatch) -> None:
        """Valid external cover URL is downloaded and stored as local path."""
        async def _fake_download(url: str, covers_dir: str, http_client: object, user_id: int) -> str:
            return "1__cover.jpg"
        monkeypatch.setattr(hygiene_router, "import_cover_from_url", _fake_download)

        b1 = _create_book(session, 1, title="B1", cover_url=None)

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "cover_url",
            "value": "https://example.com/cover.jpg",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 1
        assert data["skipped"] == 0
        session.refresh(b1)
        assert b1.cover_url == "/api/covers/1__cover.jpg"

    def test_batch_update_cover_url_invalid(self, client: TestClient, session: Session) -> None:
        """Non-external cover URL is rejected."""
        b1 = _create_book(session, 1, title="B1", cover_url=None)

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "cover_url",
            "value": "data:image/png;base64,iVBORw0KGgo=",
        })
        assert resp.status_code == 422

    def test_batch_update_cover_url_download_fails(self, client: TestClient, session: Session, monkeypatch) -> None:
        """When download fails, cover_url is set to None."""
        async def _fake_download(url: str, covers_dir: str, http_client: object, user_id: int) -> None:
            return None
        monkeypatch.setattr(hygiene_router, "import_cover_from_url", _fake_download)

        b1 = _create_book(session, 1, title="B1", cover_url=None)

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "cover_url",
            "value": "https://example.com/fail.jpg",
        })
        assert resp.status_code == 200
        session.refresh(b1)
        assert b1.cover_url is None

    def test_batch_update_cover_url_none(self, client: TestClient, session: Session) -> None:
        """Setting cover_url to None clears it."""
        b1 = _create_book(session, 1, title="B1", cover_url="/api/covers/old.jpg")

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "cover_url",
            "value": None,
        })
        assert resp.status_code == 200
        session.refresh(b1)
        assert b1.cover_url is None

    def test_batch_update_cover_url_already_set(self, client: TestClient, session: Session, monkeypatch) -> None:
        """Book already has the target cover path — skipped after download."""
        async def _fake_download(url: str, covers_dir: str, http_client: object, user_id: int) -> str:
            return "1__same.jpg"
        monkeypatch.setattr(hygiene_router, "import_cover_from_url", _fake_download)

        b1 = _create_book(session, 1, title="B1", cover_url="/api/covers/1__same.jpg")

        resp = client.post("/api/hygiene/batch-update", json={
            "book_ids": [b1.id],
            "field": "cover_url",
            "value": "https://example.com/same.jpg",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 0
        assert data["skipped"] == 1
        assert b1.id in data["skipped_ids"]
