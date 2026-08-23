"""Unit tests for app.services.book_import module."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.schemas import BookImportCandidate
from app.services import book_import as bi


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

    events = []
    async for e in bi.search_with_progress("query", "title", hardcover_api_token="token"):
        events.append(e)
    assert any(e.get("stage") == "open_library" and e.get("status") == "searching" for e in events)
    assert any(e.get("stage") == "hardcover" and e.get("status") == "searching" for e in events)
    assert any(e.get("stage") == "open_library" and e.get("status") == "done" for e in events)


@pytest.mark.anyio
async def test_search_with_progress_auto_hc_skipped_no_token() -> None:
    events = []
    async for e in bi.search_with_progress("query", "title"):
        events.append(e)
    assert any(e.get("stage") == "hardcover" and e.get("status") == "skipped" for e in events)


@pytest.mark.anyio
async def test_search_with_progress_auto_fallback_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
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

    events = []
    async for e in bi.search_with_progress("query", "title"):
        events.append(e)
    assert any(e.get("stage") == "error" for e in events)


# ── search ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_ol_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bi, "_search_open_library",
        AsyncMock(side_effect=bi.SourceBackendError("open_library", 503)),
    )
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))

    results = await bi.search("query", "title")
    assert results == []


@pytest.mark.anyio
async def test_search_ol_generic_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bi, "_search_open_library",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))

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

    results = await bi.search("query", "title", hardcover_api_token="token")
    assert len(results) == 1


@pytest.mark.anyio
async def test_search_hc_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        bi, "_search_hardcover",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    results = await bi.search("query", "title", hardcover_api_token="token")
    assert results == []


@pytest.mark.anyio
async def test_search_fallback_google_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))

    results = await bi.search("query", "title")
    assert results == []


@pytest.mark.anyio
async def test_search_fallback_google_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
    fake = BookImportCandidate(title="Book", source="google_books")
    monkeypatch.setattr(bi, "_search_google_books", AsyncMock(return_value=[fake]))

    results = await bi.search("query", "title", api_key="key")
    assert len(results) == 1


@pytest.mark.anyio
async def test_search_fallback_google_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bi, "_search_open_library", AsyncMock(return_value=[]))
    monkeypatch.setattr(bi, "_search_hardcover", AsyncMock(return_value=[]))
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


# ── _merge_and_deduplicate ─────────────────────────────────────────────────────

def test_merge_and_deduplicate_cover_preference() -> None:
    a = BookImportCandidate(title="A", isbn="123", cover_url=None, source="ol")
    b = BookImportCandidate(title="B", isbn="123", cover_url="https://x.jpg", source="gb")
    result = bi._merge_and_deduplicate([a], [b])
    assert len(result) == 1
    assert result[0].cover_url == "https://x.jpg"


def test_merge_and_deduplicate_no_cover_override() -> None:
    a = BookImportCandidate(title="A", isbn="123", cover_url="https://a.jpg", source="ol")
    b = BookImportCandidate(title="B", isbn="123", cover_url="https://b.jpg", source="gb")
    result = bi._merge_and_deduplicate([a], [b])
    assert len(result) == 1
    assert result[0].cover_url == "https://a.jpg"


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

    events = []
    async for e in bi.search_with_progress("query", "title", hardcover_api_token="token"):
        events.append(e)
    assert any(e.get("stage") == "hardcover" and e.get("status") == "error" for e in events)
