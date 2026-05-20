# Plan 57: Hardcover.app as Third Import Datasource

## 1. Overview

Add hardcover.app as a third import datasource that runs **in parallel** with Open Library (not as a fallback like Google Books) when the user has configured `HARDCOVER_APP_API_TOKEN` in their `.env`.

The hardcover.app API is GraphQL-based at `https://api.hardcover.app/v1/graphql` with Bearer token auth. For title searches, a two-step flow is required: first a `search` query to discover ISBNs, then a `book_mappings` query to get full book metadata. For ISBN searches, only the `book_mappings` query is needed.

Results from hardcover.app are **merged** with Open Library results (deduplication by ISBN, then title+author), with OL results appearing first.

Within hardcover's own results, deduplication uses a **composite key of (ISBN, page_count, language)**. The same ISBN appearing with different page counts or languages is treated as separate candidates (they likely represent different editions).

---

## 2. File-by-file Changes

### 2.1 `backend/app/config.py` — Already Done

The setting already exists at line 40:

```python
hardcover_app_api_token: str = ""
```

No changes needed.

### 2.2 `backend/app/schemas.py` — No Changes Needed

`BookImportCandidate.source` is already a free-form `str` field. The value `"hardcover"` will be used without requiring any schema changes.

The docstring on line 79 can be updated to document the new source:

```python
source: str  # "open_library" | "google_books" | "hardcover"
```

No code change strictly required, but nice to have.

### 2.3 `backend/app/services/book_import.py` — Major Changes

This is the core file. Changes are substantial.

#### 2.3.1 Add Constants (after line 28)

```python
HARDCOVER_GRAPHQL_URL = "https://api.hardcover.app/v1/graphql"
```

#### 2.3.2 Add `_search_hardcover()` function (after `_search_google_books`)

Implement a new private async function `_search_hardcover()` that:

1. For `search_type == "title"`:
   - Calls the `search` GraphQL query with the user's query string
   - Extracts ISBNs from `hits[0].document.isbns` (array of ISBN-10 and ISBN-13 strings)
   - Normalizes each to ISBN-13 (using `_normalize_isbn` from cover_candidates — see 2.4)
   - Collects up to ~10 unique ISBN-13 values
   - Calls `book_mappings` query with `{isbn_13: {_in: [...]}}` to get full book info
   - Maps each result to `BookImportCandidate`

2. For `search_type == "isbn"`:
   - Normalizes to ISBN-13 (using `_normalize_isbn`)
   - Calls `book_mappings` query directly with `{isbn_13: {_eq: "<normalized_isbn13>"}}`
   - Maps result to `BookImportCandidate`

Key implementation details:

```python
async def _search_hardcover(
    query: str,
    search_type: str,
    api_token: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    """Search hardcover.app via GraphQL."""
    if not api_token.strip():
        return []

    try:
        if search_type == "title":
            # Step 1: search query → get ISBNs
            isbn13s = await _hardcover_search_title(query, api_token, client)
            if not isbn13s:
                return []
            # Step 2: book_mappings query → get full book info
            return await _hardcover_fetch_books(isbn13s, api_token, client)
        else:  # isbn
            try:
                isbn13 = _normalize_isbn(query)
            except HTTPException:
                logger.warning("hardcover invalid ISBN: %s", query)
                return []
            return await _hardcover_fetch_books([isbn13], api_token, client)
    except Exception as exc:
        logger.warning("hardcover search failed for %r: %s", query, exc)
        return []
```

Two helper functions:

**`_hardcover_search_title()`** — Sends the `search` GraphQL query:

```python
SEARCH_QUERY = """
query SearchQuery($q: String!) {
  search(limit: 1, where: {documents: {}}, query: $q) {
    hits {
      document {
        isbns
      }
    }
  }
}
"""
```

Extracts ISBNs, normalizes each to ISBN-13, deduplicates, returns up to 10.

**`_hardcover_fetch_books()`** — Sends the `book_mappings` query:

```python
BOOK_MAPPINGS_QUERY = """
query BookMappingsQuery($where: book_mappings_bool_exp!) {
  book_mappings(limit: 10, where: $where) {
    edition {
      title
      subtitle
      isbn_13
      pages
      release_date
      image { url }
      publisher { name }
      language { code2 }
      book {
        description
        taggings {
          tag { tag }
        }
      }
      contributions {
        author { name }
        role
      }
    }
  }
}
"""
```

**Intra-source deduplication**: The `book_mappings` response may contain multiple editions for the same ISBN (e.g., different formats). Deduplicate using a **composite key of `(isbn_13, pages, language.code2)`**. Only strip true duplicates — same ISBN with different page count or language is kept as a separate candidate. Use a `_hardcover_dedup_key(edition: dict) -> tuple` helper for this.

#### 2.3.3 Add `map_hardcover()` function

Maps a hardcover GraphQL `edition` node to `BookImportCandidate`:

```python
def map_hardcover(edition: dict) -> BookImportCandidate | None:
    """Map a hardcover edition node to BookImportCandidate."""
    title = edition.get("title")
    if not title:
        return None

    # Author: first contribution where role is author or role is unset
    contributions = edition.get("contributions") or []
    author = None
    for c in contributions:
        role = (c.get("role") or "").lower()
        if role in ("author", "") and c.get("author", {}).get("name"):
            author = c["author"]["name"]
            break

    # ISBN: prefer isbn_13, but also accept isbn_10 if necessary
    isbn = edition.get("isbn_13") or None

    # Cover URL: validate with is_safe_cover_import_url
    image = edition.get("image") or {}
    raw_cover_url = image.get("url")
    cover_url = None
    if raw_cover_url and is_safe_cover_import_url(raw_cover_url):
        cover_url = raw_cover_url

    # Publisher
    publisher = (edition.get("publisher") or {}).get("name") or None

    # Published year
    release_date = edition.get("release_date") or ""
    published_year = None
    if len(release_date) >= 4:
        try:
            published_year = int(release_date[:4])
        except ValueError:
            pass

    # Page count
    page_count = edition.get("pages") or None

    # Language: code2 is ISO 639-1
    language = (edition.get("language") or {}).get("code2") or None
    if language:
        language = language.upper()

    # Tags: first 3 from taggings
    taggings = edition.get("book", {}).get("taggings") or []
    tags_list = [t["tag"]["tag"] for t in taggings if t.get("tag", {}).get("tag")][:3]
    tags = ", ".join(tags_list) if tags_list else None

    # Description
    blurb = edition.get("book", {}).get("description") or None

    return BookImportCandidate(
        title=title,
        subtitle=edition.get("subtitle") or None,
        author=author,
        isbn=isbn,
        cover_url=cover_url,
        publisher=publisher,
        published_year=published_year,
        page_count=page_count,
        language=language,
        tags=tags,
        blurb=blurb,
        source="hardcover",
    )
```

#### 2.3.4 Add `_merge_and_deduplicate()` helper

```python
def _merge_and_deduplicate(
    primary: list[BookImportCandidate],
    secondary: list[BookImportCandidate],
) -> list[BookImportCandidate]:
    """Merge two candidate lists, deduplicating by (isbn, page_count, language).
    Primary list items come first in the result.
    Same ISBN with different page_count/language → kept as separate candidates."""
    seen = set()
    result: list[BookImportCandidate] = []

    def _key(c: BookImportCandidate) -> str:
        isbn = (c.isbn or "").replace("-", "").replace(" ", "")
        pages = str(c.page_count or "")
        lang = (c.language or "").upper()
        return f"isbn:{isbn}|pages:{pages}|lang:{lang}"

    for c in primary + secondary:
        k = _key(c)
        if k not in seen:
            seen.add(k)
            result.append(c)

    return result
```

#### 2.3.5 Modify `search_with_progress()` — The Key Change

The function needs to be restructured so that hardcover runs **in parallel** with Open Library when the token is configured.

Current flow (simplified):
```
OL search → if no OL results → Google fallback → complete
```

New flow:
```
Parallel:  ┌─ OL search ─┐
           └─ HC search ─┘  (when token set)
Merge results (OL first)
If no OL+HC results → Google fallback → complete
```

Implementation sketch:

```python
async def search_with_progress(
    query: str,
    search_type: str,
    *,
    api_key: str = "",
    hardcover_api_token: str = "",
    mode: Literal["auto", "google_only"] = "auto",
    http_client: Optional[httpx.AsyncClient] = None,
) -> AsyncGenerator[dict, None]:
    ...
    try:
        ol_results: list[BookImportCandidate] = []
        hc_results: list[BookImportCandidate] = []
        gb_results: list[BookImportCandidate] = []

        if mode == "google_only":
            # Unchanged: Google-only still works as before
            ...
        else:
            # --- Parallel: OL + Hardcover ---
            tasks = []

            # Open Library task
            async def _do_ol():
                yield {"stage": "open_library", "status": "searching"}
                try:
                    r = await _search_open_library(query, search_type, client)
                    yield {"stage": "open_library", "status": "done", "count": len(r)}
                    return r
                except SourceBackendError as exc:
                    yield {"stage": "open_library", "status": "error", "reason": "backend_error"}
                    return []

            # Hardcover task (only when token is configured)
            async def _do_hc():
                if not hardcover_api_token.strip():
                    yield {"stage": "hardcover", "status": "skipped", "reason": "no_api_token"}
                    return []
                yield {"stage": "hardcover", "status": "searching"}
                try:
                    r = await _search_hardcover(query, search_type, hardcover_api_token, client)
                    yield {"stage": "hardcover", "status": "done", "count": len(r)}
                    return r
                except Exception:
                    logger.exception("hardcover search error")
                    yield {"stage": "hardcover", "status": "error", "reason": "backend_error"}
                    return []

            # Run both in parallel, collecting events and results
            ol_events: list[dict] = []
            hc_events: list[dict] = []
            ol_result: list[BookImportCandidate] = []
            hc_result: list[BookImportCandidate] = []

            async def _run_ol():
                nonlocal ol_result, ol_events
                async for event in _do_ol():
                    if isinstance(event, dict) and "stage" in event:
                        ol_events.append(event)
                    else:
                        ol_result = event  # last yielded value is the result
            # Actually, since async generators can't return values easily,
            # we use a different pattern: collect events and use a shared list for results

            # Better approach: wrap each source in a task that returns (events, results)
            ...

```

**Simpler recommended approach**: Use `asyncio.gather()` with wrapper coroutines that emit events via a shared callback or queue, then yield those events.

Even simpler: use a pattern where each source search is wrapped in a coroutine that returns `(events, results)`, then run them with `asyncio.gather()`:

```python
async def _search_source(
    source_name: str,
    search_fn,
    *args,
    **kwargs,
) -> tuple[list[dict], list[BookImportCandidate]]:
    events = []
    results = []
    try:
        events.append({"stage": source_name, "status": "searching"})
        results = await search_fn(*args, **kwargs)
        events.append({"stage": source_name, "status": "done", "count": len(results)})
    except SourceBackendError as exc:
        events.append({"stage": source_name, "status": "error", "reason": "backend_error"})
    return events, results

# In search_with_progress:
ol_task = _search_source("open_library", _search_open_library, query, search_type, client)
hc_task = None
if hardcover_api_token.strip():
    hc_task = _search_source("hardcover", _search_hardcover, query, search_type, hardcover_api_token, client)

if hc_task:
    (ol_events, ol_results), (hc_events, hc_results) = await asyncio.gather(ol_task, hc_task)
    # Yield OL events first, then HC events
    for e in ol_events:
        yield e
    for e in hc_events:
        yield e
    results = _merge_and_deduplicate(ol_results, hc_results)
else:
    (ol_events, ol_results) = await ol_task
    for e in ol_events:
        yield e
    results = ol_results
```

Then the Google Books fallback logic follows (only when `results` is empty and mode is `auto`):

```python
if not results and mode == "auto":
    if not api_key:
        yield {"stage": "google_books", "status": "skipped", "reason": "no_api_key"}
    else:
        yield {"stage": "google_books", "status": "searching"}
        try:
            gb_results = await _search_google_books(query, search_type, api_key, client)
            yield {"stage": "google_books", "status": "done", "count": len(gb_results)}
            results = gb_results
        except SourceBackendError as exc:
            yield {"stage": "google_books", "status": "error", "reason": "backend_error"}

yield {"stage": "complete", "results": [r.model_dump() for r in results]}
```

#### 2.3.6 Modify `search()` — Simple Non-Streaming Version

The simple `search()` function should also run hardcover in parallel with OL:

```python
async def search(
    query: str,
    search_type: str,
    *,
    api_key: str = "",
    hardcover_api_token: str = "",
    http_client: Optional[httpx.AsyncClient] = None,
) -> list[BookImportCandidate]:
    ...
    # Parallel OL + HC
    tasks = [_search_open_library(query, search_type, client)]
    if hardcover_api_token.strip():
        tasks.append(_search_hardcover(query, search_type, hardcover_api_token, client))

    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    ol_results = results_list[0] if not isinstance(results_list[0], Exception) else []
    hc_results = results_list[1] if len(results_list) > 1 and not isinstance(results_list[1], Exception) else []

    results = _merge_and_deduplicate(ol_results, hc_results)

    # Google fallback
    if not results:
        ...  # same fallback logic as before

    return results
```

### 2.4 `backend/app/routers/import_.py` — Plumbing Changes

The import router needs to pass the hardcover token through.

#### 2.4.1 Update `GET /api/import/search` (line 43-59)

Add `hardcover_api_token` parameter to `book_import.search()` call:

```python
results = await book_import.search(
    q,
    type,
    api_key=settings.google_books_api_key,
    hardcover_api_token=settings.hardcover_app_api_token,
    http_client=client,
)
```

#### 2.4.2 Update `GET /api/import/search/stream` (line 62-90)

Add `hardcover_api_token` parameter:

```python
async for event in book_import.search_with_progress(
    q,
    type,
    api_key=settings.google_books_api_key,
    hardcover_api_token=settings.hardcover_app_api_token,
    mode=mode,
    http_client=client,
):
    yield f"data: {json.dumps(event)}\n\n"
```

The `mode` query parameter should also accept `"hardcover"` mode if needed. Update the type hint:

```python
mode: Literal["auto", "google_only"] = Query(default="auto"),
```

No change needed to the `Literal` — the `"hardcover"` mode is not a separate mode; hardcover always runs in parallel with OL when configured. But consider if we want to add a `mode` that only searches hardcover. The requirements say it should run **in parallel with OpenLibrary always when configured**, so no separate mode is needed. But adding `"hardcover_only"` could be useful later.

### 2.5 `backend/app/services/__init__.py` — No Changes

The package init likely just exports `book_import`. No changes needed unless we want to explicitly export the new functions.

### 2.6 `frontend/src/lib/types.ts` — Add Hardcover to SearchStage

Add hardcover stage variants to the `SearchStage` union type:

```typescript
export type SearchStage =
    | { stage: 'open_library'; status: 'searching' }
    | { stage: 'open_library'; status: 'done'; count: number }
    | { stage: 'open_library'; status: 'error'; reason: string }
    | { stage: 'hardcover'; status: 'searching' }
    | { stage: 'hardcover'; status: 'done'; count: number }
    | { stage: 'hardcover'; status: 'skipped'; reason: string }
    | { stage: 'hardcover'; status: 'error'; reason: string }
    | { stage: 'google_books'; status: 'searching' }
    | { stage: 'google_books'; status: 'done'; count: number }
    | { stage: 'google_books'; status: 'skipped'; reason: string }
    | { stage: 'google_books'; status: 'error'; reason: string }
    | { stage: 'complete'; results: BookImportCandidate[] }
    | { stage: 'error'; message: string };
```

### 2.7 `frontend/src/lib/components/ImportSearch.svelte` — Render Hardcover Stage

#### 2.7.1 Update `stageLabel()` function

Add a branch for `s.stage === 'hardcover'`:

```typescript
function stageLabel(s: SearchStage): string {
    if (s.stage === 'open_library') {
        if (s.status === 'searching') return $_('import.sourceOpenLibrarySearching');
        if ('reason' in s) return $_('import.sourceBackendError', { values: { source: 'Open Library' } });
        return $_('import.resultCount', {
            values: { source: 'Open Library', count: s.count, suffix: s.count === 1 ? '' : 's' }
        });
    }
    if (s.stage === 'hardcover') {
        if (s.status === 'searching') return $_('import.sourceHardcoverSearching');
        if (s.status === 'skipped') return $_('import.sourceHardcoverSkipped');
        if ('reason' in s) return $_('import.sourceBackendError', { values: { source: 'Hardcover' } });
        return $_('import.resultCount', {
            values: { source: 'Hardcover', count: s.count, suffix: s.count === 1 ? '' : 's' }
        });
    }
    // ... google_books and error branches unchanged
}
```

#### 2.7.2 Update `stageIcon()` function

Add a branch:

```typescript
if (s.stage === 'hardcover') {
    if (s.status === 'searching') return '◌';
    if (s.status === 'skipped') return '—';
    if ('reason' in s) return '!';
    return '✓';
}
```

#### 2.7.3 Update `stageClass()` function

Add analogous handling for hardcover stage classes.

### 2.8 `frontend/src/lib/i18n/locales/en.json` — Add Translation Keys

Add under `"import"`:

```json
"sourceHardcoverSearching": "Searching Hardcover...",
"sourceHardcoverSkipped": "Hardcover skipped (no API token configured)",
```

### 2.9 `frontend/src/lib/i18n/locales/de.json` — Add German Translations

```json
"sourceHardcoverSearching": "Durchsuche Hardcover...",
"sourceHardcoverSkipped": "Hardcover übersprungen (kein API-Token konfiguriert)",
```

---

## 3. New `search_with_progress` Flow Diagram

```
search_with_progress(query, search_type, api_key, hardcover_api_token, mode)
│
├─ mode == "google_only"?
│   └─ YES → run Google Books only (unchanged from current behavior)
│
└─ mode == "auto" (default)
    │
    ├─ Launch PARALLEL tasks:
    │   │
    │   ├─ Task A: _search_open_library()
    │   │   └─ Yields: {open_library, searching} → {open_library, done, count=N}
    │   │
    │   └─ Task B: _search_hardcover()  (only if token is non-empty)
    │       └─ Yields: {hardcover, searching} → {hardcover, done, count=N}
    │               OR {hardcover, skipped, reason="no_api_token"}
    │               OR {hardcover, error, reason="backend_error"}
    │
    ├─ await asyncio.gather(Task A, Task B)   ← PARALLEL EXECUTION
    │
    ├─ Yield events in order: OL first, then HC
    │
    ├─ results = merge_and_deduplicate(ol_results, hc_results)
    │   (OL items first, then HC items not already present)
    │
    ├─ No results AND api_key is set?
    │   └─ YES → Fallback to Google Books (unchanged)
    │       Yields: {google_books, searching} → {google_books, done, count=N}
    │            OR {google_books, skipped, reason="no_api_key"}
    │
    └─ Yield: {complete, results=[...]}
```

### Stream Endpoint Event Sequence Example (auto mode, token configured):

```
1. {open_library, searching}
2. {hardcover, searching}         ← note: ordering depends on asyncio.gather
3. {open_library, done, count=3}
4. {hardcover, done, count=2}
5. {complete, results=[OL#1, OL#2, OL#3, HC#1, HC#2]}  ← deduplicated
```

### Stream Endpoint Event Sequence (auto mode, no token):

```
1. {open_library, searching}
2. {hardcover, skipped, reason="no_api_token"}
3. {open_library, done, count=3}
4. {complete, results=[OL#1, OL#2, OL#3]}
```

### Stream Endpoint Event Sequence (auto mode, OL empty, HC has results):

```
1. {open_library, searching}
2. {hardcover, searching}
3. {open_library, done, count=0}
4. {hardcover, done, count=2}
5. No Google fallback because HC has results
6. {complete, results=[HC#1, HC#2]}
```

### Stream Endpoint Event Sequence (auto mode, both empty, Google available):

```
1. {open_library, searching}
2. {hardcover, searching}
3. {open_library, done, count=0}
4. {hardcover, done, count=0}
5. {google_books, searching}
6. {google_books, done, count=1}
7. {complete, results=[GB#1]}
```

---

## 4. Testing Strategy

### 4.1 New Tests in `backend/tests/test_import.py`

#### `map_hardcover()` Unit Tests

| Test | Purpose |
|------|---------|
| `test_map_hardcover_fields` | Verify all fields mapped correctly from a complete GraphQL edition node |
| `test_map_hardcover_minimal` | Minimal edition with only title |
| `test_map_hardcover_missing_optional` | Missing contributions, image, publisher etc. |
| `test_map_hardcover_author_first_contributor` | Verify first author (not translator) is selected |
| `test_map_hardcover_cover_ssrf_protection` | Verify unsafe cover URL is rejected |
| `test_map_hardcover_tags_capped` | Tags capped at 3 |
| `test_map_hardcover_language_uppercased` | Language code2 is uppercased |
| `test_map_hardcover_published_year` | Release_date first 4 chars become year |
| `test_map_hardcover_author_null_when_no_contributions` | No author when contributions empty |

#### `_merge_and_deduplicate()` Unit Tests

| Test | Purpose |
|------|---------|
| `test_merge_and_dedup_same_isbn_pages_lang` | Same ISBN+pages+lang in both → only first (OL) kept |
| `test_merge_and_dedup_same_isbn_diff_pages` | Same ISBN, different page count → both kept |
| `test_merge_and_dedup_same_isbn_diff_lang` | Same ISBN, different language → both kept |
| `test_merge_and_dedup_same_isbn_same_pages_diff_lang` | Same ISBN+pages, different language → both kept |
| `test_merge_and_dedup_ol_first_order` | OL items come before HC items |
| `test_merge_and_dedup_no_isbn_different` | Different ISBN → both kept |

#### `_search_hardcover()` Integration Tests (monkeypatched)

| Test | Purpose |
|------|---------|
| `test_search_hardcover_title_success` | Title search returns candidates via two-step flow |
| `test_search_hardcover_title_no_isbns` | Search query returns no ISBNs → empty |
| `test_search_hardcover_isbn_success` | ISBN search returns candidate |
| `test_search_hardcover_isbn_not_found` | ISBN search returns no mappings → empty |
| `test_search_hardcover_no_token` | Empty token → empty results (skipped) |

#### `search_with_progress()` Integration Tests (with hardcover)

| Test | Purpose |
|------|---------|
| `test_search_with_progress_ol_and_hc_parallel` | Both run; events contain both stages |
| `test_search_with_progress_hc_no_token` | HC skipped when no token |
| `test_search_with_progress_ol_hc_dedup` | Results deduplicated |
| `test_search_with_progress_hc_only` | HC runs; OL returns empty; HC results used |
| `test_search_with_progress_ol_hc_empty_fallsback_to_gb` | Both empty → Google fallback |
| `test_search_with_progress_hc_with_gb_fallback` | Full chain: OL empty, HC empty, Google fallback |

### 4.2 Test Fixtures for GraphQL Responses

Add fixtures for hardcover GraphQL responses:

```python
HARDCOVER_GRAPHQL_SEARCH_RESPONSE = {
    "data": {
        "search": [
            {
                "hits": [
                    {
                        "document": {
                            "isbns": ["9780441013593", "0441013597"]
                        }
                    }
                ]
            }
        ]
    }
}

HARDCOVER_GRAPHQL_BOOK_MAPPING = {
    "data": {
        "book_mappings": [
            {
                "edition": {
                    "title": "Dune",
                    "subtitle": None,
                    "isbn_13": "9780441013593",
                    "pages": 412,
                    "release_date": "1965-08-01",
                    "image": {"url": "https://assets.hardcover.app/editions/123/cover.jpg"},
                    "publisher": {"name": "Ace Books"},
                    "language": {"code2": "en"},
                    "book": {
                        "description": "A science fiction novel.",
                        "taggings": [
                            {"tag": {"tag": "Science Fiction"}},
                            {"tag": {"tag": "Ecology"}},
                        ],
                    },
                    "contributions": [
                        {"author": {"name": "Frank Herbert"}, "role": "Author"},
                    ],
                }
            },
        ]
    }
}
```

### 4.3 Existing Tests That Should Still Pass

- All existing `map_open_library` tests
- All existing `map_google_books` tests
- All existing `search()` integration tests (with empty hardcover token)
- All existing `search_with_progress()` tests (with empty hardcover token)
- All existing stream endpoint tests
- All existing import endpoint tests

### 4.4 SSR/Endpoint Tests

- `test_import_search_stream_accepts_hardcover_token` — Verify stream endpoint passes token
- `test_import_search_uses_hardcover_token` — Verify simple search passes token

---

## 5. Risk Considerations

### 5.1 Breaking Changes

- **`search()` signature change**: Adding `hardcover_api_token` as a keyword-only parameter. Callers that pass positional args could break. However, all current callers (the router) use keyword args, so this is low risk.
- **`search_with_progress()` signature change**: Same consideration. Adding a new keyword-only parameter with default empty string is backwards-compatible.
- **`search_with_progress()` behavior change**: The function now runs two sources in parallel instead of sequentially. This changes the ordering of yielded events. The frontend handles stages based on their `stage` field, so UI rendering should not break — new stage types appear. However, the frontend's `mergeCandidates` logic (which runs client-side for the Google supplement) should be unaffected because hardcover results are server-merged before the `complete` event.

### 5.2 API Rate Limits

Hardcover.app GraphQL API has rate limits. The `_search_hardcover` function makes up to 2 queries per title search (`search` + `book_mappings`) and 1 query per ISBN search. Ensure `_hardcover_search_title` only extracts up to ~10 ISBNs to limit `book_mappings` query size.

### 5.3 GraphQL Error Handling

The GraphQL endpoint may return HTTP 200 with `errors` in the response body. The implementation must check for `errors` key in the response JSON, not just HTTP status code. Example:

```python
data = resp.json()
if "errors" in data:
    logger.warning("hardcover GraphQL errors: %s", data["errors"])
    return []
```

### 5.4 SSRF Protection

Cover URLs from hardcover must be validated with `is_safe_cover_import_url()` before use. This is already noted in the `map_hardcover()` function above. Additionally, since hardcover API responses could theoretically be compromised, the `is_safe_cover_import_url` check is essential.

### 5.5 ISBN Conversion Dependency

`_normalize_isbn()` is currently defined in `cover_candidates.py`. Using it from `book_import.py` creates an import dependency:
- Option A (recommended): Move `_normalize_isbn()` and `_isbn13_to_isbn10()` to a shared utility module (e.g., `backend/app/services/isbn_utils.py`) and import from both places.
- Option B: Create a thin wrapper in `book_import.py` that duplicates the logic.
- Option C: Import directly from `cover_candidates`.

**Recommendation**: Option A — extract to a shared utility. This avoids circular imports and keeps the code DRY.

### 5.6 Monetization Risk

Hardcover.app API tokens may be rate-limited or have usage costs. The feature is gated behind the `hardcover_app_api_token` setting, so it only activates when explicitly configured. The user must obtain their own API token.

### 5.7 Frontend Rendering

The `stageLabel()` function uses exhaustiveness checks via `if/else` branches. Adding `s.stage === 'hardcover'` needs to be placed before the final `return ''` fallback. No TypeScript `switch` exhaustive check is currently used, so no type-level breakage.

### 5.8 ISBN-13 vs ISBN-10 in `book_mappings` Query

The `edition.isbn_13` field in hardcover's GraphQL schema might be null even when `edition.isbn_10` is present. The `map_hardcover` function should fall back to using `isbn_10` from the mapping, or derive ISBN-13 from ISBN-10 via `_normalize_isbn()`. Check the hardcover GraphQL schema for `isbn_10` availability.

### 5.9 `search` GraphQL Query Pagination

The `search` query with `limit: 1` returns only one hit. Its `hits[0].document.isbns` array may contain up to 10+ ISBNs. The implementation should collect up to ~10 unique ones. If the API supports pagination (`offset`), consider adding it in a future iteration.

---

## 6. Implementation Order

1. **Extract ISBN utilities** — Move `_normalize_isbn()` and `_isbn13_to_isbn10()` to `backend/app/services/isbn_utils.py`
2. **Add `map_hardcover()`** — Pure function, easy to test independently
3. **Add `_merge_and_deduplicate()`** — Pure function
4. **Add `_hardcover_search_title()`** — Title search GraphQL query
5. **Add `_hardcover_fetch_books()`** — Book mappings GraphQL query
6. **Add `_search_hardcover()`** — Orchestrator that combines the above
7. **Modify `search_with_progress()`** — Add parallel OL+HC execution
8. **Modify `search()`** — Add parallel OL+HC execution
9. **Update `import_.py` router** — Pass hardcover token
10. **Update `types.ts`** — Add hardcover to `SearchStage`
11. **Update `ImportSearch.svelte`** — Render hardcover stage
12. **Update i18n files** — Add translation keys
13. **Write tests** — Follow the testing strategy above
14. **Manual testing** — Run against real hardcover API with a token
