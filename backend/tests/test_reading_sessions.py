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


def test_deleting_last_session_clears_progress_log(client: TestClient) -> None:
    """When no session remains, the progress log must be reset too."""
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z", page_count=200)
    client.post(f"/api/books/{book['id']}/progress", json={"page": 200})
    assert len(client.get(f"/api/books/{book['id']}/progress").json()) == 1

    sessions = client.get(f"/api/books/{book['id']}/sessions").json()
    client.delete(f"/api/books/{book['id']}/sessions/{sessions[0]['id']}")

    # Book reset to want_to_read, progress log empty.
    book = client.get(f"/api/books/{book['id']}").json()
    assert book["reading_status"] == "want_to_read"
    assert client.get(f"/api/books/{book['id']}/progress").json() == []


def test_deleting_a_session_removes_its_progress_entries(client: TestClient) -> None:
    """Progress entries attached to a deleted session must be removed with it."""
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z", page_count=200)
    client.post(f"/api/books/{book['id']}/progress", json={"page": 100})
    client.post(f"/api/books/{book['id']}/progress", json={"page": 200})
    assert len(client.get(f"/api/books/{book['id']}/progress").json()) == 2

    # Add a re-read so there is a second session to keep.
    _read_again(client, book["id"])
    client.post(f"/api/books/{book['id']}/transition-status", json={"new_status": "read"})

    # The first session (the 2024 read) owns the progress entries.
    sessions = client.get(f"/api/books/{book['id']}/sessions").json()
    first_session = next(s for s in sessions if s["date_finished"] == "2024-01-10T00:00:00Z")
    client.delete(f"/api/books/{book['id']}/sessions/{first_session['id']}")

    # The deleted session's progress must be gone; the re-read session has none.
    remaining_progress = client.get(f"/api/books/{book['id']}/progress").json()
    assert remaining_progress == []
    book = client.get(f"/api/books/{book['id']}").json()
    assert book["reading_status"] == "read"


def test_unrelated_patch_does_not_change_sessions(client: TestClient) -> None:
    """Editing an unrelated field must never rewrite a reading session."""
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z")
    # Add an older past read.
    client.post(
        f"/api/books/{book['id']}/sessions",
        json={"status": "read", "date_started": "2020-01-01T00:00:00Z", "date_finished": "2020-02-01T00:00:00Z"},
    )
    before = client.get(f"/api/books/{book['id']}/sessions").json()

    # Change only the rating.
    resp = client.patch(f"/api/books/{book['id']}", json={"rating": 5})
    assert resp.status_code == 200

    after = client.get(f"/api/books/{book['id']}/sessions").json()
    assert len(after) == 2
    # Sessions must be unchanged: the 2020 read stays 2020-01-01..2020-02-01.
    by_id = {s["id"]: s for s in after}
    for b in before:
        a = by_id[b["id"]]
        assert a["date_started"] == b["date_started"]
        assert a["date_finished"] == b["date_finished"]


def test_delete_non_current_session_remirrors_book(client: TestClient) -> None:
    """Deleting a non-current session must re-derive the book mirror."""
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z")
    # Add an older past read (2020). The mirror stays on the 2024 read.
    client.post(
        f"/api/books/{book['id']}/sessions",
        json={"status": "read", "date_started": "2020-01-01T00:00:00Z", "date_finished": "2020-02-01T00:00:00Z"},
    )
    sessions = client.get(f"/api/books/{book['id']}/sessions").json()
    # The 2024 read (date_finished 2024-01-10) is the "latest" session.
    latest = next(s for s in sessions if s["date_finished"] == "2024-01-10T00:00:00Z")

    resp = client.delete(f"/api/books/{book['id']}/sessions/{latest['id']}")
    assert resp.status_code == 200
    # Mirror must now point at the remaining 2020 read.
    assert resp.json()["date_started"] == "2020-01-01T00:00:00Z"
    assert resp.json()["date_finished"] == "2020-02-01T00:00:00Z"


def test_progress_rejects_foreign_session(client: TestClient, create_user_with_key: Any) -> None:
    book_a = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z", page_count=200)
    session_a = client.get(f"/api/books/{book_a['id']}/sessions").json()[0]

    book_b = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z", page_count=200)

    resp = client.post(
        f"/api/books/{book_b['id']}/progress",
        json={"page": 40, "session_id": session_a["id"]},
    )
    assert resp.status_code == 404


def test_pages_read_counts_read_book_without_finish_date(client: TestClient) -> None:
    """A read book without a finish date still contributes to pages_read."""
    _create_book(client, reading_status="read", page_count=70)
    resp = client.get("/api/statistics")
    data = resp.json()
    assert data["page_buckets"]["pages_read"] == 70
    assert data["total_reads"] == 1


def test_completed_sessions_timeline_endpoint(client: TestClient) -> None:
    """The completed-reads timeline endpoint returns one row per completed read."""
    book = _create_book(client, reading_status="read", date_started="2024-01-01T00:00:00Z", date_finished="2024-01-10T00:00:00Z")
    _read_again(client, book["id"])
    client.post(f"/api/books/{book['id']}/transition-status", json={"new_status": "read"})

    resp = client.get("/api/books/sessions")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2
    reread_rows = [r for r in rows if r["is_reread"]]
    assert len(reread_rows) == 1
    assert reread_rows[0]["read_number"] == 2


def test_open_session_never_keeps_a_finish_date(client: TestClient) -> None:
    """A currently_reading session must not carry a finish date."""
    book = _create_book(client, reading_status="currently_reading", date_started="2024-01-01T00:00:00Z")
    session_id = client.get(f"/api/books/{book['id']}/sessions").json()[0]["id"]

    resp = client.patch(
        f"/api/books/{book['id']}/sessions/{session_id}",
        json={"date_finished": "2024-02-01T00:00:00Z"},
    )
    assert resp.status_code == 200
    session = resp.json()["session"]
    assert session["status"] == "currently_reading"
    assert session["date_finished"] is None
    assert session["is_current"] is True
