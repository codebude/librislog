"""
Tests for the book import service and import API endpoints.

HTTP calls are intercepted with monkeypatch — no real network requests are made.
All test functions are modular (no classes).
"""

import pytest
import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.routers import import_ as import_router
from app.schemas import BookImportCandidate
from app.services import book_import


# ── Fake response data ─────────────────────────────────────────────────────────

OPEN_LIBRARY_DUNE_DOC = {
    "title": "Dune",
    "author_name": ["Frank Herbert"],
    "isbn": ["9780441013593", "0441013597"],
    "language": ["eng"],
    "publisher": ["Ace Books", "Chilton Books"],
    "first_publish_year": 1965,
    "number_of_pages_median": 412,
    "subject": ["Science Fiction", "Ecology", "Fantasy"],
    "cover_i": 11481354,
}

GOOGLE_BOOKS_FOUNDATION_ITEM = {
    "volumeInfo": {
        "title": "Foundation",
        "authors": ["Isaac Asimov"],
        "industryIdentifiers": [
            {"type": "ISBN_13", "identifier": "9780553293357"},
            {"type": "ISBN_10", "identifier": "0553293354"},
        ],
        "publisher": "Bantam Books",
        "publishedDate": "1991",
        "language": "en",
        "pageCount": 255,
        "categories": ["Science Fiction"],
        "imageLinks": {"thumbnail": "http://books.google.com/thumbnail.jpg"},
    }
}


# ── map_open_library unit tests ────────────────────────────────────────────────

def test_map_open_library_fields():
    result = book_import.map_open_library(OPEN_LIBRARY_DUNE_DOC)
    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    assert result.isbn == "9780441013593"  # ISBN-13 preferred
    assert result.published_year == 1965
    assert result.page_count == 412
    assert result.language == "EN"
    assert result.publisher == "Ace Books"
    assert "Science Fiction" in result.genre
    assert result.cover_url == "https://covers.openlibrary.org/b/id/11481354-L.jpg"
    assert result.source == "open_library"


def test_map_open_library_missing_optional_fields():
    minimal = {"title": "Minimal Book"}
    result = book_import.map_open_library(minimal)
    assert result.title == "Minimal Book"
    assert result.author is None
    assert result.isbn is None
    assert result.cover_url is None
    assert result.language is None
    assert result.publisher is None
    assert result.genre is None
    assert result.source == "open_library"


def test_map_open_library_genre_capped_at_three():
    doc = {"title": "X", "subject": ["A", "B", "C", "D", "E"]}
    result = book_import.map_open_library(doc)
    assert result.genre == "A, B, C"


# ── map_google_books unit tests ───────────────────────────────────────────────

def test_map_google_books_fields():
    result = book_import.map_google_books(GOOGLE_BOOKS_FOUNDATION_ITEM)
    assert result.title == "Foundation"
    assert result.author == "Isaac Asimov"
    assert result.isbn == "9780553293357"  # ISBN-13 preferred
    assert result.publisher == "Bantam Books"
    assert result.published_year == 1991
    assert result.page_count == 255
    assert result.language == "EN"
    assert result.genre == "Science Fiction"
    assert result.cover_url == "https://books.google.com/thumbnail.jpg"  # https upgraded
    assert result.source == "google_books"


def test_map_google_books_missing_optional_fields():
    minimal = {"volumeInfo": {"title": "Minimal"}}
    result = book_import.map_google_books(minimal)
    assert result.title == "Minimal"
    assert result.author is None
    assert result.isbn is None
    assert result.cover_url is None
    assert result.language is None
    assert result.published_year is None
    assert result.source == "google_books"


def test_normalize_language_code_converts_iso_639_2_to_iso_639_1():
    assert book_import._normalize_language_code("eng") == "EN"
    assert book_import._normalize_language_code("fra") == "FR"


def test_normalize_language_code_keeps_iso_639_1_uppercase():
    assert book_import._normalize_language_code("en") == "EN"
    assert book_import._normalize_language_code(" De ") == "DE"


def test_normalize_language_code_rejects_invalid_values():
    assert book_import._normalize_language_code(None) is None
    assert book_import._normalize_language_code("") is None
    assert book_import._normalize_language_code("123") is None
    assert book_import._normalize_language_code("english") is None
    assert book_import._normalize_language_code("zzz") is None


def test_map_google_books_prefers_isbn13_over_isbn10():
    item = {
        "volumeInfo": {
            "title": "T",
            "industryIdentifiers": [
                {"type": "ISBN_10", "identifier": "0553293354"},
                {"type": "ISBN_13", "identifier": "9780553293357"},
            ],
        }
    }
    result = book_import.map_google_books(item)
    assert result.isbn == "9780553293357"


def test_map_google_books_published_year_partial_date():
    item = {"volumeInfo": {"title": "T", "publishedDate": "1991-06"}}
    result = book_import.map_google_books(item)
    assert result.published_year == 1991


# ── search() integration tests using monkeypatch ──────────────────────────────

@pytest.fixture()
def fake_ol_result() -> list[BookImportCandidate]:
    return [book_import.map_open_library(OPEN_LIBRARY_DUNE_DOC)]


@pytest.fixture()
def fake_gb_result() -> list[BookImportCandidate]:
    return [book_import.map_google_books(GOOGLE_BOOKS_FOUNDATION_ITEM)]


@pytest.mark.anyio
async def test_search_returns_open_library_results(monkeypatch, fake_ol_result):
    async def fake_ol(query, search_type, client):
        return fake_ol_result

    async def fake_gb(query, search_type, api_key, client):
        return []

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_google_books", fake_gb)

    results = await book_import.search("dune", "title")
    assert len(results) == 1
    assert results[0].title == "Dune"
    assert results[0].source == "open_library"


@pytest.mark.anyio
async def test_search_falls_back_to_google_books_when_ol_empty(monkeypatch, fake_gb_result):
    async def fake_ol(query, search_type, client):
        return []

    async def fake_gb(query, search_type, api_key, client):
        return fake_gb_result

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_google_books", fake_gb)

    # api_key must be non-empty — the real API requires a key and the guard
    # skips the fallback when none is configured.
    results = await book_import.search("foundation", "title", api_key="test-key")
    assert len(results) == 1
    assert results[0].source == "google_books"


@pytest.mark.anyio
async def test_search_returns_empty_when_both_fail(monkeypatch):
    async def fake_ol(query, search_type, client):
        return []

    async def fake_gb(query, search_type, api_key, client):
        return []

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_google_books", fake_gb)

    results = await book_import.search("unknownxyz", "title")
    assert results == []


# ── Import API endpoint tests ─────────────────────────────────────────────────

def test_import_search_endpoint(client: TestClient, monkeypatch):
    async def fake_search(query, search_type, *, api_key, http_client):
        return [book_import.map_open_library(OPEN_LIBRARY_DUNE_DOC)]

    monkeypatch.setattr(book_import, "search", fake_search)

    resp = client.get("/api/import/search?q=dune&type=title")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Dune"
    assert data[0]["source"] == "open_library"


def test_import_search_requires_query(client: TestClient):
    resp = client.get("/api/import/search")
    assert resp.status_code == 422


def test_import_book_creates_entry(client: TestClient):
    payload = {
        "candidate": {
            "title": "Dune",
            "author": "Frank Herbert",
            "isbn": "9780441013593",
            "cover_url": "https://covers.openlibrary.org/b/id/11481354-M.jpg",
            "publisher": "Ace Books",
            "published_year": 1965,
            "page_count": 412,
            "genre": "Science Fiction",
            "source": "open_library",
        },
        "reading_status": "want_to_read",
    }
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Dune"
    assert data["isbn"] == "9780441013593"
    assert data["reading_status"] == "want_to_read"
    assert data["id"] is not None


def test_import_book_duplicate_isbn_returns_409(client: TestClient):
    payload = {
        "candidate": {
            "title": "Dune",
            "isbn": "9780441013593",
            "source": "open_library",
        },
        "reading_status": "want_to_read",
    }
    client.post("/api/import", json=payload)
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 409


def test_import_book_without_isbn_allows_duplicates(client: TestClient):
    """Books without ISBN can be added multiple times (no unique constraint)."""
    payload = {
        "candidate": {
            "title": "Unknown Book",
            "source": "open_library",
        },
        "reading_status": "want_to_read",
    }
    r1 = client.post("/api/import", json=payload)
    r2 = client.post("/api/import", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201


def test_import_book_with_reading_status(client: TestClient):
    payload = {
        "candidate": {
            "title": "Foundation",
            "isbn": "9780553293357",
            "source": "google_books",
        },
        "reading_status": "read",
    }
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 201
    assert resp.json()["reading_status"] == "read"


# ── search_with_progress() tests ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_with_progress_open_library_success(monkeypatch, fake_ol_result):
    async def fake_ol(query, search_type, client):
        return fake_ol_result

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)

    events = []
    async for event in book_import.search_with_progress("dune", "title"):
        events.append(event)

    assert events[0] == {"stage": "open_library", "status": "searching"}
    assert events[1] == {"stage": "open_library", "status": "done", "count": 1}
    complete = events[2]
    assert complete["stage"] == "complete"
    assert len(complete["results"]) == 1
    assert complete["results"][0]["title"] == "Dune"
    # Google Books events should NOT be present
    assert not any(e.get("stage") == "google_books" for e in events)


@pytest.mark.anyio
async def test_search_with_progress_falls_back_to_google(monkeypatch, fake_gb_result):
    async def fake_ol(query, search_type, client):
        return []

    async def fake_gb(query, search_type, api_key, client):
        return fake_gb_result

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_google_books", fake_gb)

    events = []
    async for event in book_import.search_with_progress("foundation", "title", api_key="test-key"):
        events.append(event)

    stages = [(e["stage"], e.get("status")) for e in events]
    assert ("open_library", "searching") in stages
    assert ("open_library", "done") in stages
    assert ("google_books", "searching") in stages
    assert ("google_books", "done") in stages
    ol_done = next(e for e in events if e.get("stage") == "open_library" and e.get("status") == "done")
    assert ol_done["count"] == 0
    gb_done = next(e for e in events if e.get("stage") == "google_books" and e.get("status") == "done")
    assert gb_done["count"] == 1
    complete = next(e for e in events if e.get("stage") == "complete")
    assert complete["results"][0]["source"] == "google_books"


@pytest.mark.anyio
async def test_search_with_progress_skips_google_without_key(monkeypatch):
    async def fake_ol(query, search_type, client):
        return []

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)

    events = []
    async for event in book_import.search_with_progress("anything", "title"):
        events.append(event)

    skipped = next((e for e in events if e.get("stage") == "google_books"), None)
    assert skipped is not None
    assert skipped["status"] == "skipped"
    assert skipped["reason"] == "no_api_key"
    complete = next(e for e in events if e.get("stage") == "complete")
    assert complete["results"] == []


@pytest.mark.anyio
async def test_search_with_progress_google_only_runs_google(monkeypatch, fake_gb_result):
    calls = {"ol": 0, "gb": 0}

    async def fake_ol(query, search_type, client):
        calls["ol"] += 1
        return []

    async def fake_gb(query, search_type, api_key, client):
        calls["gb"] += 1
        return fake_gb_result

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_google_books", fake_gb)

    events = []
    async for event in book_import.search_with_progress(
        "foundation", "title", api_key="test-key", mode="google_only"
    ):
        events.append(event)

    stages = [(e["stage"], e.get("status")) for e in events if e.get("stage") != "complete"]
    assert ("google_books", "searching") in stages
    assert ("google_books", "done") in stages
    assert calls["ol"] == 0
    assert calls["gb"] == 1
    complete = next(e for e in events if e.get("stage") == "complete")
    assert complete["results"][0]["source"] == "google_books"


@pytest.mark.anyio
async def test_search_with_progress_google_only_without_key_skips(monkeypatch):
    calls = {"gb": 0}

    async def fake_gb(query, search_type, api_key, client):
        calls["gb"] += 1
        return []

    monkeypatch.setattr(book_import, "_search_google_books", fake_gb)

    events = []
    async for event in book_import.search_with_progress("foundation", "title", mode="google_only"):
        events.append(event)

    skipped = next(e for e in events if e.get("stage") == "google_books")
    assert skipped["status"] == "skipped"
    assert skipped["reason"] == "no_api_key"
    complete = next(e for e in events if e.get("stage") == "complete")
    assert complete["results"] == []
    assert calls["gb"] == 0


# ── Stream endpoint tests ──────────────────────────────────────────────────────

def _parse_sse(text: str) -> list[dict]:
    """Parse SSE response body into a list of event dicts."""
    import json as _json
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload:
                events.append(_json.loads(payload))
    return events


def test_search_stream_endpoint(client: TestClient, monkeypatch):
    observed_mode = {"value": None}

    async def fake_search_with_progress(query, search_type, *, api_key, mode, http_client):
        observed_mode["value"] = mode
        yield {"stage": "open_library", "status": "searching"}
        yield {"stage": "open_library", "status": "done", "count": 1}
        yield {
            "stage": "complete",
            "results": [book_import.map_open_library(OPEN_LIBRARY_DUNE_DOC).model_dump()],
        }

    monkeypatch.setattr(book_import, "search_with_progress", fake_search_with_progress)

    resp = client.get("/api/import/search/stream?q=dune&type=title")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse(resp.text)
    assert events[0] == {"stage": "open_library", "status": "searching"}
    assert events[1] == {"stage": "open_library", "status": "done", "count": 1}
    complete = events[2]
    assert complete["stage"] == "complete"
    assert complete["results"][0]["title"] == "Dune"
    assert observed_mode["value"] == "auto"


def test_search_stream_endpoint_forwards_google_only_mode(client: TestClient, monkeypatch):
    observed_mode = {"value": None}

    async def fake_search_with_progress(query, search_type, *, api_key, mode, http_client):
        observed_mode["value"] = mode
        yield {"stage": "google_books", "status": "searching"}
        yield {"stage": "google_books", "status": "done", "count": 0}
        yield {"stage": "complete", "results": []}

    monkeypatch.setattr(book_import, "search_with_progress", fake_search_with_progress)

    resp = client.get("/api/import/search/stream?q=dune&type=title&mode=google_only")
    assert resp.status_code == 200
    assert observed_mode["value"] == "google_only"


def test_search_stream_endpoint_requires_query(client: TestClient):
    resp = client.get("/api/import/search/stream")
    assert resp.status_code == 422


# ── _best_google_books_cover() tests ─────────────────────────────────────────

class _FakeResponse:
    """Minimal fake for httpx responses used in cover-resolution tests."""

    def __init__(self, status_code: int = 200, headers: dict | None = None, body: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body or {}
        self.is_success = 200 <= status_code < 300

    def raise_for_status(self):
        if not self.is_success:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]

    def json(self) -> dict:
        return self._body


class _FakeClient:
    """Fake httpx.AsyncClient that returns pre-registered responses by URL."""

    def __init__(self, get_map: dict | None = None, head_map: dict | None = None):
        self._get = get_map or {}
        self._head = head_map or {}

    async def get(self, url: str, **_kwargs) -> _FakeResponse:
        resp = self._get.get(url)
        if resp is None:
            return _FakeResponse(404)
        return resp

    async def head(self, url: str, **_kwargs) -> _FakeResponse:
        resp = self._head.get(url)
        if resp is None:
            return _FakeResponse(404)
        return resp


_LARGE_URL = "https://books.google.com/large.jpg"
_MEDIUM_URL = "https://books.google.com/medium.jpg"
_THUMB_URL  = "https://books.google.com/thumbnail.jpg"

_VOLUME_ID = "vol123"
_VOLUME_URL = f"https://www.googleapis.com/books/v1/volumes/{_VOLUME_ID}"

_IMAGE_HEADERS = {"content-type": "image/jpeg", "content-length": "50000"}


@pytest.mark.anyio
async def test_best_cover_prefers_large_over_thumbnail():
    """When the volume record has a 'large' URL and it validates, use it."""
    volume_resp = _FakeResponse(200, body={
        "volumeInfo": {
            "imageLinks": {
                "large": _LARGE_URL,
                "thumbnail": _THUMB_URL,
            }
        }
    })
    fake_client = _FakeClient(
        get_map={_VOLUME_URL: volume_resp},
        head_map={
            _LARGE_URL: _FakeResponse(200, headers=_IMAGE_HEADERS),
        },
    )
    result = await book_import._best_google_books_cover(_VOLUME_ID, _THUMB_URL, fake_client)  # type: ignore[arg-type]
    assert result == _LARGE_URL


@pytest.mark.anyio
async def test_best_cover_falls_back_when_large_too_small():
    """If the large URL returns a tiny file (placeholder), fall back to medium."""
    volume_resp = _FakeResponse(200, body={
        "volumeInfo": {
            "imageLinks": {
                "large": _LARGE_URL,
                "medium": _MEDIUM_URL,
            }
        }
    })
    fake_client = _FakeClient(
        get_map={_VOLUME_URL: volume_resp},
        head_map={
            _LARGE_URL:  _FakeResponse(200, headers={"content-type": "image/jpeg", "content-length": "100"}),
            _MEDIUM_URL: _FakeResponse(200, headers=_IMAGE_HEADERS),
        },
    )
    result = await book_import._best_google_books_cover(_VOLUME_ID, _THUMB_URL, fake_client)  # type: ignore[arg-type]
    assert result == _MEDIUM_URL


@pytest.mark.anyio
async def test_best_cover_falls_back_when_large_not_image():
    """If the large URL returns non-image content-type (book page), skip it."""
    volume_resp = _FakeResponse(200, body={
        "volumeInfo": {
            "imageLinks": {
                "large": _LARGE_URL,
                "thumbnail": _THUMB_URL,
            }
        }
    })
    fake_client = _FakeClient(
        get_map={_VOLUME_URL: volume_resp},
        head_map={
            _LARGE_URL: _FakeResponse(200, headers={"content-type": "text/html", "content-length": "50000"}),
            _THUMB_URL: _FakeResponse(200, headers=_IMAGE_HEADERS),
        },
    )
    result = await book_import._best_google_books_cover(_VOLUME_ID, _THUMB_URL, fake_client)  # type: ignore[arg-type]
    assert result == _THUMB_URL


@pytest.mark.anyio
async def test_best_cover_uses_fallback_when_volume_fetch_fails():
    """If the volume GET fails, fall back to the search-result thumbnail."""
    fake_client = _FakeClient(
        get_map={},  # volume fetch → 404
        head_map={
            _THUMB_URL: _FakeResponse(200, headers=_IMAGE_HEADERS),
        },
    )
    result = await book_import._best_google_books_cover(_VOLUME_ID, _THUMB_URL, fake_client)  # type: ignore[arg-type]
    assert result == _THUMB_URL


@pytest.mark.anyio
async def test_best_cover_upgrades_http_to_https():
    """http:// URLs are upgraded to https:// before being returned."""
    http_thumb = "http://books.google.com/thumbnail.jpg"
    volume_resp = _FakeResponse(200, body={"volumeInfo": {"imageLinks": {}}})
    fake_client = _FakeClient(
        get_map={_VOLUME_URL: volume_resp},
        head_map={
            _THUMB_URL: _FakeResponse(200, headers=_IMAGE_HEADERS),  # https version
        },
    )
    result = await book_import._best_google_books_cover(_VOLUME_ID, http_thumb, fake_client)  # type: ignore[arg-type]
    assert result is not None
    assert result.startswith("https://")


@pytest.mark.anyio
async def test_best_cover_returns_none_when_no_candidates():
    """Returns None when no fallback is provided and volume fetch fails."""
    fake_client = _FakeClient()
    result = await book_import._best_google_books_cover(None, None, fake_client)  # type: ignore[arg-type]
    assert result is None


# ── import_book cover-download integration tests ───────────────────────────────

def test_import_book_downloads_cover_locally(client: TestClient, monkeypatch, tmp_path):
    """When download_cover succeeds, cover_url is set to the local /api/covers/ path."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))

    async def fake_download(url, covers_dir, http_client, user_id):
        return "abc123deadbeef.jpg"

    monkeypatch.setattr(import_router, "download_cover", fake_download)

    payload = {
        "candidate": {
            "title": "Dune",
            "isbn": "9780441013593",
            "cover_url": "https://covers.openlibrary.org/b/id/11481354-L.jpg",
            "source": "open_library",
        },
        "reading_status": "want_to_read",
    }
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 201
    assert resp.json()["cover_url"] == "/api/covers/abc123deadbeef.jpg"


def test_import_book_falls_back_to_external_url_on_cover_failure(client: TestClient, monkeypatch, tmp_path):
    """When download_cover returns None, the original external URL is preserved."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))

    async def fake_download(url, covers_dir, http_client, user_id):
        return None  # simulate download failure

    monkeypatch.setattr(import_router, "download_cover", fake_download)

    external_url = "https://covers.openlibrary.org/b/id/11481354-L.jpg"
    payload = {
        "candidate": {
            "title": "Foundation",
            "isbn": "9780553293357",
            "cover_url": external_url,
            "source": "open_library",
        },
        "reading_status": "want_to_read",
    }
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 201
    assert resp.json()["cover_url"] == external_url


def test_import_book_no_cover_url_skips_download(client: TestClient, monkeypatch, tmp_path):
    """When the candidate has no cover_url, download_cover is never called."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    called = []

    async def fake_download(url, covers_dir, http_client, user_id):
        called.append(url)
        return None

    monkeypatch.setattr(import_router, "download_cover", fake_download)

    payload = {
        "candidate": {
            "title": "No Cover Book",
            "source": "open_library",
        },
        "reading_status": "want_to_read",
    }
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 201
    assert resp.json()["cover_url"] is None
    assert called == [], "download_cover should not be called when cover_url is None"
