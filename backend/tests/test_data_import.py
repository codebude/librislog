"""Unit tests for app.services.data_import module."""

import io
import json
import os
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest import MonkeyPatch
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import settings
from app.models import AcquisitionStatus, Book, ReadingStatus, User, UserRole
from app.schemas import ImportFieldConfig
from app.services import data_import as di
from app.services.authors import authors_list_for_book, sync_book_authors
from app.services.data_export import _serialize_datetime, build_export_zip
from app.services.tags import sync_book_tags, tags_list_for_book


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


def test_to_flat_row_list_is_preserved() -> None:
    """List values are kept as-is so JSON author arrays survive flattening."""
    flat = di._to_flat_row({"author": ["Asimov, Isaac", "Robert Heinlein"]})
    assert flat["author"] == ["Asimov, Isaac", "Robert Heinlein"]


def test_canonicalize_mapping_renames_author_target() -> None:
    """Legacy 'author' targets map to the canonical 'authors' field."""
    from app.schemas import ImportFieldConfig

    canonical = di.canonicalize_mapping(
        {"title": ImportFieldConfig(source="Title"), "author": ImportFieldConfig(source="Author")}
    )
    assert set(canonical) == {"title", "authors"}
    assert canonical["authors"].source == "Author"


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


def test_parse_upload_csv_custom_delimiter(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    csv = "Title;Author\nDune;Frank Herbert\n"
    result = di.parse_upload(csv.encode(), "test.csv", 1, delimiter=";")
    assert result["format"] == "csv"
    assert result["source_fields"] == ["Title", "Author"]
    assert result["sample_rows"][0] == {"Title": "Dune", "Author": "Frank Herbert"}


def test_parse_upload_csv_invalid_delimiter(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    with pytest.raises(ValueError, match="error.importInvalidDelimiter"):
        di.parse_upload(b"Title\nDune\n", "test.csv", 1, delimiter=";;")


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


def test_mapped_row_array_authors_skips_transform() -> None:
    """A list source mapped to `authors` bypasses the transform (scalar-only)."""
    result = di._mapped_row(
        {"A": ["Neil Gaiman", "Terry Pratchett"]},
        {"authors": ImportFieldConfig(source="A", transform="value.upper()")},
        {},
        {},
    )
    assert result == {"authors": ["Neil Gaiman", "Terry Pratchett"]}


def test_mapped_row_transform_returning_list_kept_for_authors() -> None:
    """A transform that returns a list (e.g. value.split(';')) stays a list for
    the adaptive `authors` target, so the preview renders a JSON array."""
    transform_cache = di._build_transform_cache(
        {"authors": ImportFieldConfig(source="A", transform="value.split(';')")}
    )
    result = di._mapped_row(
        {"A": "Doe, Jane; Mike; mansarde"},
        {"authors": ImportFieldConfig(source="A", transform="value.split(';')")},
        transform_cache,
        {},
    )
    assert result == {"authors": ["Doe, Jane", " Mike", " mansarde"]}


def test_mapped_row_transform_returning_list_kept_for_tags() -> None:
    """Same list pass-through applies to the adaptive `tags` target."""
    transform_cache = di._build_transform_cache(
        {"tags": ImportFieldConfig(source="A", transform="value.split(',')")}
    )
    result = di._mapped_row(
        {"A": "fantasy,humor"},
        {"tags": ImportFieldConfig(source="A", transform="value.split(',')")},
        transform_cache,
        {},
    )
    assert result == {"tags": ["fantasy", "humor"]}


def test_mapped_row_transform_returning_list_stringified_for_scalar_target() -> None:
    """A list result on a non-adaptive target (e.g. title) is stringified."""
    transform_cache = di._build_transform_cache(
        {"title": ImportFieldConfig(source="A", transform="value.split(' ')")}
    )
    result = di._mapped_row(
        {"A": "Dune Messiah"},
        {"title": ImportFieldConfig(source="A", transform="value.split(' ')")},
        transform_cache,
        {},
    )
    assert result == {"title": "['Dune', 'Messiah']"}


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
    mapping = {
        "title": ImportFieldConfig(source="A", transform="value.upper()"),
        "acquisition_status": ImportFieldConfig(source="B"),
    }
    warnings, errors = di._validate_mapping(mapping, {"A", "B"})
    assert len(errors) == 0


def test_validate_mapping_requires_acquisition_status() -> None:
    _warnings, errors = di._validate_mapping(
        {"title": ImportFieldConfig(source="A")}, {"A"}, require_acquisition_status=True
    )
    assert "Mapping missing required field: acquisition_status" in errors


def test_parse_acquisition_status_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="acquisition_status"):
        di._parse_acquisition_status("wishlist")


# ── preview_import ────────────────────────────────────────────────────────────

def test_preview_import_json_lists_render_as_arrays(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """JSON `authors`/`tags` arrays stay arrays in the preview, and the
    canonical `authors` target (not legacy `author`) is shown."""
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [
            {
                "title": "Good Omens",
                "author": "Neil Gaiman; Terry Pratchett",
                "authors": ["Neil Gaiman", "Terry Pratchett"],
                "tags": ["fantasy", "humor"],
                "page_count": 288,
                "reading_status": "want_to_read",
            }
        ],
        "source_fields": ["title", "author", "authors", "tags", "page_count", "reading_status"],
    }
    file_id = "test_preview_lists"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    mapping = di.suggest_mapping(list(payload["source_fields"]))
    result = di.preview_import(file_id, user, mapping)
    assert len(result["preview_rows"]) == 1
    row = result["preview_rows"][0]

    # Source keeps raw file values: author string stays a string, lists stay lists.
    assert row["source"]["author"] == "Neil Gaiman; Terry Pratchett"
    assert row["source"]["authors"] == ["Neil Gaiman", "Terry Pratchett"]
    assert row["source"]["tags"] == ["fantasy", "humor"]

    # Transformed shows only the canonical `authors` target, as an array.
    assert "author" not in row["transformed"]
    assert row["transformed"]["authors"] == ["Neil Gaiman", "Terry Pratchett"]
    assert row["transformed"]["tags"] == ["fantasy", "humor"]


def test_preview_import_basic(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "author": "Author"}],
        "source_fields": ["title", "author"],
    }
    file_id = "test_preview"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(file_id, user, {"invalid_target": ImportFieldConfig(source="title")})
    assert len(result["preview_rows"]) == 0
    assert len(result["errors"]) > 0


# ── validate_import ───────────────────────────────────────────────────────────

def _require(value: int | None) -> int:
    assert value is not None
    return value


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
    assert user.id is not None
    return user


def test_validate_import_rating_out_of_range(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "rating": "99"}],
        "source_fields": ["title", "rating"],
    }
    file_id = "test_rating"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id, user, {"invalid_target": ImportFieldConfig(source="title")}, session, "continue_on_error"
    ):
        events.append(event)
    assert any("Invalid mapping target" in e.get("message", "") for e in events)


@pytest.mark.anyio
async def test_execute_import_tags_list_and_multi_author(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """A JSON backup with list tags and list authors (as exported) round-trips."""
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [
            {
                "title": "Good Omens",
                "author": "Neil Gaiman; Terry Pratchett",
                "tags": ["fantasy", "humor"],
                "page_count": "288",
                "reading_status": "want_to_read",
            }
        ],
        "source_fields": ["title", "author", "tags", "page_count", "reading_status"],
    }
    file_id = "test_exec_tags_list"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    mapping = {
        "title": ImportFieldConfig(source="title"),
        "author": ImportFieldConfig(source="author"),
        "tags": ImportFieldConfig(source="tags"),
        "page_count": ImportFieldConfig(source="page_count"),
        "reading_status": ImportFieldConfig(source="reading_status"),
    }
    events = []
    async for event in di.execute_import(file_id, user, mapping, session, "continue_on_error"):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["imported"] == 1

    book = session.exec(select(Book).where(Book.user_id == user.id)).one()
    assert authors_list_for_book(session, book.id) == ["Neil Gaiman", "Terry Pratchett"]
    assert tags_list_for_book(session, book.id) == ["fantasy", "humor"]


@pytest.mark.anyio
async def test_execute_import_full_library_json_round_trip(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Export a full library as JSON and re-import it, verifying every field.

    Covers a fully-populated book, a multi-author/tagged book, and a minimal
    book. ``date_added`` is excluded: the import assigns a fresh timestamp.
    """
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    user_id = _require(user.id)

    # ── Source library ──────────────────────────────────────────────────────
    full = Book(
        title="Dune",
        subtitle="A sci-fi classic",
        isbn="9780441013593",
        publisher="Ace Books",
        published_year=1965,
        page_count=412,
        language="EN",
        notes="Spice must flow.",
        blurb="A desert planet, a young duke, and a spice that grants prescience.",
        rating=5,
        reading_status=ReadingStatus.read,
        acquisition_status=AcquisitionStatus.owned,
        date_started=datetime(2025, 1, 10, 9, 30, tzinfo=timezone.utc),
        date_finished=datetime(2025, 1, 20, 21, 45, tzinfo=timezone.utc),
        user_id=user.id,
    )
    multi = Book(
        title="Good Omens",
        subtitle=None,
        isbn="9780060853983",
        publisher="William Morrow",
        published_year=1990,
        page_count=288,
        language="EN",
        notes=None,
        blurb="An angel, a demon, and an approaching apocalypse.",
        rating=4,
        reading_status=ReadingStatus.want_to_read,
        acquisition_status=AcquisitionStatus.digital_access,
        date_started=None,
        date_finished=None,
        user_id=user.id,
    )
    minimal = Book(
        title="Minimal",
        page_count=100,
        reading_status=ReadingStatus.want_to_read,
        acquisition_status=AcquisitionStatus.owned,
        user_id=user.id,
    )
    session.add_all([full, multi, minimal])
    session.flush()
    full_id = _require(full.id)
    multi_id = _require(multi.id)
    minimal_id = _require(minimal.id)

    sync_book_authors(session, user_id, full_id, ["Frank Herbert"])
    sync_book_tags(session, user_id, full_id, "sci-fi,classic")
    sync_book_authors(session, user_id, multi_id, ["Neil Gaiman", "Terry Pratchett"])
    sync_book_tags(session, user_id, multi_id, ["fantasy", "humor"])
    session.commit()

    # ── Export ───────────────────────────────────────────────────────────────
    zip_bytes, _ = build_export_zip(session, user, ["books"], "json", settings.covers_dir)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        exported_rows = json.loads(zf.read("books.json"))
    assert len(exported_rows) == 3
    exported_by_title = {row["title"]: row for row in exported_rows}

    # Exported multi-author author string must be the "; "-joined form.
    assert exported_by_title["Good Omens"]["author"] == "Neil Gaiman; Terry Pratchett"
    assert exported_by_title["Good Omens"]["authors"] == ["Neil Gaiman", "Terry Pratchett"]
    assert exported_by_title["Good Omens"]["tags"] == ["fantasy", "humor"]

    # Remove the source library so only the imported copies remain.
    for book in (full, multi, minimal):
        session.delete(book)
    session.commit()

    # ── Re-import the exported rows ──────────────────────────────────────────
    file_id = "roundtrip_full"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"rows": exported_rows, "source_fields": list(exported_rows[0].keys())})
    )

    mapping = {
        field: ImportFieldConfig(source=field)
        for field in (
            "title",
            "subtitle",
            "author",
            "isbn",
            "publisher",
            "published_year",
            "page_count",
            "language",
            "tags",
            "notes",
            "blurb",
            "rating",
            "reading_status",
            "acquisition_status",
            "date_started",
            "date_finished",
            "cover_url",
        )
    }
    events = []
    async for event in di.execute_import(
        file_id, user, mapping, session, "continue_on_error", require_acquisition_status=True
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["imported"] == 3
    assert complete["failed"] == 0

    imported = {
        b.title: b for b in session.exec(select(Book).where(Book.user_id == user.id)).all()
    }
    assert set(imported) == {"Dune", "Good Omens", "Minimal"}

    for title, row in exported_by_title.items():
        book = imported[title]
        assert book.subtitle == row["subtitle"]
        assert book.isbn == row["isbn"]
        assert book.publisher == row["publisher"]
        assert book.published_year == row["published_year"]
        assert book.page_count == row["page_count"]
        assert book.language == row["language"]
        assert book.notes == row["notes"]
        assert book.blurb == row["blurb"]
        assert book.rating == row["rating"]
        assert book.reading_status.value == row["reading_status"]
        assert book.acquisition_status.value == row["acquisition_status"]
        assert book.cover_url == row["cover_url"]
        assert _serialize_datetime(book.date_started) == row["date_started"]
        assert _serialize_datetime(book.date_finished) == row["date_finished"]
        assert authors_list_for_book(session, book.id) == row["authors"]
        assert tags_list_for_book(session, book.id) == row["tags"]


@pytest.mark.anyio
async def test_execute_import_rating_out_of_range_set_to_none(session: Session, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "rating": "99"}],
        "source_fields": ["title", "rating"],
    }
    file_id = "test_exec_rating"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
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


# ── _parse_acquisition_status ─────────────────────────────────────────────────

def test_parse_acquisition_status_missing_value() -> None:
    with pytest.raises(ValueError, match="Missing required field 'acquisition_status'"):
        di._parse_acquisition_status(None)
    with pytest.raises(ValueError, match="Missing required field 'acquisition_status'"):
        di._parse_acquisition_status("   ")


# ── _mapped_row ───────────────────────────────────────────────────────────────

def test_mapped_row_transform_execution_error() -> None:
    mapping = {"title": ImportFieldConfig(source="title", transform="return int(value)")}
    transform_cache = di._build_transform_cache(mapping)
    errors: list[str] = []
    result = di._mapped_row(
        {"title": "not-a-number"},
        mapping,
        transform_cache,
        {},
        errors,
    )
    assert "title" not in result
    assert any("title" in e for e in errors)


# ── _validate_mapping ─────────────────────────────────────────────────────────

def test_validate_mapping_invalid_target_with_empty_source() -> None:
    mapping = {
        "title": ImportFieldConfig(source="A"),
        "invalid_target": ImportFieldConfig(source=""),
    }
    warnings, errors = di._validate_mapping(mapping, {"A"})
    assert any("Invalid mapping target: invalid_target" in e for e in errors)


# ── validate_import ───────────────────────────────────────────────────────────

def test_validate_import_invalid_mapping_returns_early(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book"}],
        "source_fields": ["title"],
    }
    file_id = "test_validate_early"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(
        file_id, user, {"invalid_target": ImportFieldConfig(source="title")}, session
    )
    assert result["valid"] is False
    assert any("Invalid mapping target" in e for e in result["errors"])


def test_validate_import_require_acquisition_status_invalid(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "acq": "wishlist"}],
        "source_fields": ["title", "acq"],
    }
    file_id = "test_validate_acq"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "acquisition_status": ImportFieldConfig(source="acq")},
        session,
        require_acquisition_status=True,
    )
    assert any("acquisition_status" in e for e in result["errors"])


def test_validate_import_invalid_date_started(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "started": "not-a-date"}],
        "source_fields": ["title", "started"],
    }
    file_id = "test_validate_bad_started"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "date_started": ImportFieldConfig(source="started")},
        session,
    )
    assert any("date_started" in e for e in result["errors"])


def test_validate_import_invalid_date_finished(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "finished": "not-a-date"}],
        "source_fields": ["title", "finished"],
    }
    file_id = "test_validate_bad_finished"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.validate_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "date_finished": ImportFieldConfig(source="finished")},
        session,
    )
    assert any("date_finished" in e for e in result["errors"])


# ── preview_import ────────────────────────────────────────────────────────────

def test_preview_import_missing_title(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": ""}],
        "source_fields": ["title"],
    }
    file_id = "test_preview_missing_title"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id, user, {"title": ImportFieldConfig(source="title")}
    )
    assert any("Missing required field 'title'" in e for e in result["preview_rows"][0]["errors"])


def test_preview_import_rating_out_of_range(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "rating": "99"}],
        "source_fields": ["title", "rating"],
    }
    file_id = "test_preview_rating"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "rating": ImportFieldConfig(source="rating")}
    )
    assert any("Rating out of range" in e for e in result["preview_rows"][0]["errors"])


def test_preview_import_invalid_page_count(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "pages": "abc"}],
        "source_fields": ["title", "pages"],
    }
    file_id = "test_preview_pages"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "page_count": ImportFieldConfig(source="pages")}
    )
    assert any("page_count" in e for e in result["preview_rows"][0]["errors"])


def test_preview_import_invalid_date_started(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "started": "bad-date"}],
        "source_fields": ["title", "started"],
    }
    file_id = "test_preview_bad_started"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "date_started": ImportFieldConfig(source="started")}
    )
    assert any("date_started" in e for e in result["preview_rows"][0]["errors"])


def test_preview_import_invalid_date_finished(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "finished": "bad-date"}],
        "source_fields": ["title", "finished"],
    }
    file_id = "test_preview_bad_finished"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "date_finished": ImportFieldConfig(source="finished")}
    )
    assert any("date_finished" in e for e in result["preview_rows"][0]["errors"])


def test_preview_import_date_order(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "started": "2024-02-01", "finished": "2024-01-01"}],
        "source_fields": ["title", "started", "finished"],
    }
    file_id = "test_preview_order"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id,
        user,
        {
            "title": ImportFieldConfig(source="title"),
            "date_started": ImportFieldConfig(source="started"),
            "date_finished": ImportFieldConfig(source="finished"),
        },
    )
    assert any("date_started is after date_finished" in e for e in result["preview_rows"][0]["errors"])


def test_preview_import_read_without_finished_date(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "status": "read"}],
        "source_fields": ["title", "status"],
    }
    file_id = "test_preview_read_nofinish"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "reading_status": ImportFieldConfig(source="status")}
    )
    assert any("no finished date" in e for e in result["preview_rows"][0]["errors"])


def test_preview_import_require_acquisition_status_invalid(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "acq": "wishlist"}],
        "source_fields": ["title", "acq"],
    }
    file_id = "test_preview_acq"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "acquisition_status": ImportFieldConfig(source="acq")},
        require_acquisition_status=True,
    )
    assert any("acquisition_status" in e for e in result["preview_rows"][0]["errors"])


def test_preview_import_invalid_isbn(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "isbn": "not-valid"}],
        "source_fields": ["title", "isbn"],
    }
    file_id = "test_preview_isbn"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    result = di.preview_import(
        file_id, user, {"title": ImportFieldConfig(source="title"), "isbn": ImportFieldConfig(source="isbn")}
    )
    assert any("isbn" in e.lower() for e in result["preview_rows"][0]["errors"])


# ── execute_import ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_execute_import_transform_error(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "num": "abc"}],
        "source_fields": ["title", "num"],
    }
    file_id = "test_exec_transform"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "rating": ImportFieldConfig(source="num", transform="return int(value)")},
        session,
        "continue_on_error",
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["failed"] == 1


@pytest.mark.anyio
async def test_execute_import_invalid_date_started(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "started": "bad-date"}],
        "source_fields": ["title", "started"],
    }
    file_id = "test_exec_bad_started"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "date_started": ImportFieldConfig(source="started")},
        session,
        "continue_on_error",
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["failed"] == 1


@pytest.mark.anyio
async def test_execute_import_invalid_date_finished(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "finished": "bad-date"}],
        "source_fields": ["title", "finished"],
    }
    file_id = "test_exec_bad_finished"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "date_finished": ImportFieldConfig(source="finished")},
        session,
        "continue_on_error",
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["failed"] == 1


@pytest.mark.anyio
async def test_execute_import_read_without_finished_date(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "status": "read"}],
        "source_fields": ["title", "status"],
    }
    file_id = "test_exec_read_nofinish"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    events = []
    async for event in di.execute_import(
        file_id,
        user,
        {"title": ImportFieldConfig(source="title"), "reading_status": ImportFieldConfig(source="status")},
        session,
        "continue_on_error",
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["failed"] == 1


@pytest.mark.anyio
async def test_execute_import_naive_log_date_gets_utc_tz(
    session: Session, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "import_temp_dir", str(tmp_path))
    user = _create_test_user(session)
    payload = {
        "rows": [{"title": "Book", "status": "read", "pages": "100", "finished": "2024-01-15"}],
        "source_fields": ["title", "status", "pages", "finished"],
    }
    file_id = "test_exec_naive_logdate"
    path = di._temp_file_path(user.id, file_id)  # ty: ignore[invalid-argument-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    original_parse_datetime = di._parse_datetime

    def _naive_finished_parse(value: object, field: str):
        if field == "date_finished":
            return datetime(2024, 1, 15, 10, 30, 0)  # naive
        return original_parse_datetime(value, field)

    monkeypatch.setattr(di, "_parse_datetime", _naive_finished_parse)

    events = []
    async for event in di.execute_import(
        file_id,
        user,
        {
            "title": ImportFieldConfig(source="title"),
            "reading_status": ImportFieldConfig(source="status"),
            "page_count": ImportFieldConfig(source="pages"),
            "date_finished": ImportFieldConfig(source="finished"),
        },
        session,
        "continue_on_error",
        create_progress_for_read=True,
    ):
        events.append(event)
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["imported"] == 1


# ── get_predefined_mapping ────────────────────────────────────────────────────

def test_get_predefined_mapping_known_id() -> None:
    result = di.get_predefined_mapping(-1)
    assert result is not None
    assert result["name"] == "Goodreads Export"


def test_get_predefined_mapping_unknown_id() -> None:
    assert di.get_predefined_mapping(-999) is None
