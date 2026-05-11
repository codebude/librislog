from enum import Enum
from typing import Optional
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class ReadingStatus(str, Enum):
    want_to_read = "want_to_read"
    currently_reading = "currently_reading"
    read = "read"
    did_not_finish = "did_not_finish"


class UserRole(str, Enum):
    admin = "admin"
    user = "user"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    author: Optional[str] = Field(default=None, index=True)
    isbn: Optional[str] = Field(default=None, unique=True)
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: Optional[int] = None
    genre: Optional[str] = None
    notes: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    reading_status: ReadingStatus = Field(default=ReadingStatus.want_to_read, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    date_added: datetime = Field(default_factory=_utcnow, index=True)
    date_started: Optional[datetime] = Field(default=None, index=True)
    date_finished: Optional[datetime] = Field(default=None, index=True)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    firstname: str
    lastname: str
    email: str = Field(index=True, unique=True)
    role: UserRole = Field(default=UserRole.user, index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class UserSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    language: str = Field(default="en", max_length=10)


class ApiKey(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key_prefix: str = Field(index=True)
    key_hash: str = Field(index=True, unique=True)
    key_encrypted: Optional[str] = None
    description: Optional[str] = None
    is_primary: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class OidcLink(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, unique=True)
    provider_name: str = Field(index=True)
    oidc_sub: str = Field(index=True, unique=True)
    oidc_email: Optional[str] = Field(default=None)
    oidc_name: Optional[str] = Field(default=None)
    linked_at: datetime = Field(default_factory=_utcnow)
