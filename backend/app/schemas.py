from typing import Optional
from datetime import datetime

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.models import ReadingStatus, UserRole


class BookCreate(SQLModel):
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: Optional[int] = None
    genre: Optional[str] = None
    notes: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    reading_status: ReadingStatus = ReadingStatus.want_to_read
    date_started: Optional[datetime] = None
    date_finished: Optional[datetime] = None


class BookUpdate(SQLModel):
    title: Optional[str] = None
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: Optional[int] = None
    genre: Optional[str] = None
    notes: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    reading_status: Optional[ReadingStatus] = None
    date_started: Optional[datetime] = None
    date_finished: Optional[datetime] = None


class BookImportCandidate(SQLModel):
    """A book result from an external API, not yet persisted locally."""
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: Optional[int] = None
    language: Optional[str] = None
    genre: Optional[str] = None
    source: str  # "open_library" | "google_books"


class BookImportRequest(SQLModel):
    """Persists a BookImportCandidate into the local DB."""
    candidate: BookImportCandidate
    reading_status: ReadingStatus = ReadingStatus.want_to_read


class BookRead(SQLModel):
    id: int
    title: str
    author: Optional[str]
    isbn: Optional[str]
    cover_url: Optional[str]
    publisher: Optional[str]
    published_year: Optional[int]
    page_count: Optional[int]
    genre: Optional[str]
    notes: Optional[str]
    rating: Optional[int]
    reading_status: ReadingStatus
    date_added: datetime
    date_started: Optional[datetime]
    date_finished: Optional[datetime]


class UserLogin(SQLModel):
    email: str
    password: str


class SetupRequest(SQLModel):
    firstname: str
    lastname: str
    email: str
    password: str


class UserCreate(SQLModel):
    firstname: str
    lastname: str
    email: str
    password: str
    role: UserRole = UserRole.user


class UserRead(SQLModel):
    id: int
    firstname: str
    lastname: str
    email: str
    role: UserRole
    created_at: datetime


class UserUpdate(SQLModel):
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class ProfileUpdate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    firstname: Optional[str] = None
    lastname: Optional[str] = None
    password: Optional[str] = None


class UserAdminUpdate(SQLModel):
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None


class UserSettingsRead(SQLModel):
    user_id: int
    language: str


class UserSettingsUpdate(SQLModel):
    language: Optional[str] = None


class ApiKeyCreate(SQLModel):
    description: Optional[str] = None


class ApiKeyRead(SQLModel):
    id: int
    key_prefix: str
    description: Optional[str]
    is_primary: bool
    created_at: datetime
    last_used_at: Optional[datetime]


class ApiKeyCreateResponse(SQLModel):
    key: str
    api_key: ApiKeyRead


class StatusTransitionRequest(SQLModel):
    new_status: ReadingStatus
    force_date_started: Optional[datetime] = None
    force_date_finished: Optional[datetime] = None


class DateConflict(SQLModel):
    field: str
    existing_date: datetime
    suggested_date: datetime


class StatusTransitionResponse(SQLModel):
    book: BookRead
    date_conflict: Optional[DateConflict] = None


class OidcConfigRead(SQLModel):
    enabled: bool
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None


class OidcLinkRead(SQLModel):
    linked: bool
    provider_name: Optional[str] = None
    oidc_email: Optional[str] = None
    oidc_name: Optional[str] = None


class OidcLoginResponse(SQLModel):
    user: UserRead
    api_key: str
