# 48 — Data Import/Export

## Overview

Add a comprehensive data import/export feature for LibrisLog that allows users to:

1. **Export** their library data (books, reading progress, covers, tags) to CSV or JSON with multi-select dataset options.
2. **Import** books from CSV or JSON files with flexible field mapping, validation, simulation mode, and configurable failure handling.
3. Access these features through a dedicated `/data` page with tabbed UI (Import/Export).
4. Navigate to the data page from the book import dialog and profile page.

This feature empowers users to back up their library, migrate data between instances, bulk-import book collections, and integrate with external tools.

---

## 1. Design Decisions

### 1.1 Export Architecture

**Export Options:**
- **Datasets**: Books (basic fields), Books (with covers), Reading Progress Entries, Tags
- **Formats**: CSV, JSON
- **Packaging**: All selected datasets are packaged into a single ZIP file with a manifest describing the export

**ZIP Structure:**
```
export-2024-05-18T12-30-45Z.zip
├── manifest.json         # Export metadata (timestamp, version, datasets, format)
├── books.csv / books.json
├── progress.csv / progress.json
├── tags.csv / tags.json
└── covers/               # Only if "Books (with covers)" selected
    ├── 1__abc123.jpg
    ├── 1__def456.png
    └── ...
```

**Manifest Structure:**
```json
{
  "export_timestamp": "2024-05-18T12:30:45Z",
  "app_version": "0.1.0",
  "user_id": 42,
  "user_email": "user@example.com",
  "datasets": ["books", "covers", "progress", "tags"],
  "format": "json",
  "counts": {
    "books": 127,
    "covers": 89,
    "progress_entries": 543,
    "tags": 24
  }
}
```

**CSV Field Order (Books):**
```
title, author, isbn, publisher, published_year, page_count, language, tags, notes, rating, reading_status, date_added, date_started, date_finished, cover_url
```

**JSON Format (Books):**
```json
[
  {
    "title": "Example Book",
    "author": "Author Name",
    "isbn": "9781234567890",
    "publisher": "Publisher",
    "published_year": 2020,
    "page_count": 350,
    "language": "EN",
    "tags": "fiction,sci-fi",
    "notes": "Loved it!",
    "rating": 5,
    "reading_status": "read",
    "date_added": "2024-01-15T10:00:00Z",
    "date_started": "2024-01-20T08:30:00Z",
    "date_finished": "2024-02-10T22:15:00Z",
    "cover_url": "/api/covers/1__abc123.jpg"
  }
]
```

**Rationale:**
- ZIP packaging allows bundling multiple datasets and cover files in a single download
- Manifest enables version checking and validation on import
- Both CSV and JSON support flat object structures that map cleanly to database models
- Cover files included in ZIP preserve the local cache prefix (user_id__hash.ext) for deduplication on import

### 1.2 Import Architecture

**Import Flow:**

1. **File Upload** → Single file (CSV/JSON/ZIP), drag-and-drop or file picker
2. **Parse & Analyze** → Backend extracts fields, detects format, returns column list
3. **Mapping UI** → User maps source fields to LibrisLog attributes
4. **Save/Load Mappings** → Persist mappings for reuse (per-user, keyed by schema fingerprint)
5. **Simulate** → Validate all data, report issues (required fields, data types, conflicts)
6. **Import** → Write to database with progress tracking

**Import Modes (on row failure):**

a) **Rollback All** (default): Entire import cancelled if any row fails (DB transaction rollback)
b) **Continue on Error**: Import all valid rows, report failed rows with error details

**Mapping Storage:**

Stored in a new `import_mapping` table:
```python
class ImportMapping(SQLModel, table=True):
    id: int
    user_id: int
    name: str                    # User-assigned name ("My Goodreads Export")
    schema_fingerprint: str      # Hash of sorted source field names
    mapping: str                 # JSON: {"source_field": "db_field", ...}
    created_at: datetime
    updated_at: datetime
```

**Schema Fingerprint:**
- Computed as `sha256(json.dumps(sorted(source_fields)))`
- Used to match saved mappings to new uploads with identical structure
- If a loaded mapping references fields absent in the current file, those mappings are ignored with a warning

**Cover Handling on Import:**
- If source has `cover_url` and it's an HTTP(S) URL → download and cache using existing `download_cover()` logic (same as manual book creation)
- If source has `cover_url` and it matches a file in the uploaded ZIP's `covers/` directory → save directly to `covers_dir`
- No external API calls (OpenLibrary/Google) during import
- Covers download/import happens during the actual import step, not during simulate

**Progress Tracking:**
- Use **Server-Sent Events (SSE)** like the existing `/api/import/search/stream` endpoint
- Progress events include: `parsing`, `validating`, `importing`, `progress` (with row count/total), `complete`, `error`

### 1.3 API Contract

#### Export

**Endpoint:**
```
POST /api/data/export
```

**Request Body:**
```json
{
  "datasets": ["books", "covers", "progress", "tags"],
  "format": "json"  // "json" | "csv"
}
```

**Response:**
- **200 OK**: Binary ZIP file download
- **Content-Type**: `application/zip`
- **Content-Disposition**: `attachment; filename="librislog-export-2024-05-18T12-30-45Z.zip"`
- **400 Bad Request**: Invalid dataset/format selection

**Export Progress (SSE):**
Not implemented in first iteration — export is fast enough (< 10s for most libraries) to run synchronously.

#### Parse Import File

**Endpoint:**
```
POST /api/data/import/parse
```

**Request:** Multipart form with single file (CSV/JSON/ZIP)

**Response:**
```json
{
  "file_id": "temp-abc123",  // Temporary identifier for this upload session
  "format": "csv",           // "csv" | "json"
  "is_zip": false,
  "has_covers": false,
  "source_fields": ["Title", "Author", "ISBN", "MyRating", "DateRead"],
  "sample_rows": [
    {"Title": "Book 1", "Author": "Author A", "ISBN": "123", "MyRating": "5", "DateRead": "2024-01-15"},
    {"Title": "Book 2", "Author": "Author B", "ISBN": "456", "MyRating": "4", "DateRead": "2024-02-20"}
  ],
  "row_count": 127
}
```

**Storage:**
- Uploaded files stored temporarily in `data/import_temp/{user_id}/{file_id}.{ext}`
- Cleaned up after import or after 24 hours
- MAX file size: 100 MB
- MAX row count: 10,000 rows (first iteration limit)

#### Get Suggested Mapping

**Endpoint:**
```
POST /api/data/import/suggest-mapping
```

**Request:**
```json
{
  "file_id": "temp-abc123",
  "source_fields": ["Title", "Author", "ISBN", "MyRating", "DateRead"]
}
```

**Response:**
```json
{
  "suggested_mapping": {
    "Title": "title",
    "Author": "author",
    "ISBN": "isbn",
    "MyRating": "rating",
    "DateRead": "date_finished"
  },
  "db_fields": [
    "title", "author", "isbn", "publisher", "published_year", 
    "page_count", "language", "tags", "notes", "rating", 
    "reading_status", "date_started", "date_finished"
  ]
}
```

**Mapping Logic:**
- Case-insensitive exact match first (e.g., "title" → "title")
- Common aliases (e.g., "Book Title" → "title", "Pages" → "page_count", "Year" → "published_year")
- Unmapped fields left null in suggestion

#### Save Mapping

**Endpoint:**
```
POST /api/data/import/mappings
```

**Request:**
```json
{
  "name": "My Goodreads Export",
  "schema_fingerprint": "abc123...",
  "mapping": {
    "Title": "title",
    "Author": "author",
    "ISBN": "isbn"
  }
}
```

**Response:**
```json
{
  "id": 42,
  "name": "My Goodreads Export",
  "schema_fingerprint": "abc123...",
  "mapping": { ... },
  "created_at": "2024-05-18T12:00:00Z",
  "updated_at": "2024-05-18T12:00:00Z"
}
```

#### List Saved Mappings

**Endpoint:**
```
GET /api/data/import/mappings
```

**Response:**
```json
[
  {
    "id": 42,
    "name": "My Goodreads Export",
    "schema_fingerprint": "abc123...",
    "created_at": "2024-05-18T12:00:00Z",
    "updated_at": "2024-05-18T12:00:00Z"
  }
]
```

#### Load Mapping

**Endpoint:**
```
GET /api/data/import/mappings/{mapping_id}
```

**Response:**
```json
{
  "id": 42,
  "name": "My Goodreads Export",
  "schema_fingerprint": "abc123...",
  "mapping": {
    "Title": "title",
    "Author": "author"
  },
  "created_at": "2024-05-18T12:00:00Z",
  "updated_at": "2024-05-18T12:00:00Z"
}
```

#### Delete Mapping

**Endpoint:**
```
DELETE /api/data/import/mappings/{mapping_id}
```

**Response:** 204 No Content

#### Validate (Simulate)

**Endpoint:**
```
POST /api/data/import/validate
```

**Request:**
```json
{
  "file_id": "temp-abc123",
  "mapping": {
    "Title": "title",
    "Author": "author",
    "ISBN": "isbn",
    "MyRating": "rating",
    "DateRead": "date_finished"
  }
}
```

**Response (Success):**
```json
{
  "valid": true,
  "row_count": 127,
  "warnings": [
    "Row 23: Missing required field 'title' — row will be skipped",
    "Row 45: Invalid rating value '10' (must be 1-5) — will be set to null"
  ]
}
```

**Response (Errors):**
```json
{
  "valid": false,
  "errors": [
    "Mapping missing required field: 'title'",
    "Row 12: ISBN '123' already exists for book ID 456"
  ],
  "row_count": 127
}
```

**Validation Rules:**
- **Required**: `title` must be mapped and non-empty in every row
- **Data types**: `published_year`, `page_count`, `rating` must be integers if present
- **Value ranges**: `rating` ∈ [1, 5], `language` must be 2-letter code
- **Uniqueness**: `isbn` must not conflict with existing user books (warning, not error)
- **Dates**: `date_started`, `date_finished` must be valid ISO datetimes, not in future, started ≤ finished

#### Import (Execute)

**Endpoint:**
```
POST /api/data/import/execute
```

**Request:**
```json
{
  "file_id": "temp-abc123",
  "mapping": {
    "Title": "title",
    "Author": "author"
  },
  "import_mode": "rollback_all",  // "rollback_all" | "continue_on_error"
  "download_covers": true
}
```

**Response (SSE stream):**

```
data: {"event": "start", "total_rows": 127}

data: {"event": "progress", "processed": 10, "total": 127, "percent": 7.9}

data: {"event": "progress", "processed": 50, "total": 127, "percent": 39.4}

data: {"event": "complete", "imported": 125, "failed": 2, "duration_seconds": 8.3, "failures": [
  {"row": 23, "data": {"Title": "Bad Book"}, "error": "Missing required field: title"},
  {"row": 45, "data": {"Title": "Another", "ISBN": "123"}, "error": "ISBN conflict with existing book ID 456"}
]}
```

**On Error (rollback_all mode):**
```
data: {"event": "error", "message": "Import failed: Row 23 missing required field 'title'. All changes rolled back."}
```

### 1.4 Security

- **Authentication**: All endpoints require `Depends(require_user)`
- **CSRF**: All POST/DELETE endpoints validate CSRF token (already enforced by middleware)
- **File Upload**:
  - Content-Type validation: only `text/csv`, `application/json`, `application/zip` accepted
  - File size limit: 100 MB (configurable via `settings.max_import_file_size_mb`)
  - Row count limit: 10,000 rows (configurable via `settings.max_import_row_count`)
  - Temporary file storage in isolated per-user directories (`data/import_temp/{user_id}/`)
  - Path traversal prevention: validate filenames with `safe_filename()` pattern from `cover_storage.py`
- **Cover Downloads**:
  - Reuse existing `download_cover()` function which validates content-type, file size, and writes atomically
  - Timeout: 15 seconds per cover (already enforced in `download_cover()`)
  - Limit parallel downloads: process covers sequentially to avoid resource exhaustion
- **Data Isolation**: All queries filtered by `user_id` — users can only export/import their own data
- **Mapping Storage**: Mappings belong to user — no cross-user access

### 1.5 Performance Constraints

**Export:**
- Synchronous export for up to 10,000 books + 5,000 progress entries + 1 GB covers (< 10s)
- Streaming ZIP generation using `zipfile` with `ZipFile(mode='w', compression=ZIP_DEFLATED)`
- Memory-efficient: read covers from disk and stream into ZIP without loading all into memory

**Import:**
- Async import with SSE progress for responsive UI
- Database transaction per batch (100 rows) to balance atomicity and performance
- Covers downloaded during import step (not simulate) to avoid double work
- Temporary file cleanup: background task deletes files older than 24 hours on startup and every 6 hours

**Limits (first iteration):**
- Max file size: 100 MB
- Max row count: 10,000 rows
- Max CSV field length: 10,000 characters (prevent abuse)
- Timeout: 5 minutes for entire import operation

### 1.6 Validation & Error Model

**Validation Levels:**

1. **Parse-time**: File format, encoding, size, row count
2. **Mapping-time**: Required field presence in mapping
3. **Row-level**: Required fields, data types, value ranges, date logic
4. **Database-level**: Uniqueness constraints (ISBN conflicts)

**Error Response Format:**
```json
{
  "valid": false,
  "errors": [
    {
      "row": 23,
      "field": "title",
      "message": "Required field missing",
      "value": null
    }
  ]
}
```

**Partial Failure (continue_on_error mode):**
```json
{
  "event": "complete",
  "imported": 125,
  "failed": 2,
  "failures": [
    {
      "row": 23,
      "data": {"Title": "Bad Book"},
      "error": "Missing required field: title"
    },
    {
      "row": 45,
      "data": {"Title": "Duplicate ISBN", "ISBN": "123"},
      "error": "ISBN '123' already exists for book ID 456"
    }
  ]
}
```

---

## 2. Database Changes

### 2.1 New Table: `import_mapping`

**Schema:**
```python
class ImportMapping(SQLModel, table=True):
    __tablename__ = "import_mapping"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=255)
    schema_fingerprint: str = Field(max_length=64, index=True)
    mapping: str  # JSON string: {"source_field": "db_field"}
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(UtcDateTime, default=_utcnow)
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(UtcDateTime, default=_utcnow)
    )
```

**Migration:**
- No data migration needed (new table)
- Auto-created via SQLModel on first run

---

## 3. Files to Create

### Backend

| File | Purpose |
|---|---|
| `backend/app/routers/data.py` | New router with all data import/export endpoints |
| `backend/app/services/data_export.py` | Export logic (build ZIP, serialize data) |
| `backend/app/services/data_import.py` | Import logic (parse, validate, persist) |
| `backend/app/schemas.py` (additions) | Pydantic models for import/export request/response |

### Frontend

| File | Purpose |
|---|---|
| `frontend/src/routes/data/+page.svelte` | Main data management page with Import/Export tabs |
| `frontend/src/lib/components/DataExport.svelte` | Export tab UI (dataset selection, format, download) |
| `frontend/src/lib/components/DataImport.svelte` | Import tab UI (upload, mapping, simulate, execute) |
| `frontend/src/lib/components/ImportMappingEditor.svelte` | Field mapping UI (source → target dropdowns) |
| `frontend/src/lib/types.ts` (additions) | TypeScript types for import/export |
| `frontend/src/lib/api.ts` (additions) | API client methods for data endpoints |

---

## 4. Files to Modify

### Backend

| File | Change |
|---|---|
| `backend/app/main.py` | Add `app.include_router(data.router)` |
| `backend/app/models.py` | Add `ImportMapping` model |
| `backend/app/schemas.py` | Add import/export schemas |
| `backend/app/config.py` | Add `max_import_file_size_mb: int = 100`, `max_import_row_count: int = 10000`, `import_temp_dir: str = "./data/import_temp"` |

### Frontend

| File | Change |
|---|---|
| `frontend/src/lib/components/AddBookModal.svelte` | Add link to `/data?tab=import` in import tab (looks like third tab) |
| `frontend/src/routes/profile/+page.svelte` | Add "Manage my data" section with link to `/data?tab=export` |
| `frontend/src/lib/i18n/locales/en.json` | Add i18n keys for data page, import/export UI, errors |
| `frontend/src/lib/i18n/locales/de.json` | Add German translations |
| `frontend/src/lib/api.ts` | Add `api.data.*` methods |
| `frontend/src/lib/types.ts` | Add import/export types |

---

## 5. Detailed Implementation Steps

### Phase 1: Backend — Export (Days 1-2)

#### Step 1.1: Add Configuration

**File:** `backend/app/config.py`

```python
# Add to Settings class
max_import_file_size_mb: int = 100
max_import_row_count: int = 10000
import_temp_dir: str = "./data/import_temp"
```

#### Step 1.2: Add Export Schemas

**File:** `backend/app/schemas.py`

```python
from typing import Literal

class DataExportRequest(SQLModel):
    datasets: List[Literal["books", "covers", "progress", "tags"]]
    format: Literal["csv", "json"]

class ExportManifest(SQLModel):
    export_timestamp: datetime
    app_version: str
    user_id: int
    user_email: str
    datasets: List[str]
    format: str
    counts: dict[str, int]
```

#### Step 1.3: Create Export Service

**File:** `backend/app/services/data_export.py`

```python
"""Data export service — generates ZIP archives with user data."""

import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal
from zipfile import ZipFile, ZIP_DEFLATED

from sqlmodel import Session, select

from app.models import Book, ReadingProgress, Tag, BookTag, User
from app.services.cover_storage import resolve_cover_path
from app.schemas import ExportManifest

logger = logging.getLogger(__name__)


def export_user_data(
    session: Session,
    user: User,
    datasets: List[Literal["books", "covers", "progress", "tags"]],
    format: Literal["csv", "json"],
    covers_dir: str,
) -> bytes:
    """
    Generate a ZIP archive containing the requested user data.
    
    Returns:
        Binary ZIP file content.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    counts = {}
    
    # Create in-memory ZIP
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, mode='w', compression=ZIP_DEFLATED) as zipf:
        # Export books
        if "books" in datasets:
            books = session.exec(
                select(Book).where(Book.user_id == user.id)
            ).all()
            counts["books"] = len(books)
            
            if format == "json":
                books_data = [_book_to_dict(b) for b in books]
                zipf.writestr("books.json", json.dumps(books_data, indent=2, default=str))
            else:  # csv
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=_BOOK_CSV_FIELDS)
                writer.writeheader()
                for book in books:
                    writer.writerow(_book_to_dict(book))
                zipf.writestr("books.csv", output.getvalue())
        
        # Export covers
        if "covers" in datasets and "books" in datasets:
            books = session.exec(
                select(Book).where(Book.user_id == user.id)
            ).all()
            cover_count = 0
            for book in books:
                if book.cover_url and book.cover_url.startswith("/api/covers/"):
                    filename = book.cover_url.replace("/api/covers/", "")
                    cover_path = resolve_cover_path(covers_dir, filename)
                    if cover_path and cover_path.exists():
                        zipf.write(cover_path, f"covers/{filename}")
                        cover_count += 1
            counts["covers"] = cover_count
        
        # Export progress
        if "progress" in datasets:
            progress_entries = session.exec(
                select(ReadingProgress).where(ReadingProgress.user_id == user.id)
            ).all()
            counts["progress_entries"] = len(progress_entries)
            
            if format == "json":
                progress_data = [_progress_to_dict(p) for p in progress_entries]
                zipf.writestr("progress.json", json.dumps(progress_data, indent=2, default=str))
            else:  # csv
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=_PROGRESS_CSV_FIELDS)
                writer.writeheader()
                for p in progress_entries:
                    writer.writerow(_progress_to_dict(p))
                zipf.writestr("progress.csv", output.getvalue())
        
        # Export tags
        if "tags" in datasets:
            tags = session.exec(
                select(Tag).where(Tag.user_id == user.id)
            ).all()
            counts["tags"] = len(tags)
            
            if format == "json":
                tags_data = [_tag_to_dict(t) for t in tags]
                zipf.writestr("tags.json", json.dumps(tags_data, indent=2, default=str))
            else:  # csv
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=_TAG_CSV_FIELDS)
                writer.writeheader()
                for tag in tags:
                    writer.writerow(_tag_to_dict(tag))
                zipf.writestr("tags.csv", output.getvalue())
        
        # Add manifest
        manifest = ExportManifest(
            export_timestamp=datetime.now(timezone.utc),
            app_version="0.1.0",  # TODO: read from version.py
            user_id=user.id,
            user_email=user.email,
            datasets=datasets,
            format=format,
            counts=counts,
        )
        zipf.writestr("manifest.json", json.dumps(manifest.model_dump(mode="json"), indent=2, default=str))
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


_BOOK_CSV_FIELDS = [
    "title", "author", "isbn", "publisher", "published_year", "page_count",
    "language", "tags", "notes", "rating", "reading_status",
    "date_added", "date_started", "date_finished", "cover_url"
]

_PROGRESS_CSV_FIELDS = ["book_id", "page", "created_at", "updated_at"]

_TAG_CSV_FIELDS = ["tag_id", "name", "created_at"]


def _book_to_dict(book: Book) -> dict:
    return {
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "publisher": book.publisher,
        "published_year": book.published_year,
        "page_count": book.page_count,
        "language": book.language,
        "tags": book.tags,
        "notes": book.notes,
        "rating": book.rating,
        "reading_status": book.reading_status.value,
        "date_added": book.date_added.isoformat() if book.date_added else None,
        "date_started": book.date_started.isoformat() if book.date_started else None,
        "date_finished": book.date_finished.isoformat() if book.date_finished else None,
        "cover_url": book.cover_url,
    }


def _progress_to_dict(progress: ReadingProgress) -> dict:
    return {
        "book_id": progress.book_id,
        "page": progress.page,
        "created_at": progress.created_at.isoformat() if progress.created_at else None,
        "updated_at": progress.updated_at.isoformat() if progress.updated_at else None,
    }


def _tag_to_dict(tag: Tag) -> dict:
    return {
        "tag_id": tag.id,
        "name": tag.name,
        "created_at": tag.created_at.isoformat() if tag.created_at else None,
    }
```

#### Step 1.4: Create Export Router

**File:** `backend/app/routers/data.py`

```python
"""Data import/export endpoints."""

import logging
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session

from app.auth import require_user
from app.config import settings
from app.database import get_session
from app.models import User
from app.schemas import DataExportRequest
from app.services.data_export import export_user_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/export")
async def export_data(
    body: DataExportRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    """Export user data as a ZIP archive."""
    if not body.datasets:
        raise HTTPException(status_code=400, detail="No datasets selected")
    
    if body.format not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="Invalid format")
    
    logger.info("Exporting data for user %s — datasets=%s format=%s", 
                current_user.id, body.datasets, body.format)
    
    zip_bytes = export_user_data(
        session=session,
        user=current_user,
        datasets=body.datasets,
        format=body.format,
        covers_dir=settings.covers_dir,
    )
    
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    filename = f"librislog-export-{timestamp}.zip"
    
    logger.info("Export complete for user %s — size=%d bytes", current_user.id, len(zip_bytes))
    
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
```

#### Step 1.5: Register Router

**File:** `backend/app/main.py`

```python
# Add import
from app.routers import auth, books, covers, data, docs, health, import_, oidc, profile, progress, statistics, users

# Add router
app.include_router(data.router)
```

---

### Phase 2: Frontend — Export (Days 2-3)

#### Step 2.1: Add Export Types

**File:** `frontend/src/lib/types.ts`

```typescript
export type ExportDataset = 'books' | 'covers' | 'progress' | 'tags';
export type ExportFormat = 'csv' | 'json';

export interface DataExportRequest {
  datasets: ExportDataset[];
  format: ExportFormat;
}
```

#### Step 2.2: Add Export API Methods

**File:** `frontend/src/lib/api.ts`

```typescript
// Add to api object
data: {
  async exportData(request: DataExportRequest): Promise<Blob> {
    const res = await fetch(`${BASE}/data/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        'X-CSRF-Token': get(csrfToken) || ''
      },
      credentials: 'same-origin',
      body: JSON.stringify(request)
    });
    
    if (!res.ok) {
      throw new Error(`Export failed: ${res.status}`);
    }
    
    return res.blob();
  }
}
```

#### Step 2.3: Create Export Component

**File:** `frontend/src/lib/components/DataExport.svelte`

```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import { _ } from '$lib/i18n';
  import { toasts } from '$lib/toasts';
  import type { ExportDataset, ExportFormat } from '$lib/types';

  let selectedDatasets = $state<ExportDataset[]>(['books']);
  let format = $state<ExportFormat>('json');
  let exporting = $state(false);

  const datasetOptions: { value: ExportDataset; label: string }[] = [
    { value: 'books', label: 'export.dataset.books' },
    { value: 'covers', label: 'export.dataset.covers' },
    { value: 'progress', label: 'export.dataset.progress' },
    { value: 'tags', label: 'export.dataset.tags' }
  ];

  function toggleDataset(dataset: ExportDataset) {
    if (selectedDatasets.includes(dataset)) {
      selectedDatasets = selectedDatasets.filter(d => d !== dataset);
    } else {
      selectedDatasets = [...selectedDatasets, dataset];
    }
  }

  async function handleExport() {
    if (selectedDatasets.length === 0) {
      toasts.error($_('export.error.noDatasets'));
      return;
    }

    exporting = true;
    try {
      const blob = await api.data.exportData({
        datasets: selectedDatasets,
        format
      });

      // Trigger download
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `librislog-export-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toasts.success($_('export.success'));
    } catch (err) {
      console.error(err);
      toasts.error($_('export.error.failed'));
    } finally {
      exporting = false;
    }
  }
</script>

<div class="max-w-2xl">
  <h2 class="text-2xl font-bold mb-4">{$_('export.title')}</h2>
  <p class="text-gray-600 dark:text-gray-400 mb-6">{$_('export.description')}</p>

  <div class="space-y-6">
    <!-- Dataset Selection -->
    <div>
      <h3 class="text-lg font-semibold mb-3">{$_('export.selectDatasets')}</h3>
      <div class="space-y-2">
        {#each datasetOptions as option}
          <label class="flex items-center space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={selectedDatasets.includes(option.value)}
              onchange={() => toggleDataset(option.value)}
              class="w-4 h-4"
            />
            <span>{$_(option.label)}</span>
          </label>
        {/each}
      </div>
    </div>

    <!-- Format Selection -->
    <div>
      <h3 class="text-lg font-semibold mb-3">{$_('export.selectFormat')}</h3>
      <div class="space-y-2">
        <label class="flex items-center space-x-3 cursor-pointer">
          <input type="radio" bind:group={format} value="json" class="w-4 h-4" />
          <span>JSON</span>
        </label>
        <label class="flex items-center space-x-3 cursor-pointer">
          <input type="radio" bind:group={format} value="csv" class="w-4 h-4" />
          <span>CSV</span>
        </label>
      </div>
    </div>

    <!-- Export Button -->
    <button
      onclick={handleExport}
      disabled={exporting || selectedDatasets.length === 0}
      class="btn btn-primary"
    >
      {exporting ? $_('export.exporting') : $_('export.button')}
    </button>
  </div>
</div>
```

#### Step 2.4: Create Data Page

**File:** `frontend/src/routes/data/+page.svelte`

```svelte
<script lang="ts">
  import { page } from '$app/stores';
  import { _ } from '$lib/i18n';
  import DataExport from '$lib/components/DataExport.svelte';
  import DataImport from '$lib/components/DataImport.svelte';

  const activeTab = $derived(($page.url.searchParams.get('tab') || 'export') as 'export' | 'import');

  function setTab(tab: 'export' | 'import') {
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    window.history.pushState({}, '', url);
  }
</script>

<svelte:head>
  <title>{$_('data.title')} — LibrisLog</title>
</svelte:head>

<div class="container mx-auto px-4 py-8">
  <h1 class="text-3xl font-bold mb-6">{$_('data.title')}</h1>

  <!-- Tabs -->
  <div class="border-b border-gray-300 dark:border-gray-700 mb-6">
    <nav class="flex space-x-8">
      <button
        onclick={() => setTab('export')}
        class="py-3 px-1 border-b-2 transition-colors {activeTab === 'export' 
          ? 'border-blue-500 text-blue-600 dark:text-blue-400 font-medium' 
          : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'}"
      >
        {$_('data.tabs.export')}
      </button>
      <button
        onclick={() => setTab('import')}
        class="py-3 px-1 border-b-2 transition-colors {activeTab === 'import' 
          ? 'border-blue-500 text-blue-600 dark:text-blue-400 font-medium' 
          : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'}"
      >
        {$_('data.tabs.import')}
      </button>
    </nav>
  </div>

  <!-- Tab Content -->
  <div>
    {#if activeTab === 'export'}
      <DataExport />
    {:else}
      <DataImport />
    {/if}
  </div>
</div>
```

#### Step 2.5: Add Link from Profile Page

**File:** `frontend/src/routes/profile/+page.svelte`

Add new section after API Keys section (around line 400):

```svelte
<!-- Data Management -->
<section id="section-data" class="scroll-mt-32">
  <h2 class="text-2xl font-semibold mb-4">{$_('profile.dataManagement.title')}</h2>
  <p class="text-gray-700 dark:text-gray-300 mb-4">{$_('profile.dataManagement.description')}</p>
  <a href="/data?tab=export" class="btn btn-secondary">
    {$_('profile.dataManagement.linkExport')}
  </a>
</section>
```

Add anchor link in nav (around line 250):

```svelte
<li>
  <a
    href="#section-data"
    class="block py-2 px-4 rounded transition-colors {activeSection === 'section-data'
      ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 font-medium'
      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'}"
  >
    {$_('profile.nav.dataManagement')}
  </a>
</li>
```

#### Step 2.6: Add Link from Add Book Dialog

**File:** `frontend/src/lib/components/AddBookModal.svelte`

Add link below the Import tab (around line 100):

```svelte
<div class="mt-4 text-center">
  <a href="/data?tab=import" class="text-blue-600 dark:text-blue-400 hover:underline text-sm">
    {$_('addBook.importFromFile')}
  </a>
</div>
```

#### Step 2.7: Add i18n Keys

**File:** `frontend/src/lib/i18n/locales/en.json`

```json
{
  "data": {
    "title": "Data Management",
    "tabs": {
      "export": "Export",
      "import": "Import"
    }
  },
  "export": {
    "title": "Export Your Library",
    "description": "Download your books, reading progress, and covers as a backup or for migration.",
    "selectDatasets": "Select data to export",
    "selectFormat": "Choose format",
    "dataset": {
      "books": "Books (titles, authors, metadata)",
      "covers": "Cover images",
      "progress": "Reading progress entries",
      "tags": "Tags"
    },
    "button": "Export Data",
    "exporting": "Exporting...",
    "success": "Export completed! Download started.",
    "error": {
      "noDatasets": "Please select at least one dataset to export",
      "failed": "Export failed. Please try again."
    }
  },
  "profile": {
    "dataManagement": {
      "title": "Manage My Data",
      "description": "Export your library data or import books from a file.",
      "linkExport": "Go to Data Management"
    },
    "nav": {
      "dataManagement": "Data Management"
    }
  },
  "addBook": {
    "importFromFile": "Or import multiple books from a file →"
  }
}
```

---

### Phase 3: Backend — Import (Days 4-6)

#### Step 3.1: Add Import Models

**File:** `backend/app/models.py`

```python
class ImportMapping(SQLModel, table=True):
    __tablename__ = "import_mapping"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=255)
    schema_fingerprint: str = Field(max_length=64, index=True)
    mapping: str  # JSON string
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(UtcDateTime, default=_utcnow)
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(UtcDateTime, default=_utcnow)
    )
```

#### Step 3.2: Add Import Schemas

**File:** `backend/app/schemas.py`

```python
class ImportFileParseResponse(SQLModel):
    file_id: str
    format: Literal["csv", "json"]
    is_zip: bool
    has_covers: bool
    source_fields: List[str]
    sample_rows: List[dict]
    row_count: int


class ImportMappingSuggestion(SQLModel):
    suggested_mapping: dict[str, str]
    db_fields: List[str]


class ImportMappingSave(SQLModel):
    name: str
    schema_fingerprint: str
    mapping: dict[str, str]


class ImportMappingRead(SQLModel):
    id: int
    name: str
    schema_fingerprint: str
    mapping: dict[str, str]
    created_at: datetime
    updated_at: datetime


class ImportMappingListItem(SQLModel):
    id: int
    name: str
    schema_fingerprint: str
    created_at: datetime
    updated_at: datetime


class ImportValidateRequest(SQLModel):
    file_id: str
    mapping: dict[str, str]


class ImportValidateResponse(SQLModel):
    valid: bool
    row_count: int
    warnings: List[str] = []
    errors: List[str] = []


class ImportExecuteRequest(SQLModel):
    file_id: str
    mapping: dict[str, str]
    import_mode: Literal["rollback_all", "continue_on_error"] = "rollback_all"
    download_covers: bool = True
```

#### Step 3.3: Create Import Service

**File:** `backend/app/services/data_import.py`

(This is a large file; outline the key functions)

```python
"""Data import service — parse, validate, and persist user-uploaded data."""

import csv
import hashlib
import io
import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, List, Literal
from zipfile import ZipFile

import httpx
from sqlmodel import Session, select

from app.config import settings
from app.models import Book, ReadingStatus, User
from app.schemas import ImportFileParseResponse
from app.services.cover_storage import download_cover, save_uploaded_cover

logger = logging.getLogger(__name__)


async def parse_upload(
    file_content: bytes,
    filename: str,
    user_id: int,
) -> ImportFileParseResponse:
    """
    Parse uploaded file and return structure analysis.
    
    Supports CSV, JSON, and ZIP (with books.csv/json + optional covers/).
    """
    # Implementation: detect format, parse rows, extract fields, save to temp storage
    ...


def suggest_mapping(source_fields: List[str]) -> dict[str, str]:
    """
    Suggest db field mappings for source fields using fuzzy matching.
    
    Examples:
      "Title" → "title"
      "Book Title" → "title"
      "Author Name" → "author"
      "Pages" → "page_count"
      "Year Published" → "published_year"
      "My Rating" → "rating"
      "Date Read" → "date_finished"
    """
    # Implementation: case-insensitive matching + alias dictionary
    ...


def compute_schema_fingerprint(source_fields: List[str]) -> str:
    """Compute SHA-256 hash of sorted source field names."""
    sorted_fields = sorted(source_fields)
    payload = json.dumps(sorted_fields)
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_import(
    file_id: str,
    mapping: dict[str, str],
    user_id: int,
    session: Session,
) -> dict:
    """
    Validate import data without persisting.
    
    Returns:
      {
        "valid": bool,
        "row_count": int,
        "warnings": List[str],
        "errors": List[str]
      }
    """
    # Implementation: load temp file, apply mapping, validate each row
    ...


async def execute_import(
    file_id: str,
    mapping: dict[str, str],
    import_mode: Literal["rollback_all", "continue_on_error"],
    download_covers: bool,
    user_id: int,
    session: Session,
) -> AsyncGenerator[dict, None]:
    """
    Execute import and stream progress via SSE.
    
    Yields:
      {"event": "start", "total_rows": N}
      {"event": "progress", "processed": X, "total": N, "percent": P}
      {"event": "complete", "imported": X, "failed": Y, "failures": [...]}
      {"event": "error", "message": "..."}
    """
    # Implementation: load temp file, apply mapping, batch insert with progress events
    ...


def cleanup_temp_files(max_age_hours: int = 24):
    """Delete temporary import files older than max_age_hours."""
    # Implementation: scan import_temp_dir, delete old files
    ...
```

#### Step 3.4: Add Import Endpoints to Router

**File:** `backend/app/routers/data.py`

Add endpoints:

```python
@router.post("/import/parse", response_model=ImportFileParseResponse)
async def parse_import_file(...): ...

@router.post("/import/suggest-mapping", response_model=ImportMappingSuggestion)
async def suggest_import_mapping(...): ...

@router.post("/import/mappings", response_model=ImportMappingRead, status_code=201)
async def save_import_mapping(...): ...

@router.get("/import/mappings", response_model=List[ImportMappingListItem])
async def list_import_mappings(...): ...

@router.get("/import/mappings/{mapping_id}", response_model=ImportMappingRead)
async def get_import_mapping(...): ...

@router.delete("/import/mappings/{mapping_id}", status_code=204)
async def delete_import_mapping(...): ...

@router.post("/import/validate", response_model=ImportValidateResponse)
async def validate_import_data(...): ...

@router.post("/import/execute")
async def execute_import(...) -> StreamingResponse:
    """SSE endpoint for import execution."""
    ...
```

#### Step 3.5: Add Cleanup Background Task

**File:** `backend/app/main.py`

```python
from app.services.data_import import cleanup_temp_files

@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.covers_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.import_temp_dir).mkdir(parents=True, exist_ok=True)
    
    # Cleanup old temp files on startup
    cleanup_temp_files()
    
    yield
```

---

### Phase 4: Frontend — Import (Days 7-9)

#### Step 4.1: Create Import Component Stub

**File:** `frontend/src/lib/components/DataImport.svelte`

```svelte
<script lang="ts">
  import { _ } from '$lib/i18n';

  let step = $state<'upload' | 'mapping' | 'validate' | 'execute'>('upload');
</script>

<div class="max-w-4xl">
  <h2 class="text-2xl font-bold mb-4">{$_('import.title')}</h2>
  <p class="text-gray-600 dark:text-gray-400 mb-6">{$_('import.description')}</p>

  {#if step === 'upload'}
    <!-- File upload UI -->
  {:else if step === 'mapping'}
    <!-- Mapping editor -->
  {:else if step === 'validate'}
    <!-- Validation results -->
  {:else}
    <!-- Import progress -->
  {/if}
</div>
```

(Full implementation with file upload, mapping editor, validation display, progress bar)

#### Step 4.2: Create Mapping Editor Component

**File:** `frontend/src/lib/components/ImportMappingEditor.svelte`

```svelte
<script lang="ts">
  type MappingEditorProps = {
    sourceFields: string[];
    dbFields: string[];
    mapping: Record<string, string>;
    onMappingChange: (mapping: Record<string, string>) => void;
  };

  let { sourceFields, dbFields, mapping, onMappingChange }: MappingEditorProps = $props();

  function updateMapping(sourceField: string, dbField: string) {
    const newMapping = { ...mapping };
    if (dbField === '') {
      delete newMapping[sourceField];
    } else {
      newMapping[sourceField] = dbField;
    }
    onMappingChange(newMapping);
  }
</script>

<div class="space-y-3">
  {#each sourceFields as sourceField}
    <div class="flex items-center space-x-4">
      <div class="flex-1 font-medium text-sm">{sourceField}</div>
      <div class="text-gray-500">→</div>
      <select
        value={mapping[sourceField] || ''}
        onchange={(e) => updateMapping(sourceField, e.currentTarget.value)}
        class="flex-1 border border-gray-300 dark:border-gray-700 rounded px-3 py-2"
      >
        <option value="">{$_('import.mapping.skip')}</option>
        {#each dbFields as dbField}
          <option value={dbField}>{dbField}</option>
        {/each}
      </select>
    </div>
  {/each}
</div>
```

#### Step 4.3: Add Import i18n

**File:** `frontend/src/lib/i18n/locales/en.json`

```json
{
  "import": {
    "title": "Import Books",
    "description": "Upload a CSV or JSON file to bulk-import books into your library.",
    "upload": {
      "title": "Upload File",
      "dragDrop": "Drag and drop a file here, or click to browse",
      "fileSelected": "File: {filename} ({size})",
      "button": "Parse File"
    },
    "mapping": {
      "title": "Map Fields",
      "description": "Match your file's columns to LibrisLog fields.",
      "skip": "(Skip field)",
      "save": "Save Mapping",
      "load": "Load Saved Mapping",
      "button": "Continue to Validation"
    },
    "validate": {
      "title": "Validation Results",
      "valid": "All rows are valid! Ready to import.",
      "invalid": "Some rows have errors. Please fix your file and re-upload.",
      "warnings": "Warnings",
      "errors": "Errors",
      "button": "Simulate Import"
    },
    "execute": {
      "title": "Import Progress",
      "importing": "Importing {processed} of {total} books...",
      "complete": "Import complete! Imported {imported} books.",
      "failed": "Import failed: {error}",
      "mode": {
        "rollback_all": "Rollback all on error",
        "continue_on_error": "Continue on error"
      }
    }
  }
}
```

---

## 6. Testing Strategy

### Backend Unit Tests

**File:** `backend/tests/test_data_export.py`

- Test export with different dataset combinations
- Test CSV vs JSON format
- Test cover inclusion in ZIP
- Test manifest generation
- Test empty library export

**File:** `backend/tests/test_data_import.py`

- Test CSV/JSON/ZIP parsing
- Test field mapping suggestions
- Test schema fingerprint computation
- Test validation (required fields, data types, duplicates)
- Test import execution (rollback_all vs continue_on_error)
- Test cover download during import
- Test temp file cleanup

### Backend Integration Tests

**File:** `backend/tests/test_data_router.py`

- Test export endpoint (authenticated)
- Test import parse endpoint (file upload)
- Test mapping save/load/delete
- Test validate endpoint
- Test execute endpoint (SSE stream)
- Test auth enforcement (require_user)
- Test CSRF token validation

### Frontend Component Tests

- DataExport.svelte: dataset selection, format selection, download trigger
- DataImport.svelte: step navigation, file upload, mapping UI
- ImportMappingEditor.svelte: field mapping, save/load mappings

### Playwright E2E Tests

**File:** `playwright/data-export.spec.ts`

- Navigate to /data, switch to Export tab
- Select datasets, choose format, trigger export, verify download

**File:** `playwright/data-import.spec.ts`

- Upload CSV file
- Map fields
- Validate
- Execute import
- Verify books appear in library

---

## 7. Rollout Plan

### Phase 1: Export (Week 1)
- Backend export service + endpoint
- Frontend export UI + data page
- Add links from profile page
- Test export with sample data

### Phase 2: Import Parse & Mapping (Week 2)
- Backend parse + mapping endpoints
- Frontend upload + mapping UI
- Test CSV/JSON parsing
- Test mapping suggestions

### Phase 3: Import Validation & Execution (Week 3)
- Backend validate + execute endpoints
- Frontend validation display + progress UI
- Test import execution
- Test error handling

### Phase 4: Polish & Docs (Week 4)
- Add German translations
- Write user documentation
- Add tooltips and help text
- Performance testing (10k rows)
- Security review

---

## 8. Future Enhancements (Out of Scope for v1)

- **Export Progress (SSE)**: For very large libraries (10k+ books)
- **Import Preview**: Show first 10 imported books before confirming
- **Scheduled Exports**: Auto-export weekly to cloud storage
- **Import from URL**: Import directly from a CSV/JSON URL
- **Advanced Mapping**: Transform functions (e.g., split author string, parse dates)
- **Duplicate Detection**: Fuzzy matching on title+author to detect near-duplicates
- **Multi-file Import**: Upload multiple CSVs in one session
- **Export Filters**: Export only books with specific tags/statuses
- **Import Undo**: Rollback last import operation

---

## 9. Open Questions & Assumptions

### Assumptions

1. **File Size**: 100 MB limit is sufficient for 99% of users (≈10k books with covers)
2. **Format Support**: CSV and JSON cover most export formats (Goodreads, Calibre, etc.)
3. **Cover Download**: Sequential download is acceptable (parallel would complicate error handling)
4. **Temp File Cleanup**: 24-hour retention is sufficient for users to complete imports
5. **Mapping Persistence**: Per-user storage is sufficient (no cross-user sharing needed)

### Open Questions

1. **Should we support Excel (.xlsx) import?**
   - Pro: Popular export format
   - Con: Requires additional dependency (`openpyxl` or `pandas`)
   - **Decision**: Not in v1. Users can convert to CSV.

2. **Should we validate ISBN format (checksums)?**
   - Pro: Catch data entry errors
   - Con: Many ISBNs in the wild have invalid checksums
   - **Decision**: No checksum validation. ISBN is just a string identifier.

3. **Should we support partial exports (e.g., only read books)?**
   - Pro: Useful for sharing reading lists
   - Con: Adds UI complexity
   - **Decision**: Not in v1. Export all, filter externally if needed.

4. **Should we deduplicate covers in export ZIP?**
   - Pro: Smaller ZIP size if same cover used for multiple books
   - Con: Complicates import (need to track cover reuse)
   - **Decision**: Not in v1. Each book's cover exported separately.

---

## 10. Success Metrics

- **Export Adoption**: 30% of users export data within first month
- **Import Success Rate**: >95% of imports complete without errors
- **Performance**: Export completes in <10s for 1000 books
- **Performance**: Import completes in <30s for 500 books
- **Support Tickets**: <5% of users report issues with import/export

---

**Plan Status:** Ready for implementation  
**Estimated Effort:** 3-4 weeks (1 backend dev + 1 frontend dev)  
**Priority:** Medium (valuable feature, not blocking other work)  
**Dependencies:** None (all required infrastructure exists)
