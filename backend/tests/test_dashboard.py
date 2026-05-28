from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import settings
import app.services.quote_cache as quote_cache
from app.services.quote_cache import (
    configure_quote_cache_ttl,
    get_or_fetch_dashboard_quote,
    invalidate_quote_cache,
)


def _create_book(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    """Helper to create a book via the API and return the JSON response."""
    payload = {"title": "Test Book", "author": "Test Author", "page_count": 100, **kwargs}
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201
    return resp.json()


def test_book_stats_empty_library(client: TestClient) -> None:
    resp = client.get("/api/books/stats")
    assert resp.status_code == 200
    assert resp.json() == {
        "total_books": 0,
        "books_read": 0,
        "books_reading": 0,
        "books_want_to_read": 0,
        "books_did_not_finish": 0,
    }


def test_book_stats_counts_all_statuses(client: TestClient) -> None:
    _create_book(client, title="Want", reading_status="want_to_read")
    _create_book(client, title="Reading", reading_status="currently_reading")
    _create_book(client, title="Read", reading_status="read")
    _create_book(client, title="DNF", reading_status="did_not_finish")

    resp = client.get("/api/books/stats")
    assert resp.status_code == 200
    assert resp.json() == {
        "total_books": 4,
        "books_read": 1,
        "books_reading": 1,
        "books_want_to_read": 1,
        "books_did_not_finish": 1,
    }


def test_book_stats_require_auth(client: TestClient) -> None:
    original = client.headers.get("X-API-Key")
    client.headers.pop("X-API-Key", None)
    client.post("/api/auth/logout")
    try:
        resp = client.get("/api/books/stats")
    finally:
        if original:
            client.headers["X-API-Key"] = original
    assert resp.status_code == 401


def test_book_stats_is_user_scoped(client: TestClient, create_user_with_key: Callable[..., Any]) -> None:
    _create_book(client, title="User 1 Book", reading_status="read")

    _, other_key = create_user_with_key(email="other@example.com")
    original = client.headers.get("X-API-Key")
    client.headers["X-API-Key"] = other_key
    try:
        _create_book(client, title="User 2 Book", reading_status="want_to_read")
        _create_book(client, title="User 2 Book 2", reading_status="currently_reading")
        resp = client.get("/api/books/stats")
    finally:
        if original:
            client.headers["X-API-Key"] = original
    assert resp.status_code == 200
    assert resp.json() == {
        "total_books": 2,
        "books_read": 0,
        "books_reading": 1,
        "books_want_to_read": 1,
        "books_did_not_finish": 0,
    }


def test_dashboard_quote_returns_none_when_disabled(client: TestClient, monkeypatch) -> None:
    invalidate_quote_cache()
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)
    resp = client.get("/api/books/dashboard-quote")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Dashboard quote feature is disabled"


class _FakeQuoteResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"quote": "Stay humble.", "author": "Anon"}


class _FakeAsyncClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        return None

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get(self, url: str) -> _FakeQuoteResponse:
        return _FakeQuoteResponse()


def test_dashboard_quote_returns_quote(client: TestClient, monkeypatch) -> None:
    invalidate_quote_cache()
    configure_quote_cache_ttl(86400)
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)
    monkeypatch.setattr(quote_cache.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/books/dashboard-quote")
    assert resp.status_code == 200
    assert resp.json() == {"quote": "Stay humble.", "author": "Anon"}


class _ChangingFakeAsyncClient:
    calls: int = 0

    def __init__(self, *args: object, **kwargs: object) -> None:
        return None

    async def __aenter__(self) -> "_ChangingFakeAsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get(self, url: str) -> _FakeQuoteResponse:
        _ChangingFakeAsyncClient.calls += 1
        return _FakeQuoteResponse()


@pytest.mark.anyio
async def test_dashboard_quote_network_error(monkeypatch) -> None:
    """Network error during quote fetch should return None."""
    invalidate_quote_cache()

    class _ErrorClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_ErrorClient":
            return self

        async def __aexit__(self, *args: object, **kwargs: object) -> None:
            return None

        async def get(self, url: str) -> None:
            raise Exception("network down")

    monkeypatch.setattr("app.services.quote_cache.httpx.AsyncClient", _ErrorClient)
    result = await get_or_fetch_dashboard_quote()
    assert result is None


@pytest.mark.anyio
async def test_dashboard_quote_non_dict_payload(monkeypatch) -> None:
    """Non-dict JSON payload should return None."""
    invalidate_quote_cache()

    class _ListResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> list[str]:
            return ["not", "a", "dict"]

    class _FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: object, **kwargs: object) -> None:
            return None

        async def get(self, url: str) -> _ListResponse:
            return _ListResponse()

    monkeypatch.setattr("app.services.quote_cache.httpx.AsyncClient", _FakeClient)
    result = await get_or_fetch_dashboard_quote()
    assert result is None


@pytest.mark.anyio
async def test_dashboard_quote_empty_quote(monkeypatch) -> None:
    """Empty or whitespace-only quote should return None."""
    invalidate_quote_cache()

    class _EmptyQuoteResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, str]:
            return {"quote": "   ", "author": "Anon"}

    class _FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: object, **kwargs: object) -> None:
            return None

        async def get(self, url: str) -> _EmptyQuoteResponse:
            return _EmptyQuoteResponse()

    monkeypatch.setattr("app.services.quote_cache.httpx.AsyncClient", _FakeClient)
    result = await get_or_fetch_dashboard_quote()
    assert result is None


@pytest.mark.anyio
async def test_dashboard_quote_non_string_author(monkeypatch) -> None:
    """Non-string author should be treated as None."""
    invalidate_quote_cache()

    class _NumAuthorResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {"quote": "Hello", "author": 42}

    class _FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: object, **kwargs: object) -> None:
            return None

        async def get(self, url: str) -> _NumAuthorResponse:
            return _NumAuthorResponse()

    monkeypatch.setattr("app.services.quote_cache.httpx.AsyncClient", _FakeClient)
    result = await get_or_fetch_dashboard_quote()
    assert result is not None
    assert result.quote == "Hello"
    assert result.author is None


def test_dashboard_quote_uses_backend_cache(client: TestClient, monkeypatch) -> None:
    invalidate_quote_cache()
    configure_quote_cache_ttl(86400)
    _ChangingFakeAsyncClient.calls = 0
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)
    monkeypatch.setattr(quote_cache.httpx, "AsyncClient", _ChangingFakeAsyncClient)

    first = client.get("/api/books/dashboard-quote")
    second = client.get("/api/books/dashboard-quote")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {"quote": "Stay humble.", "author": "Anon"}
    assert second.json() == {"quote": "Stay humble.", "author": "Anon"}
    assert _ChangingFakeAsyncClient.calls == 1
