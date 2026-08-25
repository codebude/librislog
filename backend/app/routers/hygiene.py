"""Data hygiene endpoints — find books with missing attributes and batch-update them."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlmodel import Session, col, func, select, update as sqlmodel_update

from app.auth import require_user
from app.config import settings
from app.database import get_session
from app.models import Book, BookAuthor, User
from app.schemas import (
    HygieneAttribute,
    HygieneBatchUpdateRequest,
    HygieneBatchUpdateResponse,
    HygieneMissingBook,
    HygieneMissingResponse,
)
from app.services.authors import cleanup_orphan_authors, join_authors, load_authors_batch, sync_book_authors
from app.services.cover_import import import_cover_from_url, is_external_cover_url
from app.services.tags import load_tags_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hygiene", tags=["hygiene"])

_MAX_BATCH_SIZE = 500


def _missing_condition(attr: HygieneAttribute):
    """Return a SQLAlchemy filter condition for a given attribute being missing."""
    if attr == HygieneAttribute.author:
        return ~col(Book.id).in_(
            select(BookAuthor.book_id).where(BookAuthor.book_id == col(Book.id))
        )
    col_expr = getattr(Book, attr.value)
    if attr == HygieneAttribute.page_count:
        return or_(col_expr == 0, col_expr.is_(None))
    return col_expr.is_(None)


def _compute_missing_attributes(book: Book, author_names: list[str]) -> list[HygieneAttribute]:
    """Return the list of hygiene attributes that are missing for a given book."""
    missing: list[HygieneAttribute] = []
    for attr in HygieneAttribute:
        if attr == HygieneAttribute.author:
            if not author_names:
                missing.append(attr)
            continue
        val = getattr(book, attr.value)
        is_missing = val is None or val == "" or val == 0
        if is_missing:
            missing.append(attr)
    return missing


@router.get("/missing", response_model=HygieneMissingResponse)
def list_missing(
    attributes: str = Query(default="", description="Comma-separated list of HygieneAttribute values"),
    match: Literal["any", "all"] = Query(default="all"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> HygieneMissingResponse:
    """List books with missing attributes for the current user."""
    requested: list[HygieneAttribute] = []
    if attributes.strip():
        for part in attributes.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                requested.append(HygieneAttribute(part))
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Unknown attribute: {part}")
    else:
        requested = list(HygieneAttribute)

    if not requested:
        raise HTTPException(status_code=422, detail="At least one attribute is required")

    # When ALL attributes are selected (no explicit filter), always use OR logic.
    # When specific attributes are requested, respect the match parameter.
    all_attrs_selected = set(requested) == set(HygieneAttribute)
    effective_match = "any" if all_attrs_selected else match

    conditions = [_missing_condition(attr) for attr in requested]

    if effective_match == "all":
        filter_ = conditions[0]
        for c in conditions[1:]:
            filter_ = and_(filter_, c)
    else:
        filter_ = conditions[0]
        for c in conditions[1:]:
            filter_ = or_(filter_, c)

    base = select(Book).where(Book.user_id == current_user.id).where(filter_)

    total = session.exec(
        select(func.count()).select_from(base.subquery())
    ).one()

    books = session.exec(
        base.order_by(Book.title).offset(offset).limit(limit)
    ).all()

    hygiene_books = []
    book_ids = [book.id for book in books if book.id is not None]
    tags_map = load_tags_batch(session, book_ids)
    authors_map = load_authors_batch(session, book_ids)
    for book in books:
        assert book.id is not None
        author_names = authors_map.get(book.id, [])
        missing_attrs = _compute_missing_attributes(book, author_names)
        hygiene_books.append(HygieneMissingBook(
            id=book.id,
            title=book.title,
            author=join_authors(author_names),
            authors=author_names,
            isbn=book.isbn,
            publisher=book.publisher,
            published_year=book.published_year,
            blurb=book.blurb,
            language=book.language,
            subtitle=book.subtitle,
            page_count=book.page_count or 0,
            cover_url=book.cover_url,
            missing_attributes=[a for a in requested if a in missing_attrs],
        ))

    total_missing_per_attribute: dict[str, int] = {}
    for attr in requested:
        cond = _missing_condition(attr)
        cnt = session.exec(
            select(func.count()).select_from(Book).where(
                Book.user_id == current_user.id,
                cond,
            )
        ).one()
        total_missing_per_attribute[attr.value] = cnt

    return HygieneMissingResponse(
        books=hygiene_books,
        total=total,
        total_missing_per_attribute=total_missing_per_attribute,
    )


@router.post("/batch-update", response_model=HygieneBatchUpdateResponse)
async def batch_update(
    req: HygieneBatchUpdateRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> HygieneBatchUpdateResponse:
    """Set a single attribute value on multiple books."""
    if not req.book_ids:
        raise HTTPException(status_code=422, detail="book_ids must not be empty")

    if len(req.book_ids) > _MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=422,
            detail=f"At most {_MAX_BATCH_SIZE} books can be updated at once",
        )

    if req.field == HygieneAttribute.author:
        if req.value is not None:
            val = str(req.value).strip()
            if not val:
                raise HTTPException(
                    status_code=422,
                    detail="author must not be empty",
                )
            req.value = val
    elif req.field == HygieneAttribute.published_year:
        if req.value is not None:
            try:
                val = int(str(req.value))
                if val > 2099:
                    raise ValueError
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=422,
                    detail="published_year must be an integer no greater than 2099",
                )
            req.value = val
    elif req.field == HygieneAttribute.page_count:
        if req.value is not None:
            try:
                val = int(str(req.value))
                if val < 1:
                    raise ValueError
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=422,
                    detail="page_count must be a positive integer",
                )
            req.value = val
    elif req.field == HygieneAttribute.language:
        if req.value is not None:
            val = str(req.value).strip().upper()
            if len(val) != 2 or not val.isalpha():
                raise HTTPException(
                    status_code=422,
                    detail="Language must be a 2-letter ISO code (for example: EN, DE, FR)",
                )
            req.value = val
    elif req.field == HygieneAttribute.cover_url:
        if req.value is not None:
            url = str(req.value).strip()
            if not is_external_cover_url(url):
                raise HTTPException(
                    status_code=422,
                    detail="cover_url must be an external http:// or https:// URL",
                )
            filename = await import_cover_from_url(
                url,
                settings.covers_dir,
                current_user.id,  # ty: ignore[invalid-argument-type]
                settings.cover_import_timeout_seconds,
            )
            if filename:
                req.value = f"/api/covers/{filename}"
            else:
                logger.warning("Cover download failed for %s — setting cover_url to None", url)
                req.value = None

    books = session.exec(
        select(Book).where(
            col(Book.id).in_(req.book_ids),
            Book.user_id == current_user.id,
        )
    ).all()

    found_ids = {b.id for b in books}
    missing_ids = set(req.book_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Books not found or not owned: {sorted(missing_ids)}",
        )

    skipped_ids: list[int] = []
    to_update_ids: list[int] = []
    current_authors_map = (
        load_authors_batch(session, [b.id for b in books if b.id is not None])
        if req.field == HygieneAttribute.author
        else {}
    )
    for book in books:
        if req.field == HygieneAttribute.author:
            # Compare against the current author set so multi-author books are
            # only skipped when they already contain exactly the target author.
            current_val = ", ".join(current_authors_map.get(book.id, [])) or None
        else:
            current_val = getattr(book, req.field.value)
        if current_val == req.value:
            skipped_ids.append(book.id)  # ty: ignore[invalid-argument-type]
        else:
            to_update_ids.append(book.id)  # ty: ignore[invalid-argument-type]

    updated = 0
    if to_update_ids:
        if req.field == HygieneAttribute.author:
            # Authors live in a relation table; a bulk SQL update does not work.
            assert current_user.id is not None
            for book in books:
                if book.id not in set(to_update_ids):
                    continue
                assert book.id is not None
                sync_book_authors(session, current_user.id, book.id, [str(req.value)])
                updated += 1
            cleanup_orphan_authors(session, current_user.id)
            try:
                session.commit()
            except Exception:
                session.rollback()
                logger.exception("Batch author update failed for %d books", len(to_update_ids))
                raise HTTPException(status_code=500, detail="Batch update failed due to a database error")
        else:
            try:
                stmt = (
                    sqlmodel_update(Book)
                    .where(col(Book.id).in_(to_update_ids))
                    .values({req.field.value: req.value})
                )
                updated = len(to_update_ids)
                session.exec(stmt)
                session.commit()
            except Exception:
                session.rollback()
                logger.exception("Batch update failed for %d books", len(to_update_ids))
                raise HTTPException(status_code=500, detail="Batch update failed due to a database error")

    return HygieneBatchUpdateResponse(
        updated=updated,
        skipped=len(skipped_ids),
        skipped_ids=skipped_ids,
    )
