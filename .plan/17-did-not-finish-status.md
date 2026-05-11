# Implementation Plan: Did Not Finish Book Status

**Plan ID**: 17  
**Feature**: Add fourth book state/tab for "Did Not Finish" (DNF) books  
**Status**: Ready for implementation  
**Complexity**: Medium (database migration + full-stack changes)  
**Estimated Time**: 3-4 hours  

---

## Overview

Add a new `did_not_finish` reading status as a first-class state alongside the existing three states (`want_to_read`, `currently_reading`, `read`). This allows users to track books they intentionally abandoned because they were bad, boring, or not interesting.

### User Impact

**Before**: No way to distinguish between unfinished books and books user never wants to finish  
**After**: Clear "Did Not Finish" status with dedicated tab, allowing users to track abandoned books separately

---

## Phase 1: Backend - Database & Models

### 1.1 Create Alembic Migration

**File**: `backend/alembic/versions/[timestamp]_add_did_not_finish_status.py`

**Action**: Add new enum value `did_not_finish` to the `ReadingStatus` enum in the database.

**Migration Steps**:

```python
"""add did_not_finish status

Revision ID: [auto-generated]
Revises: 9e90ac72c767
Create Date: [auto-generated]

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '[auto-generated]'
down_revision: Union[str, None] = '9e90ac72c767'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add did_not_finish to ReadingStatus enum."""
    # SQLite doesn't support ALTER TYPE for enums, so we use a workaround:
    # 1. Add new column with updated enum
    # 2. Migrate data
    # 3. Drop old column
    # 4. Rename new column
    
    # For SQLite, we need to recreate the table with the new enum
    with op.batch_alter_table('book', schema=None) as batch_op:
        # SQLite limitation: Can't directly alter enum values
        # We'll use a string check constraint instead
        batch_op.alter_column(
            'reading_status',
            type_=sa.Enum('want_to_read', 'currently_reading', 'read', 'did_not_finish', name='readingstatus'),
            existing_type=sa.Enum('want_to_read', 'currently_reading', 'read', name='readingstatus'),
            nullable=False
        )


def downgrade() -> None:
    """Remove did_not_finish from ReadingStatus enum."""
    # Migrate any books with did_not_finish status to want_to_read before removing enum value
    op.execute(
        "UPDATE book SET reading_status = 'want_to_read' WHERE reading_status = 'did_not_finish'"
    )
    
    with op.batch_alter_table('book', schema=None) as batch_op:
        batch_op.alter_column(
            'reading_status',
            type_=sa.Enum('want_to_read', 'currently_reading', 'read', name='readingstatus'),
            existing_type=sa.Enum('want_to_read', 'currently_reading', 'read', 'did_not_finish', name='readingstatus'),
            nullable=False
        )
```

**Notes**:
- SQLite doesn't support `ALTER TYPE` for enums natively
- Use `batch_alter_table` context for SQLite compatibility
- Downgrade migration moves `did_not_finish` books back to `want_to_read` (safest fallback)
- Alternative: Could move to `read` status in downgrade if that makes more semantic sense

**Backward Compatibility**: 
- Existing data remains unchanged
- Old clients that don't know about `did_not_finish` will see it in API responses (handled by validation in Phase 2)
- Downgrade migration provides safe rollback path

---

### 1.2 Update SQLModel Enum

**File**: `backend/app/models.py`

**Change**: Add `did_not_finish` to `ReadingStatus` enum

```python
class ReadingStatus(str, Enum):
    want_to_read = "want_to_read"
    currently_reading = "currently_reading"
    read = "read"
    did_not_finish = "did_not_finish"  # NEW
```

**Lines Modified**: Line 11 (add new enum value)

**Impact**: All API endpoints that use `ReadingStatus` will now accept and return this new value

---

### 1.3 Verify API Schema Compatibility

**File**: `backend/app/schemas.py`

**Action**: No changes needed — schemas already reference `ReadingStatus` enum from `models.py`

**Verified Files**:
- `BookCreate` — uses `ReadingStatus` (default remains `want_to_read`)
- `BookUpdate` — uses `Optional[ReadingStatus]` (automatically supports new value)
- `BookRead` — uses `ReadingStatus` (automatically supports new value)
- `BookImportRequest` — uses `ReadingStatus` (default remains `want_to_read`)

**API Compatibility**: All endpoints automatically support new status via enum reference

---

### 1.4 Verify Router Logic

**File**: `backend/app/routers/books.py`

**Action**: No changes needed

**Verified Logic**:
- `list_books()` — Status filtering works via enum (lines 39-40)
- `create_book()` — Accepts any `ReadingStatus` value
- `update_book()` — Accepts any `ReadingStatus` value

**Routing Impact**: All existing query, filter, and sort logic automatically supports new status

---

## Phase 2: Backend - Testing

### 2.1 Add Unit Tests for DNF Status

**File**: `backend/tests/test_books.py`

**New Tests** (add after existing status tests, ~line 87):

```python
# ── did_not_finish status tests ──────────────────────────────────────────────

def test_create_book_with_did_not_finish_status(client: TestClient):
    """Can create a book with did_not_finish status."""
    resp = client.post(
        "/api/books",
        json={"title": "Boring Book", "reading_status": "did_not_finish"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["reading_status"] == "did_not_finish"
    assert data["title"] == "Boring Book"


def test_list_books_filter_by_did_not_finish(client: TestClient):
    """Can filter books by did_not_finish status."""
    _create_book(client, title="Want", reading_status="want_to_read")
    _create_book(client, title="Reading", reading_status="currently_reading")
    _create_book(client, title="Done", reading_status="read")
    _create_book(client, title="Abandoned", reading_status="did_not_finish")

    resp = client.get("/api/books?status=did_not_finish")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Abandoned"
    assert data[0]["reading_status"] == "did_not_finish"


def test_update_book_to_did_not_finish_status(client: TestClient):
    """Can update a book to did_not_finish status."""
    book = _create_book(client, title="Started But Bad", reading_status="currently_reading")
    
    resp = client.patch(
        f"/api/books/{book['id']}",
        json={"reading_status": "did_not_finish"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reading_status"] == "did_not_finish"


def test_import_book_with_did_not_finish_status(client: TestClient):
    """Can import a book directly to did_not_finish status."""
    # This tests the BookImportRequest flow
    import_payload = {
        "candidate": {
            "title": "Bad Book",
            "author": "Unknown Author",
            "isbn": "1234567890123",
            "source": "open_library"
        },
        "reading_status": "did_not_finish"
    }
    
    resp = client.post("/api/import", json=import_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["reading_status"] == "did_not_finish"
    assert data["title"] == "Bad Book"
```

**Lines Added**: ~60 lines

**Test Coverage**:
- ✅ Create book with `did_not_finish` status
- ✅ Filter books by `did_not_finish` status  
- ✅ Update book to `did_not_finish` status
- ✅ Import book with `did_not_finish` status (via import endpoint)

**Notes**:
- Uses existing `_create_book()` helper
- Follows existing test patterns (arrange-act-assert)
- Uses `client` fixture from `conftest.py`
- Tests all CRUD operations for new status

---

### 2.2 Run Existing Test Suite

**Action**: Verify no regressions with new enum value

```bash
cd backend
pytest tests/test_books.py -v
pytest tests/test_import.py -v
```

**Expected**: All existing tests should pass unchanged (enum is additive, not breaking)

---

### 2.3 Manual Migration Testing

**Action**: Test migration up/down with sample data

```bash
cd backend

# Create sample book with existing status
python -c "from app.database import engine; from app.models import Book, ReadingStatus, SQLModel; SQLModel.metadata.create_all(engine); from sqlmodel import Session; s = Session(engine); b = Book(title='Test', reading_status=ReadingStatus.currently_reading); s.add(b); s.commit()"

# Run migration up
alembic upgrade head

# Verify enum accepts new value
python -c "from app.database import engine; from app.models import Book, ReadingStatus; from sqlmodel import Session; s = Session(engine); b = Book(title='DNF Book', reading_status=ReadingStatus.did_not_finish); s.add(b); s.commit(); print('✓ Migration successful')"

# Test downgrade
alembic downgrade -1

# Verify DNF books migrated to want_to_read
python -c "from app.database import engine; from app.models import Book; from sqlmodel import Session, select; s = Session(engine); books = s.exec(select(Book).where(Book.title == 'DNF Book')).all(); print(f'Status after downgrade: {books[0].reading_status if books else \"not found\"}')"
```

**Expected Outcomes**:
- ✅ Migration up adds enum value without errors
- ✅ New books can be created with `did_not_finish` status
- ✅ Migration down converts `did_not_finish` → `want_to_read`
- ✅ No data loss during migrations

---

## Phase 3: Frontend - Types & API Layer

### 3.1 Update TypeScript Type Definitions

**File**: `frontend/src/lib/types.ts`

**Change**: Add `did_not_finish` to `ReadingStatus` type

```typescript
export type ReadingStatus = 'want_to_read' | 'currently_reading' | 'read' | 'did_not_finish';
```

**Lines Modified**: Line 1

**Impact**: TypeScript compiler will now accept `did_not_finish` in all components

---

### 3.2 Verify API Client Compatibility

**File**: `frontend/src/lib/api.ts`

**Action**: No changes needed

**Reason**: API client uses `ReadingStatus` type from `types.ts`, so it automatically supports new value

**Verified Endpoints** (check if file exists):
- `books.list({ status })` — Type-safe status filter
- `books.create(data)` — Accepts any `ReadingStatus`
- `books.update(id, data)` — Accepts any `ReadingStatus`

---

## Phase 4: Frontend - Navigation & Layout

### 4.1 Add DNF Tab to Navigation

**File**: `frontend/src/routes/+layout.svelte`

**Changes**:

1. **Add NAV_ITEMS entry** (line 16-20):

```typescript
const NAV_ITEMS: { status: ReadingStatus; label: string; icon: string }[] = [
	{ status: 'want_to_read', label: 'Want to Read', icon: '📚' },
	{ status: 'currently_reading', label: 'Reading', icon: '📖' },
	{ status: 'read', label: 'Read', icon: '✓' },
	{ status: 'did_not_finish', label: 'Did Not Finish', icon: '❌' }  // NEW
];
```

**Icon Choice**: ❌ (cross mark) — visually distinct, indicates abandonment  
**Alternative Icons**: 🚫 (prohibited), ⛔ (no entry), 🗑️ (trash), 💔 (broken heart)

**Label**: "Did Not Finish" — clear and self-explanatory  
**Alternative Labels**: "Abandoned", "DNF", "Unfinished" (but semantically different)

2. **Navigation Impact**:
   - Desktop sidebar: Fourth button appears below "Read"
   - Mobile bottom bar: Fourth tab icon appears (may require layout adjustment if cramped)

**Lines Modified**: 1 line added (array entry)

**UX Considerations**:
- **Desktop**: Sidebar can accommodate 4+ items easily
- **Mobile**: Bottom bar with 4 tabs is standard pattern (common in many apps)
- **Overflow**: If future states are added, consider hamburger menu or tabs slider

---

### 4.2 Add Status Label Mapping

**File**: `frontend/src/routes/+page.svelte`

**Change**: Add `did_not_finish` to `STATUS_LABELS` object (line 87-91)

```typescript
const STATUS_LABELS: Record<string, string> = {
	want_to_read: 'Want to Read',
	currently_reading: 'Currently Reading',
	read: 'Read',
	did_not_finish: 'Did Not Finish'  // NEW
};
```

**Lines Modified**: 1 line added

**Impact**: Page header shows "Did Not Finish" when user navigates to `/?status=did_not_finish`

---

## Phase 5: Frontend - Component Updates

### 5.1 Update Book Drawer Status Selector

**File**: `frontend/src/lib/components/BookDrawer.svelte`

**Action**: Find status selector `<select>` element and add fourth option

**Expected Location** (~line 50-100, typical pattern in drawer components):

```svelte
<select bind:value={editedBook.reading_status} class="select select-bordered">
	<option value="want_to_read">Want to Read</option>
	<option value="currently_reading">Currently Reading</option>
	<option value="read">Read</option>
	<option value="did_not_finish">Did Not Finish</option>  <!-- NEW -->
</select>
```

**Lines Modified**: 1 line added (option element)

**Impact**: Users can change book status to "Did Not Finish" in edit drawer

---

### 5.2 Update Add Book Modal Status Selector

**File**: `frontend/src/lib/components/AddBookModal.svelte`

**Action**: Find status selector `<select>` element and add fourth option

**Expected Location** (~line 60-120, typical pattern in modal forms):

```svelte
<select bind:value={newBook.reading_status} class="select select-bordered">
	<option value="want_to_read">Want to Read</option>
	<option value="currently_reading">Currently Reading</option>
	<option value="read">Read</option>
	<option value="did_not_finish">Did Not Finish</option>  <!-- NEW -->
</select>
```

**Lines Modified**: 1 line added (option element)

**Impact**: Users can create books directly in "Did Not Finish" status

---

### 5.3 Update Import Book Status Selector

**File**: `frontend/src/lib/components/ImportSearch.svelte`

**Action**: Find status selector for import candidates (if exists) and add fourth option

**Expected Pattern** (check if status selector exists in import flow):

```svelte
<select bind:value={importStatus} class="select select-bordered select-sm">
	<option value="want_to_read">Want to Read</option>
	<option value="currently_reading">Currently Reading</option>
	<option value="read">Read</option>
	<option value="did_not_finish">Did Not Finish</option>  <!-- NEW -->
</select>
```

**Note**: If import flow always defaults to `want_to_read` and users change status later, this may not be needed. Review component to determine.

**Lines Modified**: 0-1 line (if status selector exists in import flow)

---

### 5.4 Verify Book Card Component

**File**: `frontend/src/lib/components/BookCard.svelte`

**Action**: No changes needed (displays book data, doesn't filter by status)

**Reason**: Component renders whatever books are passed to it, agnostic to status values

---

## Phase 6: Frontend - Testing

### 6.1 Manual UI Testing Checklist

**Test Environment**: Development server (`npm run dev`)

**Test Cases** (30 tests):

#### Navigation (6 tests)
1. ✅ Desktop: "Did Not Finish" button appears in sidebar
2. ✅ Desktop: Clicking "Did Not Finish" navigates to `/?status=did_not_finish`
3. ✅ Mobile: "Did Not Finish" tab appears in bottom bar
4. ✅ Mobile: Tapping "Did Not Finish" navigates correctly
5. ✅ Page header shows "Did Not Finish" on DNF tab
6. ✅ URL query param `?status=did_not_finish` works via direct navigation

#### Create Book (6 tests)
7. ✅ "Did Not Finish" option appears in Add Book modal status dropdown
8. ✅ Can create book with "Did Not Finish" status
9. ✅ New DNF book appears in DNF tab (not in other tabs)
10. ✅ Book card renders correctly in DNF tab
11. ✅ Date added populates correctly
12. ✅ Create book validation still works (required title, rating 1-5, etc.)

#### Edit Book (6 tests)
13. ✅ "Did Not Finish" option appears in Book Drawer status dropdown
14. ✅ Can change book from "Currently Reading" → "Did Not Finish"
15. ✅ Edited book moves to DNF tab (disappears from old tab)
16. ✅ Can change book from "Did Not Finish" → "Read"
17. ✅ Book details (title, author, notes, rating) save correctly
18. ✅ Edit validation still works (rating 1-5, etc.)

#### List/Filter (6 tests)
19. ✅ DNF tab shows only DNF books (not other statuses)
20. ✅ Search works in DNF tab (title/author filtering)
21. ✅ Sort by date added works in DNF tab (asc/desc)
22. ✅ Sort by rating works in DNF tab (asc/desc)
23. ✅ Empty state shows when no DNF books ("No books here yet")
24. ✅ Loading spinner shows during fetch

#### Import (3 tests)
25. ✅ Can import book to "Did Not Finish" status (if status selector exists in import)
26. ✅ Imported DNF book appears in DNF tab
27. ✅ Import search result marking works for DNF books (if implemented)

#### Delete (3 tests)
28. ✅ Can delete book from DNF tab
29. ✅ Deleted DNF book disappears from list
30. ✅ Cover cleanup works for DNF books (if cover exists)

**Devices to Test**:
- Desktop: Chrome/Firefox/Safari (macOS/Windows/Linux)
- Mobile: Safari (iOS), Chrome (Android)
- Tablet: iPad Safari, Android Chrome

**Browsers**: Test in at least 2 browsers (Chrome + one other)

---

### 6.2 Regression Testing

**Verify Existing Functionality Unchanged**:

1. ✅ "Want to Read" tab still works (create, edit, filter, search, sort, delete)
2. ✅ "Currently Reading" tab still works (all operations)
3. ✅ "Read" tab still works (all operations)
4. ✅ Import flow unchanged (if no status selector added)
5. ✅ Cover upload/download still works
6. ✅ Toast notifications still appear
7. ✅ Responsive layout not broken (mobile/desktop)

---

### 6.3 End-to-End User Flow Test

**Scenario**: User marks a boring book as DNF

**Steps**:
1. User is reading "Boring Book 2000" (status: `currently_reading`)
2. User decides book is too boring to finish
3. User navigates to "Currently Reading" tab
4. User clicks book card to open drawer
5. User changes status dropdown to "Did Not Finish"
6. User adds note: "First 50 pages were too slow"
7. User clicks "Save"
8. **Expected**: Drawer closes, book disappears from "Currently Reading" tab
9. User navigates to "Did Not Finish" tab
10. **Expected**: "Boring Book 2000" appears with note, status badge shows "Did Not Finish"

**Result**: ✅ / ❌

---

## Phase 7: Documentation & UX Copy

### 7.1 Update README (if feature list exists)

**File**: `README.md`

**Action**: Add "Did Not Finish" status to feature list (if README documents reading statuses)

**Example**:

```markdown
## Features

- Track books across four reading states:
  - **Want to Read**: Books on your wish list
  - **Currently Reading**: Books you're actively reading
  - **Read**: Finished books
  - **Did Not Finish**: Books you intentionally abandoned
```

---

### 7.2 User-Facing Copy Review

**Review Locations**:
- Navigation labels: "Did Not Finish" (clear, self-explanatory)
- Page header: "Did Not Finish" (consistent with nav)
- Status dropdown options: "Did Not Finish" (matches everywhere)
- Empty state message: "No books here yet." (generic, works for all tabs)

**Consistency Check**: All labels should say "Did Not Finish" (not "DNF", "Abandoned", etc.)

---

### 7.3 Inline Code Comments

**Add Comments Where Helpful**:

```typescript
// Four reading states: want_to_read, currently_reading, read, did_not_finish
export type ReadingStatus = 'want_to_read' | 'currently_reading' | 'read' | 'did_not_finish';
```

```python
class ReadingStatus(str, Enum):
    """Reading status of a book.
    
    - want_to_read: On wish list, not started
    - currently_reading: Actively reading
    - read: Finished
    - did_not_finish: Intentionally abandoned (bad/boring/uninteresting)
    """
    want_to_read = "want_to_read"
    currently_reading = "currently_reading"
    read = "read"
    did_not_finish = "did_not_finish"
```

---

## Phase 8: Deployment & Rollback

### 8.1 Pre-Deployment Checklist

- ✅ All backend tests pass (`pytest backend/tests/`)
- ✅ All frontend tests pass (if any exist)
- ✅ Manual UI testing completed (30 test cases)
- ✅ Regression testing completed (existing tabs still work)
- ✅ Database migration tested locally (up + down)
- ✅ Code reviewed (self-review or peer review)
- ✅ No console errors in browser devtools

---

### 8.2 Deployment Steps

**Backend Deployment**:

```bash
cd backend

# 1. Backup database (production safety)
cp data/librislog.db data/librislog.db.backup-$(date +%Y%m%d-%H%M%S)

# 2. Run migration
alembic upgrade head

# 3. Restart backend service
# (systemctl restart librislog-backend, or docker-compose restart backend, etc.)
```

**Frontend Deployment**:

```bash
cd frontend

# 1. Build production assets
npm run build

# 2. Deploy static files
# (copy build/ to web server, or docker-compose restart frontend, etc.)
```

**Verify Deployment**:
- ✅ Backend health check: `curl http://localhost:8000/api/health`
- ✅ Frontend loads: Open app in browser
- ✅ DNF tab appears in navigation
- ✅ Can create book with DNF status

---

### 8.3 Rollback Plan

**If Issues Found Post-Deployment**:

**Quick Disable** (hide DNF tab in frontend, keep backend):
- Remove DNF entry from `NAV_ITEMS` in `+layout.svelte`
- Redeploy frontend only (~5 minutes)
- Books with `did_not_finish` status remain in database (accessible via API)

**Full Rollback** (database + code):

```bash
# 1. Rollback database migration
cd backend
alembic downgrade -1  # Migrates DNF books to want_to_read

# 2. Revert code changes
git revert <commit-hash>  # Or restore from backup

# 3. Redeploy backend + frontend
# (restart services)
```

**Rollback Impact**:
- Books with `did_not_finish` status migrate to `want_to_read` (safest fallback)
- No data loss (all book metadata preserved)
- Users may need to re-mark DNF books if feature is re-deployed later

**Complexity**: Low (clean migration downgrade path, self-contained feature)

---

## Key Decisions & Questions for User Confirmation

### Before Implementation Starts:

#### 1. Icon Choice for DNF Tab

**Proposed**: ❌ (cross mark) — visually distinct, indicates "no" or "stop"  
**Alternatives**:
- 🚫 Prohibited sign (stronger "no" signal)
- 💔 Broken heart (emotional, indicates disappointment)
- 📕 Closed red book (book metaphor, but may confuse with "Read")
- 🗑️ Trash can (implies deletion, may be too negative)

**Question**: Is ❌ acceptable, or do you prefer a different icon?

---

#### 2. Label Wording

**Proposed**: "Did Not Finish" (clear, grammatically complete)  
**Alternatives**:
- "DNF" (shorter, but requires users to know abbreviation)
- "Abandoned" (implies user gave up, slightly negative connotation)
- "Unfinished" (ambiguous — could include paused books)
- "Dropped" (casual tone, less formal)

**Question**: Is "Did Not Finish" the right label, or do you prefer shorter/alternative wording?

---

#### 3. Migration Downgrade Behavior

**Proposed**: `did_not_finish` → `want_to_read` (safest, indicates book is still "available" to read)  
**Alternative**: `did_not_finish` → `read` (user "completed" their interaction with the book, even if DNF)

**Question**: If migration is rolled back, should DNF books move to "Want to Read" or "Read"?

---

#### 4. Mobile Bottom Bar Layout

**Current**: 3 tabs (easy to tap, ~33% width each)  
**After**: 4 tabs (~25% width each)

**Concern**: Bottom bar may feel crowded on small screens (iPhone SE, etc.)

**Alternatives**:
- Keep 4 tabs (standard pattern, most apps handle 4-5 tabs fine)
- Add "More" menu (5th tab that shows additional options)
- Use horizontal scrolling tabs (allows unlimited states, but less discoverable)

**Question**: Is 4-tab bottom bar acceptable, or do you want to test on small screen first?

---

#### 5. Default Status for Imported Books

**Current**: Imported books default to `want_to_read`  
**Proposed**: Keep this default (users rarely import books they know are bad)

**Alternative**: Add status selector to import flow (allows importing to any status, including DNF)

**Question**: Should import flow add a status selector, or is `want_to_read` default sufficient?

---

#### 6. Empty State Message

**Current**: Generic "No books here yet." for all tabs  
**Alternative**: Tab-specific messages (e.g., "No abandoned books yet. Mark books as DNF to see them here.")

**Question**: Should DNF tab have a custom empty state message, or keep generic message?

---

## Success Criteria

Implementation is complete when:

1. ✅ Database migration adds `did_not_finish` to `ReadingStatus` enum
2. ✅ Migration up/down works without errors or data loss
3. ✅ Backend API accepts and returns `did_not_finish` status
4. ✅ All backend tests pass (existing + 4 new DNF tests)
5. ✅ Frontend navigation shows DNF tab (desktop sidebar + mobile bottom bar)
6. ✅ Page header shows "Did Not Finish" on DNF tab
7. ✅ Users can create books with DNF status (Add Book modal)
8. ✅ Users can edit books to DNF status (Book Drawer)
9. ✅ Users can import books to DNF status (if import status selector added)
10. ✅ DNF tab filters correctly (shows only DNF books)
11. ✅ Search and sort work in DNF tab
12. ✅ All 30 manual UI tests pass
13. ✅ Regression tests pass (existing tabs unchanged)
14. ✅ No console errors in browser devtools
15. ✅ Mobile responsive layout works (bottom bar not broken)
16. ✅ README updated (if feature list exists)
17. ✅ Deployment tested locally (backend + frontend)
18. ✅ Rollback plan verified (downgrade migration works)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SQLite enum migration fails | Low | High | Test migration extensively locally; provide fallback SQL script |
| Mobile bottom bar too crowded | Low | Medium | Test on small screen (iPhone SE); prepare horizontal scroll fallback |
| Users confused by "Did Not Finish" label | Low | Low | Use clear label + icon; add tooltip if needed |
| Downgrade migration loses data | Very Low | High | Downgrade moves books to `want_to_read` (no deletion); database backup before deployment |
| Existing tabs break | Very Low | Medium | Comprehensive regression testing (all CRUD operations in 3 existing tabs) |
| TypeScript type errors | Very Low | Low | `ReadingStatus` type update is additive (no breaking changes) |

**Overall Risk**: **Low** (additive feature, clean migration path, well-tested patterns)

---

## Implementation Order

**Recommended Sequence** (minimizes context switching):

### Step 1: Backend Foundation (1 hour)
1. Update `models.py` enum (2 min)
2. Generate Alembic migration (5 min)
3. Review and refine migration SQL (15 min)
4. Test migration up/down locally (20 min)
5. Add backend unit tests (18 min)
6. Run full backend test suite (5 min)

### Step 2: Frontend Types & Navigation (45 min)
7. Update `types.ts` enum (1 min)
8. Add DNF nav item to `+layout.svelte` (3 min)
9. Add DNF label to `+page.svelte` (2 min)
10. Test navigation in dev server (10 min)
11. Verify mobile bottom bar layout (10 min)
12. Adjust spacing/styling if needed (19 min)

### Step 3: Frontend Components (45 min)
13. Update `BookDrawer.svelte` status selector (3 min)
14. Update `AddBookModal.svelte` status selector (3 min)
15. Update `ImportSearch.svelte` if needed (5 min)
16. Test create/edit flows in dev server (30 min)
17. Fix any UI bugs found (4 min)

### Step 4: Testing & Documentation (1 hour)
18. Run 30-test manual UI checklist (40 min)
19. Run regression tests (existing tabs) (10 min)
20. Update README (if needed) (5 min)
21. Add code comments where helpful (5 min)

### Step 5: Deployment Prep (30 min)
22. Review all changes (code self-review) (10 min)
23. Test deployment locally (docker-compose, etc.) (15 min)
24. Verify rollback works (downgrade migration) (5 min)

**Total Estimated Time**: **4 hours**  
**Buffer for unknowns**: +30 min (enum edge cases, mobile layout tweaks)  
**Realistic Estimate**: **4.5 hours**

---

## Context for Implementation

**When ready to implement**:

### Reference Files (Already Read)
- `backend/app/models.py` — Enum definition pattern
- `backend/alembic/versions/9e90ac72c767_create_book_table.py` — Migration pattern
- `backend/tests/test_books.py` — Test patterns (use `_create_book()` helper)
- `frontend/src/lib/types.ts` — Type definitions
- `frontend/src/routes/+layout.svelte` — Navigation structure
- `frontend/src/routes/+page.svelte` — Status label mapping

### Useful Tools
- **Alembic CLI**: Generate migration: `alembic revision --autogenerate -m "add did_not_finish status"`
- **Pytest**: Run tests: `pytest backend/tests/test_books.py -v -k did_not_finish`
- **SvelteKit Dev**: Hot reload: `npm run dev` in `frontend/`

### Testing ISBNs (For Manual Testing)
- 9780441013593 (Dune — classic, likely "Read")
- 9780345391803 (The Hitchhiker's Guide — funny, likely "Read")
- 0000000000000 (Invalid ISBN — good for DNF testing)

### Database Backup Command (Before Deployment)
```bash
cp data/librislog.db data/librislog.db.backup-$(date +%Y%m%d-%H%M%S)
```

---

## Future Enhancements (Out of Scope)

**Not Included in This Plan** (consider for later):

1. **DNF Reason Field**: Optional dropdown (e.g., "Too slow", "Not interesting", "Bad writing") — requires schema change
2. **Date DNF'd Field**: Track when user abandoned book (similar to `date_finished`) — requires schema change
3. **Re-attempt Tracking**: Allow users to mark DNF books as "Want to Re-Try" — requires new status or flag
4. **DNF Statistics**: Show % of books DNF'd, most DNF'd genres, etc. — requires analytics view
5. **Sort by DNF Date**: Sort DNF tab by when books were abandoned (requires `date_dnf` field)
6. **Import DNF Books**: Bulk import from Goodreads "abandoned" shelf — requires import mapping

---

**Plan Status**: ✅ Ready for Implementation  
**Blockers**: None (awaiting user confirmation on key decisions)  
**Next Step**: User reviews plan → confirms decisions → implementation begins
