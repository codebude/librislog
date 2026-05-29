"""Unit tests for app.services.data_import module."""

import json
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest import MonkeyPatch
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.config import settings
from app.models import Book, ReadingStatus, User, UserRole
from app.schemas import ImportFieldConfig
from app.services import data_import as di


# ── _display_value / _format_value_error ──────────────────────────────────────

def test_display_value_none() -> None:
    assert di._display_value(None) == "null"


def test_display_value_empty_string() -> None:
    assert di._display_value("") == '""'


def test_format_value_error_without_hint() -> None:
    msg = di._format_value_error("field", "expected", "value")
    assert "Hint" not in msg


# ── compute_schema_fingerprint ────────────────────────────────────────────────

def test_compute_schema_fingerprint() -> None:
    fp1 = di.compute_schema_fingerprint(["a", "b"])
    fp2 = di.compute_schema_fingerprint(["b", "a"])
    assert fp1 == fp2
    assert len(fp1) == 64


# ── _to_flat_row ──────────────────────────────────────────────────────────────

def test_to_flat_row_nested_dict_raises() -> None:
    with pytest.raises(ValueError, match="error.importNestedValuesNotSupported"):
        di._to_flat_row({"key": {"nested": 1}})


def test_to_flat_row_nested_list_raises() -> None:
    with pytest.raises(ValueError, match="error.importNestedValuesNotSupported"):
        di._to_flat_row({"key": [1, 2]})


# ── parse_upload ──────────────────────────────────────────────────────────────

def test_parse_upload_empty_file() -> None:
    with pytest.raises(ValueError, match="error.importEmptyFile"):
        di.parse_upload(b"", "test.csv", 1)


def test_parse_upload_file_too_large(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_import_file_size_mb", 0)
    with pytest.raises(ValueError, match="error.importFileTooLarge"):
        di.parse_upload(b"x", "test.csv", 1)


def test_parse_upload_csv_missing_header() -> None:
    with pytest.raises(ValueError, match="error.importMissingHeader"):
        di.parse_upload(b"\n", "test.csv", 1)


def test_parse_upload_json_not_array() -> None:
    payload = json.dumps({"key": "value"}).encode()
    with pytest.raises(ValueError, match="error.importJsonMustBeArray"):
        di.parse_upload(payload, "test.json", 1)


def test_parse_upload_json_rows_not_objects() -> None:
    payload = json.dumps(["not_an_object"]).encode()
    with pytest.raises(ValueError, match="error.importJsonRowsMustBeObjects"):
        di.parse_upload(payload, "test.json", 1)


def test_parse_upload_json_flat_row_keys(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    payload = json.dumps([{"a": 1, "b": 2}]).encode()
    result = di.parse_upload(payload, "test.json", 1)
    assert result["format"] == "json"
    assert sorted(result["source_fields"]) == ["a", "b"]


def test_parse_upload_too_many_rows(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_import_row_count", 1)
    csv = "Title\nBook1\nBook2\n"
    with pytest.raises(ValueError, match="error.importTooManyRows"):
        di.parse_upload(csv.encode(), "test.csv", 1)


def test_parse_upload_unsupported_file_type() -> None:
    with pytest.raises(ValueError, match="error.importUnsupportedFileType"):
        di.parse_upload(b"x", "test.txt", 1)


def test_parse_upload_temp_file_create_failed(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    # Force FileExistsError on every attempt
    call_count = 0

    def _always_exists(*args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        raise FileExistsError("exists")

    monkeypatch.setattr(Path, "open", _always_exists)
    with pytest.raises(ValueError, match="error.importTempFileCreateFailed"):
        di.parse_upload(b"Title\nBook\n", "test.csv", 1)
    assert call_count == 5


# ── load_parsed_upload / delete_parsed_upload ─────────────────────────────────

def test_load_parsed_upload_missing_file() -> None:
    with pytest.raises(FileNotFoundError, match="error.importFileNotFound"):
        di.load_parsed_upload("nonexistent", 1)


def test_delete_parsed_upload_missing_ok(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    # Should not raise
    di.delete_parsed_upload("missing", 1)


# ── suggest_mapping ───────────────────────────────────────────────────────────

def test_suggest_mapping_direct_alias() -> None:
    # "book title" should directly match via _ALIASES
    result = di.suggest_mapping(["book title"])
    assert result["title"].source == "book title"


def test_suggest_mapping_compact_match() -> None:
    # "booktitle" should match "book title" -> "title"
    result = di.suggest_mapping(["booktitle"])
    assert result["title"].source == "booktitle"


def test_suggest_mapping_no_match() -> None:
    result = di.suggest_mapping(["unknown_field"])
    assert "unknown_field" not in {cfg.source for cfg in result.values()}


# ── _parse_int ────────────────────────────────────────────────────────────────

def test_parse_int_whitespace_only() -> None:
    assert di._parse_int("   ", "field") is None


def test_parse_int_decimal_raises() -> None:
    with pytest.raises(ValueError, match="Whole numbers only"):
        di._parse_int("3.14", "field")


def test_parse_int_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Use digits only"):
        di._parse_int("abc", "field")


# ── _parse_year ───────────────────────────────────────────────────────────────

def test_parse_year_from_date_string() -> None:
    assert di._parse_year("2024-05-20", "field") == 2024


def test_parse_year_whitespace_only() -> None:
    assert di._parse_year("   ", "field") is None


def test_parse_year_no_year_found() -> None:
    with pytest.raises(ValueError, match="a year"):
        di._parse_year("no year here", "field")


# ── _parse_datetime ───────────────────────────────────────────────────────────

def test_parse_datetime_datetime_object() -> None:
    dt = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
    result = di._parse_datetime(dt, "field")
    assert result == dt


def test_parse_datetime_z_suffix() -> None:
    result = di._parse_datetime("2024-01-15T10:30:00Z", "field")
    assert result == datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)


def test_parse_datetime_invalid_iso() -> None:
    with pytest.raises(ValueError, match="ISO date or datetime"):
        di._parse_datetime("not-a-date", "field")


# ── _normalize_language ───────────────────────────────────────────────────────

def test_normalize_language_empty_after_strip() -> None:
    assert di._normalize_language("   ") is None


def test_normalize_language_not_two_chars() -> None:
    with pytest.raises(ValueError, match="2-letter ISO code"):
        di._normalize_language("ENG")


def test_normalize_language_not_alpha() -> None:
    with pytest.raises(ValueError, match="2-letter ISO code"):
        di._normalize_language("E1")


def test_normalize_language_valid() -> None:
    assert di._normalize_language("en") == "EN"


# ── _parse_reading_status ─────────────────────────────────────────────────────

def test_parse_reading_status_invalid() -> None:
    with pytest.raises(ValueError, match="reading_status"):
        di._parse_reading_status("invalid_status")


# ── _mapped_row ───────────────────────────────────────────────────────────────

def test_mapped_row_skips_empty_source() -> None:
    result = di._mapped_row(
        {"A": "1"},
        {"title": ImportFieldConfig(source=""), "author": ImportFieldConfig(source="B")},
        {},
        {},
    )
    assert result == {"author": ""}  # row.get("B") returns None -> ""


# ── _validate_mapping ─────────────────────────────────────────────

def test_validate_mapping_empty_mapping() -> None:
    warnings, errors = di._validate_mapping({}, {"A"})
    assert any("title" in e for e in errors)


def test_validate_mapping_invalid_targets() -> None:
    mapping = {"title": ImportFieldConfig(source="A"), "invalid_field": ImportFieldConfig(source="B")}
    warnings, errors = di._validate_mapping(mapping, {"A", "B"})
    assert any("Invalid mapping target" in e for e in errors)


def test_validate_mapping_source_missing() -> None:
    mapping = {"title": ImportFieldConfig(source="A"), "author": ImportFieldConfig(source="C")}
    warnings, errors = di._validate_mapping(mapping, {"A"})
    assert any("Mapped source field missing in file: C" in w for w in warnings)


def test_validate_mapping_transform_invalid() -> None:
    mapping = {"title": ImportFieldConfig(source="A", transform="bad syntax {{")}
    warnings, errors = di._validate_mapping(mapping, {"A"})
    assert any(e.startswith("\x1ftitle\x1f") for e in errors)


def test_validate_mapping_transform_valid() -> None:
    mapping = {"title": ImportFieldConfig(source="A", transform="value.upper()")}
    warnings, errors = di._validate_mapping(mapping, {"A"})
    assert len(errors) == 0


# ── preview_import ────────────────────────────────────────────────────────────

def test_preview_import_basic(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "author": "Author"}],
        "source_fields": ["title", "author"],
    }
    file_id = "test_preview"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "author": ImportFieldConfig(source="author")}
    )
    assert len(result["preview_rows"]) == 1
    assert result["preview_rows"][0]["transformed"]["title"] == "Book"
    assert result["row_count"] == 1


def test_preview_import_with_transform(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "book", "author": "author"}],
        "source_fields": ["title", "author"],
    }
    file_id = "test_preview_transform"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id,
        user,
        {
            "title": ImportFieldConfig(source="title", transform="value.upper()"),
            "author": ImportFieldConfig(source="author"),
        },
    )
    assert result["preview_rows"][0]["transformed"]["title"] == "BOOK"


def test_preview_import_mapping_errors(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book"}],
        "source_fields": ["title"],
    }
    file_id = "test_preview_errors"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(file_id, user, {"invalid_target": ImportFieldConfig(source="title")})
    assert len(result["preview_rows"]) == 0
    assert len(result["errors"]) > 0


# ── validate_import ───────────────────────────────────────────────────────────

def _create_test_user(session: Session) -> User:
    """Create and return a test user for import tests."""
    from app.auth import get_password_hash
    user = User(
        firstname="Test",
        lastname="User",
        email="test_data_import@example.com",
        role=UserRole.user,
        hashed_password=get_password_hash("secret123"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_validate_import_rating_out_of_range(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "rating": "99"}],
        "source_fields": ["title", "rating"],
    }
    file_id = "test_rating"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(file_id, user, {"title": ImportFieldConfig(source="title"), "rating": ImportFieldConfig(source="rating")}, session)
    assert any("rating out of range" in w for w in result["warnings"])


def test_validate_import_date_started_after_finished(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "started": "2024-02-01", "finished": "2024-01-01"}],
        "source_fields": ["title", "started", "finished"],
    }
    file_id = "test_dates"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(file_id, user, {"title": ImportFieldConfig(source="title"), "date_started": ImportFieldConfig(source="started"), "date_finished": ImportFieldConfig(source="finished")}, session)
    assert any("date_started is after date_finished" in e for e in result["errors"])


def test_validate_import_progress_warning_no_pages(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "status": "read"}],
        "source_fields": ["title", "status"],
    }
    file_id = "test_progress"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "reading_status": ImportFieldConfig(source="status")}, session, create_progress_for_read=True
    )
    assert any("marked as 'read' but has no page count" in w for w in result["warnings"])


def test_validate_import_isbn_already_exists(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    # Create existing book with ISBN
    existing = Book(title="Existing", isbn="1234567890", user_id=user.id)
    session.add(existing)
    session.commit()

    payload = {
        "rows": [{"title": "Book", "isbn": "1234567890"}],
        "source_fields": ["title", "isbn"],
    }
    file_id = "test_isbn"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(file_id, user, {"title": ImportFieldConfig(source="title"), "isbn": ImportFieldConfig(source="isbn")}, session)
    assert any("ISBN already exists" in w for w in result["warnings"])


def test_validate_import_no_isbns(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Cover the path where isbns_in_file is empty (no DB query)."""
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book"}],
        "source_fields": ["title"],
    }
    file_id = "test_no_isbn"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(file_id, user, {"title": ImportFieldConfig(source="title")}, session)
    assert result["valid"] is True


def test_validate_import_missing_title(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": ""}],
        "source_fields": ["title"],
    }
    file_id = "test_missing_title"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(file_id, user, {"title": ImportFieldConfig(source="title")}, session)
    assert any("missing required field 'title'" in e for e in result["errors"])


def test_validate_import_value_error_caught(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "pages": "abc"}],
        "source_fields": ["title", "pages"],
    }
    file_id = "test_value_error"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(file_id, user, {"title": ImportFieldConfig(source="title"), "page_count": ImportFieldConfig(source="pages")}, session)
    assert any("Row 1:" in e for e in result["errors"])


def test_validate_import_cover_url_warns_on_non_url(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "cover": "/local/path/image.jpg"}],
        "source_fields": ["title", "cover"],
    }
    file_id = "test_cover_nonurl"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "cover_url": ImportFieldConfig(source="cover")}, session
    )
    assert any("cover_url must be an HTTP(S) URL" in w for w in result["warnings"])


def test_validate_import_cover_url_accepts_valid_url(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "cover": "https://example.com/cover.jpg"}],
        "source_fields": ["title", "cover"],
    }
    file_id = "test_cover_valid"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "cover_url": ImportFieldConfig(source="cover")}, session
    )
    assert not any("cover_url" in w for w in result["warnings"])


# ── execute_import ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_execute_import_mapping_errors(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book"}],
        "source_fields": ["title"],
    }
    file_id = "test_exec_map"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id, user, {"invalid_target": ImportFieldConfig(source="title")}, session, "continue_on_error"
    ):
        events.append(event)
    assert any("Invalid mapping target" in e.get("message", "") for e in events)


@pytest.mark.anyio
async def test_execute_import_rating_out_of_range_set_to_none(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "rating": "99"}],
        "source_fields": ["title", "rating"],
    }
    file_id = "test_exec_rating"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "rating": ImportFieldConfig(source="rating")}, session, "continue_on_error"
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["imported"] == 1


@pytest.mark.anyio
async def test_execute_import_date_started_after_finished(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "started": "2024-02-01", "finished": "2024-01-01"}],
        "source_fields": ["title", "started", "finished"],
    }
    file_id = "test_exec_dates"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "date_started": ImportFieldConfig(source="started"), "date_finished": ImportFieldConfig(source="finished")}, session, "continue_on_error"
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["failed"] == 1


@pytest.mark.anyio
async def test_execute_import_cover_download(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path / "covers"))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "cover": "https://example.com/cover.jpg"}],
        "source_fields": ["title", "cover"],
    }
    file_id = "test_exec_cover"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    async def _fake_download(url: str, covers_dir: str, client: Any, user_id: int) -> str:
        return "cover_123.jpg"

    monkeypatch.setattr(di, "download_cover", _fake_download)

    events = []
    async for event in di.execute_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "cover_url": ImportFieldConfig(source="cover")}, session, "continue_on_error"
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["imported"] == 1


@pytest.mark.anyio
async def test_execute_import_progress_date_naive_tz_fix(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    # Provide a naive datetime for date_finished to trigger tz fix at line 511
    payload = {
        "rows": [{"title": "Book", "status": "read", "pages": "100", "finished": "2024-01-15T10:30:00"}],
        "source_fields": ["title", "status", "pages", "finished"],
    }
    file_id = "test_exec_tz"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "reading_status": ImportFieldConfig(source="status"), "page_count": ImportFieldConfig(source="pages"), "date_finished": ImportFieldConfig(source="finished")},
        session, "continue_on_error",
        create_progress_for_read=True,
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["imported"] == 1


@pytest.mark.anyio
async def test_execute_import_rollback_all_commit(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book1"}, {"title": "Book2"}],
        "source_fields": ["title"],
    }
    file_id = "test_exec_rollback"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id, user, {"title": ImportFieldConfig(source="title")}, session, "rollback_all"
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["imported"] == 2


@pytest.mark.anyio
async def test_execute_import_missing_title_row(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": ""}],
        "source_fields": ["title"],
    }
    file_id = "test_exec_missing_title"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id, user, {"title": ImportFieldConfig(source="title")}, session, "continue_on_error"
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["failed"] == 1


@pytest.mark.anyio
async def test_execute_import_rollback_all_error(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book1"}, {"title": ""}],
        "source_fields": ["title"],
    }
    file_id = "test_exec_rollback_err"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id, user, {"title": ImportFieldConfig(source="title")}, session, "rollback_all"
    ):
        events.append(event)
    assert any(e["event"] == "error" and "All changes rolled back" in e.get("message", "") for e in events)


@pytest.mark.anyio
async def test_execute_import_progress_naive_date_finished(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Pass a naive datetime object directly to trigger line 510-511."""
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    # Provide a datetime object directly (not a string) so _parse_datetime returns it as-is
    # but it's naive, triggering the tz fix at line 510-511
    payload = {
        "rows": [
            {
                "title": "Book",
                "status": "read",
                "pages": "100",
                # Use a datetime object directly - _parse_datetime will return it as-is at line 269
                "finished": datetime(2024, 1, 15, 10, 30, 0),
            }
        ],
        "source_fields": ["title", "status", "pages", "finished"],
    }
    file_id = "test_exec_naive_dt"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, default=str))

    events = []
    async for event in di.execute_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "reading_status": ImportFieldConfig(source="status"), "page_count": ImportFieldConfig(source="pages"), "date_finished": ImportFieldConfig(source="finished")},
        session, "continue_on_error",
        create_progress_for_read=True,
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["imported"] == 1


@pytest.mark.anyio
async def test_execute_import_progress_naive_utcnow_fallback(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Mock utcnow to return a naive datetime to trigger line 510-511 via the fallback path."""
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "status": "read", "pages": "100", "finished": "2024-01-15"}],
        "source_fields": ["title", "status", "pages", "finished"],
    }
    file_id = "test_exec_naive_utc"
    path = di._temp_file_path(user.id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    # Mock utcnow to return a naive datetime
    monkeypatch.setattr(di, "utcnow", lambda: datetime(2024, 1, 15, 10, 30, 0))

    events = []
    async for event in di.execute_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "reading_status": ImportFieldConfig(source="status"), "page_count": ImportFieldConfig(source="pages"), "date_finished": ImportFieldConfig(source="finished")},
        session, "continue_on_error",
        create_progress_for_read=True,
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["imported"] == 1


# ── cleanup_temp_files ────────────────────────────────────────────────────────

def test_cleanup_temp_files_root_missing(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", "/nonexistent/path/for/cleanup")
    # Should not raise
    di.cleanup_temp_files()


def test_cleanup_temp_files_deletes_old_files(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    # Create an old JSON file by setting its mtime to the past
    path = tmp_path / "old.json"
    path.write_text("{}")
    old_time = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(str(path), (old_time, old_time))

    di.cleanup_temp_files()
    assert not path.exists()


def test_cleanup_temp_files_keeps_recent_files(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    # Create a recent JSON file
    path = tmp_path / "recent.json"
    path.write_text("{}")

    di.cleanup_temp_files()
    assert path.exists()


def test_cleanup_temp_files_oserror_on_stat(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    # Create a JSON file
    (tmp_path / "test.json").write_text("{}")

    def _raise(*args: Any, **kwargs: Any) -> Any:
        raise OSError("stat failed")

    monkeypatch.setattr(Path, "stat", _raise)
    # Should not raise
    di.cleanup_temp_files()


def test_cleanup_temp_files_oserror_on_unlink(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    # Create an old JSON file
    path = tmp_path / "test.json"
    path.write_text("{}")
    old_time = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(str(path), (old_time, old_time))

    original_unlink = Path.unlink

    def _raise_unlink(self: Path, missing_ok: bool = False) -> Any:
        if self == path:
            raise OSError("unlink failed")
        return original_unlink(self, missing_ok=missing_ok)  # pragma: no cover

    monkeypatch.setattr(Path, "unlink", _raise_unlink)
    # Should not raise
    di.cleanup_temp_files()
