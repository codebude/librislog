# Summary: Display Language and Page Count in Import Search Results

## Quick Overview

Add two new metadata fields to import search result cards:
- **Language** (ISO code badge, e.g., "EN", "FR")
- **Number of pages** (plain text, e.g., "412 pages")

Both fields display conditionally — only shown when data is available.

## What's Being Built

**Feature**: Extend import search UI to show language and page count alongside existing metadata (author, year, source).

**User Experience**:
- Search results show language as a small badge (e.g., `EN`)
- Page count appears as plain text (e.g., `412 pages`)
- Missing fields are gracefully hidden (no empty placeholders)

**Visual mockup**:
```
┌────────────────────────────────────────┐
│ [Cover] Dune                           │
│         Frank Herbert                  │
│         open_library · 1965 · EN ·     │
│         412 pages              [Add]   │
└────────────────────────────────────────┘
```

## Implementation Approach

### Backend Changes

**1. Schema Update** (`backend/app/schemas.py`):
```python
class BookImportCandidate(SQLModel):
    # ... existing fields ...
    language: Optional[str] = None  # ← NEW: 2-letter ISO code (e.g., "EN")
    source: str
```

**2. Map Language from Open Library** (`backend/app/services/book_import.py`):
- Extract `language` field from API response (returns 3-letter ISO 639-2 codes)
- Normalize to 2-letter uppercase code using new helper function
- Example: `["eng"]` → `"EN"`

**3. Map Language from Google Books** (`backend/app/services/book_import.py`):
- Extract `language` field (already 2-letter ISO 639-1 code)
- Normalize to uppercase
- Example: `"en"` → `"EN"`

**4. Add Normalization Helper**:
```python
def _normalize_language_code(code: str | None) -> str | None:
    """
    Convert ISO 639 codes (2 or 3 letter) to uppercase 2-letter format.
    Examples: "eng" → "EN", "en" → "EN", "fre" → "FR"
    """
    # Maps common 3-letter → 2-letter codes
    # Returns uppercase 2-letter code or None
```

### Frontend Changes

**File**: `frontend/src/lib/components/ImportSearch.svelte`

**Update UI template** (lines 243-282):
```svelte
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

**Styling**:
- Language: DaisyUI badge (subtle, visually distinct)
- Page count: Plain text (readable, no clutter)
- Separators: `·` between items
- Wrapping: `flex-wrap` for responsive layout

## Key Files Modified

| File | Changes | LOC Added |
|------|---------|-----------|
| `backend/app/schemas.py` | Add `language` field to `BookImportCandidate` | 1 |
| `backend/app/services/book_import.py` | • Add `_normalize_language_code()` helper<br>• Map language in `map_open_library()`<br>• Map language in `map_google_books()`<br>• Update search field lists | ~60 |
| `frontend/src/lib/components/ImportSearch.svelte` | Update result card template | ~10 |
| `backend/tests/test_import.py` | • Add 12 new test cases<br>• Update existing test data | ~100 |

**Total LOC**: ~170 lines (including tests)

## Testing Strategy

### Backend Tests (12 new tests)
1. ✅ `test_map_open_library_extracts_language`
2. ✅ `test_map_open_library_handles_missing_language`
3. ✅ `test_map_open_library_picks_first_language_from_list`
4. ✅ `test_map_google_books_extracts_language`
5. ✅ `test_map_google_books_handles_missing_language`
6. ✅ `test_normalize_language_code_3_letter_to_2_letter`
7. ✅ `test_normalize_language_code_2_letter_passthrough`
8. ✅ `test_normalize_language_code_case_insensitive`
9. ✅ `test_normalize_language_code_handles_none`
10. ✅ `test_normalize_language_code_handles_empty_string`
11. ✅ `test_normalize_language_code_unknown_3_letter`
12. ✅ `test_normalize_language_code_invalid_format`

### Frontend Tests (10 manual tests)
1. ✅ Language badge displays when available
2. ✅ Page count displays when available
3. ✅ Both fields display together correctly
4. ✅ Only language displays when page count missing
5. ✅ Only page count displays when language missing
6. ✅ Neither displays when both missing
7. ✅ Layout wraps gracefully on narrow screens
8. ✅ Badge styling matches theme
9. ✅ Open Library results show language
10. ✅ Google Books results show language

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Multiple languages in Open Library | Pick first only (e.g., `["eng", "spa"]` → `"EN"`) |
| Invalid language code | Return `None`, hide badge |
| Long language string (malformed data) | Validate length/format, return `None` |
| Missing language field | ✅ Conditional rendering hides field |
| Missing page_count field | ✅ Conditional rendering hides field |
| Open Library 3-letter code | ✅ Normalize to 2-letter (e.g., `"eng"` → `"EN"`) |
| Google Books 2-letter code | ✅ Uppercase (e.g., `"en"` → `"EN"`) |
| Inconsistent data across sources | ✅ Display as-is from each source |

## Data Mapping Examples

### Open Library
**API Response**:
```json
{
  "title": "Dune",
  "language": ["eng"],
  "number_of_pages_median": 412
}
```
**Mapped Result**:
```python
BookImportCandidate(
    title="Dune",
    language="EN",    # Normalized from "eng"
    page_count=412,   # Already available
)
```

### Google Books
**API Response**:
```json
{
  "volumeInfo": {
    "title": "Foundation",
    "language": "en",
    "pageCount": 255
  }
}
```
**Mapped Result**:
```python
BookImportCandidate(
    title="Foundation",
    language="EN",   # Uppercased from "en"
    page_count=255,  # Already available
)
```

## Language Code Normalization

**Common Mappings**:
```
3-letter (ISO 639-2) → 2-letter (ISO 639-1)
───────────────────────────────────────────
eng → EN
fre → FR
spa → ES
ger → DE
ita → IT
por → PT
jpn → JA
chi → ZH
```

**Input Handling**:
- Case-insensitive: `"EN"`, `"en"`, `"eN"` → `"EN"`
- Strips whitespace
- Returns `None` for invalid formats (non-alphabetic, wrong length)

## Success Criteria

1. ✅ Schema includes `language` field
2. ✅ Open Library results populate language
3. ✅ Google Books results populate language
4. ✅ Language codes normalized to 2-letter uppercase
5. ✅ UI displays language badge when available
6. ✅ UI displays page count when available
7. ✅ Missing fields don't break UI
8. ✅ All backend tests pass
9. ✅ Manual frontend tests pass
10. ✅ Layout responsive on mobile

## Implementation Time

| Phase | Tasks | Time |
|-------|-------|------|
| **Backend** | Schema + mapping + helper + API fields | 50 min |
| **Frontend** | Type update + UI template | 25 min |
| **Backend Tests** | 12 new tests + update existing | 60 min |
| **Frontend Tests** | Manual testing | 20 min |
| **Documentation** | Comments + README | 10 min |
| **Total** | | **~2h 45m** |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Invalid language codes | Validate format, return None for invalid |
| API format changes | Monkeypatch tests catch schema mismatches |
| UI clutter | Use subtle styling (ghost badge, small text) |
| Layout breaks on narrow screens | flex-wrap for responsive wrapping |
| Missing data from APIs | Conditional rendering hides missing fields |

## Future Enhancements

1. **Full language names**: Display "English" instead of "EN"
   - Use `Intl.DisplayNames` API or language dictionary
2. **Multiple languages**: Show all languages for bilingual books (e.g., "EN, ES")
3. **Tooltips**: Hover over badge to see full language name
4. **Filtering**: Add language filter dropdown in search UI
5. **Store in database**: Add `language` field to `Book` model for collection stats

## Dependencies

**None** — uses existing:
- Pydantic/SQLModel for schema
- Svelte 5 conditional rendering
- DaisyUI badge component
- pytest for backend tests

## Rollback

**Simple rollback** (all changes localized):

**Backend**:
1. Remove `language` field from `BookImportCandidate`
2. Remove language mapping lines
3. Remove `_normalize_language_code()` helper
4. Remove added tests

**Frontend**:
1. Remove `language` from type
2. Revert UI template to original

**Rollback time**: < 15 minutes

---

**Status**: Ready for implementation  
**Complexity**: Low-Medium  
**Risk**: Low  
**Value**: Medium (improves UX, provides useful metadata)
