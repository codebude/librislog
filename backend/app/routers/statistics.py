"""Statistics dashboard — full stats, pages-per-day breakdown, and book-level fallback."""

import calendar
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from types import SimpleNamespace
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.auth import require_user
from app.database import get_session
from app.models import AcquisitionStatus, Author, Book, BookAuthor, ReadingProgress, ReadingStatus, User, UserSettings
from app.services.authors import join_authors, load_authors_batch
from app.schemas import (
    AcquisitionStatusDistribution,
    DailyPages,
    DailyPagesResponse,
    GamificationResponse,
    GoalProgress,
    GoalType,
    LanguageDistribution,
    MonthlyBooks,
    MonthlyPages,
    PageBuckets,
    StatisticsResponse,
    StatusDistribution,
    TopAuthor,
    TopAuthorCover,
    TopRatedBook,
    YearlyBooks,
)

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


def _zone_from_name(timezone_name: str | None) -> ZoneInfo:
    """Return a ZoneInfo for *timezone_name*, falling back to UTC."""
    try:
        return ZoneInfo(timezone_name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _user_timezone(session: Session, user_id: int) -> ZoneInfo:
    """Return the user's configured timezone, falling back to UTC."""
    settings = session.exec(select(UserSettings).where(UserSettings.user_id == user_id)).first()
    return _zone_from_name(settings.timezone if settings else None)


def _month_key(dt: datetime, tz: ZoneInfo) -> str:
    """Format a datetime as ``YYYY-MM`` in the given timezone."""
    local = dt.astimezone(tz)
    return f"{local.year:04d}-{local.month:02d}"


def _month_range(start_key: str, end_key: str) -> list[str]:
    """Generate a list of ``YYYY-MM`` keys from *start_key* to *end_key* inclusive."""
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


def _clamp_window(
    start: datetime, end: datetime,
    window_start: datetime | None, window_end: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    """Clamp *start*/*end* to *window_start*/*window_end* if provided.
    
    Returns (clamped_start, clamped_end) or (None, None) when the span
    does not overlap the window at all.
    All returned datetimes are UTC-aware (matching the DB convention)
    so callers can safely use .astimezone() and compare.
    """
    if window_start is not None:
        w_start = _naive_utc(window_start)
        s = _naive_utc(start)
        e = _naive_utc(end)
        if e < w_start:
            return (None, None)
        if s < w_start:
            start = w_start.replace(tzinfo=timezone.utc)
    if window_end is not None:
        w_end = _naive_utc(window_end)
        s = _naive_utc(start)
        e = _naive_utc(end)
        if s > w_end:
            return (None, None)
        if e > w_end:
            end = w_end.replace(tzinfo=timezone.utc)
    return (start, end)


def _naive_utc(dt: datetime) -> datetime:
    """Return a naive datetime representing the same instant as *dt* in UTC."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _extract_progress_daily_pages(
    entries: list, tz: ZoneInfo,
    window_start: datetime | None = None, window_end: datetime | None = None,
) -> dict[str, float]:
    """Distribute reading progress page-deltas across calendar days.
    
    When *window_start*/*window_end* are provided, only days within that
    window are emitted.  The daily average is still computed from the full
    span so the values stay correct.
    """
    daily: dict[str, float] = defaultdict(float)
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
                    start, end = _clamp_window(prev.created_at, curr.created_at, window_start, window_end)
                    if start is None or end is None:
                        continue
                    while start <= end:
                        date_key = start.astimezone(tz).strftime("%Y-%m-%d")
                        daily[date_key] += daily_avg
                        start += timedelta(days=1)

    return daily


def _extract_book_level_daily_pages(
    books: list[Book], tz: ZoneInfo,
    window_start: datetime | None = None, window_end: datetime | None = None,
) -> dict[str, float]:
    """Distribute page counts across the reading period for books finished without progress entries.
    
    When *window_start*/*window_end* are provided, only days within that
    window are emitted.  The daily average is still computed from the full
    span so the values stay correct.
    """
    daily: dict[str, float] = defaultdict(float)
    for book in books:
        if not (book.date_started and book.date_finished and book.page_count):
            continue
        if book.date_finished < book.date_started:
            continue
        total_days = (book.date_finished - book.date_started).days + 1
        if total_days <= 0:
            continue
        daily_avg = book.page_count / total_days
        start, end = _clamp_window(book.date_started, book.date_finished, window_start, window_end)
        if start is None or end is None:
            continue
        while start <= end:
            date_key = start.astimezone(tz).strftime("%Y-%m-%d")
            daily[date_key] += daily_avg
            start += timedelta(days=1)
    return daily


def _allocate_daily_avg_across_months(
    daily_avg: float, start: datetime, end: datetime, tz: ZoneInfo
) -> dict[str, float]:
    """Spread a per-day value proportionally across months from *start* to *end* inclusive."""
    monthly: dict[str, float] = defaultdict(float)
    current = start
    while current <= end:
        _, last_dom = calendar.monthrange(current.year, current.month)
        period_end = min(current.replace(day=last_dom), end)
        days = (period_end - current).days + 1
        month_key = _month_key(current, tz)
        monthly[month_key] += daily_avg * days
        current = period_end + timedelta(days=1)
    return monthly


def _compute_pages_per_month_from_progress(entries: list, tz: ZoneInfo) -> dict[str, float]:
    """Compute pages read per month from reading progress entries."""
    monthly: dict[str, float] = defaultdict(float)
    grouped: dict[int, list] = {}
    for entry in entries:
        grouped.setdefault(entry.book_id, []).append(entry)
    for book_id in sorted(grouped):
        book_entries = sorted(grouped[book_id], key=lambda e: (e.created_at, e.page))
        for prev, curr in zip(book_entries, book_entries[1:]):
            delta = curr.page - prev.page
            if delta <= 0:
                continue
            day_diff = (curr.created_at - prev.created_at).days + 1
            if day_diff <= 0:
                continue
            m = _allocate_daily_avg_across_months(delta / day_diff, prev.created_at, curr.created_at, tz)
            for k, v in m.items():
                monthly[k] += v
    return monthly


def _compute_pages_per_month_from_books(books: list[Book], tz: ZoneInfo) -> dict[str, float]:
    """Compute pages read per month for finished books without progress entries."""
    monthly: dict[str, float] = defaultdict(float)
    for book in books:
        if not (book.date_started and book.date_finished and book.page_count):
            continue
        if book.date_finished < book.date_started:
            continue
        total_days = (book.date_finished - book.date_started).days + 1
        if total_days <= 0:
            continue
        m = _allocate_daily_avg_across_months(
            book.page_count / total_days, book.date_started, book.date_finished, tz
        )
        for k, v in m.items():
            monthly[k] += v
    return monthly


def _day_key(dt: datetime, tz: ZoneInfo) -> str:
    """Return the ``YYYY-MM-DD`` calendar day of *dt* in *tz*."""
    return dt.astimezone(tz).strftime("%Y-%m-%d")


def current_streak(active_dates: set[str], today: date) -> int:
    """Return the number of consecutive active days ending at *today*.

    Today counts as the first day when it is active; otherwise the streak
    starts at yesterday, so a not-yet-logged today does not break an ongoing
    streak.  The streak is 0 when neither today nor yesterday are active.
    """
    streak = 0
    day = today
    first = True
    while True:
        if day.isoformat() in active_dates:
            streak += 1
        elif not first:
            break
        first = False
        day -= timedelta(days=1)
    return streak


def longest_streak(active_dates: set[str]) -> tuple[int, Optional[str], Optional[str]]:
    """Return the longest consecutive run of active dates.

    Returns ``(length, start, end)`` with ``YYYY-MM-DD`` keys.  Ties are
    broken in favour of the most recent run.  When there is no activity at
    all the result is ``(0, None, None)``.
    """
    if not active_dates:
        return 0, None, None
    ordered = sorted(active_dates)
    best_len, best_start, best_end = 0, None, None
    run_start = ordered[0]
    run_len = 1
    prev = ordered[0]
    for current in ordered[1:]:
        if (date.fromisoformat(current) - date.fromisoformat(prev)).days == 1:
            run_len += 1
        else:
            if run_len >= best_len:
                best_len, best_start, best_end = run_len, run_start, prev
            run_start, run_len = current, 1
        prev = current
    if run_len >= best_len:
        best_len, best_start, best_end = run_len, run_start, prev
    return best_len, best_start, best_end


def _pages_logged_on_day(entries: list, tz: ZoneInfo, day_key: str) -> int:
    """Sum the positive page-deltas logged on *day_key*.

    A delta is the page gain between two consecutive progress entries of the
    same book, attributed to the calendar day (in *tz*) of the later entry.
    """
    grouped: dict[int, list] = {}
    for entry in entries:
        grouped.setdefault(entry.book_id, []).append(entry)
    total = 0
    for book_entries in grouped.values():
        book_entries.sort(key=lambda e: (e.created_at, e.page))
        for prev, curr in zip(book_entries, book_entries[1:]):
            delta = curr.page - prev.page
            if delta > 0 and _day_key(curr.created_at, tz) == day_key:
                total += delta
    return total


def _compute_goal_progress(
    tz: ZoneInfo,
    settings: UserSettings,
    today: datetime,
    entries: list,
    books: list,
    book_ids_with_progress: set[int],
) -> list[GoalProgress]:
    """Compute current progress for every enabled reading goal.

    Disabled goals are omitted from the response; the dashboard only shows
    goals the user opted into.
    """
    today_key = today.strftime("%Y-%m-%d")
    current_month_key = today.strftime("%Y-%m")
    current_year = today.year

    fallback_books = [
        b
        for b in books
        if b.id not in book_ids_with_progress
        and b.reading_status == ReadingStatus.read
        and b.date_started
        and b.date_finished
        and b.page_count
    ]

    # Mirror get_statistics: anchor every book with progress at page 0 on its
    # start date so the first progress delta is attributed to the reading span,
    # keeping the pages-per-month goal consistent with the statistics chart.
    virtual_entries = [
        SimpleNamespace(book_id=b.id, page=0, created_at=b.date_started)
        for b in books
        if b.id in book_ids_with_progress
        and b.date_started
        and not (b.reading_status == ReadingStatus.read and not b.date_finished)
    ]

    goals_spec = [
        (GoalType.pages_per_day, settings.goal_pages_per_day_enabled, settings.goal_pages_per_day),
        (GoalType.pages_per_month, settings.goal_pages_per_month_enabled, settings.goal_pages_per_month),
        (GoalType.books_per_month, settings.goal_books_per_month_enabled, settings.goal_books_per_month),
        (GoalType.books_per_year, settings.goal_books_per_year_enabled, settings.goal_books_per_year),
    ]

    results: list[GoalProgress] = []
    for goal_type, enabled, target in goals_spec:
        if not enabled:
            continue
        current = _goal_current_value(
            goal_type, tz, today_key, current_month_key, current_year,
            entries, books, fallback_books, virtual_entries,
        )
        results.append(
            GoalProgress(type=goal_type, target=target, current=current, reached=current >= target)
        )
    return results


def _goal_current_value(
    goal_type: GoalType,
    tz: ZoneInfo,
    today_key: str,
    current_month_key: str,
    current_year: int,
    entries: list,
    books: list,
    fallback_books: list,
    virtual_entries: list,
) -> int:
    """Return the current value for a single reading goal."""
    if goal_type == GoalType.pages_per_day:
        total = _pages_logged_on_day(entries, tz, today_key)
        for b in fallback_books:
            if _day_key(b.date_finished, tz) == today_key:
                total += b.page_count
        return total

    if goal_type == GoalType.pages_per_month:
        monthly = _compute_pages_per_month_from_progress(entries + virtual_entries, tz)
        for k, v in _compute_pages_per_month_from_books(fallback_books, tz).items():
            monthly[k] += v
        return int(round(monthly.get(current_month_key, 0)))

    if goal_type == GoalType.books_per_month:
        return sum(
            1
            for b in books
            if b.reading_status == ReadingStatus.read
            and b.date_finished is not None
            and _month_key(b.date_finished, tz) == current_month_key
        )

    if goal_type == GoalType.books_per_year:
        return sum(
            1
            for b in books
            if b.reading_status == ReadingStatus.read
            and b.date_finished is not None
            and b.date_finished.astimezone(tz).year == current_year
        )

    return 0


@router.get("/gamification", response_model=GamificationResponse)
def get_gamification(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> GamificationResponse:
    """Return dashboard gamification data — reading streaks and goal progress."""
    assert current_user.id is not None

    settings = session.exec(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    ).first()
    tz = _zone_from_name(settings.timezone if settings else None)
    today = datetime.now(tz)
    if not settings:
        settings = UserSettings(user_id=current_user.id, language="en")

    if not settings.gamification_enabled:
        return GamificationResponse(
            enabled=False,
            current_streak=0,
            longest_streak=0,
            longest_streak_start=None,
            longest_streak_end=None,
            goals=[],
        )

    # Only the columns needed for streaks and goal progress are loaded; the
    # per-request cost still grows with lifetime library size, which is
    # acceptable for typical personal-library volumes.
    entries = list(
        session.exec(
            select(ReadingProgress)
            .where(ReadingProgress.user_id == current_user.id)
            .order_by(col(ReadingProgress.book_id), col(ReadingProgress.created_at))
        ).all()
    )
    books = list(
        session.exec(
            select(Book)
            .where(Book.user_id == current_user.id)
            .order_by(col(Book.id))
        ).all()
    )
    book_ids_with_progress = {entry.book_id for entry in entries}

    active_dates = {_day_key(entry.created_at, tz) for entry in entries}
    for book in books:
        if (
            book.id not in book_ids_with_progress
            and book.reading_status == ReadingStatus.read
            and book.date_finished is not None
        ):
            active_dates.add(_day_key(book.date_finished, tz))

    current = current_streak(active_dates, today.date())
    longest, longest_start, longest_end = longest_streak(active_dates)

    goals = _compute_goal_progress(
        tz, settings, today, entries, books, book_ids_with_progress
    )

    return GamificationResponse(
        enabled=True,
        current_streak=current,
        longest_streak=longest,
        longest_streak_start=longest_start,
        longest_streak_end=longest_end,
        goals=goals,
    )


@router.get("/pages-per-day", response_model=DailyPagesResponse)
def get_pages_per_day(
    days: int = Query(default=365, ge=1, le=730),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> DailyPagesResponse:
    """Return a daily page-count breakdown for the last N days.
    """
    assert current_user.id is not None
    tz = _user_timezone(session, current_user.id)
    end_date = datetime.now(tz)
    start_date = end_date - timedelta(days=days)

    start_date_utc = start_date.astimezone(timezone.utc).replace(tzinfo=None)
    end_date_utc = end_date.astimezone(timezone.utc).replace(tzinfo=None)

    # Books with at least one progress entry in the window — we need their full
    # entry chains to compute correct daily averages.
    book_ids_with_window_progress = set(
        session.exec(
            select(ReadingProgress.book_id)
            .where(
                ReadingProgress.user_id == current_user.id,
                ReadingProgress.created_at >= start_date_utc,
            )
            .distinct()
        ).all()
    )

    # Load full entry chains for those books (including entries before the window
    # so that the prev→curr delta and day_diff span are complete).
    if book_ids_with_window_progress:
        progress_entries = list(
            session.exec(
                select(ReadingProgress)
                .where(
                    ReadingProgress.user_id == current_user.id,
                    col(ReadingProgress.book_id).in_(book_ids_with_window_progress),
                )
                .order_by(col(ReadingProgress.book_id), col(ReadingProgress.created_at))
            ).all()
        )
    else:
        progress_entries = []

    # All book_ids with *any* progress entry (used to exclude books from fallback).
    all_book_ids_with_progress = set(
        session.exec(
            select(ReadingProgress.book_id)
            .where(ReadingProgress.user_id == current_user.id)
            .distinct()
        ).all()
    )

    books = list(
        session.exec(select(Book).where(Book.user_id == current_user.id)).all()
    )

    virtual_entries = []
    for book in books:
        if book.id not in all_book_ids_with_progress or not book.date_started:
            continue
        # Finished books without date_finished have no bounded reading
        # period; skip to avoid spreading pages from date_started to
        # today via a single import-created progress entry.
        if book.reading_status == ReadingStatus.read and not book.date_finished:
            continue
        virtual_entries.append(
            SimpleNamespace(
                book_id=book.id,
                page=0,
                created_at=book.date_started,
            )
        )

    all_progress_entries = list(progress_entries) + virtual_entries
    progress_daily = _extract_progress_daily_pages(all_progress_entries, tz, start_date_utc, end_date_utc)

    fallback_books = [
        b
        for b in books
        if b.id not in all_book_ids_with_progress
        and b.reading_status == ReadingStatus.read
        and b.date_started
        and b.date_finished
        and b.page_count
        # Only include books whose reading period could overlap the window.
        and _naive_utc(b.date_finished) >= start_date_utc
    ]
    fallback_daily = _extract_book_level_daily_pages(fallback_books, tz, start_date_utc, end_date_utc)

    combined: dict[str, float] = defaultdict(float)
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
        total_pages=int(round(sum(pages for _, pages in sorted(combined.items()) if start_date_str <= _ <= end_date_str))),
    )


@router.get("", response_model=StatisticsResponse)
def get_statistics(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> StatisticsResponse:
    """Return the full statistics dashboard for the authenticated user."""
    assert current_user.id is not None
    tz = _user_timezone(session, current_user.id)
    now = datetime.now(tz)
    current_month_key = f"{now.year:04d}-{now.month:02d}"
    current_year = now.year
    books = list(session.exec(select(Book).where(Book.user_id == current_user.id)).all())

    total_authors = session.exec(
        select(func.count()).select_from(Author).where(Author.user_id == current_user.id)
    ).one()

    status_counts = Counter(book.reading_status for book in books)
    status_distribution = StatusDistribution(
        want_to_read=status_counts.get(ReadingStatus.want_to_read, 0),
        currently_reading=status_counts.get(ReadingStatus.currently_reading, 0),
        read=status_counts.get(ReadingStatus.read, 0),
        did_not_finish=status_counts.get(ReadingStatus.did_not_finish, 0),
    )

    acquisition_counts = Counter(book.acquisition_status for book in books)
    acquisition_status_distribution = AcquisitionStatusDistribution(
        owned=acquisition_counts.get(AcquisitionStatus.owned, 0),
        borrowed=acquisition_counts.get(AcquisitionStatus.borrowed, 0),
        digital_access=acquisition_counts.get(AcquisitionStatus.digital_access, 0),
        to_acquire=acquisition_counts.get(AcquisitionStatus.to_acquire, 0),
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
                col(ReadingProgress.book_id).in_(dnf_book_ids),
            )
            .group_by(col(ReadingProgress.book_id))
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
    for book in finished_books:
        assert book.date_finished is not None
        month = _month_key(book.date_finished, tz)
        finished_books_per_month[month] += 1

    progress_entries = list(
        session.exec(
            select(ReadingProgress)
            .where(ReadingProgress.user_id == current_user.id)
            .order_by(col(ReadingProgress.book_id), col(ReadingProgress.created_at))
        ).all()
    )

    books_with_progress = {e.book_id for e in progress_entries}

    virtual_entries = []
    for book in books:
        if book.id not in books_with_progress or not book.date_started:
            continue
        if book.reading_status == ReadingStatus.read and not book.date_finished:
            continue
        virtual_entries.append(
            SimpleNamespace(
                book_id=book.id,
                page=0,
                created_at=book.date_started,
            )
        )

    all_progress_entries = list(progress_entries) + virtual_entries
    pages_read_per_month_counter = _compute_pages_per_month_from_progress(all_progress_entries, tz)

    fallback_books = [
        b
        for b in books
        if b.id not in books_with_progress
        and b.reading_status == ReadingStatus.read
        and b.date_started
        and b.date_finished
        and b.page_count
    ]
    fallback_monthly = _compute_pages_per_month_from_books(fallback_books, tz)
    for k, v in fallback_monthly.items():
        pages_read_per_month_counter[k] += v

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
        month_keys = _month_range(min(finished_books_per_month), max(max(finished_books_per_month), current_month_key))
        books_finished_per_month = [
            MonthlyBooks(month=month, count=finished_books_per_month.get(month, 0)) for month in month_keys
        ]
    else:
        avg_books_per_month = None
        busiest_month = None
        busiest_month_count = None
        books_finished_per_month = []

    if pages_read_per_month_counter:
        all_months = set(pages_read_per_month_counter) | {current_month_key}
        if finished_books_per_month:
            all_months |= set(finished_books_per_month)
        month_keys = _month_range(min(all_months), max(all_months))
        pages_read_per_month = [
            MonthlyPages(month=month, pages=int(round(pages_read_per_month_counter.get(month, 0)))) for month in month_keys
        ]
    else:
        pages_read_per_month = []

    if finished_books_per_month:
        yearly_counts: Counter[int] = Counter()
        for month_key, count in finished_books_per_month.items():
            yearly_counts[int(month_key.split("-")[0])] += count
        year_start = min(yearly_counts)
        year_end = max(max(yearly_counts), current_year)
        books_finished_per_year = [
            YearlyBooks(year=year, count=yearly_counts.get(year, 0))
            for year in range(year_start, year_end + 1)
        ]
    else:
        books_finished_per_year = []

    author_count_label = func.count(func.distinct(BookAuthor.book_id)).label("cnt")
    author_count_rows = session.exec(
        select(Author.name, author_count_label)
        .join(BookAuthor, col(BookAuthor.author_id) == col(Author.id))
        .join(Book, col(Book.id) == col(BookAuthor.book_id))
        .where(Book.user_id == current_user.id)
        .group_by(col(Author.id))
        .order_by(author_count_label.desc(), col(Author.name).asc())
        .limit(3)
    ).all()
    author_counts = Counter({name: count for name, count in author_count_rows})

    top_authors: list[TopAuthor] = []
    if author_counts:
        top_author_counts = author_counts.most_common(3)
        top_author_names = [name for name, _ in top_author_counts]

        covers_by_author: dict[str, list[TopAuthorCover]] = {}
        for author_name in top_author_names:
            max_slots = min(5, author_counts[author_name])
            book_ids_with_author = select(BookAuthor.book_id).join(
                Author, col(Author.id) == col(BookAuthor.author_id)
            ).where(
                Author.user_id == current_user.id,
                Author.name == author_name,
            )
            cover_rows = session.exec(
                select(Book.id, Book.title, Book.reading_status, Book.cover_url)
                .where(
                    Book.user_id == current_user.id,
                    col(Book.id).in_(book_ids_with_author),
                    col(Book.cover_url).is_not(None),
                )
                .order_by(col(Book.id))
                .limit(max_slots)
            ).all()
            results = [
                TopAuthorCover(book_id=book_id, title=title, reading_status=reading_status, cover_url=cover_url)
                for book_id, title, reading_status, cover_url in cover_rows
                if book_id is not None
            ]
            remaining = max_slots - len(results)
            if remaining > 0:
                no_cover_rows = session.exec(
                    select(Book.id, Book.title, Book.reading_status, Book.cover_url)
                    .where(
                        Book.user_id == current_user.id,
                        col(Book.id).in_(book_ids_with_author),
                        col(Book.cover_url).is_(None),
                    )
                    .order_by(col(Book.id))
                    .limit(remaining)
                ).all()
                results.extend(
                    TopAuthorCover(book_id=book_id, title=title, reading_status=reading_status, cover_url=cover_url)
                    for book_id, title, reading_status, cover_url in no_cover_rows
                    if book_id is not None
                )
            covers_by_author[author_name] = results

        top_authors = [
            TopAuthor(
                author=author_name,
                book_count=author_count,
                covers=covers_by_author.get(author_name, []),
            )
            for author_name, author_count in top_author_counts
        ]

    # --- Rating stats ---
    books_with_rating = sum(1 for b in books if b.rating is not None)
    books_without_rating = sum(1 for b in books if b.rating is None)
    rating_values = [b.rating for b in books if b.rating is not None]
    average_rating = round(mean(rating_values), 2) if rating_values else None

    rated_books = [b for b in books if b.rating is not None]
    rated_book_ids = [b.id for b in rated_books if b.id is not None]
    rated_authors_map = load_authors_batch(session, rated_book_ids)

    def _rating_sort_key(book: Book) -> tuple[int, float]:
        assert book.rating is not None
        return (book.rating, -(book.date_added or datetime.min).timestamp())

    # Top rated: highest rating first; ties broken by newest-added first.
    top_rated_books = []
    for b in sorted(rated_books, key=lambda x: (-_rating_sort_key(x)[0], _rating_sort_key(x)[1])):
        assert b.id is not None
        assert b.rating is not None
        author_names = rated_authors_map.get(b.id, [])
        top_rated_books.append(
            TopRatedBook(book_id=b.id, title=b.title or "", author=join_authors(author_names), authors=author_names, rating=b.rating, reading_status=b.reading_status, cover_url=b.cover_url)
        )

    # Worst rated: lowest rating first; ties broken by newest-added first.
    worst_rated_books = []
    for b in sorted(rated_books, key=_rating_sort_key):
        assert b.id is not None
        assert b.rating is not None
        author_names = rated_authors_map.get(b.id, [])
        worst_rated_books.append(
            TopRatedBook(book_id=b.id, title=b.title or "", author=join_authors(author_names), authors=author_names, rating=b.rating, reading_status=b.reading_status, cover_url=b.cover_url)
        )

    return StatisticsResponse(
        total_books=len(books),
        total_authors=total_authors,
        avg_books_per_month=avg_books_per_month,
        busiest_month=busiest_month,
        busiest_month_count=busiest_month_count,
        avg_page_count=avg_page_count,
        most_popular_language=most_popular_language,
        most_popular_language_count=most_popular_language_count,
        language_distribution=language_distribution,
        status_distribution=status_distribution,
        acquisition_status_distribution=acquisition_status_distribution,
        page_buckets=page_buckets,
        pages_read_per_month=pages_read_per_month,
        books_finished_per_month=books_finished_per_month,
        books_finished_per_year=books_finished_per_year,
        top_authors=top_authors,
        books_with_rating=books_with_rating,
        books_without_rating=books_without_rating,
        average_rating=average_rating,
        top_rated_books=top_rated_books,
        worst_rated_books=worst_rated_books,
    )
