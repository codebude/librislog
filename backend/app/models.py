from enum import Enum
from typing import Optional
from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


class ReadingStatus(str, Enum):
    want_to_read = "want_to_read"
    currently_reading = "currently_reading"
    read = "read"
    did_not_finish = "did_not_finish"


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
    date_added: datetime = Field(default_factory=_utcnow, index=True)
    date_started: Optional[date] = None
    date_finished: Optional[date] = None
