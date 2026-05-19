import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings


def _parse_sse(text: str) -> list[dict]:
    events: list[dict] = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def test_data_export_zip_contains_manifest_and_books_json(client: TestClient):
    create_resp = client.post(
        "/api/books",
        json={"title": "Dune", "author": "Frank Herbert", "reading_status": "read"},
    )
    assert create_resp.status_code == 201

    export_resp = client.post(
        "/api/data/export",
        json={"datasets": ["books", "progress", "tags", "covers"], "format": "json"},
    )
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"] == "application/zip"
    assert "attachment; filename=" in export_resp.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(export_resp.content), "r") as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "books.json" in names
        assert "progress.json" in names
        assert "tags.json" in names
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["counts"]["books"] == 1
        books = json.loads(zf.read("books.json"))
        assert books[0]["title"] == "Dune"


def test_data_import_parse_and_suggest_mapping(client: TestClient):
    csv_payload = "Title,Author,My Rating\nDune,Frank Herbert,5\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    assert parse_resp.status_code == 200
    parsed = parse_resp.json()
    assert parsed["format"] == "csv"
    assert parsed["row_count"] == 1
    assert parsed["source_fields"] == ["Title", "Author", "My Rating"]

    suggest_resp = client.post(
        "/api/data/import/suggest-mapping",
        json={"file_id": parsed["file_id"]},
    )
    assert suggest_resp.status_code == 200
    suggested = suggest_resp.json()["suggested_mapping"]
    assert suggested["Title"] == "title"
    assert suggested["Author"] == "author"
    assert suggested["My Rating"] == "rating"


def test_data_import_mapping_crud(client: TestClient):
    save_resp = client.post(
        "/api/data/import/mappings",
        json={
            "name": "Goodreads",
            "source_fields": ["Title", "Author"],
            "mapping": {"Title": "title", "Author": "author"},
        },
    )
    assert save_resp.status_code == 201
    saved = save_resp.json()

    list_resp = client.get("/api/data/import/mappings")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = client.get(f"/api/data/import/mappings/{saved['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Goodreads"

    delete_resp = client.delete(f"/api/data/import/mappings/{saved['id']}")
    assert delete_resp.status_code == 204

    get_missing = client.get(f"/api/data/import/mappings/{saved['id']}")
    assert get_missing.status_code == 404


def test_data_import_validate_and_execute_continue_on_error(client: TestClient):
    csv_payload = "Title,Author\nDune,Frank Herbert\n,No Title\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    validate_resp = client.post(
        "/api/data/import/validate",
        json={"file_id": file_id, "mapping": {"Title": "title", "Author": "author"}},
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["valid"] is False

    execute_resp = client.post(
        "/api/data/import/execute",
        json={
            "file_id": file_id,
            "mapping": {"Title": "title", "Author": "author"},
            "import_mode": "continue_on_error",
        },
    )
    assert execute_resp.status_code == 200
    events = _parse_sse(execute_resp.text)
    complete = next(event for event in events if event.get("event") == "complete")
    assert complete["imported"] == 1
    assert complete["failed"] == 1


def test_data_import_execute_rollback_all_rolls_back(client: TestClient):
    csv_payload = "Title,Author\nDune,Frank Herbert\n,Missing\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    execute_resp = client.post(
        "/api/data/import/execute",
        json={
            "file_id": file_id,
            "mapping": {"Title": "title", "Author": "author"},
            "import_mode": "rollback_all",
        },
    )
    assert execute_resp.status_code == 200
    events = _parse_sse(execute_resp.text)
    assert any(event.get("event") == "error" for event in events)

    books = client.get("/api/books")
    assert books.status_code == 200
    assert books.json() == []


def test_data_import_execute_rejects_invalid_target_mapping(client: TestClient):
    csv_payload = "Title\nDune\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    validate_resp = client.post(
        "/api/data/import/validate",
        json={"file_id": file_id, "mapping": {"Title": "invalid_field"}},
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["valid"] is False
    assert any(
        error.startswith("Invalid mapping target:")
        for error in validate_resp.json()["errors"]
    )


def test_data_import_validate_rejects_invalid_reading_status_enum(client: TestClient):
    csv_payload = "Title,Status\nDune,uxnread\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    validate_resp = client.post(
        "/api/data/import/validate",
        json={"file_id": file_id, "mapping": {"Title": "title", "Status": "reading_status"}},
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()
    assert payload["valid"] is False
    assert any("reading_status" in error for error in payload["errors"])


def test_data_import_execute_deletes_temp_file_after_completion(client: TestClient):
    csv_payload = "Title\nDune\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    temp_file = Path("data/import_temp/1") / f"{file_id}.json"
    assert temp_file.exists()

    execute_resp = client.post(
        "/api/data/import/execute",
        json={
            "file_id": file_id,
            "mapping": {"Title": "title"},
            "import_mode": "continue_on_error",
        },
    )
    assert execute_resp.status_code == 200
    events = _parse_sse(execute_resp.text)
    assert any(event.get("event") == "complete" for event in events)
    assert not temp_file.exists()


def test_data_import_execute_progress_uses_date_finished_for_read_books(
    client: TestClient, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title,Status,Pages,Date Finished\nDune,read,412,2024-01-15T10:30:00Z\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    execute_resp = client.post(
        "/api/data/import/execute",
        json={
            "file_id": file_id,
            "mapping": {
                "Title": "title",
                "Status": "reading_status",
                "Pages": "page_count",
                "Date Finished": "date_finished",
            },
            "import_mode": "continue_on_error",
            "create_progress_for_read": True,
        },
    )
    assert execute_resp.status_code == 200

    books_resp = client.get("/api/books")
    assert books_resp.status_code == 200
    books = books_resp.json()
    assert len(books) == 1
    book = books[0]
    assert book["date_finished"] == "2024-01-15T10:30:00Z"

    progress_resp = client.get(f"/api/books/{book['id']}/progress")
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert len(progress) == 1
    assert progress[0]["page"] == 412
    assert progress[0]["created_at"] == "2024-01-15T10:30:00Z"


def test_data_import_execute_progress_falls_back_to_now_without_date_finished(
    client: TestClient, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title,Status,Pages\nDune,read,412\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    before = datetime.now(timezone.utc)
    execute_resp = client.post(
        "/api/data/import/execute",
        json={
            "file_id": file_id,
            "mapping": {
                "Title": "title",
                "Status": "reading_status",
                "Pages": "page_count",
            },
            "import_mode": "continue_on_error",
            "create_progress_for_read": True,
        },
    )
    after = datetime.now(timezone.utc)
    assert execute_resp.status_code == 200

    books_resp = client.get("/api/books")
    assert books_resp.status_code == 200
    books = books_resp.json()
    assert len(books) == 1
    book = books[0]
    assert book["date_finished"] is None

    progress_resp = client.get(f"/api/books/{book['id']}/progress")
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert len(progress) == 1

    created_at = datetime.fromisoformat(progress[0]["created_at"].replace("Z", "+00:00"))
    assert before <= created_at <= after


def test_data_import_execute_progress_uses_date_only_finished_date(
    client: TestClient, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title,Status,Pages,Date Finished\nDune,read,412,2024-01-15\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    execute_resp = client.post(
        "/api/data/import/execute",
        json={
            "file_id": file_id,
            "mapping": {
                "Title": "title",
                "Status": "reading_status",
                "Pages": "page_count",
                "Date Finished": "date_finished",
            },
            "import_mode": "continue_on_error",
            "create_progress_for_read": True,
        },
    )
    assert execute_resp.status_code == 200

    books_resp = client.get("/api/books")
    assert books_resp.status_code == 200
    books = books_resp.json()
    assert len(books) == 1
    book = books[0]

    progress_resp = client.get(f"/api/books/{book['id']}/progress")
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert len(progress) == 1
    assert progress[0]["created_at"] == "2024-01-15T00:00:00Z"
