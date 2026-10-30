"""SQLModel ORM models for LibrisLog database tables."""

from enum import Enum
import re
from typing import Optional
from datetime import date, datetime, timezone

import sqlalchemy as sa
from pydantic import model_validator
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


class AcquisitionStatus(str, Enum):
    """Enum of a book's current availability to the user."""

    owned = "owned"
    borrowed = "borrowed"
    digital_access = "digital_access"
    to_acquire = "to_acquire"


def normalize_medium_key(value: str) -> str:
    """Normalize a medium display value or enum key for comparisons."""
    return re.sub(r"[\s/]+", "_", value.strip().lower())


class Medium(str, Enum):
    """Enum of a book's physical or digital medium format."""

    print = "Print"
    ebook = "eBook"
    audiobook = "Audiobook"
    comic_graphic_novel = "Comic / Graphic Novel"
    magazine_newspaper = "Magazine / Newspaper"

    @classmethod
    def _missing_(cls, value: object) -> "Medium | None":
        """Accept enum keys and normalized display values at API boundaries."""
        if not isinstance(value, str):
            return None
        normalized = normalize_medium_key(value)
        for member in cls:
            member_value = normalize_medium_key(member.value)
            if normalized in {member.name, member_value}:
                return member
        return None


class UserRole(str, Enum):
    """Enum of possible user roles."""

    admin = "admin"
    user = "user"


class AvatarSource(str, Enum):
    """Selected source for a user's profile picture."""

    animal = "animal"
    oidc = "oidc"
    upload = "upload"


class Book(SQLModel, table=True):
    """A book in the user's library."""

    __table_args__ = (
        sa.UniqueConstraint("user_id", "isbn", name="uq_book_user_id_isbn"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    subtitle: Optional[str] = None
    isbn: Optional[str] = Field(default=None)
    cover_url: Optional[str] = None
    publisher: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_cover_url(cls, data: dict) -> dict:
        if isinstance(data, dict) and "cover_url" in data and data["cover_url"] == "":
            data["cover_url"] = None
        return data
    published_year: Optional[int] = None
    page_count: int = Field(default=0)
    language: Optional[str] = Field(default=None, max_length=2)
    notes: Optional[str] = None
    blurb: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    reading_status: ReadingStatus = Field(default=ReadingStatus.want_to_read, index=True)
    acquisition_status: AcquisitionStatus = Field(default=AcquisitionStatus.owned, index=True)
    medium: Optional[Medium] = Field(default=None, index=True)
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

    __tablename__: str = "tag"
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

    __tablename__: str = "book_tag"

    book_id: int = Field(foreign_key="book.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True, index=True)


class Author(SQLModel, table=True):
    """A user-specific author name that can be associated with books."""

    __tablename__: str = "author"
    __table_args__ = (sa.UniqueConstraint("user_id", "name", name="uq_author_user_id_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(index=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )


class BookAuthor(SQLModel, table=True):
    """Many-to-many association between books and authors."""

    __tablename__: str = "book_author"

    book_id: int = Field(foreign_key="book.id", primary_key=True)
    author_id: int = Field(foreign_key="author.id", primary_key=True, index=True)


class User(SQLModel, table=True):
    """A user account."""

    id: Optional[int] = Field(default=None, primary_key=True)
    firstname: str
    lastname: str
    email: str = Field(index=True, unique=True)
    role: UserRole = Field(default=UserRole.user, index=True)
    avatar_source: AvatarSource = Field(default=AvatarSource.animal, index=True)
    hashed_password: str
    credentials_version: int = Field(
        default=0,
        sa_column=Column(sa.Integer, default=0, nullable=False)
    )
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
    goal_pages_per_day_enabled: bool = Field(default=False)
    goal_pages_per_day: int = Field(default=20, ge=1)
    goal_pages_per_month_enabled: bool = Field(default=False)
    goal_pages_per_month: int = Field(default=300, ge=1)
    goal_books_per_month_enabled: bool = Field(default=False)
    goal_books_per_month: int = Field(default=2, ge=1)
    goal_books_per_year_enabled: bool = Field(default=False)
    goal_books_per_year: int = Field(default=25, ge=1)
    gamification_enabled: bool = Field(default=True)
    auto_set_date_started: bool = Field(default=True)
    auto_set_date_finished: bool = Field(default=True)
    statistics_range: str = Field(default="alltime", max_length=20)
    statistics_custom_from: Optional[date] = Field(default=None)
    statistics_custom_to: Optional[date] = Field(default=None)


class UserImage(SQLModel, table=True):
    """A locally cached or uploaded image owned by a user."""

    __tablename__: str = "user_image"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "kind", "variant", name="uq_user_image_user_kind_variant"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("user.id"),
            index=True,
            nullable=False,
        ),
    )
    kind: str = Field(default="avatar", index=True)
    variant: str = Field(index=True)
    filename: Optional[str] = None
    external_url: Optional[str] = None
    content_type: Optional[str] = None
    byte_size: Optional[int] = None
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow, nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(
            UtcDateTime,
            default=utcnow,
            onupdate=utcnow,
            nullable=False,
        ),
    )


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


class ReadingSession(SQLModel, table=True):
    """A single reading period (first read, re-read, etc.) of a book.

    ``Book.date_started`` / ``Book.date_finished`` remain a denormalized mirror
    of the *current* session (``is_current=True``), or of the latest session when
    none is current, so every existing consumer keeps working unchanged. A book
    with a single session therefore behaves identically to the pre-session model.

    At most one current session exists per book (enforced by a partial unique
    index on ``is_current`` and by the service layer).
    """

    __tablename__: str = "reading_session"
    __table_args__ = (
        sa.Index(
            "uq_reading_session_book_current",
            "book_id",
            unique=True,
            sqlite_where=sa.text("is_current = 1"),
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    status: ReadingStatus = Field(index=True)
    date_started: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, index=True)
    )
    date_finished: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, index=True)
    )
    is_current: bool = Field(default=False, index=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )


class ReadingProgress(SQLModel, table=True):
    """A page-number reading progress entry for a book."""

    __tablename__: str = "reading_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # Note: no FK to reading_session here. SQLite cannot add a FOREIGN KEY via
    # ALTER TABLE, and this project does not enforce FKs at the SQLite level, so
    # the relationship is maintained in the application layer only.
    session_id: Optional[int] = Field(default=None, index=True)
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


class EmbedToken(SQLModel, table=True):
    """A scoped embed token for iframe/dashboard integrations."""

    __tablename__: str = "embed_token"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=255)
    token_prefix: str = Field(index=True)
    token_hash: str = Field(index=True, unique=True)
    scopes: str = Field(default="embed:stats:read")  # comma-separated list
    allowed_origins: Optional[str] = None  # comma-separated; null = wildcard
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, default=None)
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, default=None)
    )
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )
    revoked_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, default=None)
    )


class PublicProfileAudience(str, Enum):
    """Who may access a public profile share link."""

    public = "public"                # everyone, including anonymous viewers
    authenticated = "authenticated"  # logged-in users only


class PublicProfileLink(SQLModel, table=True):
    """A shareable public profile link owned by a user."""

    __tablename__: str = "public_profile_link"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=255)
    token_prefix: str = Field(index=True)
    token: Optional[str] = Field(default=None, nullable=True)
    token_hash: str = Field(index=True, unique=True)
    audience: PublicProfileAudience = Field(default=PublicProfileAudience.public)
    language: Optional[str] = Field(default=None, nullable=True)
    visibility_config_json: str = Field(
        default="{}",
        sa_column=Column(sa.Text, default="{}"),
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, default=None),
    )
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow),
    )
    revoked_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(UtcDateTime, default=None),
    )


class ImportMapping(SQLModel, table=True):
    """A saved column-mapping configuration for data import."""

    __tablename__: str = "import_mapping"
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


class InstallationInfo(SQLModel, table=True):
    """Singleton row storing the anonymous installation id for telemetry.

    The id is a random UUIDv4 generated on first startup and persisted in the
    database so it stays stable across container restarts and updates. It is
    never derived from any machine-specific identifier.
    """

    __tablename__: str = "installation_info"

    id: int = Field(default=1, primary_key=True)
    installation_id: str = Field(max_length=64)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow)
    )
