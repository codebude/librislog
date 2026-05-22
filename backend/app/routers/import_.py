"""External book search and import endpoints — search, stream, and persist candidates."""

import json
import logging
from typing import List, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.config import settings
from app.database import get_session
from app.models import Book, User
from app.schemas import BookImportCandidate, BookImportRequest, BookRead
from app.services import book_import
from app.services.cover_storage import download_cover
from app.services.tags import build_book_read, sync_book_tags

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["import"])


def _raise_integrity_conflict(exc: IntegrityError) -> None:
    """Convert ISBN unique-constraint violations to HTTP 409."""
    message = str(exc.orig).lower() if exc.orig else str(exc).lower()
    if "book.isbn" in message and "unique" in message:
        raise HTTPException(status_code=409, detail="This ISBN is already used by another book.") from exc
    raise


def _normalize_language(language: str | None) -> str | None:
    """Normalize a language code to uppercase ISO 639-1, raising HTTP 422 on invalid input."""
    if language is None:
        return None
    normalized = language.strip().upper()
    if not normalized:
        return None
    if len(normalized) != 2 or not normalized.isalpha():
        raise HTTPException(status_code=422, detail="Language must be a 2-letter ISO code (for example: EN, DE, FR).")
    return normalized


@router.get("/search", response_model=List[BookImportCandidate])
async def search_books(
    q: str = Query(min_length=1, description="Title string or ISBN"),
    type: Literal["title", "isbn"] = Query(default="title"),
    _user: User = Depends(require_user),
) -> List[BookImportCandidate]:
    """Search external APIs for books by title or ISBN."""
    logger.debug("Search request — q=%r type=%r", q, type)
    async with httpx.AsyncClient(timeout=10.0) as client:
        results = await book_import.search(
            q,
            type,
            api_key=settings.google_books_api_key,
            hardcover_api_token=settings.hardcover_app_api_token,
            http_client=client,
        )
    logger.debug("Search returning %d candidate(s) for %r", len(results), q)
    return results


@router.get("/search/stream")
async def search_books_stream(
    q: str = Query(min_length=1, description="Title string or ISBN"),
    type: Literal["title", "isbn"] = Query(default="title"),
    mode: Literal["auto", "google_only"] = Query(default="auto"),
    _user: User = Depends(require_user),
) -> StreamingResponse:
    """Stream import search progress as Server-Sent Events (text/event-stream).

    Yields progress events for each source (open_library, hardcover, google_books)
    and finally a ``complete`` event with the merged results.
    """
    logger.debug("Stream search request — q=%r type=%r", q, type)

    async def event_generator():
        async with httpx.AsyncClient(timeout=10.0) as client:
            async for event in book_import.search_with_progress(
                q,
                type,
                api_key=settings.google_books_api_key,
                hardcover_api_token=settings.hardcover_app_api_token,
                mode=mode,
                http_client=client,
            ):
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=BookRead, status_code=201)
async def import_book(
    body: BookImportRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> BookRead:
    """Persist an import candidate into the local database.

    Checks for duplicate ISBNs, downloads cover images, and syncs tags.
    """
    c = body.candidate

    # Reject duplicates by ISBN when an ISBN is present
    if c.isbn:
        existing = session.exec(
            select(Book).where(Book.isbn == c.isbn, Book.user_id == current_user.id)
        ).first()
        if existing:
            logger.warning("Duplicate ISBN rejected — isbn=%s existing_id=%s", c.isbn, existing.id)
            raise HTTPException(
                status_code=409,
                detail=f"A book with ISBN {c.isbn} already exists (id={existing.id}).",
            )

    # Attempt to download and cache the cover locally; fall back to external URL.
    cover_url = c.cover_url
    if cover_url:
        async with httpx.AsyncClient(timeout=15.0) as client:
            filename = await download_cover(cover_url, settings.covers_dir, client, current_user.id)
        if filename:
            cover_url = f"/api/covers/{filename}"
        else:
            logger.warning("Cover download failed or invalid for %s — skipping cover during import", cover_url)
            cover_url = None

    book = Book(
        title=c.title,
        subtitle=c.subtitle,
        author=c.author,
        isbn=c.isbn,
        cover_url=cover_url,
        publisher=c.publisher,
        published_year=c.published_year,
        page_count=c.page_count,
        language=_normalize_language(c.language),
        blurb=c.blurb,
        reading_status=body.reading_status,
        user_id=current_user.id,
    )
    session.add(book)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        _raise_integrity_conflict(exc)
    sync_book_tags(session, current_user.id, book.id or 0, c.tags)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        _raise_integrity_conflict(exc)
    session.refresh(book)
    logger.info("Imported book: %r (isbn=%s id=%s)", book.title, book.isbn, book.id)
    return build_book_read(session, book)
