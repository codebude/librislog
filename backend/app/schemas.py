from typing import Optional
from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models import ReadingStatus


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
    date_started: Optional[date] = None
    date_finished: Optional[date] = None


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
    date_started: Optional[date] = None
    date_finished: Optional[date] = None


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
    date_started: Optional[date]
    date_finished: Optional[date]
