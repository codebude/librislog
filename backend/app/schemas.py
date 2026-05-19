from typing import Optional
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.models import ReadingStatus, UserRole


class ReadingProgressCreate(SQLModel):
    page: int = Field(ge=0)


class ReadingProgressRead(SQLModel):
    id: int
    book_id: int
    page: int
    created_at: datetime
    updated_at: datetime


class ReadingProgressLatest(SQLModel):
    book_id: int
    current_page: int


class BookCreate(SQLModel):
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: Optional[int] = None
    language: Optional[str] = None
    tags: Optional[str] = None
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
    language: Optional[str] = None
    tags: Optional[str] = None
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
    tags: Optional[str] = None
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
    language: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str]
    rating: Optional[int]
    reading_status: ReadingStatus
    date_added: datetime
    date_started: Optional[datetime]
    date_finished: Optional[datetime]


class TagCloudEntry(SQLModel):
    tag: str
    count: int


class SuggestionList(SQLModel):
    suggestions: list[str]


class LibraryStats(SQLModel):
    total_books: int
    books_read: int
    books_reading: int
    books_want_to_read: int
    books_did_not_finish: int


class DashboardQuote(SQLModel):
    quote: str
    author: Optional[str] = None


class LanguageDistribution(SQLModel):
    language: Optional[str]
    count: int


class StatusDistribution(SQLModel):
    want_to_read: int
    currently_reading: int
    read: int
    did_not_finish: int


class PageBuckets(SQLModel):
    pages_to_read: int
    pages_read: int
    pages_wasted: int


class MonthlyPages(SQLModel):
    month: str
    pages: int


class MonthlyBooks(SQLModel):
    month: str
    count: int


class YearlyBooks(SQLModel):
    year: int
    count: int


class FavoriteAuthor(SQLModel):
    author: str
    book_count: int
    cover_urls: list[str]


class StatisticsResponse(SQLModel):
    avg_books_per_month: Optional[float]
    busiest_month: Optional[str]
    busiest_month_count: Optional[int]
    avg_page_count: Optional[float]
    most_popular_language: Optional[str]
    most_popular_language_count: Optional[int]
    language_distribution: list[LanguageDistribution]
    status_distribution: StatusDistribution
    page_buckets: PageBuckets
    pages_read_per_month: list[MonthlyPages]
    books_finished_per_month: list[MonthlyBooks]
    books_finished_per_year: list[YearlyBooks]
    favorite_author: Optional[FavoriteAuthor]


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
    timezone: str
    quote_service_enabled: bool


class UserSettingsUpdate(SQLModel):
    language: Optional[str] = None
    timezone: Optional[str] = None


class ConfirmationPhrase(SQLModel):
    confirmation: str


class DataResetDeleted(SQLModel):
    books: int
    tags: int
    progress_entries: int


class DataResetResponse(SQLModel):
    message: str
    deleted: DataResetDeleted


class ApiKeyCreate(SQLModel):
    description: Optional[str] = None


class ApiKeyRead(SQLModel):
    id: int
    key_prefix: str
    description: Optional[str]
    created_at: datetime
    last_used_at: Optional[datetime]


class ApiKeyCreateResponse(SQLModel):
    key: str
    api_key: ApiKeyRead


class StatusTransitionRequest(SQLModel):
    new_status: ReadingStatus
    force_date_started: Optional[datetime] = None
    force_date_finished: Optional[datetime] = None
    skip_auto_date_started: bool = False
    clear_date_started: bool = False
    clear_date_finished: bool = False


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


class DataExportRequest(SQLModel):
    datasets: list[Literal["books", "progress", "tags", "covers"]]
    format: Literal["csv", "json"]


class DataImportParseResponse(SQLModel):
    file_id: str
    format: Literal["csv", "json"]
    source_fields: list[str]
    sample_rows: list[dict]
    row_count: int


class DataImportMappingSave(SQLModel):
    name: str
    source_fields: list[str]
    mapping: dict[str, str]


class DataImportMappingRead(SQLModel):
    id: int
    name: str
    source_fields: list[str]
    mapping: dict[str, str]
    created_at: datetime
    updated_at: datetime


class DataImportMappingListItem(SQLModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime


class DataImportRunRequest(SQLModel):
    file_id: str
    mapping: dict[str, str]
    import_mode: Literal["rollback_all", "continue_on_error"] = "rollback_all"
    create_progress_for_read: bool = False


class DataImportSuggestRequest(SQLModel):
    file_id: str


class DataImportSuggestResponse(SQLModel):
    suggested_mapping: dict[str, str]
    db_fields: list[str]


class DataImportValidateRequest(SQLModel):
    file_id: str
    mapping: dict[str, str]
    create_progress_for_read: bool = False


class DataImportValidateResponse(SQLModel):
    valid: bool
    row_count: int
    warnings: list[str]
    errors: list[str]


class DataImportExecuteResult(SQLModel):
    imported: int
    failed: int
    failures: list[dict]
