"""
Tests for the book import service and import API endpoints.

HTTP calls are intercepted with monkeypatch — no real network requests are made.
All test functions are modular (no classes).
"""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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

def test_map_open_library_fields() -> None:
    result = book_import.map_open_library(OPEN_LIBRARY_DUNE_DOC)
    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    assert result.isbn == "9780441013593"  # ISBN-13 preferred
    assert result.published_year == 1965
    assert result.page_count == 412
    assert result.language == "EN"
    assert result.publisher == "Ace Books"
    assert "Science Fiction" in result.tags
    assert result.cover_url == "https://covers.openlibrary.org/b/id/11481354-L.jpg"
    assert result.source == "open_library"


def test_map_open_library_missing_optional_fields() -> None:
    minimal = {"title": "Minimal Book"}
    result = book_import.map_open_library(minimal)
    assert result.title == "Minimal Book"
    assert result.author is None
    assert result.isbn is None
    assert result.cover_url is None
    assert result.language is None
    assert result.publisher is None
    assert result.tags is None
    assert result.source == "open_library"


def test_map_open_library_tags_capped_at_three() -> None:
    doc = {"title": "X", "subject": ["A", "B", "C", "D", "E"]}
    result = book_import.map_open_library(doc)
    assert result.tags == "A, B, C"


# ── map_google_books unit tests ───────────────────────────────────────────────

def test_map_google_books_fields() -> None:
    result = book_import.map_google_books(GOOGLE_BOOKS_FOUNDATION_ITEM)
    assert result.title == "Foundation"
    assert result.author == "Isaac Asimov"
    assert result.isbn == "9780553293357"  # ISBN-13 preferred
    assert result.publisher == "Bantam Books"
    assert result.published_year == 1991
    assert result.page_count == 255
    assert result.language == "EN"
    assert result.tags == "Science Fiction"
    assert result.cover_url == "https://books.google.com/thumbnail.jpg"  # https upgraded
    assert result.source == "google_books"


def test_map_google_books_missing_optional_fields() -> None:
    minimal = {"volumeInfo": {"title": "Minimal"}}
    result = book_import.map_google_books(minimal)
    assert result.title == "Minimal"
    assert result.author is None
    assert result.isbn is None
    assert result.cover_url is None
    assert result.language is None
    assert result.published_year is None
    assert result.source == "google_books"


def test_normalize_language_code_converts_iso_639_2_to_iso_639_1() -> None:
    assert book_import._normalize_language_code("eng") == "EN"
    assert book_import._normalize_language_code("fra") == "FR"


def test_normalize_language_code_keeps_iso_639_1_uppercase() -> None:
    assert book_import._normalize_language_code("en") == "EN"
    assert book_import._normalize_language_code(" De ") == "DE"


def test_normalize_language_code_rejects_invalid_values() -> None:
    assert book_import._normalize_language_code(None) is None
    assert book_import._normalize_language_code("") is None
    assert book_import._normalize_language_code("123") is None
    assert book_import._normalize_language_code("english") is None
    assert book_import._normalize_language_code("zzz") is None


def test_map_google_books_prefers_isbn13_over_isbn10() -> None:
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


def test_map_google_books_published_year_partial_date() -> None:
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
async def test_search_returns_open_library_results(monkeypatch: MonkeyPatch, fake_ol_result: list[BookImportCandidate]) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return fake_ol_result

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)

    results = await book_import.search("dune", "title")
    assert len(results) == 1
    assert results[0].title == "Dune"
    assert results[0].source == "open_library"


@pytest.mark.anyio
async def test_search_falls_back_to_google_books_when_ol_empty(monkeypatch: MonkeyPatch, fake_gb_result: list[BookImportCandidate]) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return []

    async def fake_gb(query: str, search_type: str, api_key: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return fake_gb_result

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_google_books", fake_gb)

    # api_key must be non-empty — the real API requires a key and the guard
    # skips the fallback when none is configured.
    results = await book_import.search("foundation", "title", api_key="test-key")
    assert len(results) == 1
    assert results[0].source == "google_books"


@pytest.mark.anyio
async def test_search_returns_empty_when_both_fail(monkeypatch: MonkeyPatch) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return []

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)

    results = await book_import.search("unknownxyz", "title")
    assert results == []


# ── map_hardcover unit tests ──────────────────────────────────────────────────

HARDCOVER_EDITION = {
    "title": "Dune",
    "subtitle": None,
    "isbn_13": "9780441013593",
    "pages": 412,
    "release_date": "1965-08-01",
    "image": {"url": "https://assets.hardcover.app/editions/123/cover.jpg"},
    "publisher": {"name": "Ace Books"},
    "language": {"code2": "en"},
    "book": {
        "description": "A science fiction novel.",
        "taggings": [
            {"tag": {"tag": "Science Fiction"}},
            {"tag": {"tag": "Ecology"}},
        ],
    },
    "contributions": [
        {"author": {"name": "Frank Herbert"}},
    ],
}


def test_map_hardcover_fields() -> None:
    result = book_import.map_hardcover(HARDCOVER_EDITION)
    assert result is not None
    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    assert result.isbn == "9780441013593"
    assert result.published_year == 1965
    assert result.page_count == 412
    assert result.language == "EN"
    assert result.publisher == "Ace Books"
    assert result.tags == "Science Fiction, Ecology"
    assert result.cover_url == "https://assets.hardcover.app/editions/123/cover.jpg"
    assert result.blurb == "A science fiction novel."
    assert result.source == "hardcover"


def test_map_hardcover_missing_title() -> None:
    result = book_import.map_hardcover({"title": ""})
    assert result is None


def test_map_hardcover_missing_optional() -> None:
    minimal = {"title": "Minimal"}
    result = book_import.map_hardcover(minimal)
    assert result is not None
    assert result.title == "Minimal"
    assert result.author is None
    assert result.isbn is None
    assert result.cover_url is None
    assert result.publisher is None
    assert result.published_year is None
    assert result.page_count is None
    assert result.language is None
    assert result.tags is None
    assert result.blurb is None


def test_map_hardcover_tags_capped() -> None:
    edition = {"title": "X", "book": {"taggings": [
        {"tag": {"tag": "A"}}, {"tag": {"tag": "B"}},
        {"tag": {"tag": "C"}}, {"tag": {"tag": "D"}},
    ]}}
    result = book_import.map_hardcover(edition)
    assert result is not None
    assert result.tags == "A, B, C"


def test_map_hardcover_language_uppercased() -> None:
    edition = {"title": "X", "language": {"code2": "de"}}
    result = book_import.map_hardcover(edition)
    assert result is not None
    assert result.language == "DE"


# ── _merge_and_deduplicate unit tests ────────────────────────────────────────

def _make_candidate(title: str, isbn: str | None = None, pages: int | None = None, lang: str | None = None) -> BookImportCandidate:
    """Create a BookImportCandidate with default values for reuse in dedup tests."""
    return BookImportCandidate(
        title=title,
        author="Author",
        isbn=isbn,
        page_count=pages,
        language=lang,
        source="open_library",
    )


def test_merge_and_dedup_same_isbn_pages_lang() -> None:
    a = _make_candidate("Dune", "9780441013593", 412, "EN")
    b = _make_candidate("Dune", "9780441013593", 412, "EN")
    result = book_import._merge_and_deduplicate([a], [b])
    assert len(result) == 1
    assert result[0].title == "Dune"


def test_merge_and_dedup_same_isbn_diff_pages() -> None:
    a = _make_candidate("Dune", "9780441013593", 412, "EN")
    b = _make_candidate("Dune HC", "9780441013593", 688, "EN")
    result = book_import._merge_and_deduplicate([a], [b])
    assert len(result) == 2


def test_merge_and_dedup_same_isbn_diff_lang() -> None:
    a = _make_candidate("Dune", "9780441013593", 412, "EN")
    b = _make_candidate("Dune DE", "9780441013593", 412, "DE")
    result = book_import._merge_and_deduplicate([a], [b])
    assert len(result) == 2


def test_merge_and_dedup_ol_first_order() -> None:
    ol = _make_candidate("OL Book", "9781111111111", 200, "EN")
    hc = _make_candidate("HC Book", "9782222222222", 300, "DE")
    result = book_import._merge_and_deduplicate([ol], [hc])
    assert len(result) == 2
    assert result[0].title == "OL Book"
    assert result[1].title == "HC Book"


def test_merge_and_dedup_prefers_candidate_with_cover() -> None:
    a = _make_candidate("No Cover", "9780441013593", 412, "EN")
    b = _make_candidate("Has Cover", "9780441013593", 412, "EN")
    b.cover_url = "https://example.com/cover.jpg"
    result = book_import._merge_and_deduplicate([a], [b])
    assert len(result) == 1
    assert result[0].title == "Has Cover"


def test_merge_and_dedup_prefers_cover_when_primary_missing_cover() -> None:
    a = _make_candidate("OL No Cover", "9780441013593", 412, "EN")
    b = _make_candidate("HC Has Cover", "9780441013593", 412, "EN")
    b.cover_url = "https://example.com/cover.jpg"
    result = book_import._merge_and_deduplicate([a], [b])
    assert len(result) == 1
    assert result[0].title == "HC Has Cover"


def test_merge_and_dedup_keeps_primary_cover_when_both_have_cover() -> None:
    a = _make_candidate("OL Cover", "9780441013593", 412, "EN")
    a.cover_url = "https://ol-cover.jpg"
    b = _make_candidate("HC Cover", "9780441013593", 412, "EN")
    b.cover_url = "https://hc-cover.jpg"
    result = book_import._merge_and_deduplicate([a], [b])
    assert len(result) == 1
    assert result[0].title == "OL Cover"


# ── _hardcover_dedup_key tests ───────────────────────────────────────────────

def test_hardcover_dedup_key() -> None:
    edition = {"isbn_13": "9780441013593", "pages": 412, "language": {"code2": "en"}}
    key = book_import._hardcover_dedup_key(edition)
    assert key == ("9780441013593", 412, "en")


def test_hardcover_dedup_key_no_isbn() -> None:
    key = book_import._hardcover_dedup_key({"pages": 412})
    assert key is None


# ── search() with hardcover ──────────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_runs_hardcover_in_parallel(monkeypatch: MonkeyPatch) -> None:
    ol_called = False
    hc_called = False

    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        nonlocal ol_called
        ol_called = True
        return [book_import.map_open_library(OPEN_LIBRARY_DUNE_DOC)]

    async def fake_hc(query: str, search_type: str, api_token: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        nonlocal hc_called
        hc_called = True
        return []

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_hardcover", fake_hc)

    results = await book_import.search("dune", "title", hardcover_api_token="test-token")
    assert ol_called
    assert hc_called
    assert len(results) == 1


@pytest.mark.anyio
async def test_search_merges_ol_and_hc_results(monkeypatch: MonkeyPatch) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return [_make_candidate("OL Book", "9781111111111", 200, "EN")]

    async def fake_hc(query: str, search_type: str, api_token: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return [_make_candidate("HC Book", "9782222222222", 300, "DE")]

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_hardcover", fake_hc)

    results = await book_import.search("test", "title", hardcover_api_token="token")
    assert len(results) == 2
    assert results[0].title == "OL Book"
    assert results[1].title == "HC Book"


@pytest.mark.anyio
async def test_search_hardcover_skipped_without_token(monkeypatch: MonkeyPatch) -> None:
    hc_called = False

    async def fake_hc(query: str, search_type: str, api_token: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:  # pragma: no cover
        nonlocal hc_called
        hc_called = True
        return []

    monkeypatch.setattr(book_import, "_search_hardcover", fake_hc)

    await book_import.search("dune", "title")
    assert not hc_called


# ── search_with_progress() with hardcover ────────────────────────────────────

@pytest.mark.anyio
async def test_search_with_progress_runs_hc_in_parallel(monkeypatch: MonkeyPatch, fake_ol_result: list[BookImportCandidate]) -> None:
    hc_called = False

    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return fake_ol_result

    async def fake_hc(query: str, search_type: str, api_token: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        nonlocal hc_called
        hc_called = True
        return []

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_hardcover", fake_hc)

    events = []
    async for event in book_import.search_with_progress("dune", "title", hardcover_api_token="token"):
        events.append(event)

    stages = [(e["stage"], e.get("status")) for e in events if e["stage"] != "complete"]
    assert ("open_library", "done") in stages
    assert ("hardcover", "done") in stages
    assert hc_called


@pytest.mark.anyio
async def test_search_with_progress_hc_skipped_no_token(monkeypatch: MonkeyPatch, fake_ol_result: list[BookImportCandidate]) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return fake_ol_result

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)

    events = []
    async for event in book_import.search_with_progress("dune", "title"):
        events.append(event)

    stages = [(e["stage"], e.get("status")) for e in events if e["stage"] != "complete"]
    assert ("hardcover", "skipped") in stages


@pytest.mark.anyio
async def test_search_with_progress_hc_error_graceful(monkeypatch: MonkeyPatch) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return []

    async def fake_hc(query: str, search_type: str, api_token: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        raise RuntimeError("API down")

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_hardcover", fake_hc)

    events = []
    async for event in book_import.search_with_progress("test", "title", hardcover_api_token="token"):
        events.append(event)

    stages_by_stage = {e["stage"]: e for e in events if "stage" in e and e["stage"] != "complete"}
    assert stages_by_stage["hardcover"]["status"] == "error"


# ── _search_hardcover ISBN path tests ──────────────────────────────────────

@pytest.mark.anyio
async def test_search_hardcover_isbn_path(monkeypatch: MonkeyPatch) -> None:
    called_with: dict[str, list[str]] = {}

    async def fake_hc_fetch(isbns: list[str], token: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        called_with["isbns"] = isbns
        return [BookImportCandidate(title="Dune", isbn="9780441013593", source="hardcover")]

    monkeypatch.setattr(book_import, "_hardcover_fetch_books", fake_hc_fetch)

    async with httpx.AsyncClient() as client:
        results = await book_import._search_hardcover("9780441013593", "isbn", "token", client)

    assert called_with.get("isbns") == ["9780441013593"]
    assert len(results) == 1
    assert results[0].isbn == "9780441013593"


@pytest.mark.anyio
async def test_search_hardcover_isbn_invalid(monkeypatch: MonkeyPatch) -> None:
    called = False

    async def fake_hc_fetch(isbns: list[str], token: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:  # pragma: no cover
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(book_import, "_hardcover_fetch_books", fake_hc_fetch)

    async with httpx.AsyncClient() as client:
        results = await book_import._search_hardcover("not-an-isbn", "isbn", "token", client)

    assert results == []
    assert not called


@pytest.mark.anyio
async def test_search_hardcover_isbn_not_found(monkeypatch: MonkeyPatch) -> None:
    async def fake_hc_fetch(isbns: list[str], token: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return []

    monkeypatch.setattr(book_import, "_hardcover_fetch_books", fake_hc_fetch)

    async with httpx.AsyncClient() as client:
        results = await book_import._search_hardcover("9780000000000", "isbn", "token", client)

    assert results == []


# ── search() with hardcover exception handling ──────────────────────────────

@pytest.mark.anyio
async def test_search_hardcover_exception_ol_still_works(monkeypatch: MonkeyPatch, fake_ol_result: list[BookImportCandidate]) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return fake_ol_result

    async def fake_hc_exc(query: str, search_type: str, api_token: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        raise RuntimeError("HC temporary failure")

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)
    monkeypatch.setattr(book_import, "_search_hardcover", fake_hc_exc)

    results = await book_import.search("dune", "title", hardcover_api_token="token")
    assert len(results) == 1
    assert results[0].source == "open_library"
    assert results[0].title == "Dune"


# ── Import API endpoint tests ─────────────────────────────────────────────────

def test_import_search_endpoint(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    async def fake_search(query: str, search_type: str, *, api_key: str | None, hardcover_api_token: str | None, http_client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return [book_import.map_open_library(OPEN_LIBRARY_DUNE_DOC)]

    monkeypatch.setattr(book_import, "search", fake_search)

    resp = client.get("/api/import/search?q=dune&type=title")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Dune"
    assert data[0]["source"] == "open_library"


def test_import_search_requires_query(client: TestClient) -> None:
    resp = client.get("/api/import/search")
    assert resp.status_code == 422


def test_import_book_creates_entry(client: TestClient) -> None:
    payload = {
        "candidate": {
            "title": "Dune",
            "author": "Frank Herbert",
            "isbn": "9780441013593",
            "cover_url": "https://covers.openlibrary.org/b/id/11481354-M.jpg",
            "publisher": "Ace Books",
            "published_year": 1965,
            "page_count": 412,
            "language": "EN",
            "tags": "Science Fiction",
            "source": "open_library",
        },
        "reading_status": "want_to_read",
    }
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Dune"
    assert data["isbn"] == "9780441013593"
    assert data["language"] == "EN"
    assert data["reading_status"] == "want_to_read"
    assert data["id"] is not None


def test_import_book_duplicate_isbn_returns_409(client: TestClient) -> None:
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


def test_import_book_without_isbn_allows_duplicates(client: TestClient) -> None:
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


def test_import_book_with_reading_status(client: TestClient) -> None:
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
async def test_search_with_progress_open_library_success(monkeypatch: MonkeyPatch, fake_ol_result: list[BookImportCandidate]) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return fake_ol_result

    monkeypatch.setattr(book_import, "_search_open_library", fake_ol)

    events = []
    async for event in book_import.search_with_progress("dune", "title"):
        events.append(event)

    stages = [(e["stage"], e.get("status")) for e in events]
    assert ("open_library", "searching") in stages
    assert ("open_library", "done") in stages
    assert ("hardcover", "skipped") in stages
    complete = next(e for e in events if e.get("stage") == "complete")
    assert len(complete["results"]) == 1
    assert complete["results"][0]["title"] == "Dune"
    # Google Books events should NOT be present
    assert not any(e.get("stage") == "google_books" for e in events)


@pytest.mark.anyio
async def test_search_with_progress_falls_back_to_google(monkeypatch: MonkeyPatch, fake_gb_result: list[BookImportCandidate]) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        return []

    async def fake_gb(query: str, search_type: str, api_key: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
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
async def test_search_with_progress_skips_google_without_key(monkeypatch: MonkeyPatch) -> None:
    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
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
async def test_search_with_progress_google_only_runs_google(monkeypatch: MonkeyPatch, fake_gb_result: list[BookImportCandidate]) -> None:
    calls: dict[str, int] = {"ol": 0, "gb": 0}

    async def fake_ol(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:  # pragma: no cover
        calls["ol"] += 1
        return []

    async def fake_gb(query: str, search_type: str, api_key: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
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
async def test_search_with_progress_google_only_without_key_skips(monkeypatch: MonkeyPatch) -> None:
    calls: dict[str, int] = {"gb": 0}

    async def fake_gb(query: str, search_type: str, api_key: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:  # pragma: no cover
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
    events: list[dict] = []
    for line in text.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload:
                events.append(_json.loads(payload))
    return events


def test_search_stream_endpoint(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    observed_mode: dict[str, str | None] = {"value": None}

    async def fake_search_with_progress(query: str, search_type: str, *, api_key: str | None, hardcover_api_token: str | None, mode: str, http_client: httpx.AsyncClient) -> AsyncIterator[dict]:
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


def test_search_stream_endpoint_forwards_google_only_mode(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    observed_mode: dict[str, str | None] = {"value": None}

    async def fake_search_with_progress(query: str, search_type: str, *, api_key: str | None, hardcover_api_token: str | None, mode: str, http_client: httpx.AsyncClient) -> AsyncIterator[dict]:
        observed_mode["value"] = mode
        yield {"stage": "google_books", "status": "searching"}
        yield {"stage": "google_books", "status": "done", "count": 0}
        yield {"stage": "complete", "results": []}

    monkeypatch.setattr(book_import, "search_with_progress", fake_search_with_progress)

    resp = client.get("/api/import/search/stream?q=dune&type=title&mode=google_only")
    assert resp.status_code == 200
    assert observed_mode["value"] == "google_only"


def test_search_stream_endpoint_requires_query(client: TestClient) -> None:
    resp = client.get("/api/import/search/stream")
    assert resp.status_code == 422


# ── _best_google_books_cover() tests ─────────────────────────────────────────

class _FakeResponse:
    """Minimal fake for httpx responses used in cover-resolution tests."""

    def __init__(self, status_code: int = 200, headers: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> None:
        self.status_code: int = status_code
        self.headers: dict[str, str] = headers or {}
        self._body: dict[str, Any] = body or {}
        self.is_success: bool = 200 <= status_code < 300

    def raise_for_status(self) -> None:
        if not self.is_success:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]

    def json(self) -> dict[str, Any]:
        return self._body


class _FakeClient:
    """Fake httpx.AsyncClient that returns pre-registered responses by URL."""

    def __init__(self, get_map: dict[str, _FakeResponse] | None = None, head_map: dict[str, _FakeResponse] | None = None) -> None:
        self._get: dict[str, _FakeResponse] = get_map or {}
        self._head: dict[str, _FakeResponse] = head_map or {}

    async def get(self, url: str, **_kwargs: Any) -> _FakeResponse:
        resp = self._get.get(url)
        if resp is None:
            return _FakeResponse(404)
        return resp

    async def head(self, url: str, **_kwargs: Any) -> _FakeResponse:
        resp = self._head.get(url)
        if resp is None:
            return _FakeResponse(404)  # pragma: no cover
        return resp


_LARGE_URL = "https://books.google.com/large.jpg"
_MEDIUM_URL = "https://books.google.com/medium.jpg"
_THUMB_URL  = "https://books.google.com/thumbnail.jpg"

_VOLUME_ID = "vol123"
_VOLUME_URL = f"https://www.googleapis.com/books/v1/volumes/{_VOLUME_ID}"

_IMAGE_HEADERS = {"content-type": "image/jpeg", "content-length": "50000"}


@pytest.mark.anyio
async def test_best_cover_prefers_large_over_thumbnail() -> None:
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
async def test_best_cover_falls_back_when_large_too_small() -> None:
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
async def test_best_cover_falls_back_when_large_not_image() -> None:
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
async def test_best_cover_uses_fallback_when_volume_fetch_fails() -> None:
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
async def test_best_cover_upgrades_http_to_https() -> None:
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
async def test_best_cover_returns_none_when_no_candidates() -> None:
    """Returns None when no fallback is provided and volume fetch fails."""
    fake_client = _FakeClient()
    result = await book_import._best_google_books_cover(None, None, fake_client)  # type: ignore[arg-type]
    assert result is None


# ── import_book cover-download integration tests ───────────────────────────────

def test_import_book_downloads_cover_locally(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """When download_cover succeeds, cover_url is set to the local /api/covers/ path."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))

    async def fake_download(url: str, covers_dir: str, http_client: httpx.AsyncClient, user_id: int | None) -> str | None:
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


def test_import_book_cover_failure_skips_cover(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """When download_cover returns None, the imported book stores no cover URL."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))

    async def fake_download(url: str, covers_dir: str, http_client: httpx.AsyncClient, user_id: int | None) -> str | None:
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
    assert resp.json()["cover_url"] is None


def test_import_book_no_cover_url_skips_download(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """When the candidate has no cover_url, download_cover is never called."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))
    called: list[str] = []

    async def fake_download(url: str, covers_dir: str, http_client: httpx.AsyncClient, user_id: int | None) -> str | None:  # pragma: no cover
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


# ── import router unit tests for uncovered lines ───────────────────────────────

def test_normalize_language_empty_string() -> None:
    """Whitespace-only language should be treated as None."""
    assert import_router._normalize_language("   ") is None


def test_normalize_language_invalid_code() -> None:
    """Non-alpha or non-2-char language should raise 422."""
    with pytest.raises(HTTPException) as exc_info:
        import_router._normalize_language("english")
    assert exc_info.value.status_code == 422
    assert "Language must be a 2-letter ISO code" in exc_info.value.detail


def test_raise_integrity_conflict_isbn_unique() -> None:
    """ISBN unique constraint violation should raise 409."""
    exc = IntegrityError("insert", "params", Exception("UNIQUE constraint failed: book.isbn"))
    with pytest.raises(HTTPException) as exc_info:
        import_router._raise_integrity_conflict(exc)
    assert exc_info.value.status_code == 409
    assert "This ISBN is already used by another book." in exc_info.value.detail


def test_raise_integrity_conflict_other() -> None:
    """Non-ISBN integrity error should be re-raised."""
    exc = IntegrityError("insert", "params", Exception("FOREIGN KEY constraint failed"))
    with pytest.raises(IntegrityError):
        try:
            raise exc
        except IntegrityError:
            import_router._raise_integrity_conflict(exc)


def test_import_book_flush_integrity_error(client: TestClient, session: Session, monkeypatch: MonkeyPatch) -> None:
    from sqlalchemy.exc import IntegrityError

    flush_count: list[int] = [0]
    original_flush = session.flush

    def fake_flush(*args: Any, **kwargs: Any) -> None:
        flush_count[0] += 1
        if flush_count[0] == 6:
            raise IntegrityError("insert", "params", Exception("UNIQUE constraint failed: book.isbn"))
        original_flush(*args, **kwargs)

    monkeypatch.setattr(session, "flush", fake_flush)

    payload = {
        "candidate": {
            "title": "Dune",
            "isbn": "9780441013593",
            "source": "open_library",
        },
        "reading_status": "want_to_read",
    }
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 409
    assert "This ISBN is already used by another book." in resp.json()["detail"]


def test_import_book_commit_integrity_error(client: TestClient, session: Session, monkeypatch: MonkeyPatch) -> None:
    from sqlalchemy.exc import IntegrityError

    call_count: list[int] = [0]
    original_commit = session.commit

    def fake_commit() -> None:
        call_count[0] += 1
        if call_count[0] == 2:
            raise IntegrityError("insert", "params", Exception("UNIQUE constraint failed: book.isbn"))
        original_commit()

    monkeypatch.setattr(session, "commit", fake_commit)

    payload = {
        "candidate": {
            "title": "Dune",
            "isbn": "9780441013593",
            "source": "open_library",
        },
        "reading_status": "want_to_read",
    }
    resp = client.post("/api/import", json=payload)
    assert resp.status_code == 409
    assert "This ISBN is already used by another book." in resp.json()["detail"]
