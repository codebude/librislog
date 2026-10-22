"""Reading progress CRUD endpoints and batch latest-progress query."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.auth import require_user
from app.database import get_session
from app.models import Book, ReadingProgress, ReadingSession, User
from app.schemas import ReadingProgressCreate, ReadingProgressLatest, ReadingProgressRead, ReadingProgressUpdate
from app.services.reading_sessions import active_session, sessions_for_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["progress"])


@router.post("/{book_id}/progress", response_model=ReadingProgressRead, status_code=201)
def create_progress_entry(
    book_id: int,
    data: ReadingProgressCreate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> ReadingProgressRead:
    """Record a reading progress entry (page reached) for a book.

    The page must not exceed the book's page_count (if set).
    """
    assert current_user.id is not None
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.page_count is not None and data.page > book.page_count:
        raise HTTPException(
            status_code=422,
            detail=f"Page cannot exceed book page count ({book.page_count})",
        )

    session_id = data.session_id
    if session_id is not None:
        # A caller-supplied session id must belong to this book and this user.
        supplied = session.get(ReadingSession, session_id)
        if (
            not supplied
            or supplied.book_id != book_id
            or supplied.user_id != current_user.id
        ):
            raise HTTPException(status_code=404, detail="Reading session not found")
    else:
        current = active_session(session, book_id)
        if current is not None:
            session_id = current.id
        else:
            sessions = sessions_for_book(session, book_id)
            if sessions:
                session_id = sessions[0].id

    entry = ReadingProgress(
        book_id=book_id,
        user_id=current_user.id,
        page=data.page,
        session_id=session_id,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    assert entry.id is not None
    logger.debug("Created progress entry: book_id=%s page=%s session_id=%s", book_id, data.page, session_id)
    return ReadingProgressRead(
        id=entry.id,
        book_id=entry.book_id,
        page=entry.page,
        session_id=entry.session_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("/{book_id}/progress", response_model=List[ReadingProgressRead])
def list_progress_entries(
    book_id: int,
    session_id: Optional[int] = Query(default=None),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> List[ReadingProgressRead]:
    """List progress entries for a book, newest first.

    When ``session_id`` is omitted, all entries are returned (matching the
    pre-session behaviour). Pass ``session_id`` to filter to a single session.
    """
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Book not found")

    statement = select(ReadingProgress).where(
        ReadingProgress.book_id == book_id,
        ReadingProgress.user_id == current_user.id,
    )
    if session_id is not None:
        statement = statement.where(ReadingProgress.session_id == session_id)
    rows = session.exec(
        statement.order_by(col(ReadingProgress.created_at).desc())
    ).all()
    return [
        ReadingProgressRead(
            id=r.id,  # ty: ignore[invalid-argument-type]
            book_id=r.book_id,
            page=r.page,
            session_id=r.session_id,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.patch("/{book_id}/progress/{entry_id}", response_model=ReadingProgressRead)
def update_progress_entry(
    book_id: int,
    entry_id: int,
    data: ReadingProgressUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> ReadingProgressRead:
    """Update the date of a single progress entry."""
    entry = session.get(ReadingProgress, entry_id)
    if not entry or entry.book_id != book_id or entry.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Progress entry not found")

    entry.created_at = data.created_at
    entry.updated_at = data.created_at
    session.commit()
    session.refresh(entry)
    logger.debug("Updated progress entry date: entry_id=%s", entry_id)
    return ReadingProgressRead(
        id=entry.id,  # ty: ignore[invalid-argument-type]
        book_id=entry.book_id,
        page=entry.page,
        session_id=entry.session_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.delete("/{book_id}/progress/{entry_id}", status_code=204)
def delete_progress_entry(
    book_id: int,
    entry_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    """Delete a single progress entry."""
    entry = session.get(ReadingProgress, entry_id)
    if not entry or entry.book_id != book_id or entry.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Progress entry not found")

    session.delete(entry)
    session.commit()
    logger.debug("Deleted progress entry: book_id=%s entry_id=%s", book_id, entry_id)


@router.get("/progress/latest", response_model=List[ReadingProgressLatest])
def get_latest_progress_batch(
    book_ids: str,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> List[ReadingProgressLatest]:
    """Return the latest progress page for each book in a comma-separated list of IDs.

    Session-aware: for a book with a current (open) session, the latest page of
    *that* session is returned, so a re-read correctly shows 0 % while the
    previous session's entries stay separate. Books without a current session
    fall back to the latest page across all entries (legacy behaviour).

    Implemented with a SQL window function so only the latest entry per
    ``(book, session)`` is materialized; the per-book selection of the current
    session (or the overall latest) happens in Python over that small result set.
    """
    ids = [int(i.strip()) for i in book_ids.split(",") if i.strip()]
    if not ids:
        return []

    current_sessions = {
        s.book_id: s.id
        for s in session.exec(
            select(ReadingSession).where(
                col(ReadingSession.book_id).in_(ids),
                ReadingSession.is_current.is_(True),
            )
        ).all()
    }

    # Latest entry per (book_id, session_id), computed in SQL.
    rn = func.row_number().over(
        partition_by=[col(ReadingProgress.book_id), col(ReadingProgress.session_id)],
        order_by=col(ReadingProgress.created_at).desc(),
    )
    subq = (
        select(
            ReadingProgress.book_id.label("book_id"),
            ReadingProgress.session_id.label("session_id"),
            ReadingProgress.page.label("page"),
            ReadingProgress.created_at.label("created_at"),
            rn.label("rn"),
        )
        .where(
            col(ReadingProgress.book_id).in_(ids),
            ReadingProgress.user_id == current_user.id,
        )
        .subquery()
    )
    latest_per_session = list(
        session.exec(
            select(subq.c.book_id, subq.c.session_id, subq.c.page, subq.c.created_at).where(
                subq.c.rn == 1
            )
        ).all()
    )

    # For each book, prefer the current session's latest entry; otherwise the
    # latest entry across all sessions of the book.
    best_by_book: dict[int, tuple[datetime, int]] = {}
    for row in latest_per_session:
        book_id = row[0]
        sid = row[1]
        page = row[2]
        created_at = row[3]
        current_sid = current_sessions.get(book_id)
        if current_sid is not None:
            if sid == current_sid:
                best_by_book[book_id] = (created_at, page)
        else:
            prev = best_by_book.get(book_id)
            if prev is None or created_at > prev[0]:
                best_by_book[book_id] = (created_at, page)

    return [
        ReadingProgressLatest(book_id=book_id, current_page=page)
        for book_id, (_created_at, page) in best_by_book.items()
    ]
