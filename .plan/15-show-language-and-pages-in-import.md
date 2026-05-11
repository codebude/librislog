# Plan: Display Language and Page Count in Import Search Results

## Overview

Extend the import search result UI to display two additional book metadata fields per result:
- **Language** (from the `BookImportCandidate` data)
- **Number of pages** (already available as `page_count`)

Both fields should render conditionally — only shown when the data is available for that specific result.

**Goal**: Provide users with more information about books in import search results to help them make informed decisions before importing.

## Current State Analysis

### Backend

**Data Model** (`backend/app/schemas.py`):
```python
class BookImportCandidate(SQLModel):
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: Optional[int] = None  # ✅ Already available
    genre: Optional[str] = None
    source: str  # "open_library" | "google_books"
```

**Current Status**:
- ✅ `page_count` field exists and is already populated by import services
- ❌ **`language` field does NOT exist** in `BookImportCandidate`

**Data Source Analysis**:

**Open Library API** (`backend/app/services/book_import.py`, lines 154-191):
- Fields currently mapped: `title, author_name, isbn, publisher, first_publish_year, number_of_pages_median, subject, cover_i`
- **Available but not mapped**: `language` — returns ISO 639-2 codes (3-letter) as a list, e.g. `["eng", "fre"]`
- Example response:
  ```json
  {
    "title": "Dune",
    "language": ["eng"],
    "number_of_pages_median": 412
  }
  ```

**Google Books API** (`backend/app/services/book_import.py`, lines 372-415):
- Fields currently mapped: `title, authors, industryIdentifiers, publisher, publishedDate, pageCount, categories, imageLinks`
- **Available but not mapped**: `language` — returns ISO 639-1 codes (2-letter), e.g. `"en"`, `"fr"`
- Example response:
  ```json
  {
    "volumeInfo": {
      "title": "Foundation",
      "language": "en",
      "pageCount": 255
    }
  }
  ```

**Key Findings**:
1. Both APIs provide language codes, but in different formats:
   - Open Library: 3-letter ISO 639-2, as a list
   - Google Books: 2-letter ISO 639-1, as a string
2. `page_count` is already mapped and available
3. No language field currently exists in schema or UI

### Frontend

**Component**: `frontend/src/lib/components/ImportSearch.svelte`

**Current display per result** (lines 243-282):
- Cover image thumbnail (10px width)
- Title (font-medium, line-clamp-2)
- Author (text-xs, if available)
- Source + published year (text-xs, e.g., "open_library · 1965")
- "Already imported" badge (if applicable)
- "Add" button

**Observations**:
- Metadata displayed in a compact vertical layout
- Uses conditional rendering for optional fields (e.g., `{#if candidate.author}`)
- Space constraints — card is ~80px max-height in scrollable list
- Uses Tailwind + DaisyUI for styling

**TypeScript types** (`frontend/src/lib/types.ts`):
```typescript
// Current (inferred from schema)
type BookImportCandidate = {
  title: string;
  author?: string | null;
  isbn?: string | null;
  cover_url?: string | null;
  publisher?: string | null;
  published_year?: number | null;
  page_count?: number | null;  // ✅ Already available
  genre?: string | null;
  source: string;
}
```

**Type Update Needed**: Add `language?: string | null` to frontend types.

## Requirements

### Functional Requirements

1. ✅ **Backend schema update**: Add `language: Optional[str]` to `BookImportCandidate`
2. ✅ **Open Library mapping**: Extract `language` field, normalize to 2-letter code or readable name
3. ✅ **Google Books mapping**: Extract `language` field (already 2-letter code)
4. ✅ **Frontend UI update**: Display language and page count in result cards
5. ✅ **Conditional rendering**: Only show fields when data is available
6. ✅ **Graceful degradation**: Results without these fields should render normally

### Non-Functional Requirements

- **Performance**: No new API calls — data already available in existing responses
- **UX**: Fields should be visually distinct but not cluttered
- **Consistency**: Follow existing styling patterns in `ImportSearch.svelte`
- **Maintainability**: Use existing helper functions and styles

### Out of Scope

- ❌ Language translation (display codes as-is, or simple mapping to full names)
- ❌ Storing language in local book database (`Book` model)
- ❌ Filtering or sorting by language/page count
- ❌ Localizing language names to user's locale

## Problem Statement

Users browsing import search results cannot see:
1. **Language** of the book — important for multilingual readers
2. **Number of pages** — useful for estimating reading time and book length

Both fields are available from the external APIs but not currently extracted or displayed.

## Implementation Plan

### Phase 1: Backend Schema Update

**Goal**: Add `language` field to `BookImportCandidate` and populate it from API responses.

#### Step 1.1: Update Schema

**File**: `backend/app/schemas.py`

**Change** (after line 51):
```python
class BookImportCandidate(SQLModel):
    """A book result from an external API, not yet persisted locally."""
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    page_count: Optional[int] = None
    genre: Optional[str] = None
    language: Optional[str] = None  # ← ADD THIS LINE (ISO 639-1/639-2 code or full name)
    source: str  # "open_library" | "google_books"
```

**Rationale**: 
- Keep it simple — store as a string (not a list, even though Open Library returns a list)
- Store the code or a human-readable name (decision in next step)

#### Step 1.2: Map Language from Open Library

**File**: `backend/app/services/book_import.py`

**Update `map_open_library()` function** (lines 194-226):

**Add after line 214** (after genre mapping):
```python
    # Language: first entry of the list, prefer English if multiple
    # Open Library returns ISO 639-2 codes (3-letter) as a list, e.g. ["eng"]
    languages: list[str] = doc.get("language") or []
    language = _normalize_language_code(languages[0]) if languages else None
```

**Update return statement** (line 216):
```python
    return BookImportCandidate(
        title=doc["title"],
        author=author,
        isbn=isbn,
        cover_url=cover_url,
        publisher=publisher,
        published_year=doc.get("first_publish_year"),
        page_count=doc.get("number_of_pages_median"),
        genre=genre,
        language=language,  # ← ADD THIS LINE
        source="open_library",
    )
```

**Also update search fields** (lines 162 and 168):
```python
# Line 162 (ISBN search)
"fields": "title,author_name,isbn,publisher,first_publish_year,number_of_pages_median,subject,cover_i,language",

# Line 168 (title search)
"fields": "title,author_name,isbn,publisher,first_publish_year,number_of_pages_median,subject,cover_i,language",
```

#### Step 1.3: Map Language from Google Books

**File**: `backend/app/services/book_import.py`

**Update `map_google_books()` function** (lines 372-415):

**Add after line 403** (after genre mapping):
```python
    # Language: 2-letter ISO 639-1 code (e.g., "en", "fr")
    language_code: Optional[str] = vi.get("language")
    language = _normalize_language_code(language_code) if language_code else None
```

**Update return statement** (line 405):
```python
    return BookImportCandidate(
        title=vi["title"],
        author=author,
        isbn=isbn,
        cover_url=cover_url,
        publisher=vi.get("publisher"),
        published_year=published_year,
        page_count=vi.get("pageCount"),
        genre=genre,
        language=language,  # ← ADD THIS LINE
        source="google_books",
    )
```

#### Step 1.4: Add Language Code Normalization Helper

**File**: `backend/app/services/book_import.py`

**Add helper function after `_pick_isbn()` (after line 430)**:

```python
def _normalize_language_code(code: str | None) -> str | None:
    """
    Normalize ISO 639 language codes to a human-readable format.
    
    Accepts both ISO 639-1 (2-letter) and ISO 639-2 (3-letter) codes.
    Returns the 2-letter code in uppercase for display, or None if invalid.
    
    Examples:
        "eng" → "EN"
        "en" → "EN"
        "fre" → "FR"
        "fr" → "FR"
        "spa" → "ES"
        None → None
    """
    if not code:
        return None
    
    code = code.strip().lower()
    
    # Map common 3-letter ISO 639-2 codes to 2-letter ISO 639-1
    iso_639_2_to_1 = {
        "eng": "en",
        "fre": "fr",
        "spa": "es",
        "ger": "de",
        "ita": "it",
        "por": "pt",
        "dut": "nl",
        "rus": "ru",
        "jpn": "ja",
        "chi": "zh",
        "ara": "ar",
        "hin": "hi",
    }
    
    # Convert 3-letter to 2-letter if needed
    normalized = iso_639_2_to_1.get(code, code)
    
    # Return uppercase 2-letter code for display
    if len(normalized) == 2 and normalized.isalpha():
        return normalized.upper()
    
    # Fallback: return original code if it's valid
    if len(code) <= 3 and code.isalpha():
        return code.upper()
    
    return None
```

**Rationale**:
- **Simple approach**: Display 2-letter codes instead of full language names
- **Keeps bundle size small**: No need for large language dictionaries
- **Handles both formats**: Open Library (3-letter) and Google Books (2-letter)
- **Uppercase for UI**: More professional appearance
- **Extensible**: Can be enhanced later with full names if needed

**Alternative (Full Language Names)**:
If we want full names like "English", "French", expand the mapping:
```python
def _language_name(code: str | None) -> str | None:
    language_names = {
        "en": "English",
        "fr": "French",
        "es": "Spanish",
        "de": "German",
        # ... (20-30 common languages)
    }
    normalized = _normalize_language_code(code)
    return language_names.get(normalized.lower()) if normalized else None
```

**Decision**: Start with **uppercase 2-letter codes** (simpler, less maintenance). Can be enhanced later if user feedback requests full names.

### Phase 2: Frontend UI Update

**Goal**: Display language and page count in import search result cards.

#### Step 2.1: Update TypeScript Type

**File**: `frontend/src/lib/types.ts` (or inline in ImportSearch.svelte if no separate types file)

**Add to `BookImportCandidate` type**:
```typescript
export type BookImportCandidate = {
  title: string;
  author?: string | null;
  isbn?: string | null;
  cover_url?: string | null;
  publisher?: string | null;
  published_year?: number | null;
  page_count?: number | null;
  genre?: string | null;
  language?: string | null;  // ← ADD THIS LINE
  source: string;
};
```

**Note**: If types are not in a separate file, the FastAPI schema will be inferred automatically at runtime.

#### Step 2.2: Update UI Template

**File**: `frontend/src/lib/components/ImportSearch.svelte`

**Modify result list item** (lines 243-282).

**Current layout**:
```svelte
<p class="text-xs text-base-content/40">
  {candidate.source}{candidate.published_year ? ` · ${candidate.published_year}` : ''}
</p>
```

**New layout** (replace lines 262 with extended version):
```svelte
{#if candidate.author}
  <p class="text-xs text-base-content/60">{candidate.author}</p>
{/if}
<div class="flex flex-wrap items-center gap-1.5 text-xs text-base-content/40">
  <span>{candidate.source}</span>
  {#if candidate.published_year}
    <span>·</span>
    <span>{candidate.published_year}</span>
  {/if}
  {#if candidate.language}
    <span>·</span>
    <span class="badge badge-xs badge-ghost">{candidate.language}</span>
  {/if}
  {#if candidate.page_count}
    <span>·</span>
    <span>{candidate.page_count} pages</span>
  {/if}
</div>
```

**Styling approach**:
- **Language**: Display as a badge (e.g., `EN`, `FR`) for visual prominence
  - Uses DaisyUI `badge-xs badge-ghost` for subtle styling
  - Badge makes it clear it's a category/tag
- **Page count**: Display as plain text (e.g., `412 pages`)
  - More readable for numeric data
- **Separators**: Use `·` to separate metadata items
- **Wrapping**: `flex-wrap` ensures items wrap gracefully if too wide

**Visual mockup**:
```
┌────────────────────────────────────────────┐
│ [Cover]  Dune                              │
│          Frank Herbert                     │
│          open_library · 1965 · [EN] · 412 │
│          pages                     [Add]   │
└────────────────────────────────────────────┘
```

**Alternative (more compact)**:
If space is too tight, combine into one line with icons:
```svelte
<div class="text-xs text-base-content/40">
  {candidate.source}{candidate.published_year ? ` · ${candidate.published_year}` : ''}
  {#if candidate.language}
    · 🌐 {candidate.language}
  {/if}
  {#if candidate.page_count}
    · 📄 {candidate.page_count}p
  {/if}
</div>
```

**Decision**: Use **badge for language, plain text for pages** (clearer, no emoji dependency).

#### Step 2.3: Handle Edge Cases

**Case 1: Only language available, no page count**
```svelte
{#if candidate.language}
  <span>·</span>
  <span class="badge badge-xs badge-ghost">{candidate.language}</span>
{/if}
```
Result: "open_library · 1965 · EN" ✅

**Case 2: Only page count available, no language**
```svelte
{#if candidate.page_count}
  <span>·</span>
  <span>{candidate.page_count} pages</span>
{/if}
```
Result: "open_library · 1965 · 412 pages" ✅

**Case 3: Neither available**
Result: "open_library · 1965" (same as current behavior) ✅

**Case 4: Very long metadata line (wrapping)**
- `flex-wrap` ensures items wrap to a new line if needed
- Text remains readable and not truncated

### Phase 3: Testing

#### Backend Tests

**File**: `backend/tests/test_import.py`

##### Test 3.1: map_open_library with language

**Add after `test_map_open_library_genre_capped_at_three` (line 78)**:

```python
def test_map_open_library_extracts_language():
    """Language field should be extracted from Open Library response."""
    doc = {
        "title": "Le Petit Prince",
        "author_name": ["Antoine de Saint-Exupéry"],
        "language": ["fre"],
    }
    result = book_import.map_open_library(doc)
    assert result.title == "Le Petit Prince"
    assert result.language == "FR"  # Normalized to 2-letter uppercase


def test_map_open_library_handles_missing_language():
    """Missing language field should result in None."""
    doc = {"title": "Book Without Language"}
    result = book_import.map_open_library(doc)
    assert result.language is None


def test_map_open_library_picks_first_language_from_list():
    """When multiple languages, pick the first one."""
    doc = {"title": "Multilingual Book", "language": ["eng", "spa"]}
    result = book_import.map_open_library(doc)
    assert result.language == "EN"
```

##### Test 3.2: map_google_books with language

**Add after `test_map_google_books_published_year_partial_date` (line 124)**:

```python
def test_map_google_books_extracts_language():
    """Language field should be extracted from Google Books response."""
    item = {
        "volumeInfo": {
            "title": "Foundation",
            "language": "en",
        }
    }
    result = book_import.map_google_books(item)
    assert result.language == "EN"


def test_map_google_books_handles_missing_language():
    """Missing language field should result in None."""
    item = {"volumeInfo": {"title": "No Language Book"}}
    result = book_import.map_google_books(item)
    assert result.language is None
```

##### Test 3.3: Language code normalization

**Add as a new test section after the map_google_books tests (after line 125)**:

```python
# ── _normalize_language_code unit tests ────────────────────────────────────

def test_normalize_language_code_3_letter_to_2_letter():
    """Common 3-letter ISO 639-2 codes should be converted to 2-letter."""
    assert book_import._normalize_language_code("eng") == "EN"
    assert book_import._normalize_language_code("fre") == "FR"
    assert book_import._normalize_language_code("spa") == "ES"
    assert book_import._normalize_language_code("ger") == "DE"


def test_normalize_language_code_2_letter_passthrough():
    """2-letter codes should be uppercased and passed through."""
    assert book_import._normalize_language_code("en") == "EN"
    assert book_import._normalize_language_code("fr") == "FR"
    assert book_import._normalize_language_code("es") == "ES"


def test_normalize_language_code_case_insensitive():
    """Input should be case-insensitive."""
    assert book_import._normalize_language_code("EN") == "EN"
    assert book_import._normalize_language_code("En") == "EN"
    assert book_import._normalize_language_code("eN") == "EN"
    assert book_import._normalize_language_code("ENG") == "EN"
    assert book_import._normalize_language_code("Eng") == "EN"


def test_normalize_language_code_handles_none():
    """None input should return None."""
    assert book_import._normalize_language_code(None) is None


def test_normalize_language_code_handles_empty_string():
    """Empty string should return None."""
    assert book_import._normalize_language_code("") is None
    assert book_import._normalize_language_code("   ") is None


def test_normalize_language_code_unknown_3_letter():
    """Unknown 3-letter codes should return uppercase original."""
    assert book_import._normalize_language_code("xyz") == "XYZ"


def test_normalize_language_code_invalid_format():
    """Invalid formats should return None."""
    assert book_import._normalize_language_code("123") is None
    assert book_import._normalize_language_code("e") is None
    assert book_import._normalize_language_code("english") is None
```

##### Test 3.4: Update existing test data

**Update test data** to include language field (optional, for thoroughness):

**Lines 20-29** (OPEN_LIBRARY_DUNE_DOC):
```python
OPEN_LIBRARY_DUNE_DOC = {
    "title": "Dune",
    "author_name": ["Frank Herbert"],
    "isbn": ["9780441013593", "0441013597"],
    "publisher": ["Ace Books", "Chilton Books"],
    "first_publish_year": 1965,
    "number_of_pages_median": 412,
    "subject": ["Science Fiction", "Ecology", "Fantasy"],
    "cover_i": 11481354,
    "language": ["eng"],  # ← ADD THIS LINE
}
```

**Lines 31-45** (GOOGLE_BOOKS_FOUNDATION_ITEM):
```python
GOOGLE_BOOKS_FOUNDATION_ITEM = {
    "volumeInfo": {
        "title": "Foundation",
        "authors": ["Isaac Asimov"],
        "industryIdentifiers": [
            {"type": "ISBN_13", "identifier": "9780553293357"},
            {"type": "ISBN_10", "identifier": "0553293354"},
        ],
        "publisher": "Bantam Books",
        "publishedDate": "1991",
        "pageCount": 255,
        "categories": ["Science Fiction"],
        "imageLinks": {"thumbnail": "http://books.google.com/thumbnail.jpg"},
        "language": "en",  # ← ADD THIS LINE
    }
}
```

**Update test assertions**:

**Line 59** (test_map_open_library_fields):
```python
def test_map_open_library_fields():
    result = book_import.map_open_library(OPEN_LIBRARY_DUNE_DOC)
    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    assert result.isbn == "9780441013593"
    assert result.published_year == 1965
    assert result.page_count == 412
    assert result.publisher == "Ace Books"
    assert "Science Fiction" in result.genre
    assert result.cover_url == "https://covers.openlibrary.org/b/id/11481354-L.jpg"
    assert result.language == "EN"  # ← ADD THIS LINE
    assert result.source == "open_library"
```

**Line 92** (test_map_google_books_fields):
```python
def test_map_google_books_fields():
    result = book_import.map_google_books(GOOGLE_BOOKS_FOUNDATION_ITEM)
    assert result.title == "Foundation"
    assert result.author == "Isaac Asimov"
    assert result.isbn == "9780553293357"
    assert result.publisher == "Bantam Books"
    assert result.published_year == 1991
    assert result.page_count == 255
    assert result.genre == "Science Fiction"
    assert result.cover_url == "https://books.google.com/thumbnail.jpg"
    assert result.language == "EN"  # ← ADD THIS LINE
    assert result.source == "google_books"
```

#### Frontend Tests

**Manual Testing Checklist**:

Since no automated frontend test infrastructure exists, perform manual testing:

1. **✅ Test: Language badge displays for books with language**
   - Search for "Dune" in Import tab
   - **Expected**: Result shows language badge (e.g., "EN") after published year

2. **✅ Test: Page count displays for books with page_count**
   - Search for "Foundation"
   - **Expected**: Result shows "255 pages" (or similar) after language

3. **✅ Test: Both fields display together**
   - Search for a book with both language and page count
   - **Expected**: Both fields visible with separators (e.g., "1965 · EN · 412 pages")

4. **✅ Test: Only language displays when page_count is missing**
   - Find a result without page count
   - **Expected**: Only language badge visible

5. **✅ Test: Only page count displays when language is missing**
   - Find a result without language
   - **Expected**: Only page count visible

6. **✅ Test: Neither field displays when both are missing**
   - Find a result without language or page count
   - **Expected**: Metadata line shows only source and year (current behavior)

7. **✅ Test: Layout wraps gracefully on narrow screens**
   - Resize browser to mobile width (~375px)
   - **Expected**: Metadata items wrap to new line if needed, no horizontal overflow

8. **✅ Test: Language badge styling matches DaisyUI theme**
   - Check badge appearance in light/dark mode (if theme switching exists)
   - **Expected**: Badge uses ghost variant, readable in both themes

9. **✅ Test: Search results from Open Library show language**
   - Search by title (defaults to Open Library)
   - **Expected**: Language field populated if available

10. **✅ Test: Search results from Google Books show language**
    - Perform supplemental Google Books search
    - **Expected**: Language field populated if available

#### Integration Tests (Future — Playwright)

**File**: `frontend/tests/import-metadata-display.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('Import Metadata Display', () => {
  test('should display language badge for books with language', async ({ page }) => {
    await page.goto('/');
    await page.click('text=Import Book');
    await page.fill('input[placeholder*="Search"]', 'Dune');
    await page.click('button:has-text("Search")');
    
    await page.waitForSelector('text=Dune');
    
    // Check for language badge (e.g., EN)
    const badge = page.locator('.badge:has-text("EN")').first();
    await expect(badge).toBeVisible();
  });

  test('should display page count when available', async ({ page }) => {
    await page.goto('/');
    await page.click('text=Import Book');
    await page.fill('input[placeholder*="Search"]', 'Foundation');
    await page.click('button:has-text("Search")');
    
    await page.waitForSelector('text=Foundation');
    
    // Check for page count
    const pageCount = page.locator('text=/\\d+ pages/').first();
    await expect(pageCount).toBeVisible();
  });

  test('should handle missing language gracefully', async ({ page }) => {
    // Assumes there's a book without language in test data
    await page.goto('/');
    await page.click('text=Import Book');
    await page.fill('input[placeholder*="Search"]', 'book-without-language');
    await page.click('button:has-text("Search")');
    
    await page.waitForTimeout(2000);
    
    // Badge should not be present
    const badge = page.locator('.badge');
    await expect(badge).not.toBeVisible();
  });

  test('should handle missing page count gracefully', async ({ page }) => {
    // Assumes there's a book without page count
    await page.goto('/');
    await page.click('text=Import Book');
    await page.fill('input[placeholder*="Search"]', 'book-without-pages');
    await page.click('button:has-text("Search")');
    
    await page.waitForTimeout(2000);
    
    // "pages" text should not be present
    const pageText = page.locator('text=/\\d+ pages/');
    await expect(pageText).not.toBeVisible();
  });
});
```

### Phase 4: Documentation and Cleanup

#### Step 4.1: Update API Documentation

**File**: `backend/app/schemas.py` (docstring update)

**Update `BookImportCandidate` docstring**:
```python
class BookImportCandidate(SQLModel):
    """
    A book result from an external API, not yet persisted locally.
    
    Fields:
        - language: ISO 639-1/639-2 code (e.g., 'EN', 'FR') or None if unavailable
        - page_count: Number of pages, may be None for some results
    """
```

#### Step 4.2: Add Inline Comments

**File**: `backend/app/services/book_import.py`

**Add comment above Open Library search fields**:
```python
# Request language field for UI display (returns ISO 639-2 codes)
"fields": "title,author_name,isbn,publisher,first_publish_year,number_of_pages_median,subject,cover_i,language",
```

**Add comment in mapping functions**:
```python
# Language: Normalize to 2-letter uppercase code for display (e.g., "EN", "FR")
language = _normalize_language_code(languages[0]) if languages else None
```

#### Step 4.3: Update README (Optional)

**File**: `README.md`

**If there's a features section**, add:
```markdown
### Import Features
- Search books by title or ISBN
- Import from Open Library and Google Books
- Display book metadata: author, year, **language**, **page count**
- Visual indicators for already-imported books
```

## Edge Cases and Considerations

### Edge Case 1: Multiple Languages in Open Library

**Problem**: Open Library returns `"language": ["eng", "spa"]` for bilingual books.

**Current behavior**: We pick the first entry (`languages[0]`).

**Alternative**: Display both (e.g., `"EN, ES"`)?

**Decision**: **Pick first only** for initial implementation.

**Rationale**:
- Simpler UI
- Most books have a single primary language
- Can be enhanced later if user feedback requests it

**Future enhancement**:
```python
# Map multiple languages
languages_list = [_normalize_language_code(lang) for lang in languages[:2]]
language = ", ".join(filter(None, languages_list)) if languages_list else None
```

### Edge Case 2: Invalid or Unrecognized Language Codes

**Problem**: API returns invalid or rare language codes (e.g., `"xx"`, `"zxx"`).

**Current behavior**: `_normalize_language_code()` returns the uppercase code as-is if it's alphabetic.

**Example**:
- Input: `"zxx"` (Open Library code for "no linguistic content")
- Output: `"ZXX"`

**Impact**: Badge displays `"ZXX"` — not ideal but not breaking.

**Decision**: **Accept and display** — rare edge case, not worth complex filtering.

**Future enhancement**: Blacklist specific codes:
```python
IGNORED_CODES = {"zxx", "und", "mul"}  # No content, undetermined, multiple
if code.lower() in IGNORED_CODES:
    return None
```

### Edge Case 3: Very Long Language Codes

**Problem**: Malformed data returns a long string instead of a code.

**Current behavior**: `_normalize_language_code()` checks `len(code) <= 3` and `isalpha()`.

**Impact**: Invalid codes return `None` → no badge displayed.

**Decision**: **Safe default** — better to hide invalid data than display garbage.

### Edge Case 4: Page Count Formatting

**Problem**: How to format page count? `"412 pages"`, `"412p"`, or `"412 pp."`?

**Current decision**: `"{page_count} pages"` (most readable).

**Alternative**: Abbreviate if space is tight:
```svelte
{candidate.page_count}p
```

**Decision**: Start with **full word** (`"pages"`). Can abbreviate later if feedback indicates space issues.

### Edge Case 5: Inconsistent Data Across Sources

**Problem**: Same book from Open Library vs. Google Books may have different language/page count.

**Example**:
- Open Library: `language: ["eng"]`, `page_count: 412`
- Google Books: `language: "en"`, `page_count: 410`

**Impact**: User sees slightly different metadata depending on source.

**Decision**: **Accept as-is** — reflects actual API data, user can see source field.

**Future enhancement**: Merge/deduplicate results and pick best metadata values.

### Edge Case 6: Missing Page Count in Google Books

**Problem**: Google Books sometimes omits `pageCount` for obscure or self-published books.

**Current behavior**: `page_count: null` → not displayed.

**Decision**: **Working as intended** — conditional rendering handles this gracefully.

## Implementation Steps Summary

| Step | Description | File(s) | Estimated Time |
|------|-------------|---------|----------------|
| 1.1  | Update `BookImportCandidate` schema | `backend/app/schemas.py` | 5 min |
| 1.2  | Map language from Open Library | `backend/app/services/book_import.py` | 15 min |
| 1.3  | Map language from Google Books | `backend/app/services/book_import.py` | 10 min |
| 1.4  | Add language normalization helper | `backend/app/services/book_import.py` | 20 min |
| 2.1  | Update frontend TypeScript types | `frontend/src/lib/types.ts` or inline | 5 min |
| 2.2  | Update UI template | `frontend/src/lib/components/ImportSearch.svelte` | 20 min |
| 3.1  | Add backend tests (map_open_library) | `backend/tests/test_import.py` | 15 min |
| 3.2  | Add backend tests (map_google_books) | `backend/tests/test_import.py` | 10 min |
| 3.3  | Add backend tests (language normalization) | `backend/tests/test_import.py` | 25 min |
| 3.4  | Update existing test data | `backend/tests/test_import.py` | 10 min |
| 4.1  | Manual frontend testing | Browser | 20 min |
| 4.2  | Documentation updates | Various | 10 min |
| **Total** | | | **~2h 45m** |

## Success Criteria

1. ✅ `BookImportCandidate` schema includes `language` field
2. ✅ Open Library results populate `language` field when available
3. ✅ Google Books results populate `language` field when available
4. ✅ Language codes are normalized to 2-letter uppercase format
5. ✅ Import search results display language badge when available
6. ✅ Import search results display page count when available
7. ✅ Missing language field does not break UI
8. ✅ Missing page_count field does not break UI
9. ✅ All existing backend tests pass
10. ✅ New backend tests for language mapping pass
11. ✅ Manual frontend tests confirm correct rendering

## Testing Coverage

### Backend Tests (Added)
- `test_map_open_library_extracts_language`
- `test_map_open_library_handles_missing_language`
- `test_map_open_library_picks_first_language_from_list`
- `test_map_google_books_extracts_language`
- `test_map_google_books_handles_missing_language`
- `test_normalize_language_code_3_letter_to_2_letter`
- `test_normalize_language_code_2_letter_passthrough`
- `test_normalize_language_code_case_insensitive`
- `test_normalize_language_code_handles_none`
- `test_normalize_language_code_handles_empty_string`
- `test_normalize_language_code_unknown_3_letter`
- `test_normalize_language_code_invalid_format`

**Total new tests**: 12

### Frontend Tests (Manual)
- 10 manual test cases (see Phase 3, Frontend Tests)

## Rollback Plan

If issues arise:

**Backend rollback**:
1. Remove `language: Optional[str]` from `BookImportCandidate` (schemas.py)
2. Remove language mapping lines from `map_open_library()` and `map_google_books()`
3. Remove `_normalize_language_code()` helper function
4. Remove added backend tests

**Frontend rollback**:
1. Remove `language?: string | null` from TypeScript type
2. Revert UI template to original version (before language/page count display)

**Rollback complexity**: Low — all changes are localized to 2 backend files and 1 frontend component.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Invalid language codes display as ugly badges | Low | Low | Normalize codes, return None for invalid formats |
| API returns unexpected language format | Low | Medium | Test with monkeypatch for edge cases, graceful None fallback |
| Layout breaks on narrow screens | Low | Low | Use `flex-wrap` for responsive wrapping |
| Page count formatting unclear | Low | Low | Use full word ("pages") for clarity |
| Cluttered UI with too much metadata | Medium | Low | Use subtle styling (badge-ghost, small text) |
| Language field missing from API response | Medium | Low | Conditional rendering — field simply not shown |

## Future Enhancements

1. **Full language names**: Display "English" instead of "EN"
   - Requires language dictionary (~50KB bundle size increase)
   - Or use browser `Intl.DisplayNames` API (requires fallback for old browsers)

2. **Multiple languages**: Display all languages for bilingual books
   - e.g., "EN, ES" instead of just "EN"

3. **Page count icons**: Add 📖 icon for visual clarity
   - Alternative to text-only display

4. **Tooltips**: Hover over language badge to see full name
   - e.g., Badge shows "EN", tooltip shows "English"

5. **Filtering by language**: Add language filter dropdown in search UI

6. **Store language in local database**: Add `language` field to `Book` model
   - Useful for future features (collection stats, filtering)

## Dependencies

**No new dependencies required.**

Uses existing:
- Pydantic/SQLModel for schema updates
- Svelte 5 conditional rendering (`{#if}`)
- DaisyUI badge component (already in use)
- Existing test infrastructure (pytest, TestClient)

## Conclusion

This implementation extends the import search UI with two key metadata fields — **language** and **page count** — by:

1. **Backend**: Extracting language from Open Library and Google Books APIs, normalizing codes to 2-letter uppercase format
2. **Frontend**: Displaying both fields conditionally using badges and plain text
3. **Testing**: Adding comprehensive backend unit tests and manual frontend validation
4. **Graceful degradation**: Ensuring missing fields don't break the UI

The approach prioritizes **simplicity** (uppercase codes instead of full names), **consistency** (follows existing patterns), and **robustness** (handles edge cases gracefully). Future enhancements can add full language names, multiple language support, and filtering capabilities based on user feedback.
