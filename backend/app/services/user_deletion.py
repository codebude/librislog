"""User data and account deletion utilities."""

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from app.models import ApiKey, Book, BookTag, OidcLink, ReadingProgress, Tag, User, UserRole, UserSettings
from app.time_utils import utcnow
from app.services.cover_storage import delete_cover_file, local_cover_filename


@dataclass
class ReadingDataDeletionCounts:
    """Counts of items deleted during a reading-data or account deletion."""
    books: int
    tags: int
    progress_entries: int


def assert_not_last_admin(session: Session, target_user: User) -> None:
    """Raise HTTP 403 if *target_user* is the last remaining admin."""
    if target_user.role != UserRole.admin:
        return
    admin_count = session.exec(
        select(func.count()).select_from(User).where(User.role == UserRole.admin)
    ).one()
    if admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete the last administrator account.",
        )


def delete_user_reading_data(session: Session, user_id: int, covers_dir: str) -> ReadingDataDeletionCounts:
    """Delete all reading data (books, tags, progress) for a user.

    Cover files that are not shared with other users are also deleted.
    """
    user_books = session.exec(select(Book).where(Book.user_id == user_id)).all()
    book_ids = [book.id for book in user_books if book.id is not None]

    progress_count = session.exec(
        select(func.count()).select_from(ReadingProgress).where(ReadingProgress.user_id == user_id)
    ).one()
    tags_count = session.exec(
        select(func.count()).select_from(Tag).where(Tag.user_id == user_id)
    ).one()

    if book_ids:
        for cover_url in {book.cover_url for book in user_books if book.cover_url}:
            filename = local_cover_filename(cover_url)
            if not filename:
                continue
            shared = session.exec(
                select(Book.id).where(Book.cover_url == cover_url, Book.user_id != user_id)
            ).first()
            if not shared:
                delete_cover_file(filename, covers_dir)

        for link in session.exec(select(BookTag).where(BookTag.book_id.in_(book_ids))).all():
            session.delete(link)

    for entry in session.exec(select(ReadingProgress).where(ReadingProgress.user_id == user_id)).all():
        session.delete(entry)

    for tag in session.exec(select(Tag).where(Tag.user_id == user_id)).all():
        session.delete(tag)

    for book in user_books:
        session.delete(book)

    return ReadingDataDeletionCounts(
        books=len(user_books),
        tags=tags_count,
        progress_entries=progress_count,
    )


def delete_user_account_data(session: Session, user: User, covers_dir: str) -> ReadingDataDeletionCounts:
    """Delete a user and all associated data.

    Revokes API keys, unlinks OIDC, removes settings, then deletes the user.
    """
    deletion_counts = delete_user_reading_data(session, user.id, covers_dir)

    for key in session.exec(select(ApiKey).where(ApiKey.user_id == user.id)).all():
        key.revoked_at = utcnow()
        session.add(key)

    oidc_link = session.exec(select(OidcLink).where(OidcLink.user_id == user.id)).first()
    if oidc_link:
        session.delete(oidc_link)

    settings = session.exec(select(UserSettings).where(UserSettings.user_id == user.id)).first()
    if settings:
        session.delete(settings)

    session.delete(user)
    return deletion_counts
