"""Book CRUD, status transitions, suggestions, tag cloud, and dashboard quote endpoints."""

import logging
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, or_, select

from app.auth import require_user
from app.config import settings
from app.database import get_session
from app.models import Book, BookTag, ReadingProgress, ReadingStatus, Tag, User
from app.schemas import (
    BookCreate,
    BookListResponse,
    BookRead,
    BookUpdate,
    DashboardQuote,
    DateConflict,
    LibraryStats,
    StatusTransitionRequest,
    StatusTransitionResponse,
    SuggestionList,
    TagCloudEntry,
)
from app.services.cover_storage import (
    delete_cover_file,
    local_cover_filename,
)
from app.services.cover_import import import_cover_from_url, is_external_cover_url
from app.services.quote_cache import get_or_fetch_dashboard_quote
from app.services.tags import build_book_read, cleanup_orphan_tags, load_tags_batch, sync_book_tags
from app.time_utils import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["books"])

STATUS_DEFAULT_SORT_COLUMN: dict[ReadingStatus, object] = {
    ReadingStatus.want_to_read: Book.date_added,
    ReadingStatus.currently_reading: Book.date_started,
    ReadingStatus.read: Book.date_finished,
    ReadingStatus.did_not_finish: Book.date_started,
}


def _utcnow() -> datetime:
    """Return current UTC datetime (wrapper for testability)."""
    return utcnow()


def _apply_status_transition_dates(
    book: Book,
    target_status: ReadingStatus,
    update_data: dict,
    skip_auto_date_started: bool = False,
) -> None:
    """Auto-fill date_started / date_finished when transitioning to a new status."""
    if target_status == book.reading_status:
        return

    if target_status == ReadingStatus.currently_reading:
        if skip_auto_date_started:
            update_data.setdefault("date_started", None)
        elif book.date_started is None and update_data.get("date_started") is None:
            update_data["date_started"] = _utcnow()

    if target_status in (ReadingStatus.read, ReadingStatus.did_not_finish):
        if update_data.get("date_finished") is None:
            update_data["date_finished"] = _utcnow()


def _validate_dates(data: dict) -> None:
    """Validate that date fields are not in the future and are logically ordered."""
    now = _utcnow()
    for field in ("date_started", "date_finished"):
        val = data.get(field)
        if val is not None:
            if val.tzinfo is None:
                val = val.replace(tzinfo=timezone.utc)
            if val > now:
                raise HTTPException(status_code=422, detail="Date cannot be in the future.")
    ds = data.get("date_started")
    df = data.get("date_finished")
    if ds is not None and df is not None and ds.tzinfo is None:
        ds = ds.replace(tzinfo=timezone.utc)
    if df is not None and df.tzinfo is None:
        df = df.replace(tzinfo=timezone.utc)
    if ds is not None and df is not None and ds > df:
        raise HTTPException(status_code=422, detail="Start date cannot be after finish date.")


def _validate_date_finished_for_read(
    book: Book,
    update_data: dict,
    target_status: ReadingStatus,
) -> None:
    """Ensure date_finished is not explicitly cleared while the book is read."""
    if "date_finished" not in update_data:
        return
    if update_data["date_finished"] is not None:
        return
    if book.date_finished is None:
        return
    if book.reading_status == ReadingStatus.read and target_status == ReadingStatus.read:
        raise HTTPException(status_code=422, detail="A finished book must have an end date. Change the status if you want to remove the finish date.")


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


def _raise_integrity_conflict(exc: IntegrityError) -> None:
    """Convert ISBN unique-constraint violations to HTTP 409."""
    message = str(exc.orig).lower() if exc.orig else str(exc).lower()
    if ("book.isbn" in message or "uq_book_user_id_isbn" in message) and "unique" in message:
        raise HTTPException(status_code=409, detail="This ISBN is already used by another book.") from exc
    raise


def _build_book_read_with_tags(book: Book, tags_text: str | None) -> BookRead:
    """Build a BookRead from a Book model with a pre-resolved tags string."""
    payload = book.model_dump()
    payload.pop("user_id", None)
    payload["tags"] = tags_text
    return BookRead.model_validate(payload)


@router.get("", response_model=BookListResponse)
def list_books(
    status: Optional[ReadingStatus] = Query(default=None),
    q: Optional[str] = Query(default=None),
    has_cover: Optional[bool] = Query(default=None),
    sort: Literal["title", "date_added", "date_started", "date_finished", "rating"] = Query(
        default="date_added"
    ),
    order: Literal["asc", "desc"] = Query(default="desc"),
    smart_sort: bool = Query(default=True),
    offset: int = Query(default=0, ge=0),
    limit: Optional[int] = Query(default=None, ge=1, le=200),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> BookListResponse:
    """List books for the authenticated user with filtering, sorting, and pagination.

    ``smart_sort`` overrides *sort*/*order* when a status filter is active:
    want_to_read → date_added, currently_reading → date_started,
    read → date_finished, did_not_finish → date_started (all descending).
    """
    logger.debug(
        "list_books — status=%r q=%r sort=%s order=%s smart_sort=%s",
        status, q, sort, order, smart_sort,
    )
    base_statement = select(Book).where(Book.user_id == current_user.id)

    if status is not None:
        base_statement = base_statement.where(Book.reading_status == status)

    if q:
        pattern = f"%{q}%"
        matching_tag_book_ids = select(BookTag.book_id).join(Tag, Tag.id == BookTag.tag_id).where(
            Tag.user_id == current_user.id,
            Tag.name.ilike(pattern),
        )
        base_statement = base_statement.where(
            or_(
                Book.title.ilike(pattern),
                Book.subtitle.ilike(pattern),
                Book.author.ilike(pattern),
                Book.blurb.ilike(pattern),
                Book.id.in_(matching_tag_book_ids),
            )
        )

    if has_cover is not None:
        if has_cover:
            base_statement = base_statement.where(Book.cover_url.is_not(None), Book.cover_url != "")
        else:
            base_statement = base_statement.where(
                sa.or_(Book.cover_url.is_(None), Book.cover_url == "")
            )

    total = session.exec(
        select(func.count()).select_from(base_statement.subquery())
    ).one()

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

    sort_expression = sort_col.desc() if sort_order == "desc" else sort_col.asc()
    if sort_col in (Book.date_started, Book.date_finished):
        sort_expression = sort_expression.nullslast()

    statement = base_statement.order_by(sort_expression).offset(offset)
    if limit is not None:
        statement = statement.limit(limit)

    books = list(session.exec(statement).all())
    logger.debug("list_books — returning %d/%d book(s)", len(books), total)
    book_ids = [b.id for b in books if b.id is not None]
    book_tags_map = load_tags_batch(session, book_ids) if book_ids else {}
    return BookListResponse(
        books=[
            _build_book_read_with_tags(book, book_tags_map.get(book.id))
            for book in books
        ],
        total=total,
    )


@router.get("/stats", response_model=LibraryStats)
def get_library_stats(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> LibraryStats:
    """Return aggregate library statistics for the authenticated user."""
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
    """Return the cached dashboard quote or fetch a fresh one.

    Raises HTTP 503 if the feature is disabled.
    """
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
    """Return tags sorted by usage count (descending) for the authenticated user."""
    count_label = func.count(BookTag.book_id).label("cnt")
    rows = session.exec(
        select(Tag.name, count_label)
        .join(BookTag, BookTag.tag_id == Tag.id)
        .where(Tag.user_id == current_user.id)
        .group_by(Tag.id)
        .order_by(count_label.desc(), Tag.name.asc())
        .limit(limit)
    ).all()
    return [TagCloudEntry(tag=name, count=count) for name, count in rows]


def _suggest_field(
    session: Session,
    user_id: int,
    column: str,
    q: str,
    limit: int,
) -> list[str]:
    """Return distinct values for a Book column matching the query."""
    if not q.strip():
        return []
    pattern = f"%{q}%"
    col = getattr(Book, column)
    rows = session.exec(
        select(col)
        .where(
            Book.user_id == user_id,
            col.isnot(None),
            col.ilike(pattern),
        )
        .distinct()
        .order_by(col)
        .limit(limit)
    ).all()
    return list(rows)


@router.get("/suggestions/authors", response_model=SuggestionList)
def suggest_authors(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> SuggestionList:
    """Autocomplete author names from the user's existing books."""
    suggestions = _suggest_field(session, current_user.id, "author", q, limit)
    return SuggestionList(suggestions=suggestions)


@router.get("/suggestions/publishers", response_model=SuggestionList)
def suggest_publishers(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> SuggestionList:
    """Autocomplete publisher names from the user's existing books."""
    suggestions = _suggest_field(session, current_user.id, "publisher", q, limit)
    return SuggestionList(suggestions=suggestions)


@router.get("/suggestions/tags", response_model=SuggestionList)
def suggest_tags(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> SuggestionList:
    """Autocomplete tag names from the user's existing tags."""
    if not q.strip():
        return SuggestionList(suggestions=[])
    pattern = f"%{q}%"
    rows = session.exec(
        select(Tag.name)
        .where(
            Tag.user_id == current_user.id,
            Tag.name.ilike(pattern),
        )
        .distinct()
        .order_by(Tag.name)
        .limit(limit)
    ).all()
    return SuggestionList(suggestions=list(rows))


@router.post("", response_model=BookRead, status_code=201)
async def create_book(
    book_in: BookCreate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> BookRead:
    """Create a new book, downloading the cover if an external URL is provided."""
    logger.debug("create_book — title=%r", book_in.title)

    cover_url = book_in.cover_url
    if is_external_cover_url(cover_url):
        filename = await import_cover_from_url(
            cover_url,
            settings.covers_dir,
            current_user.id,
            settings.cover_import_timeout_seconds,
        )
        if filename:
            cover_url = f"/api/covers/{filename}"
            logger.debug("create_book — downloaded cover → %s", cover_url)
        else:
            logger.warning("Cover download failed or invalid for %s — skipping cover during creation", cover_url)
            cover_url = None

    book_data = book_in.model_dump()
    book_data["language"] = _normalize_language(book_data.get("language"))
    book_data["cover_url"] = cover_url
    book_data.pop("tags", None)
    book_data["user_id"] = current_user.id
    _validate_dates(book_data)
    book = Book.model_validate(book_data)
    session.add(book)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        _raise_integrity_conflict(exc)
    sync_book_tags(session, current_user.id, book.id or 0, book_in.tags)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        _raise_integrity_conflict(exc)
    session.refresh(book)
    logger.info("Created book: %r (id=%s)", book.title, book.id)
    return build_book_read(session, book)


@router.get("/{book_id}", response_model=BookRead)
def get_book(
    book_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> BookRead:
    """Return a single book by ID (scoped to the authenticated user)."""
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
    """Partially update a book, handling cover download and tag sync."""
    logger.debug("update_book — id=%s fields=%s", book_id, list(book_in.model_dump(exclude_unset=True)))
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        logger.debug("update_book — id=%s not found", book_id)
        raise HTTPException(status_code=404, detail="Book not found")

    update_data = book_in.model_dump(exclude_unset=True)
    if "language" in update_data:
        update_data["language"] = _normalize_language(update_data.get("language"))
    tags_provided = "tags" in update_data
    tags_raw = update_data.pop("tags", None) if tags_provided else None
    target_status = update_data.get("reading_status", book.reading_status)

    # Download external cover URL -> local file.
    if "cover_url" in update_data and is_external_cover_url(update_data["cover_url"]):
        filename = await import_cover_from_url(
            update_data["cover_url"],
            settings.covers_dir,
            current_user.id,
            settings.cover_import_timeout_seconds,
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
    _validate_dates(update_data)
    _validate_date_finished_for_read(book, update_data, target_status)

    book.sqlmodel_update(update_data)
    session.add(book)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        _raise_integrity_conflict(exc)
    if tags_provided:
        sync_book_tags(session, current_user.id, book.id, tags_raw)
        cleanup_orphan_tags(session, current_user.id)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        _raise_integrity_conflict(exc)
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
    """Change a book's reading status with date-conflict detection and resolution."""
    logger.debug(
        "transition_status — id=%s new_status=%s force_date_started=%r force_date_finished=%r",
        book_id, transition.new_status, transition.force_date_started, transition.force_date_finished,
    )
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Book not found")

    conflict: DateConflict | None = None
    update_data: dict = {"reading_status": transition.new_status}
    now = _utcnow()

    # date_finished handling is split into two passes:
    #   1. Inline below — conflict detection when moving TO read/did_not_finish
    #      and force_date_finished override.
    #   2. _apply_status_transition_dates — default-fills date_finished when
    #      the target status is read/did_not_finish and it's still None.
    # This is intentional: the conflict dialog interrupts before mutation,
    # while default-fill runs during the actual update.
    if (
        transition.new_status == ReadingStatus.currently_reading
        and transition.new_status != book.reading_status
        and book.date_started is not None
        and not transition.skip_auto_date_started
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
            book.date_finished is not None
            and transition.force_date_started > book.date_finished
        ):
            conflict = DateConflict(
                field="started_after_finished",
                existing_date=book.date_finished,
                suggested_date=now,
            )
            return StatusTransitionResponse(book=build_book_read(session, book), date_conflict=conflict)

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

    if (
        transition.new_status == ReadingStatus.currently_reading
        and transition.new_status != book.reading_status
        and book.date_started is None
        and book.date_finished is not None
        and transition.force_date_started is None
        and not transition.skip_auto_date_started
    ):
        conflict = DateConflict(
            field="started_after_finished",
            existing_date=book.date_finished,
            suggested_date=now,
        )
        return StatusTransitionResponse(book=build_book_read(session, book), date_conflict=conflict)

    if (
        transition.force_date_started is not None
        and transition.new_status == ReadingStatus.currently_reading
        and transition.new_status != book.reading_status
        and book.date_finished is not None
        and transition.force_date_started > book.date_finished
    ):
        update_data["date_started"] = transition.force_date_started
        update_data["date_finished"] = None

    if (
        transition.clear_date_started
        and transition.new_status == ReadingStatus.currently_reading
        and transition.new_status != book.reading_status
    ):
        update_data["date_started"] = None

    if (
        transition.clear_date_finished
        and transition.new_status != book.reading_status
        and transition.new_status != ReadingStatus.read
    ):
        update_data["date_finished"] = None

    # Apply user-provided date overrides outside conflict paths.
    if transition.force_date_started is not None:
        update_data["date_started"] = transition.force_date_started
    if transition.force_date_finished is not None:
        update_data["date_finished"] = transition.force_date_finished

    _apply_status_transition_dates(book, transition.new_status, update_data, transition.skip_auto_date_started)
    _validate_dates(update_data)
    _validate_date_finished_for_read(book, update_data, transition.new_status)
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
    """Delete a book, its tags, progress entries, and orphaned cover files."""
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
    for entry in session.exec(
        select(ReadingProgress).where(ReadingProgress.book_id == book.id)
    ).all():
        session.delete(entry)
    session.delete(book)
    cleanup_orphan_tags(session, current_user.id)
    session.commit()
    logger.info("Deleted book id=%s", book_id)
