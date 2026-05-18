# Plan: Add Language Field to Books

**Feature ID:** 45  
**Status:** Draft  
**Priority:** Medium  
**Complexity:** Medium

---

## Overview

Add a `language` field to the Book model to store the language a book is written in. The field will be populated during import from Google Books/Open Library and can be manually edited. Language codes will be stored as uppercase ISO 639-1 codes (e.g., "EN", "DE", "FR") with validation and normalization.

**Key Design Decisions:**
- Use ISO 639-1 (2-letter) codes stored as uppercase strings (e.g., "EN", "DE")
- Field is optional (nullable) to support legacy data and books without language info
- Import services already extract and normalize language codes (via `pycountry`)
- Display human-readable language names in UI via `Intl.DisplayNames` (CLDR/ICU data), with code fallback
- No index on language field initially (can be added later if filtering by language becomes a feature)

---

## 1. Backend Implementation

### 1.1 Database Schema Changes

**File:** `backend/app/models.py`

Add `language` field to the `Book` model after `page_count`:

```python
# Line ~49, after page_count
language: Optional[str] = Field(default=None, max_length=2)  # ISO 639-1 code (uppercase)
```

**Rationale:**
- `max_length=2` enforces ISO 639-1 format
- Optional field allows gradual adoption without breaking existing data
- No index needed initially (add later if language filtering becomes a common query)

---

### 1.2 Database Migration

**File:** `backend/alembic/versions/YYYYMMDDHHMMSS_add_language_to_book.py` (auto-generated revision ID)

Create a new Alembic migration:

```bash
cd backend
alembic revision --autogenerate -m "add_language_to_book"
```

**Expected Migration Content:**

```python
def upgrade() -> None:
    op.add_column('book', sa.Column('language', sa.String(length=2), nullable=True))

def downgrade() -> None:
    op.drop_column('book', 'language')
```

**Validation Steps:**
- Test upgrade on dev database
- Verify existing books have `language=NULL`
- Test downgrade (rollback)

---

### 1.3 API Schema Updates

**File:** `backend/app/schemas.py`

Add `language` field to all book-related schemas:

**BookCreate** (line ~27-40):
```python
language: Optional[str] = Field(default=None, max_length=2)
```

**BookUpdate** (line ~43-56):
```python
language: Optional[str] = Field(default=None, max_length=2)
```

**BookRead** (line ~79-94):
```python
language: Optional[str] = None
```

**BookImportCandidate** already has `language` field (line 68) — no change needed.

---

### 1.4 API Router Validation

**File:** `backend/app/routers/books.py`

No functional changes required — existing create/update logic already handles optional fields. The language field will flow through naturally.

**Optional Enhancement (Post-MVP):**
Add a validation helper to normalize language codes:

```python
def _normalize_language(lang: Optional[str]) -> Optional[str]:
    """Normalize language code to uppercase ISO 639-1 format."""
    if not lang:
        return None
    lang = lang.strip().upper()
    if len(lang) != 2 or not lang.isalpha():
        return None
    # Optional: validate against pycountry.languages
    return lang
```

Call this in `create_book` and `update_book` before persisting:
```python
book_data["language"] = _normalize_language(book_data.get("language"))
```

**Decision:** Implement validation helper immediately to prevent invalid data entry.

---

### 1.5 Import Service Integration

**File:** `backend/app/services/book_import.py`

**Status:** ✅ Already implemented!

The import service already extracts and normalizes language codes:

- **Open Library mapping** (line 272-274): Extracts ISO 639-2 codes and converts to ISO 639-1
- **Google Books mapping** (line 471-472): Extracts ISO 639-1 codes directly
- **Normalization function** (line 503-522): Uses `pycountry` to validate and convert to uppercase ISO 639-1

**Verification Needed:**
- Test import with books in various languages
- Verify language codes are correctly populated in `BookImportCandidate`
- Confirm normalization handles edge cases (invalid codes, missing data)

---

## 2. Frontend Implementation

### 2.1 TypeScript Type Updates

**File:** `frontend/src/lib/types.ts`

Add `language` field to `Book` interface (line ~3-19):

```typescript
export interface Book {
    id: number;
    title: string;
    author: string | null;
    isbn: string | null;
    cover_url: string | null;
    publisher: string | null;
    published_year: number | null;
    page_count: number | null;
    language: string | null;  // ADD THIS LINE (after page_count)
    tags: string | null;
    notes: string | null;
    rating: number | null;
    reading_status: ReadingStatus;
    date_added: string;
    date_started: string | null;
    date_finished: string | null;
}
```

**Note:** `BookImportCandidate` already has `language` field (line 29) — no change needed.

---

### 2.2 UI Component Updates

#### 2.2.1 BookDrawer (Edit Form)

**File:** `frontend/src/lib/components/BookDrawer.svelte`

Add language input field in the form after page_count (around line 314):

**Add to state declarations (line ~36-48):**
```typescript
let language = $state('');
```

**Add to $effect block (line ~50-69):**
```typescript
language = book.language ?? '';
```

**Add to buildNonStatusPayload function (line ~71-91):**
```typescript
language: language || null,
```

**Add UI field after page_count (after line 314):**
```svelte
<label class="form-control">
    <span class="label label-text">{$_('book.language')}</span>
    <input 
        type="text" 
        class="input input-bordered input-sm" 
        bind:value={language} 
        maxlength="2"
        placeholder="EN, DE, FR..."
    />
</label>
```

**Design Decision:** Use a simple text input with maxlength=2 rather than a dropdown. Rationale:
- Supports ~180 languages without massive dropdown
- Import auto-fills correct codes
- Validation happens on backend
- Can be enhanced to autocomplete dropdown in future

---

#### 2.2.2 BookDetailDialog (Read-Only View)

**File:** `frontend/src/lib/components/BookDetailDialog.svelte`

Add language display in the metadata grid (around line 277-301):

```svelte
<div class="grid grid-cols-2 gap-3 text-sm">
    <div>
        <div class="text-xs text-base-content/60">{$_('book.language')}</div>
        <div>{book.language ? $_(`language.${book.language.toLowerCase()}`) : '-'}</div>
    </div>
    <div>
        <div class="text-xs text-base-content/60">{$_('book.publisher')}</div>
        <div>{book.publisher ?? '-'}</div>
    </div>
    <!-- ... rest of grid items ... -->
</div>
```

**Placement:** Insert as first grid cell before publisher.

---

#### 2.2.3 AddBookModal (Manual Entry)

**File:** `frontend/src/lib/components/AddBookModal.svelte`

Add language input in the manual entry form (around line 141):

**Add to state declarations (line ~27-37):**
```typescript
let language = $state('');
```

**Add to reset function (line ~40-53):**
```typescript
language = '';
```

**Add to submitManual function (line ~55-86), in the api.books.create payload:**
```typescript
language: language || null,
```

**Add UI field in grid (after page_count, around line 144):**
```svelte
<label class="form-control">
    <span class="label label-text">{$_('book.language')}</span>
    <input 
        type="text" 
        class="input input-bordered input-sm" 
        bind:value={language}
        maxlength="2"
        placeholder="EN, DE, FR..."
    />
</label>
```

---

#### 2.2.4 ImportSearch Integration

**File:** `frontend/src/lib/components/ImportSearch.svelte` (check if exists)

**Status:** Verify import flow includes language field.

Expected: When importing from Google Books/Open Library, the `BookImportCandidate.language` field should already flow through to the created book. No code changes needed if the candidate is passed directly to `api.books.create()`.

**Test Case:** Import a book and verify language is populated.

---

### 2.3 Internationalization (i18n)

#### 2.3.1 Use CLDR/ICU via `Intl.DisplayNames` (No language list in locale JSON)

**Files:**
- `frontend/src/lib/i18n/locales/en.json`
- `frontend/src/lib/i18n/locales/de.json`
- `frontend/src/lib/utils/language.ts` (new helper)

**Approach:**
- Keep only UI label translation key (`book.language`) in locale files.
- Do **not** add a giant `language.*` map to JSON.
- Resolve human-readable language names at runtime with `Intl.DisplayNames`:

```typescript
// frontend/src/lib/utils/language.ts
export function formatLanguageCode(code: string | null | undefined, locale: string): string {
    if (!code) return '-';
    const normalized = code.trim().toLowerCase();
    try {
        const dn = new Intl.DisplayNames([locale], { type: 'language' });
        return dn.of(normalized) ?? code.toUpperCase();
    } catch {
        return code.toUpperCase();
    }
}
```

Then in `BookDetailDialog.svelte`, use current UI locale from i18n store and render:

```svelte
<div>{formatLanguageCode(book.language, $locale)}</div>
```

**Benefits:**
- Supports all CLDR/ICU language names available in runtime
- No i18n JSON bloat
- Automatically localized labels per UI locale
- Graceful fallback for unknown/invalid codes

---

## 3. Testing Strategy

### 3.1 Backend Tests

**File:** `backend/tests/test_books.py`

Add tests for language field:

```python
def test_create_book_with_language(client, auth_token):
    """Test creating a book with language code."""
    response = client.post(
        "/api/books",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Das Kapital",
            "author": "Karl Marx",
            "language": "DE",
            "reading_status": "want_to_read"
        }
    )
    assert response.status_code == 201
    book = response.json()
    assert book["language"] == "DE"


def test_create_book_language_normalized(client, auth_token):
    """Test language code normalization (lowercase → uppercase)."""
    response = client.post(
        "/api/books",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Le Petit Prince",
            "author": "Antoine de Saint-Exupéry",
            "language": "fr",  # lowercase
            "reading_status": "want_to_read"
        }
    )
    assert response.status_code == 201
    book = response.json()
    assert book["language"] == "FR"  # normalized to uppercase


def test_update_book_language(client, auth_token):
    """Test updating book language."""
    # Create book without language
    create_response = client.post(
        "/api/books",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"title": "Test Book", "reading_status": "want_to_read"}
    )
    book_id = create_response.json()["id"]
    
    # Update with language
    update_response = client.patch(
        f"/api/books/{book_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"language": "EN"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["language"] == "EN"


def test_import_book_preserves_language(client, auth_token):
    """Test that imported book language is preserved."""
    candidate = {
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "language": "EN",
        "source": "open_library"
    }
    response = client.post(
        "/api/books/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "candidate": candidate,
            "reading_status": "want_to_read"
        }
    )
    assert response.status_code == 201
    book = response.json()
    assert book["language"] == "EN"
```

**Additional Test Cases:**
- Language field is nullable (create book without language)
- Invalid language codes are rejected or normalized to None
- Language field is returned in list/detail endpoints

---

### 3.2 Import Service Tests

**File:** `backend/tests/test_book_import.py` (create if doesn't exist)

```python
import pytest
from app.services.book_import import _normalize_language_code


def test_normalize_language_iso_639_1():
    """Test normalization of 2-letter ISO 639-1 codes."""
    assert _normalize_language_code("en") == "EN"
    assert _normalize_language_code("EN") == "EN"
    assert _normalize_language_code("de") == "DE"
    assert _normalize_language_code("fr") == "FR"


def test_normalize_language_iso_639_2_terminology():
    """Test normalization of 3-letter ISO 639-2 terminology codes."""
    assert _normalize_language_code("eng") == "EN"
    assert _normalize_language_code("deu") == "DE"
    assert _normalize_language_code("fra") == "FR"


def test_normalize_language_iso_639_2_bibliographic():
    """Test normalization of 3-letter ISO 639-2 bibliographic codes."""
    assert _normalize_language_code("ger") == "DE"  # bibliographic code for German
    assert _normalize_language_code("fre") == "FR"  # bibliographic code for French


def test_normalize_language_invalid():
    """Test that invalid codes return None."""
    assert _normalize_language_code("") is None
    assert _normalize_language_code(None) is None
    assert _normalize_language_code("xyz") is None
    assert _normalize_language_code("12") is None
    assert _normalize_language_code("toolong") is None
```

---

### 3.3 Frontend Tests (Manual QA)

**Manual Test Checklist:**

1. **Manual Book Creation:**
   - Create book with language "EN" → verify saved and displayed correctly
   - Create book with lowercase "de" → verify normalized to "DE"
   - Create book without language → verify displays "-" in detail view
   - Create book with invalid code "XY" → verify backend rejects or normalizes

2. **Book Import:**
   - Import English book from Open Library → verify language = "EN"
   - Import German book from Google Books → verify language = "DE"
   - Import book with no language data → verify language = null

3. **Book Editing:**
   - Edit existing book, add language "FR" → verify saved
   - Edit book, change language "EN" → "DE" → verify updated
   - Edit book, clear language field → verify becomes null

4. **UI Display:**
   - Verify language label appears in BookDetailDialog
   - Verify language input appears in BookDrawer
   - Verify language input appears in AddBookModal
   - Verify language displays human-readable name (e.g., "EN" → "English")
   - Verify fallback for unknown codes (e.g., "XX" displays as "XX")

5. **Internationalization:**
   - Switch UI language to German → verify "Language" becomes "Sprache"
   - Switch UI language to German → verify language names come from `Intl.DisplayNames` (e.g., EN → Englisch)
   - Verify fallback behavior when runtime lacks a language label for a code

---

## 4. Migration and Rollout Strategy

### 4.1 Database Migration Steps

1. **Backup Production Database** (if applicable)
2. Run Alembic migration:
   ```bash
   cd backend
   alembic upgrade head
   ```
3. Verify column added:
   ```sql
   PRAGMA table_info(book);
   -- Should show 'language' column with type VARCHAR(2), nullable
   ```

### 4.2 Deployment Order

1. **Backend Deployment:**
   - Deploy updated models, schemas, and migration
   - Verify `/api/books` endpoints accept and return `language` field

2. **Frontend Deployment:**
   - Deploy updated TypeScript types and UI components
   - Verify language field appears in forms and detail views

### 4.3 Rollback Plan

If issues arise:

1. **Backend Rollback:**
   ```bash
   alembic downgrade -1
   ```
   Removes `language` column from database.

2. **Frontend Rollback:**
   - Revert frontend commits
   - Missing `language` field in API responses will render as `null` (safe)

---

## 5. Future Enhancements (Out of Scope)

These features are **not included** in this plan but can be added later:

1. **Language Filtering:**
   - Add `/api/books?language=EN` query parameter
   - Add language filter dropdown to Library page
   - Add database index on `language` column for performance

2. **Language Statistics:**
   - Show language distribution in Dashboard
   - Add "Books by Language" chart

3. **Advanced Language Input:**
   - Replace text input with searchable dropdown (e.g., using `pycountry` on frontend)
   - Add autocomplete with language name suggestions

4. **Bulk Language Update:**
   - Admin feature to set language for all books by an author or publisher

5. **Multi-Language Books:**
   - Support books with multiple languages (e.g., bilingual editions)
   - Change `language` from string to array

---

## 6. Implementation Checklist

### Backend
- [ ] Add `language` field to `Book` model (`backend/app/models.py`)
- [ ] Generate and test Alembic migration
- [ ] Add `language` to `BookCreate`, `BookUpdate`, `BookRead` schemas
- [ ] Add `_normalize_language()` validation helper in `books.py` router
- [ ] Verify import service language extraction (already implemented)
- [ ] Write backend tests (`test_books.py`)
- [ ] Write import service tests (`test_book_import.py`)

### Frontend
- [ ] Add `language` to `Book` interface (`frontend/src/lib/types.ts`)
- [ ] Add language input to `BookDrawer.svelte`
- [ ] Add language display to `BookDetailDialog.svelte`
- [ ] Add language input to `AddBookModal.svelte`
- [ ] Add `book.language` translation key to `en.json` and `de.json`
- [ ] Add `frontend/src/lib/utils/language.ts` helper using `Intl.DisplayNames`
- [ ] Manual QA testing (import, create, edit, display)

### Documentation
- [ ] Update API documentation (if using OpenAPI/Swagger)
- [ ] Add language field to user-facing docs/README

### Deployment
- [ ] Run database migration in dev/staging
- [ ] Deploy backend changes
- [ ] Deploy frontend changes
- [ ] Verify in production (smoke test)

---

## 7. Estimated Effort

**Backend:** 2-3 hours
- Model/schema changes: 30 min
- Migration: 15 min
- Validation helper: 30 min
- Tests: 1-1.5 hours

**Frontend:** 2-3 hours
- Type updates: 15 min
- UI components: 1.5 hours
- i18n translations: 30 min
- Manual QA: 30-45 min

**Total:** 4-6 hours (one working day)

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Invalid language codes stored in DB | Medium | Add backend validation helper, normalize on save |
| Import service returns invalid codes | Low | Already uses `pycountry` validation, test edge cases |
| Unknown language codes in UI | Low | Add fallback to display raw code if translation missing |
| User confusion with 2-letter codes | Medium | Show placeholder examples ("EN, DE, FR..."), add tooltip in future |
| Performance impact of pycountry validation | Low | Validation only runs on create/update (infrequent), no concern |

---

## 9. Success Criteria

This feature is complete when:

1. ✅ Database schema includes `language` column (nullable, max_length=2)
2. ✅ Backend API accepts and returns `language` in all book endpoints
3. ✅ Language codes are normalized to uppercase ISO 639-1 format
4. ✅ Book import from Google Books/Open Library populates `language` field
5. ✅ Frontend displays language input in BookDrawer and AddBookModal
6. ✅ Frontend displays human-readable language names in BookDetailDialog via `Intl.DisplayNames` (with fallback)
7. ✅ All backend tests pass (create, update, import, validation)
8. ✅ Manual QA confirms correct behavior across all UI flows
9. ✅ No regressions in existing book CRUD functionality

---

**Next Steps:**
1. Review plan with team/stakeholders
2. Begin backend implementation (model → migration → schemas → tests)
3. Begin frontend implementation (types → UI components → i18n)
4. Deploy to staging and conduct QA
5. Deploy to production
