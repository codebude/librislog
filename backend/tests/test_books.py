from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.config import settings
import app.routers.books as books_router


# ── helpers ──────────────────────────────────────────────────────────────────

def _create_book(client: TestClient, **kwargs) -> dict:
    payload = {"title": "Test Book", **kwargs}
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ── create ────────────────────────────────────────────────────────────────────

def test_create_book_returns_201(client: TestClient):
    resp = client.post("/api/books", json={"title": "Dune"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Dune"
    assert data["id"] is not None
    assert data["reading_status"] == "want_to_read"


def test_create_book_with_all_fields(client: TestClient):
    payload = {
        "title": "Dune",
        "author": "Frank Herbert",
        "isbn": "9780441013593",
        "publisher": "Ace Books",
        "published_year": 1965,
        "page_count": 412,
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
    assert data["rating"] == 5
    assert data["reading_status"] == "read"


def test_create_book_missing_title_returns_422(client: TestClient):
    resp = client.post("/api/books", json={"author": "Frank Herbert"})
    assert resp.status_code == 422


def test_create_book_invalid_rating_returns_422(client: TestClient):
    resp = client.post("/api/books", json={"title": "Dune", "rating": 6})
    assert resp.status_code == 422


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_books_empty(client: TestClient):
    resp = client.get("/api/books")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_books_returns_all(client: TestClient):
    _create_book(client, title="Book A")
    _create_book(client, title="Book B")
    resp = client.get("/api/books")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_books_filter_by_status(client: TestClient):
    _create_book(client, title="Want", reading_status="want_to_read")
    _create_book(client, title="Reading", reading_status="currently_reading")
    _create_book(client, title="Done", reading_status="read")
    _create_book(client, title="DNF", reading_status="did_not_finish")

    resp = client.get("/api/books?status=currently_reading")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Reading"


def test_list_books_search_by_title(client: TestClient):
    _create_book(client, title="Dune")
    _create_book(client, title="Foundation")
    resp = client.get("/api/books?q=dune")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Dune"


def test_list_books_search_by_author(client: TestClient):
    _create_book(client, title="Dune", author="Frank Herbert")
    _create_book(client, title="Foundation", author="Isaac Asimov")
    resp = client.get("/api/books?q=asimov")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Foundation"


def test_list_books_sort_by_rating(client: TestClient):
    _create_book(client, title="Low", rating=2)
    _create_book(client, title="High", rating=5)
    resp = client.get("/api/books?sort=rating&order=desc")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["title"] == "High"
    assert data[1]["title"] == "Low"


def test_list_books_sort_by_date_added_asc(client: TestClient):
    _create_book(client, title="First")
    _create_book(client, title="Second")
    resp = client.get("/api/books?sort=date_added&order=asc")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["title"] == "First"


def test_list_books_smart_sort_currently_reading_by_date_started(client: TestClient):
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
    data = resp.json()
    assert [item["title"] for item in data] == ["Newer", "Older", "No Start"]


def test_list_books_smart_sort_read_by_date_finished(client: TestClient):
    _create_book(client, title="Older", reading_status="read", date_finished="2024-01-01")
    _create_book(client, title="Newer", reading_status="read", date_finished="2024-02-01")
    _create_book(client, title="No Finish", reading_status="read")

    resp = client.get("/api/books?status=read")
    assert resp.status_code == 200
    data = resp.json()
    assert [item["title"] for item in data] == ["Newer", "Older", "No Finish"]


def test_list_books_manual_sort_still_available_with_smart_sort_off(client: TestClient):
    _create_book(client, title="Low", reading_status="currently_reading", rating=1)
    _create_book(client, title="High", reading_status="currently_reading", rating=5)

    resp = client.get("/api/books?status=currently_reading&smart_sort=false&sort=rating&order=desc")
    assert resp.status_code == 200
    data = resp.json()
    assert [item["title"] for item in data] == ["High", "Low"]


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_book_returns_book(client: TestClient):
    book = _create_book(client, title="Dune")
    resp = client.get(f"/api/books/{book['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Dune"


def test_get_book_not_found_returns_404(client: TestClient):
    resp = client.get("/api/books/9999")
    assert resp.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────

def test_update_book_status(client: TestClient):
    book = _create_book(client)
    resp = client.patch(f"/api/books/{book['id']}", json={"reading_status": "currently_reading"})
    assert resp.status_code == 200
    assert resp.json()["reading_status"] == "currently_reading"


def test_create_book_with_did_not_finish_status(client: TestClient):
    resp = client.post("/api/books", json={"title": "DNF Book", "reading_status": "did_not_finish"})
    assert resp.status_code == 201
    assert resp.json()["reading_status"] == "did_not_finish"


def test_list_books_filter_by_did_not_finish_status(client: TestClient):
    _create_book(client, title="Read", reading_status="read")
    _create_book(client, title="DNF", reading_status="did_not_finish")

    resp = client.get("/api/books?status=did_not_finish")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "DNF"


def test_update_book_to_did_not_finish_status(client: TestClient):
    book = _create_book(client, title="Update To DNF")

    resp = client.patch(f"/api/books/{book['id']}", json={"reading_status": "did_not_finish"})
    assert resp.status_code == 200
    assert resp.json()["reading_status"] == "did_not_finish"


def test_update_book_sets_date_started_when_moving_to_currently_reading(client: TestClient, monkeypatch):
    book = _create_book(client, title="Date Start")
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.patch(f"/api/books/{book['id']}", json={"reading_status": "currently_reading"})
    assert resp.status_code == 200
    assert resp.json()["date_started"].startswith("2026-05-11T10:30:00")


def test_update_book_sets_date_finished_when_moving_to_read(client: TestClient, monkeypatch):
    book = _create_book(client, title="Date Finished")
    monkeypatch.setattr(
        books_router,
        "_utcnow",
        lambda: datetime(2026, 5, 11, 10, 30, tzinfo=timezone.utc),
    )

    resp = client.patch(f"/api/books/{book['id']}", json={"reading_status": "read"})
    assert resp.status_code == 200
    assert resp.json()["date_finished"].startswith("2026-05-11T10:30:00")


def test_update_book_does_not_override_existing_date_started(client: TestClient, monkeypatch):
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


def test_transition_status_returns_conflict_when_date_started_exists(client: TestClient, monkeypatch):
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


def test_transition_status_can_keep_existing_date_started(client: TestClient, monkeypatch):
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


def test_transition_status_sets_date_finished_for_did_not_finish(client: TestClient, monkeypatch):
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


def test_transition_status_returns_conflict_when_date_finished_exists(client: TestClient, monkeypatch):
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


def test_transition_status_can_override_existing_date_finished(client: TestClient, monkeypatch):
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


def test_transition_status_conflict_when_started_after_finished(client: TestClient, monkeypatch):
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


def test_transition_status_option_a_clear_finished_and_start(client: TestClient, monkeypatch):
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


def test_transition_status_option_b_skip_auto_date_started(client: TestClient, monkeypatch):
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


def test_transition_status_chained_detects_started_after_finished(client: TestClient, monkeypatch):
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


def test_transition_status_chained_option_a_clear_finished(client: TestClient, monkeypatch):
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


def test_transition_status_chained_option_b_keep_finished(client: TestClient, monkeypatch):
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


def test_update_book_rating(client: TestClient):
    book = _create_book(client)
    resp = client.patch(f"/api/books/{book['id']}", json={"rating": 4})
    assert resp.status_code == 200
    assert resp.json()["rating"] == 4


def test_update_book_partial_leaves_other_fields(client: TestClient):
    book = _create_book(client, title="Dune", author="Frank Herbert")
    resp = client.patch(f"/api/books/{book['id']}", json={"rating": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["author"] == "Frank Herbert"
    assert data["rating"] == 3


def test_update_book_not_found_returns_404(client: TestClient):
    resp = client.patch("/api/books/9999", json={"rating": 3})
    assert resp.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_book(client: TestClient):
    book = _create_book(client)
    resp = client.delete(f"/api/books/{book['id']}")
    assert resp.status_code == 204
    # Confirm gone
    assert client.get(f"/api/books/{book['id']}").status_code == 404


def test_delete_book_removes_local_cover_file(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    filename = "abc123.jpg"
    cover_path = tmp_path / filename
    cover_path.write_bytes(b"image-bytes")

    book = _create_book(client, title="With Cover", cover_url=f"/api/covers/{filename}")

    resp = client.delete(f"/api/books/{book['id']}")
    assert resp.status_code == 204
    assert not cover_path.exists()


def test_delete_book_keeps_shared_cover_file(client: TestClient, tmp_path, monkeypatch):
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


def test_delete_book_ignores_external_cover_url(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    external_url = "https://covers.example.com/book.jpg"
    book = _create_book(client, title="External Cover", cover_url=external_url)

    resp = client.delete(f"/api/books/{book['id']}")
    assert resp.status_code == 204


def test_delete_book_still_succeeds_when_cover_file_missing(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    book = _create_book(client, title="Missing Cover", cover_url="/api/covers/missing.jpg")

    resp = client.delete(f"/api/books/{book['id']}")
    assert resp.status_code == 204


def test_delete_book_not_found_returns_404(client: TestClient):
    resp = client.delete("/api/books/9999")
    assert resp.status_code == 404


# ── create / update cover download ────────────────────────────────────────────

async def _fake_download_cover_success(url, covers_dir, http_client, user_id):
    """Fake that saves a small sentinel file and returns its name."""
    from pathlib import Path
    filename = "fakecover123.jpg"
    (Path(covers_dir) / filename).write_bytes(b"img")
    return filename


async def _fake_download_cover_fail(url, covers_dir, http_client, user_id):
    """Fake that simulates a download failure."""
    return None


def test_create_book_with_external_cover_downloads_local(client, tmp_path, monkeypatch):
    """When cover_url is external, create_book downloads it locally."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "download_cover", _fake_download_cover_success)

    resp = client.post("/api/books", json={"title": "Book", "cover_url": "https://example.com/c.jpg"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["cover_url"] == "/api/covers/fakecover123.jpg"
    assert (tmp_path / "fakecover123.jpg").exists()


def test_create_book_cover_download_fail_skips_cover(client, tmp_path, monkeypatch):
    """When cover download fails, create_book stores no cover URL."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "download_cover", _fake_download_cover_fail)

    ext_url = "https://example.com/fallback.jpg"
    resp = client.post("/api/books", json={"title": "Book", "cover_url": ext_url})
    assert resp.status_code == 201
    assert resp.json()["cover_url"] is None


def test_create_book_local_cover_url_not_re_downloaded(client, tmp_path, monkeypatch):
    """A /api/covers/ URL is passed through unchanged (no download attempt)."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    called = []
    async def spy(*args, **kwargs):
        called.append(True)
        return None
    monkeypatch.setattr(books_router, "download_cover", spy)

    local_url = "/api/covers/existing.jpg"
    resp = client.post("/api/books", json={"title": "Book", "cover_url": local_url})
    assert resp.status_code == 201
    assert resp.json()["cover_url"] == local_url
    assert called == []  # download_cover must NOT be called


def test_update_book_with_external_cover_downloads_local(client, tmp_path, monkeypatch):
    """update_book downloads an external cover_url to local storage."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "download_cover", _fake_download_cover_success)

    book = _create_book(client, title="Book")
    resp = client.patch(f"/api/books/{book['id']}", json={"cover_url": "https://example.com/c.jpg"})
    assert resp.status_code == 200
    assert resp.json()["cover_url"] == "/api/covers/fakecover123.jpg"


def test_update_book_cover_change_deletes_old_local_cover(client, tmp_path, monkeypatch):
    """Changing cover_url on update removes the old local cover file."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "download_cover", _fake_download_cover_success)

    # Create book with an existing local cover.
    old_filename = "oldcover.jpg"
    old_path = tmp_path / old_filename
    old_path.write_bytes(b"old-img")
    book = _create_book(client, title="Book", cover_url=f"/api/covers/{old_filename}")

    # Update with a new external URL (which fakes to fakecover123.jpg).
    resp = client.patch(f"/api/books/{book['id']}", json={"cover_url": "https://example.com/new.jpg"})
    assert resp.status_code == 200
    assert not old_path.exists(), "Old cover file should have been deleted"


def test_update_book_cover_change_keeps_shared_cover(client, tmp_path, monkeypatch):
    """Old local cover is NOT deleted when another book references it."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "download_cover", _fake_download_cover_success)

    shared_filename = "shared.jpg"
    shared_path = tmp_path / shared_filename
    shared_path.write_bytes(b"shared-img")
    shared_url = f"/api/covers/{shared_filename}"

    book1 = _create_book(client, title="B1", cover_url=shared_url)
    _create_book(client, title="B2", cover_url=shared_url)

    resp = client.patch(f"/api/books/{book1['id']}", json={"cover_url": "https://example.com/new.jpg"})
    assert resp.status_code == 200
    assert shared_path.exists(), "Shared cover must not be deleted"

def test_health(client: TestClient, monkeypatch):
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


def test_health_database_down(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)

    def fake_text(*args, **kwargs):
        raise Exception("Connection refused")
    monkeypatch.setattr("app.routers.health.text", fake_text)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["checks"]["database_connectivity"]["status"] == "unhealthy"
    assert "Connection refused" in data["checks"]["database_connectivity"]["detail"]


def test_health_missing_tables(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)

    class FakeInspector:
        def get_table_names(self):
            return []

    monkeypatch.setattr("app.routers.health.inspect", lambda bind: FakeInspector())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["checks"]["database_schema"]["status"] == "unhealthy"
    assert "Missing tables" in data["checks"]["database_schema"]["detail"]


def test_health_data_dir_not_writable(client: TestClient, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)

    db_dir = tmp_path / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_dir}/librislog.db")
    monkeypatch.setattr("app.routers.health.os_module.access", lambda *a, **kw: False)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["checks"]["data_dir_writable"]["status"] == "unhealthy"


def test_health_quote_service_unhealthy(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)

    class FakeFailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        async def get(self, url):
            raise Exception("Connection timeout")

    monkeypatch.setattr("app.routers.health.httpx.AsyncClient", FakeFailingAsyncClient)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["quote_service"]["status"] == "unhealthy"


def test_health_quote_service_disabled(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["quote_service"]["status"] == "healthy"
    assert "disabled via configuration" in data["checks"]["quote_service"]["detail"]


# ── suggestions ────────────────────────────────────────────────────────────────

def test_suggest_authors_returns_matching(client: TestClient):
    _create_book(client, title="A", author="Frank Herbert")
    _create_book(client, title="B", author="Franklin Bob")
    _create_book(client, title="C", author="Isaac Asimov")
    resp = client.get("/api/books/suggestions/authors?q=frank")
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggestions"] == ["Frank Herbert", "Franklin Bob"]


def test_suggest_authors_empty_query_returns_empty(client: TestClient):
    _create_book(client, title="A", author="Frank Herbert")
    resp = client.get("/api/books/suggestions/authors?q=")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []


def test_suggest_authors_no_match_returns_empty(client: TestClient):
    _create_book(client, title="A", author="Frank Herbert")
    resp = client.get("/api/books/suggestions/authors?q=zzzzz")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []


def test_suggest_authors_deduplication(client: TestClient):
    _create_book(client, title="A", author="Frank Herbert")
    _create_book(client, title="B", author="Frank Herbert")
    resp = client.get("/api/books/suggestions/authors?q=herbert")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == ["Frank Herbert"]


def test_suggest_publishers_returns_matching(client: TestClient):
    _create_book(client, title="A", publisher="Ace Books")
    _create_book(client, title="B", publisher="Bantam Books")
    resp = client.get("/api/books/suggestions/publishers?q=bantam")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == ["Bantam Books"]


def test_suggest_tags_returns_matching(client: TestClient):
    _create_book(client, title="A", tags="Science Fiction")
    _create_book(client, title="B", tags="Fantasy")
    resp = client.get("/api/books/suggestions/tags?q=fant")
    assert resp.status_code == 200
    data = resp.json()
    assert "Fantasy" in data["suggestions"]


def test_suggest_user_isolation(client, create_user_with_key):
    _create_book(client, title="User1 Book", author="Frank Herbert")

    user2, key2 = create_user_with_key(email="other@example.com")
    c2 = TestClient(client.app)
    c2.headers.update({"X-API-Key": key2})
    resp2 = c2.post("/api/books", json={"title": "User2 Book", "author": "Isaac Asimov"})
    assert resp2.status_code == 201

    resp = client.get("/api/books/suggestions/authors?q=frank")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == ["Frank Herbert"]

    resp2 = c2.get("/api/books/suggestions/authors?q=frank")
    assert resp2.status_code == 200
    assert resp2.json()["suggestions"] == []


# ── prevent removing date_finished for read books ──────────────────────────────

def test_update_book_rejects_clearing_date_finished_for_read(client: TestClient):
    book = _create_book(client, title="Read Book", reading_status="read", date_finished="2024-06-01")

    resp = client.patch(f"/api/books/{book['id']}", json={"date_finished": None})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "error.dateFinishedRequiredForRead"


def test_update_book_allows_clearing_date_finished_when_changing_status(client: TestClient):
    book = _create_book(client, title="Change Status", reading_status="read", date_finished="2024-06-01")

    resp = client.patch(
        f"/api/books/{book['id']}",
        json={"reading_status": "want_to_read", "date_finished": None},
    )
    assert resp.status_code == 200
    assert resp.json()["reading_status"] == "want_to_read"
    assert resp.json()["date_finished"] is None


def test_update_book_allows_edit_without_touching_date_finished_for_read(client: TestClient):
    book = _create_book(client, title="Edit Other", reading_status="read", date_finished="2024-06-01")

    resp = client.patch(f"/api/books/{book['id']}", json={"rating": 5})
    assert resp.status_code == 200
    assert resp.json()["date_finished"] == "2024-06-01T00:00:00Z"


def test_update_book_allows_clearing_when_date_finished_already_null(client: TestClient):
    book = _create_book(client, title="Already Null", reading_status="read")

    resp = client.patch(f"/api/books/{book['id']}", json={"date_finished": None})
    assert resp.status_code == 200


def test_transition_status_preserves_date_finished_without_clear_flag(client: TestClient, monkeypatch):
    book = _create_book(client, title="Preserve DF", reading_status="read", date_finished="2024-06-01")

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "want_to_read"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "want_to_read"
    assert data["book"]["date_finished"] == "2024-06-01T00:00:00Z"


def test_transition_status_clears_date_finished_with_clear_flag(client: TestClient, monkeypatch):
    book = _create_book(client, title="Clear DF", reading_status="read", date_finished="2024-06-01")

    resp = client.post(
        f"/api/books/{book['id']}/transition-status",
        json={"new_status": "want_to_read", "clear_date_finished": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["book"]["reading_status"] == "want_to_read"
    assert data["book"]["date_finished"] is None


def test_transition_status_ignores_clear_date_finished_when_target_is_read(client: TestClient, monkeypatch):
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


def test_transition_status_respects_force_date_started_to_read(client: TestClient, monkeypatch):
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
