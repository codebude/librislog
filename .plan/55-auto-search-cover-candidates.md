# Plan 55: Auto-Search Cover Candidates from ISBN

## Overview

Extend the book edit dialog with an "Auto-search covers" feature that queries multiple providers (AbeBooks, OpenLibrary, Amazon) by ISBN, displays candidate covers in a modal with size/resolution info, and allows the user to click a cover to download and set it for the current book.

**Key Goals:**
- Add "Auto-search covers" button beside the existing "Google covers" button (renamed from "search for covers")
- Only enable when ISBN field is non-empty (not necessarily saved)
- Show modal with spinner during search, then display candidates with hover info (filesize + resolution)
- Download and set cover on candidate click (reuse existing cover download flow)
- Proper error handling with toast or in-modal messages
- Follow existing repo conventions (FastAPI backend, Svelte 5 frontend, daisyUI modals)

---

## 1. Files to Create

### 1.1 `backend/app/routers/cover_candidates.py` (new router)

**Purpose:** Provide `/api/cover-candidates/search` endpoint that takes an ISBN and queries all providers.

**Responsibilities:**
- Accept ISBN as query parameter (validate ISBN-10 or ISBN-13 format)
- Normalize ISBN: strip hyphens/spaces, validate checksum (optional strict mode or just length check)
- Query providers in parallel with timeouts (use `asyncio.gather` with `return_exceptions=True`)
- For each provider URL:
  - Perform HEAD request to check Content-Type, Content-Length
  - If image and size >= threshold (e.g., 5 KB), try to extract image dimensions (or return None)
  - Build `CoverCandidate` response object
- Return list of available candidates with metadata

**Provider URL patterns:**
- AbeBooks: `https://pictures.abebooks.com/isbn/{isbn13}-de.jpg`
- OpenLibrary: `https://covers.openlibrary.org/b/isbn/{isbn13}-M.jpg`
- Amazon: `https://images-eu.ssl-images-amazon.com/images/P/{isbn13}.01.L.jpg`

**Dependencies:**
- `httpx.AsyncClient` (reuse or create new instance with timeout)
- `app.config.settings` for timeout/size thresholds (add optional config vars: `cover_candidate_timeout_seconds`, `cover_candidate_min_size_bytes`)
- Optional: `PIL` or `imagesize` library to extract dimensions from image bytes (fallback: return `None` for width/height if not feasible without download)

**API Contract:**
```python
# Request
GET /api/cover-candidates/search?isbn=9780451524935

# Response (CoverCandidateList schema)
{
  "candidates": [
    {
      "source": "abebooks",
      "url": "https://pictures.abebooks.com/isbn/9780451524935-de.jpg",
      "available": true,
      "width": 300,        # null if unknown
      "height": 475,       # null if unknown
      "filesize": 45231,   # bytes, null if unknown
      "content_type": "image/jpeg"
    },
    {
      "source": "openlibrary",
      "url": "https://covers.openlibrary.org/b/isbn/9780451524935-M.jpg",
      "available": false,
      "width": null,
      "height": null,
      "filesize": null,
      "content_type": null
    },
    {
      "source": "amazon",
      "url": "https://images-eu.ssl-images-amazon.com/images/P/9780451524935.01.L.jpg",
      "available": true,
      "width": null,
      "height": null,
      "filesize": 52104,
      "content_type": "image/jpeg"
    }
  ],
  "query_isbn": "9780451524935"
}
```

**Error handling:**
- Invalid ISBN format: return HTTP 400 with `{"detail": "error.invalidIsbn"}`
- Network failures for all providers: return HTTP 200 with empty candidates list + warning message
- Partial failures: include successful candidates, log failures

**Implementation notes:**
- Use HEAD requests only (don't download full images during search)
- Set timeout per provider (e.g., 5 seconds)
- Use `httpx.AsyncClient(follow_redirects=True)` to handle redirects
- For dimension extraction: if needed, consider downloading a small chunk (e.g., first 10 KB) and using `imagesize.get()` or `PIL.Image.open()` with partial stream. Otherwise, return `null` for dimensions.
- Filter out results with `Content-Length < MIN_SIZE_BYTES` (default 5000)

---

### 1.2 `backend/app/schemas.py` — Add new schemas

**Add:**

```python
class CoverCandidate(SQLModel):
    """A single cover candidate from an external provider."""
    source: str  # "abebooks" | "openlibrary" | "amazon"
    url: str
    available: bool
    width: Optional[int] = None  # pixels, null if unknown
    height: Optional[int] = None  # pixels, null if unknown
    filesize: Optional[int] = None  # bytes, null if unknown
    content_type: Optional[str] = None


class CoverCandidateList(SQLModel):
    """Response containing all cover candidates for an ISBN search."""
    candidates: List[CoverCandidate]
    query_isbn: str
```

**Location:** Add after existing `BookImportCandidate` schema (around line 80).

---

### 1.3 `frontend/src/lib/components/AutoSearchCoverModal.svelte` (new component)

**Purpose:** Modal that displays cover search results and allows user to click a candidate to import.

**Props:**
- `open: boolean` (bindable)
- `isbn: string` (the ISBN to search)
- `onCoverSelected: (url: string) => void` (callback when user clicks a candidate)

**State:**
- `loading: boolean` — true during search
- `candidates: CoverCandidate[]` — search results
- `error: string | null` — error message if search fails
- `hoveredCandidate: string | null` — track which candidate is hovered (by source)

**Behavior:**
- On open (via `$effect`), immediately call `/api/cover-candidates/search?isbn={isbn}`
- Show spinner during loading
- On success: display candidates in a grid (2-3 columns)
- On error: display error message in modal
- Hovering a candidate: show tooltip/overlay with filesize + resolution (if available)
- Clicking a candidate: call `onCoverSelected(candidate.url)` and close modal
- Modal has:
  - Close X button (top-right)
  - Cancel button (bottom-right)
  - Info text: "Click a cover to import it"

**UI structure (daisyUI):**
```svelte
<div class="modal modal-open">
  <div class="modal-box w-full max-w-2xl">
    <button class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2">✕</button>
    <h3 class="font-bold text-lg">Auto-search Covers</h3>
    
    {#if loading}
      <div class="flex items-center justify-center py-8">
        <span class="loading loading-spinner loading-lg"></span>
      </div>
    {:else if error}
      <div class="alert alert-error mt-4">
        <span>{error}</span>
      </div>
    {:else if candidates.length === 0}
      <p class="text-sm text-base-content/70 mt-4">No covers found for this ISBN.</p>
    {:else}
      <p class="text-sm text-base-content/70 mt-2 mb-4">Click a cover to import it</p>
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {#each candidates as candidate}
          {#if candidate.available}
            <button
              class="relative border-2 border-base-300 rounded-lg overflow-hidden hover:border-primary transition-colors aspect-[2/3]"
              on:mouseenter={() => hoveredCandidate = candidate.source}
              on:mouseleave={() => hoveredCandidate = null}
              on:click={() => { onCoverSelected(candidate.url); open = false; }}
            >
              <img src={candidate.url} alt="Cover from {candidate.source}" class="w-full h-full object-cover" />
              {#if hoveredCandidate === candidate.source}
                <div class="absolute inset-0 bg-black/70 flex flex-col items-center justify-center text-white text-xs">
                  <div class="font-semibold uppercase">{candidate.source}</div>
                  {#if candidate.width && candidate.height}
                    <div>{candidate.width} × {candidate.height} px</div>
                  {/if}
                  {#if candidate.filesize}
                    <div>{(candidate.filesize / 1024).toFixed(1)} KB</div>
                  {/if}
                </div>
              {/if}
            </button>
          {/if}
        {/each}
      </div>
    {/if}
    
    <div class="modal-action">
      <button class="btn btn-sm" on:click={() => open = false}>Cancel</button>
    </div>
  </div>
</div>
```

**Dependencies:**
- `$lib/api` — add `api.coverCandidates.search(isbn: string)` method
- `$lib/toasts` — for error fallback (optional, errors also shown in modal)
- `$lib/i18n` — for translated strings

**i18n keys to add (see section 4.1):**
- `book.autoSearchCovers`
- `book.googleCovers`
- `book.autoSearchModalTitle`
- `book.autoSearchModalInfo`
- `book.autoSearchLoading`
- `book.autoSearchNoResults`
- `book.autoSearchError`

---

## 2. Files to Modify

### 2.1 `backend/app/main.py` — Register new router

**Change:**

Add import:
```python
from app.routers import cover_candidates
```

Add router registration (after `app.include_router(covers.router)`):
```python
app.include_router(cover_candidates.router)
```

**Location:** Around line 35-45 (where other routers are registered).

---

### 2.2 `backend/app/config.py` — Add optional config for cover candidate search

**Add (optional, with defaults):**

```python
class Settings(BaseSettings):
    # ... existing fields ...
    cover_candidate_timeout_seconds: int = 5
    cover_candidate_min_size_bytes: int = 5000
```

**Location:** After line 36 (`data_dir: str = "./data"`).

**Purpose:** Allow operators to tune timeout and minimum size threshold for candidate checks.

---

### 2.3 `backend/app/schemas.py` — Add `CoverCandidate` schemas

See section 1.2 above.

---

### 2.4 `frontend/src/lib/components/BookDrawer.svelte` — Rename button and add auto-search

**Current code (lines 376-381):**
```svelte
<CoverPicker bind:value={cover_url} disabled={saving} />
<div class="-mt-1">
  <a href={coverSearchUrl} target="_blank" rel="noreferrer" class="btn btn-outline btn-xs">
    {$_('book.searchForCovers')}
  </a>
</div>
```

**Change to:**
```svelte
<CoverPicker bind:value={cover_url} disabled={saving} />
<div class="-mt-1 flex gap-2">
  <a href={coverSearchUrl} target="_blank" rel="noreferrer" class="btn btn-outline btn-xs">
    {$_('book.googleCovers')}
  </a>
  <button
    type="button"
    class="btn btn-outline btn-xs"
    disabled={!isbn.trim() || saving}
    onclick={() => autoSearchModalOpen = true}
  >
    {$_('book.autoSearchCovers')}
  </button>
</div>

<AutoSearchCoverModal
  bind:open={autoSearchModalOpen}
  isbn={isbn.trim()}
  onCoverSelected={(url) => {
    cover_url = url;
    toasts.add($_('book.coverImported'), 'success');
  }}
/>
```

**Additional state needed (add near top of script):**
```svelte
let autoSearchModalOpen = $state(false);
```

**Import needed:**
```svelte
import AutoSearchCoverModal from './AutoSearchCoverModal.svelte';
```

**Note:** The button is enabled when `isbn.trim()` is non-empty. This checks the current form state, not the saved book state, as per requirements.

---

### 2.5 `frontend/src/lib/api.ts` — Add cover candidates endpoint

**Add (in appropriate section, likely after `covers` or `books` endpoints):**

```typescript
coverCandidates: {
  search: async (isbn: string): Promise<CoverCandidateList> => {
    const params = new URLSearchParams({ isbn });
    const res = await fetch(`${API_BASE}/api/cover-candidates/search?${params}`, {
      credentials: 'include'
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'error.networkError' }));
      throw new Error(error.detail || 'error.networkError');
    }
    return res.json();
  }
}
```

**Types needed (add to `frontend/src/lib/types.ts`):**

```typescript
export interface CoverCandidate {
  source: string;
  url: string;
  available: boolean;
  width?: number | null;
  height?: number | null;
  filesize?: number | null;
  content_type?: string | null;
}

export interface CoverCandidateList {
  candidates: CoverCandidate[];
  query_isbn: string;
}
```

---

### 2.6 `frontend/src/lib/i18n/locales/en.json` — Add i18n keys

**Add (in `book` section, around line 140):**

```json
"book": {
  ...
  "searchForCovers": "Search for covers",  // OLD KEY - to be replaced
  "googleCovers": "Google covers",
  "autoSearchCovers": "Auto-search covers",
  "autoSearchModalTitle": "Auto-search Covers",
  "autoSearchModalInfo": "Click a cover to import it",
  "autoSearchLoading": "Searching for covers...",
  "autoSearchNoResults": "No covers found for this ISBN.",
  "autoSearchError": "Failed to search for covers. Please try again.",
  "coverImported": "Cover imported successfully"
}
```

**Change existing key:**
- `"searchForCovers"` → `"googleCovers"` (rename, keep for backward compat if needed or just replace)

**Location:** In the `book` section after `coverOf`.

---

### 2.7 `frontend/src/lib/i18n/locales/de.json` — Add German translations

**Add (matching structure):**

```json
"book": {
  ...
  "googleCovers": "Google-Cover",
  "autoSearchCovers": "Cover automatisch suchen",
  "autoSearchModalTitle": "Cover automatisch suchen",
  "autoSearchModalInfo": "Klicken Sie auf ein Cover, um es zu importieren",
  "autoSearchLoading": "Suche nach Covern...",
  "autoSearchNoResults": "Keine Cover für diese ISBN gefunden.",
  "autoSearchError": "Fehler beim Suchen von Covern. Bitte versuchen Sie es erneut.",
  "coverImported": "Cover erfolgreich importiert"
}
```

---

## 3. Backend Implementation Details

### 3.1 ISBN Validation and Normalization

**Helper function (in `backend/app/routers/cover_candidates.py` or new `app/utils/isbn.py`):**

```python
def normalize_isbn(isbn: str) -> str | None:
    """Strip hyphens/spaces and validate ISBN-10 or ISBN-13 length.
    
    Returns ISBN-13 if valid, None otherwise.
    """
    clean = isbn.replace("-", "").replace(" ", "")
    if len(clean) == 10:
        # Convert ISBN-10 to ISBN-13 (add 978 prefix + recalculate checksum)
        # For simplicity: just validate length and let provider handle
        # Real impl: use `isbnlib` or manual checksum validation
        return f"978{clean[:-1]}{_isbn13_checksum('978' + clean[:-1])}"
    elif len(clean) == 13 and clean.isdigit():
        return clean
    return None

def _isbn13_checksum(base: str) -> str:
    """Calculate ISBN-13 checksum digit."""
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))
    return str((10 - (total % 10)) % 10)
```

**Note:** Consider using `isbnlib` library if already in dependencies, otherwise implement basic validation.

---

### 3.2 Provider Query Logic

**Implementation (in `backend/app/routers/cover_candidates.py`):**

```python
import asyncio
import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import require_user
from app.config import settings
from app.database import get_session
from app.models import User
from app.schemas import CoverCandidate, CoverCandidateList

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cover-candidates", tags=["cover-candidates"])

PROVIDERS = {
    "abebooks": "https://pictures.abebooks.com/isbn/{isbn13}-de.jpg",
    "openlibrary": "https://covers.openlibrary.org/b/isbn/{isbn13}-M.jpg",
    "amazon": "https://images-eu.ssl-images-amazon.com/images/P/{isbn13}.01.L.jpg",
}

async def _check_candidate(
    source: str,
    url: str,
    client: httpx.AsyncClient,
    min_size: int
) -> CoverCandidate:
    """Check if a cover URL is available and extract metadata."""
    try:
        resp = await client.head(url, timeout=settings.cover_candidate_timeout_seconds)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.debug("Non-image content-type for %s: %s", source, content_type)
                return CoverCandidate(source=source, url=url, available=False)
            
            content_length = resp.headers.get("content-length")
            filesize = int(content_length) if content_length else None
            
            if filesize and filesize < min_size:
                logger.debug("Cover too small for %s: %d bytes", source, filesize)
                return CoverCandidate(source=source, url=url, available=False)
            
            # Optionally: download partial bytes and extract dimensions
            # For now: return None for width/height
            return CoverCandidate(
                source=source,
                url=url,
                available=True,
                filesize=filesize,
                content_type=content_type,
                width=None,
                height=None
            )
        else:
            logger.debug("HTTP %d for %s", resp.status_code, source)
            return CoverCandidate(source=source, url=url, available=False)
    except Exception as exc:
        logger.warning("Failed to check %s: %s", source, exc)
        return CoverCandidate(source=source, url=url, available=False)


@router.get("/search", response_model=CoverCandidateList)
async def search_cover_candidates(
    isbn: str = Query(..., min_length=10, max_length=17),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> CoverCandidateList:
    """Search for cover images from multiple providers by ISBN."""
    isbn13 = normalize_isbn(isbn)
    if not isbn13:
        raise HTTPException(status_code=400, detail="error.invalidIsbn")
    
    logger.debug("search_cover_candidates — isbn=%s isbn13=%s", isbn, isbn13)
    
    urls = {source: tmpl.format(isbn13=isbn13) for source, tmpl in PROVIDERS.items()}
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [
            _check_candidate(source, url, client, settings.cover_candidate_min_size_bytes)
            for source, url in urls.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    candidates = [r for r in results if isinstance(r, CoverCandidate)]
    
    logger.info(
        "search_cover_candidates — isbn=%s available=%d/%d",
        isbn13,
        sum(1 for c in candidates if c.available),
        len(candidates)
    )
    
    return CoverCandidateList(candidates=candidates, query_isbn=isbn13)
```

**Dependencies:**
- `httpx` (already in project)
- `app.config.settings` (add new fields: `cover_candidate_timeout_seconds`, `cover_candidate_min_size_bytes`)

**Error handling:**
- Invalid ISBN format: HTTP 400
- All providers fail: return empty candidates list (HTTP 200)
- Partial failures: include successful results

---

### 3.3 Dimension Extraction (Optional Enhancement)

**If dimensions are required**, consider downloading the first ~10 KB and using `imagesize`:

```python
from io import BytesIO
import imagesize

async def _get_dimensions(url: str, client: httpx.AsyncClient) -> tuple[int, int] | None:
    """Download partial image and extract dimensions."""
    try:
        async with client.stream("GET", url, timeout=5) as resp:
            if resp.status_code != 200:
                return None
            chunk = await resp.aread(10240)  # 10 KB
            size = imagesize.get(BytesIO(chunk))
            if size[0] > 0 and size[1] > 0:
                return size
    except Exception as exc:
        logger.debug("Failed to get dimensions: %s", exc)
    return None
```

**Add `imagesize` to `requirements.txt`:**
```
imagesize==1.4.1
```

**Integrate into `_check_candidate`:**
```python
if filesize and filesize >= min_size:
    dims = await _get_dimensions(url, client)
    width, height = dims if dims else (None, None)
```

**Decision:** Implement if dimensions are critical for UX, otherwise leave as `None` and show only filesize.

---

## 4. Frontend Implementation Details

### 4.1 AutoSearchCoverModal Component Structure

**File:** `frontend/src/lib/components/AutoSearchCoverModal.svelte`

**Full implementation:**

```svelte
<script lang="ts">
  import { _ } from '$lib/i18n';
  import { api } from '$lib/api';
  import { toasts } from '$lib/toasts';
  import type { CoverCandidate } from '$lib/types';

  let {
    open = $bindable(false),
    isbn,
    onCoverSelected
  }: {
    open?: boolean;
    isbn: string;
    onCoverSelected: (url: string) => void;
  } = $props();

  let loading = $state(false);
  let candidates = $state<CoverCandidate[]>([]);
  let error = $state<string | null>(null);
  let hoveredCandidate = $state<string | null>(null);

  async function searchCovers() {
    if (!isbn.trim()) return;
    loading = true;
    error = null;
    candidates = [];
    try {
      const result = await api.coverCandidates.search(isbn);
      candidates = result.candidates.filter(c => c.available);
      if (candidates.length === 0) {
        error = $_('book.autoSearchNoResults');
      }
    } catch (e: unknown) {
      const message = e instanceof Error && e.message.startsWith('error.')
        ? $_(e.message)
        : $_('book.autoSearchError');
      error = message;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (open && isbn.trim()) {
      void searchCovers();
    } else if (!open) {
      // Reset state when modal closes
      candidates = [];
      error = null;
      hoveredCandidate = null;
    }
  });

  function handleCandidateClick(candidate: CoverCandidate) {
    onCoverSelected(candidate.url);
    open = false;
  }
</script>

{#if open}
  <div class="modal modal-open">
    <div class="modal-box w-full max-w-2xl">
      <button
        class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"
        onclick={() => (open = false)}
        aria-label={$_('common.close')}
      >✕</button>
      
      <h3 class="font-bold text-lg">{$_('book.autoSearchModalTitle')}</h3>
      
      {#if loading}
        <div class="flex flex-col items-center justify-center py-12">
          <span class="loading loading-spinner loading-lg"></span>
          <p class="text-sm text-base-content/70 mt-4">{$_('book.autoSearchLoading')}</p>
        </div>
      {:else if error}
        <div class="alert alert-warning mt-4">
          <span>{error}</span>
        </div>
      {:else if candidates.length === 0}
        <p class="text-sm text-base-content/70 mt-4">{$_('book.autoSearchNoResults')}</p>
      {:else}
        <p class="text-sm text-base-content/70 mt-2 mb-4">{$_('book.autoSearchModalInfo')}</p>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {#each candidates as candidate (candidate.source)}
            <button
              type="button"
              class="relative border-2 border-base-300 rounded-lg overflow-hidden hover:border-primary hover:shadow-lg transition-all aspect-[2/3] bg-base-200"
              onmouseenter={() => (hoveredCandidate = candidate.source)}
              onmouseleave={() => (hoveredCandidate = null)}
              onclick={() => handleCandidateClick(candidate)}
            >
              <img
                src={candidate.url}
                alt="Cover from {candidate.source}"
                class="w-full h-full object-cover"
              />
              {#if hoveredCandidate === candidate.source}
                <div class="absolute inset-0 bg-black/75 flex flex-col items-center justify-center text-white text-xs p-2">
                  <div class="font-semibold uppercase mb-1">{candidate.source}</div>
                  {#if candidate.width && candidate.height}
                    <div class="mb-0.5">{candidate.width} × {candidate.height} px</div>
                  {/if}
                  {#if candidate.filesize}
                    <div>{(candidate.filesize / 1024).toFixed(1)} KB</div>
                  {/if}
                </div>
              {/if}
            </button>
          {/each}
        </div>
      {/if}
      
      <div class="modal-action">
        <button type="button" class="btn btn-sm" onclick={() => (open = false)}>
          {$_('common.cancel')}
        </button>
      </div>
    </div>
  </div>
{/if}
```

**Styling notes:**
- Uses daisyUI `modal modal-open` pattern
- Grid layout: 2 columns on mobile, 3 on desktop
- Aspect ratio enforced with `aspect-[2/3]` for consistent layout
- Hover overlay with black semi-transparent background for metadata display

---

### 4.2 Integration with BookDrawer

**State additions (near top of `<script>`):**
```svelte
let autoSearchModalOpen = $state(false);
```

**Import:**
```svelte
import AutoSearchCoverModal from './AutoSearchCoverModal.svelte';
```

**Button placement (after CoverPicker, line ~376):**
```svelte
<div class="-mt-1 flex gap-2">
  <a href={coverSearchUrl} target="_blank" rel="noreferrer" class="btn btn-outline btn-xs">
    {$_('book.googleCovers')}
  </a>
  <button
    type="button"
    class="btn btn-outline btn-xs"
    disabled={!isbn.trim() || saving}
    onclick={() => (autoSearchModalOpen = true)}
  >
    {$_('book.autoSearchCovers')}
  </button>
</div>
```

**Modal component (before closing `{/if}` of drawer, around line ~477):**
```svelte
<AutoSearchCoverModal
  bind:open={autoSearchModalOpen}
  isbn={isbn.trim()}
  onCoverSelected={(url) => {
    cover_url = url;
    toasts.add($_('book.coverImported'), 'success');
  }}
/>
```

**Behavior:**
- Auto-search button is disabled when:
  - ISBN field is empty or whitespace-only (`!isbn.trim()`)
  - Form is currently saving (`saving`)
- Clicking auto-search opens modal and triggers search immediately
- Clicking a candidate:
  - Sets `cover_url` to the selected URL (external URL)
  - Shows success toast
  - Closes modal
- On save, the existing cover download flow in `BookDrawer` will handle the external URL → local file conversion (via `update_book` endpoint)

---

## 5. Tests to Add/Update

### 5.1 Backend Tests

#### 5.1.1 `backend/tests/test_cover_candidates.py` (new file)

**Structure:**
```python
"""
Tests for GET /api/cover-candidates/search endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.auth import require_user
from app.models import User, UserRole


@pytest.fixture
def client():
    def _fake_user() -> User:
        return User(
            id=1,
            firstname="Test",
            lastname="User",
            email="test@example.com",
            role=UserRole.user,
            hashed_password="x"
        )
    
    app.dependency_overrides[require_user] = _fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_search_cover_candidates_valid_isbn(client: TestClient):
    """Valid ISBN returns candidate list."""
    # Mock httpx HEAD requests to return success
    with patch("app.routers.cover_candidates.httpx.AsyncClient") as mock_client:
        mock_head = AsyncMock()
        mock_head.status_code = 200
        mock_head.headers = {"content-type": "image/jpeg", "content-length": "50000"}
        mock_client.return_value.__aenter__.return_value.head = AsyncMock(return_value=mock_head)
        
        resp = client.get("/api/cover-candidates/search?isbn=9780451524935")
        assert resp.status_code == 200
        data = resp.json()
        assert "candidates" in data
        assert "query_isbn" in data
        assert data["query_isbn"] == "9780451524935"
        assert len(data["candidates"]) == 3  # abebooks, openlibrary, amazon


def test_search_cover_candidates_invalid_isbn(client: TestClient):
    """Invalid ISBN returns HTTP 400."""
    resp = client.get("/api/cover-candidates/search?isbn=invalid")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "error.invalidIsbn"


def test_search_cover_candidates_no_results(client: TestClient):
    """All providers fail: returns empty list."""
    with patch("app.routers.cover_candidates.httpx.AsyncClient") as mock_client:
        mock_head = AsyncMock()
        mock_head.status_code = 404
        mock_client.return_value.__aenter__.return_value.head = AsyncMock(return_value=mock_head)
        
        resp = client.get("/api/cover-candidates/search?isbn=9780451524935")
        assert resp.status_code == 200
        data = resp.json()
        assert len([c for c in data["candidates"] if c["available"]]) == 0


def test_search_cover_candidates_partial_success(client: TestClient):
    """Some providers succeed, some fail."""
    with patch("app.routers.cover_candidates.httpx.AsyncClient") as mock_client:
        async def mock_head(url, **kwargs):
            if "abebooks" in url:
                resp = AsyncMock()
                resp.status_code = 200
                resp.headers = {"content-type": "image/jpeg", "content-length": "45000"}
                return resp
            else:
                resp = AsyncMock()
                resp.status_code = 404
                return resp
        
        mock_client.return_value.__aenter__.return_value.head = mock_head
        
        resp = client.get("/api/cover-candidates/search?isbn=9780451524935")
        assert resp.status_code == 200
        data = resp.json()
        available = [c for c in data["candidates"] if c["available"]]
        assert len(available) == 1
        assert available[0]["source"] == "abebooks"


def test_search_cover_candidates_requires_auth(client: TestClient):
    """Endpoint requires authentication."""
    app.dependency_overrides.clear()
    resp = client.get("/api/cover-candidates/search?isbn=9780451524935")
    assert resp.status_code == 401
```

**Coverage:**
- Valid ISBN → returns candidates
- Invalid ISBN → HTTP 400
- All providers fail → empty list
- Partial success → returns available candidates
- Authentication required

**Run with:**
```bash
pytest backend/tests/test_cover_candidates.py -v
```

---

#### 5.1.2 `backend/tests/test_books.py` — Update existing tests (if needed)

**No changes needed** — cover download flow already tested, auto-search just provides URLs.

---

### 5.2 Frontend Tests (Manual / Playwright)

**Test plan for manual verification or Playwright automation:**

#### Test 1: Button visibility and state
- Open book edit drawer
- Verify "Google covers" button is visible
- Verify "Auto-search covers" button is visible and disabled when ISBN is empty
- Fill ISBN field → verify auto-search button becomes enabled

#### Test 2: Modal opens and searches
- Fill ISBN field with valid ISBN (e.g., `9780451524935`)
- Click "Auto-search covers"
- Verify modal opens with spinner
- Wait for search to complete
- Verify candidates are displayed (if available) or "No covers found" message

#### Test 3: Hover and metadata display
- Hover over a candidate cover
- Verify overlay shows source name, dimensions (if available), filesize (if available)

#### Test 4: Click candidate to import
- Click a candidate cover
- Verify modal closes
- Verify success toast appears ("Cover imported successfully")
- Verify cover preview in CoverPicker updates to selected cover

#### Test 5: Cancel modal
- Open auto-search modal
- Click Cancel button or X → verify modal closes

#### Test 6: Error handling
- Mock API failure (network error or invalid ISBN)
- Verify error message displays in modal

#### Test 7: No results
- Use ISBN with no available covers
- Verify "No covers found" message

**Playwright test sketch (optional):**
```typescript
// frontend/tests/auto-search-covers.spec.ts
import { test, expect } from '@playwright/test';

test('auto-search covers button is enabled when ISBN is filled', async ({ page }) => {
  // Login, navigate to book edit
  // ...
  
  await page.fill('input[type="text"]', '9780451524935'); // ISBN input
  const btn = page.locator('button:has-text("Auto-search covers")');
  await expect(btn).toBeEnabled();
  
  await btn.click();
  await expect(page.locator('.modal-open')).toBeVisible();
  
  // Wait for search to complete
  await page.waitForSelector('.loading', { state: 'detached' });
  
  // Verify candidates or no results message
  const candidates = page.locator('.modal-box img');
  const count = await candidates.count();
  if (count > 0) {
    await candidates.first().click();
    await expect(page.locator('.toast:has-text("Cover imported")')).toBeVisible();
  } else {
    await expect(page.locator('text=No covers found')).toBeVisible();
  }
});
```

---

## 6. Implementation Order & Milestones

### Phase 1: Backend Foundation
1. ✅ Add `CoverCandidate` and `CoverCandidateList` schemas to `backend/app/schemas.py`
2. ✅ Create `backend/app/routers/cover_candidates.py` with search endpoint
3. ✅ Implement ISBN normalization helper
4. ✅ Implement provider query logic (HEAD requests, size checks)
5. ✅ Register router in `backend/app/main.py`
6. ✅ Add config vars to `backend/app/config.py` (optional)
7. ✅ Write backend tests in `backend/tests/test_cover_candidates.py`

### Phase 2: Frontend Component
1. ✅ Add `CoverCandidate` types to `frontend/src/lib/types.ts`
2. ✅ Add `coverCandidates.search` method to `frontend/src/lib/api.ts`
3. ✅ Create `frontend/src/lib/components/AutoSearchCoverModal.svelte`
4. ✅ Add i18n keys to `en.json` and `de.json`

### Phase 3: Integration
1. ✅ Modify `BookDrawer.svelte`: rename button, add auto-search button + modal
2. ✅ Test end-to-end flow (open drawer → click auto-search → select cover → save)
3. ✅ Verify cover download works (external URL → local file via existing flow)

### Phase 4: Testing & Refinement
1. ✅ Run backend tests (`pytest backend/tests/test_cover_candidates.py`)
2. ✅ Manual UI testing (all scenarios from 5.2)
3. ✅ Optional: Add Playwright tests
4. ✅ Error handling review (toasts, modal messages)
5. ✅ Performance check (timeout tuning, parallel requests)

### Phase 5: Documentation & Deployment
1. ✅ Update `.plan/55-auto-search-cover-candidates.md` (this file) if needed
2. ✅ Deploy to dev/staging environment
3. ✅ User acceptance testing
4. ✅ Deploy to production

---

## 7. Risk Analysis & Mitigations

### Risk 1: External providers block HEAD requests or rate-limit
**Impact:** Medium — some candidates may not be detected  
**Mitigation:**
- Use realistic `User-Agent` header in httpx client
- Add exponential backoff (optional)
- Allow graceful degradation (partial results)
- Consider caching HEAD results per ISBN for short duration (e.g., 1 hour)

### Risk 2: Providers change URL patterns
**Impact:** Medium — candidates fail to load  
**Mitigation:**
- Log failures with provider name for monitoring
- Consider making provider URLs configurable via environment variables
- Document URL patterns in code comments

### Risk 3: Large image downloads slow down cover import
**Impact:** Low — existing cover download flow already handles this  
**Mitigation:**
- Reuse existing `download_cover` function with timeout (already 15s in `books.py`)
- No additional work needed

### Risk 4: ISBN normalization issues (ISBN-10 vs ISBN-13)
**Impact:** Low — some valid ISBNs may be rejected  
**Mitigation:**
- Use robust ISBN library (`isbnlib`) if available
- Document expected format (prefer ISBN-13)
- Show user-friendly error if ISBN is invalid

### Risk 5: Modal UI performance with many candidates
**Impact:** Low — max 3-5 providers expected  
**Mitigation:**
- Limit grid to available candidates only
- Lazy-load images (browser handles this by default)
- Consider pagination if provider list grows (future)

---

## 8. Future Enhancements (Out of Scope)

- **More providers:** Add Google Books, Goodreads, LibraryThing
- **Cover quality scoring:** Rank candidates by resolution/filesize
- **User preferences:** Remember preferred provider per user
- **Batch auto-search:** Auto-search covers for all books with ISBN but no cover
- **Cover caching:** Cache provider HEAD results to reduce latency on repeated searches
- **AI-powered cover validation:** Use image recognition to filter out placeholder/generic covers

---

## 9. Acceptance Criteria

**Backend:**
- ✅ `/api/cover-candidates/search?isbn=<isbn>` endpoint returns candidate list
- ✅ Invalid ISBN returns HTTP 400 with `error.invalidIsbn`
- ✅ Valid ISBN queries all 3 providers in parallel
- ✅ HEAD requests include size and content-type checks
- ✅ Endpoint requires authentication
- ✅ Backend tests cover success, failure, and partial success cases

**Frontend:**
- ✅ "Google covers" button renamed from "search for covers"
- ✅ "Auto-search covers" button added beside "Google covers"
- ✅ Auto-search button disabled when ISBN is empty
- ✅ Clicking auto-search opens modal with spinner
- ✅ Modal displays candidates in grid layout (2-3 columns)
- ✅ Hovering candidate shows overlay with metadata (source, dimensions, filesize)
- ✅ Clicking candidate imports cover and shows success toast
- ✅ Modal has close X and cancel button
- ✅ Error states handled gracefully (no results, API failure)
- ✅ Cover download flow reused (external URL → local file)

**Testing:**
- ✅ Backend tests pass (pytest)
- ✅ Manual UI tests pass (all scenarios in 5.2)
- ✅ No regressions in existing cover upload/download functionality

**i18n:**
- ✅ All UI strings translated (EN + DE)

---

## 10. Verification Checklist

**Before marking as complete, verify:**

- [ ] Backend endpoint returns expected JSON structure
- [ ] Invalid ISBN returns HTTP 400
- [ ] All 3 providers queried in parallel (check logs)
- [ ] HEAD requests use correct URL patterns
- [ ] Frontend button state correct (enabled/disabled based on ISBN)
- [ ] Modal opens and displays candidates
- [ ] Hover overlay shows metadata
- [ ] Clicking candidate imports cover successfully
- [ ] Success toast appears after import
- [ ] Modal closes after import
- [ ] Cancel button works
- [ ] Error messages display correctly (no results, API failure)
- [ ] Existing cover upload/download flow not broken
- [ ] Backend tests pass
- [ ] Manual UI tests pass
- [ ] i18n keys added for EN and DE
- [ ] No console errors in browser
- [ ] No unhandled promise rejections

---

## 11. Notes & Decisions

### Decision 1: HEAD requests only during search
**Rationale:** Avoid downloading large images multiple times. Use HEAD to check availability + size, then download only the selected candidate.

### Decision 2: Dimensions optional (return null if unavailable)
**Rationale:** Extracting dimensions requires partial download or full download, which adds complexity and latency. Filesize alone is sufficient for initial version. Can be enhanced later.

### Decision 3: Reuse existing cover download flow
**Rationale:** `books.py` already has `download_cover` function that handles external URLs → local files. No need to duplicate logic. Just pass the external URL from modal to `cover_url` field, and the save flow handles the rest.

### Decision 4: No caching of provider results
**Rationale:** Search is fast (<5s), and covers don't change frequently. Caching adds complexity. Can be added later if needed.

### Decision 5: Use daisyUI modal pattern
**Rationale:** Consistent with existing UI components (`BookDetailDialog`, `AddBookModal`, etc.). Leverages existing CSS and behavior.

---

## Appendix A: Example API Response

**Request:**
```
GET /api/cover-candidates/search?isbn=9780451524935
```

**Response (200 OK):**
```json
{
  "candidates": [
    {
      "source": "abebooks",
      "url": "https://pictures.abebooks.com/isbn/9780451524935-de.jpg",
      "available": true,
      "width": null,
      "height": null,
      "filesize": 47832,
      "content_type": "image/jpeg"
    },
    {
      "source": "openlibrary",
      "url": "https://covers.openlibrary.org/b/isbn/9780451524935-M.jpg",
      "available": true,
      "width": null,
      "height": null,
      "filesize": 52104,
      "content_type": "image/jpeg"
    },
    {
      "source": "amazon",
      "url": "https://images-eu.ssl-images-amazon.com/images/P/9780451524935.01.L.jpg",
      "available": false,
      "width": null,
      "height": null,
      "filesize": null,
      "content_type": null
    }
  ],
  "query_isbn": "9780451524935"
}
```

---

## Appendix B: Provider URL Patterns

| Provider | URL Template | Notes |
|----------|--------------|-------|
| AbeBooks | `https://pictures.abebooks.com/isbn/{isbn13}-de.jpg` | `-de` suffix for German region; other regions: `-us`, `-uk` |
| OpenLibrary | `https://covers.openlibrary.org/b/isbn/{isbn13}-M.jpg` | `-M` for medium size; also available: `-S` (small), `-L` (large) |
| Amazon | `https://images-eu.ssl-images-amazon.com/images/P/{isbn13}.01.L.jpg` | `.01.L` for large size; region: `-eu` (Europe), `-na` (North America) |

**Future consideration:** Make region/size configurable per user or globally.

---

## Appendix C: Error Messages

| Error Code | Message Key | EN Text | DE Text |
|------------|-------------|---------|---------|
| 400 | `error.invalidIsbn` | Invalid ISBN format | Ungültiges ISBN-Format |
| 500 | `error.networkError` | Network error | Netzwerkfehler |
| Modal | `book.autoSearchNoResults` | No covers found for this ISBN. | Keine Cover für diese ISBN gefunden. |
| Modal | `book.autoSearchError` | Failed to search for covers. Please try again. | Fehler beim Suchen von Covern. Bitte versuchen Sie es erneut. |

---

**End of Plan 55**
