"""Reading session CRUD, re-read, and timeline endpoints."""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.auth import require_user
from app.database import get_session
from app.models import Book, ReadingProgress, ReadingSession, ReadingStatus, User
from app.routers.books import _validate_dates
from app.schemas import (
    BookRead,
    ReadAgainRequest,
    ReadingSessionCreate,
    ReadingSessionRead,
    ReadingSessionUpdate,
    SessionMutationResponse,
    TimelineSessionEntry,
)
from app.services.authors import join_authors, load_authors_batch
from app.services.reading_sessions import (
    assign_read_numbers,
    build_session_read,
    progress_aggregates,
    recompute_book_mirror,
    sessions_for_book,
    start_read_again,
)
from app.services.tags import build_book_read
from app.time_utils import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["sessions"])


def _get_owned_book(session: Session, book_id: int, user_id: int) -> Book:
    book = session.get(Book, book_id)
    if not book or book.user_id != user_id:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


def _get_owned_session(
    session: Session, book_id: int, session_id: int, user_id: int
) -> ReadingSession:
    reading_session = session.get(ReadingSession, session_id)
    if (
        not reading_session
        or reading_session.book_id != book_id
        or reading_session.user_id != user_id
    ):
        raise HTTPException(status_code=404, detail="Reading session not found")
    return reading_session


def _to_session_reads(
    session: Session, sessions: list[ReadingSession]
) -> list[ReadingSessionRead]:
    if not sessions:
        return []
    read_numbers = assign_read_numbers(sessions)
    aggs = progress_aggregates(session, sessions[0].book_id)
    return [
        build_session_read(session, s, read_numbers.get(s.id), aggs.get(s.id or 0))
        for s in sessions
    ]


@router.get("", response_model=List[TimelineSessionEntry])
def list_completed_sessions(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> List[TimelineSessionEntry]:
    """Return every completed read (session) across the user's books, newest first."""
    rows = session.exec(
        select(ReadingSession, Book)
        .join(Book, col(Book.id) == col(ReadingSession.book_id))
        .where(
            ReadingSession.user_id == current_user.id,
            ReadingSession.status == ReadingStatus.read,
            col(ReadingSession.date_finished).is_not(None),
        )
        .order_by(col(ReadingSession.date_finished).desc())
    ).all()

    per_book: dict[int, list[ReadingSession]] = {}
    for rs, _book in rows:
        per_book.setdefault(rs.book_id, []).append(rs)
    authors_map = load_authors_batch(session, list(per_book))

    result: list[TimelineSessionEntry] = []
    for rs, book in rows:
        read_number = assign_read_numbers(per_book[rs.book_id]).get(rs.id)
        authors = authors_map.get(book.id, [])
        result.append(
            TimelineSessionEntry(
                session_id=rs.id or 0,
                book_id=book.id or 0,
                title=book.title,
                author=join_authors(authors),
                authors=authors,
                cover_url=book.cover_url,
                rating=book.rating,
                page_count=book.page_count,
                date_finished=rs.date_finished,
                read_number=read_number,
                is_reread=read_number is not None and read_number >= 2,
            )
        )
    return result


@router.get("/{book_id}/sessions", response_model=List[ReadingSessionRead])
def list_sessions(
    book_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> List[ReadingSessionRead]:
    """List a book's reading sessions, newest first."""
    _get_owned_book(session, book_id, current_user.id)
    return _to_session_reads(session, sessions_for_book(session, book_id))


@router.post("/{book_id}/sessions", response_model=SessionMutationResponse, status_code=201)
def create_session(
    book_id: int,
    data: ReadingSessionCreate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> SessionMutationResponse:
    """Add a historical (past) reading session.

    Past reads are pure history: they never become current and never change the
    book's status or dates.
    """
    book = _get_owned_book(session, book_id, current_user.id)
    if data.status == ReadingStatus.want_to_read:
        raise HTTPException(status_code=422, detail="A session cannot be 'want_to_read'.")
    if data.status == ReadingStatus.currently_reading:
        raise HTTPException(
            status_code=422,
            detail="Use the 'Read again' action to start a current session.",
        )
    if data.status == ReadingStatus.read and data.date_finished is None:
        raise HTTPException(
            status_code=422, detail="A completed session must have a finish date."
        )
    _validate_dates({"date_started": data.date_started, "date_finished": data.date_finished})

    reading_session = ReadingSession(
        book_id=book.id,
        user_id=current_user.id,
        status=data.status,
        date_started=data.date_started,
        date_finished=data.date_finished,
        is_current=False,
    )
    session.add(reading_session)
    session.commit()
    session.refresh(reading_session)

    sessions = sessions_for_book(session, book_id)
    return SessionMutationResponse(
        session=build_session_read(
            session,
            reading_session,
            assign_read_numbers(sessions).get(reading_session.id),
        ),
        book=build_book_read(session, book),
    )


@router.patch("/{book_id}/sessions/{session_id}", response_model=SessionMutationResponse)
def update_session(
    book_id: int,
    session_id: int,
    data: ReadingSessionUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> SessionMutationResponse:
    """Edit a session's dates or status; re-mirrors the book if it is the current one."""
    book = _get_owned_book(session, book_id, current_user.id)
    reading_session = _get_owned_session(session, book_id, session_id, current_user.id)

    update = data.model_dump(exclude_unset=True)
    if "status" in update and update["status"] == ReadingStatus.want_to_read:
        raise HTTPException(status_code=422, detail="A session cannot be 'want_to_read'.")
    _validate_dates(
        {
            "date_started": update.get("date_started", reading_session.date_started),
            "date_finished": update.get("date_finished", reading_session.date_finished),
        }
    )

    for field, value in update.items():
        setattr(reading_session, field, value)

    if reading_session.status == ReadingStatus.read and reading_session.date_finished is None:
        raise HTTPException(
            status_code=422, detail="A completed session must have a finish date."
        )

    was_current = reading_session.is_current
    if was_current and reading_session.status != ReadingStatus.currently_reading:
        reading_session.is_current = False
        if reading_session.date_finished is None:
            reading_session.date_finished = utcnow()

    session.add(reading_session)
    session.commit()
    session.refresh(reading_session)

    if was_current:
        book.reading_status = reading_session.status
        recompute_book_mirror(book, sessions_for_book(session, book_id))
        session.add(book)
        session.commit()
        session.refresh(book)

    sessions = sessions_for_book(session, book_id)
    return SessionMutationResponse(
        session=build_session_read(
            session,
            reading_session,
            assign_read_numbers(sessions).get(session_id),
        ),
        book=build_book_read(session, book),
    )


@router.delete("/{book_id}/sessions/{session_id}", response_model=BookRead)
def delete_session(
    book_id: int,
    session_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> BookRead:
    """Delete a session and its progress entries, then re-mirror the book."""
    book = _get_owned_book(session, book_id, current_user.id)
    reading_session = _get_owned_session(session, book_id, session_id, current_user.id)
    was_current = reading_session.is_current

    for entry in session.exec(
        select(ReadingProgress).where(ReadingProgress.session_id == session_id)
    ).all():
        session.delete(entry)

    session.delete(reading_session)
    session.commit()

    remaining = sessions_for_book(session, book_id)
    if not remaining:
        book.reading_status = ReadingStatus.want_to_read
        book.date_started = None
        book.date_finished = None
        session.add(book)
        session.commit()
    elif was_current:
        promoted = remaining[0]
        promoted.is_current = True
        session.add(promoted)
        book.reading_status = promoted.status
        recompute_book_mirror(book, remaining)
        session.add(book)
        session.commit()

    return build_book_read(session, book)


@router.post("/{book_id}/read-again", response_model=SessionMutationResponse)
def read_again(
    book_id: int,
    data: ReadAgainRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> SessionMutationResponse:
    """Start a re-read: keep earlier sessions and open a new current session."""
    book = _get_owned_book(session, book_id, current_user.id)
    if book.reading_status not in (ReadingStatus.read, ReadingStatus.did_not_finish):
        raise HTTPException(
            status_code=422, detail="Only finished books can be read again."
        )

    if data.date_started is not None:
        _validate_dates({"date_started": data.date_started, "date_finished": None})

    new_session = start_read_again(session, book, data.date_started)
    session.commit()
    session.refresh(book)
    session.refresh(new_session)

    sessions = sessions_for_book(session, book_id)
    return SessionMutationResponse(
        session=build_session_read(
            session,
            new_session,
            assign_read_numbers(sessions).get(new_session.id),
        ),
        book=build_book_read(session, book),
    )
