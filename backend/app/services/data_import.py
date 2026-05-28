"""CSV/JSON data import pipeline — parsing, validation, mapping, and execution."""

import csv
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import settings
from app.models import Book, ReadingProgress, ReadingStatus, User
from app.schemas import ImportFieldConfig
from app.time_utils import utcnow
from app.services.cover_storage import download_cover
from app.services.tags import sync_book_tags

BOOK_IMPORT_FIELDS: list[str] = [
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
    "date_started",
    "date_finished",
    "cover_url",
]

_ALIASES: dict[str, str] = {
    "title": "title",
    "book title": "title",
    "name": "title",
    "subtitle": "subtitle",
    "book subtitle": "subtitle",
    "author": "author",
    "authors": "author",
    "author name": "author",
    "isbn": "isbn",
    "isbn13": "isbn",
    "isbn10": "isbn",
    "publisher": "publisher",
    "year": "published_year",
    "published": "published_year",
    "published year": "published_year",
    "pages": "page_count",
    "page count": "page_count",
    "language": "language",
    "lang": "language",
    "tags": "tags",
    "genres": "tags",
    "notes": "notes",
    "blurb": "blurb",
    "description": "blurb",
    "summary": "blurb",
    "synopsis": "blurb",
    "rating": "rating",
    "my rating": "rating",
    "status": "reading_status",
    "reading status": "reading_status",
    "date started": "date_started",
    "started": "date_started",
    "date finished": "date_finished",
    "finished": "date_finished",
    "date read": "date_finished",
    "cover": "cover_url",
    "cover url": "cover_url",
}


def _display_value(value: object) -> str:
    """Format a value for display in error messages."""
    if value is None:
        return "null"
    text = str(value)
    if text == "":
        return '""'
    return text


def _format_value_error(field: str, expected: str, value: object, hint: str | None = None) -> str:
    """Format a validation error message."""
    message = f"Invalid value for '{field}'. Expected: {expected}. Given: {_display_value(value)}."
    if hint:
        return f"{message} Hint: {hint}."
    return message


def compute_schema_fingerprint(source_fields: list[str]) -> str:
    """Compute a SHA-256 fingerprint for a set of source fields."""
    payload = json.dumps(sorted(source_fields), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _user_temp_dir(user_id: int) -> Path:
    """Return the temp directory for a specific user."""
    return Path(settings.import_temp_dir) / str(user_id)


def _temp_file_path(user_id: int, file_id: str) -> Path:
    """Return the path to a parsed upload file."""
    return _user_temp_dir(user_id) / f"{file_id}.json"


def delete_parsed_upload(file_id: str, user_id: int) -> None:
    """Delete a previously-uploaded and parsed import file."""
    _temp_file_path(user_id, file_id).unlink(missing_ok=True)


def _to_flat_row(row: dict) -> dict[str, str | int | float | bool | None]:
    """Flatten a row dict, rejecting nested values."""
    flat: dict[str, str | int | float | bool | None] = {}
    for key, value in row.items():
        if isinstance(value, (dict, list)):
            raise ValueError("error.importNestedValuesNotSupported")
        flat[str(key)] = value
    return flat


def parse_upload(content: bytes, filename: str, user_id: int) -> dict:
    """Parse an uploaded CSV or JSON file and persist the parsed result to disk.

    Args:
        content: Raw file bytes.
        filename: Original filename (used to detect format).
        user_id: Owner of the upload.

    Returns:
        A dict with file_id, format, source_fields, sample_rows, and row_count.

    Raises:
        ValueError: On validation failures.
    """
    if not content:
        raise ValueError("error.importEmptyFile")
    if len(content) > settings.max_import_file_size_mb * 1024 * 1024:
        raise ValueError("error.importFileTooLarge")

    lower = filename.lower()
    if lower.endswith(".csv"):
        parsed_format = "csv"
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames:
            raise ValueError("error.importMissingHeader")
        rows = [_to_flat_row(row) for row in reader]
        source_fields = [str(field) for field in reader.fieldnames]
    elif lower.endswith(".json"):
        parsed_format = "json"
        payload = json.loads(content.decode("utf-8"))
        if not isinstance(payload, list):
            raise ValueError("error.importJsonMustBeArray")
        rows = []
        source_set: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("error.importJsonRowsMustBeObjects")
            flat = _to_flat_row(item)
            rows.append(flat)
            source_set.update(flat.keys())
        source_fields = sorted(source_set)
    else:
        raise ValueError("error.importUnsupportedFileType")

    if len(rows) > settings.max_import_row_count:
        raise ValueError("error.importTooManyRows")

    user_dir = _user_temp_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    file_id = ""
    for _ in range(5):
        file_id = secrets.token_urlsafe(18)
        payload = {
            "file_id": file_id,
            "format": parsed_format,
            "source_fields": source_fields,
            "rows": rows,
            "created_at": utcnow().isoformat(),
        }
        path = _temp_file_path(user_id, file_id)
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle)
            break
        except FileExistsError:
            continue
    else:
        raise ValueError("error.importTempFileCreateFailed")

    return {
        "file_id": file_id,
        "format": parsed_format,
        "source_fields": source_fields,
        "sample_rows": rows[:5],
        "row_count": len(rows),
    }


def load_parsed_upload(file_id: str, user_id: int) -> dict:
    """Load a previously-parsed upload from disk."""
    path = _temp_file_path(user_id, file_id)
    if not path.exists():
        raise FileNotFoundError("error.importFileNotFound")
    return json.loads(path.read_text(encoding="utf-8"))


def suggest_mapping(source_fields: list[str]) -> dict[str, "ImportFieldConfig"]:
    """Suggest a column mapping based on known field name aliases.

    Args:
        source_fields: List of field names from the import file.

    Returns:
        Dict mapping each recognised DB target field to its source field config.
    """
    from app.schemas import ImportFieldConfig

    suggested: dict[str, ImportFieldConfig] = {}
    for field in source_fields:
        key = " ".join(field.strip().lower().replace("_", " ").split())
        if key in _ALIASES:
            suggested[_ALIASES[key]] = ImportFieldConfig(source=field)
            continue
        compact = key.replace(" ", "")
        for alias, target in _ALIASES.items():
            if alias.replace(" ", "") == compact:
                suggested[target] = ImportFieldConfig(source=field)
                break
    return suggested


_YEAR_PATTERN: re.Pattern = re.compile(r"\b(\d{4})\b")


def _parse_int(value: object, field: str) -> int | None:
    """Parse an integer value, raising a descriptive error on failure."""
    if value is None or value == "":
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if "." in raw:
        raise ValueError(
            _format_value_error(
                field=field,
                expected="an integer number",
                value=value,
                hint="Whole numbers only, no decimals",
            )
        )
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError(
            _format_value_error(
                field=field,
                expected="an integer number",
                value=value,
                hint="Use digits only, for example 1998 or 320",
            )
        )


def _parse_year(value: object, field: str) -> int | None:
    """Parse a year value, accepting 4-digit integers and date strings."""
    if value is None or value == "":
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    m = _YEAR_PATTERN.search(raw)
    if m:
        return int(m.group(1))
    raise ValueError(
        _format_value_error(
            field=field,
            expected="a year (e.g., 1998) or date string",
            value=value,
            hint="Use a 4-digit year like 1998, or a date that includes the year",
        )
    )


def _parse_datetime(value: object, field: str) -> datetime | None:
    """Parse an ISO-8601 datetime value."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(
                _format_value_error(
                    field=field,
                    expected="an ISO date or datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
                    value=value,
                    hint="Examples: 2026-05-19 or 2026-05-19T12:30:00Z",
                )
            ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _normalize_language(language: str | None) -> str | None:
    """Normalize a language code to uppercase ISO 639-1."""
    if language is None:
        return None
    normalized = language.strip().upper()
    if not normalized:
        return None
    if len(normalized) != 2 or not normalized.isalpha():
        raise ValueError(
            _format_value_error(
                field="language",
                expected="a 2-letter ISO code",
                value=language,
                hint="Use uppercase letters like EN, DE, FR",
            )
        )
    return normalized


def _parse_reading_status(value: object) -> ReadingStatus:
    """Parse a reading status value, defaulting to want_to_read."""
    if value is None or str(value).strip() == "":
        return ReadingStatus.want_to_read

    raw = str(value).strip()
    allowed = [status.value for status in ReadingStatus]
    if raw not in allowed:
        raise ValueError(
            _format_value_error(
                field="reading_status",
                expected=f"one of: {', '.join(allowed)}",
                value=value,
                hint="Use exact values from the app export format",
            )
        )

    return ReadingStatus(raw)


def _build_transform_cache(
    mapping: dict[str, "ImportFieldConfig"],
) -> dict[str, Callable[..., str]]:
    """Compile all transform expressions into a cache of callables."""
    from app.services.transform_engine import compile_transform

    cache: dict[str, Callable[..., str]] = {}
    for target, config in mapping.items():
        if config.transform:
            cache[target] = compile_transform(config.transform)
    return cache


def _mapped_row(
    row: dict,
    mapping: dict[str, "ImportFieldConfig"],
    transform_cache: dict[str, Callable[..., str]],
    context: dict[str, Any],
    errors: list[str] | None = None,
) -> dict:
    """Apply a field mapping and optional transforms to a single row."""
    mapped: dict[str, object] = {}
    for target, config in mapping.items():
        source = config.source
        if not source:
            continue
        value = row.get(source, "")
        value_str = "" if value is None else str(value)
        if target in transform_cache:
            from app.services.transform_engine import TransformExecutionError, execute_transform

            try:
                value_str = execute_transform(
                    transform_cache[target], value_str, row, context
                )
            except TransformExecutionError as exc:
                if errors is not None:
                    errors.append(f"\x1f{target}\x1f{exc}")
                continue
        mapped[target] = value_str
    return mapped


def _validate_mapping(
    mapping: dict[str, ImportFieldConfig], source_fields: set[str]
) -> tuple[list[str], list[str]]:
    """Validate an import mapping, returning (warnings, errors)."""
    warnings: list[str] = []
    errors: list[str] = []
    mapped_targets = [target for target in mapping.keys() if target]

    if "title" not in mapped_targets:
        errors.append("Mapping missing required field: title")

    invalid_targets = sorted({target for target in mapped_targets if target not in BOOK_IMPORT_FIELDS})
    for target in invalid_targets:
        errors.append(f"Invalid mapping target: {target}")

    for target, config in mapping.items():
        source = config.source
        if not source:
            continue
        if source not in source_fields:
            warnings.append(f"Mapped source field missing in file: {source}")
        if config.transform:
            try:
                from app.services.transform_engine import compile_transform

                compile_transform(config.transform)
            except ValueError as exc:
                errors.append(f"\x1f{target}\x1f{exc}")

    return warnings, errors


def validate_import(
    file_id: str,
    user: User,
    mapping: dict[str, ImportFieldConfig],
    session: Session,
    create_progress_for_read: bool = False,
) -> dict:
    """Validate a parsed import file against the DB schema and existing data.

    Args:
        file_id: Upload file ID.
        user: Target user.
        mapping: Column mapping dict.
        session: Active DB session.
        create_progress_for_read: Whether to flag missing page counts for read books.

    Returns:
        A dict with keys: valid, row_count, warnings, errors.
    """
    parsed = load_parsed_upload(file_id, user.id)
    rows = parsed.get("rows", [])
    source_fields = set(parsed.get("source_fields", []))

    warnings, errors = _validate_mapping(mapping, source_fields)

    if errors:
        return {"valid": False, "row_count": len(rows), "warnings": warnings, "errors": errors}

    transform_cache = _build_transform_cache(mapping)

    for idx, row in enumerate(rows, start=1):
        row_data = _mapped_row(row, mapping, transform_cache, {"row": idx, "total": len(rows)}, errors)
        title_value = row_data.get("title")
        title = str(title_value).strip() if title_value is not None else ""
        if not title:
            errors.append(f"Row {idx}: missing required field 'title'")
            continue

        cover_raw = row_data.get("cover_url")
        if cover_raw:
            cover_val = str(cover_raw).strip()
            if not (cover_val.startswith("http://") or cover_val.startswith("https://")):
                warnings.append(
                    f"Row {idx}: cover_url must be an HTTP(S) URL to an image; non-URL values will be ignored"
                )

        try:
            rating = _parse_int(row_data.get("rating"), "rating")
            if rating is not None and (rating < 1 or rating > 5):
                warnings.append(f"Row {idx}: rating out of range, will be ignored")
            _parse_year(row_data.get("published_year"), "published_year")
            _parse_int(row_data.get("page_count"), "page_count")
            reading_status = _parse_reading_status(row_data.get("reading_status"))
            date_started = _parse_datetime(row_data.get("date_started"), "date_started")
            date_finished = _parse_datetime(row_data.get("date_finished"), "date_finished")
            if date_started and date_finished and date_started > date_finished:
                errors.append(f"Row {idx}: date_started is after date_finished")
                continue
            _normalize_language(
                None if row_data.get("language") is None else str(row_data.get("language"))
            )
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue

        if create_progress_for_read and reading_status == ReadingStatus.read and not row_data.get("page_count"):
            warnings.append(f"Row {idx}: marked as 'read' but has no page count; will not create a progress entry")

    # Batch-check ISBNs to avoid N+1 queries
    isbns_in_file: set[str] = set()
    for idx, row in enumerate(rows, start=1):
        row_data = _mapped_row(row, mapping, transform_cache, {"row": idx, "total": len(rows)})
        isbn = row_data.get("isbn")
        if isbn:
            isbns_in_file.add(str(isbn))

    existing_isbns: set[str] = set()
    if isbns_in_file:
        results = session.exec(
            select(Book.isbn).where(Book.user_id == user.id, Book.isbn.in_(isbns_in_file))
        ).all()
        existing_isbns = set(results)

    for idx, row in enumerate(rows, start=1):
        row_data = _mapped_row(row, mapping, transform_cache, {"row": idx, "total": len(rows)})
        isbn = row_data.get("isbn")
        if isbn and str(isbn) in existing_isbns:
            warnings.append(f"Row {idx}: ISBN already exists and may fail to import")

    return {
        "valid": len(errors) == 0,
        "row_count": len(rows),
        "warnings": warnings,
        "errors": errors,
    }


def preview_import(
    file_id: str,
    user: User,
    mapping: dict[str, ImportFieldConfig],
    limit: int = 5,
) -> dict:
    """Preview how a mapping and transforms will affect the first *limit* rows.

    Returns a dict with keys: preview_rows, row_count, errors.
    """
    parsed = load_parsed_upload(file_id, user.id)
    rows = parsed.get("rows", [])
    source_fields = set(parsed.get("source_fields", []))

    _warnings, mapping_errors = _validate_mapping(mapping, source_fields)
    if mapping_errors:
        return {"preview_rows": [], "row_count": len(rows), "errors": mapping_errors}

    transform_cache = _build_transform_cache(mapping)
    preview_rows: list[dict] = []

    for idx, row in enumerate(rows[:limit], start=1):
        row_errors: list[str] = []
        row_data = _mapped_row(row, mapping, transform_cache, {"row": idx, "total": len(rows)}, row_errors)

        # Validate required fields and data types for preview
        title_value = row_data.get("title")
        title = str(title_value).strip() if title_value is not None else ""
        if not title:
            row_errors.append("Missing required field 'title'")

        try:
            rating = _parse_int(row_data.get("rating"), "rating")
            if rating is not None and (rating < 1 or rating > 5):
                row_errors.append("Rating out of range, will be ignored")
            _parse_year(row_data.get("published_year"), "published_year")
            _parse_int(row_data.get("page_count"), "page_count")
            _parse_reading_status(row_data.get("reading_status"))
            date_started = _parse_datetime(row_data.get("date_started"), "date_started")
            date_finished = _parse_datetime(row_data.get("date_finished"), "date_finished")
            if date_started and date_finished and date_started > date_finished:
                row_errors.append("date_started is after date_finished")
            _normalize_language(
                None if row_data.get("language") is None else str(row_data.get("language"))
            )
        except ValueError as exc:
            row_errors.append(str(exc))

        # Convert raw values to strings for display
        source_display = {k: str(v) if v is not None else "" for k, v in row.items()}
        # Convert transformed values to strings for display
        transformed_display = {k: str(v) if v is not None else "" for k, v in row_data.items()}

        preview_rows.append({
            "row_number": idx,
            "source": source_display,
            "transformed": transformed_display,
            "errors": row_errors,
        })

    return {"preview_rows": preview_rows, "row_count": len(rows), "errors": []}


async def execute_import(
    file_id: str,
    user: User,
    mapping: dict[str, ImportFieldConfig],
    session: Session,
    import_mode: str,
    create_progress_for_read: bool = False,
):
    """Execute an import, yielding progress and result events.

    Args:
        file_id: Upload file ID.
        user: Target user.
        mapping: Column mapping dict.
        session: Active DB session.
        import_mode: ``"rollback_all"`` or ``"continue_on_error"``.
        create_progress_for_read: Auto-create progress entries for read books.

    Yields:
        Dicts with event type and data.
    """
    parsed = load_parsed_upload(file_id, user.id)
    rows: list[dict] = parsed.get("rows", [])
    total = len(rows)
    imported = 0
    failed = 0
    failures: list[dict] = []

    yield {"event": "start", "total_rows": total}

    rollback_all = import_mode == "rollback_all"

    source_fields = set(parsed.get("source_fields", []))
    _warnings, mapping_errors = _validate_mapping(mapping, source_fields)
    if mapping_errors:
        yield {"event": "error", "message": "; ".join(mapping_errors)}
        return

    transform_cache = _build_transform_cache(mapping)

    async with httpx.AsyncClient(timeout=15.0) as client:
        for idx, row in enumerate(rows, start=1):
            try:
                row_transform_errors: list[str] = []
                row_data = _mapped_row(row, mapping, transform_cache, {"row": idx, "total": total}, row_transform_errors)
                if row_transform_errors:
                    raise ValueError(f"Transform error: {row_transform_errors[0]}")
                title_value = row_data.get("title")
                title = str(title_value).strip() if title_value is not None else ""
                if not title:
                    raise ValueError("Missing required field 'title'")

                rating = _parse_int(row_data.get("rating"), "rating")
                if rating is not None and (rating < 1 or rating > 5):
                    rating = None

                reading_status = _parse_reading_status(row_data.get("reading_status"))

                language = _normalize_language(
                    None if row_data.get("language") is None else str(row_data.get("language"))
                )
                date_started = _parse_datetime(row_data.get("date_started"), "date_started")
                date_finished = _parse_datetime(row_data.get("date_finished"), "date_finished")
                if date_started and date_finished and date_started > date_finished:
                    raise ValueError("date_started is after date_finished")

                cover_url = None
                raw_cover = row_data.get("cover_url")
                if raw_cover:
                    cover_candidate = str(raw_cover).strip()
                    if cover_candidate.startswith("http://") or cover_candidate.startswith("https://"):
                        filename = await download_cover(cover_candidate, settings.covers_dir, client, user.id)
                        if filename:
                            cover_url = f"/api/covers/{filename}"

                page_count = _parse_int(row_data.get("page_count"), "page_count")
                book = Book(
                    title=title,
                    subtitle=None if row_data.get("subtitle") in (None, "") else str(row_data.get("subtitle")),
                    author=None if row_data.get("author") in (None, "") else str(row_data.get("author")),
                    isbn=None if row_data.get("isbn") in (None, "") else str(row_data.get("isbn")),
                    cover_url=cover_url,
                    publisher=None if row_data.get("publisher") in (None, "") else str(row_data.get("publisher")),
                    published_year=_parse_year(row_data.get("published_year"), "published_year"),
                    page_count=page_count,
                    language=language,
                    notes=None if row_data.get("notes") in (None, "") else str(row_data.get("notes")),
                    blurb=None if row_data.get("blurb") in (None, "") else str(row_data.get("blurb")),
                    rating=rating,
                    reading_status=reading_status,
                    date_started=date_started,
                    date_finished=date_finished,
                    user_id=user.id,
                )
                session.add(book)
                session.flush()

                if create_progress_for_read and reading_status == ReadingStatus.read and page_count is not None:
                    log_date = date_finished if date_finished is not None else utcnow()
                    if log_date.tzinfo is None:
                        log_date = log_date.replace(tzinfo=timezone.utc)
                    progress_entry = ReadingProgress(
                        book_id=book.id,
                        user_id=user.id,
                        page=page_count,
                        created_at=log_date,
                    )
                    session.add(progress_entry)

                sync_book_tags(
                    session,
                    user.id,
                    book.id,
                    None if row_data.get("tags") in (None, "") else str(row_data.get("tags")),
                )

                if not rollback_all:
                    session.commit()

                imported += 1
            except (ValueError, IntegrityError) as exc:
                failed += 1
                failures.append({"row": idx, "error": str(exc), "data": row})
                if rollback_all:
                    session.rollback()
                    yield {
                        "event": "error",
                        "message": f"Import failed on row {idx}: {exc}. All changes rolled back.",
                    }
                    return
                session.rollback()

            yield {
                "event": "progress",
                "processed": idx,
                "total": total,
                "percent": round((idx / total) * 100, 1) if total else 100.0,
            }

    if rollback_all:
        session.commit()

    yield {
        "event": "complete",
        "imported": imported,
        "failed": failed,
        "failures": failures,
    }


PREDEFINED_MAPPINGS: list[dict[str, Any]] = [
    {
        "id": -1,
        "name": "Goodreads Export",
        "source_fields": [
            "Book Id", "Title", "Author", "ISBN", "ISBN13",
            "Publisher", "Number of Pages", "Year Published",
            "Original Publication Year", "Date Read", "Date Added",
            "Exclusive Shelf", "My Review", "Bookshelves",
            "My Rating", "Average Rating", "Read Count",
        ],
        "mapping": {
            "title": {"source": "Title", "transform": None},
            "subtitle": {"source": "", "transform": None},
            "author": {"source": "Author", "transform": None},
            "isbn": {"source": "ISBN13", "transform": None},
            "publisher": {"source": "Publisher", "transform": None},
            "published_year": {
                "source": "Original Publication Year",
                "transform": "str(int(value)) if value and str(value).strip() else None",
            },
            "page_count": {
                "source": "Number of Pages",
                "transform": "str(int(value)) if value and str(value).strip() else None",
            },
            "language": {"source": "", "transform": None},
            "tags": {"source": "Bookshelves", "transform": None},
            "notes": {"source": "My Review", "transform": None},
            "blurb": {"source": "", "transform": None},
            "rating": {
                "source": "My Rating",
                "transform": "str(int(value)) if value and str(value).strip() else None",
            },
            "reading_status": {
                "source": "Exclusive Shelf",
                "transform": (
                    "shelf_map = {'to-read': 'want_to_read', "
                    "'currently-reading': 'currently_reading', 'read': 'read'}\n"
                    "status = shelf_map.get(value.strip().lower(), 'want_to_read')\n"
                    "return status"
                ),
            },
            "date_started": {"source": "Date Added", "transform": None},
            "date_finished": {"source": "Date Read", "transform": None},
            "cover_url": {"source": "", "transform": None},
        },
    },
]


def get_predefined_mapping(mapping_id: int) -> dict[str, object] | None:
    """Return a predefined mapping by its negative ID, or None if not found."""
    for pm in PREDEFINED_MAPPINGS:
        if pm["id"] == mapping_id:
            return pm
    return None


def cleanup_temp_files(max_age_hours: int = 24) -> None:
    """Delete temporary import files older than *max_age_hours*.

    Args:
        max_age_hours: Maximum age in hours before a file is deleted.
    """
    root = Path(settings.import_temp_dir)
    if not root.exists():
        return
    cutoff = utcnow().timestamp() - (max_age_hours * 3600)
    for path in root.rglob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            continue
