"""SQLModel ORM models for LibrisLog database tables."""

from enum import Enum
from typing import Optional
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, TypeDecorator
from sqlmodel import Field, SQLModel

from app.time_utils import utcnow


class UtcDateTime(TypeDecorator):
    """SQLAlchemy type decorator that stores aware datetimes as naive UTC.

    On bind: converts aware datetime to UTC and strips tzinfo.
    On result: attaches UTC tzinfo to the returned value.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        """Convert aware datetime to naive UTC before storing."""
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        """Attach UTC tzinfo to the value returned from the database."""
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class ReadingStatus(str, Enum):
    """Enum of possible reading statuses for a book."""

    want_to_read = "want_to_read"
    currently_reading = "currently_reading"
    read = "read"
    did_not_finish = "did_not_finish"


class UserRole(str, Enum):
    """Enum of possible user roles."""

    admin = "admin"
    user = "user"


class Book(SQLModel, table=True):
    """A book in the user's library."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    subtitle: Optional[str] = None
    author: str = Field(default="", index=True)
    isbn: Optional[str] = Field(default=None, unique=True)
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: int = Field(default=0)
    language: Optional[str] = Field(default=None, max_length=2)
    notes: Optional[str] = None
    blurb: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    reading_status: ReadingStatus = Field(default=ReadingStatus.want_to_read, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    date_added: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow, index=True)
    )
    date_started: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, index=True)
    )
    date_finished: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, index=True)
    )


class Tag(SQLModel, table=True):
    """A user-specific tag that can be applied to books."""

    __tablename__ = "tag"
    __table_args__ = (sa.UniqueConstraint("user_id", "name", name="uq_tag_user_id_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(index=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )


class BookTag(SQLModel, table=True):
    """Many-to-many association between books and tags."""

    __tablename__ = "book_tag"

    book_id: int = Field(foreign_key="book.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True, index=True)


class User(SQLModel, table=True):
    """A user account."""

    id: Optional[int] = Field(default=None, primary_key=True)
    firstname: str
    lastname: str
    email: str = Field(index=True, unique=True)
    role: UserRole = Field(default=UserRole.user, index=True)
    hashed_password: str
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )


class UserSettings(SQLModel, table=True):
    """Per-user settings such as language, timezone, and theme."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    language: str = Field(default="en", max_length=10)
    timezone: str = Field(default="UTC", max_length=64)
    theme: str = Field(default="light", max_length=20)
    custom_theme: Optional[str] = Field(default=None, max_length=30)


class ApiKey(SQLModel, table=True):
    """API key for programmatic access."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key_prefix: str = Field(index=True)
    key_hash: str = Field(index=True, unique=True)
    key_encrypted: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, default=None)
    )
    revoked_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, default=None)
    )


class ReadingProgress(SQLModel, table=True):
    """A page-number reading progress entry for a book."""

    __tablename__ = "reading_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    page: int = Field(ge=0)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )


class OidcLink(SQLModel, table=True):
    """Links an OIDC identity to a local user account."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, unique=True)
    provider_id: str = Field(index=True)
    oidc_sub: str = Field(index=True, unique=True)
    oidc_email: Optional[str] = Field(default=None)
    oidc_name: Optional[str] = Field(default=None)
    linked_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )


class ImportMapping(SQLModel, table=True):
    """A saved column-mapping configuration for data import."""

    __tablename__ = "import_mapping"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "name", name="uq_import_mapping_user_id_name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=255)
    schema_fingerprint: str = Field(max_length=64, index=True)
    source_fields_json: str
    mapping_json: str
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )
