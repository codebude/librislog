import io
import json
import zipfile
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlmodel import Session

from app.config import settings


def _parse_sse(text: str) -> list[dict[str, str | int | bool | None]]:
    """Parse a Server-Sent Events (SSE) text into a list of event dicts."""
    events: list[dict[str, str | int | bool | None]] = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def test_data_export_zip_contains_manifest_and_books_json(client: TestClient) -> None:
    create_resp = client.post(
        "/api/books",
        json={"title": "Dune", "author": "Frank Herbert", "page_count": 412, "reading_status": "read"},
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


def test_data_export_csv_format(client: TestClient) -> None:
    create_resp = client.post(
        "/api/books",
        json={"title": "Dune", "author": "Frank Herbert", "page_count": 412, "reading_status": "read"},
    )
    assert create_resp.status_code == 201

    export_resp = client.post(
        "/api/data/export",
        json={"datasets": ["books", "progress", "tags"], "format": "csv"},
    )
    assert export_resp.status_code == 200

    with zipfile.ZipFile(io.BytesIO(export_resp.content), "r") as zf:
        names = set(zf.namelist())
        assert "books.csv" in names
        assert "progress.csv" in names
        assert "tags.csv" in names
        books_csv = zf.read("books.csv").decode()
        assert "title,subtitle" in books_csv
        assert "Dune" in books_csv


def test_data_export_with_covers(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    covers_dir = tmp_path / "covers"
    covers_dir.mkdir()
    monkeypatch.setattr(settings, "covers_dir", str(covers_dir))

    create_resp = client.post(
        "/api/books",
        json={"title": "Dune", "author": "Frank Herbert", "page_count": 412, "reading_status": "read", "cover_url": "/api/covers/test_cover.jpg"},
    )
    assert create_resp.status_code == 201

    # Create a fake cover file
    (covers_dir / "test_cover.jpg").write_bytes(b"fake-cover")

    export_resp = client.post(
        "/api/data/export",
        json={"datasets": ["books", "covers"], "format": "json"},
    )
    assert export_resp.status_code == 200

    with zipfile.ZipFile(io.BytesIO(export_resp.content), "r") as zf:
        names = set(zf.namelist())
        assert "covers/test_cover.jpg" in names
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["counts"]["covers"] == 1


def test_data_export_missing_cover_skipped(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    covers_dir = tmp_path / "covers"
    covers_dir.mkdir()
    monkeypatch.setattr(settings, "covers_dir", str(covers_dir))

    create_resp = client.post(
        "/api/books",
        json={"title": "Dune", "author": "Frank Herbert", "page_count": 412, "reading_status": "read", "cover_url": "/api/covers/missing.jpg"},
    )
    assert create_resp.status_code == 201

    export_resp = client.post(
        "/api/data/export",
        json={"datasets": ["books", "covers"], "format": "json"},
    )
    assert export_resp.status_code == 200

    with zipfile.ZipFile(io.BytesIO(export_resp.content), "r") as zf:
        names = set(zf.namelist())
        assert "covers/missing.jpg" not in names
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["counts"]["covers"] == 0


def test_data_export_with_progress_and_tags(client: TestClient) -> None:
    create_resp = client.post(
        "/api/books",
        json={"title": "Dune", "author": "Frank Herbert", "reading_status": "read", "page_count": 412, "tags": "Sci-Fi"},
    )
    assert create_resp.status_code == 201
    book_id = create_resp.json()["id"]

    # Add a progress entry
    progress_resp = client.post(f"/api/books/{book_id}/progress", json={"page": 100})
    assert progress_resp.status_code == 201

    export_resp = client.post(
        "/api/data/export",
        json={"datasets": ["books", "progress", "tags"], "format": "json"},
    )
    assert export_resp.status_code == 200

    with zipfile.ZipFile(io.BytesIO(export_resp.content), "r") as zf:
        progress = json.loads(zf.read("progress.json"))
        assert len(progress) == 1
        assert progress[0]["page"] == 100
        assert progress[0]["book_title"] == "Dune"

        tags = json.loads(zf.read("tags.json"))
        assert len(tags) == 1
        assert tags[0]["name"] == "Sci-Fi"
        assert tags[0]["book_count"] == 1


def test_data_import_parse_and_suggest_mapping(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
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
    assert suggested["title"]["source"] == "Title"
    assert suggested["author"]["source"] == "Author"
    assert suggested["rating"]["source"] == "My Rating"


def test_data_import_mapping_crud(client: TestClient) -> None:
    save_resp = client.post(
        "/api/data/import/mappings",
        json={
            "name": "Goodreads",
            "source_fields": ["Title", "Author"],
            "mapping": {"title": {"source": "Title", "transform": None}, "author": {"source": "Author", "transform": None}},
        },
    )
    assert save_resp.status_code == 201
    saved = save_resp.json()

    list_resp = client.get("/api/data/import/mappings")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 2
    assert data[0]["is_predefined"] is True
    assert data[0]["name"] == "Goodreads Export"
    assert data[1]["is_predefined"] is False
    assert data[1]["name"] == "Goodreads"

    get_resp = client.get(f"/api/data/import/mappings/{saved['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Goodreads"

    delete_resp = client.delete(f"/api/data/import/mappings/{saved['id']}")
    assert delete_resp.status_code == 204

    get_missing = client.get(f"/api/data/import/mappings/{saved['id']}")
    assert get_missing.status_code == 404


def test_data_import_validate_and_execute_continue_on_error(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title,Author\nDune,Frank Herbert\n,No Title\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    validate_resp = client.post(
        "/api/data/import/validate",
        json={"file_id": file_id, "mapping": {"title": {"source": "Title", "transform": None}, "author": {"source": "Author", "transform": None}}},
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["valid"] is False

    preview_resp = client.post(
        "/api/data/import/preview",
        json={"file_id": file_id, "mapping": {"title": {"source": "Title", "transform": None}, "author": {"source": "Author", "transform": None}}},
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert preview["row_count"] == 2
    assert len(preview["preview_rows"]) == 2
    assert preview["preview_rows"][0]["transformed"]["title"] == "Dune"

    execute_resp = client.post(
        "/api/data/import/execute",
        json={
            "file_id": file_id,
            "mapping": {"title": {"source": "Title", "transform": None}, "author": {"source": "Author", "transform": None}},
            "import_mode": "continue_on_error",
        },
    )
    assert execute_resp.status_code == 200
    events = _parse_sse(execute_resp.text)
    complete = next(event for event in events if event.get("event") == "complete")
    assert complete["imported"] == 1
    assert complete["failed"] == 1


def test_data_import_execute_rollback_all_rolls_back(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
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
            "mapping": {"title": {"source": "Title", "transform": None}, "author": {"source": "Author", "transform": None}},
            "import_mode": "rollback_all",
        },
    )
    assert execute_resp.status_code == 200
    events = _parse_sse(execute_resp.text)
    assert any(event.get("event") == "error" for event in events)

    books = client.get("/api/books")
    assert books.status_code == 200
    assert books.json() == {"books": [], "total": 0}


def test_data_import_execute_rejects_invalid_target_mapping(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title\nDune\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    validate_resp = client.post(
        "/api/data/import/validate",
        json={"file_id": file_id, "mapping": {"invalid_field": {"source": "Title", "transform": None}}},
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["valid"] is False
    assert any(
        error.startswith("Invalid mapping target:")
        for error in validate_resp.json()["errors"]
    )


def test_data_import_validate_rejects_invalid_reading_status_enum(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title,Status\nDune,uxnread\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    validate_resp = client.post(
        "/api/data/import/validate",
        json={"file_id": file_id, "mapping": {"title": {"source": "Title", "transform": None}, "reading_status": {"source": "Status", "transform": None}}},
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()
    assert payload["valid"] is False
    assert any("reading_status" in error for error in payload["errors"])



def test_data_import_execute_progress_uses_date_finished_for_read_books(
    client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
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
                "title": {"source": "Title", "transform": None},
                "reading_status": {"source": "Status", "transform": None},
                "page_count": {"source": "Pages", "transform": None},
                "date_finished": {"source": "Date Finished", "transform": None},
            },
            "import_mode": "continue_on_error",
            "create_progress_for_read": True,
        },
    )
    assert execute_resp.status_code == 200

    books_resp = client.get("/api/books")
    assert books_resp.status_code == 200
    books_body = books_resp.json()
    assert books_body["total"] == 1
    book = books_body["books"][0]
    assert book["date_finished"] == "2024-01-15T10:30:00Z"

    progress_resp = client.get(f"/api/books/{book['id']}/progress")
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert len(progress) == 1
    assert progress[0]["page"] == 412
    assert progress[0]["created_at"] == "2024-01-15T10:30:00Z"


def test_data_import_execute_read_book_without_date_finished_skips_progress(
    client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title,Status,Pages\nDune,read,412\n"
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
                "title": {"source": "Title", "transform": None},
                "reading_status": {"source": "Status", "transform": None},
                "page_count": {"source": "Pages", "transform": None},
            },
            "import_mode": "continue_on_error",
            "create_progress_for_read": True,
        },
    )
    assert execute_resp.status_code == 200
    events = _parse_sse(execute_resp.text)
    complete = next(e for e in events if e.get("event") == "complete")
    assert complete["failed"] == 1
    assert complete["imported"] == 0

    books_resp = client.get("/api/books")
    assert books_resp.status_code == 200
    books_body = books_resp.json()
    assert books_body["total"] == 0


def test_data_export_no_datasets_raises_400(client: TestClient) -> None:
    resp = client.post("/api/data/export", json={"datasets": [], "format": "json"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Select at least one dataset to export."


def test_data_import_parse_unsupported_content_type(client: TestClient) -> None:
    resp = client.post(
        "/api/data/import/parse",
        files={"file": ("test.exe", b"invalid", "application/octet-stream")},
    )
    assert resp.status_code == 415
    assert resp.json()["detail"] == "Unsupported upload content type. Use CSV or JSON files."


def test_data_import_parse_invalid_json(client: TestClient) -> None:
    resp = client.post(
        "/api/data/import/parse",
        files={"file": ("test.json", b"{invalid", "application/json")},
    )
    assert resp.status_code == 400


def test_data_import_suggest_mapping_not_found(client: TestClient) -> None:
    resp = client.post("/api/data/import/suggest-mapping", json={"file_id": "nonexistent"})
    assert resp.status_code == 404


def test_data_import_mapping_update_existing(client: TestClient) -> None:
    # Save first
    client.post(
        "/api/data/import/mappings",
        json={
            "name": "UpdateMe",
            "source_fields": ["F1"],
            "mapping": {"title": {"source": "F1", "transform": None}},
        },
    )
    # Save again with same name
    resp = client.post(
        "/api/data/import/mappings",
        json={
            "name": "UpdateMe",
            "source_fields": ["F1", "F2"],
            "mapping": {"title": {"source": "F1", "transform": None}, "author": {"source": "F2", "transform": None}},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_fields"] == ["F1", "F2"]


def test_data_import_mapping_not_found(client: TestClient) -> None:
    resp = client.get("/api/data/import/mappings/99999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Import mapping not found."

    resp = client.delete("/api/data/import/mappings/99999")
    assert resp.status_code == 404


def test_data_import_validate_not_found(client: TestClient) -> None:
    resp = client.post(
        "/api/data/import/validate",
        json={"file_id": "nonexistent", "mapping": {}},
    )
    assert resp.status_code == 404


def test_data_import_execute_not_found(client: TestClient) -> None:
    resp = client.post(
        "/api/data/import/execute",
        json={"file_id": "nonexistent", "mapping": {}, "import_mode": "continue_on_error"},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert any("error.importFileNotFound" in str(event.get("message")) for event in events)


def test_data_import_mapping_integrity_error_new_mapping(client: TestClient, session: Session, monkeypatch: MonkeyPatch) -> None:
    from sqlalchemy.exc import IntegrityError

    call_count: list[int] = [0]
    original_commit = session.commit

    def fake_commit() -> None:
        call_count[0] += 1
        if call_count[0] == 2:
            raise IntegrityError("insert", "params", Exception("UNIQUE constraint failed: importmapping.name"))
        original_commit()

    monkeypatch.setattr(session, "commit", fake_commit)

    resp = client.post(
        "/api/data/import/mappings",
        json={"name": "Conflict", "source_fields": ["F1"], "mapping": {"title": {"source": "F1", "transform": None}}},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "A mapping with this name already exists."


def test_data_import_execute_rollback_when_not_completed(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title\nDune\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    from app.routers import data as data_module

    async def mock_execute(*args: object, **kwargs: object) -> AsyncGenerator[dict[str, str], None]:
        yield {"event": "progress", "message": "test"}

    monkeypatch.setattr(data_module, "execute_import", mock_execute)

    resp = client.post(
        "/api/data/import/execute",
        json={"file_id": file_id, "mapping": {"title": {"source": "Title", "transform": None}}, "import_mode": "continue_on_error"},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert any(event.get("event") == "progress" for event in events)


def test_data_import_execute_cancelled_error(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    import asyncio

    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title\nDune\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    from app.routers import data as data_module

    async def mock_execute(*args: object, **kwargs: object) -> AsyncGenerator[dict[str, str], None]:
        raise asyncio.CancelledError()
        yield {}  # make it an async generator

    monkeypatch.setattr(data_module, "execute_import", mock_execute)

    resp = client.post(
        "/api/data/import/execute",
        json={"file_id": file_id, "mapping": {"title": {"source": "Title", "transform": None}}, "import_mode": "continue_on_error"},
    )
    # StreamingResponse returns 200 before consuming the generator.
    # The generator raises CancelledError, which closes the stream.
    assert resp.status_code == 200


def test_data_import_execute_unexpected_error(client: TestClient, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path / "import_temp"))
    csv_payload = "Title\nDune\n"
    parse_resp = client.post(
        "/api/data/import/parse",
        files={"file": ("books.csv", csv_payload, "text/csv")},
    )
    file_id = parse_resp.json()["file_id"]

    from app.routers import data

    async def mock_execute(*args: object, **kwargs: object) -> AsyncGenerator[dict[str, str], None]:
        raise Exception("Unexpected")
        yield {}  # pragma: no cover

    monkeypatch.setattr(data, "execute_import", mock_execute)

    resp = client.post(
        "/api/data/import/execute",
        json={"file_id": file_id, "mapping": {"title": {"source": "Title", "transform": None}}, "import_mode": "continue_on_error"},
    )
    events = _parse_sse(resp.text)
    assert any(event.get("message") == "error.importExecutionFailed" for event in events)
