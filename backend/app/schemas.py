"""Pydantic / SQLModel request and response schemas for the API."""

from typing import Optional
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator
from sqlmodel import Field, SQLModel

from app.models import ReadingStatus, UserRole


class ReadingProgressCreate(SQLModel):
    """Request body to create a reading progress entry."""
    page: int = Field(ge=0)


class ReadingProgressRead(SQLModel):
    """Response schema for a reading progress entry."""
    id: int
    book_id: int
    page: int
    created_at: datetime
    updated_at: datetime


class ReadingProgressUpdate(SQLModel):
    """Request body to update a reading progress entry's date."""
    created_at: datetime


class ReadingProgressLatest(SQLModel):
    """Latest reading progress for a single book."""
    book_id: int
    current_page: int


class BookCreate(SQLModel):
    """Request body to create a new book."""
    title: str
    subtitle: Optional[str] = None
    author: str
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: int
    language: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    blurb: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    reading_status: ReadingStatus = ReadingStatus.want_to_read
    date_started: Optional[datetime] = None
    date_finished: Optional[datetime] = None


class BookUpdate(SQLModel):
    """Request body to partially update a book."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: Optional[int] = None
    language: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    blurb: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    reading_status: Optional[ReadingStatus] = None
    date_started: Optional[datetime] = None
    date_finished: Optional[datetime] = None


class BookImportCandidate(SQLModel):
    """A book result from an external API, not yet persisted locally."""
    title: str
    subtitle: Optional[str] = None
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: Optional[int] = None
    language: Optional[str] = None
    tags: Optional[str] = None
    blurb: Optional[str] = None
    source: str  # "open_library" | "google_books" | "hardcover"


class CoverCandidate(SQLModel):
    """A single cover image candidate discovered by the auto-search."""
    source: str
    url: str
    available: bool
    width: Optional[int] = None
    height: Optional[int] = None
    filesize: Optional[int] = None
    content_type: Optional[str] = None


class CoverCandidateList(SQLModel):
    """List of cover candidates returned by the search endpoint."""
    candidates: list[CoverCandidate]
    query_isbn: str


class CoverCandidateImportRequest(SQLModel):
    """Request body to import a cover candidate by URL."""
    url: str


class BookImportRequest(SQLModel):
    """Persists a BookImportCandidate into the local DB."""
    candidate: BookImportCandidate
    reading_status: ReadingStatus = ReadingStatus.want_to_read


class BookRead(SQLModel):
    """Response schema for a single book."""
    id: int
    title: str
    subtitle: Optional[str]
    author: Optional[str]
    isbn: Optional[str]
    cover_url: Optional[str]
    publisher: Optional[str]
    published_year: Optional[int]
    page_count: Optional[int]
    language: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str]
    blurb: Optional[str]
    rating: Optional[int]
    reading_status: ReadingStatus
    date_added: datetime
    date_started: Optional[datetime]
    date_finished: Optional[datetime]


class BookListResponse(BaseModel):
    """Paginated book list with total count."""
    books: list[BookRead]
    total: int


class TagCloudEntry(SQLModel):
    """A single tag with its usage count."""
    tag: str
    count: int


class SuggestionList(SQLModel):
    """List of autocomplete suggestions."""
    suggestions: list[str]


class LibraryStats(SQLModel):
    """Aggregated library statistics."""
    total_books: int
    books_read: int
    books_reading: int
    books_want_to_read: int
    books_did_not_finish: int


class DashboardQuote(SQLModel):
    """A motivational quote shown on the dashboard."""
    quote: str
    author: Optional[str] = None


class LanguageDistribution(SQLModel):
    """Language distribution entry."""
    language: Optional[str]
    count: int


class StatusDistribution(SQLModel):
    """Count of books per reading status."""
    want_to_read: int
    currently_reading: int
    read: int
    did_not_finish: int


class PageBuckets(SQLModel):
    """Page count buckets for the statistics dashboard."""
    pages_to_read: int
    pages_read: int
    pages_wasted: int


class MonthlyPages(SQLModel):
    """Pages read in a given month."""
    month: str
    pages: int


class MonthlyBooks(SQLModel):
    """Books finished in a given month."""
    month: str
    count: int


class YearlyBooks(SQLModel):
    """Books finished in a given year."""
    year: int
    count: int


class TopAuthor(SQLModel):
    """An author with the most books in the library."""
    author: str
    book_count: int
    covers: list["TopAuthorCover"]


class TopAuthorCover(SQLModel):
    """Cover reference for a book by a top author."""
    book_id: int
    title: str
    reading_status: ReadingStatus
    cover_url: str | None


class TopRatedBook(SQLModel):
    """A book appearing in top/worst rated lists."""
    book_id: int
    title: str
    author: Optional[str]
    rating: int
    reading_status: ReadingStatus
    cover_url: Optional[str]


class StatisticsResponse(SQLModel):
    """Full statistics dashboard response."""
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
    top_authors: list[TopAuthor]
    books_with_rating: int
    books_without_rating: int
    average_rating: Optional[float]
    top_rated_books: list[TopRatedBook]
    worst_rated_books: list[TopRatedBook]


class UserLogin(SQLModel):
    """Login request body."""
    email: str
    password: str


class SetupRequest(SQLModel):
    """Initial admin setup request body."""
    firstname: str
    lastname: str
    email: str
    password: str


class UserCreate(SQLModel):
    """Admin-only user creation request."""
    firstname: str
    lastname: str
    email: str
    password: str
    role: UserRole = UserRole.user


class UserRead(SQLModel):
    """User read response."""
    id: int
    firstname: str
    lastname: str
    email: str
    role: UserRole
    created_at: datetime


class UserUpdate(SQLModel):
    """Admin-only user update request."""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class ProfileUpdate(SQLModel):
    """Profile update request (non-admin)."""
    model_config = ConfigDict(extra="forbid")

    firstname: Optional[str] = None
    lastname: Optional[str] = None
    password: Optional[str] = None


class UserAdminUpdate(SQLModel):
    """Admin-only user update request with role support."""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None


class UserSettingsRead(SQLModel):
    """User settings read response."""
    user_id: int
    language: str
    timezone: str
    quote_service_enabled: bool
    theme: str
    custom_theme: Optional[str] = None


class UserSettingsUpdate(SQLModel):
    """User settings update request."""
    language: Optional[str] = None
    timezone: Optional[str] = None
    theme: Optional[str] = None
    custom_theme: Optional[str] = None

    @field_validator('theme')
    @classmethod
    def validate_theme(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ('light', 'dark', 'custom'):
            raise ValueError('theme must be one of: light, dark, custom')
        return v

    @field_validator('custom_theme')
    @classmethod
    def validate_custom_theme(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == '':
            return None
        return v


class ConfirmationPhrase(SQLModel):
    """A confirmation phrase required for destructive actions."""
    confirmation: str


class DataResetDeleted(SQLModel):
    """Counts of deleted items after a data reset."""
    books: int
    tags: int
    progress_entries: int


class DataResetResponse(SQLModel):
    """Response after a data reset."""
    message: str
    deleted: DataResetDeleted


class ApiKeyCreate(SQLModel):
    """API key creation request."""
    description: Optional[str] = None


class ApiKeyRead(SQLModel):
    """API key read response (without the raw key value)."""
    id: int
    key_prefix: str
    description: Optional[str]
    created_at: datetime
    last_used_at: Optional[datetime]


class ApiKeyCreateResponse(SQLModel):
    """API key creation response containing the raw key (shown once)."""
    key: str
    api_key: ApiKeyRead


class StatusTransitionRequest(SQLModel):
    """Request body for changing a book's reading status."""
    new_status: ReadingStatus
    force_date_started: Optional[datetime] = None
    force_date_finished: Optional[datetime] = None
    skip_auto_date_started: bool = False
    clear_date_started: bool = False
    clear_date_finished: bool = False


class DateConflict(SQLModel):
    """Describes a date conflict in a status transition."""
    field: str
    existing_date: datetime
    suggested_date: datetime


class StatusTransitionResponse(SQLModel):
    """Response after a status transition, possibly with a date conflict."""
    book: BookRead
    date_conflict: Optional[DateConflict] = None


class OidcConfigRead(SQLModel):
    """OIDC provider configuration."""
    enabled: bool
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None


class OidcLinkRead(SQLModel):
    """OIDC link status."""
    linked: bool
    provider_name: Optional[str] = None
    oidc_email: Optional[str] = None
    oidc_name: Optional[str] = None


class OidcLoginResponse(SQLModel):
    """OIDC login response."""
    user: UserRead


class HygieneAttribute(str, Enum):
    """Book attributes that can be checked for missing values."""
    author = "author"
    isbn = "isbn"
    publisher = "publisher"
    published_year = "published_year"
    blurb = "blurb"
    language = "language"
    subtitle = "subtitle"
    page_count = "page_count"
    cover_url = "cover_url"


class HygieneMissingBook(SQLModel):
    """A single book in the data-hygiene listing with its missing fields annotated."""
    id: int
    title: str
    author: str | None
    isbn: str | None
    publisher: str | None
    published_year: int | None
    blurb: str | None
    language: str | None
    subtitle: str | None
    page_count: int
    cover_url: str | None
    missing_attributes: list[HygieneAttribute]


class HygieneMissingResponse(SQLModel):
    """Paginated list of books with missing attributes."""
    books: list[HygieneMissingBook]
    total: int
    total_missing_per_attribute: dict[str, int]


class HygieneBatchUpdateRequest(SQLModel):
    """Batch-update a single field on multiple books."""
    book_ids: list[int]
    field: HygieneAttribute
    value: str | int | None


class HygieneBatchUpdateResponse(SQLModel):
    """Result of a batch update operation."""
    updated: int
    skipped: int
    skipped_ids: list[int]


class DailyPages(SQLModel):
    """Pages read on a single day."""
    date: str
    pages: int


class DailyPagesResponse(SQLModel):
    """Daily pages breakdown response."""
    data: list[DailyPages]
    total_days: int
    days_with_activity: int
    total_pages: int


class DataExportRequest(SQLModel):
    """Data export request body."""
    datasets: list[Literal["books", "progress", "tags", "covers"]]
    format: Literal["csv", "json"]


class DataImportParseResponse(SQLModel):
    """Response after parsing an uploaded import file."""
    file_id: str
    format: Literal["csv", "json"]
    source_fields: list[str]
    sample_rows: list[dict]
    row_count: int


class ImportFieldConfig(SQLModel):
    """Per-target field mapping configuration."""
    source: Optional[str] = None
    transform: Optional[str] = None


class DataImportMappingSave(SQLModel):
    """Request body to save an import column mapping."""
    name: str
    source_fields: list[str]
    mapping: dict[str, ImportFieldConfig]


class DataImportMappingRead(SQLModel):
    """Saved import mapping read response."""
    id: int
    name: str
    source_fields: list[str]
    mapping: dict[str, ImportFieldConfig]
    created_at: datetime
    updated_at: datetime
    is_predefined: bool = False


class DataImportMappingListItem(SQLModel):
    """Summary of a saved import mapping for list views."""
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    is_predefined: bool = False


class DataImportRunRequest(SQLModel):
    """Request body to execute an import."""
    file_id: str
    mapping: dict[str, ImportFieldConfig]
    import_mode: Literal["rollback_all", "continue_on_error"] = "rollback_all"
    create_progress_for_read: bool = False


class DataImportSuggestRequest(SQLModel):
    """Request body to get a suggested mapping."""
    file_id: str


class DataImportSuggestResponse(SQLModel):
    """Suggested column mapping response."""
    suggested_mapping: dict[str, ImportFieldConfig]
    db_fields: list[str]


class DataImportValidateRequest(SQLModel):
    """Request body to validate an import."""
    file_id: str
    mapping: dict[str, ImportFieldConfig]
    create_progress_for_read: bool = False


class DataImportValidateResponse(SQLModel):
    """Import validation response."""
    valid: bool
    row_count: int
    warnings: list[str]
    errors: list[str]


class DataImportPreviewRow(SQLModel):
    """A single row in the import preview."""
    row_number: int
    source: dict[str, str]
    transformed: dict[str, Optional[str]]
    errors: list[str]


class DataImportPreviewRequest(SQLModel):
    """Request body to preview an import with transforms."""
    file_id: str
    mapping: dict[str, ImportFieldConfig]


class DataImportPreviewResponse(SQLModel):
    """Import preview response."""
    preview_rows: list[DataImportPreviewRow]
    row_count: int
    errors: list[str] = []


class DataImportExecuteResult(SQLModel):
    """Import execution result summary."""
    imported: int
    failed: int
    failures: list[dict]
