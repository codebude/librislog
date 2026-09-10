"""Shared helpers for public profile share links.

Keeps the JSON-in-DB visibility configuration, the whitelisted book DTO, and
the statistics filter in one place so the authenticated management router and
the public (unauthenticated) endpoint cannot drift apart.
"""

import json
from typing import Any

from sqlmodel import Session, col, select

from app.models import Book
from app.schemas import (
    PublicProfileBook,
    PublicProfileSectionKey,
    PublicProfileStatisticsKey,
    PublicProfileVisibilityConfig,
    StatisticsResponse,
)
from app.services.authors import load_authors_batch


def parse_visibility_config(raw: str | None) -> PublicProfileVisibilityConfig:
    """Parse the stored JSON visibility config leniently.

    Unknown or invalid section/statistic keys are silently dropped so that
    configs saved by a future version with more sections keep working after a
    downgrade, and vice versa.
    """
    if not raw:
        return PublicProfileVisibilityConfig()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return PublicProfileVisibilityConfig()
    if not isinstance(data, dict):
        return PublicProfileVisibilityConfig()

    sections = [
        key
        for key in (data.get("sections", []) or [])
        if key in PublicProfileSectionKey._value2member_map_
    ]
    statistics = [
        key
        for key in (data.get("statistics", []) or [])
        if key in PublicProfileStatisticsKey._value2member_map_
    ]
    return PublicProfileVisibilityConfig(sections=sections, statistics=statistics)


def serialize_visibility_config(config: PublicProfileVisibilityConfig) -> str:
    """Serialize a visibility config for storage in the database."""
    return config.model_dump_json()


def filter_statistics(
    full: StatisticsResponse,
    keys: list[PublicProfileStatisticsKey],
) -> dict[str, Any]:
    """Return only the requested statistics as a keyed dict.

    The response is keyed by the stable statistic keys so the frontend can
    render exactly what the owner selected, and nothing else is leaked.

    Helper fields that annotate a requested statistic (for example
    ``busiest_month_count`` for ``busiest_month``) are included alongside
    their parent so the descriptions render correctly.
    """
    data = full.model_dump()
    result = {key.value: data[key.value] for key in keys if key.value in data}
    for key in list(result):
        companion = COMPANION_STATISTIC_FIELDS.get(key)
        if companion is not None:
            result[companion] = data.get(companion)
    return result


COMPANION_STATISTIC_FIELDS = {
    "busiest_month": "busiest_month_count",
    "most_popular_language": "most_popular_language_count",
}


def build_public_books(
    session: Session,
    books: list[Book],
) -> list[PublicProfileBook]:
    """Convert owned book rows into the whitelisted public DTO."""
    book_ids = [b.id for b in books if b.id is not None]
    authors_map = load_authors_batch(session, book_ids)
    result: list[PublicProfileBook] = []
    for book in books:
        if book.id is None:
            continue
        result.append(
            PublicProfileBook(
                id=book.id,
                title=book.title,
                subtitle=book.subtitle,
                authors=authors_map.get(book.id, []),
                cover_url=book.cover_url,
                reading_status=book.reading_status,
                page_count=book.page_count,
                language=book.language,
                rating=book.rating,
                date_started=book.date_started,
                date_finished=book.date_finished,
            )
        )
    return result


BOOK_SECTIONS = {"currently_reading", "last_read", "reading_timeline", "full_library"}


def load_owner_books(session: Session, user_id: int) -> list[Book]:
    """Load all owned books ordered by date added (newest first)."""
    return list(
        session.exec(
            select(Book)
            .where(Book.user_id == user_id)
            .order_by(col(Book.date_added).desc(), col(Book.id).desc())
        ).all()
    )