import logging
from datetime import datetime, timezone
from typing import List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, or_, select

from app.auth import require_user
from app.config import settings
from app.database import get_session
from app.models import Book, BookTag, ReadingStatus, Tag, User
from app.schemas import (
    BookCreate,
    BookRead,
    BookUpdate,
    DashboardQuote,
    DateConflict,
    LibraryStats,
    StatusTransitionRequest,
    StatusTransitionResponse,
    TagCloudEntry,
)
from app.services.cover_storage import (
    delete_cover_file,
    download_cover,
    local_cover_filename,
)
from app.services.quote_cache import get_or_fetch_dashboard_quote
from app.services.tags import build_book_read, cleanup_orphan_tags, sync_book_tags

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["books"])

STATUS_DEFAULT_SORT_COLUMN = {
    ReadingStatus.want_to_read: Book.date_added,
    ReadingStatus.currently_reading: Book.date_started,
    ReadingStatus.read: Book.date_finished,
    ReadingStatus.did_not_finish: Book.date_started,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _apply_status_transition_dates(
    book: Book,
    target_status: ReadingStatus,
    update_data: dict,
) -> None:
    if target_status == book.reading_status:
        return

    if target_status == ReadingStatus.currently_reading and book.date_started is None:
        if update_data.get("date_started") is None:
            update_data["date_started"] = _utcnow()

    if target_status in (ReadingStatus.read, ReadingStatus.did_not_finish):
        if update_data.get("date_finished") is None:
            update_data["date_finished"] = _utcnow()


def _is_external_url(url: str | None) -> bool:
    """Return True if the URL is an external HTTP(S) URL (not a local /api/covers/ path)."""
    return bool(url and (url.startswith("http://") or url.startswith("https://")))


@router.get("", response_model=List[BookRead])
def list_books(
    status: Optional[ReadingStatus] = Query(default=None),
    q: Optional[str] = Query(default=None),
    sort: Literal["title", "date_added", "date_started", "date_finished", "rating"] = Query(
        default="date_added"
    ),
    order: Literal["asc", "desc"] = Query(default="desc"),
    smart_sort: bool = Query(default=True),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> List[BookRead]:
    logger.debug(
        "list_books — status=%r q=%r sort=%s order=%s smart_sort=%s",
        status,
        q,
        sort,
        order,
        smart_sort,
    )
    statement = select(Book).where(Book.user_id == current_user.id)

    if status is not None:
        statement = statement.where(Book.reading_status == status)

    if q:
        pattern = f"%{q}%"
        matching_tag_book_ids = select(BookTag.book_id).join(Tag, Tag.id == BookTag.tag_id).where(
            Tag.user_id == current_user.id,
            Tag.name.ilike(pattern),
        )
        statement = statement.where(
            or_(
                Book.title.ilike(pattern),  # type: ignore[union-attr]
                Book.author.ilike(pattern),
                Book.id.in_(matching_tag_book_ids),
            )
        )

    if smart_sort and status is not None:
        sort_col = STATUS_DEFAULT_SORT_COLUMN[status]
        sort_order = "desc"
    elif sort == "rating":
        sort_col = Book.rating
        sort_order = order
    elif sort == "date_started":
        sort_col = Book.date_started
        sort_order = order
    elif sort == "date_finished":
        sort_col = Book.date_finished
        sort_order = order
    elif sort == "title":
        sort_col = Book.title
        sort_order = order
    else:
        sort_col = Book.date_added
        sort_order = order

    sort_expression = sort_col.desc() if sort_order == "desc" else sort_col.asc()  # type: ignore[union-attr]
    if sort_col in (Book.date_started, Book.date_finished):
        sort_expression = sort_expression.nullslast()  # type: ignore[assignment]

    statement = statement.order_by(sort_expression)

    books = list(session.exec(statement).all())
    logger.debug("list_books — returning %d book(s)", len(books))
    return [build_book_read(session, book) for book in books]


@router.get("/stats", response_model=LibraryStats)
def get_library_stats(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> LibraryStats:
    total_books = session.exec(
        select(func.count()).select_from(Book).where(Book.user_id == current_user.id)
    ).one()
    books_read = session.exec(
        select(func.count()).select_from(Book).where(
            Book.user_id == current_user.id,
            Book.reading_status == ReadingStatus.read,
        )
    ).one()
    books_reading = session.exec(
        select(func.count()).select_from(Book).where(
            Book.user_id == current_user.id,
            Book.reading_status == ReadingStatus.currently_reading,
        )
    ).one()
    books_want_to_read = session.exec(
        select(func.count()).select_from(Book).where(
            Book.user_id == current_user.id,
            Book.reading_status == ReadingStatus.want_to_read,
        )
    ).one()
    books_did_not_finish = session.exec(
        select(func.count()).select_from(Book).where(
            Book.user_id == current_user.id,
            Book.reading_status == ReadingStatus.did_not_finish,
        )
    ).one()

    return LibraryStats(
        total_books=total_books,
        books_read=books_read,
        books_reading=books_reading,
        books_want_to_read=books_want_to_read,
        books_did_not_finish=books_did_not_finish,
    )


@router.get("/dashboard-quote", response_model=DashboardQuote | None)
async def get_dashboard_quote(
    current_user: User = Depends(require_user),
) -> DashboardQuote | None:
    if not settings.dashboard_quote_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard quote feature is disabled",
        )

    return await get_or_fetch_dashboard_quote()


@router.get("/tags/cloud", response_model=List[TagCloudEntry])
def get_tag_cloud(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> List[TagCloudEntry]:
    rows = session.exec(
        select(Tag.name, func.count(BookTag.book_id))
        .join(BookTag, BookTag.tag_id == Tag.id)
        .where(Tag.user_id == current_user.id)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count(BookTag.book_id).desc(), Tag.name.asc())
        .limit(limit)
    ).all()
    return [TagCloudEntry(tag=name, count=count) for name, count in rows]


@router.post("", response_model=BookRead, status_code=201)
async def create_book(
    book_in: BookCreate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> BookRead:
    logger.debug("create_book — title=%r", book_in.title)

    cover_url = book_in.cover_url
    if _is_external_url(cover_url):
        async with httpx.AsyncClient(timeout=15) as client:
            filename = await download_cover(cover_url, settings.covers_dir, client, current_user.id)  # type: ignore[arg-type]
        if filename:
            cover_url = f"/api/covers/{filename}"
            logger.debug("create_book — downloaded cover → %s", cover_url)
        else:
            logger.warning("Cover download failed or invalid for %s — skipping cover during creation", cover_url)
            cover_url = None

    book_data = book_in.model_dump()
    book_data["cover_url"] = cover_url
    book_data.pop("tags", None)
    book_data["user_id"] = current_user.id
    book = Book.model_validate(book_data)
    session.add(book)
    session.flush()
    sync_book_tags(session, current_user.id, book.id or 0, book_in.tags)
    session.commit()
    session.refresh(book)
    logger.info("Created book: %r (id=%s)", book.title, book.id)
    return build_book_read(session, book)


@router.get("/{book_id}", response_model=BookRead)
def get_book(
    book_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> BookRead:
    logger.debug("get_book — id=%s", book_id)
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        logger.debug("get_book — id=%s not found", book_id)
        raise HTTPException(status_code=404, detail="Book not found")
    return build_book_read(session, book)


@router.patch("/{book_id}", response_model=BookRead)
async def update_book(
    book_id: int,
    book_in: BookUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> BookRead:
    logger.debug("update_book — id=%s fields=%s", book_id, list(book_in.model_dump(exclude_unset=True)))
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        logger.debug("update_book — id=%s not found", book_id)
        raise HTTPException(status_code=404, detail="Book not found")

    update_data = book_in.model_dump(exclude_unset=True)
    tags_provided = "tags" in update_data
    tags_raw = update_data.pop("tags", None) if tags_provided else None
    target_status = update_data.get("reading_status", book.reading_status)

    # Download external cover URL → local file.
    if "cover_url" in update_data and _is_external_url(update_data["cover_url"]):
        async with httpx.AsyncClient(timeout=15) as client:
            filename = await download_cover(
                update_data["cover_url"], settings.covers_dir, client, current_user.id
            )
        if filename:
            update_data["cover_url"] = f"/api/covers/{filename}"
            logger.debug("update_book — downloaded cover → %s", update_data['cover_url'])
        else:
            logger.warning("Cover download failed or invalid for %s — skipping cover update", update_data["cover_url"])
            update_data.pop("cover_url", None)

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

    _apply_status_transition_dates(book, target_status, update_data)

    book.sqlmodel_update(update_data)
    session.add(book)
    if tags_provided:
        sync_book_tags(session, current_user.id, book.id, tags_raw)
        cleanup_orphan_tags(session, current_user.id)
    session.commit()
    session.refresh(book)
    logger.info("Updated book: %r (id=%s) — changed %s", book.title, book.id, list(update_data))
    return build_book_read(session, book)


@router.post("/{book_id}/transition-status", response_model=StatusTransitionResponse)
def transition_status(
    book_id: int,
    transition: StatusTransitionRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> StatusTransitionResponse:
    logger.debug(
        "transition_status — id=%s new_status=%s force_date_started=%r force_date_finished=%r",
        book_id,
        transition.new_status,
        transition.force_date_started,
        transition.force_date_finished,
    )
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Book not found")

    conflict: DateConflict | None = None
    update_data: dict = {"reading_status": transition.new_status}
    now = _utcnow()

    if (
        transition.new_status == ReadingStatus.currently_reading
        and transition.new_status != book.reading_status
        and book.date_started is not None
    ):
        if transition.force_date_started is None:
            conflict = DateConflict(
                field="date_started",
                existing_date=book.date_started,
                suggested_date=now,
            )
            return StatusTransitionResponse(book=build_book_read(session, book), date_conflict=conflict)
        update_data["date_started"] = transition.force_date_started

    if (
        transition.new_status in (ReadingStatus.read, ReadingStatus.did_not_finish)
        and transition.new_status != book.reading_status
        and book.date_finished is not None
    ):
        if transition.force_date_finished is None:
            conflict = DateConflict(
                field="date_finished",
                existing_date=book.date_finished,
                suggested_date=now,
            )
            return StatusTransitionResponse(book=build_book_read(session, book), date_conflict=conflict)
        update_data["date_finished"] = transition.force_date_finished

    _apply_status_transition_dates(book, transition.new_status, update_data)
    book.sqlmodel_update(update_data)
    session.add(book)
    session.commit()
    session.refresh(book)
    return StatusTransitionResponse(book=build_book_read(session, book), date_conflict=None)


@router.delete("/{book_id}", status_code=204)
def delete_book(
    book_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    logger.debug("delete_book — id=%s", book_id)
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        logger.debug("delete_book — id=%s not found", book_id)
        raise HTTPException(status_code=404, detail="Book not found")

    filename = local_cover_filename(book.cover_url)
    if filename:
        shared = session.exec(
            select(Book.id).where(Book.cover_url == f"/api/covers/{filename}", Book.id != book_id)
        ).first()
        if not shared:
            delete_cover_file(filename, settings.covers_dir)

    for link in session.exec(select(BookTag).where(BookTag.book_id == book.id)).all():
        session.delete(link)
    session.delete(book)
    cleanup_orphan_tags(session, current_user.id)
    session.commit()
    logger.info("Deleted book id=%s", book_id)
