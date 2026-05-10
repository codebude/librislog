# LibrisLog — Optional Google Books Supplement After Open Library Results

## Goal

When import search returns one or more Open Library matches, do **not** stop the
user at that point. Instead, show existing Open Library results immediately and
offer an explicit action: **"Search Google Books too"**.

The Google search should be optional (user-triggered), and results should be
merged into the current list without removing already shown Open Library items.

---

## Current Behavior

- `book_import.search_with_progress()` searches Open Library first.
- If Open Library has results, Google Books is not queried.
- Google Books is only used as fallback when Open Library is empty.
- `ImportSearch.svelte` consumes streamed events and renders final results once.

This blocks users from discovering additional candidates from Google Books when
Open Library already returned partial/incomplete matches.

---

## Proposed Product Behavior

1. User runs a normal search (title/ISBN).
2. App returns and displays Open Library results as today.
3. If at least one Open Library result exists, UI shows a secondary action:
   **Search Google Books too**.
4. On click, app performs a second search against Google Books only.
5. New Google results are merged with current list (deduplicated), preserving
   existing Open Library results already displayed.

---

## API / Service Design

### 1) Add search mode for stream endpoint

Extend stream route with a `mode` query parameter:

- `mode=auto` (default): current behavior (Open Library first, Google fallback)
- `mode=google_only`: skip Open Library and run only Google Books

Proposed endpoint shape:

`GET /api/import/search/stream?q=...&type=title|isbn&mode=auto|google_only`

### 2) Extend service function

Update `book_import.search_with_progress(...)` to accept `mode` and branch:

- `auto`: unchanged behavior
- `google_only`:
  - emit `google_books/searching`
  - if no API key: emit `google_books/skipped` then `complete` with `[]`
  - else query Google Books, emit `google_books/done`, then `complete`

Keep event shapes backward-compatible with current frontend types.

### 3) Keep non-stream search API unchanged

`/api/import/search` is currently not used by import UI flow; no change needed
for this feature.

---

## Frontend Plan

### `frontend/src/lib/api.ts`

- Extend `api.import.searchStream(q, type, mode = 'auto')`.
- Append `mode` query param to stream URL.

### `frontend/src/lib/types.ts`

- Add search mode type:
  - `type ImportSearchMode = 'auto' | 'google_only'`

### `frontend/src/lib/components/ImportSearch.svelte`

Add state and flow for optional second pass:

- New UI state:
  - `hasOlResults` (derived from current results/stages)
  - `googleSupplementSearched` (prevent duplicate button spam)
  - `supplementingGoogle` (secondary loading state)
- Keep existing `search()` for initial pass (`mode='auto'`).
- Add `searchGoogleToo()` for second pass (`mode='google_only'`).
- Merge strategy for supplementary results:
  - Keep all existing results.
  - Add new Google candidates only when not duplicate.
  - Dedup key priority:
    1. normalized ISBN when present
    2. fallback `title+author` normalized
- Show button only when:
  - not currently searching,
  - current results include at least one Open Library candidate,
  - supplementary Google search not already completed.

Suggested label:

- Idle: `Search Google Books too`
- Loading: `Searching Google Books…`

---

## Deduplication Rules

For merged result list (OL + optional GB):

1. If both candidates have same ISBN (normalized, hyphens removed), treat as duplicate.
2. If ISBN missing, use normalized `title|author` match (case-folded, trimmed).
3. Keep first occurrence already shown (Open Library stays preferred when equal).

This avoids duplicate cards after supplementary search.

---

## Test Plan

Project already has backend pytest suite, so add/extend tests there.

### A) Backend service tests (`backend/tests/test_import.py`)

Add tests for `search_with_progress(..., mode=...)`:

1. `test_search_with_progress_google_only_runs_google`
   - monkeypatch OL and GB search fns
   - call with `mode='google_only'` and API key
   - assert OL fn not called, GB called
   - assert stages include `google_books/searching`, `google_books/done`, `complete`

2. `test_search_with_progress_google_only_without_key_skips`
   - call with `mode='google_only'` and empty key
   - assert `google_books/skipped` emitted and complete results empty

3. `test_search_with_progress_auto_unchanged_when_ol_has_results`
   - OL returns one result
   - assert no Google stage appears in auto mode (regression guard)

### B) Stream endpoint tests (`backend/tests/test_import.py`)

4. `test_search_stream_endpoint_forwards_mode_google_only`
   - monkeypatch `search_with_progress` spy
   - request `/api/import/search/stream?...&mode=google_only`
   - assert spy receives `mode='google_only'`

5. `test_search_stream_endpoint_default_mode_auto`
   - request without mode
   - assert mode defaults to `auto`

### C) Frontend tests

Current frontend has no test harness in repo (`package.json` has no test script,
no spec files). For this iteration:

- implement manual verification checklist (below)
- keep automated frontend tests out of scope unless we explicitly introduce
  Vitest + Testing Library in a follow-up task.

### D) Manual QA checklist

1. Search term with OL hits (e.g., "Dune") shows OL results and button.
2. Clicking button appends Google-only results (no OL reset).
3. Duplicate ISBN/title candidates are not duplicated in UI.
4. No API key configured: button click yields clear skipped state (or toast) and
   list remains stable.
5. Standard fallback behavior still works when OL has zero results.

---

## Files Expected To Change

- `backend/app/services/book_import.py`
- `backend/app/routers/import_.py`
- `backend/tests/test_import.py`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/components/ImportSearch.svelte`

---

## Risks / Notes

- Google API key may be missing; UX must handle this gracefully.
- Supplementary search is a second network round-trip; UI needs clear loading.
- Dedup rules should remain deterministic to prevent item flicker/reordering.

---

## Out of Scope

- Parallel OL+Google search in first pass.
- New backend persistence fields for "chosen source".
- Introducing frontend automated test tooling in this same change.
