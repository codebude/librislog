from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import mean
from types import SimpleNamespace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Book, ReadingProgress, ReadingStatus, User, UserSettings
from app.schemas import (
    DailyPages,
    DailyPagesResponse,
    LanguageDistribution,
    MonthlyBooks,
    MonthlyPages,
    PageBuckets,
    StatisticsResponse,
    StatusDistribution,
    TopAuthor,
    TopAuthorCover,
    YearlyBooks,
)

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


def _user_timezone(session: Session, user_id: int) -> ZoneInfo:
    settings = session.exec(select(UserSettings).where(UserSettings.user_id == user_id)).first()
    timezone_name = settings.timezone if settings and settings.timezone else "UTC"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _month_key(dt: datetime, tz: ZoneInfo) -> str:
    local = dt.astimezone(tz)
    return f"{local.year:04d}-{local.month:02d}"


def _month_range(start_key: str, end_key: str) -> list[str]:
    start_year, start_month = map(int, start_key.split("-"))
    end_year, end_month = map(int, end_key.split("-"))
    keys: list[str] = []
    year, month = start_year, start_month
    while (year < end_year) or (year == end_year and month <= end_month):
        keys.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return keys


def _extract_progress_daily_pages(
    entries: list, tz: ZoneInfo
) -> Counter[str]:
    daily: Counter[str] = Counter()
    grouped: dict[int, list] = {}
    for entry in entries:
        grouped.setdefault(entry.book_id, []).append(entry)

    for book_id in sorted(grouped):
        book_entries = grouped[book_id]
        book_entries.sort(key=lambda e: (e.created_at, e.page))
        for prev, curr in zip(book_entries, book_entries[1:]):
            delta = curr.page - prev.page
            if delta > 0:
                day_diff = (curr.created_at - prev.created_at).days + 1
                if day_diff > 0:
                    daily_avg = delta / day_diff
                    current = prev.created_at
                    end_dt = curr.created_at
                    while current <= end_dt:
                        date_key = current.astimezone(tz).strftime("%Y-%m-%d")
                        daily[date_key] += daily_avg
                        current += timedelta(days=1)

    return daily


def _extract_book_level_daily_pages(books: list[Book], tz: ZoneInfo) -> Counter[str]:
    daily: Counter[str] = Counter()
    for book in books:
        if not (book.date_started and book.date_finished and book.page_count):
            continue
        if book.date_finished < book.date_started:
            continue
        total_days = (book.date_finished - book.date_started).days + 1
        if total_days <= 0:
            continue
        daily_avg = book.page_count / total_days
        current = book.date_started
        while current <= book.date_finished:
            date_key = current.astimezone(tz).strftime("%Y-%m-%d")
            daily[date_key] += daily_avg
            current += timedelta(days=1)
    return daily


@router.get("/pages-per-day", response_model=DailyPagesResponse)
def get_pages_per_day(
    days: int = Query(default=365, ge=1, le=730),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> DailyPagesResponse:
    tz = _user_timezone(session, current_user.id)
    end_date = datetime.now(tz)
    start_date = end_date - timedelta(days=days)

    start_date_utc = start_date.astimezone(timezone.utc).replace(tzinfo=None)
    end_date_utc = end_date.astimezone(timezone.utc).replace(tzinfo=None)

    progress_entries = list(
        session.exec(
            select(ReadingProgress)
            .where(
                ReadingProgress.user_id == current_user.id,
                ReadingProgress.created_at >= start_date_utc,
                ReadingProgress.created_at <= end_date_utc,
            )
            .order_by(ReadingProgress.book_id, ReadingProgress.created_at)
        ).all()
    )

    books = list(
        session.exec(select(Book).where(Book.user_id == current_user.id)).all()
    )

    books_with_progress = {e.book_id for e in progress_entries}

    virtual_entries = []
    for book in books:
        if book.id in books_with_progress and book.date_started:
            virtual_entries.append(
                SimpleNamespace(
                    book_id=book.id,
                    page=0,
                    created_at=book.date_started,
                )
            )

    all_progress_entries = list(progress_entries) + virtual_entries
    progress_daily = _extract_progress_daily_pages(all_progress_entries, tz)

    fallback_books = [
        b
        for b in books
        if b.id not in books_with_progress
        and b.reading_status == ReadingStatus.read
        and b.date_started
        and b.date_finished
        and b.page_count
    ]
    fallback_daily = _extract_book_level_daily_pages(fallback_books, tz)

    combined: Counter[str] = Counter()
    for k, v in progress_daily.items():
        combined[k] += v
    for k, v in fallback_daily.items():
        combined[k] += v

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    data = [
        DailyPages(date=date_str, pages=int(round(pages)))
        for date_str, pages in sorted(combined.items())
        if start_date_str <= date_str <= end_date_str
    ]

    return DailyPagesResponse(
        data=data,
        total_days=days,
        days_with_activity=len(data),
        total_pages=sum(d.pages for d in data),
    )


@router.get("", response_model=StatisticsResponse)
def get_statistics(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> StatisticsResponse:
    tz = _user_timezone(session, current_user.id)
    books = list(session.exec(select(Book).where(Book.user_id == current_user.id)).all())

    status_counts = Counter(book.reading_status for book in books)
    status_distribution = StatusDistribution(
        want_to_read=status_counts.get(ReadingStatus.want_to_read, 0),
        currently_reading=status_counts.get(ReadingStatus.currently_reading, 0),
        read=status_counts.get(ReadingStatus.read, 0),
        did_not_finish=status_counts.get(ReadingStatus.did_not_finish, 0),
    )

    page_values = [book.page_count for book in books if book.page_count is not None]
    avg_page_count = round(mean(page_values), 2) if page_values else None

    language_counts: Counter[str | None] = Counter(book.language for book in books)
    language_distribution = [
        LanguageDistribution(language=language, count=count)
        for language, count in sorted(
            language_counts.items(),
            key=lambda item: (-item[1], item[0] is None, item[0] or ""),
        )
    ]
    known_language_counts = [(code, count) for code, count in language_counts.items() if code]
    known_language_counts.sort(key=lambda item: (-item[1], item[0]))
    most_popular_language = known_language_counts[0][0] if known_language_counts else None
    most_popular_language_count = known_language_counts[0][1] if known_language_counts else None

    pages_to_read = sum(
        book.page_count or 0
        for book in books
        if book.reading_status == ReadingStatus.want_to_read and book.page_count is not None
    )
    pages_read = sum(
        book.page_count or 0
        for book in books
        if book.reading_status == ReadingStatus.read and book.page_count is not None
    )

    dnf_book_ids = [book.id for book in books if book.reading_status == ReadingStatus.did_not_finish and book.id is not None]
    pages_wasted = 0
    if dnf_book_ids:
        wasted_rows = session.exec(
            select(ReadingProgress.book_id, func.max(ReadingProgress.page))
            .where(
                ReadingProgress.user_id == current_user.id,
                ReadingProgress.book_id.in_(dnf_book_ids),
            )
            .group_by(ReadingProgress.book_id)
        ).all()
        pages_wasted = int(sum((max_page or 0) for _, max_page in wasted_rows))

    page_buckets = PageBuckets(
        pages_to_read=int(pages_to_read),
        pages_read=int(pages_read),
        pages_wasted=pages_wasted,
    )

    finished_books = [
        book
        for book in books
        if book.reading_status == ReadingStatus.read and book.date_finished is not None
    ]

    finished_books_per_month: Counter[str] = Counter()
    pages_read_per_month_counter: Counter[str] = Counter()
    for book in finished_books:
        month = _month_key(book.date_finished, tz)
        finished_books_per_month[month] += 1
        if book.page_count is not None:
            pages_read_per_month_counter[month] += int(book.page_count)

    if finished_books_per_month:
        avg_books_per_month = round(
            sum(finished_books_per_month.values()) / len(finished_books_per_month),
            2,
        )
        busiest_month, busiest_month_count = min(
            (
                (month, count)
                for month, count in finished_books_per_month.items()
            ),
            key=lambda item: (-item[1], item[0]),
        )
        month_keys = _month_range(min(finished_books_per_month), max(finished_books_per_month))
        books_finished_per_month = [
            MonthlyBooks(month=month, count=finished_books_per_month.get(month, 0)) for month in month_keys
        ]
    else:
        avg_books_per_month = None
        busiest_month = None
        busiest_month_count = None
        books_finished_per_month = []

    if pages_read_per_month_counter:
        month_keys = _month_range(min(pages_read_per_month_counter), max(pages_read_per_month_counter))
        pages_read_per_month = [
            MonthlyPages(month=month, pages=pages_read_per_month_counter.get(month, 0)) for month in month_keys
        ]
    else:
        pages_read_per_month = []

    if finished_books_per_month:
        yearly_counts: Counter[int] = Counter()
        for month_key, count in finished_books_per_month.items():
            yearly_counts[int(month_key.split("-")[0])] += count
        year_start = min(yearly_counts)
        year_end = max(yearly_counts)
        books_finished_per_year = [
            YearlyBooks(year=year, count=yearly_counts.get(year, 0))
            for year in range(year_start, year_end + 1)
        ]
    else:
        books_finished_per_year = []

    author_counts: Counter[str] = Counter()
    for book in books:
        if book.author and book.author.strip():
            author_counts[book.author.strip()] += 1

    top_authors: list[TopAuthor] = []
    if author_counts:
        author_items = sorted(author_counts.items(), key=lambda item: item[0].lower())
        top_author_counts = sorted(author_items, key=lambda item: item[1], reverse=True)[:3]
        top_author_names = [name for name, _ in top_author_counts]

        covers_by_author: dict[str, list[TopAuthorCover]] = {}
        for author_name in top_author_names:
            # Multiple books by the same author can share cover_url; distinct keeps the stack diverse.
            author_cover_rows = session.exec(
                select(Book.id, Book.reading_status, Book.cover_url)
                .where(
                    Book.user_id == current_user.id,
                    Book.author == author_name,
                    Book.cover_url.is_not(None),
                )
                .order_by(Book.id)
                .limit(5)
            ).all()
            covers_by_author[author_name] = [
                TopAuthorCover(book_id=book_id, reading_status=reading_status, cover_url=cover_url)
                for book_id, reading_status, cover_url in author_cover_rows
                if cover_url and book_id is not None
            ]

        top_authors = [
            TopAuthor(
                author=author_name,
                book_count=author_count,
                covers=covers_by_author.get(author_name, []),
            )
            for author_name, author_count in top_author_counts
        ]

    return StatisticsResponse(
        avg_books_per_month=avg_books_per_month,
        busiest_month=busiest_month,
        busiest_month_count=busiest_month_count,
        avg_page_count=avg_page_count,
        most_popular_language=most_popular_language,
        most_popular_language_count=most_popular_language_count,
        language_distribution=language_distribution,
        status_distribution=status_distribution,
        page_buckets=page_buckets,
        pages_read_per_month=pages_read_per_month,
        books_finished_per_month=books_finished_per_month,
        books_finished_per_year=books_finished_per_year,
        top_authors=top_authors,
    )
