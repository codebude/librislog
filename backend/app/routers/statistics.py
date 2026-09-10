"""Statistics dashboard — full stats, pages-per-day breakdown, and book-level fallback.

The heavy aggregation logic lives in :mod:`app.services.statistics`, which is
shared with the public profile endpoint. This router keeps only the
authentication layer and thin endpoint wrappers.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, select

from app.auth import require_user
from app.database import get_session
from app.models import Book, ReadingProgress, ReadingStatus, User, UserSettings
from app.schemas import (
    DailyPages,
    DailyPagesResponse,
    GamificationResponse,
    StatisticsRange,
    StatisticsResponse,
)
from app.services.statistics import (
    _compute_goal_progress,
    _day_key,
    _extract_book_level_daily_pages,
    _extract_progress_daily_pages,
    _naive_utc,
    _user_timezone,
    _zone_from_name,
    compute_statistics,
    current_streak,
    longest_streak,
)

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


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

    # Rebuild virtual entries with a simple namespace replacement.
    from types import SimpleNamespace

    virtual_entries = [
        SimpleNamespace(
            book_id=book.id,
            page=0,
            created_at=book.date_started,
        )
        for book in books
        if book.id in all_book_ids_with_progress
        and book.date_started
        and not (book.reading_status == ReadingStatus.read and not book.date_finished)
    ]

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

    combined: dict[str, float] = {}
    for k, v in progress_daily.items():
        combined[k] = combined.get(k, 0) + v
    for k, v in fallback_daily.items():
        combined[k] = combined.get(k, 0) + v

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
    range_value: StatisticsRange = Query(default=StatisticsRange.alltime, alias="range"),
    custom_from: Optional[date] = Query(default=None, alias="from"),
    custom_to: Optional[date] = Query(default=None, alias="to"),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> StatisticsResponse:
    """Return the full statistics dashboard for the authenticated user.

    The *range* query parameter selects a shared time window for the three
    trend charts (pages read per month, books finished per month/year).  When
    *range* is ``custom``, the ``from``/``to`` dates bound the window inclusive.
    All other statistics (status/acquisition distributions, top authors,
    ratings, page buckets) are computed over the full library.
    """
    assert current_user.id is not None
    return compute_statistics(
        session,
        current_user.id,
        range_value=range_value,
        custom_from=custom_from,
        custom_to=custom_to,
    )