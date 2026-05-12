from fastapi.testclient import TestClient
from app.config import settings
import app.routers.books as books_router


def _create_book(client: TestClient, **kwargs) -> dict:
    payload = {"title": "Test Book", **kwargs}
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201
    return resp.json()


def test_book_stats_empty_library(client: TestClient):
    resp = client.get("/api/books/stats")
    assert resp.status_code == 200
    assert resp.json() == {
        "total_books": 0,
        "books_read": 0,
        "books_reading": 0,
        "books_want_to_read": 0,
        "books_did_not_finish": 0,
    }


def test_book_stats_counts_all_statuses(client: TestClient):
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


def test_book_stats_require_auth(client: TestClient):
    original = client.headers.get("X-API-Key")
    client.headers.pop("X-API-Key", None)
    try:
        resp = client.get("/api/books/stats")
    finally:
        if original:
            client.headers["X-API-Key"] = original

    assert resp.status_code == 401


def test_book_stats_is_user_scoped(client: TestClient, create_user_with_key):
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


def test_dashboard_quote_returns_none_when_disabled(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)

    resp = client.get("/api/books/dashboard-quote")

    assert resp.status_code == 200
    assert resp.json() is None


class _FakeQuoteResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"quote": "Stay humble.", "author": "Anon"}


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url):
        return _FakeQuoteResponse()


def test_dashboard_quote_returns_quote(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)
    monkeypatch.setattr(books_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/books/dashboard-quote")

    assert resp.status_code == 200
    assert resp.json() == {"quote": "Stay humble.", "author": "Anon"}
