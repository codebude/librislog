# Implementation Plan: Reading Progress Tracker

## Goal

Add a reading progress tracking system that allows users to log their current page for books, view progress on book cards, interact with a slider/input in the detail view, see a progress-over-time graph, and manage individual log entries.

---

## 1) Database Model + Migration

### 1.1 New SQLModel

File: `backend/app/models.py`

```python
class ReadingProgress(SQLModel, table=True):
    __tablename__ = "reading_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    page: int = Field(ge=0)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
```

- Append-only log: each change creates a new row.
- `page` is the current page reached (cumulative).
- Foreign keys to `book` (with `ondelete="CASCADE"`) and `user`.
- Index on `(book_id, created_at DESC)` for efficient "latest per book" queries.

### 1.2 Alembic Migration

Generate a new Alembic revision:

```
$ cd backend && alembic revision --autogenerate -m "add reading_progress table"
```

Then hand-edit the migration to add `ondelete="CASCADE"` on the `book_id` FK, since SQLModel's `Field(foreign_key=...)` doesn't express `ON DELETE CASCADE` natively. The upgrade should look like:

```python
def upgrade() -> None:
    op.create_table(
        "reading_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["book.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reading_progress_book_id", "reading_progress", ["book_id"])
    op.create_index("ix_reading_progress_user_id", "reading_progress", ["user_id"])
```

---

## 2) Backend Endpoints

### 2.1 New Schema (Pydantic/SQLModel)

File: `backend/app/schemas.py`

```python
class ReadingProgressCreate(SQLModel):
    page: int = Field(ge=0)

class ReadingProgressRead(SQLModel):
    id: int
    book_id: int
    page: int
    created_at: datetime
    updated_at: datetime

class ReadingProgressLatest(SQLModel):
    """Latest progress for a single book (used in batch card rendering)."""
    book_id: int
    current_page: int
```

### 2.2 New Router

File: `backend/app/routers/progress.py` (new file, registered in `main.py`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/books/{book_id}/progress` | Create a new progress entry (append). Validates book ownership, `page` ≤ `book.page_count` (if set). Returns `ReadingProgressRead`. |
| `GET` | `/api/books/{book_id}/progress` | List all progress entries for a book, ordered by `created_at DESC`. Returns `List[ReadingProgressRead]`. |
| `DELETE` | `/api/books/{book_id}/progress/{entry_id}` | Delete a single progress entry. Validates ownership. Status 204. |
| `GET` | `/api/books/progress/latest` | Batch endpoint for card rendering. Accepts query param `book_ids=1,2,3...`. Returns `List[ReadingProgressLatest]` — the latest page per book. |

**Design notes:**

- The `POST` endpoint merges duplicate dates: if a progress entry already exists for the same `(book_id, date)` (using `created_at` date only), update it in-place rather than appending a new row. This matches the "one entry per day" UX expectation. Alternative: always append (pure log). The requirement says "append-only log", so we always create new rows — the graph deduplication happens at query/render time.
- The latest-progress-per-book batch endpoint uses a subquery with `ROW_NUMBER() OVER (PARTITION BY book_id ORDER BY created_at DESC)` for SQLite 3.25+. Since SQLite has supported window functions since 3.25, this works. Simpler approach: `SELECT book_id, page FROM reading_progress WHERE id IN (SELECT MAX(id) FROM reading_progress WHERE book_id IN (...) AND user_id = ? GROUP BY book_id)`.
- All endpoints must validate `user_id` matches `current_user.id` — user isolation.
- Error handling: `page > book.page_count` returns `422` with a descriptive message.

### 2.3 BookRead Extension

Optionally add `current_page: Optional[int] = None` to `BookRead` schema so the book detail endpoint returns the latest progress in a single call. This means amending `build_book_read` to query the latest progress entry and attach it.

Better approach: keep `BookRead` clean and have the frontend fetch progress separately. This avoids coupling. The frontend already fetches a single book via `GET /api/books/{id}`, so it can make a parallel call to `GET /api/books/{id}/progress?limit=1` or use the dedicated latest endpoint.

**Decision: Keep BookRead unchanged.** The frontend calls the batch latest-progress endpoint for cards and the per-book progress endpoint for the detail view.

### 2.4 Register Router

In `backend/app/main.py`, add:

```python
from app.routers import progress as progress_router
app.include_router(progress_router)
```

### 2.5 Tests

File: `backend/tests/test_progress.py` (new file)

- `test_create_progress_entry`
- `test_create_progress_page_exceeds_page_count`
- `test_list_progress_entries_ordered_by_date`
- `test_delete_progress_entry`
- `test_delete_progress_entry_wrong_user_returns_404`
- `test_latest_progress_batch`
- `test_create_progress_wrong_book_user_returns_404`

---

## 3) Frontend API Layer

File: `frontend/src/lib/api.ts`

Add a `progress` sub-object under `books`:

```typescript
export interface ReadingProgressEntry {
    id: number;
    book_id: number;
    page: number;
    created_at: string;
    updated_at: string;
}

export interface BookProgress {
    book_id: number;
    current_page: number;
}

// In api.books:
progress: {
    async list(bookId: number): Promise<ReadingProgressEntry[]> { ... },
    async create(bookId: number, page: number): Promise<ReadingProgressEntry> { ... },
    async delete(bookId: number, entryId: number): Promise<void> { ... },
    async latest(bookIds: number[]): Promise<BookProgress[]> { ... },
}
```

File: `frontend/src/lib/types.ts`

Add the TypeScript interfaces for `ReadingProgressEntry` and `BookProgress`.

---

## 4) Frontend Components / Updates

### 4.1 BookCard.svelte — Progress Bar

Add a small single-color progress bar at the bottom of the card (inside `.card-body`, after the hints paragraph).

**Logic:**
- Fetch latest progress for all books on the current page via `api.books.progress.latest([...bookIds])` when the list loads.
- Look up `current_page` by `book.id`. If found and `book.page_count` is set and `current_page > 0`, show a thin `<progress>` bar (DaisyUI) or a custom div with `width: (current_page / page_count * 100)%`.
- If no progress or `page_count` is null/0 → render nothing.

**Data flow for cards:** The parent component (e.g. a book list view) currently fetches books and passes them to `BookCard`. It should also fetch `api.books.progress.latest(allVisibleBookIds)` and pass a `Map<number, number>` (book_id → current_page) to `BookCard` as a new prop `progressMap`.

Alternatively, `BookCard` fetches its own progress on mount. That's N+1 queries. Batch is better.

**Update `BookCard` props:**

```typescript
let {
    book,
    onClick,
    currentPage
}: {
    book: Book;
    onClick: (book: Book) => void;
    currentPage?: number;
} = $props();
```

### 4.2 BookDetailDialog.svelte — Reading Progress Block

Insert a new block between the tags row (line ~142) and the ISBN row (line ~144).

The block contains:

1. **Label + text display:** "Reading Progress" with `{current_page}/{total_pages}`.
2. **Editable input:** The `current_page` part is a numeric `<input>` of type `number`, bound to a local state variable.
3. **DaisyUI range slider:** `<input type="range">` with `min=0` and `max={page_count}`, synced to the same state variable.
4. **Persistence:** On `blur` of the input OR when the dialog is about to close (before `open = false`), check if the local value differs from the latest DB value. If yes, call `api.books.progress.create(book.id, currentPage)`. Use `on:blur` on the input and an `$effect` that triggers on dialog close.
5. **Disabled state:** If `book.page_count` is null/0, the entire block is grayed out (`opacity-50 pointer-events-none`) with text "Please set total pages first." (i18n key).
6. **Error handling:** Show a toast on failure.

**State:**

```typescript
let progressEntries: ReadingProgressEntry[] = $state([]);
let currentPage: number = $state(0);
let latestDbPage: number = $state(0);
let hasUnsavedProgress: boolean = $state(false);
```

On book load, fetch `api.books.progress.list(book.id)` and set `currentPage` / `latestDbPage` from the first (most recent) entry's `page` value. If no entries exist, both are 0.

**Save logic:**

```typescript
function saveProgress() {
    if (currentPage === latestDbPage || !book?.page_count) return;
    api.books.progress.create(book.id, currentPage)
        .then(() => { latestDbPage = currentPage; })
        .catch(e => toasts.add(e.message, 'error'));
}
```

Wire `onblur` on the `<input>` to `saveProgress()`, and in the `$effect` that runs when `open` becomes false, call `saveProgress()` before the dialog hides.

### 4.3 Progress Graph (Line Chart)

Add a section below the reading progress block (before the notes section).

**Chart library decision:**

- No chart library is currently in `package.json`.
- Options:
  1. **Chart.js** (~60KB gzipped) — mature, well-documented, Svelte wrapper available (`svelte-chartjs`).
  2. **uPlot** (~35KB) — very fast, but more imperative API.
  3. **Custom SVG** — lightweight, full control, no dependency. A simple line chart with 20-50 data points is easy to implement with a `<svg>` + `<polyline>`.
  4. **Layerchart** — if already considered.

  **Recommendation: Use a small custom SVG-based chart.** It avoids adding a ~40-80KB dependency for a simple single-line chart. The data volume is tiny (< 100 entries per book). SVG gives full styling control with Tailwind/DaisyUI colors. Implementation: ~100 lines of Svelte.

**SVG chart implementation:**

```svelte
{#if progressEntries.length > 1}
  <div class="mt-4">
    <h4 class="text-xs text-base-content/60 mb-2">{$_('book.readingProgress')}</h4>
    <svg viewBox="0 0 {WIDTH} {HEIGHT}" class="w-full h-24">
      <!-- axes, gridlines, polyline, dots -->
    </svg>
  </div>
{/if}
```

- X-axis: dates of entries (one per unique day, using latest entry per day).
- Y-axis: page values.
- Polyline connects the points.
- Hover tooltip: track mouse position via `onpointermove`, find nearest data point, show a small tooltip with page + date.
- If `page_count` is available, optionally draw a dashed horizontal line at `y = page_count` (the finish line).

### 4.4 Log Entry Editor (Modal)

A button "View progress log" in the reading progress section that opens a DaisyUI modal showing all entries sorted by `created_at DESC`.

**New component:** `ProgressLogModal.svelte` (or inline in `BookDetailDialog` if small).

Each row: date, page, delete button.

Delete button: confirmation prompt (native `confirm()`), then `api.books.progress.delete(book.id, entry.id)`, then refresh the local list.

The modal uses DaisyUI's `<dialog>` element with `class="modal"`.

---

## 5) i18n Keys

File: `frontend/src/lib/i18n/locales/en.json`

```json
{
  "book": {
    "readingProgress": "Reading Progress",
    "currentPage": "Page",
    "progressLog": "Progress Log",
    "progressLogEmpty": "No progress entries yet.",
    "setPageCountFirst": "Please set total pages first.",
    "logDate": "Date",
    "logPage": "Page",
    "deleteEntry": "Delete",
    "deleteEntryConfirm": "Delete this entry?",
    "progressGraph": "Progress Over Time"
  }
}
```

File: `frontend/src/lib/i18n/locales/de.json`

```json
{
  "book": {
    "readingProgress": "Lesefortschritt",
    "currentPage": "Seite",
    "progressLog": "Verlauf",
    "progressLogEmpty": "Noch keine Einträge.",
    "setPageCountFirst": "Bitte zuerst Gesamtseitenzahl festlegen.",
    "logDate": "Datum",
    "logPage": "Seite",
    "deleteEntry": "Löschen",
    "deleteEntryConfirm": "Diesen Eintrag löschen?",
    "progressGraph": "Fortschritt im Zeitverlauf"
  }
}
```

---

## 6) Implementation Order

| Step | Description | Files | Dependencies |
|------|-------------|-------|-------------|
| 1 | Add `ReadingProgress` model to `models.py` | `backend/app/models.py` | None |
| 2 | Generate + hand-edit Alembic migration | `backend/alembic/versions/*.py` | Step 1 |
| 3 | Add schemas (`ReadingProgressCreate`, `ReadingProgressRead`, `ReadingProgressLatest`) | `backend/app/schemas.py` | None |
| 4 | Create `progress.py` router with all 4 endpoints | `backend/app/routers/progress.py` | Steps 1, 3 |
| 5 | Register router in `main.py` | `backend/app/main.py` | Step 4 |
| 6 | Backend tests for progress endpoints | `backend/tests/test_progress.py` | Step 4 |
| 7 | Update `frontend/src/lib/types.ts` with TS interfaces | `frontend/src/lib/types.ts` | Step 3 |
| 8 | Update `frontend/src/lib/api.ts` with progress API methods | `frontend/src/lib/api.ts` | Step 7 |
| 9 | Update `frontend/src/lib/i18n/locales/en.json` and `de.json` | i18n locale files | None (parallel) |
| 10 | Update `BookCard.svelte` — add progress bar prop and rendering | `frontend/src/lib/components/BookCard.svelte` + parent book list components | Steps 8, 9 |
| 11 | Update `BookDetailDialog.svelte` — add reading progress block with input + range slider + save on blur/close | `frontend/src/lib/components/BookDetailDialog.svelte` | Steps 8, 9 |
| 12 | Add SVG progress graph to `BookDetailDialog.svelte` | `BookDetailDialog.svelte` | Step 11 |
| 13 | Add log entry editor (modal + delete) | `BookDetailDialog.svelte` or new `ProgressLogModal.svelte` | Steps 8, 9 |
| 14 | Wire batch progress fetching into book list views (dashboard, status pages) | Parent components passing `progressMap` to `BookCard` | Step 10 |
| 15 | Manual verification / Playwright test update | — | All above |

**Parallelism:** Steps 1+2+3 (backend model + schemas) can be done in parallel with Step 9 (i18n). Steps 7+8 (frontend types + API) can start after Step 3. Steps 10+11+12+13 (frontend components) depend on Steps 8+9 but can largely be done in parallel.

---

## 7) Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| User navigates away / closes tab before progress saves | Save on blur + on dialog close covers normal flow. Data loss risk is minimal (one field). |
| Race condition: two progress saves for the same book simultaneously | Append-only log means no conflict; both rows are kept. The "latest" query picks the most recent. |
| SVG chart becomes complex with many data points | Limit visible data points by sampling (e.g. show every Nth entry if > 50). For typical books (< 50 entries) full resolution is fine. |
| `page > page_count` submitted | Backend validates and returns 422. Frontend shows toast with error message. |
| Deleting the latest progress entry leaves no "current page" | After delete, the latest remaining entry's page becomes the new current. If no entries remain, `current_page = 0` and the progress bar disappears — correct behavior. |
