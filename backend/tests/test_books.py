from fastapi.testclient import TestClient

from app.config import settings


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


# ── health ────────────────────────────────────────────────────────────────────

def test_health(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
