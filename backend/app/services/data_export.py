"""Data export service — builds ZIP archives with CSV or JSON datasets."""

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from sqlmodel import Session, col, select

from app._build_info import __git_sha__, __version__
from app.models import Book, BookTag, ReadingProgress, Tag, User
from app.services.authors import authors_list_for_book
from app.time_utils import utcnow
from app.services.cover_storage import local_cover_filename, resolve_cover_path
from app.services.tags import tags_list_for_book

BOOK_CSV_FIELDS: list[str] = [
    "title",
    "subtitle",
    "author",
    "authors",
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
    "date_added",
    "date_started",
    "date_finished",
    "cover_url",
]

PROGRESS_CSV_FIELDS: list[str] = ["book_id", "book_title", "page", "created_at", "updated_at"]
TAG_CSV_FIELDS: list[str] = ["id", "name", "book_count", "created_at"]


def _serialize_datetime(value: datetime | None) -> str | None:
    """Format a datetime as ISO-8601 with trailing Z."""
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _book_to_dict(session: Session, book: Book, export_format: str) -> dict:
    """Convert a Book model to a flat export dict.

    JSON exports mirror the API shape: ``author`` is the joined string (using
    ``; `` so it round-trips through the adaptive import), ``authors`` is the
    name list, and ``tags`` is a list of tag names. CSV has no list type: both
    the ``author`` and ``authors`` columns use ``; `` (so they round-trip
    through ``parse_authors``), and ``tags`` is a comma-separated string.
    """
    authors = authors_list_for_book(session, book.id)
    tags = tags_list_for_book(session, book.id)
    author_value = "; ".join(authors) if authors else None
    tags_value = tags if export_format == "json" else (", ".join(tags) if tags else None)
    authors_value = authors if export_format == "json" else ("; ".join(authors) if authors else None)
    return {
        "title": book.title,
        "subtitle": book.subtitle,
        "author": author_value,
        "authors": authors_value,
        "isbn": book.isbn,
        "publisher": book.publisher,
        "published_year": book.published_year,
        "page_count": book.page_count,
        "language": book.language,
        "tags": tags_value,
        "notes": book.notes,
        "blurb": book.blurb,
        "rating": book.rating,
        "reading_status": book.reading_status.value,
        "acquisition_status": book.acquisition_status.value,
        "date_added": _serialize_datetime(book.date_added),
        "date_started": _serialize_datetime(book.date_started),
        "date_finished": _serialize_datetime(book.date_finished),
        "cover_url": book.cover_url,
    }


def _progress_to_dict(entry: ReadingProgress, book_titles: dict[int, str]) -> dict:
    """Convert a ReadingProgress entry to a flat export dict."""
    return {
        "book_id": entry.book_id,
        "book_title": book_titles.get(entry.book_id),
        "page": entry.page,
        "created_at": _serialize_datetime(entry.created_at),
        "updated_at": _serialize_datetime(entry.updated_at),
    }


def _tag_to_dict(tag: Tag, counts: dict[int, int]) -> dict:
    """Convert a Tag model to a flat export dict."""
    return {
        "id": tag.id,
        "name": tag.name,
        "book_count": counts.get(tag.id or -1, 0),
        "created_at": _serialize_datetime(tag.created_at),
    }


def _dump_csv(rows: list[dict], fields: list[str]) -> str:
    """Render a list of dicts as a CSV string."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return out.getvalue()


def build_export_zip(
    session: Session,
    user: User,
    datasets: Sequence[str],
    export_format: str,
    covers_dir: str,
) -> tuple[bytes, str]:
    """Build a ZIP archive containing the requested datasets.

    Args:
        session: Active DB session.
        user: The user whose data to export.
        datasets: List of dataset names (``"books"``, ``"progress"``, ``"tags"``, ``"covers"``).
        export_format: ``"csv"`` or ``"json"``.
        covers_dir: Path to the cover storage directory.

    Returns:
        Tuple of ``(zip_bytes, filename)``.
    """
    now = utcnow()
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    filename = f"librislog-export-{timestamp}.zip"

    books = list(session.exec(select(Book).where(Book.user_id == user.id)).all())
    progress_entries = list(
        session.exec(
            select(ReadingProgress)
            .join(Book, col(Book.id) == col(ReadingProgress.book_id))
            .where(ReadingProgress.user_id == user.id, Book.user_id == user.id)
        ).all()
    )
    tags = list(session.exec(select(Tag).where(Tag.user_id == user.id)).all())
    tag_counts_rows = list(
        session.exec(
            select(BookTag.tag_id, BookTag.book_id)
            .join(Tag, col(Tag.id) == col(BookTag.tag_id))
            .join(Book, col(Book.id) == col(BookTag.book_id))
            .where(Tag.user_id == user.id, Book.user_id == user.id)
        ).all()
    )

    tag_counts: dict[int, int] = {}
    for tag_id, _book_id in tag_counts_rows:
        tag_counts[tag_id] = tag_counts.get(tag_id, 0) + 1

    book_titles = {book.id: book.title for book in books if book.id is not None}

    books_rows = [_book_to_dict(session, book, export_format) for book in books]
    progress_rows = [_progress_to_dict(entry, book_titles) for entry in progress_entries]
    tag_rows = [_tag_to_dict(tag, tag_counts) for tag in tags]

    counts = {
        "books": len(books_rows),
        "progress_entries": len(progress_rows),
        "tags": len(tag_rows),
        "covers": 0,
    }

    buffer = io.BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        if "books" in datasets:
            if export_format == "json":
                zip_file.writestr("books.json", json.dumps(books_rows, indent=2))
            else:
                zip_file.writestr("books.csv", _dump_csv(books_rows, BOOK_CSV_FIELDS))

        if "progress" in datasets:
            if export_format == "json":
                zip_file.writestr("progress.json", json.dumps(progress_rows, indent=2))
            else:
                zip_file.writestr("progress.csv", _dump_csv(progress_rows, PROGRESS_CSV_FIELDS))

        if "tags" in datasets:
            if export_format == "json":
                zip_file.writestr("tags.json", json.dumps(tag_rows, indent=2))
            else:
                zip_file.writestr("tags.csv", _dump_csv(tag_rows, TAG_CSV_FIELDS))

        if "covers" in datasets:
            covers_written = 0
            for book in books:
                cover_filename = local_cover_filename(book.cover_url)
                if not cover_filename:
                    continue
                cover_path = resolve_cover_path(covers_dir, cover_filename)
                if cover_path is None or not Path(cover_path).exists():
                    continue
                zip_file.write(cover_path, arcname=f"covers/{cover_filename}")
                covers_written += 1
            counts["covers"] = covers_written

        manifest = {
            "export_timestamp": now.isoformat().replace("+00:00", "Z"),
            "app_version": __version__,
            "git_sha": __git_sha__,
            "user_id": user.id,
            "user_email": user.email,
            "datasets": datasets,
            "format": export_format,
            "counts": counts,
        }
        zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

    return buffer.getvalue(), filename
