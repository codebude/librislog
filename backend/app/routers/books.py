import logging
from typing import List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.models import Book, ReadingStatus
from app.schemas import BookCreate, BookRead, BookUpdate
from app.services.cover_storage import (
    delete_cover_file,
    download_cover,
    local_cover_filename,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["books"])


def _is_external_url(url: str | None) -> bool:
    """Return True if the URL is an external HTTP(S) URL (not a local /api/covers/ path)."""
    return bool(url and (url.startswith("http://") or url.startswith("https://")))


@router.get("", response_model=List[BookRead])
def list_books(
    status: Optional[ReadingStatus] = Query(default=None),
    q: Optional[str] = Query(default=None),
    sort: Literal["date_added", "rating"] = Query(default="date_added"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    session: Session = Depends(get_session),
) -> List[Book]:
    logger.debug("list_books — status=%r q=%r sort=%s order=%s", status, q, sort, order)
    statement = select(Book)

    if status is not None:
        statement = statement.where(Book.reading_status == status)

    if q:
        pattern = f"%{q}%"
        statement = statement.where(
            Book.title.ilike(pattern) | Book.author.ilike(pattern)  # type: ignore[union-attr]
        )

    sort_col = Book.date_added if sort == "date_added" else Book.rating
    if order == "desc":
        statement = statement.order_by(sort_col.desc())  # type: ignore[union-attr]
    else:
        statement = statement.order_by(sort_col.asc())  # type: ignore[union-attr]

    books = list(session.exec(statement).all())
    logger.debug("list_books — returning %d book(s)", len(books))
    return books


@router.post("", response_model=BookRead, status_code=201)
async def create_book(book_in: BookCreate, session: Session = Depends(get_session)) -> Book:
    logger.debug("create_book — title=%r", book_in.title)

    cover_url = book_in.cover_url
    if _is_external_url(cover_url):
        async with httpx.AsyncClient(timeout=15) as client:
            filename = await download_cover(cover_url, settings.covers_dir, client)  # type: ignore[arg-type]
        if filename:
            cover_url = f"/api/covers/{filename}"
            logger.debug("create_book — downloaded cover → %s", cover_url)

    book_data = book_in.model_dump()
    book_data["cover_url"] = cover_url
    book = Book.model_validate(book_data)
    session.add(book)
    session.commit()
    session.refresh(book)
    logger.info("Created book: %r (id=%s)", book.title, book.id)
    return book


@router.get("/{book_id}", response_model=BookRead)
def get_book(book_id: int, session: Session = Depends(get_session)) -> Book:
    logger.debug("get_book — id=%s", book_id)
    book = session.get(Book, book_id)
    if not book:
        logger.debug("get_book — id=%s not found", book_id)
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.patch("/{book_id}", response_model=BookRead)
async def update_book(
    book_id: int, book_in: BookUpdate, session: Session = Depends(get_session)
) -> Book:
    logger.debug("update_book — id=%s fields=%s", book_id, list(book_in.model_dump(exclude_unset=True)))
    book = session.get(Book, book_id)
    if not book:
        logger.debug("update_book — id=%s not found", book_id)
        raise HTTPException(status_code=404, detail="Book not found")

    update_data = book_in.model_dump(exclude_unset=True)

    # Download external cover URL → local file.
    if "cover_url" in update_data and _is_external_url(update_data["cover_url"]):
        async with httpx.AsyncClient(timeout=15) as client:
            filename = await download_cover(update_data["cover_url"], settings.covers_dir, client)
        if filename:
            update_data["cover_url"] = f"/api/covers/{filename}"
            logger.debug("update_book — downloaded cover → %s", update_data['cover_url'])

    # Clean up old local cover if it has changed.
    if "cover_url" in update_data and update_data["cover_url"] != book.cover_url:
        old_filename = local_cover_filename(book.cover_url)
        if old_filename:
            shared = session.exec(
                select(Book.id).where(
                    Book.cover_url == book.cover_url,
                    Book.id != book_id,
                )
            ).first()
            if not shared:
                delete_cover_file(old_filename, settings.covers_dir)

    book.sqlmodel_update(update_data)
    session.add(book)
    session.commit()
    session.refresh(book)
    logger.info("Updated book: %r (id=%s) — changed %s", book.title, book.id, list(update_data))
    return book


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int, session: Session = Depends(get_session)) -> None:
    logger.debug("delete_book — id=%s", book_id)
    book = session.get(Book, book_id)
    if not book:
        logger.debug("delete_book — id=%s not found", book_id)
        raise HTTPException(status_code=404, detail="Book not found")

    filename = local_cover_filename(book.cover_url)
    if filename:
        shared = session.exec(
            select(Book.id).where(Book.cover_url == f"/api/covers/{filename}", Book.id != book_id)
        ).first()
        if not shared:
            delete_cover_file(filename, settings.covers_dir)

    session.delete(book)
    session.commit()
    logger.info("Deleted book id=%s", book_id)
