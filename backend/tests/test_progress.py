from fastapi.testclient import TestClient


def _create_book(client: TestClient, **kwargs) -> dict:
    payload = {"title": "Progress Test Book", **kwargs}
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201
    return resp.json()


def test_create_progress_entry(client: TestClient):
    book = _create_book(client, page_count=200)
    resp = client.post(f"/api/books/{book['id']}/progress", json={"page": 50})
    assert resp.status_code == 201
    data = resp.json()
    assert data["book_id"] == book["id"]
    assert data["page"] == 50
    assert "created_at" in data


def test_create_progress_page_exceeds_page_count(client: TestClient):
    book = _create_book(client, page_count=200)
    resp = client.post(f"/api/books/{book['id']}/progress", json={"page": 300})
    assert resp.status_code == 422


def test_create_progress_no_page_count_allowed(client: TestClient):
    book = _create_book(client, page_count=None)
    resp = client.post(f"/api/books/{book['id']}/progress", json={"page": 50})
    assert resp.status_code == 201
    assert resp.json()["page"] == 50


def test_create_progress_wrong_user_returns_404(client: TestClient, create_user_with_key):
    book = _create_book(client)
    user2, key2 = create_user_with_key(email="other@example.com")
    c2 = TestClient(client.app)
    c2.headers.update({"X-API-Key": key2})
    resp = c2.post(f"/api/books/{book['id']}/progress", json={"page": 10})
    assert resp.status_code == 404


def test_list_progress_entries_ordered_by_date(client: TestClient):
    book = _create_book(client, page_count=200)
    client.post(f"/api/books/{book['id']}/progress", json={"page": 10})
    client.post(f"/api/books/{book['id']}/progress", json={"page": 50})
    client.post(f"/api/books/{book['id']}/progress", json={"page": 100})

    resp = client.get(f"/api/books/{book['id']}/progress")
    assert resp.status_code == 200
    data = resp.json()
    # Most recent first
    assert data[0]["page"] == 100
    assert data[1]["page"] == 50
    assert data[2]["page"] == 10


def test_list_progress_empty(client: TestClient):
    book = _create_book(client)
    resp = client.get(f"/api/books/{book['id']}/progress")
    assert resp.status_code == 200
    assert resp.json() == []


def test_delete_progress_entry(client: TestClient):
    book = _create_book(client, page_count=200)
    entry = client.post(f"/api/books/{book['id']}/progress", json={"page": 50}).json()

    resp = client.delete(f"/api/books/{book['id']}/progress/{entry['id']}")
    assert resp.status_code == 204

    resp = client.get(f"/api/books/{book['id']}/progress")
    assert resp.json() == []


def test_delete_progress_entry_wrong_user_returns_404(client: TestClient, create_user_with_key):
    book = _create_book(client)
    entry = client.post(f"/api/books/{book['id']}/progress", json={"page": 10}).json()
    user2, key2 = create_user_with_key(email="other@example.com")
    c2 = TestClient(client.app)
    c2.headers.update({"X-API-Key": key2})
    resp = c2.delete(f"/api/books/{book['id']}/progress/{entry['id']}")
    assert resp.status_code == 404


def test_latest_progress_batch(client: TestClient):
    book1 = _create_book(client, page_count=200)
    book2 = _create_book(client, page_count=300)
    book3 = _create_book(client, page_count=100)

    client.post(f"/api/books/{book1['id']}/progress", json={"page": 20})
    client.post(f"/api/books/{book1['id']}/progress", json={"page": 50})
    client.post(f"/api/books/{book2['id']}/progress", json={"page": 150})

    resp = client.get(
        f"/api/books/progress/latest?book_ids={book1['id']},{book2['id']},{book3['id']}"
    )
    assert resp.status_code == 200
    data = resp.json()
    by_book = {item["book_id"]: item["current_page"] for item in data}
    assert by_book[book1["id"]] == 50
    assert by_book[book2["id"]] == 150
    assert book3["id"] not in by_book


def test_latest_progress_batch_empty_ids(client: TestClient):
    resp = client.get("/api/books/progress/latest?book_ids=")
    assert resp.status_code == 200
    assert resp.json() == []


def test_book_delete_cascades_progress(client: TestClient):
    book = _create_book(client, page_count=200)
    client.post(f"/api/books/{book['id']}/progress", json={"page": 10})
    client.post(f"/api/books/{book['id']}/progress", json={"page": 50})

    client.delete(f"/api/books/{book['id']}")
    resp = client.get(f"/api/books/{book['id']}/progress")
    assert resp.status_code == 404


def test_create_progress_appends_new_entry(client: TestClient):
    """Each create call adds a new row (append-only log)."""
    book = _create_book(client, page_count=200)
    client.post(f"/api/books/{book['id']}/progress", json={"page": 30})
    client.post(f"/api/books/{book['id']}/progress", json={"page": 30})
    resp = client.get(f"/api/books/{book['id']}/progress")
    assert len(resp.json()) == 2
