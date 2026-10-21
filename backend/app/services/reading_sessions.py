"""Reading session lifecycle, mirroring, and query helpers.

This module is the single place that owns the invariants between ``Book`` and its
``ReadingSession`` rows:

- A book has at most one *current* session (``is_current=True``), which is the
  session being read right now.
- ``Book.date_started`` / ``Book.date_finished`` mirror the current session, or
  the latest session when none is current (``NULL`` when no session exists).
- Historical sessions are never modified implicitly by status transitions, only
  by explicit session edits.

Keeping the mirror here (and calling it after every write that touches reading
dates) guarantees that a book with a single session behaves identically to the
pre-session model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, col, select

from app.models import Book, ReadingProgress, ReadingSession, ReadingStatus
from app.schemas import ReadingSessionRead
from app.time_utils import utcnow


def session_counts(session: Session, book_ids: list[int]) -> dict[int, dict[str, int]]:
    """Return ``{book_id: {"session_count": n, "read_count": n}}`` for the ids."""
    if not book_ids:
        return {}
    counts: dict[int, dict[str, int]] = {
        bid: {"session_count": 0, "read_count": 0} for bid in book_ids
    }
    rows = session.exec(
        select(ReadingSession.book_id, ReadingSession.status).where(
            col(ReadingSession.book_id).in_(book_ids)
        )
    ).all()
    for book_id, status in rows:
        entry = counts.setdefault(book_id, {"session_count": 0, "read_count": 0})
        entry["session_count"] += 1
        if status == ReadingStatus.read:
            entry["read_count"] += 1
    return counts


def sessions_for_book(session: Session, book_id: int) -> list[ReadingSession]:
    """Return all sessions of a book, newest first (by created_at, then id)."""
    return list(
        session.exec(
            select(ReadingSession)
            .where(ReadingSession.book_id == book_id)
            .order_by(col(ReadingSession.created_at).desc(), col(ReadingSession.id).desc())
        ).all()
    )


def active_session(session: Session, book_id: int) -> ReadingSession | None:
    """Return the book's current (open) session, or ``None``."""
    return session.exec(
        select(ReadingSession).where(
            ReadingSession.book_id == book_id,
            ReadingSession.is_current.is_(True),
        )
    ).first()


def assign_read_numbers(sessions: list[ReadingSession]) -> dict[int, int]:
    """Compute and return ``{session_id: read_number}`` for completed sessions.

    Completed (``read``) sessions are ordered chronologically by finish date
    (tie-break: start date, then id) and numbered from 1. Non-completed sessions
    get no read number.
    """
    completed = [s for s in sessions if s.status == ReadingStatus.read]
    completed.sort(
        key=lambda s: (
            s.date_finished or s.date_started or utcnow(),
            s.date_started or utcnow(),
            s.id or 0,
        )
    )
    return {s.id: idx + 1 for idx, s in enumerate(completed)}


def progress_aggregates(
    session: Session, book_id: int
) -> dict[int, tuple[int, int | None, int | None]]:
    """Return ``{session_id: (count, last_page, max_page)}`` for a book's sessions.

    Entries without a session are grouped under key ``0``.
    """
    rows = session.exec(
        select(ReadingProgress.session_id, ReadingProgress.page).where(
            ReadingProgress.book_id == book_id
        )
    ).all()
    agg: dict[int, list[int]] = {}
    for sid, page in rows:
        agg.setdefault(sid or 0, []).append(page)
    result: dict[int, tuple[int, int | None, int | None]] = {}
    for sid, pages in agg.items():
        result[sid] = (len(pages), max(pages), max(pages))
    return result


def build_session_read(
    session: Session,
    reading_session: ReadingSession,
    read_number: Optional[int],
    agg: Optional[tuple[int, int | None, int | None]] = None,
) -> ReadingSessionRead:
    """Build a :class:`ReadingSessionRead` for a session, with aggregates."""
    if agg is None:
        aggs = progress_aggregates(session, reading_session.book_id)
        agg = aggs.get(reading_session.id or 0, (0, None, None))
    count, last_page, max_page = agg
    return ReadingSessionRead(
        id=reading_session.id or 0,
        book_id=reading_session.book_id,
        status=reading_session.status,
        date_started=reading_session.date_started,
        date_finished=reading_session.date_finished,
        is_current=reading_session.is_current,
        read_number=read_number,
        is_reread=read_number is not None and read_number >= 2,
        progress_count=count,
        last_page=last_page,
        max_page=max_page,
        created_at=reading_session.created_at,
        updated_at=reading_session.updated_at,
    )


def recompute_book_mirror(book: Book, sessions: list[ReadingSession]) -> None:
    """Re-derive ``Book`` dates from the current (else latest) session."""
    current = next((s for s in sessions if s.is_current), None)
    if current is not None:
        book.date_started = current.date_started
        book.date_finished = None
        if current.status != ReadingStatus.currently_reading:
            book.date_finished = current.date_finished
        return
    latest = sessions[0] if sessions else None
    if latest is None:
        book.date_started = None
        book.date_finished = None
        return
    book.date_started = latest.date_started
    book.date_finished = latest.date_finished


def create_initial_session(
    session: Session, book: Book
) -> ReadingSession | None:
    """Create the initial session for a freshly created/imported book.

    Only books with a non-want-to-read status get a session; the session mirrors
    the book's dates. Returns ``None`` when no session was created.
    """
    if book.id is None:
        return None
    if book.reading_status == ReadingStatus.want_to_read:
        return None
    s = ReadingSession(
        book_id=book.id,
        user_id=book.user_id,
        status=book.reading_status,
        date_started=book.date_started,
        date_finished=book.date_finished,
        is_current=book.reading_status == ReadingStatus.currently_reading,
    )
    session.add(s)
    session.flush()
    return s


def start_read_again(
    session: Session, book: Book, date_started: Optional[datetime]
) -> ReadingSession:
    """Start a re-read: demote any current session and open a new one."""
    now = utcnow()
    for s in sessions_for_book(session, book.id or 0):
        if s.is_current:
            s.is_current = False
            session.add(s)
    new_session = ReadingSession(
        book_id=book.id,
        user_id=book.user_id,
        status=ReadingStatus.currently_reading,
        date_started=date_started or now,
        date_finished=None,
        is_current=True,
    )
    session.add(new_session)
    book.reading_status = ReadingStatus.currently_reading
    book.date_started = new_session.date_started
    book.date_finished = None
    session.add(book)
    session.flush()
    return new_session


def reconcile_book_sessions(session: Session, book: Book) -> None:
    """Reconcile a book's sessions with its current status after a book write.

    Ensures the invariant that a book's sessions reflect its status:

    - ``currently_reading``: exactly one current (open) session exists; it is
      created on first read or re-read, or its start date is updated.
    - ``read`` / ``did_not_finish``: any current session is closed and a
      completed session exists (created or updated) for the finish.
    - ``want_to_read``: sessions are left untouched (pure history).

    This never overwrites the book's own date fields; it only keeps the session
    rows consistent so statistics and history stay correct.
    """
    if book.id is None:
        return
    current = active_session(session, book.id)

    if book.reading_status == ReadingStatus.currently_reading:
        if current is not None:
            current.status = ReadingStatus.currently_reading
            current.date_started = book.date_started
            current.date_finished = None
            current.is_current = True
            session.add(current)
        else:
            session.add(
                ReadingSession(
                    book_id=book.id,
                    user_id=book.user_id,
                    status=ReadingStatus.currently_reading,
                    date_started=book.date_started,
                    date_finished=None,
                    is_current=True,
                )
            )
    elif book.reading_status in (ReadingStatus.read, ReadingStatus.did_not_finish):
        if current is not None:
            current.status = book.reading_status
            current.date_finished = book.date_finished
            current.is_current = False
            session.add(current)
        else:
            sessions = sessions_for_book(session, book.id)
            latest = sessions[0] if sessions else None
            if latest is not None and latest.status == book.reading_status:
                latest.date_started = book.date_started
                latest.date_finished = book.date_finished
                session.add(latest)
            else:
                session.add(
                    ReadingSession(
                        book_id=book.id,
                        user_id=book.user_id,
                        status=book.reading_status,
                        date_started=book.date_started,
                        date_finished=book.date_finished,
                        is_current=False,
                    )
                )


def total_completed_and_reread(
    session: Session, user_id: int
) -> tuple[int, int]:
    """Return ``(total_reads, reread_books)`` for a user.

    ``total_reads`` counts completed sessions; ``reread_books`` counts books with
    two or more completed sessions.
    """
    rows = session.exec(
        select(ReadingSession.book_id)
        .where(
            ReadingSession.user_id == user_id,
            ReadingSession.status == ReadingStatus.read,
        )
    ).all()
    per_book: dict[int, int] = {}
    for book_id in rows:
        per_book[book_id] = per_book.get(book_id, 0) + 1
    total = sum(per_book.values())
    reread = sum(1 for count in per_book.values() if count >= 2)
    return total, reread
