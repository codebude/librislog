from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Self

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError
from sqlmodel import Session

from app.config import settings
from app.models import Book, User
import app.routers.books as books_router


# ── helpers ──────────────────────────────────────────────────────────────────

def _create_book(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    """Create a book via POST /api/books and return the response JSON."""
    payload: dict[str, Any] = {"title": "Test Book", "author": "Test Author", "page_count": 100, **kwargs}
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ── create ────────────────────────────────────────────────────────────────────

def test_create_book_returns_201(client: TestClient) -> None:
    resp = client.post("/api/books", json={"title": "Dune", "author": "Frank Herbert", "page_count": 412})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Dune"
    assert data["id"] is not None
    assert data["reading_status"] == "want_to_read"


def test_create_book_with_all_fields(client: TestClient) -> None:
    payload = {
        "title": "Dune",
        "author": "Frank Herbert",
        "isbn": "9780441013593",
        "publisher": "Ace Books",
        "published_year": 1965,
        "page_count": 412,
        "language": "en",
        "tags": "Science Fiction",
        "notes": "A classic",
        "rating": 5,
        "reading_status": "read",
        "date_started": "2024-01-01",
        "date_finished": "2024-01-15",
    }
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["author"] == "Frank Herbert"
    assert data["isbn"] == "9780441013593"
    assert data["language"] == "EN"
    assert data["rating"] == 5
    assert data["reading_status"] == "read"


def test_create_book_missing_title_returns_422(client: TestClient) -> None:
    resp = client.post("/api/books", json={"author": "Frank Herbert", "page_count": 400})
    assert resp.status_code == 422


def test_create_book_invalid_rating_returns_422(client: TestClient) -> None:
    resp = client.post("/api/books", json={"title": "Dune", "author": "Frank Herbert", "page_count": 412, "rating": 6})
    assert resp.status_code == 422


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_books_empty(client: TestClient) -> None:
    resp = client.get("/api/books")
    assert resp.status_code == 200
    assert resp.json() == {"books": [], "total": 0}


def test_list_books_returns_all(client: TestClient) -> None:
    _create_book(client, title="Book A")
    _create_book(client, title="Book B")
    resp = client.get("/api/books")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["books"]) == 2


def test_list_books_filter_by_status(client: TestClient) -> None:
    _create_book(client, title="Want", reading_status="want_to_read")
    _create_book(client, title="Reading", reading_status="currently_reading")
    _create_book(client, title="Done", reading_status="read")
    _create_book(client, title="DNF", reading_status="did_not_finish")

    resp = client.get("/api/books?status=currently_reading")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["books"][0]["title"] == "Reading"


def test_list_books_search_by_title(client: TestClient) -> None:
    _create_book(client, title="Dune")
    _create_book(client, title="Foundation")
    resp = client.get("/api/books?q=dune")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["books"][0]["title"] == "Dune"


def test_list_books_search_by_author(client: TestClient) -> None:
    _create_book(client, title="Dune", author="Frank Herbert")
    _create_book(client, title="Foundation", author="Isaac Asimov")
    resp = client.get("/api/books?q=asimov")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["books"][0]["title"] == "Foundation"


def test_list_books_sort_by_rating(client: TestClient) -> None:
    _create_book(client, title="Low", rating=2)
    _create_book(client, title="High", rating=5)
    resp = client.get("/api/books?sort=rating&order=desc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["books"][0]["title"] == "High"
    assert body["books"][1]["title"] == "Low"


def test_list_books_sort_by_date_added_asc(client: TestClient) -> None:
    _create_book(client, title="First")
    _create_book(client, title="Second")
    resp = client.get("/api/books?sort=date_added&order=asc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["books"][0]["title"] == "First"


def test_list_books_smart_sort_currently_reading_by_date_started(client: TestClient) -> None:
    _create_book(
        client,
        title="Older",
        reading_status="currently_reading",
        date_started="2024-01-01",
    )
    _create_book(
        client,
        title="Newer",
        reading_status="currently_reading",
        date_started="2024-02-01",
    )
    _create_book(client, title="No Start", reading_status="currently_reading")

    resp = client.get("/api/books?status=currently_reading")
    assert resp.status_code == 200
    body = resp.json()
    assert [item["title"] for item in body["books"]] == ["Newer", "Older", "No Start"]


def test_list_books_smart_sort_read_by_date_finished(client: TestClient) -> None:
    _create_book(client, title="Older", reading_status="read", date_finished="2024-01-01")
    _create_book(client, title="Newer", reading_status="read", date_finished="2024-02-01")
    _create_book(client, title="No Finish", reading_status="read")

    resp = client.get("/api/books?status=read")
    assert resp.status_code == 200
    body = resp.json()
    assert [item["title"] for item in body["books"]] == ["Newer", "Older", "No Finish"]


def test_list_books_manual_sort_still_available_with_smart_sort_off(client: TestClient) -> None:
    _create_book(client, title="Low", reading_status="currently_reading", rating=1)
    _create_book(client, title="High", reading_status="currently_reading", rating=5)

    resp = client.get("/api/books?status=currently_reading&smart_sort=false&sort=rating&order=desc")
    assert resp.status_code == 200
    body = resp.json()
    assert [item["title"] for item in body["books"]] == ["High", "Low"]


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_book_returns_book(client: TestClient) -> None:
    book = _create_book(client, title="Dune")
    resp = client.get(f"/api/books/{book['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Dune"


def test_get_book_not_found_returns_404(client: TestClient) -> None:
    resp = client.get("/api/books/9999")
    assert resp.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────

def test_update_book_status(client: TestClient) -> None:
    book = _create_book(client)
    resp = client.patch(f"/api/books/{book['id']}", json={"reading_status": "currently_reading"})
    assert resp.status_code == 200
    assert resp.json()["reading_status"] == "currently_reading"


def test_update_book_language(client: TestClient) -> None:
    book = _create_book(client)
    resp = client.patch(f"/api/books/{book['id']}", json={"language": "de"})
    assert resp.status_code == 200
    assert resp.json()["language"] == "DE"


def test_create_book_invalid_language_returns_422(client: TestClient) -> None:
    resp = client.post("/api/books", json={"title": "Dune", "author": "Frank Herbert", "page_count": 412, "language": "english"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Language must be a 2-letter ISO code (for example: EN, DE, FR)."


def test_create_book_with_did_not_finish_status(client: TestClient) -> None:
    resp = client.post("/api/books", json={"title": "DNF Book", "author": "Test Author", "page_count": 100, "reading_status": "did_not_finish"})
    assert resp.status_code == 201
    assert resp.json()["reading_status"] == "did_not_finish"


def test_list_books_filter_by_did_not_finish_status(client: TestClient) -> None:
    _create_book(client, title="Read", reading_status="read")
    _create_book(client, title="DNF", reading_status="did_not_finish")

    resp = client.get("/api/books?status=did_not_finish")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["books"][0]["title"] == "DNF"


def test_list_books_supports_limit_and_offset(client: TestClient) -> None:
    _create_book(client, title="First")
    _create_book(client, title="Second")
    _create_book(client, title="Third")

    first_page = client.get("/api/books?sort=title&order=asc&limit=2&offset=0")
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert [item["title"] for item in first_body["books"]] == ["First", "Second"]

    second_page = client.get("/api/books?sort=title&order=asc&limit=2&offset=2")
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert [item["title"] for item in second_body["books"]] == ["Third"]


async def _fake_download_cover(url: str, covers_dir: str | Path, http_client: Any, user_id: int) -> str:
    filename = "test_cover.jpg"
    (Path(covers_dir) / filename).write_bytes(b"img")
    return filename


def test_list_books_filter_has_cover_excludes_empty_string(client: TestClient, session: Session, monkeypatch: MonkeyPatch) -> None:
    """A book with cover_url='' (bypassing validator) is treated as missing a cover."""
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover)
    book = _create_book(client, title="Empty Cover")

    # Bypass the model validator by setting cover_url to "" via raw SQL
    from sqlalchemy import update as sa_update
    session.exec(sa_update(Book).where(Book.id == book["id"]).values(cover_url=""))
    session.commit()

    _create_book(client, title="Real Cover", cover_url="http://example.com/real.jpg")

    resp = client.get("/api/books?has_cover=true")
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()["books"]]
    assert "Real Cover" in titles
    assert "Empty Cover" not in titles


def test_list_books_filter_has_cover_false(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover)
    _create_book(client, title="No Cover", cover_url=None)
    _create_book(client, title="With Cover", cover_url="http://example.com/cover.jpg")

    resp = client.get("/api/books?has_cover=false")
    assert resp.status_code == 200
    data = resp.json()
    titles = [b["title"] for b in data["books"]]
    assert "No Cover" in titles
    assert "With Cover" not in titles


def test_list_books_filter_has_cover_true(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover)
    _create_book(client, title="No Cover", cover_url=None)
    _create_book(client, title="With Cover", cover_url="http://example.com/cover.jpg")

    resp = client.get("/api/books?has_cover=true")
    assert resp.status_code == 200
    data = resp.json()
    titles = [b["title"] for b in data["books"]]
    assert "With Cover" in titles
    assert "No Cover" not in titles


def test_list_books_without_has_cover_returns_all(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover)
    _create_book(client, title="Book A", cover_url=None)
    _create_book(client, title="Book B", cover_url="http://example.com/cover.jpg")

    resp = client.get("/api/books")
    assert resp.status_code == 200
    assert len(resp.json()["books"]) == 2


def test_update_book_to_did_not_finish_status(client: TestClient) -> None:
    book = _create_book(client, title="Update To DNF")

    resp = client.patch(f"/api/books/{book['id']}", json={"reading_status": "did_not_finish"})
    assert resp.status_code == 200
    assert resp.json()["reading_status"] == "did_not_finish"


def test_update_book_sets_date_started_when_moving_to_currently_reading(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(client, title="Date Start")
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.patch(f"/api/books/{book['id']}", json={"reading_status": "currently_reading"})
    assert resp.status_code == 200
    assert resp.json()["date_started"].startswith("2026-05-11T10:30:00")


def test_update_book_sets_date_finished_when_moving_to_read(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(client, title="Date Finished")
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.patch(f"/api/books/{book['id']}", json={"reading_status": "read"})
    assert resp.status_code == 200
    assert resp.json()["date_finished"].startswith("2026-05-11T10:30:00")


def test_update_book_does_not_override_existing_date_started(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(
        client,
        title="Keep Date",
        reading_status="want_to_read",
        date_started="2020-01-01",
    )
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.patch(f"/api/books/{book['id']}", json={"reading_status": "currently_reading"})
    assert resp.status_code == 200
    assert resp.json()["date_started"].startswith("2020-01-01T00:00:00")


def test_transition_status_returns_conflict_when_date_started_exists(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(client, title="Conflict", date_started="2024-01-10")
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "currently_reading"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "want_to_read"
    assert data["date_conflict"] == {
        "field": "date_started",
        "existing_date": "2024-01-10T00:00:00Z",
        "suggested_date": "2026-05-11T10:30:00Z",
    }


def test_transition_status_can_keep_existing_date_started(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(client, title="Keep", date_started="2024-01-10")
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={
            "new_status": "currently_reading",
            "force_date_started": "2024-01-10T00:00:00Z",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "currently_reading"
    assert data["book"]["date_started"] == "2024-01-10T00:00:00Z"
    assert data["date_conflict"] is None


def test_transition_status_sets_date_finished_for_did_not_finish(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(client, title="DNF Date")
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "did_not_finish"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "did_not_finish"
    assert data["book"]["date_finished"].startswith("2026-05-11T10:30:00")


def test_transition_status_returns_conflict_when_date_finished_exists(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(
        client,
        title="Finished Conflict",
        reading_status="currently_reading",
        date_finished="2024-02-02",
    )
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "read"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "currently_reading"
    assert data["date_conflict"] == {
        "field": "date_finished",
        "existing_date": "2024-02-02T00:00:00Z",
        "suggested_date": "2026-05-11T10:30:00Z",
    }


def test_transition_status_can_override_existing_date_finished(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(
        client,
        title="Finished Override",
        reading_status="currently_reading",
        date_finished="2024-02-02",
    )
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={
            "new_status": "read",
            "force_date_finished": "2026-05-01T08:15:00Z",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "read"
    assert data["book"]["date_finished"].startswith("2026-05-01T08:15:00")
    assert data["date_conflict"] is None


def test_transition_status_conflict_when_started_after_finished(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(
        client,
        title="StartedAfterFinished Conflict",
        reading_status="read",
        date_started=None,
        date_finished="2024-02-02",
    )
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "currently_reading"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "read"
    assert data["date_conflict"] == {
        "field": "started_after_finished",
        "existing_date": "2024-02-02T00:00:00Z",
        "suggested_date": "2026-05-11T10:30:00Z",
    }


def test_transition_status_option_a_clear_finished_and_start(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(
        client,
        title="OptionA",
        reading_status="read",
        date_started=None,
        date_finished="2024-02-02",
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={
            "new_status": "currently_reading",
            "force_date_started": "2026-05-11T10:30:00Z",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "currently_reading"
    assert data["book"]["date_started"] == "2026-05-11T10:30:00Z"
    assert data["book"]["date_finished"] is None
    assert data["date_conflict"] is None


def test_transition_status_option_b_skip_auto_date_started(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(
        client,
        title="OptionB",
        reading_status="read",
        date_started=None,
        date_finished="2024-02-02",
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={
            "new_status": "currently_reading",
            "skip_auto_date_started": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "currently_reading"
    assert data["book"]["date_started"] is None
    assert data["book"]["date_finished"] == "2024-02-02T00:00:00Z"
    assert data["date_conflict"] is None


# ── chained conflict: date_started conflict → started_after_finished conflict ──


def test_transition_status_chained_detects_started_after_finished(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """Book has both dates set; first call gets date_started conflict,
    second with force_date_started gets started_after_finished conflict."""
    book = _create_book(
        client,
        title="Chained conflict",
        reading_status="read",
        date_started="2024-01-01",
        date_finished="2024-02-02",
    )
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    # Step 1: trigger date_started conflict
    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "currently_reading"},
    )
    assert resp.status_code == 200
    assert resp.json()["date_conflict"]["field"] == "date_started"

    # Step 2: resolve date_started with force_date_started → should get started_after_finished
    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={
            "new_status": "currently_reading",
            "force_date_started": "2026-05-11T10:30:00Z",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "read"
    assert data["date_conflict"] == {
        "field": "started_after_finished",
        "existing_date": "2024-02-02T00:00:00Z",
        "suggested_date": "2026-05-11T10:30:00Z",
    }


def test_transition_status_chained_option_a_clear_finished(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """Resolve started_after_finished with force_date_started + skip → clears date_finished."""
    book = _create_book(
        client,
        title="Chained A",
        reading_status="read",
        date_started="2024-01-01",
        date_finished="2024-02-02",
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={
            "new_status": "currently_reading",
            "force_date_started": "2026-05-11T10:30:00Z",
            "skip_auto_date_started": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "currently_reading"
    assert data["book"]["date_started"] == "2026-05-11T10:30:00Z"
    assert data["book"]["date_finished"] is None
    assert data["date_conflict"] is None


def test_transition_status_chained_option_b_keep_finished(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """Resolve started_after_finished with skip_auto_date_started → clears date_started, keeps date_finished."""
    book = _create_book(
        client,
        title="Chained B",
        reading_status="read",
        date_started="2024-01-01",
        date_finished="2024-02-02",
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={
            "new_status": "currently_reading",
            "skip_auto_date_started": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "currently_reading"
    assert data["book"]["date_started"] is None
    assert data["book"]["date_finished"] == "2024-02-02T00:00:00Z"
    assert data["date_conflict"] is None


def test_update_book_rating(client: TestClient) -> None:
    book = _create_book(client)
    resp = client.patch(f"/api/books/{book['id']}", json={"rating": 4})
    assert resp.status_code == 200
    assert resp.json()["rating"] == 4


def test_update_book_partial_leaves_other_fields(client: TestClient) -> None:
    book = _create_book(client, title="Dune", author="Frank Herbert")
    resp = client.patch(f"/api/books/{book['id']}", json={"rating": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["author"] == "Frank Herbert"
    assert data["rating"] == 3


def test_update_book_not_found_returns_404(client: TestClient) -> None:
    resp = client.patch("/api/books/9999", json={"rating": 3})
    assert resp.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_book(client: TestClient) -> None:
    book = _create_book(client)
    resp = client.delete(f"/api/books/{book['id']}")
    assert resp.status_code == 204
    # Confirm gone
    assert client.get(f"/api/books/{book['id']}").status_code == 404


def test_delete_book_removes_local_cover_file(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    filename = "abc123.jpg"
    cover_path = tmp_path / filename
    cover_path.write_bytes(b"image-bytes")

    book = _create_book(client, title="With Cover", cover_url=f"/api/covers/{filename}")

    resp = client.delete(f"/api/books/{book['id']}")
    assert resp.status_code == 204
    assert not cover_path.exists()


def test_delete_book_keeps_shared_cover_file(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    filename = "shared123.jpg"
    cover_path = tmp_path / filename
    cover_path.write_bytes(b"image-bytes")

    cover_url = f"/api/covers/{filename}"
    book1 = _create_book(client, title="Book 1", cover_url=cover_url)
    _create_book(client, title="Book 2", cover_url=cover_url)

    resp = client.delete(f"/api/books/{book1['id']}")
    assert resp.status_code == 204
    assert cover_path.exists()


def test_delete_book_ignores_external_cover_url(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    external_url = "https://covers.example.com/book.jpg"
    book = _create_book(client, title="External Cover", cover_url=external_url)

    resp = client.delete(f"/api/books/{book['id']}")
    assert resp.status_code == 204


def test_delete_book_still_succeeds_when_cover_file_missing(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    book = _create_book(client, title="Missing Cover", cover_url="/api/covers/missing.jpg")

    resp = client.delete(f"/api/books/{book['id']}")
    assert resp.status_code == 204


def test_delete_book_not_found_returns_404(client: TestClient) -> None:
    resp = client.delete("/api/books/9999")
    assert resp.status_code == 404


# ── create / update cover download ────────────────────────────────────────────

async def _fake_download_cover_success(url: str, covers_dir: str | Path, http_client: Any, user_id: int) -> str:
    """Fake that saves a small sentinel file and returns its name."""
    filename = "fakecover123.jpg"
    (Path(covers_dir) / filename).write_bytes(b"img")
    return filename


async def _fake_download_cover_fail(url: str, covers_dir: str | Path, http_client: Any, user_id: int) -> None:
    """Fake that simulates a download failure."""
    return None


def test_create_book_with_external_cover_downloads_local(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """When cover_url is external, create_book downloads it locally."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover_success)

    resp = client.post("/api/books", json={"title": "Book", "author": "Test Author", "page_count": 100, "cover_url": "https://example.com/c.jpg"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["cover_url"] == "/api/covers/fakecover123.jpg"
    assert (tmp_path / "fakecover123.jpg").exists()


def test_create_book_cover_download_fail_skips_cover(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """When cover download fails, create_book stores no cover URL."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover_fail)

    ext_url = "https://example.com/fallback.jpg"
    resp = client.post("/api/books", json={"title": "Book", "author": "Test Author", "page_count": 100, "cover_url": ext_url})
    assert resp.status_code == 201
    assert resp.json()["cover_url"] is None


def test_create_book_local_cover_url_not_re_downloaded(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """A /api/covers/ URL is passed through unchanged (no download attempt)."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    called: list[bool] = []
    async def spy(*args: Any, **kwargs: Any) -> None:  # pragma: no cover
        called.append(True)
        return None
    monkeypatch.setattr(books_router, "import_cover_from_url", spy)

    local_url = "/api/covers/existing.jpg"
    resp = client.post("/api/books", json={"title": "Book", "author": "Test Author", "page_count": 100, "cover_url": local_url})
    assert resp.status_code == 201
    assert resp.json()["cover_url"] == local_url
    assert called == []  # download_cover must NOT be called


def test_update_book_with_external_cover_downloads_local(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """update_book downloads an external cover_url to local storage."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover_success)

    book = _create_book(client, title="Book")
    resp = client.patch(f"/api/books/{book['id']}", json={"cover_url": "https://example.com/c.jpg"})
    assert resp.status_code == 200
    assert resp.json()["cover_url"] == "/api/covers/fakecover123.jpg"


def test_update_book_cover_change_deletes_old_local_cover(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Changing cover_url on update removes the old local cover file."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover_success)

    # Create book with an existing local cover.
    old_filename = "oldcover.jpg"
    old_path = tmp_path / old_filename
    old_path.write_bytes(b"old-img")
    book = _create_book(client, title="Book", cover_url=f"/api/covers/{old_filename}")

    # Update with a new external URL (which fakes to fakecover123.jpg).
    resp = client.patch(f"/api/books/{book['id']}", json={"cover_url": "https://example.com/new.jpg"})
    assert resp.status_code == 200
    assert not old_path.exists(), "Old cover file should have been deleted"


def test_update_book_cover_change_keeps_shared_cover(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Old local cover is NOT deleted when another book references it."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover_success)

    shared_filename = "shared.jpg"
    shared_path = tmp_path / shared_filename
    shared_path.write_bytes(b"shared-img")
    shared_url = f"/api/covers/{shared_filename}"

    book1 = _create_book(client, title="B1", cover_url=shared_url)
    _create_book(client, title="B2", cover_url=shared_url)

    resp = client.patch(f"/api/books/{book1['id']}", json={"cover_url": "https://example.com/new.jpg"})
    assert resp.status_code == 200
    assert shared_path.exists(), "Shared cover must not be deleted"


def test_health(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["checks"]["database_connectivity"]["status"] == "healthy"
    assert data["checks"]["database_schema"]["status"] == "healthy"
    assert data["checks"]["data_dir_writable"]["status"] == "healthy"
    assert data["checks"]["quote_service"]["status"] == "healthy"
    assert "detail" in data["checks"]["quote_service"]
    assert "version" in data["checks"]["app_version"]
    assert "git_sha" in data["checks"]["app_version"]


def test_health_database_down(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)

    def fake_text(*args: Any, **kwargs: Any) -> Any:
        raise Exception("Connection refused")
    monkeypatch.setattr("app.routers.health.text", fake_text)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["checks"]["database_connectivity"]["status"] == "unhealthy"
    assert "Connection refused" in data["checks"]["database_connectivity"]["detail"]


def test_health_missing_tables(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)

    class FakeInspector:
        def get_table_names(self) -> list[str]:
            return []

    monkeypatch.setattr("app.routers.health.inspect", lambda bind: FakeInspector())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["checks"]["database_schema"]["status"] == "unhealthy"
    assert "Missing tables" in data["checks"]["database_schema"]["detail"]


def test_health_data_dir_not_writable(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)

    db_dir = tmp_path / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_dir}/librislog.db")
    monkeypatch.setattr("app.routers.health.os_module.access", lambda *a: False)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["checks"]["data_dir_writable"]["status"] == "unhealthy"


def test_health_quote_service_unhealthy(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)

    class FakeFailingAsyncClient:
        async def __aenter__(self) -> Self:
            return self
        async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
            pass
        async def get(self, url: str) -> Any:
            raise Exception("Connection timeout")

    monkeypatch.setattr("app.routers.health.httpx.AsyncClient", FakeFailingAsyncClient)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["quote_service"]["status"] == "unhealthy"


def test_health_quote_service_disabled(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["quote_service"]["status"] == "healthy"
    assert "disabled via configuration" in data["checks"]["quote_service"]["detail"]


# ── suggestions ────────────────────────────────────────────────────────────────

def test_suggest_authors_returns_matching(client: TestClient) -> None:
    _create_book(client, title="A", author="Frank Herbert")
    _create_book(client, title="B", author="Franklin Bob")
    _create_book(client, title="C", author="Isaac Asimov")
    resp = client.get("/api/books/suggestions/authors?q=frank")
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggestions"] == ["Frank Herbert", "Franklin Bob"]


def test_suggest_authors_empty_query_returns_empty(client: TestClient) -> None:
    _create_book(client, title="A", author="Frank Herbert")
    resp = client.get("/api/books/suggestions/authors?q=")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []


def test_suggest_authors_no_match_returns_empty(client: TestClient) -> None:
    _create_book(client, title="A", author="Frank Herbert")
    resp = client.get("/api/books/suggestions/authors?q=zzzzz")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []


def test_suggest_authors_deduplication(client: TestClient) -> None:
    _create_book(client, title="A", author="Frank Herbert")
    _create_book(client, title="B", author="Frank Herbert")
    resp = client.get("/api/books/suggestions/authors?q=herbert")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == ["Frank Herbert"]


def test_suggest_publishers_returns_matching(client: TestClient) -> None:
    _create_book(client, title="A", publisher="Ace Books")
    _create_book(client, title="B", publisher="Bantam Books")
    resp = client.get("/api/books/suggestions/publishers?q=bantam")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == ["Bantam Books"]


def test_suggest_tags_returns_matching(client: TestClient) -> None:
    _create_book(client, title="A", tags="Science Fiction")
    _create_book(client, title="B", tags="Fantasy")
    resp = client.get("/api/books/suggestions/tags?q=fant")
    assert resp.status_code == 200
    data = resp.json()
    assert "Fantasy" in data["suggestions"]


def test_suggest_user_isolation(client: TestClient, create_user_with_key: Callable[..., tuple[User, str]]) -> None:
    _create_book(client, title="User1 Book", author="Frank Herbert")

    user2, key2 = create_user_with_key(email="other@example.com")
    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key2})
        resp2 = c2.post("/api/books", json={"title": "User2 Book", "author": "Isaac Asimov", "page_count": 200})
        assert resp2.status_code == 201

        resp = client.get("/api/books/suggestions/authors?q=frank")
        assert resp.status_code == 200
        assert resp.json()["suggestions"] == ["Frank Herbert"]

        resp2 = c2.get("/api/books/suggestions/authors?q=frank")
        assert resp2.status_code == 200
        assert resp2.json()["suggestions"] == []


# ── user data isolation ────────────────────────────────────────────────────────

def test_same_isbn_allowed_for_different_users(client: TestClient, create_user_with_key: Callable[..., tuple[User, str]]) -> None:
    """ISBN uniqueness is per-user — two users can each have the same ISBN."""

    shared_isbn = "9780441013593"

    # Create book with a shared ISBN for User 1 (default admin)
    book1 = _create_book(client, title="Dune", author="Frank Herbert", page_count=412, isbn=shared_isbn)

    # Create second user and their book with the same ISBN
    user2, key2 = create_user_with_key(email="other@example.com")
    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key2})
        resp = c2.post("/api/books", json={
            "title": "Dune", "author": "Frank Herbert", "page_count": 412, "isbn": shared_isbn,
        })
        assert resp.status_code == 201
        book2 = resp.json()

    # ── list ──
    list1 = client.get("/api/books").json()
    assert len(list1["books"]) == 1
    assert list1["books"][0]["id"] == book1["id"]

    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key2})
        list2 = c2.get("/api/books").json()
        assert len(list2["books"]) == 1
        assert list2["books"][0]["id"] == book2["id"]

    # ── get by id (own) ──
    assert client.get(f"/api/books/{book1['id']}").status_code == 200

    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key2})
        assert c2.get(f"/api/books/{book2['id']}").status_code == 200

    # ── get by id (other user) ──
    assert client.get(f"/api/books/{book2['id']}").status_code == 404

    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key2})
        assert c2.get(f"/api/books/{book1['id']}").status_code == 404

    # ── update (other user) ──
    assert client.patch(f"/api/books/{book2['id']}", json={"title": "Hacked"}).status_code == 404

    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key2})
        assert c2.patch(f"/api/books/{book1['id']}", json={"title": "Hacked"}).status_code == 404

    # ── delete (other user) ──
    assert client.delete(f"/api/books/{book2['id']}").status_code == 404

    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key2})
        assert c2.delete(f"/api/books/{book1['id']}").status_code == 404

    # ── stats isolation ──
    stats1 = client.get("/api/books/stats").json()
    assert stats1["total_books"] == 1

    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key2})
        stats2 = c2.get("/api/books/stats").json()
        assert stats2["total_books"] == 1

    # ── suggestions isolation ──
    resp1 = client.get("/api/books/suggestions/authors?q=Frank")
    assert resp1.json()["suggestions"] == ["Frank Herbert"]

    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key2})
        resp2 = c2.get("/api/books/suggestions/authors?q=Frank")
        assert resp2.json()["suggestions"] == ["Frank Herbert"]


# ── prevent removing date_finished for read books ──────────────────────────────

def test_update_book_rejects_clearing_date_finished_for_read(client: TestClient) -> None:
    book = _create_book(client, title="Read Book", reading_status="read", date_finished="2024-06-01")

    resp = client.patch(f"/api/books/{book['id']}", json={"date_finished": None})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "A finished book must have an end date. Change the status if you want to remove the finish date."


def test_update_book_allows_clearing_date_finished_when_changing_status(client: TestClient) -> None:
    book = _create_book(client, title="Change Status", reading_status="read", date_finished="2024-06-01")

    resp = client.patch(
        f"/api/books/{book['id']}",
        json={"reading_status": "want_to_read", "date_finished": None},
    )
    assert resp.status_code == 200
    assert resp.json()["reading_status"] == "want_to_read"
    assert resp.json()["date_finished"] is None


def test_update_book_allows_edit_without_touching_date_finished_for_read(client: TestClient) -> None:
    book = _create_book(client, title="Edit Other", reading_status="read", date_finished="2024-06-01")

    resp = client.patch(f"/api/books/{book['id']}", json={"rating": 5})
    assert resp.status_code == 200
    assert resp.json()["date_finished"] == "2024-06-01T00:00:00Z"


def test_update_book_allows_clearing_when_date_finished_already_null(client: TestClient) -> None:
    book = _create_book(client, title="Already Null", reading_status="read")

    resp = client.patch(f"/api/books/{book['id']}", json={"date_finished": None})
    assert resp.status_code == 200


def test_transition_status_preserves_date_finished_without_clear_flag(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(client, title="Preserve DF", reading_status="read", date_finished="2024-06-01")

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "want_to_read"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "want_to_read"
    assert data["book"]["date_finished"] == "2024-06-01T00:00:00Z"


def test_transition_status_clears_date_finished_with_clear_flag(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(client, title="Clear DF", reading_status="read", date_finished="2024-06-01")

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "want_to_read", "clear_date_finished": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "want_to_read"
    assert data["book"]["date_finished"] is None


def test_transition_status_ignores_clear_date_finished_when_target_is_read(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    book = _create_book(
        client,
        title="Clear DF Ignored",
        reading_status="currently_reading",
        date_started="2024-01-01",
        date_finished="2024-06-01",
    )
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "read", "clear_date_finished": True, "force_date_finished": "2024-06-01T00:00:00Z"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "read"
    assert data["book"]["date_finished"] is not None


def test_transition_status_respects_force_date_started_to_read(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """Transition from currently_reading to read with a custom start date."""
    book = _create_book(
        client,
        title="Force DS",
        reading_status="currently_reading",
        date_started="2024-01-01",
    )
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={
            "new_status": "read",
            "force_date_started": "2025-06-15T00:00:00Z",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "read"
    assert data["book"]["date_started"] == "2025-06-15T00:00:00Z"
    assert data["book"]["date_finished"] == "2026-05-11T10:30:00Z"


# ── Missing coverage additions ────────────────────────────────────────────────

def test_create_book_future_date_started_returns_422(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    resp = client.post("/api/books", json={"title": "Future", "author": "Test Author", "page_count": 100, "date_started": "2025-01-01"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Date cannot be in the future."


def test_create_book_date_started_after_finished_returns_422(client: TestClient) -> None:
    resp = client.post(
        "/api/books",
        json={"title": "Bad Dates", "author": "Test Author", "page_count": 100, "date_started": "2024-02-01", "date_finished": "2024-01-01"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Start date cannot be after finish date."


def test_create_book_whitespace_language_returns_none(client: TestClient) -> None:
    resp = client.post("/api/books", json={"title": "Whitespace Lang", "author": "Test Author", "page_count": 100, "language": "   "})
    assert resp.status_code == 201
    assert resp.json()["language"] is None


def test_create_book_duplicate_isbn_returns_409(client: TestClient) -> None:
    _create_book(client, title="First", isbn="9780441013593")
    resp = client.post("/api/books", json={"title": "Duplicate", "author": "Test Author", "page_count": 100, "isbn": "9780441013593"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "This ISBN is already used by another book."


def test_list_books_sort_by_date_started(client: TestClient) -> None:
    _create_book(client, title="A", date_started="2024-01-01")
    _create_book(client, title="B", date_started="2024-02-01")
    resp = client.get("/api/books?sort=date_started&order=desc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["books"][0]["title"] == "B"


def test_list_books_sort_by_date_finished(client: TestClient) -> None:
    _create_book(client, title="A", date_finished="2024-01-01")
    _create_book(client, title="B", date_finished="2024-02-01")
    resp = client.get("/api/books?sort=date_finished&order=desc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["books"][0]["title"] == "B"


def test_get_library_stats(client: TestClient) -> None:
    _create_book(client, title="Read", reading_status="read")
    _create_book(client, title="Reading", reading_status="currently_reading")
    _create_book(client, title="Want", reading_status="want_to_read")
    _create_book(client, title="DNF", reading_status="did_not_finish")

    resp = client.get("/api/books/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_books"] == 4
    assert data["books_read"] == 1
    assert data["books_reading"] == 1
    assert data["books_want_to_read"] == 1
    assert data["books_did_not_finish"] == 1


def test_dashboard_quote_disabled_returns_503(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)
    resp = client.get("/api/books/dashboard-quote")
    assert resp.status_code == 503


def test_tag_cloud(client: TestClient) -> None:
    _create_book(client, title="A", tags="Sci-Fi")
    _create_book(client, title="B", tags="Sci-Fi")
    _create_book(client, title="C", tags="Fantasy")

    resp = client.get("/api/books/tags/cloud")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Sci-Fi should have count 2
    sci_fi = next((t for t in data if t["tag"] == "Sci-Fi"), None)
    assert sci_fi is not None
    assert sci_fi["count"] == 2


def test_suggest_tags_empty_query_returns_empty(client: TestClient) -> None:
    _create_book(client, title="A", tags="Sci-Fi")
    resp = client.get("/api/books/suggestions/tags?q=")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []


def test_update_book_cover_download_failed_skips_cover(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "import_cover_from_url", _fake_download_cover_fail)

    book = _create_book(client, title="Book")
    resp = client.patch(
        f"/api/books/{book['id']}",
        json={"cover_url": "https://example.com/fail.jpg"},
    )
    assert resp.status_code == 200
    assert resp.json()["cover_url"] is None


def test_update_book_duplicate_isbn_returns_409(client: TestClient) -> None:
    _create_book(client, title="First", isbn="9780441013593")
    book2 = _create_book(client, title="Second")
    resp = client.patch(
        f"/api/books/{book2['id']}",
        json={"isbn": "9780441013593"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "This ISBN is already used by another book."


def test_transition_status_not_found_returns_404(client: TestClient) -> None:
    resp = client.post("/api/books/9999/transition-status", json={"new_status": "read"})
    assert resp.status_code == 404


def test_transition_status_clears_date_started(client: TestClient) -> None:
    book = _create_book(
        client,
        title="Clear DS",
        reading_status="want_to_read",
        date_started="2024-01-01",
    )
    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "currently_reading", "clear_date_started": True, "skip_auto_date_started": True},
    )
    assert resp.status_code == 200
    assert resp.json()["book"]["date_started"] is None


def test_delete_book_with_tags_and_progress(client: TestClient) -> None:
    book = _create_book(client, title="Tagged", tags="Sci-Fi", page_count=100)
    book_id = book["id"]

    # Add progress
    prog_resp = client.post(f"/api/books/{book_id}/progress", json={"page": 50})
    assert prog_resp.status_code == 201

    resp = client.delete(f"/api/books/{book_id}")
    assert resp.status_code == 204

    # Confirm gone
    assert client.get(f"/api/books/{book_id}").status_code == 404


def test_update_book_tags(client: TestClient) -> None:
    book = _create_book(client, title="Tag Me", tags="Old Tag")
    resp = client.patch(
        f"/api/books/{book['id']}",
        json={"tags": "New Tag"},
    )
    assert resp.status_code == 200
    assert resp.json()["tags"] == "New Tag"


def test_dashboard_quote_enabled_returns_quote(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)

    async def _fake_quote() -> dict[str, str]:
        return {"quote": "Hello", "author": "World"}

    monkeypatch.setattr(books_router, "get_or_fetch_dashboard_quote", _fake_quote)
    resp = client.get("/api/books/dashboard-quote")
    assert resp.status_code == 200
    assert resp.json()["quote"] == "Hello"


def test_create_book_commit_integrity_error(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """Commit IntegrityError in create_book is caught and re-raised (covers lines 378-380, 119)."""
    original_commit = Session.commit
    call_count = 0

    def _fake_commit(self: Session) -> None:
        nonlocal call_count
        call_count += 1
        # auth dependency commits first (call_count=1), create_book commits second (call_count=2)
        if call_count == 2:
            raise SQLAIntegrityError("stmt", {}, Exception("commit conflict"))
        return original_commit(self)

    monkeypatch.setattr(Session, "commit", _fake_commit)
    with pytest.raises(SQLAIntegrityError):
        client.post("/api/books", json={"title": "Commit Conflict", "author": "Test Author", "page_count": 100})


def test_update_book_commit_integrity_error(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """Commit IntegrityError in update_book is caught and re-raised (covers lines 464-466, 119)."""
    original_commit = Session.commit
    call_count = 0

    def _fake_commit(self: Session) -> None:
        nonlocal call_count
        call_count += 1
        # auth(1) + create_book(2) + auth(3) + update_book(4)
        if call_count == 4:
            raise SQLAIntegrityError("stmt", {}, Exception("commit conflict"))
        return original_commit(self)

    monkeypatch.setattr(Session, "commit", _fake_commit)
    book = _create_book(client, title="Book")
    with pytest.raises(SQLAIntegrityError):
        client.patch(f"/api/books/{book['id']}", json={"tags": "Tag"})
