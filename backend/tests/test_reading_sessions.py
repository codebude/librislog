"""Tests for reading sessions: CRUD, re-read flow, and statistics integration."""

from typing import Any

from fastapi.testclient import TestClient


def _create_book(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    payload = {"title": "Book", "author": "Author", "page_count": 200, **kwargs}
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _read_again(client: TestClient, book_id: int) -> dict[str, Any]:
    resp = client.post(f"/api/books/{book_id}/read-again", json={})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_create_book_with_read_status_creates_session(client: TestClient) -> None:
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z")
    assert book["session_count"] == 1
    assert book["read_count"] == 1

    resp = client.get(f"/api/books/{book['id']}/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["status"] == "read"
    assert sessions[0]["read_number"] == 1
    assert sessions[0]["is_reread"] is False


def test_read_again_creates_second_session(client: TestClient) -> None:
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z")

    result = _read_again(client, book["id"])
    assert result["book"]["reading_status"] == "currently_reading"
    assert result["book"]["date_finished"] is None
    assert result["session"]["status"] == "currently_reading"
    assert result["session"]["is_current"] is True

    sessions = client.get(f"/api/books/{book['id']}/sessions").json()
    assert len(sessions) == 2
    statuses = {s["status"] for s in sessions}
    assert statuses == {"read", "currently_reading"}

    # The completed session keeps its original finish date.
    completed = next(s for s in sessions if s["status"] == "read")
    assert completed["date_finished"] == "2024-01-10T00:00:00Z"


def test_read_again_requires_finished_book(client: TestClient) -> None:
    book = _create_book(client, reading_status="want_to_read")
    resp = client.post(f"/api/books/{book['id']}/read-again", json={})
    assert resp.status_code == 422


def test_add_past_read_session(client: TestClient) -> None:
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z")
    resp = client.post(
        f"/api/books/{book['id']}/sessions",
        json={"status": "read", "date_started": "2023-05-01T00:00:00Z", "date_finished": "2023-05-08T00:00:00Z"},
    )
    assert resp.status_code == 201
    assert resp.json()["book"]["reading_status"] == "read"  # past read does not change the book

    sessions = client.get(f"/api/books/{book['id']}/sessions").json()
    assert len(sessions) == 2
    read_numbers = sorted(s["read_number"] for s in sessions)
    assert read_numbers == [1, 2]
    reread = next(s for s in sessions if s["read_number"] == 2)
    assert reread["is_reread"] is True


def test_delete_last_session_resets_book(client: TestClient) -> None:
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z")
    sessions = client.get(f"/api/books/{book['id']}/sessions").json()
    session_id = sessions[0]["id"]

    resp = client.delete(f"/api/books/{book['id']}/sessions/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["reading_status"] == "want_to_read"
    assert resp.json()["date_started"] is None
    assert resp.json()["date_finished"] is None


def test_sessions_are_scoped_to_owner(client: TestClient, create_user_with_key: Any) -> None:
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z")
    _other, other_key = create_user_with_key(email="other@example.com")

    resp = client.get(
        f"/api/books/{book['id']}/sessions",
        headers={"X-API-Key": other_key},
    )
    assert resp.status_code == 404


def test_statistics_count_completions_and_rereads(client: TestClient) -> None:
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z", page_count=200)
    _read_again(client, book["id"])

    resp = client.get("/api/statistics")
    data = resp.json()
    assert data["total_books"] == 1
    assert data["status_distribution"]["read"] == 0  # now currently_reading
    # The completed first read still counts as one completion.
    assert data["total_reads"] == 1
    assert data["reread_books"] == 0  # only one completed session so far
    assert data["page_buckets"]["pages_read"] == 200


def test_progress_scoped_to_session(client: TestClient) -> None:
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z", page_count=200)
    client.post(f"/api/books/{book['id']}/progress", json={"page": 200})

    _read_again(client, book["id"])

    # Latest progress now reflects the fresh (empty) current session: no entry yet.
    latest = client.get(f"/api/books/progress/latest?book_ids={book['id']}").json()
    assert latest == []
