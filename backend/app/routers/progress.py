import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Book, ReadingProgress, User
from app.schemas import ReadingProgressCreate, ReadingProgressLatest, ReadingProgressRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["progress"])


@router.post("/{book_id}/progress", response_model=ReadingProgressRead, status_code=201)
def create_progress_entry(
    book_id: int,
    data: ReadingProgressCreate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> ReadingProgressRead:
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.page_count is not None and data.page > book.page_count:
        raise HTTPException(
            status_code=422,
            detail=f"Page cannot exceed book page count ({book.page_count})",
        )

    entry = ReadingProgress(
        book_id=book_id,
        user_id=current_user.id,
        page=data.page,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    logger.debug("Created progress entry: book_id=%s page=%s", book_id, data.page)
    return ReadingProgressRead(
        id=entry.id,
        book_id=entry.book_id,
        page=entry.page,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("/{book_id}/progress", response_model=List[ReadingProgressRead])
def list_progress_entries(
    book_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> List[ReadingProgressRead]:
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Book not found")

    rows = session.exec(
        select(ReadingProgress)
        .where(
            ReadingProgress.book_id == book_id,
            ReadingProgress.user_id == current_user.id,
        )
        .order_by(ReadingProgress.created_at.desc())
    ).all()
    return [
        ReadingProgressRead(
            id=r.id,
            book_id=r.book_id,
            page=r.page,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.delete("/{book_id}/progress/{entry_id}", status_code=204)
def delete_progress_entry(
    book_id: int,
    entry_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
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
    ids = [int(i.strip()) for i in book_ids.split(",") if i.strip()]
    if not ids:
        return []

    subq = (
        select(
            ReadingProgress.book_id,
            ReadingProgress.page,
            func.row_number()
            .over(partition_by=ReadingProgress.book_id, order_by=ReadingProgress.created_at.desc())
            .label("rn"),
        )
        .where(
            ReadingProgress.book_id.in_(ids),
            ReadingProgress.user_id == current_user.id,
        )
        .subquery()
    )
    rows = session.exec(
        select(subq.c.book_id, subq.c.page).where(subq.c.rn == 1)
    ).all()
    return [ReadingProgressLatest(book_id=book_id, current_page=page) for book_id, page in rows]
