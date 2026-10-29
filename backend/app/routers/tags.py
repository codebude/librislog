"""Tag management endpoints — list tags and batch-apply tag changes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, select

from app.schemas import TagListEntry

from app.auth import require_user
from app.database import get_session
from app.models import Book, User
from app.schemas import TagBatchRequest, TagBatchResponse, TagListResponse
from app.services.tags import apply_batch_tags, list_tags_with_counts, parse_tags

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tags", tags=["tags"])

_MAX_BATCH_SIZE = 500
_MAX_TAGS_PER_LIST = 50


@router.get("", response_model=TagListResponse)
def list_tags(
    q: str = Query(default="", max_length=100, description="Substring filter on tag name"),
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> TagListResponse:
    """List the current user's tags with usage counts."""
    assert current_user.id is not None
    rows, total = list_tags_with_counts(session, current_user.id, q or None, limit, offset)

    return TagListResponse(
        tags=[TagListEntry(name=name, count=count) for name, count in rows],
        total=total,
    )


@router.post("/batch", response_model=TagBatchResponse)
def batch_tags(
    req: TagBatchRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> TagBatchResponse:
    """Add and/or remove tags on a set of books in one transaction."""
    if not req.book_ids:
        raise HTTPException(status_code=422, detail="book_ids must not be empty")

    deduped_ids = list(dict.fromkeys(req.book_ids))
    if len(deduped_ids) > _MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=422,
            detail=f"At most {_MAX_BATCH_SIZE} books can be updated at once",
        )

    if any("," in str(v) for v in req.add) or any("," in str(v) for v in req.remove):
        raise HTTPException(
            status_code=422, detail="Tag names must not contain commas"
        )

    add_names = parse_tags(req.add)
    remove_names = parse_tags(req.remove)

    if not add_names and not remove_names:
        raise HTTPException(
            status_code=422, detail="At least one tag must be provided in add or remove"
        )

    if len(add_names) > _MAX_TAGS_PER_LIST or len(remove_names) > _MAX_TAGS_PER_LIST:
        raise HTTPException(
            status_code=422,
            detail=f"At most {_MAX_TAGS_PER_LIST} tags per list",
        )

    overlap = {n.casefold() for n in add_names} & {n.casefold() for n in remove_names}
    if overlap:
        raise HTTPException(
            status_code=422,
            detail=f"A tag cannot be both added and removed: {sorted(overlap)}",
        )

    books = session.exec(
        select(Book).where(
            col(Book.id).in_(deduped_ids),
            Book.user_id == current_user.id,
        )
    ).all()

    found_ids = {b.id for b in books}
    missing_ids = set(deduped_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Books not found or not owned: {sorted(missing_ids)}",
        )

    try:
        assert current_user.id is not None
        result = apply_batch_tags(session, current_user.id, list(books), add_names, remove_names)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Batch tag update failed")
        raise HTTPException(status_code=500, detail="Batch tag update failed due to a database error")

    return TagBatchResponse(
        matched_books=result.matched_books,
        books_changed=result.books_changed,
        links_added=result.links_added,
        links_removed=result.links_removed,
        unchanged_books=result.unchanged_books,
        created_tags=result.created_tags,
        deleted_tags=result.deleted_tags,
    )