from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

from sqlmodel import Session, select

from app.models import Book, ReadingProgress, ReadingStatus, UserSettings
from app.routers.statistics import _extract_book_level_daily_pages


def _create_book(client: Any, **overrides: Any) -> dict[str, Any]:
    """Helper to create a book via the API and return the JSON response."""
    payload = {"title": "Book", "author": "Test Author", "page_count": 100, **overrides}
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201
    return resp.json()


def test_statistics_requires_auth(client: Any) -> None:
    client.headers.pop("X-API-Key")
    resp = client.get("/api/statistics")
    assert resp.status_code == 401


def test_statistics_empty_library(client: Any) -> None:
    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_books_per_month"] is None
    assert data["busiest_month"] is None
    assert data["avg_page_count"] is None
    assert data["most_popular_language"] is None
    assert data["status_distribution"] == {
        "want_to_read": 0,
        "currently_reading": 0,
        "read": 0,
        "did_not_finish": 0,
    }
    assert data["page_buckets"] == {"pages_to_read": 0, "pages_read": 0, "pages_wasted": 0}
    assert data["pages_read_per_month"] == []
    assert data["books_finished_per_month"] == []
    assert data["books_finished_per_year"] == []
    assert data["top_authors"] == []


def test_statistics_core_metrics_and_distributions(client: Any) -> None:
    _create_book(
        client, title="Read Jan 1", author="Author A", cover_url="/api/covers/a1.jpg",
        page_count=100, language="EN", reading_status="read",
        date_started="2026-01-10T10:00:00Z",
        date_finished="2026-01-10T10:00:00Z",
    )
    _create_book(
        client, title="Read Jan 2", author="Author A", cover_url="/api/covers/a2.jpg",
        page_count=200, language="EN", reading_status="read",
        date_started="2026-01-15T10:00:00Z",
        date_finished="2026-01-15T10:00:00Z",
    )
    _create_book(
        client, title="Read Mar", author="Author B",
        page_count=300, language="DE", reading_status="read",
        date_started="2026-03-01T10:00:00Z",
        date_finished="2026-03-01T10:00:00Z",
    )
    _create_book(client, title="Want", author="Author B", page_count=120, language="EN", reading_status="want_to_read")
    dnf = _create_book(client, title="DNF", author="Author A", language="FR", reading_status="did_not_finish")

    client.post(f"/api/books/{dnf['id']}/progress", json={"page": 40})
    client.post(f"/api/books/{dnf['id']}/progress", json={"page": 60})

    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_books_per_month"] == 1.5
    assert data["busiest_month"] == "2026-01"
    assert data["busiest_month_count"] == 2
    assert data["avg_page_count"] == 164.0
    assert data["most_popular_language"] == "EN"
    assert data["most_popular_language_count"] == 3
    assert data["status_distribution"] == {
        "want_to_read": 1, "currently_reading": 0, "read": 3, "did_not_finish": 1,
    }
    assert data["page_buckets"] == {"pages_to_read": 120, "pages_read": 600, "pages_wasted": 60}
    now = datetime.now(timezone.utc)
    expected_months = []
    year, month = 2026, 1
    while (year < now.year) or (year == now.year and month <= now.month):
        expected_months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    current_month = f"{now.year:04d}-{now.month:02d}"
    assert data["books_finished_per_month"] == [
        {"month": m, "count": 2 if m == "2026-01" else 1 if m == "2026-03" else 0}
        for m in expected_months
    ]
    assert data["pages_read_per_month"] == [
        {"month": m, "pages": 300 if m == "2026-01" else 300 if m == "2026-03" else 20 if m == current_month else 0}
        for m in expected_months
    ]
    expected_years = list(range(2026, now.year + 1))
    assert data["books_finished_per_year"] == [
        {"year": y, "count": 3 if y == 2026 else 0} for y in expected_years
    ]
    assert len(data["top_authors"]) == 2
    assert data["top_authors"][0]["author"] == "Author A"
    assert data["top_authors"][0]["book_count"] == 3
    top_a_cover_urls = [cover["cover_url"] for cover in data["top_authors"][0]["covers"]]
    assert "/api/covers/a1.jpg" in top_a_cover_urls
    assert "/api/covers/a2.jpg" in top_a_cover_urls
    assert data["top_authors"][1]["author"] == "Author B"
    assert data["top_authors"][1]["book_count"] == 2


def test_statistics_top_authors_limit_and_tiebreaker(client: Any) -> None:
    _create_book(client, title="A1", author="Author Z", reading_status="read")
    _create_book(client, title="A2", author="Author Z", reading_status="read")
    _create_book(client, title="B1", author="Author A", reading_status="read")
    _create_book(client, title="B2", author="Author A", reading_status="read")
    _create_book(client, title="C1", author="Author B", reading_status="read")
    _create_book(client, title="D1", author="Author C", reading_status="read")

    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    top_authors = resp.json()["top_authors"]
    assert len(top_authors) == 3
    assert [entry["author"] for entry in top_authors] == ["Author A", "Author Z", "Author B"]


def test_statistics_top_authors_cover_limit(client: Any) -> None:
    author = "Author Covers"
    for idx in range(1, 8):
        _create_book(client, title=f"Cover {idx}", author=author,
                     cover_url=f"/api/covers/{idx}.jpg", reading_status="read")

    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    top_authors = resp.json()["top_authors"]
    assert top_authors[0]["author"] == author
    assert len(top_authors[0]["covers"]) == 5


def test_statistics_top_authors_no_covers(client: Any) -> None:
    _create_book(client, title="No Cover 1", author="No Cover Author", reading_status="read")
    _create_book(client, title="No Cover 2", author="No Cover Author", reading_status="read")

    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    top_authors = resp.json()["top_authors"]
    assert top_authors[0]["author"] == "No Cover Author"
    assert len(top_authors[0]["covers"]) == 2
    assert all(c["cover_url"] is None for c in top_authors[0]["covers"])


def test_statistics_timezone_month_bucketing(client: Any, session: Session) -> None:
    settings = session.exec(select(UserSettings)).first()
    settings.timezone = "America/New_York"
    session.add(settings)
    session.commit()

    _create_book(client, title="Boundary", reading_status="read",
                 page_count=222, date_started="2026-05-01T03:00:00Z", date_finished="2026-05-01T03:00:00Z")

    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    data = resp.json()
    now = datetime.now(timezone.utc)
    expected_months = []
    year, month = 2026, 4
    while (year < now.year) or (year == now.year and month <= now.month):
        expected_months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    assert data["books_finished_per_month"] == [
        {"month": m, "count": 1 if m == "2026-04" else 0} for m in expected_months
    ]
    assert data["pages_read_per_month"] == [
        {"month": m, "pages": 222 if m == "2026-04" else 0} for m in expected_months
    ]


def test_statistics_pages_wasted_ignores_non_dnf(client: Any) -> None:
    read = _create_book(client, title="Read", reading_status="read")
    dnf = _create_book(client, title="DNF", reading_status="did_not_finish")
    client.post(f"/api/books/{read['id']}/progress", json={"page": 90})
    client.post(f"/api/books/{dnf['id']}/progress", json={"page": 33})

    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    assert resp.json()["page_buckets"]["pages_wasted"] == 33


def test_statistics_invalid_timezone_falls_back_to_utc(client: Any, session: Session) -> None:
    settings = session.exec(select(UserSettings)).first()
    settings.timezone = "Mars/OlympusMons"
    session.add(settings)
    session.commit()

    _create_book(client, title="UTC fallback", reading_status="read",
                 page_count=111, date_finished="2026-05-01T00:30:00Z")

    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    assert resp.json()["books_finished_per_month"] == [{"month": "2026-05", "count": 1}]


def test_pages_per_day_fallback_books_without_progress(client: Any) -> None:
    """Books marked read with start/finish dates but no progress entries contribute via fallback."""
    _create_book(client, title="Fallback Book", reading_status="read",
                 page_count=300, date_started="2026-05-01T10:00:00Z",
                 date_finished="2026-05-03T10:00:00Z")

    resp = client.get("/api/statistics/pages-per-day?days=730")
    assert resp.status_code == 200
    data = resp.json()["data"]
    dates = {row["date"]: row["pages"] for row in data}
    assert dates.get("2026-05-01") == 100
    assert dates.get("2026-05-02") == 100
    assert dates.get("2026-05-03") == 100


def test_pages_per_day_skips_books_missing_dates_or_pages(client: Any) -> None:
    """Books without date_started, date_finished, or page_count should be skipped in fallback."""
    _create_book(client, title="No Dates", reading_status="read", page_count=100)
    _create_book(client, title="No Pages", reading_status="read",
                 page_count=0,
                 date_started="2026-05-01T10:00:00Z", date_finished="2026-05-02T10:00:00Z")

    resp = client.get("/api/statistics/pages-per-day?days=730")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 0


def test_pages_per_day_skips_inverted_date_range(client: Any, session: Session) -> None:
    """Books with date_finished < date_started should be skipped."""
    book = Book(
        title="Inverted Dates", reading_status="read", page_count=100,
        date_started=datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc),
        date_finished=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        user_id=1,
    )
    session.add(book)
    session.commit()

    resp = client.get("/api/statistics/pages-per-day?days=730")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 0


def test_statistics_books_spanning_multiple_years(client: Any) -> None:
    """Books finished across year boundaries should trigger month/year rollover logic."""
    _create_book(client, title="Dec Book", reading_status="read",
                 page_count=100, date_finished="2025-12-15T10:00:00Z")
    _create_book(client, title="Jan Book", reading_status="read",
                 page_count=200, date_finished="2026-01-10T10:00:00Z")

    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    data = resp.json()
    now = datetime.now(timezone.utc)
    expected_months = []
    year, month = 2025, 12
    while (year < now.year) or (year == now.year and month <= now.month):
        expected_months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    assert data["books_finished_per_month"] == [
        {"month": m, "count": 1 if m in ("2025-12", "2026-01") else 0} for m in expected_months
    ]
    expected_years = list(range(2025, now.year + 1))
    assert data["books_finished_per_year"] == [
        {"year": y, "count": 1 if y == 2025 else 1 if y == 2026 else 0} for y in expected_years
    ]


def test_pages_per_day_counts_single_log_when_started_and_finished_same_day(client: Any, session: Session) -> None:
    date_iso = "2026-05-01T10:00:00Z"
    created = _create_book(client, title="Same-day single log", reading_status="read",
                           page_count=250, date_started=date_iso, date_finished=date_iso)

    book = session.get(Book, created["id"])
    assert book is not None
    session.add(ReadingProgress(
        book_id=book.id, user_id=book.user_id, page=250,
        created_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
    ))
    session.commit()

    resp = client.get("/api/statistics/pages-per-day?days=730")
    assert resp.status_code == 200
    data = resp.json()["data"]
    target = next((row for row in data if row["date"] == "2026-05-01"), None)
    assert target is not None
    assert target["pages"] == 250


# ── Direct unit tests for _extract_book_level_daily_pages edge cases ───────────


def test_extract_book_level_skips_books_with_missing_fields() -> None:
    """Books without date_started, date_finished or page_count are skipped."""
    book = Book(
        title="Incomplete", reading_status=ReadingStatus.read,
        date_started=None, date_finished=None, page_count=None, user_id=1,
    )
    result = _extract_book_level_daily_pages([book], timezone.utc)
    assert result == Counter()


def test_extract_book_level_skips_non_positive_total_days() -> None:
    """total_days <= 0 should cause the book to be skipped."""
    class FakeDateTime:
        def __lt__(self, other: object) -> bool:
            return False

        def __sub__(self, other: object) -> MagicMock:
            mock_delta = MagicMock()
            mock_delta.days = -1
            return mock_delta

    book = MagicMock()
    book.date_started = FakeDateTime()
    book.date_finished = FakeDateTime()
    book.page_count = 100

    result = _extract_book_level_daily_pages([book], timezone.utc)
    assert result == Counter()
