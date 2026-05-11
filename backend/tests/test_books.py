from fastapi.testclient import TestClient

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
        "genre": "Science Fiction",
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

async def _fake_download_cover_success(url, covers_dir, http_client):
    """Fake that saves a small sentinel file and returns its name."""
    from pathlib import Path
    filename = "fakecover123.jpg"
    (Path(covers_dir) / filename).write_bytes(b"img")
    return filename


async def _fake_download_cover_fail(url, covers_dir, http_client):
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


def test_create_book_cover_download_fail_falls_back_to_external(client, tmp_path, monkeypatch):
    """When cover download fails, create_book stores the original external URL."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    monkeypatch.setattr(books_router, "download_cover", _fake_download_cover_fail)

    ext_url = "https://example.com/fallback.jpg"
    resp = client.post("/api/books", json={"title": "Book", "cover_url": ext_url})
    assert resp.status_code == 201
    assert resp.json()["cover_url"] == ext_url


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

def test_health(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
