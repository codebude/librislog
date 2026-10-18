"""Unit tests for app.services.book_import module."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.schemas import BookImportCandidate
from app.services import book_import as bi


@pytest.fixture(autouse=True)
def _all_sources_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn every import source on for this module.

    The orchestration tests here assert on which sources run, not on the shipped
    defaults, which are covered in test_main.py. Enabling them explicitly also keeps
    the suite independent of whatever the developer's .env happens to contain.
    """
    for spec in bi._build_sources(""):
        monkeypatch.setattr(bi.settings, f"{spec.stage}_import_search_enabled", True)
    # Google Books is the fallback, not a registry entry.
    monkeypatch.setattr(bi.settings, "google_books_import_search_enabled", True)


# ── SourceBackendError ─────────────────────────────────────────────────────────

def test_source_backend_error_with_status() -> None:
    exc = bi.SourceBackendError("open_library", 503)
    assert exc.source == "open_library"
    assert exc.status_code == 503
    assert "open_library backend error" in str(exc)


def test_source_backend_error_without_status() -> None:
    exc = bi.SourceBackendError("google_books")
    assert exc.status_code is None


# ── _truncate_api_key ──────────────────────────────────────────────────────────

def test_truncate_api_key_empty() -> None:
    assert bi._truncate_api_key("") == "<empty>"
    assert bi._truncate_api_key(None) == "<empty>"  # ty: ignore[invalid-argument-type]


def test_truncate_api_key_short() -> None:
    assert bi._truncate_api_key("abcd") == "ab...cd"


def test_truncate_api_key_long() -> None:
    assert bi._truncate_api_key("1234567890abcdef") == "1234...cdef"


# ── search_with_progress ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_with_progress_google_only_no_key() -> None:
    events = []
    async for e in bi.search_with_progress("query", "title", mode="google_only"):
        events.append(e)
    assert any(e.get("stage") == "google_books" and e.get("status") == "skipped" for e in events)


@pytest.mark.anyio
async def test_search_with_progress_google_only_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_candidate = BookImportCandidate(title="Book", source="google_books")
    monkeypatch.setattr(bi, "_search_google_books", AsyncMock(return_value=[fake_candidate]))

    events = []
    async for e in bi.search_with_progress("query", "title", api_key="key", mode="google_only"):
        events.append(e)
    assert any(e.get("stage") == "google_books" and e.get("status") == "done" for e in events)
    complete = [e for e in events if e.get("stage") == "complete"][0]
    assert len(complete["results"]) == 1


@pytest.mark.anyio
async def test_search_with_progress_google_only_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bi, "_search_google_books",
        AsyncMock(side_effect=bi.SourceBackendError("google_books", 500)),
    )

    events = []
    async for e in bi.search_with_progress("query", "title", api_key="key", mode="google_only"):
        events.append(e)
    assert any(e.get("stage") == "google_books" and e.get("status") == "error" for e in events)


@pytest.mark.anyio
async def test_search_with_progress_auto_ol_and_hc(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ol = BookImportCandidate(title="OL Book", source="open_library")
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[fake_ol]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    events = []
    async for e in bi.search_with_progress("query", "title", hardcover_api_token="token"):
        events.append(e)
    assert any(e.get("stage") == "open_library" and e.get("status") == "searching" for e in events)
    assert any(e.get("stage") == "hardcover" and e.get("status") == "searching" for e in events)
    assert any(e.get("stage") == "open_library" and e.get("status") == "done" for e in events)


@pytest.mark.anyio
async def test_search_with_progress_auto_hc_skipped_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))
    events = []
    async for e in bi.search_with_progress("query", "title"):
        events.append(e)
    assert any(e.get("stage") == "hardcover" and e.get("status") == "skipped" for e in events)
    # A skipped source must be reported exactly once: never also as a result count.
    hardcover = [e for e in events if e.get("stage") == "hardcover"]
    assert len(hardcover) == 1


@pytest.mark.anyio
async def test_search_with_progress_auto_fallback_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))
    fake_gb = BookImportCandidate(title="GB Book", source="google_books")
    monkeypatch.setattr(bi, "_search_google_books", AsyncMock(return_value=[fake_gb]))

    events = []
    async for e in bi.search_with_progress("query", "title", api_key="key"):
        events.append(e)
    assert any(e.get("stage") == "google_books" and e.get("status") == "done" for e in events)
    complete = [e for e in events if e.get("stage") == "complete"][0]
    assert len(complete["results"]) == 1


@pytest.mark.anyio
async def test_search_with_progress_auto_fallback_google_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        bi, "_search_google_books",
        AsyncMock(side_effect=bi.SourceBackendError("google_books", 500)),
    )

    events = []
    async for e in bi.search_with_progress("query", "title", api_key="key"):
        events.append(e)
    assert any(e.get("stage") == "google_books" and e.get("status") == "error" for e in events)


@pytest.mark.anyio
async def test_search_with_progress_general_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    events = []
    async for e in bi.search_with_progress("query", "title"):
        events.append(e)
    assert any(e.get("stage") == "open_library" and e.get("status") == "error" for e in events)


# ── search ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_ol_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bi, "_search_open_library",
        AsyncMock(side_effect=bi.SourceBackendError("open_library", 503)),
    )
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    results = await bi.search("query", "title")
    assert results == []


@pytest.mark.anyio
async def test_search_ol_generic_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bi, "_search_open_library",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    results = await bi.search("query", "title")
    assert results == []


@pytest.mark.anyio
async def test_search_ol_generic_exception_with_hc(monkeypatch: pytest.MonkeyPatch) -> None:
    """OL throws generic exception while HC succeeds — covers line 253."""
    monkeypatch.setattr(
        bi, "_search_open_library",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    fake_hc = BookImportCandidate(title="HC Book", source="hardcover")
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[fake_hc]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    results = await bi.search("query", "title", hardcover_api_token="token")
    assert len(results) == 1


@pytest.mark.anyio
async def test_search_hc_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        bi, "_search_hardcover",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    results = await bi.search("query", "title", hardcover_api_token="token")
    assert results == []


@pytest.mark.anyio
async def test_search_fallback_google_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    results = await bi.search("query", "title")
    assert results == []


@pytest.mark.anyio
async def test_search_fallback_google_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))
    fake = BookImportCandidate(title="Book", source="google_books")
    monkeypatch.setattr(bi, "_search_google_books", AsyncMock(return_value=[fake]))

    results = await bi.search("query", "title", api_key="key")
    assert len(results) == 1


@pytest.mark.anyio
async def test_search_fallback_google_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        bi, "_search_google_books",
        AsyncMock(side_effect=bi.SourceBackendError("google_books", 500)),
    )

    results = await bi.search("query", "title", api_key="key")
    assert results == []


# ── _search_open_library ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_open_library_isbn(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "docs": [{"title": "Book", "isbn": ["9781234567897"]}]
    }
    fake_client = AsyncMock()
    fake_client.get.return_value = fake_resp

    results = await bi._search_open_library("9781234567897", "isbn", fake_client)
    assert len(results) == 1
    assert results[0].title == "Book"


@pytest.mark.anyio
async def test_search_open_library_http_status_error() -> None:
    fake_resp = MagicMock()
    fake_resp.status_code = 503
    fake_resp.text = "error"
    exc = httpx.HTTPStatusError("err", request=MagicMock(), response=fake_resp)
    fake_client = AsyncMock()
    fake_client.get.side_effect = exc

    with pytest.raises(bi.SourceBackendError) as exc_info:
        await bi._search_open_library("query", "title", fake_client)
    assert exc_info.value.status_code == 503


@pytest.mark.anyio
async def test_search_open_library_http_error() -> None:
    fake_client = AsyncMock()
    fake_client.get.side_effect = httpx.ConnectError("failed")

    with pytest.raises(bi.SourceBackendError) as exc_info:
        await bi._search_open_library("query", "title", fake_client)
    assert exc_info.value.status_code is None


# ── map_open_library ───────────────────────────────────────────────────────────

def test_map_open_library_full() -> None:
    doc = {
        "title": "Book",
        "author_name": ["Author"],
        "isbn": ["9781234567897"],
        "publisher": ["Pub"],
        "first_publish_year": 2024,
        "number_of_pages_median": 300,
        "subject": ["Fiction", "Sci-Fi"],
        "cover_i": 12345,
        "language": ["eng"],
    }
    c = bi.map_open_library(doc)
    assert c.title == "Book"
    assert c.author == "Author"
    assert c.isbn == "9781234567897"
    assert c.publisher == "Pub"
    assert c.published_year == 2024
    assert c.page_count == 300
    assert c.language == "EN"
    assert c.tags == "Fiction, Sci-Fi"
    assert c.cover_url is not None
    assert c.source == "open_library"


def test_map_open_library_minimal() -> None:
    doc = {"title": "Book"}
    c = bi.map_open_library(doc)
    assert c.title == "Book"
    assert c.author is None
    assert c.isbn is None
    assert c.cover_url is None


# ── _search_google_books ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_google_books_retry_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = []
    for i in range(2):
        resp = MagicMock()
        resp.status_code = 429
        resp.content = b""
        resp.is_success = False
        responses.append(resp)
    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.content = b'{"items": []}'
    success_resp.is_success = True
    success_resp.json.return_value = {"items": []}
    responses.append(success_resp)

    fake_client = AsyncMock()
    fake_client.get.side_effect = responses

    # Patch asyncio.sleep to avoid actual delays
    monkeypatch.setattr(bi.asyncio, "sleep", AsyncMock())

    results = await bi._search_google_books("query", "title", "key", fake_client)
    assert results == []
    assert fake_client.get.call_count == 3


@pytest.mark.anyio
async def test_search_google_books_max_retries_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = []
    for _ in range(4):
        resp = MagicMock()
        resp.status_code = 503
        resp.content = b""
        resp.is_success = False
        responses.append(resp)

    fake_client = AsyncMock()
    fake_client.get.side_effect = responses
    monkeypatch.setattr(bi.asyncio, "sleep", AsyncMock())

    with pytest.raises(bi.SourceBackendError):
        await bi._search_google_books("query", "title", "key", fake_client)


@pytest.mark.anyio
async def test_search_google_books_non_retryable_error() -> None:
    resp = MagicMock()
    resp.status_code = 400
    resp.content = b"bad request"
    resp.is_success = False
    resp.text = "bad request"

    fake_client = AsyncMock()
    fake_client.get.return_value = resp

    with pytest.raises(bi.SourceBackendError) as exc_info:
        await bi._search_google_books("query", "title", "key", fake_client)
    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_search_google_books_request_error() -> None:
    fake_client = AsyncMock()
    fake_client.get.side_effect = httpx.ConnectError("failed")

    with pytest.raises(bi.SourceBackendError):
        await bi._search_google_books("query", "title", "key", fake_client)


@pytest.mark.anyio
async def test_search_google_books_error_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b'{}'
    resp.is_success = True
    resp.json.return_value = {"error": {"message": "quota exceeded"}}

    fake_client = AsyncMock()
    fake_client.get.return_value = resp

    results = await bi._search_google_books("query", "title", "key", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_search_google_books_with_cover_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b'{}'
    resp.is_success = True
    resp.json.return_value = {
        "items": [
            {"id": "vol1", "volumeInfo": {"title": "Book", "imageLinks": {"thumbnail": "http://example.com/t.jpg"}}}
        ]
    }

    fake_client = AsyncMock()
    fake_client.get.return_value = resp

    async def _fake_best_cover(item_id: str | None, fallback: str | None, client: AsyncMock) -> str:
        """Mock cover resolution returning a fixed URL."""
        return "https://example.com/cover.jpg"

    monkeypatch.setattr(bi, "_best_google_books_cover", _fake_best_cover)

    results = await bi._search_google_books("query", "title", "key", fake_client)
    assert len(results) == 1
    assert results[0].cover_url == "https://example.com/cover.jpg"


# ── _best_google_books_cover ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_best_google_books_cover_head_success() -> None:
    fake_client = AsyncMock()

    vol_resp = MagicMock()
    vol_resp.status_code = 200
    vol_resp.json.return_value = {
        "volumeInfo": {"imageLinks": {"large": "http://example.com/large.jpg"}}
    }

    head_resp = MagicMock()
    head_resp.status_code = 200
    head_resp.headers = {"content-type": "image/jpeg", "content-length": "5000"}

    fake_client.get.return_value = vol_resp
    fake_client.head.return_value = head_resp

    result = await bi._best_google_books_cover("id", "http://example.com/fallback.jpg", fake_client)
    assert result == "https://example.com/large.jpg"


@pytest.mark.anyio
async def test_best_google_books_cover_head_non_image() -> None:
    fake_client = AsyncMock()

    vol_resp = MagicMock()
    vol_resp.status_code = 200
    vol_resp.json.return_value = {
        "volumeInfo": {"imageLinks": {"large": "http://example.com/large.jpg"}}
    }

    head_resp = MagicMock()
    head_resp.status_code = 200
    head_resp.headers = {"content-type": "text/html", "content-length": "5000"}

    fake_client.get.return_value = vol_resp
    fake_client.head.return_value = head_resp

    result = await bi._best_google_books_cover("id", "http://example.com/fallback.jpg", fake_client)
    assert result == "https://example.com/fallback.jpg"


@pytest.mark.anyio
async def test_best_google_books_cover_head_too_small() -> None:
    fake_client = AsyncMock()

    vol_resp = MagicMock()
    vol_resp.status_code = 200
    vol_resp.json.return_value = {
        "volumeInfo": {"imageLinks": {"large": "http://example.com/large.jpg"}}
    }

    head_resp = MagicMock()
    head_resp.status_code = 200
    head_resp.headers = {"content-type": "image/jpeg", "content-length": "500"}

    fake_client.get.return_value = vol_resp
    fake_client.head.return_value = head_resp

    result = await bi._best_google_books_cover("id", "http://example.com/fallback.jpg", fake_client)
    assert result == "https://example.com/fallback.jpg"


@pytest.mark.anyio
async def test_best_google_books_cover_head_no_content_length() -> None:
    fake_client = AsyncMock()

    vol_resp = MagicMock()
    vol_resp.status_code = 200
    vol_resp.json.return_value = {
        "volumeInfo": {"imageLinks": {"large": "http://example.com/large.jpg"}}
    }

    head_resp = MagicMock()
    head_resp.status_code = 200
    head_resp.headers = {"content-type": "image/jpeg"}

    fake_client.get.return_value = vol_resp
    fake_client.head.return_value = head_resp

    result = await bi._best_google_books_cover("id", "http://example.com/fallback.jpg", fake_client)
    assert result == "https://example.com/large.jpg"


@pytest.mark.anyio
async def test_best_google_books_cover_http_error_on_head() -> None:
    fake_client = AsyncMock()

    vol_resp = MagicMock()
    vol_resp.status_code = 200
    vol_resp.json.return_value = {
        "volumeInfo": {"imageLinks": {"large": "http://example.com/large.jpg"}}
    }

    fake_client.get.return_value = vol_resp
    fake_client.head.side_effect = httpx.ConnectError("failed")

    result = await bi._best_google_books_cover("id", "http://example.com/fallback.jpg", fake_client)
    assert result == "https://example.com/fallback.jpg"


@pytest.mark.anyio
async def test_best_google_books_cover_no_item_id() -> None:
    fake_client = AsyncMock()

    head_resp = MagicMock()
    head_resp.status_code = 200
    head_resp.headers = {"content-type": "image/jpeg", "content-length": "5000"}

    fake_client.head.return_value = head_resp

    result = await bi._best_google_books_cover(None, "http://example.com/fallback.jpg", fake_client)
    assert result == "https://example.com/fallback.jpg"


@pytest.mark.anyio
async def test_best_google_books_cover_no_candidates() -> None:
    fake_client = AsyncMock()

    vol_resp = MagicMock()
    vol_resp.status_code = 200
    vol_resp.json.return_value = {"volumeInfo": {}}

    fake_client.get.return_value = vol_resp

    result = await bi._best_google_books_cover("id", None, fake_client)
    assert result is None


# ── map_google_books ───────────────────────────────────────────────────────────

def test_map_google_books_full() -> None:
    item = {
        "volumeInfo": {
            "title": "Book",
            "subtitle": "Subtitle",
            "authors": ["Author"],
            "industryIdentifiers": [
                {"type": "ISBN_13", "identifier": "9781234567897"},
                {"type": "ISBN_10", "identifier": "1234567890"},
            ],
            "imageLinks": {"thumbnail": "http://example.com/t.jpg"},
            "publisher": "Pub",
            "publishedDate": "2024-05",
            "pageCount": 300,
            "language": "en",
            "categories": ["Fiction"],
            "description": "A great book",
        }
    }
    c = bi.map_google_books(item)
    assert c.title == "Book"
    assert c.subtitle == "Subtitle"
    assert c.author == "Author"
    assert c.isbn == "9781234567897"
    assert c.cover_url == "https://example.com/t.jpg"
    assert c.publisher == "Pub"
    assert c.published_year == 2024
    assert c.page_count == 300
    assert c.language == "EN"
    assert c.tags == "Fiction"
    assert c.blurb == "A great book"
    assert c.source == "google_books"


def test_map_google_books_minimal() -> None:
    item = {"volumeInfo": {"title": "Book"}}
    c = bi.map_google_books(item)
    assert c.title == "Book"
    assert c.author is None
    assert c.isbn is None
    assert c.cover_url is None
    assert c.published_year is None
    assert c.page_count is None


def test_map_google_books_invalid_published_date() -> None:
    item = {"volumeInfo": {"title": "Book", "publishedDate": "not-a-date"}}
    c = bi.map_google_books(item)
    assert c.published_year is None


# ── _search_hardcover ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_hardcover_empty_token() -> None:
    fake_client = AsyncMock()
    results = await bi._search_hardcover("query", "title", "   ", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_search_hardcover_title_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_hardcover_search_title", AsyncMock(return_value=["9781234567897"]))
    fake = BookImportCandidate(title="Book", source="hardcover")
    monkeypatch.setattr(bi, "_hardcover_fetch_books", AsyncMock(return_value=[fake]))

    fake_client = AsyncMock()
    results = await bi._search_hardcover("query", "title", "token", fake_client)
    assert len(results) == 1


@pytest.mark.anyio
async def test_search_hardcover_isbn_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_hardcover_fetch_books", AsyncMock(return_value=[]))

    fake_client = AsyncMock()
    results = await bi._search_hardcover("9781234567897", "isbn", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_search_hardcover_invalid_isbn() -> None:
    fake_client = AsyncMock()
    results = await bi._search_hardcover("not-an-isbn", "isbn", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_search_hardcover_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_hardcover_search_title", AsyncMock(side_effect=RuntimeError("boom")))

    fake_client = AsyncMock()
    results = await bi._search_hardcover("query", "title", "token", fake_client)
    assert results == []


# ── _hardcover_search_title ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_hardcover_search_title_success() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "search": {
                "results": {
                    "found": 1,
                    "hits": [
                        {"document": {"isbns": ["9781234567897"]}}
                    ]
                }
            }
        }
    }

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_search_title("query", "token", fake_client)
    assert results == ["9781234567897"]


@pytest.mark.anyio
async def test_hardcover_search_title_http_error() -> None:
    fake_client = AsyncMock()
    fake_client.post.side_effect = httpx.ConnectError("failed")

    results = await bi._hardcover_search_title("query", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_search_title_non_200() -> None:
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "error"

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_search_title("query", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_search_title_graphql_errors() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"errors": [{"message": "bad query"}]}

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_search_title("query", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_search_title_no_results() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {"search": {"results": {"found": 0, "hits": []}}}
    }

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_search_title("query", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_search_title_invalid_isbn_in_hit() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "search": {
                "results": {
                    "found": 1,
                    "hits": [
                        {"document": {"isbns": ["invalid-isbn"]}}
                    ]
                }
            }
        }
    }

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_search_title("query", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_search_title_non_string_isbn() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "search": {
                "results": {
                    "found": 1,
                    "hits": [
                        {"document": {"isbns": [12345]}}
                    ]
                }
            }
        }
    }

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_search_title("query", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_search_title_max_results() -> None:
    hits = [{"document": {"isbns": [f"978123456789{i}"]}} for i in range(15)]
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "search": {
                "results": {
                    "found": 15,
                    "hits": hits,
                }
            }
        }
    }

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_search_title("query", "token", fake_client)
    assert len(results) == 10


# ── _hardcover_fetch_books ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_hardcover_fetch_books_empty_isbns() -> None:
    fake_client = AsyncMock()
    results = await bi._hardcover_fetch_books([], "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_fetch_books_http_error() -> None:
    fake_client = AsyncMock()
    fake_client.post.side_effect = httpx.ConnectError("failed")

    results = await bi._hardcover_fetch_books(["9781234567897"], "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_fetch_books_non_200() -> None:
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "error"

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_fetch_books(["9781234567897"], "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_fetch_books_graphql_errors() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"errors": [{"message": "bad query"}]}

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_fetch_books(["9781234567897"], "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_hardcover_fetch_books_success(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "book_mappings": [
                {
                    "edition": {
                        "title": "Book",
                        "isbn_13": "9781234567897",
                        "pages": 300,
                        "language": {"code2": "en"},
                    }
                }
            ]
        }
    }

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    monkeypatch.setattr(bi, "is_safe_cover_import_url", lambda url: True)

    results = await bi._hardcover_fetch_books(["9781234567897"], "token", fake_client)
    assert len(results) == 1
    assert results[0].title == "Book"


@pytest.mark.anyio
async def test_hardcover_fetch_books_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "book_mappings": [
                {
                    "edition": {
                        "title": "Book1",
                        "isbn_13": "9781234567897",
                        "pages": 300,
                        "language": {"code2": "en"},
                    }
                },
                {
                    "edition": {
                        "title": "Book2",
                        "isbn_13": "9781234567897",
                        "pages": 300,
                        "language": {"code2": "en"},
                    }
                }
            ]
        }
    }

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    monkeypatch.setattr(bi, "is_safe_cover_import_url", lambda url: True)

    results = await bi._hardcover_fetch_books(["9781234567897"], "token", fake_client)
    assert len(results) == 1


@pytest.mark.anyio
async def test_hardcover_fetch_books_map_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "book_mappings": [
                {"edition": {"title": ""}}
            ]
        }
    }

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_fetch_books(["9781234567897"], "token", fake_client)
    assert results == []


# ── map_hardcover ──────────────────────────────────────────────────────────────

def test_map_hardcover_full() -> None:
    edition = {
        "title": "Book",
        "subtitle": "Subtitle",
        "isbn_13": "9781234567897",
        "pages": 300,
        "release_date": "2024-05-20",
        "image": {"url": "https://example.com/cover.jpg"},
        "publisher": {"name": "Pub"},
        "language": {"code2": "en"},
        "book": {
            "description": "A great book",
            "taggings": [{"tag": {"tag": "Fiction"}}],
        },
        "contributions": [{"author": {"name": "Author"}}],
    }
    c = bi.map_hardcover(edition)
    assert c is not None
    assert c.title == "Book"
    assert c.subtitle == "Subtitle"
    assert c.author == "Author"
    assert c.isbn == "9781234567897"
    assert c.cover_url == "https://example.com/cover.jpg"
    assert c.publisher == "Pub"
    assert c.published_year == 2024
    assert c.page_count == 300
    assert c.language == "EN"
    assert c.tags == "Fiction"
    assert c.blurb == "A great book"
    assert c.source == "hardcover"


def test_map_hardcover_no_title() -> None:
    assert bi.map_hardcover({}) is None


def test_map_hardcover_invalid_release_date() -> None:
    edition = {
        "title": "Book",
        "release_date": "not-a-date",
    }
    c = bi.map_hardcover(edition)
    assert c is not None
    assert c.published_year is None


def test_map_hardcover_no_release_date() -> None:
    edition = {
        "title": "Book",
    }
    c = bi.map_hardcover(edition)
    assert c is not None
    assert c.published_year is None


def test_map_hardcover_unsafe_cover_url(monkeypatch: pytest.MonkeyPatch) -> None:
    edition = {
        "title": "Book",
        "image": {"url": "http://evil.com/cover.jpg"},
    }
    monkeypatch.setattr(bi, "is_safe_cover_import_url", lambda url: False)
    c = bi.map_hardcover(edition)
    assert c is not None
    assert c.cover_url is None


def test_map_hardcover_no_author() -> None:
    edition = {
        "title": "Book",
        "contributions": [{"author": {}}],
    }
    c = bi.map_hardcover(edition)
    assert c is not None
    assert c.author is None


# ── _hardcover_dedup_key ───────────────────────────────────────────────────────

def test_hardcover_dedup_key_missing_isbn() -> None:
    assert bi._hardcover_dedup_key({}) is None


def test_hardcover_dedup_key_full() -> None:
    key = bi._hardcover_dedup_key({"isbn_13": "9781234567897", "pages": 300, "language": {"code2": "en"}})
    assert key == ("9781234567897", 300, "en")


# ── _merge_results ─────────────────────────────────────────────────────────────

def test_merge_results_preserves_all_candidates() -> None:
    a = BookImportCandidate(title="A", isbn="123", cover_url=None, source="ol")
    b = BookImportCandidate(title="B", isbn="123", cover_url="https://x.jpg", source="gb")
    result = bi._merge_results([a], [b])
    assert len(result) == 2
    assert result[0] is a
    assert result[1] is b


def test_merge_results_preserves_order() -> None:
    a = BookImportCandidate(title="A", isbn="123", source="ol")
    b = BookImportCandidate(title="B", isbn="123", source="gb")
    c = BookImportCandidate(title="C", isbn="456", source="hc")
    result = bi._merge_results([a, b], [c])
    assert [r.title for r in result] == ["A", "B", "C"]


# ── _pick_isbn ─────────────────────────────────────────────────────────────────

def test_pick_isbn_13() -> None:
    assert bi._pick_isbn(["978-1-234-56789-7", "1234567890"]) == "9781234567897"


def test_pick_isbn_10() -> None:
    assert bi._pick_isbn(["1234567890", "invalid"]) == "1234567890"


def test_pick_isbn_none() -> None:
    assert bi._pick_isbn(["invalid", "also-invalid"]) == "invalid"


def test_pick_isbn_empty() -> None:
    assert bi._pick_isbn([]) is None


# ── _normalize_language_code ───────────────────────────────────────────────────

def test_normalize_language_code_2char() -> None:
    assert bi._normalize_language_code("en") == "EN"


def test_normalize_language_code_3char() -> None:
    assert bi._normalize_language_code("eng") == "EN"


def test_normalize_language_code_bibliographic() -> None:
    # "fre" is bibliographic for French; pycountry should map it
    result = bi._normalize_language_code("fre")
    assert result == "FR"


def test_normalize_language_code_invalid() -> None:
    assert bi._normalize_language_code("123") is None
    assert bi._normalize_language_code("") is None
    assert bi._normalize_language_code(None) is None
    assert bi._normalize_language_code("toolong") is None
    assert bi._normalize_language_code("x1") is None


@pytest.mark.anyio
async def test_search_with_progress_ol_error_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bi, "_search_open_library",
        AsyncMock(side_effect=bi.SourceBackendError("open_library", 500)),
    )
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    events = []
    async for e in bi.search_with_progress("query", "title"):
        events.append(e)
    assert any(e.get("stage") == "open_library" and e.get("status") == "error" for e in events)


@pytest.mark.anyio
async def test_search_hardcover_title_empty_isbns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover line 584: _hardcover_search_title returns empty list."""
    monkeypatch.setattr(bi, "_hardcover_search_title", AsyncMock(return_value=[]))

    fake_client = AsyncMock()
    results = await bi._search_hardcover("query", "title", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_search_hardcover_title_empty_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_hardcover_search_title", AsyncMock(return_value=["9781234567897"]))
    monkeypatch.setattr(bi, "_hardcover_fetch_books", AsyncMock(return_value=[]))

    fake_client = AsyncMock()
    results = await bi._search_hardcover("query", "title", "token", fake_client)
    assert results == []


@pytest.mark.anyio
async def test_search_google_books_isbn_path() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b'{}'
    resp.is_success = True
    resp.json.return_value = {"items": []}

    fake_client = AsyncMock()
    fake_client.get.return_value = resp

    results = await bi._search_google_books("9781234567897", "isbn", "key", fake_client)
    assert results == []
    # Verify params included isbn: prefix
    call_args = fake_client.get.call_args
    assert call_args[1]["params"]["q"] == "isbn:9781234567897"


@pytest.mark.anyio
async def test_best_google_books_cover_volume_fetch_http_error() -> None:
    fake_client = AsyncMock()

    vol_resp = MagicMock()
    vol_resp.raise_for_status.side_effect = httpx.HTTPError("failed")

    head_resp = MagicMock()
    head_resp.status_code = 200
    head_resp.headers = {"content-type": "image/jpeg", "content-length": "5000"}

    fake_client.get.return_value = vol_resp
    fake_client.head.return_value = head_resp

    result = await bi._best_google_books_cover("id", "http://example.com/fallback.jpg", fake_client)
    assert result == "https://example.com/fallback.jpg"


@pytest.mark.anyio
async def test_best_google_books_cover_head_not_200() -> None:
    fake_client = AsyncMock()

    vol_resp = MagicMock()
    vol_resp.status_code = 200
    vol_resp.json.return_value = {
        "volumeInfo": {"imageLinks": {"large": "http://example.com/large.jpg"}}
    }

    head_resp = MagicMock()
    head_resp.status_code = 404

    fake_client.get.return_value = vol_resp
    fake_client.head.return_value = head_resp

    result = await bi._best_google_books_cover("id", "http://example.com/fallback.jpg", fake_client)
    assert result == "https://example.com/fallback.jpg"


@pytest.mark.anyio
async def test_hardcover_fetch_books_none_dedup_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Edition without isbn_13 returns None dedup key, so it should not be deduplicated."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "book_mappings": [
                {"edition": {"title": "Book1"}},
                {"edition": {"title": "Book2"}},
            ]
        }
    }

    fake_client = AsyncMock()
    fake_client.post.return_value = resp

    results = await bi._hardcover_fetch_books(["9781234567897"], "token", fake_client)
    assert len(results) == 2


@pytest.mark.anyio
async def test_search_google_books_resp_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover the defensive resp is None check at line 416."""
    monkeypatch.setattr(bi, "_MAX_RETRIES", -1)
    fake_client = AsyncMock()
    results = await bi._search_google_books("query", "title", "key", fake_client)
    assert results == []


# ── map_open_library edge cases ────────────────────────────────────────────────

def test_map_open_library_no_isbn() -> None:
    doc = {"title": "Book"}
    c = bi.map_open_library(doc)
    assert c.isbn is None


def test_map_open_library_no_cover() -> None:
    doc = {"title": "Book"}
    c = bi.map_open_library(doc)
    assert c.cover_url is None


def test_map_open_library_multiple_authors() -> None:
    doc = {"title": "Book", "author_name": ["A", "B"]}
    c = bi.map_open_library(doc)
    assert c.author == "A, B"


# ── search_with_progress hardcover done event ──────────────────────────────────

@pytest.mark.anyio
async def test_search_with_progress_hc_done_event(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_hc = BookImportCandidate(title="HC Book", source="hardcover")
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[fake_hc]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    events = []
    async for e in bi.search_with_progress("query", "title", hardcover_api_token="token"):
        events.append(e)
    assert any(e.get("stage") == "hardcover" and e.get("status") == "done" for e in events)


# ── search_with_progress hardcover error event ─────────────────────────────────

@pytest.mark.anyio
async def test_search_with_progress_hc_error_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        bi, "_search_hardcover",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    events = []
    async for e in bi.search_with_progress("query", "title", hardcover_api_token="token"):
        events.append(e)
    assert any(e.get("stage") == "hardcover" and e.get("status") == "error" for e in events)


# ── BnF ──────────────────────────────────────────────────────────────────────────

# Two records for one ISBN: a commercial barcode stub and the real bibliographic
# record, as catalogue.bnf.fr actually answers a bib.isbn query.
BNF_SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <records>
    <record>
      <recordData>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>L'heure du Sud : ou l'invention d'un nouvel ordre mondial (Ed. 2024)</dc:title>
          <dc:creator>Badie, Bertrand</dc:creator>
          <dc:creator>Vidal, Dominique</dc:creator>
          <dc:publisher>Editions les Liens qui liberent (Paris)</dc:publisher>
          <dc:date>2024</dc:date>
          <dc:format>1 volume 295 p ; 22 cm</dc:format>
          <dc:language>fre</dc:language>
          <dc:identifier>http://catalogue.bnf.fr/ark:/12148/cb48773987b</dc:identifier>
          <dc:identifier>ISBN 9791020923554</dc:identifier>
          <dc:description>Code à barres commercial : EAN 9791020923554</dc:description>
        </oai_dc:dc>
      </recordData>
    </record>
    <record>
      <recordData>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>L'heure du Sud : ou l'invention d'un nouvel ordre mondial / sous la direction de Bertrand Badie</dc:title>
          <dc:contributor>Badie, Bertrand (1950-....).Editeur scientifique</dc:contributor>
          <dc:publisher>les Liens qui liberent (Paris)</dc:publisher>
          <dc:date>2024</dc:date>
          <dc:format>1 vol. (295 p.) : ill. ; 22 cm</dc:format>
          <dc:language>fre</dc:language>
          <dc:identifier>http://catalogue.bnf.fr/ark:/12148/cb47695466k</dc:identifier>
          <dc:identifier>ISBN 9791020923554</dc:identifier>
          <dc:subject>Relations internationales -- 2001-....</dc:subject>
        </oai_dc:dc>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>
"""


def test_map_bnf_response_basic() -> None:
    candidates = bi.map_bnf_response(BNF_SAMPLE_XML)
    # Both records carry the same ISBN, so only the richer one survives.
    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "L'heure du Sud"
    assert c.subtitle == "ou l'invention d'un nouvel ordre mondial"
    assert c.authors == ["Badie, Bertrand"]
    assert c.isbn == "9791020923554"
    assert c.publisher == "les Liens qui liberent"
    assert c.published_year == 2024
    assert c.page_count == 295
    assert c.language == "FR"
    assert c.tags == "Relations internationales"
    assert c.source == "bnf"
    assert c.cover_url is None


def test_map_bnf_response_empty() -> None:
    xml = """<?xml version="1.0"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <records/>
</searchRetrieveResponse>"""
    assert bi.map_bnf_response(xml) == []


def test_map_bnf_response_malformed_xml() -> None:
    assert bi.map_bnf_response("<invalid") == []


def test_map_bnf_response_no_records() -> None:
    xml = """<?xml version="1.0"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
</searchRetrieveResponse>"""
    assert bi.map_bnf_response(xml) == []


# ── Inventaire ─────────────────────────────────────────────────────────────────

INVENTAIRE_SAMPLE = {
    # Shape verified against https://inventaire.io/api/entities/by-uris:
    # claim values are plain strings, and P629/P50/P123 relatives come back as entities.
    "entities": {
        "inv:edition123": {
            "type": "edition",
            "originalLang": "fr",
            "labels": {"fromclaims": "L'heure du Sud"},
            "claims": {
                "wdt:P1476": ["L'heure du Sud"],
                "wdt:P1680": ["ou l'invention d'un nouvel ordre mondial"],
                "wdt:P212": ["979-10-209-2355-4"],
                "wdt:P577": ["2024"],
                "wdt:P1104": ["295"],
                "wdt:P123": ["wd:Q3236382"],
                "wdt:P629": ["inv:work123"],
                "invp:P2": ["abcdef123456"],
            },
        },
        "inv:work123": {
            "type": "work",
            "labels": {"fr": "L'heure du Sud"},
            "claims": {"wdt:P50": ["wd:Q7934"]},
        },
        "wd:Q7934": {
            "type": "human",
            "labels": {"en": "Bertrand Badie"},
        },
        "wd:Q3236382": {
            "type": "publisher",
            "labels": {"en": "Editions les Liens qui liberent"},
        },
    },
    "redirects": {"isbn:9791020923554": "inv:edition123"},
}


def test_map_inventaire_response_basic() -> None:
    candidates = bi.map_inventaire_response(INVENTAIRE_SAMPLE)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "L'heure du Sud"
    assert c.subtitle == "ou l'invention d'un nouvel ordre mondial"
    assert c.isbn == "9791020923554"
    assert c.published_year == 2024
    assert c.page_count == 295
    assert c.language == "FR"
    assert c.source == "inventaire"
    assert c.cover_url == "https://inventaire.io/img/entities/abcdef123456"
    assert c.authors == ["Bertrand Badie"]
    assert c.publisher == "Editions les Liens qui liberent"


def test_map_inventaire_response_authors_fall_back_to_edition_claims() -> None:
    data = {
        "entities": {
            "inv:edition123": {
                "type": "edition",
                "labels": {"fromclaims": "Plain Edition"},
                "claims": {
                    "wdt:P1476": ["Plain Edition"],
                    "wdt:P212": ["9782072716645"],
                    "wdt:P50": ["wd:Q43499"],
                },
            },
            "inv:work123": {"type": "work", "labels": {}, "claims": {}},
            "wd:Q43499": {"type": "human", "labels": {"en": "Erasmus"}},
        },
        "redirects": {"isbn:9782072716645": "inv:edition123"},
    }
    candidates = bi.map_inventaire_response(data)
    assert candidates[0].authors == ["Erasmus"]


def test_map_inventaire_response_without_title_is_skipped() -> None:
    data = {
        "entities": {"inv:edition123": {"type": "edition", "labels": {}, "claims": {}}},
        "redirects": {"isbn:9791020923554": "inv:edition123"},
    }
    assert bi.map_inventaire_response(data) == []


def test_map_inventaire_response_empty() -> None:
    assert bi.map_inventaire_response({"entities": {}, "redirects": {}}) == []


def test_map_inventaire_response_no_entities() -> None:
    assert bi.map_inventaire_response({}) == []


# ── Library of Congress ───────────────────────────────────────────────────────

LOC_SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <records>
    <record>
      <recordData>
        <mods:mods xmlns:mods="http://www.loc.gov/mods/v3">
          <mods:titleInfo>
            <mods:title>Dune</mods:title>
            <mods:subTitle>Book One of the Dune Chronicles</mods:subTitle>
          </mods:titleInfo>
          <mods:name type="personal">
            <mods:namePart>Herbert, Frank.</mods:namePart>
          </mods:name>
          <mods:name type="corporate">
            <mods:namePart>Chilton Books</mods:namePart>
          </mods:name>
          <mods:originInfo>
            <mods:publisher>Chilton Books</mods:publisher>
            <mods:dateIssued>1965</mods:dateIssued>
          </mods:originInfo>
          <mods:language>
            <mods:languageTerm type="code" authority="iso639-2b">eng</mods:languageTerm>
          </mods:language>
          <mods:physicalDescription>
            <mods:extent>412 p. ; 22 cm.</mods:extent>
          </mods:physicalDescription>
          <mods:subject>
            <mods:topic>Science fiction</mods:topic>
          </mods:subject>
          <mods:identifier type="isbn">9780441013593</mods:identifier>
          <mods:identifier type="lccn">65021248</mods:identifier>
        </mods:mods>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>
"""


def test_map_loc_response_basic() -> None:
    candidates = bi.map_loc_response(LOC_SAMPLE_XML)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "Dune"
    assert c.subtitle == "Book One of the Dune Chronicles"
    assert c.author == "Frank Herbert"
    assert c.authors == ["Frank Herbert"]
    assert c.publisher == "Chilton Books"
    assert c.published_year == 1965
    assert c.page_count == 412
    assert c.language == "EN"
    assert c.isbn == "9780441013593"
    assert c.tags == "Science fiction"
    assert c.source == "library_of_congress"
    assert c.cover_url is None


def test_map_loc_response_reads_topics_nested_in_subject() -> None:
    """MODS nests topics under <subject>, so only a descendant search finds them."""
    xml = """<?xml version="1.0"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <recordData>
    <mods:mods xmlns:mods="http://www.loc.gov/mods/v3">
      <mods:titleInfo><mods:title>Nested Topics</mods:title></mods:titleInfo>
      <mods:subject>
        <mods:topic>Outer</mods:topic>
        <mods:geographic><mods:topic>Inner</mods:topic></mods:geographic>
      </mods:subject>
    </mods:mods>
  </recordData>
</searchRetrieveResponse>"""
    candidates = bi.map_loc_response(xml)
    assert candidates[0].tags == "Outer, Inner"


def test_map_loc_response_accepts_spaced_isbn() -> None:
    xml = """<?xml version="1.0"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <recordData>
    <mods:mods xmlns:mods="http://www.loc.gov/mods/v3">
      <mods:titleInfo><mods:title>Spaced</mods:title></mods:titleInfo>
      <mods:identifier type="isbn">0-441-01359-8</mods:identifier>
    </mods:mods>
  </recordData>
</searchRetrieveResponse>"""
    candidates = bi.map_loc_response(xml)
    assert candidates[0].isbn == "9780441013593"


def test_map_loc_response_empty() -> None:
    xml = """<?xml version="1.0"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <records/>
</searchRetrieveResponse>"""
    assert bi.map_loc_response(xml) == []


def test_map_loc_response_malformed_xml() -> None:
    assert bi.map_loc_response("<invalid") == []


# ── Skip reasons and event bookkeeping ─────────────────────────────────────────

@pytest.mark.anyio
async def test_search_with_progress_emits_one_terminal_event_per_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each stage reports exactly one terminal event; no stage ends up twice."""
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[BookImportCandidate(title="B", source="bnf")]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi.settings, "library_of_congress_import_search_enabled", True)

    events = []
    async for e in bi.search_with_progress("query", "isbn"):
        events.append(e)

    terminal = {"done", "skipped", "error"}
    by_stage: dict[str, list[str]] = {}
    for e in events:
        if e.get("stage") in ("complete", "error"):
            continue
        by_stage.setdefault(e["stage"], []).append(e.get("status"))

    for stage, statuses in by_stage.items():
        assert statuses.count("searching") <= 1, (stage, statuses)
        assert len([s for s in statuses if s in terminal]) == 1, (stage, statuses)


@pytest.mark.anyio
async def test_search_with_progress_skips_inventaire_for_title_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inventaire has no title search, so it must be skipped rather than report 0."""
    inventaire = AsyncMock(return_value=[])
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", inventaire)
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[]))

    events = []
    async for e in bi.search_with_progress("query", "title"):
        events.append(e)

    inventaire_events = [e for e in events if e.get("stage") == "inventaire"]
    assert len(inventaire_events) == 1
    assert inventaire_events[0]["status"] == "skipped"
    assert inventaire_events[0]["reason"] == "title_search_unsupported"
    inventaire.assert_not_awaited()


@pytest.mark.anyio
async def test_search_with_progress_google_only_mode_respects_the_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bi.settings, "google_books_import_search_enabled", False)
    google = AsyncMock(return_value=[])

    events = []
    async for e in bi.search_with_progress("query", "title", api_key="key", mode="google_only"):
        events.append(e)

    assert any(
        e.get("stage") == "google_books" and e.get("reason") == "disabled" for e in events
    )
    google.assert_not_awaited()


# ── Parser edge cases found against live payloads ──────────────────────────────

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Herbert, Frank.", "Frank Herbert"),
        ("Herbert, Frank,", "Frank Herbert"),
        ("Horydczak, Theodor,", "Theodor Horydczak"),
        ("Mary Shelley", "Mary Shelley"),
    ],
)
def test_reverse_loc_author_handles_trailing_separators(raw: str, expected: str) -> None:
    assert bi._reverse_loc_author(raw) == expected


def test_split_bnf_title_strips_accented_edition_statements() -> None:
    assert bi._split_bnf_title("L'heure du Sud : ou l'invention (Éd. 2024)") == (
        "L'heure du Sud",
        "ou l'invention",
    )
    assert bi._split_bnf_title("Série noire : intégrale (Édition 2020)") == (
        "Série noire",
        "intégrale",
    )
    assert bi._split_bnf_title("Dune / Frank Herbert") == ("Dune", None)


def test_clean_bnf_tag_drops_subdivisions() -> None:
    assert bi._clean_bnf_tag("Relations internationales -- 2001-....") == "Relations internationales"
    assert bi._clean_bnf_tag("Pays en développement") == "Pays en développement"


@pytest.mark.parametrize(
    "raw",
    ['Le Seigneur des "Anneaux"', 'He said "hello"', 'back\\slash', '"', "   "],
)
def test_sanitize_cql_term_removes_quotes_and_backslashes(raw: str) -> None:
    cleaned = bi._sanitize_cql_term(raw)
    assert '"' not in cleaned
    assert "\\" not in cleaned


@pytest.mark.anyio
async def test_search_bnf_title_with_quotes_still_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    """A quote in a title must not break the CQL query into a silent empty result."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["query"] = request.url.params.get("query", "")
        return httpx.Response(200, text="<empty/>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        results = await bi._search_bnf('Le Seigneur des "Anneaux"', "title", client)

    assert results == []
    assert '""' not in seen["query"]
    assert seen["query"].count('"') % 2 == 0


# ── Hardened XML parsing ───────────────────────────────────────────────────────

_BILLION_LAUGHS = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <recordData><mods:mods xmlns:mods="http://www.loc.gov/mods/v3">
    <mods:titleInfo><mods:title>&lol3;</mods:title></mods:titleInfo>
  </mods:mods></recordData>
</searchRetrieveResponse>"""

_XXE_FILE_READ = """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <recordData><mods:mods xmlns:mods="http://www.loc.gov/mods/v3">
    <mods:titleInfo><mods:title>&xxe;</mods:title></mods:titleInfo>
  </mods:mods></recordData>
</searchRetrieveResponse>"""


def test_map_loc_response_rejects_entity_expansion() -> None:
    """A hostile SRU payload must not be expanded, and must yield no candidates."""
    assert bi.map_loc_response(_BILLION_LAUGHS) == []


def test_map_loc_response_rejects_external_entity() -> None:
    """External entity references must not be resolved to local files."""
    assert bi.map_loc_response(_XXE_FILE_READ) == []


def test_map_bnf_response_rejects_entity_expansion() -> None:
    payload = _BILLION_LAUGHS.replace("mods:mods", "oai_dc:dc").replace(
        'xmlns:mods="http://www.loc.gov/mods/v3"',
        'xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"',
    ).replace("mods:titleInfo", "").replace("mods:title", "dc:title").replace(
        "</mods:titleInfo>", ""
    ).replace("</mods:title>", "</dc:title>")
    assert bi.map_bnf_response(payload) == []


# ── Google fallback gating ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_uses_google_when_all_parallel_sources_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """With every parallel source off, Google Books must still answer as the fallback."""
    for flag, value in (
        ("open_library_import_search_enabled", False),
        ("bnf_import_search_enabled", False),
        ("inventaire_import_search_enabled", False),
        ("library_of_congress_import_search_enabled", False),
        ("dnb_import_search_enabled", False),
        ("hardcover_import_search_enabled", False),
        ("google_books_import_search_enabled", True),
    ):
        monkeypatch.setattr(bi.settings, flag, value)

    fake_gb = BookImportCandidate(title="GB Book", source="google_books")
    monkeypatch.setattr(bi, "_search_google_books", AsyncMock(return_value=[fake_gb]))

    results = await bi.search("query", "title", api_key="key")
    assert [r.source for r in results] == ["google_books"]


@pytest.mark.anyio
async def test_search_skips_google_when_fallback_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabling the fallback must stop the Google request entirely."""
    for flag, value in (
        ("open_library_import_search_enabled", False),
        ("bnf_import_search_enabled", False),
        ("inventaire_import_search_enabled", False),
        ("library_of_congress_import_search_enabled", False),
        ("dnb_import_search_enabled", False),
        ("hardcover_import_search_enabled", False),
        ("google_books_import_search_enabled", False),
    ):
        monkeypatch.setattr(bi.settings, flag, value)

    google = AsyncMock(return_value=[BookImportCandidate(title="GB", source="google_books")])
    monkeypatch.setattr(bi, "_search_google_books", google)

    results = await bi.search("query", "title", api_key="key")
    assert results == []
    google.assert_not_awaited()


@pytest.mark.anyio
async def test_search_with_progress_reports_disabled_google_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    for flag, value in (
        ("open_library_import_search_enabled", False),
        ("bnf_import_search_enabled", False),
        ("inventaire_import_search_enabled", False),
        ("library_of_congress_import_search_enabled", False),
        ("dnb_import_search_enabled", False),
        ("hardcover_import_search_enabled", False),
        ("google_books_import_search_enabled", False),
    ):
        monkeypatch.setattr(bi.settings, flag, value)

    google = AsyncMock(return_value=[BookImportCandidate(title="GB", source="google_books")])
    monkeypatch.setattr(bi, "_search_google_books", google)

    events = []
    async for e in bi.search_with_progress("query", "title", api_key="key"):
        events.append(e)

    assert any(
        e.get("stage") == "google_books" and e.get("reason") == "disabled" for e in events
    )
    google.assert_not_awaited()


@pytest.mark.anyio
async def test_search_with_progress_still_completes_without_parallel_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Google-only deployment is valid and must still emit a complete event."""
    for flag, value in (
        ("open_library_import_search_enabled", False),
        ("bnf_import_search_enabled", False),
        ("inventaire_import_search_enabled", False),
        ("library_of_congress_import_search_enabled", False),
        ("dnb_import_search_enabled", False),
        ("hardcover_import_search_enabled", False),
        ("google_books_import_search_enabled", True),
    ):
        monkeypatch.setattr(bi.settings, flag, value)

    fake_gb = BookImportCandidate(title="GB Book", source="google_books")
    monkeypatch.setattr(bi, "_search_google_books", AsyncMock(return_value=[fake_gb]))

    events = []
    async for e in bi.search_with_progress("query", "title", api_key="key"):
        events.append(e)

    complete = [e for e in events if e.get("stage") == "complete"]
    assert len(complete) == 1
    assert len(complete[0]["results"]) == 1


# ── _parse_page_count ──────────────────────────────────────────────────────────

def test_parse_page_count_valid() -> None:
    assert bi._parse_page_count("1 vol. (265 p.) ; 20 cm") == 265
    assert bi._parse_page_count("412 p. ; 22 cm.") == 412
    assert bi._parse_page_count("1,234 p.") == 1234
    assert bi._parse_page_count("528 p. : 23 cm.") == 528


def test_parse_page_count_invalid() -> None:
    assert bi._parse_page_count("no pages") is None
    assert bi._parse_page_count("") is None


# ── Source registry ─────────────────────────────────────────────────────────────

def test_book_sources_registry() -> None:
    stages = [s.stage for s in bi._build_sources("")]
    assert "open_library" in stages
    assert "bnf" in stages
    assert "inventaire" in stages
    assert "library_of_congress" in stages
    assert "dnb" in stages
    assert "hardcover" in stages


# ── Deutsche Nationalbibliothek ─────────────────────────────────────────────────

# Shaped like a real DNB SRU response: the SRU namespace is the root default and the
# MARC21 record declares its own. The title carries the U+0098/U+009C non-sorting markers
# the DNB uses in place of the MARC nonfiling indicator.
DNB_SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <version>1.1</version>
  <numberOfRecords>1</numberOfRecords>
  <records><record>
    <recordSchema>MARC21-xml</recordSchema>
    <recordPacking>xml</recordPacking>
    <recordData>
      <record xmlns="http://www.loc.gov/MARC21/slim" type="Bibliographic">
        <leader>00000nam a2200000 c 4500</leader>
        <controlfield tag="001">1395279225</controlfield>
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="020" ind1=" " ind2=" ">
          <subfield code="a">9783328115458</subfield>
          <subfield code="c">EUR 18.00</subfield>
          <subfield code="9">978-3-328-11545-8</subfield>
        </datafield>
        <datafield tag="041" ind1=" " ind2=" ">
          <subfield code="a">ger</subfield>
        </datafield>
        <datafield tag="100" ind1="1" ind2=" ">
          <subfield code="0">(DE-588)118577166</subfield>
          <subfield code="a">Mann, Thomas.</subfield>
          <subfield code="d">1875-1955</subfield>
          <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">\u0098Der\u009c Zauberberg</subfield>
          <subfield code="b">Penguin Klassiker</subfield>
        </datafield>
        <datafield tag="264" ind1=" " ind2="1">
          <subfield code="a">München</subfield>
          <subfield code="b">Penguin</subfield>
          <subfield code="c">2027</subfield>
        </datafield>
        <datafield tag="300" ind1=" " ind2=" ">
          <subfield code="a">1184 Seiten</subfield>
          <subfield code="c">19 cm</subfield>
        </datafield>
        <datafield tag="650" ind1=" " ind2="7">
          <subfield code="a">Deutsche Literatur</subfield>
        </datafield>
        <datafield tag="689" ind1="0" ind2="0">
          <subfield code="a">Deutsche Literatur</subfield>
        </datafield>
        <datafield tag="520" ind1=" " ind2=" ">
          <subfield code="a">Ein Roman über einen Menschen.</subfield>
        </datafield>
      </record>
    </recordData>
  </record></records>
</searchRetrieveResponse>"""


def _dnb_record(body: str) -> str:
    """Wrap MARC21 record fields in the SRU envelope the DNB returns."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <recordData><record xmlns="http://www.loc.gov/MARC21/slim" type="Bibliographic">
    {body}
  </record></recordData>
</searchRetrieveResponse>"""


def test_map_dnb_response_basic() -> None:
    candidates = bi.map_dnb_response(DNB_SAMPLE_XML)
    assert len(candidates) == 1
    c = candidates[0]
    # The non-sorting markers must not survive into the title.
    assert c.title == "Der Zauberberg"
    assert c.subtitle == "Penguin Klassiker"
    assert c.author == "Thomas Mann"
    assert c.authors == ["Thomas Mann"]
    assert c.publisher == "Penguin"
    assert c.published_year == 2027
    assert c.page_count == 1184
    assert c.language == "DE"
    assert c.isbn == "9783328115458"
    # 689 restates 650, so tags must not be doubled.
    assert c.tags == "Deutsche Literatur"
    assert c.blurb == "Ein Roman über einen Menschen."
    assert c.source == "dnb"
    assert c.cover_url is None


def test_map_dnb_response_uses_first_245_with_a_title() -> None:
    """245 is non-repeating; the first field carrying a $a is the title.

    The first indicator only says whether a title added entry is made, so it must not be
    used to rank candidate titles.
    """
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Erster Titel</subfield>
        </datafield>
        <datafield tag="245" ind1="0" ind2="0">
          <subfield code="a">Zweiter Titel</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].title == "Erster Titel"


def test_map_dnb_response_skips_245_without_a_title() -> None:
    """A 245 with no $a is not a title, so the record is still imported."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="b">Nur ein Resttitel</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Tatsächlicher Titel</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].title == "Tatsächlicher Titel"


def test_map_dnb_response_strips_nonfiling_markers() -> None:
    """U+0098 and U+009C are DNB non-sorting markers, not part of the title."""
    xml = _dnb_record(f"""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">\u0098Der\u009c Zauberberg</subfield>
        </datafield>
    """)
    c = bi.map_dnb_response(xml)[0]
    assert c.title == "Der Zauberberg"
    assert "\u0098" not in c.title


def test_map_dnb_response_skips_non_author_1xx() -> None:
    """A 1XX coded as editor or translator is a contributor, not the book author."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="100" ind1="1" ind2=" ">
          <subfield code="a">Herausgeber, Hans</subfield>
          <subfield code="4">edt</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Anthologie</subfield>
        </datafield>
    """)
    c = bi.map_dnb_response(xml)[0]
    assert c.authors is None
    assert c.author is None


def test_map_dnb_response_falls_back_to_corporate_author() -> None:
    """A work with no personal name still has a 110 corporate author."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="110" ind1="2" ind2=" ">
          <subfield code="a">Deutsche Akademie</subfield>
          <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Bericht</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].authors == ["Deutsche Akademie"]


def test_map_dnb_response_ignores_invalid_isbn_field() -> None:
    """A 020 with a $q note records an ISBN the DNB itself says is wrong.

    $9 then normalizes that bad value, so the whole field has to be dropped: importing
    it would attach the book to an ISBN that identifies something else.
    """
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="020" ind1=" " ind2=" ">
          <subfield code="z">9783161484100</subfield>
          <subfield code="q">falsche ISBN in Vorlage</subfield>
          <subfield code="9">978-3-16-148410-0</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Kochbuch</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].isbn is None


def test_map_dnb_response_keeps_isbn_from_other_valid_field() -> None:
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="020" ind1=" " ind2=" ">
          <subfield code="z">1111111111111</subfield>
          <subfield code="q">falsche ISBN in Vorlage</subfield>
        </datafield>
        <datafield tag="020" ind1=" " ind2=" ">
          <subfield code="a">9783328115458</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Der Zauberberg</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].isbn == "9783328115458"


def test_map_dnb_response_appends_author_coded_co_authors() -> None:
    """The DNB puts co-authors in 700 added entries, so they must be collected.

    Editors, translators and illustrators are far more common in 700 than authors are, so
    only fields explicitly coded as authors may be added.
    """
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="100" ind1="1" ind2=" ">
          <subfield code="a">Angermann, Detlef</subfield>
          <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="700" ind1="1" ind2=" ">
          <subfield code="a">Seitz, Florian</subfield>
          <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="700" ind1="1" ind2=" ">
          <subfield code="a">Hugentobler, Urs</subfield>
          <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Mission Erde</subfield>
        </datafield>
    """)
    c = bi.map_dnb_response(xml)[0]
    assert c.authors == ["Detlef Angermann", "Florian Seitz", "Urs Hugentobler"]
    assert c.author == "Detlef Angermann"


@pytest.mark.parametrize("role, name", [
    ("edt", "Herausgeber, Hans"),
    ("trl", "Übersetzer, Inge"),
    ("ill", "Illustrator, Piet"),
    ("art", "Künstler, Karl"),
])
def test_map_dnb_response_skips_non_author_coauthors(role: str, name: str) -> None:
    """A 700 coded as anything but an author is a contributor, not a co-author."""
    xml = _dnb_record(f"""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="100" ind1="1" ind2=" ">
          <subfield code="a">Mann, Thomas</subfield>
          <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="700" ind1="1" ind2=" ">
          <subfield code="a">{name}</subfield>
          <subfield code="4">{role}</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Anthologie</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].authors == ["Thomas Mann"]


def test_map_dnb_response_ignores_uncoded_700() -> None:
    """A 700 with no relator is not safe to call an author, unlike an uncoded 1XX.

    The 1XX main entry is the record's own statement of who wrote the book. A 700 is an
    added entry, and the DNB codes every one of them, so an uncoded 700 is ambiguous.
    """
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="100" ind1="1" ind2=" ">
          <subfield code="a">Mann, Thomas</subfield>
          <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="700" ind1="1" ind2=" ">
          <subfield code="a">Uncodierter Name</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Anthologie</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].authors == ["Thomas Mann"]


def test_map_dnb_response_handles_undated_publication() -> None:
    """German records without a year carry "o.J." (ohne Jahr) or "n.d." instead."""
    for placeholder in ("o.J.", "n.d.", "[o.J.]", "o. J."):
        xml = _dnb_record(f"""
            <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
            <datafield tag="264" ind1=" " ind2="1">
              <subfield code="b">Verlag</subfield>
              <subfield code="c">{placeholder}</subfield>
            </datafield>
            <datafield tag="245" ind1="1" ind2="0">
              <subfield code="a">Ohne Jahresangabe</subfield>
            </datafield>
        """)
        c = bi.map_dnb_response(xml)[0]
        assert c.publisher == "Verlag", placeholder
        assert c.published_year is None, placeholder


def test_map_dnb_response_accepts_uncoded_main_entry() -> None:
    """An uncoded 1XX is still the main entry, so it is accepted as the author."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="100" ind1="1" ind2=" ">
          <subfield code="a">Anonymus</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Ohne Verfasserangabe</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].authors == ["Anonymus"]


def test_map_dnb_response_uses_260_for_older_records() -> None:
    """Older records carry the publication statement in 260, which has no indicator."""
    xml = _dnb_record("""
        <controlfield tag="008">990101s1990    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="260" ind1=" " ind2=" ">
          <subfield code="a">Weimar</subfield>
          <subfield code="b">Verlag</subfield>
          <subfield code="c">1990</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Altbestand</subfield>
        </datafield>
    """)
    c = bi.map_dnb_response(xml)[0]
    assert c.publisher == "Verlag"
    assert c.published_year == 1990


def test_map_dnb_response_ignores_copyright_statement() -> None:
    """264 with second indicator 4 is the copyright statement, not the publication."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="264" ind1=" " ind2="4">
          <subfield code="b">Reclam</subfield>
          <subfield code="c">©1999</subfield>
        </datafield>
        <datafield tag="264" ind1=" " ind2="1">
          <subfield code="a">München</subfield>
          <subfield code="b">Hanser</subfield>
          <subfield code="c">2027</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Neuauflage</subfield>
        </datafield>
    """)
    c = bi.map_dnb_response(xml)[0]
    assert c.publisher == "Hanser"
    assert c.published_year == 2027


def test_map_dnb_response_accepts_264_without_indicator() -> None:
    """A 264 with no second indicator is still the only publication statement."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="264" ind1=" ">
          <subfield code="b">Selfpublisher</subfield>
          <subfield code="c">2020</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Eigenverlag</subfield>
        </datafield>
    """)
    c = bi.map_dnb_response(xml)[0]
    assert c.publisher == "Selfpublisher"
    assert c.published_year == 2020


def test_map_dnb_response_normalizes_isbn10() -> None:
    """ISBNs are normalized to ISBN-13 so they match every other source's output."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="020" ind1=" " ind2=" ">
          <subfield code="a">3328115455</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Der Zauberberg</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].isbn == "9783328115458"


def test_map_dnb_response_normalizes_hyphenated_isbn_from_subfield_9() -> None:
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="020" ind1=" " ind2=" ">
          <subfield code="9">978-3-328-11545-8</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Der Zauberberg</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].isbn == "9783328115458"


def test_map_dnb_response_discards_unparseable_isbn() -> None:
    """An ISBN that cannot be normalized is dropped rather than stored verbatim."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="020" ind1=" " ind2=" ">
          <subfield code="a">keine-nummer</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Titel ohne ISBN</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].isbn is None


def test_map_dnb_response_caps_subject_headings() -> None:
    """Tags are capped at three like the BnF and Library of Congress providers."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="650" ind1=" " ind2=" ">
          <subfield code="a">Erstes</subfield>
        </datafield>
        <datafield tag="650" ind1=" " ind2=" ">
          <subfield code="a">Zweites</subfield>
        </datafield>
        <datafield tag="650" ind1=" " ind2=" ">
          <subfield code="a">Drittes</subfield>
        </datafield>
        <datafield tag="650" ind1=" " ind2=" ">
          <subfield code="a">Viertes</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">Viele Schlagwörter</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].tags == "Erstes, Zweites, Drittes"


def test_parse_dnb_page_count_does_not_backtrack() -> None:
    """A long run with no page-count keyword must not cost quadratic time.

    The old lazy pattern spent ~360 ms on this input; the bounded one must stay flat, so
    a hostile 300$a cannot stall a search.
    """
    import time

    for payload in ("1" + " " * 5000, "1" + "9" * 5000, "1.1.1." * 1000):
        start = time.perf_counter()
        assert bi._parse_dnb_page_count(payload) is None
        assert (time.perf_counter() - start) < 0.25, payload[:16]


def test_map_dnb_response_unwraps_supplied_publisher_and_year() -> None:
    """Square brackets mark a value the cataloguer supplied rather than transcribed.

    The title keeps its brackets because there they are part of the title itself: the
    Library of Congress documents titles such as `24500$a[Man smoking at window]`.
    """
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">[Lisboa]</subfield>
        </datafield>
        <datafield tag="264" ind1=" " ind2="1">
          <subfield code="a">[Lisboa]</subfield>
          <subfield code="b">[Editora]</subfield>
          <subfield code="c">[2026]</subfield>
        </datafield>
    """)
    c = bi.map_dnb_response(xml)[0]
    assert c.title == "[Lisboa]"
    assert c.publisher == "Editora"
    assert c.published_year == 2026


def test_map_dnb_response_reads_language_from_008() -> None:
    """Records without a 041 still carry the language in the 008 fixed field."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||por  </controlfield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">A montanha</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].language == "PT"


def test_map_dnb_response_prefers_041_over_008() -> None:
    """041$a is the language of the text; 008 can disagree on translated works."""
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="041" ind1=" " ind2=" ">
          <subfield code="a">por</subfield>
          <subfield code="h">ger</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
          <subfield code="a">A montanha</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml)[0].language == "PT"


def test_map_dnb_response_no_title_is_skipped() -> None:
    xml = _dnb_record("""
        <controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="100" ind1="1" ind2=" ">
          <subfield code="a">Mann, Thomas</subfield>
        </datafield>
    """)
    assert bi.map_dnb_response(xml) == []


def test_map_dnb_response_empty() -> None:
    xml = """<?xml version="1.0"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>0</numberOfRecords>
</searchRetrieveResponse>"""
    assert bi.map_dnb_response(xml) == []


def test_map_dnb_response_malformed_xml() -> None:
    assert bi.map_dnb_response("<not-xml") == []


def test_map_dnb_response_rejects_entity_expansion() -> None:
    """A hostile SRU payload must not be expanded, and must yield no candidates."""
    payload = _BILLION_LAUGHS.replace(
        "<mods:titleInfo><mods:title>&lol3;</mods:title></mods:titleInfo>",
        f"""<controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="245" ind1="1" ind2="0"><subfield code="a">&lol3;</subfield></datafield>""",
    )
    assert bi.map_dnb_response(payload) == []


def test_map_dnb_response_rejects_external_entity() -> None:
    """External entity references must not be resolved to local files."""
    payload = _XXE_FILE_READ.replace(
        "<mods:titleInfo><mods:title>&xxe;</mods:title></mods:titleInfo>",
        f"""<controlfield tag="008">260331s2027    gw ||||| |||| 00||||ger  </controlfield>
        <datafield tag="245" ind1="1" ind2="0"><subfield code="a">&xxe;</subfield></datafield>""",
    )
    assert bi.map_dnb_response(payload) == []


@pytest.mark.parametrize("raw, expected", [
    ("Mann, Thomas.", "Thomas Mann"),
    ("Popper, Karl R.", "Karl R. Popper"),
    ("Goethe, Johann Wolfgang von", "Johann Wolfgang von Goethe"),
    ("Beethoven, Ludwig van", "Ludwig van Beethoven"),
    ("Einstein, Albert", "Albert Einstein"),
    ("  Surname  ", "Surname"),
    # strip(" ,;") removes a dangling separator, so these never reach the split.
    ("Ludwig van Beethoven, ", "Ludwig van Beethoven"),
    ("Surname,", "Surname"),
    (",Forename", "Forename"),
    ("Beethoven, L.", "L. Beethoven"),
    # A name that is not inverted carries no inversion punctuation, so titles and
    # abbreviations keep their periods whatever their length.
    ("Dr.", "Dr."),
    ("Prof.", "Prof."),
    ("MSc.", "MSc."),
    ("BSc.", "BSc."),
    ("Ab.", "Ab."),
    ("R.", "R."),
    ("Prof. Dr. Schmidt", "Prof. Dr. Schmidt"),
    ("Deutsche Akademie der Wissenschaften", "Deutsche Akademie der Wissenschaften"),
])
def test_reverse_dnb_name(raw: str, expected: str) -> None:
    """1XX names are catalogued inverted and must read naturally once reversed."""
    assert bi._reverse_dnb_name(raw) == expected


@pytest.mark.parametrize("text, expected", [
    ("1184 Seiten", 1184),
    ("1.184 Seiten", 1184),
    ("1 184 Seiten", 1184),
    ("1,184 Seiten", 1184),
    ("1 184 Seiten", 1184),
    ("926 pages", 926),
    ("416 sidor", 416),
    ("XXXIX, 601 S.", 601),
    ("XXIV, 601 S.", 601),
    ("219 Seiten", 219),
    ("12 Seiten", 12),
    ("Bd. 1 184 Seiten", 1184),
    # A decimal must be rejected, not read as a page count.
    ("1.5 pages", None),
    ("1,5 sidor", None),
    ("1,23 Seiten", None),
    ("1 Band", None),
    ("", None),
])
def test_parse_dnb_page_count(text: str, expected: int | None) -> None:
    """Extent statements are localized; only the arabic page count is usable."""
    assert bi._parse_dnb_page_count(text) == expected


def _dnb_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_search_dnb_isbn_query() -> None:
    """An ISBN search queries the num index with the normalized ISBN-13."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, text=DNB_SAMPLE_XML)

    async with _dnb_client(handler) as client:
        candidates = await bi._search_dnb("978-3-328-11545-8", "isbn", client)

    assert seen["query"] == "num=9783328115458"
    assert seen["recordSchema"] == "MARC21-xml"
    assert seen["version"] == "1.1"
    assert candidates[0].title == "Der Zauberberg"


@pytest.mark.anyio
async def test_search_dnb_title_query() -> None:
    """A title search is quoted so "and" or "or" in it is not read as a CQL operator."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, text="<searchRetrieveResponse/>")

    async with _dnb_client(handler) as client:
        await bi._search_dnb("Das Maß der Erde", "title", client)

    assert seen["query"] == 'tit="Das Maß der Erde"'


@pytest.mark.anyio
async def test_search_dnb_sanitizes_cql_term() -> None:
    """A quote in the query must not terminate the CQL string early."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, text="<searchRetrieveResponse/>")

    async with _dnb_client(handler) as client:
        await bi._search_dnb('Der "Zauberberg', "title", client)

    assert seen["query"] == 'tit="Der Zauberberg"'


@pytest.mark.anyio
async def test_search_dnb_empty_title_returns_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be sent")

    async with _dnb_client(handler) as client:
        assert await bi._search_dnb('"', "title", client) == []


@pytest.mark.anyio
async def test_search_dnb_invalid_isbn_returns_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be sent")

    async with _dnb_client(handler) as client:
        assert await bi._search_dnb("not-an-isbn", "isbn", client) == []


@pytest.mark.anyio
async def test_search_dnb_raises_backend_error_on_http_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    async with _dnb_client(handler) as client:
        with pytest.raises(bi.SourceBackendError) as excinfo:
            await bi._search_dnb("Faust", "title", client)

    assert excinfo.value.source == "dnb"
    assert excinfo.value.status_code == 503


@pytest.mark.anyio
async def test_search_dnb_raises_backend_error_on_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    async with _dnb_client(handler) as client:
        with pytest.raises(bi.SourceBackendError) as excinfo:
            await bi._search_dnb("Faust", "title", client)

    assert excinfo.value.source == "dnb"


@pytest.mark.anyio
async def test_dnb_is_reported_in_progress_events(monkeypatch: pytest.MonkeyPatch) -> None:
    """A finished DNB search reports its own stage with a result count."""
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_bnf", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_inventaire", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_loc", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_dnb", AsyncMock(return_value=[BookImportCandidate(
        title="Der Zauberberg", source="dnb",
    )]))

    events = []
    async for e in bi.search_with_progress("Der Zauberberg", "title"):
        events.append(e)

    assert any(e.get("stage") == "dnb" and e.get("status") == "searching" for e in events)
    assert any(e.get("stage") == "dnb" and e.get("status") == "done" and e.get("count") == 1
               for e in events)
    complete = [e for e in events if e.get("stage") == "complete"][0]
    assert complete["results"][0]["source"] == "dnb"


def test_dnb_is_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi.settings, "dnb_import_search_enabled", False)
    spec = next(s for s in bi._build_sources("") if s.stage == "dnb")
    assert spec.enabled() is False
    assert spec.display_name == "Deutsche Nationalbibliothek"
