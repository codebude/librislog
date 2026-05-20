# Plan 56: Add hardcover.app as Fourth Cover Datasource

## Overview

Extend the existing cover candidates search feature to include **hardcover.app** as a fourth datasource alongside AbeBooks, OpenLibrary, and Amazon. Unlike the existing sources which use simple HEAD probes on static image URLs, hardcover.app requires GraphQL API authentication and a different query pattern.

**Key Goals:**
- Add hardcover.app GraphQL API integration to cover candidate search
- Make hardcover source conditional on API token configuration
- Maintain consistency with existing three-source architecture
- Preserve HEAD probe validation for image URLs returned from GraphQL
- Ensure graceful degradation when token is not configured

---

## 1. Current Architecture Analysis

### 1.1 Existing Flow

The current implementation in `backend/app/routers/cover_candidates.py`:

1. **ISBN Normalization** (lines 22-54):
   - `_normalize_isbn()`: Converts ISBN-10 to ISBN-13
   - `_isbn13_to_isbn10()`: Derives ISBN-10 from ISBN-13 (if 978 prefix)

2. **URL Building** (lines 146-154):
   - Static URL patterns for each provider
   - ISBN-13 URL + ISBN-10 URL (if available) for each source

3. **Probing Strategy** (lines 56-129):
   - `_probe_candidate()`: HEAD request to check status/content-type/size
   - `_probe_source_candidates()`: Tries ISBN-13 first, then ISBN-10 fallback
   - Returns first available candidate per source

4. **Parallel Execution** (lines 159-165):
   - `asyncio.gather()` runs all source probes concurrently
   - Uses `_PROBE_SEMAPHORE` (20 concurrent requests max)
   - Results returned as `CoverCandidateList`

### 1.2 Key Challenge: GraphQL vs HEAD Probes

**Existing sources** (AbeBooks, OpenLibrary, Amazon):
- Direct image URLs
- HEAD probe checks availability + metadata

**Hardcover.app**:
- Requires POST request to GraphQL API
- Returns image URL in response body
- Image URL needs separate validation probe

This requires a **two-step process**:
1. GraphQL query to get image URL
2. HEAD probe on returned URL (same as other sources)

---

## 2. Implementation Strategy

### 2.1 Configuration Layer

**File:** `backend/app/config.py`

**Changes:**

Add new setting after line 39 (`cover_import_timeout_seconds`):

```python
hardcover_app_api_token: str = ""
```

**Also update `.env.example`** after line 29:

```bash
# Cover search settings
COVER_CANDIDATE_TIMEOUT_SECONDS=5
COVER_CANDIDATE_MIN_SIZE_BYTES=1000
COVER_IMPORT_TIMEOUT_SECONDS=15
HARDCOVER_APP_API_TOKEN=         # Optional: hardcover.app GraphQL API token
                                 # Leave empty to disable hardcover as a cover source
                                 # Get a token at https://hardcover.app/api
```

**Rationale:**
- Empty string default means hardcover is disabled by default
- Non-disruptive: existing installations work without configuration
- Follows pattern of `google_books_api_key` (optional API key)

---

### 2.2 GraphQL Integration

**File:** `backend/app/routers/cover_candidates.py`

#### 2.2.1 Add GraphQL Query Function

Insert after `_isbn13_to_isbn10()` function (around line 55):

```python
async def _query_hardcover_graphql(
    isbn13: str,
    client: httpx.AsyncClient,
    api_token: str,
) -> str | None:
    """
    Query hardcover.app GraphQL API for cover image URL by ISBN-13.
    
    Returns:
        Image URL string if found, None otherwise.
    """
    query = """
    query CoverQuery($isbn: String!) {
      book_mappings(limit: 1, where: {edition: {isbn_13: {_eq: $isbn}}}) {
        edition {
          image {
            url
          }
        }
      }
    }
    """
    
    variables = {"isbn": isbn13}
    
    try:
        async with _PROBE_SEMAPHORE:
            resp = await client.post(
                "https://api.hardcover.app/v1/graphql",
                json={"query": query, "variables": variables},
                headers={"Authorization": f"Bearer {api_token}"},
            )
        
        if resp.status_code != 200:
            logger.debug(
                "hardcover GraphQL error status=%d body=%s",
                resp.status_code,
                resp.text[:200]
            )
            return None
        
        data = resp.json()
        
        # Navigate response structure: data.book_mappings[0].edition.image.url
        book_mappings = data.get("data", {}).get("book_mappings", [])
        if not book_mappings:
            logger.debug("hardcover no book_mappings for isbn=%s", isbn13)
            return None
        
        edition = book_mappings[0].get("edition", {})
        image = edition.get("image", {})
        url = image.get("url")
        
        if not url:
            logger.debug("hardcover no image URL for isbn=%s", isbn13)
            return None
        
        logger.debug("hardcover found url=%s for isbn=%s", url, isbn13)
        return url
        
    except Exception as exc:
        logger.warning("hardcover GraphQL query failed for isbn=%s: %s", isbn13, exc)
        return None
```

**Key Design Decisions:**

1. **Semaphore Usage**: GraphQL POST request also uses `_PROBE_SEMAPHORE` to respect global concurrency limit

2. **Error Handling**: 
   - Non-200 status → return `None` (log for debugging)
   - Missing data in response → return `None`
   - Exceptions → log warning, return `None`
   - Never raises exceptions (graceful degradation)

3. **Response Navigation**: Safe dictionary access with `.get()` at each level to avoid KeyError

4. **Logging**: Debug-level logs for normal failures, warning for exceptions

---

#### 2.2.2 Add Hardcover Probe Function

Insert after `_query_hardcover_graphql()`:

```python
async def _probe_hardcover_candidate(
    client: httpx.AsyncClient,
    isbn13: str,
    api_token: str,
    min_size_bytes: int,
) -> CoverCandidate:
    """
    Probe hardcover.app for cover via GraphQL, then validate image URL.
    
    Two-step process:
    1. GraphQL query to get image URL
    2. HEAD probe to verify image availability and size
    """
    # Step 1: GraphQL query
    image_url = await _query_hardcover_graphql(isbn13, client, api_token)
    
    if not image_url:
        # GraphQL query failed or returned no results
        return CoverCandidate(
            source="hardcover",
            url="",  # No URL available
            available=False,
        )
    
    # Step 2: HEAD probe on returned image URL
    return await _probe_candidate("hardcover", image_url, client, min_size_bytes)
```

**Rationale:**
- Reuses existing `_probe_candidate()` for HEAD validation
- Maintains consistency: hardcover images validated same as other sources
- Two-step approach clearly separated
- If GraphQL fails, returns unavailable candidate with empty URL

---

#### 2.2.3 Update Main Search Endpoint

Modify `search_cover_candidates()` function (starting at line 132):

**Current code** (lines 146-165):
```python
provider_urls: dict[str, list[str]] = {
    "abebooks": [f"https://pictures.abebooks.com/isbn/{normalized_isbn13}-de.jpg"],
    "openlibrary": [f"https://covers.openlibrary.org/b/isbn/{normalized_isbn13}-M.jpg"],
    "amazon": [f"https://images-eu.ssl-images-amazon.com/images/P/{normalized_isbn13}.01.L.jpg"],
}
if isbn10 is not None:
    provider_urls["abebooks"].append(f"https://pictures.abebooks.com/isbn/{isbn10}-de.jpg")
    provider_urls["openlibrary"].append(f"https://covers.openlibrary.org/b/isbn/{isbn10}-M.jpg")
    provider_urls["amazon"].append(f"https://images-eu.ssl-images-amazon.com/images/P/{isbn10}.01.L.jpg")

logger.debug("cover candidate provider URLs: %s", provider_urls)

timeout = httpx.Timeout(settings.cover_candidate_timeout_seconds)
async with httpx.AsyncClient(timeout=timeout) as client:
    results = await asyncio.gather(
        *[
            _probe_source_candidates(source, urls, client, settings.cover_candidate_min_size_bytes)
            for source, urls in provider_urls.items()
        ]
    )
```

**Change to**:

```python
provider_urls: dict[str, list[str]] = {
    "abebooks": [f"https://pictures.abebooks.com/isbn/{normalized_isbn13}-de.jpg"],
    "openlibrary": [f"https://covers.openlibrary.org/b/isbn/{normalized_isbn13}-M.jpg"],
    "amazon": [f"https://images-eu.ssl-images-amazon.com/images/P/{normalized_isbn13}.01.L.jpg"],
}
if isbn10 is not None:
    provider_urls["abebooks"].append(f"https://pictures.abebooks.com/isbn/{isbn10}-de.jpg")
    provider_urls["openlibrary"].append(f"https://covers.openlibrary.org/b/isbn/{isbn10}-M.jpg")
    provider_urls["amazon"].append(f"https://images-eu.ssl-images-amazon.com/images/P/{isbn10}.01.L.jpg")

logger.debug("cover candidate provider URLs: %s", provider_urls)

timeout = httpx.Timeout(settings.cover_candidate_timeout_seconds)
async with httpx.AsyncClient(timeout=timeout) as client:
    # Build task list for URL-based providers
    tasks = [
        _probe_source_candidates(source, urls, client, settings.cover_candidate_min_size_bytes)
        for source, urls in provider_urls.items()
    ]
    
    # Add hardcover task if token is configured
    if settings.hardcover_app_api_token.strip():
        logger.debug("cover candidate adding hardcover source (token configured)")
        tasks.append(
            _probe_hardcover_candidate(
                client,
                normalized_isbn13,
                settings.hardcover_app_api_token,
                settings.cover_candidate_min_size_bytes,
            )
        )
    else:
        logger.debug("cover candidate skipping hardcover (no token configured)")
    
    results = await asyncio.gather(*tasks)
```

**Key Changes:**

1. **Conditional Inclusion**: Hardcover task only added when `hardcover_app_api_token` is non-empty (after stripping whitespace)

2. **Separate Task**: Hardcover uses different probe function (`_probe_hardcover_candidate` instead of `_probe_source_candidates`)

3. **Logging**: Debug logs indicate whether hardcover is enabled/disabled

4. **No Breaking Changes**: 
   - Existing three sources work identically
   - `asyncio.gather()` call unchanged
   - Return type unchanged (`CoverCandidateList`)

---

### 2.3 Error Handling & Edge Cases

#### 2.3.1 GraphQL Error Scenarios

| Scenario | HTTP Status | Behavior |
|----------|-------------|----------|
| Invalid token | 401/403 | Return `None`, log warning |
| Rate limit exceeded | 429 | Return `None`, log warning |
| Server error | 500/502/503 | Return `None`, log warning |
| Timeout | N/A (exception) | Return `None`, log warning |
| Malformed response | 200 but invalid JSON | Return `None`, log exception |
| No results | 200 with empty `book_mappings` | Return `None`, log debug |
| Image URL null | 200 with `image: null` | Return `None`, log debug |

**Implementation:** All handled by `_query_hardcover_graphql()` exception wrapper and response validation.

#### 2.3.2 HEAD Probe Validation

After GraphQL returns an image URL, the standard `_probe_candidate()` function validates:
- HTTP 200 status
- `Content-Type: image/*`
- `Content-Length >= cover_candidate_min_size_bytes`

This ensures hardcover images meet the same quality standards as other sources.

#### 2.3.3 Token Not Configured

When `HARDCOVER_APP_API_TOKEN` is empty or not set:
- Hardcover task not added to `asyncio.gather()`
- No API calls made to hardcover.app
- Result list contains 3 candidates (AbeBooks, OpenLibrary, Amazon)
- Frontend displays available candidates (no change needed)

---

## 3. Testing Strategy

### 3.1 Backend Unit Tests

**File:** `backend/tests/test_cover_candidates.py`

#### 3.1.1 Add Hardcover Test Cases

Insert after existing tests (around line 172):

```python
def test_cover_candidates_hardcover_with_token(client: TestClient, monkeypatch):
    """Hardcover source included when token is configured."""
    monkeypatch.setenv("HARDCOVER_APP_API_TOKEN", "test_token_12345")
    
    # Reload settings to pick up new env var
    from app.config import Settings
    from app import config
    config.settings = Settings()
    
    requested_urls = []
    graphql_requests = []

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data=None):
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}

        def json(self):
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            requested_urls.append(url)
            # Hardcover image URL returns 200
            if "assets.hardcover.app" in url:
                return _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "50000"}, url)
            # Other sources return 404
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs):
            graphql_requests.append((url, kwargs))
            # Mock hardcover GraphQL response
            if "hardcover.app" in url:
                return _FakeResponse(
                    200,
                    {"content-type": "application/json"},
                    url,
                    {
                        "data": {
                            "book_mappings": [
                                {
                                    "edition": {
                                        "image": {
                                            "url": "https://assets.hardcover.app/editions/12345/cover.jpg"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                )
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    assert data["query_isbn"] == "9783426440087"
    
    # Should have 4 candidates (3 URL-based + 1 hardcover)
    assert len(data["candidates"]) == 4
    
    by_source = {item["source"]: item for item in data["candidates"]}
    
    # Hardcover should be available
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is True
    assert "assets.hardcover.app" in by_source["hardcover"]["url"]
    
    # Other sources should be unavailable
    assert by_source["abebooks"]["available"] is False
    assert by_source["openlibrary"]["available"] is False
    assert by_source["amazon"]["available"] is False
    
    # Verify GraphQL request was made
    assert len(graphql_requests) == 1
    gql_url, gql_kwargs = graphql_requests[0]
    assert "hardcover.app/v1/graphql" in gql_url
    assert "Authorization" in gql_kwargs["headers"]
    assert gql_kwargs["headers"]["Authorization"] == "Bearer test_token_12345"


def test_cover_candidates_hardcover_without_token(client: TestClient, monkeypatch):
    """Hardcover source excluded when token is not configured."""
    # Ensure token is empty
    monkeypatch.setenv("HARDCOVER_APP_API_TOKEN", "")
    
    from app.config import Settings
    from app import config
    config.settings = Settings()
    
    graphql_requests = []

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str):
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs):
            graphql_requests.append((url, kwargs))
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    
    # Should have only 3 candidates (no hardcover)
    assert len(data["candidates"]) == 3
    
    sources = [item["source"] for item in data["candidates"]]
    assert "hardcover" not in sources
    assert "abebooks" in sources
    assert "openlibrary" in sources
    assert "amazon" in sources
    
    # No GraphQL requests should be made
    assert len(graphql_requests) == 0


def test_cover_candidates_hardcover_graphql_error(client: TestClient, monkeypatch):
    """Hardcover returns unavailable when GraphQL fails."""
    monkeypatch.setenv("HARDCOVER_APP_API_TOKEN", "test_token")
    
    from app.config import Settings
    from app import config
    config.settings = Settings()

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, text=""):
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self.text = text

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs):
            # Mock GraphQL error (401 Unauthorized)
            if "hardcover.app" in url:
                return _FakeResponse(401, {}, url, "Unauthorized")
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    
    # Should have 4 candidates, but hardcover should be unavailable
    assert len(data["candidates"]) == 4
    
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is False


def test_cover_candidates_hardcover_no_results(client: TestClient, monkeypatch):
    """Hardcover returns unavailable when no book found."""
    monkeypatch.setenv("HARDCOVER_APP_API_TOKEN", "test_token")
    
    from app.config import Settings
    from app import config
    config.settings = Settings()

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data=None):
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}

        def json(self):
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs):
            # Mock hardcover response with empty book_mappings
            if "hardcover.app" in url:
                return _FakeResponse(
                    200,
                    {"content-type": "application/json"},
                    url,
                    {"data": {"book_mappings": []}}
                )
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is False
    assert by_source["hardcover"]["url"] == ""  # No URL when GraphQL returns no results
```

**Test Coverage:**

1. ✅ Hardcover included when token configured
2. ✅ Hardcover excluded when token empty
3. ✅ Hardcover unavailable on GraphQL error (401)
4. ✅ Hardcover unavailable when no book found
5. ✅ GraphQL request includes correct Authorization header
6. ✅ HEAD probe validates returned image URL

---

### 3.2 Manual Integration Testing

#### Test Plan

**Test 1: Token Not Configured (Default)**
- Ensure `HARDCOVER_APP_API_TOKEN` is empty in `.env`
- Restart backend
- Open book edit dialog, enter ISBN `9783426440087`
- Click "Auto-search covers"
- **Expected:** Modal shows 3 candidates (AbeBooks, OpenLibrary, Amazon)
- **Verify:** No hardcover candidate displayed

**Test 2: Token Configured, Book Found**
- Set `HARDCOVER_APP_API_TOKEN=<valid_token>` in `.env`
- Restart backend
- Open book edit dialog, enter ISBN `9783426440087`
- Click "Auto-search covers"
- **Expected:** Modal shows 4 candidates
- **Verify:** 
  - Hardcover candidate appears with cover image
  - Hover shows metadata (filesize, resolution if available)
  - Clicking hardcover candidate imports cover successfully

**Test 3: Token Configured, Book Not Found**
- Set `HARDCOVER_APP_API_TOKEN=<valid_token>` in `.env`
- Use an obscure ISBN unlikely to be in hardcover database (e.g., `9791234567896`)
- Click "Auto-search covers"
- **Expected:** Hardcover candidate not shown (filtered by `available: false`)
- **Verify:** Modal shows only available candidates from other sources

**Test 4: Invalid Token**
- Set `HARDCOVER_APP_API_TOKEN=invalid_token_xyz` in `.env`
- Restart backend
- Enter valid ISBN, click "Auto-search covers"
- **Expected:** Hardcover candidate unavailable (GraphQL returns 401/403)
- **Verify:** 
  - Backend logs show warning about hardcover GraphQL failure
  - Frontend displays available candidates from other sources
  - No error toast shown to user (graceful degradation)

**Test 5: Concurrent Requests**
- Configure valid token
- Open multiple book edit dialogs in different tabs
- Trigger auto-search simultaneously in all tabs
- **Expected:** All requests complete successfully
- **Verify:** Semaphore prevents overwhelming hardcover API

**Test 6: GraphQL Timeout**
- Mock slow hardcover API response (use network throttling or proxy)
- Trigger auto-search
- **Expected:** Hardcover times out after 5 seconds, other sources complete
- **Verify:** User sees available candidates from other sources

---

### 3.3 Docker Compose Integration Test

**Test Scenario:** Verify hardcover integration in Docker environment

```bash
# 1. Add token to .env
echo "HARDCOVER_APP_API_TOKEN=<your_token>" >> .env

# 2. Rebuild and start containers
docker compose down
docker compose up --build -d

# 3. Check backend logs for hardcover initialization
docker compose logs backend | grep -i hardcover

# 4. Test via curl (replace with valid token)
curl -H "Cookie: librislog_session=<session_cookie>" \
  "http://localhost:8000/api/cover-candidates/search?isbn=9783426440087"

# Expected JSON response with 4 candidates including "hardcover"
```

---

### 3.4 Playwright E2E Test (Optional)

**File:** `frontend/tests/hardcover-cover-source.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('Hardcover cover source', () => {
  test.beforeEach(async ({ page }) => {
    // Login and navigate to book edit
    await page.goto('/');
    // ... login logic ...
    // ... navigate to book edit dialog ...
  });

  test('hardcover candidate appears when token configured', async ({ page }) => {
    // Fill ISBN field
    await page.locator('input[placeholder*="ISBN"]').fill('9783426440087');
    
    // Click auto-search button
    await page.locator('button:has-text("Auto-search covers")').click();
    
    // Wait for modal
    await expect(page.locator('.modal-open')).toBeVisible();
    
    // Wait for search to complete
    await page.waitForSelector('.loading', { state: 'detached', timeout: 10000 });
    
    // Count candidates
    const candidates = page.locator('.modal-box button img');
    const count = await candidates.count();
    
    // Should have at least 1 candidate (possibly 4 if all sources available)
    expect(count).toBeGreaterThanOrEqual(1);
    
    // Check if hardcover is among them by checking hover overlay text
    // (This requires hardcover to return results for this ISBN)
  });

  test('clicking hardcover candidate imports cover', async ({ page }) => {
    await page.locator('input[placeholder*="ISBN"]').fill('9783426440087');
    await page.locator('button:has-text("Auto-search covers")').click();
    await page.waitForSelector('.loading', { state: 'detached', timeout: 10000 });
    
    // Assume first candidate is hardcover (or iterate to find it)
    const firstCandidate = page.locator('.modal-box button img').first();
    await firstCandidate.click();
    
    // Verify success toast
    await expect(page.locator('.toast:has-text("Cover imported")')).toBeVisible();
    
    // Verify modal closed
    await expect(page.locator('.modal-open')).not.toBeVisible();
  });
});
```

---

## 4. Frontend Changes

### 4.1 No Direct Changes Required

**Rationale:**
- Frontend `AutoSearchCoverModal.svelte` already handles dynamic candidate lists
- Modal filters candidates by `available: true` (line 76)
- Hardcover candidates automatically displayed when available
- Source name shown in hover overlay (line 91)
- No hardcoded source list in frontend

**Verification:**
- Inspect modal rendering with 3 vs 4 candidates
- Verify "hardcover" label appears correctly in hover overlay
- Test grid layout with 4 candidates (should flow to 2nd row)

### 4.2 Optional: Update i18n Source Labels

**File:** `frontend/src/lib/i18n/locales/en.json`

**Current:** Generic source display (lowercase source name)

**Optional Enhancement:** Add friendly display names for sources

```json
"book": {
  ...
  "coverSource": {
    "abebooks": "AbeBooks",
    "openlibrary": "Open Library",
    "amazon": "Amazon",
    "hardcover": "Hardcover"
  }
}
```

**File:** `frontend/src/lib/i18n/locales/de.json`

```json
"book": {
  ...
  "coverSource": {
    "abebooks": "AbeBooks",
    "openlibrary": "Open Library",
    "amazon": "Amazon",
    "hardcover": "Hardcover"
  }
}
```

**Update Modal Component** (line 91):

```svelte
<div class="font-semibold">
  {$_(`book.coverSource.${candidate.source}`, { default: candidate.source })}
</div>
```

**Decision:** Optional. Implement if consistent with project i18n patterns. Otherwise, display raw source name (current behavior).

---

## 5. Documentation Updates

### 5.1 Environment Variables

**File:** `.env.example`

See section 2.1 above.

### 5.2 README or Deployment Guide

**If project has deployment docs**, add section:

```markdown
### Cover Search Configuration

The auto-search cover feature queries multiple providers:
- AbeBooks
- Open Library
- Amazon
- Hardcover (optional, requires API token)

To enable Hardcover:
1. Get an API token from https://hardcover.app/api
2. Add to `.env`:
   ```
   HARDCOVER_APP_API_TOKEN=your_token_here
   ```
3. Restart backend

Hardcover is disabled by default (no token required).
```

### 5.3 Code Comments

**File:** `backend/app/routers/cover_candidates.py`

Add docstring at top of file (after imports):

```python
"""
Cover candidate search endpoint.

Queries multiple providers in parallel to find available book covers by ISBN:
- AbeBooks: Static URL pattern (HEAD probe)
- OpenLibrary: Static URL pattern (HEAD probe)
- Amazon: Static URL pattern (HEAD probe)
- Hardcover: GraphQL API (requires HARDCOVER_APP_API_TOKEN env var)

All candidates are validated via HEAD probe to check:
- HTTP 200 status
- Content-Type: image/*
- Content-Length >= cover_candidate_min_size_bytes

Hardcover source is conditional: only queried when API token is configured.
"""
```

---

## 6. Risk Analysis & Mitigations

### Risk 1: Hardcover API Rate Limits

**Impact:** High — Could block all users if token hits rate limit  
**Probability:** Medium (depends on token tier and usage)

**Mitigations:**
1. **Semaphore already in place**: `_PROBE_SEMAPHORE` limits concurrent requests
2. **Graceful degradation**: Rate limit errors return `available: false`, other sources still work
3. **Logging**: Warning logs help detect rate limit issues
4. **Documentation**: Recommend separate token per environment (dev/staging/prod)
5. **Future enhancement**: Add exponential backoff or circuit breaker pattern

**Action:** Document rate limit handling in operations guide

---

### Risk 2: GraphQL Schema Changes

**Impact:** Medium — Hardcover API changes break integration  
**Probability:** Low (GraphQL schemas typically stable)

**Mitigations:**
1. **Response validation**: Code safely navigates response with `.get()` chaining
2. **Null checks**: Missing fields return `None` instead of raising exceptions
3. **Logging**: Debug logs show response structure for troubleshooting
4. **Monitoring**: Track success rate of hardcover queries

**Action:** Add integration test that validates GraphQL response structure

---

### Risk 3: Invalid Token Configuration

**Impact:** Low — Hardcover unavailable but app continues functioning  
**Probability:** Medium (user configuration error)

**Mitigations:**
1. **Token validation**: Strip whitespace before checking if configured
2. **Graceful degradation**: 401/403 responses treated as unavailable, logged
3. **Debug logging**: Clear messages when token missing or invalid
4. **Documentation**: `.env.example` includes clear instructions

**Action:** Consider adding `/health` endpoint check for hardcover token validity (future enhancement)

---

### Risk 4: Slow GraphQL Responses

**Impact:** Medium — Delays auto-search modal for all users  
**Probability:** Low (API typically fast)

**Mitigations:**
1. **Timeout configured**: Uses `cover_candidate_timeout_seconds` (5s default)
2. **Parallel execution**: `asyncio.gather()` means slow hardcover doesn't block other sources
3. **Semaphore**: Prevents overwhelming API with concurrent requests
4. **Logging**: Warning logs show timeout occurrences

**Action:** Monitor response times in production logs

---

### Risk 5: ISBN-13 Only Support

**Impact:** Low — Hardcover doesn't support ISBN-10 fallback like other sources  
**Probability:** N/A (design limitation)

**Mitigations:**
1. **ISBN-13 normalized first**: All queries use ISBN-13 (including hardcover)
2. **Consistent behavior**: Other sources also query ISBN-13 first
3. **Documentation**: Note in code comments that hardcover uses ISBN-13 only

**Action:** None needed (acceptable limitation)

---

## 7. Implementation Checklist

### Phase 1: Configuration & Setup
- [ ] Add `hardcover_app_api_token: str = ""` to `Settings` in `backend/app/config.py` (after line 39)
- [ ] Update `.env.example` with hardcover token section and comments
- [ ] Obtain test API token from hardcover.app for development
- [ ] Add test token to local `.env` file

### Phase 2: Backend Implementation
- [ ] Add `_query_hardcover_graphql()` function to `backend/app/routers/cover_candidates.py`
  - GraphQL query structure
  - Authorization header
  - Response navigation and validation
  - Error handling (status codes, exceptions)
  - Debug logging
- [ ] Add `_probe_hardcover_candidate()` function
  - Call `_query_hardcover_graphql()`
  - Pass URL to `_probe_candidate()` for HEAD validation
  - Return unavailable candidate if GraphQL fails
- [ ] Update `search_cover_candidates()` function
  - Add conditional hardcover task to `asyncio.gather()`
  - Check `settings.hardcover_app_api_token.strip()`
  - Add debug logging for token presence

### Phase 3: Testing
- [ ] Add unit tests to `backend/tests/test_cover_candidates.py`:
  - `test_cover_candidates_hardcover_with_token()` — 4 candidates returned
  - `test_cover_candidates_hardcover_without_token()` — 3 candidates, no GraphQL calls
  - `test_cover_candidates_hardcover_graphql_error()` — 401 returns unavailable
  - `test_cover_candidates_hardcover_no_results()` — empty book_mappings
- [ ] Run pytest: `pytest backend/tests/test_cover_candidates.py -v`
- [ ] Manual testing:
  - Test with token configured (valid ISBN)
  - Test without token
  - Test with invalid token
  - Test with ISBN not in hardcover database
- [ ] Docker Compose integration test
- [ ] Optional: Add Playwright E2E test

### Phase 4: Frontend Verification
- [ ] Open auto-search modal with token configured
- [ ] Verify 4 candidates displayed (if ISBN has hardcover match)
- [ ] Check hover overlay shows "hardcover" source label
- [ ] Test clicking hardcover candidate imports successfully
- [ ] Verify grid layout with 4 candidates renders correctly
- [ ] Test without token — verify 3 candidates only

### Phase 5: Documentation & Polish
- [ ] Add docstring to `backend/app/routers/cover_candidates.py` file header
- [ ] Update deployment/operations documentation with hardcover token setup
- [ ] Add inline comments explaining GraphQL two-step process
- [ ] Update `README.md` with hardcover API token instructions (if applicable)
- [ ] Document rate limit considerations

### Phase 6: Pre-Deployment Review
- [ ] Code review: error handling, logging, security
- [ ] Verify no hardcoded tokens in code
- [ ] Check `.gitignore` excludes `.env`
- [ ] Verify graceful degradation when token invalid/missing
- [ ] Review GraphQL query for SQL injection risk (N/A for GraphQL, but validate)
- [ ] Confirm timeout settings appropriate
- [ ] Check semaphore limit sufficient for concurrent users

### Phase 7: Deployment
- [ ] Deploy to staging environment
- [ ] Configure `HARDCOVER_APP_API_TOKEN` in staging `.env`
- [ ] Run full regression test suite
- [ ] Monitor backend logs for hardcover errors
- [ ] Deploy to production
- [ ] Monitor error rates and response times

---

## 8. Acceptance Criteria

### Backend
- ✅ `HARDCOVER_APP_API_TOKEN` setting added to `config.py`
- ✅ GraphQL query function implemented with proper error handling
- ✅ Hardcover probe function reuses existing HEAD validation
- ✅ Hardcover task conditionally added to `asyncio.gather()`
- ✅ Token presence checked via `.strip()` (whitespace ignored)
- ✅ GraphQL failures return unavailable candidate (no exceptions raised)
- ✅ Authorization header correctly formatted: `Bearer <token>`
- ✅ Semaphore applied to GraphQL POST requests
- ✅ Debug logs show GraphQL request/response details
- ✅ Warning logs show API errors

### Testing
- ✅ 4 unit tests pass covering token/no-token/error/no-results scenarios
- ✅ Manual testing confirms 4 candidates when token valid
- ✅ Manual testing confirms 3 candidates when token empty
- ✅ Graceful degradation on invalid token (no user-visible error)
- ✅ Docker Compose integration test passes

### Frontend
- ✅ No code changes required (dynamic candidate rendering)
- ✅ Modal displays 4 candidates when hardcover available
- ✅ Hardcover source label appears in hover overlay
- ✅ Clicking hardcover candidate imports successfully
- ✅ Grid layout handles 4 candidates without overflow

### Documentation
- ✅ `.env.example` includes hardcover token with comments
- ✅ Code docstrings explain GraphQL integration
- ✅ Deployment guide updated with token setup instructions

### Security & Operations
- ✅ No hardcoded tokens in repository
- ✅ Token loaded from environment variable only
- ✅ GraphQL errors logged but not exposed to frontend
- ✅ Rate limit failures handled gracefully
- ✅ Timeout prevents hanging requests

---

## 9. Future Enhancements (Out of Scope)

### 9.1 Health Check Integration
Add hardcover token validation to `/health` endpoint:
- Test GraphQL query on startup
- Report token status in health response
- Alert if token invalid or rate limited

### 9.2 Circuit Breaker Pattern
Disable hardcover temporarily after repeated failures:
- Track error rate per time window
- Skip hardcover queries if error rate > threshold
- Auto-reset after cooldown period

### 9.3 Response Caching
Cache GraphQL responses per ISBN:
- Redis/in-memory cache with TTL (e.g., 24 hours)
- Reduce API calls for popular ISBNs
- Invalidate on explicit user request

### 9.4 ISBN-10 Fallback
Query hardcover with both ISBN-13 and ISBN-10:
- Check if hardcover API supports ISBN-10 lookups
- Add second GraphQL query with ISBN-10 if ISBN-13 fails
- Consistent with other sources' fallback strategy

### 9.5 Additional Hardcover Metadata
Extract more fields from GraphQL response:
- Book title (for validation)
- Cover dimensions (if provided by API)
- Cover aspect ratio (for better grid layout)

### 9.6 User-Configurable Token
Allow users to provide their own hardcover tokens:
- Per-user settings table
- Override global token if user token exists
- Support multi-tenant deployments

---

## 10. GraphQL Reference

### 10.1 Query Structure

```graphql
query CoverQuery($isbn: String!) {
  book_mappings(limit: 1, where: {edition: {isbn_13: {_eq: $isbn}}}) {
    edition {
      image {
        url
      }
    }
  }
}
```

**Variables:**
```json
{
  "isbn": "9783426440087"
}
```

**Headers:**
```
Authorization: Bearer <your_token>
Content-Type: application/json
```

---

### 10.2 Response Examples

**Success (book found):**
```json
{
  "data": {
    "book_mappings": [
      {
        "edition": {
          "image": {
            "url": "https://assets.hardcover.app/editions/31027383/9694734858477922.jpg"
          }
        }
      }
    ]
  }
}
```

**No results (book not found):**
```json
{
  "data": {
    "book_mappings": []
  }
}
```

**Error (invalid token):**
```json
{
  "errors": [
    {
      "message": "Unauthorized",
      "extensions": {
        "code": "UNAUTHENTICATED"
      }
    }
  ]
}
```

---

### 10.3 API Endpoint

- **URL:** `https://api.hardcover.app/v1/graphql`
- **Method:** `POST`
- **Content-Type:** `application/json`
- **Authentication:** Bearer token in Authorization header

**Rate Limits (estimated, verify with hardcover docs):**
- Free tier: ~100 requests/hour
- Paid tiers: Higher limits

**Documentation:** https://hardcover.app/api (check for official docs)

---

## 11. Code Review Checklist

Before submitting for review, verify:

### Security
- [ ] No hardcoded API tokens in code
- [ ] Token loaded from environment variable
- [ ] GraphQL query uses parameterized variables (SQL injection N/A)
- [ ] Authorization header not logged (debug logs show redacted token)
- [ ] No sensitive data in exception messages

### Error Handling
- [ ] All exception types caught and logged
- [ ] GraphQL errors return `None` (no exceptions propagated)
- [ ] HTTP errors (401/403/429/500) handled gracefully
- [ ] Missing response fields don't raise KeyError
- [ ] Timeout exceptions caught and logged

### Logging
- [ ] Debug logs show GraphQL request structure (without token)
- [ ] Warning logs show API errors with context
- [ ] Success logs show ISBN and result count
- [ ] No PII or tokens in logs

### Performance
- [ ] GraphQL request uses semaphore (respects global limit)
- [ ] Timeout configured (reuses `cover_candidate_timeout_seconds`)
- [ ] Parallel execution with `asyncio.gather()`
- [ ] No blocking I/O in async functions

### Testing
- [ ] Unit tests cover happy path (token configured, book found)
- [ ] Unit tests cover edge cases (no token, API error, no results)
- [ ] Tests use monkeypatch for environment variables
- [ ] Tests mock httpx client for both HEAD and POST
- [ ] Tests verify Authorization header format

### Code Quality
- [ ] Type hints for function parameters and return types
- [ ] Docstrings for new functions
- [ ] Consistent naming conventions
- [ ] No dead code or commented-out sections
- [ ] Follows existing code style (matches `_probe_candidate` patterns)

---

## 12. Rollback Plan

If issues discovered in production:

### Immediate Rollback (< 5 minutes)
1. Remove `HARDCOVER_APP_API_TOKEN` from production `.env`
2. Restart backend (graceful reload if supported)
3. Verify auto-search returns 3 candidates only

**Impact:** Hardcover source disabled, other sources unaffected

### Code Revert (if needed)
1. Revert commit adding hardcover integration
2. Redeploy previous version
3. Restart backend

**Impact:** Full rollback to previous behavior

### Debugging Steps
1. Check backend logs for GraphQL errors:
   ```bash
   docker compose logs backend | grep -i hardcover
   ```
2. Test GraphQL endpoint directly:
   ```bash
   curl -X POST https://api.hardcover.app/v1/graphql \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"query": "query { __typename }", "variables": {}}'
   ```
3. Verify token validity in hardcover dashboard
4. Check rate limit status

---

## Appendix A: GraphQL Query Validation

### Test GraphQL Query Independently

```bash
# Save query to file
cat > query.graphql <<'EOF'
query CoverQuery($isbn: String!) {
  book_mappings(limit: 1, where: {edition: {isbn_13: {_eq: $isbn}}}) {
    edition {
      image {
        url
      }
    }
  }
}
EOF

# Test with curl
curl -X POST https://api.hardcover.app/v1/graphql \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query CoverQuery($isbn: String!) { book_mappings(limit: 1, where: {edition: {isbn_13: {_eq: $isbn}}}) { edition { image { url } } } }",
    "variables": {"isbn": "9783426440087"}
  }' | jq
```

**Expected output:**
```json
{
  "data": {
    "book_mappings": [
      {
        "edition": {
          "image": {
            "url": "https://assets.hardcover.app/editions/..."
          }
        }
      }
    ]
  }
}
```

---

## Appendix B: Monitoring Queries

### Backend Log Queries

**Count hardcover requests:**
```bash
docker compose logs backend | grep "hardcover GraphQL" | wc -l
```

**Find hardcover errors:**
```bash
docker compose logs backend | grep -i "hardcover" | grep -iE "(error|warn|fail)"
```

**Check success rate:**
```bash
docker compose logs backend | \
  grep "cover candidate results" | \
  grep -c "hardcover.*available.*True"
```

### Health Metrics (Future)

Add Prometheus/Grafana metrics:
- `cover_candidates_requests_total{source="hardcover"}`
- `cover_candidates_errors_total{source="hardcover",type="graphql_error"}`
- `cover_candidates_latency_seconds{source="hardcover"}`

---

## Appendix C: Token Management

### Development Environment
- Use personal hardcover account token
- Store in `.env` (gitignored)
- Rotate periodically (e.g., monthly)

### Staging Environment
- Use separate staging token (if available)
- Store in environment variable (Docker secrets, K8s secret, etc.)
- Test rate limiting with load tests

### Production Environment
- Use production-tier token (higher rate limits)
- Store in secrets manager (AWS Secrets Manager, Vault, etc.)
- Monitor usage via hardcover dashboard
- Set up alerts for rate limit warnings
- Document token rotation procedure

### Token Rotation Procedure
1. Generate new token in hardcover dashboard
2. Update secrets manager
3. Trigger rolling deployment (zero downtime)
4. Verify new token works
5. Revoke old token after 24-hour grace period

---

**End of Plan 56**
