# Plan 58: Add Thalia.de as Fifth Cover Datasource (via Scrapling)

## Overview

Extend the existing cover candidates search feature to include **Thalia.de** as a fifth datasource alongside AbeBooks, OpenLibrary, Amazon, and Hardcover. Unlike existing sources which use direct image URL probes or GraphQL, Thalia requires **web scraping** of its search results page using the **Scrapling** library to dynamically extract cover image URLs.

**Key Goals:**
- Add Thalia.de search page scraping to cover candidate search
- Use Scrapling's `Fetcher` for lightweight HTTP scraping (no browser dependency)
- Run Scrapling in a thread (`asyncio.to_thread()`) to remain async-compatible
- Rewrite Thalia CDN image URL path from segment `03`/variable to `00` (higher-res)
- Validate extracted image URLs via existing HEAD probe (`_probe_candidate()`)
- Make Thalia source conditional on a `thalia_cover_search_enabled` setting (default: enabled)
- Graceful degradation on scrape failure (network block, no results, parsing errors)

---

## 1. Current Architecture Analysis

### 1.1 Existing Flow

The current implementation in `backend/app/routers/cover_candidates.py`:

1. **ISBN Normalization** (lines 185-195):
   - `normalize_isbn()`: Converts ISBN-10 to ISBN-13
   - `isbn13_to_isbn10()`: Derives ISBN-10 from ISBN-13 (if 978 prefix)

2. **URL Building** (lines 197-206):
   - Static URL patterns for AbeBooks, OpenLibrary, Amazon
   - ISBN-13 URL + ISBN-10 URL (if available) for each source

3. **Probing Strategy** (lines 104-177):
   - `_probe_candidate()`: HEAD request to check status/content-type/size
   - `_probe_source_candidates()`: Tries ISBN-13 first, then ISBN-10 fallback per source
   - Returns first available candidate per source
   - `_probe_hardcover_candidate()`: GraphQL two-step for Hardcover

4. **Parallel Execution** (lines 210-229):
   - Task list built in `search_cover_candidates()`
   - Hardcover conditionally appended if `hardcover_app_api_token` is set
   - `asyncio.gather()` runs all source probes concurrently
   - Uses `_PROBE_SEMAPHORE` (20 concurrent requests max)
   - Results returned as `CoverCandidateList`

### 1.2 Key Challenge: Synchronous Web Scraping in Async Context

**Existing sources:**
- AbeBooks, OpenLibrary, Amazon: Direct image URL → HEAD probe
- Hardcover: GraphQL POST → image URL → HEAD probe

**Thalia.de (new):**
- Requires fetching and parsing an HTML search results page
- Scrapling is a **synchronous** library
- Must run Scrapling calls in a thread via `asyncio.to_thread()` to remain compatible with `asyncio.gather()`
- Extracted image URL needs URL rewriting (replace first path segment with `00`)
- Final HEAD probe on rewritten URL

This requires a **three-step process**:
1. Scrape Thalia search page in a thread → extract image URL
2. Rewrite CDN URL path segment to `00`
3. HEAD probe on rewritten URL (same as other sources)

### 1.3 Scrapling Overview

Scrapling is a lightweight, modern Python web scraping library with:
- `Fetcher` class for making HTTP requests (no browser/Playwright needed)
- Auto-detection of encoding
- CSS selector and XPath parsing
- Built-in support for common anti-bot evasion patterns
- Lightweight footprint (no Playwright/Puppeteer dependency)

**Relevant Scrapling API:**
```python
from scrapling import Fetcher

# Basic usage (sync)
fetcher = Fetcher()
page = fetcher.get('https://www.thalia.de/suche?sq=9783440513033')

# CSS selector with attribute extraction
page.css('dl-pageview::attr(suchtreffer)')    # returns list of values
page.css('suche-produktliste > div > ul > li:nth-child(1) > picture > img::attr(src)')  # returns list of src values
```

### 1.4 Thalia.de Search Page Structure

Search URL: `https://www.thalia.de/suche?sq={isbn13}`

**Response includes:**
```html
<dl-pageview suchbegriff="9783440513033" suchtreffer="1"></dl-pageview>
```

- `suchtreffer` attribute = count of search results
- If `suchtreffer="0"`, no results → stop

**Image element selector for first result:**
```css
suche-produktliste > div > ul > li:nth-child(1) > picture > img
```

**Extracted URL pattern (from `src` attribute):**
```
https://images.thalia.media/03/-/...
```

**URL rewriting:** Replace first path segment after domain with `00`:
- Before: `https://images.thalia.media/03/-/...`
- After:  `https://images.thalia.media/00/-/...`

The `00` segment appears to provide a higher-resolution (or more reliable) image URL.

---

## 2. Implementation Strategy

### 2.1 Configuration Layer

**File:** `backend/app/config.py`

**Changes:**

Add new setting after line 40 (`hardcover_app_api_token`):

```python
thalia_cover_search_enabled: bool = True
```

**Rationale:**
- Default `True` means Thalia is enabled out of the box (no API token needed)
- Can be disabled via `THALIA_COVER_SEARCH_ENABLED=false` in `.env`
- Follows the pattern of existing boolean flags like `dashboard_quote_enabled`, `oidc_enabled`

**Also update `.env.example`** after the cover search settings section:

```bash
# Cover search settings
COVER_CANDIDATE_TIMEOUT_SECONDS=5
COVER_CANDIDATE_MIN_SIZE_BYTES=1000
COVER_IMPORT_TIMEOUT_SECONDS=15
HARDCOVER_APP_API_TOKEN=         # Optional: hardcover.app GraphQL API token
                                 # Leave empty to disable hardcover as a cover source
                                 # Get a token at https://hardcover.app/api
THALIA_COVER_SEARCH_ENABLED=true # Optional: enable/disable Thalia.de cover search (default: true)
                                 # Thalia does not require an API key
```

---

### 2.2 Dependency: Add Scrapling

**File:** `backend/pyproject.toml`

Add to `[project] dependencies`:

```toml
"scrapling>=0.12.5",
```

The exact version should be the latest stable release at implementation time. Check PyPI for the current version.

**Run after adding:**
```bash
cd backend && uv lock && uv sync
```

---

### 2.3 Scraping Logic: `_probe_thalia_candidate()`

**File:** `backend/app/routers/cover_candidates.py`

#### 2.3.1 Add Thalia Probe Function

Insert after `_probe_hardcover_candidate()` function (after line 101):

```python
def _fetch_thalia_page_sync(isbn13: str, timeout_seconds: int) -> str | None:
    """
    Synchronously fetch Thalia.de search page and extract cover image URL.
    
    Runs in a thread via asyncio.to_thread() to remain async-compatible.
    
    Returns:
        Extracted image URL string (with path rewritten to "00") if found,
        None otherwise.
    """
    from scrapling import Fetcher
    
    search_url = f"https://www.thalia.de/suche?sq={isbn13}"
    
    try:
        fetcher = Fetcher()
        page = fetcher.get(search_url)
    except Exception as exc:
        logger.warning("thalia Scrapling fetch failed for isbn=%s: %s", isbn13, exc)
        return None
    
    if not page or not page.content:
        logger.debug("thalia empty response for isbn=%s", isbn13)
        return None
    
    # Step 1: Parse search result count
    try:
        suchtreffer_values = page.css('dl-pageview::attr(suchtreffer)')
    except Exception as exc:
        logger.debug("thalia failed to parse suchtreffer for isbn=%s: %s", isbn13, exc)
        return None
    
    if not suchtreffer_values:
        logger.debug("thalia no suchtreffer attribute found for isbn=%s", isbn13)
        return None
    
    try:
        result_count = int(suchtreffer_values[0])
    except (ValueError, IndexError) as exc:
        logger.debug("thalia invalid suchtreffer value for isbn=%s: %s", isbn13, exc)
        return None
    
    if result_count < 1:
        logger.debug("thalia zero search results for isbn=%s", isbn13)
        return None
    
    # Step 2: Extract image URL from first result
    try:
        src_values = page.css(
            'suche-produktliste > div > ul > li:nth-child(1) > picture > img::attr(src)'
        )
    except Exception as exc:
        logger.debug("thalia failed to parse image src for isbn=%s: %s", isbn13, exc)
        return None
    
    if not src_values:
        logger.debug("thalia no image src found for isbn=%s", isbn13)
        return None
    
    raw_url = src_values[0]
    if not raw_url or not isinstance(raw_url, str) or not raw_url.strip():
        logger.debug("thalia empty image src for isbn=%s", isbn13)
        return None
    
    # Step 3: Rewrite URL path segment to "00"
    rewritten_url = _rewrite_thalia_image_url(raw_url.strip())
    if not rewritten_url:
        logger.debug("thalia URL rewrite failed for isbn=%s raw_url=%s", isbn13, raw_url)
        return None
    
    logger.debug("thalia found url=%s (rewritten from %s) for isbn=%s", rewritten_url, raw_url, isbn13)
    return rewritten_url


def _rewrite_thalia_image_url(url: str) -> str | None:
    """
    Rewrite Thalia CDN image URL to use "00" path segment.
    
    Examples:
        https://images.thalia.media/03/-/...  →  https://images.thalia.media/00/-/...
        https://images.thalia.media/07/-/...  →  https://images.thalia.media/00/-/...
    
    Only rewrites URLs matching the images.thalia.media domain.
    Returns None if the URL doesn't match the expected pattern.
    """
    if not url.startswith("https://images.thalia.media/"):
        logger.debug("thalia URL does not match expected pattern: %s", url)
        return None
    
    # Split after domain and replace first path segment
    # URL structure: https://images.thalia.media/<segment>/-/...
    prefix = "https://images.thalia.media/"
    rest = url[len(prefix):]
    
    # Find the first "/" after the domain to locate the first segment boundary
    slash_idx = rest.find("/")
    if slash_idx == -1:
        # Single segment only? Return as-is, can't rewrite
        logger.debug("thalia URL has no path beyond first segment: %s", url)
        return None
    
    # Replace first segment with "00"
    new_rest = "00" + rest[slash_idx:]
    return prefix + new_rest


async def _probe_thalia_candidate(
    isbn13: str,
    client: httpx.AsyncClient,
    min_size_bytes: int,
    timeout_seconds: int,
) -> CoverCandidate:
    """
    Probe Thalia.de for cover via web scraping, then validate image URL.
    
    Three-step process:
    1. Scrape Thalia search page (in thread) → extract image URL
    2. Rewrite CDN URL path to "00" for higher resolution
    3. HEAD probe to verify image availability and size
    """
    # Step 1 & 2: Scrape and rewrite (combined in _fetch_thalia_page_sync)
    image_url = await asyncio.to_thread(
        _fetch_thalia_page_sync, isbn13, timeout_seconds
    )
    
    if not image_url:
        # Scraping failed or no results found
        return CoverCandidate(
            source="thalia",
            url="",
            available=False,
        )
    
    # Step 3: HEAD probe on rewritten image URL
    if not is_safe_cover_import_url(image_url):
        logger.warning("thalia returned unsafe URL: %s", image_url)
        return CoverCandidate(
            source="thalia",
            url="",
            available=False,
        )
    
    return await _probe_candidate("thalia", image_url, client, min_size_bytes)
```

**Key Design Decisions:**

1. **Scrapling import inside function**: Import `Fetcher` inside `_fetch_thalia_page_sync` to avoid module-level import issues and keep the Scrapling dependency optional at import time (though it's always installed).

2. **Sync function in thread**: `_fetch_thalia_page_sync()` is a plain sync function. It runs via `asyncio.to_thread()` which handles the thread pool and ensures the async event loop is not blocked.

3. **URL rewriting as separate function**: `_rewrite_thalia_image_url()` extracted as a pure function for testability and clarity. It operates on a single URL string and returns `None` for non-matching URLs.

4. **SSRF safety**: The rewritten URL is validated through `is_safe_cover_import_url()` before the HEAD probe, consistent with how Hardcover handles its GraphQL-returned URLs.

5. **Error granularity**: Different log messages for each failure mode (fetch failed, empty response, no suchtreffer, zero results, no image src, URL rewrite failure) to aid debugging.

---

#### 2.3.2 Integration in `search_cover_candidates()`

Modify the `search_cover_candidates()` function to add the Thalia task.

**Current code** (lines 210-229):
```python
timeout = httpx.Timeout(settings.cover_candidate_timeout_seconds)
async with httpx.AsyncClient(timeout=timeout) as client:
    tasks = [
        _probe_source_candidates(source, urls, client, settings.cover_candidate_min_size_bytes)
        for source, urls in provider_urls.items()
    ]

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

**Change to:**

```python
timeout = httpx.Timeout(settings.cover_candidate_timeout_seconds)
async with httpx.AsyncClient(timeout=timeout) as client:
    tasks = [
        _probe_source_candidates(source, urls, client, settings.cover_candidate_min_size_bytes)
        for source, urls in provider_urls.items()
    ]

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

    if settings.thalia_cover_search_enabled:
        logger.debug("cover candidate adding thalia source (enabled)")
        tasks.append(
            _probe_thalia_candidate(
                normalized_isbn13,
                client,
                settings.cover_candidate_min_size_bytes,
                settings.cover_candidate_timeout_seconds,
            )
        )
    else:
        logger.debug("cover candidate skipping thalia (disabled by config)")

    results = await asyncio.gather(*tasks)
```

**Key Changes:**
1. **Conditional Inclusion**: Thalia task only added when `thalia_cover_search_enabled` is `True`
2. **Separate Task**: Thalia uses a different probe function (`_probe_thalia_candidate`)
3. **Logging**: Debug logs indicate whether Thalia is enabled/disabled
4. **Timeout passed**: `cover_candidate_timeout_seconds` is passed to `_fetch_thalia_page_sync` for the Scrapling fetch timeout
5. **No Breaking Changes**:
   - Existing four sources work identically
   - `asyncio.gather()` call unchanged
   - Return type unchanged (`CoverCandidateList`)

---

### 2.4 Scrapling Fetcher vs Session Fallback

The implementation will use Scrapling's `Fetcher` class (basic HTTP fetcher, no browser dependency).

**First attempt:**
```python
fetcher = Fetcher()
page = fetcher.get(search_url)
```

**Fallback strategy** (if Thalia blocks the basic Fetcher):
If during testing we discover that Thalia blocks the default `Fetcher`, we can switch to a `StealthFetcher` or configure the fetcher with custom headers:

```python
fetcher = Fetcher(
    headers={"User-Agent": "Mozilla/5.0 ..."},
)
page = fetcher.get(search_url)
```

**Decision during implementation:** Start with `Fetcher()`. If Thalia blocks, add user-agent spoofing or use a session-based approach with custom headers. The function signature and return type remain the same regardless of which Scrapling mode is used.

---

## 3. Error Handling & Edge Cases

### 3.1 Scraping Error Scenarios

| Scenario | Behavior |
|----------|----------|
| Thalia returns 403/blocked | Log warning, return unavailable candidate |
| Network timeout | Log warning, return unavailable candidate |
| DNS resolution failure | Log warning, return unavailable candidate |
| Empty response body | Log debug, return unavailable candidate |
| `dl-pageview` element missing | Log debug, return unavailable candidate |
| `suchtreffer` attribute missing | Log debug, return unavailable candidate |
| `suchtreffer` value not parseable as int | Log debug, return unavailable candidate |
| `suchtreffer=0` | Log debug, return unavailable candidate (expected: no results) |
| Image selector matches nothing | Log debug, return unavailable candidate |
| Image `src` attribute empty/null | Log debug, return unavailable candidate |
| Image URL doesn't match `images.thalia.media` | Log debug, return unavailable candidate |
| URL rewriting produces invalid URL | Caught by `_probe_candidate()` exception handler |

**Implementation:** All handled by `_fetch_thalia_page_sync()` returning `None`, which `_probe_thalia_candidate()` maps to an unavailable `CoverCandidate`.

### 3.2 Safer URL Handling

The `_fetch_thalia_page_sync()` function uses a **timeout-aware** approach. The timeout value from settings (`cover_candidate_timeout_seconds`, default 5s) should be applied to the Scrapling `Fetcher`:

```python
fetcher = Fetcher()
page = fetcher.get(search_url, timeout=timeout_seconds)
```

Check Scrapling API docs for the exact parameter name (may be `timeout` in `get()`).

### 3.3 Concurrency Consideration

Scrapling runs in a thread via `asyncio.to_thread()`. Since Python's thread pool has a default limit and Scrapling's HTTP requests could be resource-intensive:

- Each Scrapling call is a single HTTP GET request (lightweight)
- Thread pool handles the blocking I/O without blocking the event loop
- No additional semaphore needed for Thalia (Scrapling's own HTTP handling manages this)
- The `_PROBE_SEMAPHORE` only applies to the subsequent HEAD probe (via `_probe_candidate()`)

**Resource impact per request:**
- 1 thread (Scrapling fetch, typically <1s)
- 1 HEAD request (semaphore-protected)
- Memory: page content varies (~10-100KB for a search results page)

### 3.4 SSRF Safety

The URL extracted from Thalia's search page goes through:
1. `_rewrite_thalia_image_url()` — ensures URL starts with `https://images.thalia.media/`
2. `is_safe_cover_import_url()` — blocks localhost, private IPs, credentials in URL
3. `_probe_candidate()` — only does a HEAD request (no body download)

This provides layered protection against SSRF, consistent with how other sources are handled.

---

## 4. Testing Strategy

### 4.1 Backend Unit Tests

**File:** `backend/tests/test_cover_candidates.py`

Add 4 new test cases after the existing hardcover tests:

#### 4.1.1 `test_cover_candidates_thalia_disabled_by_setting()`

Verify that when `thalia_cover_search_enabled` is `False`, the Thalia source is not included in candidates, no Scrapling calls are made, and the result has 4 candidates (the existing 4 sources).

```python
def test_cover_candidates_thalia_disabled_by_setting(client: TestClient, monkeypatch):
    """Thalia source excluded when setting is disabled."""
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)
    # Also set hardcover token to ensure we don't confuse counts
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token")

    requested_urls = []

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data=None):
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}
        def json(self):
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)
        async def post(self, url: str, **kwargs):
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["candidates"]) == 4  # 3 URL-based + 1 hardcover, no thalia

    sources = [item["source"] for item in data["candidates"]]
    assert "thalia" not in sources
    assert "hardcover" in sources
    assert "abebooks" in sources
    assert "openlibrary" in sources
    assert "amazon" in sources
```

#### 4.1.2 `test_cover_candidates_thalia_enabled_and_found()`

Mock Scrapling's `Fetcher` at the module level. Verify that when Thalia returns a valid result, the candidate appears with the rewritten URL and passes HEAD probe.

```python
def test_cover_candidates_thalia_enabled_and_found(client: TestClient, monkeypatch):
    """Thalia source returns available candidate when book is found."""
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module

    # Mock Scrapling Fetcher
    class _MockPage:
        def __init__(self, content: str):
            self.content = content

        def css(self, selector: str):
            if "suchtreffer" in selector:
                return ["1"]
            if "img::attr(src)" in selector:
                return ["https://images.thalia.media/03/-/some/path/cover.jpg"]
            return []

    class _MockFetcher:
        def get(self, url: str, **kwargs):
            return _MockPage(content="<html></html>")

    monkeypatch.setattr(cc_module, "Fetcher", _MockFetcher)

    # Mock httpx for HEAD probe
    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str):
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def head(self, url: str, follow_redirects: bool = True):
            if "images.thalia.media" in url:
                return _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "50000"}, url)
            return _FakeResponse(404, {}, url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["candidates"]) == 4

    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is True
    assert by_source["thalia"]["url"].startswith("https://images.thalia.media/00/-/")
    assert "03" not in by_source["thalia"]["url"]
```

**Note on Scrapling mocking:** Since `_fetch_thalia_page_sync()` imports `Fetcher` inside the function body, the monkeypatch target is `app.routers.cover_candidates.Fetcher`. We also need to handle the fact that `_fetch_thalia_page_sync` runs in a thread. The Scrapling import inside the function means the `Fetcher` symbol needs to be accessible on the module. An alternative approach is to make `Fetcher` available as a module-level attribute that we can monkeypatch, or to restructure the import.

**Recommended approach for testability:** Define a module-level `_THALIA_FETCHER = None` and lazily initialize it:

```python
# At module level in cover_candidates.py:
_THALIA_FETCHER: object | None = None

def _get_thalia_fetcher():
    global _THALIA_FETCHER
    if _THALIA_FETCHER is None:
        from scrapling import Fetcher
        _THALIA_FETCHER = Fetcher()
    return _THALIA_FETCHER
```

Then in `_fetch_thalia_page_sync()`:
```python
fetcher = _get_thalia_fetcher()
page = fetcher.get(search_url, timeout=timeout_seconds)
```

This makes the fetcher easily monkeypatchable via `app.routers.cover_candidates._THALIA_FETCHER`.

#### 4.1.3 `test_cover_candidates_thalia_zero_results()`

Mock Scrapling to return `suchtreffer="0"`. Verify candidate is unavailable.

```python
def test_cover_candidates_thalia_zero_results(client: TestClient, monkeypatch):
    """Thalia returns unavailable when no search results found."""
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module

    class _MockPage:
        def __init__(self, content: str):
            self.content = content
        def css(self, selector: str):
            if "suchtreffer" in selector:
                return ["0"]
            return []

    class _MockFetcher:
        def get(self, url: str, **kwargs):
            return _MockPage(content="<html></html>")

    monkeypatch.setattr(cc_module, "Fetcher", _MockFetcher)
    # Or if using the _THALIA_FETCHER pattern:
    # monkeypatch.setattr(cc_module, "_THALIA_FETCHER", _MockFetcher())

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is False
    assert by_source["thalia"]["url"] == ""
```

#### 4.1.4 `test_cover_candidates_thalia_scrapling_error()`

Mock Scrapling to raise an exception. Verify candidate is unavailable.

```python
def test_cover_candidates_thalia_scrapling_error(client: TestClient, monkeypatch):
    """Thalia returns unavailable when Scrapling fetch fails."""
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module

    class _MockFetcher:
        def get(self, url: str, **kwargs):
            raise Exception("Connection refused")

    monkeypatch.setattr(cc_module, "Fetcher", _MockFetcher)

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is False
```

#### 4.1.5 URL Rewriting Unit Tests (Optional)

Add a focused test for `_rewrite_thalia_image_url()`:

```python
def test_rewrite_thalia_image_url():
    """Verify Thalia CDN URL rewriting logic."""
    from app.routers.cover_candidates import _rewrite_thalia_image_url

    # Normal case: replace first segment with 00
    assert _rewrite_thalia_image_url(
        "https://images.thalia.media/03/-/some/path.jpg"
    ) == "https://images.thalia.media/00/-/some/path.jpg"

    # Different segment number
    assert _rewrite_thalia_image_url(
        "https://images.thalia.media/07/-/another/path.jpg"
    ) == "https://images.thalia.media/00/-/another/path.jpg"

    # Non-thalia domain: return None
    assert _rewrite_thalia_image_url(
        "https://example.com/03/-/cover.jpg"
    ) is None

    # No path after domain: return None
    assert _rewrite_thalia_image_url(
        "https://images.thalia.media/03"
    ) is None

    # Empty string
    assert _rewrite_thalia_image_url("") is None
```

### 4.2 Test Coverage Summary

| Test | Scenario | Expected |
|------|----------|----------|
| `test_cover_candidates_thalia_disabled_by_setting` | `thalia_cover_search_enabled=false` | 4 candidates, no "thalia" source |
| `test_cover_candidates_thalia_enabled_and_found` | Book found, URL rewritten, HEAD 200 | 5 candidates, thalia available |
| `test_cover_candidates_thalia_zero_results` | `suchtreffer="0"` | thalia unavailable, empty URL |
| `test_cover_candidates_thalia_scrapling_error` | Scrapling raises exception | thalia unavailable, empty URL |
| `test_rewrite_thalia_image_url` | URL rewriting cases | Correct rewritten URLs or None |

### 4.3 Manual Integration Testing

#### Test 1: Thalia Enabled (Default), ISBN Found
- Ensure `THALIA_COVER_SEARCH_ENABLED=true` (or unset)
- Restart backend
- Open book edit dialog, enter ISBN `9783440513033` (known Thalia title)
- Click "Auto-search covers"
- **Expected:** Modal shows 5 candidates (if hardcover token configured) or 4 (without hardcover)
- **Verify:** Thalia candidate appears with cover image; hover shows metadata

#### Test 2: Thalia Enabled, ISBN Not Found
- Use an obscure ISBN unlikely to be on Thalia (e.g., `9791234567896`)
- Click "Auto-search covers"
- **Expected:** Thalia candidate not shown (filtered by `available: false`)
- **Verify:** Modal shows only available candidates from other sources

#### Test 3: Thalia Disabled
- Set `THALIA_COVER_SEARCH_ENABLED=false` in `.env`
- Restart backend
- Enter valid ISBN, click "Auto-search covers"
- **Expected:** No Thalia candidate displayed
- **Verify:** Modal shows same sources as before Thalia was added

#### Test 4: Network Blocked
- Use a network proxy or firewall to block `thalia.de`
- Trigger auto-search
- **Expected:** Thalia candidate unavailable, other sources unaffected
- **Verify:** Backend logs show warning about Thalia fetch failure

---

## 5. Frontend Changes

### 5.1 No Direct Changes Required

**Rationale:**
- Frontend `AutoSearchCoverModal.svelte` already handles dynamic candidate lists
- Modal filters candidates by `available: true` (line 76)
- Thalia candidates automatically displayed when available
- Source name shown in hover overlay (line 91): `$_('book.autoSearchSourceLabel', { values: { source: candidate.source } })`
- This renders as "Source: thalia" in English (and "Quelle: thalia" in German)
- No hardcoded source list in frontend

**Verification:**
- Inspect modal rendering with 4 vs 5 candidates
- Verify "thalia" label appears correctly in hover overlay
- Test grid layout with 5 candidates (3-column grid will flow to 2nd row)

### 5.2 Optional: i18n-Friendly Source Labels

If desired, add a friendly display name for "thalia":

**File:** `frontend/src/lib/i18n/locales/en.json`
```json
"book": {
  ...
  "coverSource": {
    "abebooks": "AbeBooks",
    "openlibrary": "Open Library",
    "amazon": "Amazon",
    "hardcover": "Hardcover",
    "thalia": "Thalia"
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
    "hardcover": "Hardcover",
    "thalia": "Thalia"
  }
}
```

**Decision:** Optional enhancement. The current `autoSearchSourceLabel` already displays the raw source name ("thalia"), which is acceptable. i18n labels can be added in a follow-up if desired.

---

## 6. Documentation Updates

### 6.1 Environment Variables

**File:** `.env.example`

Add Thalia setting after the hardcover section:

```bash
# Cover search settings
COVER_CANDIDATE_TIMEOUT_SECONDS=5
COVER_CANDIDATE_MIN_SIZE_BYTES=1000
COVER_IMPORT_TIMEOUT_SECONDS=15
HARDCOVER_APP_API_TOKEN=         # Optional: hardcover.app GraphQL API token
                                 # Leave empty to disable hardcover as a cover source
                                 # Get a token at https://hardcover.app/api
THALIA_COVER_SEARCH_ENABLED=true # Optional: enable/disable Thalia.de cover search (default: true)
                                 # Thalia does not require an API key or configuration
```

### 6.2 Code Comments

**File:** `backend/app/routers/cover_candidates.py`

Update the file-level docstring to mention Thalia:

```python
"""
Cover candidate search endpoint.

Queries multiple providers in parallel to find available book covers by ISBN:
- AbeBooks: Static URL pattern (HEAD probe)
- OpenLibrary: Static URL pattern (HEAD probe)
- Amazon: Static URL pattern (HEAD probe)
- Hardcover: GraphQL API (requires HARDCOVER_APP_API_TOKEN env var)
- Thalia: Web scraping via Scrapling (enabled by default, no API key needed)

All candidates are validated via HEAD probe to check:
- HTTP 200 status
- Content-Type: image/*
- Content-Length >= cover_candidate_min_size_bytes

Hardcover source is conditional: only queried when API token is configured.
Thalia source is conditional: can be disabled via THALIA_COVER_SEARCH_ENABLED=false.
"""
```

### 6.3 README / Deployment Guide

If the project has deployment docs, add a mention that Thalia is automatically enabled and requires no configuration. Note that it uses web scraping and may be affected by Thalia's anti-bot measures.

---

## 7. Risk Analysis & Mitigations

### Risk 1: Thalia Blocks Scrapling Requests

**Impact:** High — Thalia source becomes unavailable  
**Probability:** Medium (many sites block non-browser user agents)

**Mitigations:**
1. **Graceful degradation**: Blocking returns `available: false`, other sources still work
2. **User-agent spoofing**: Can add custom headers to `Fetcher()` to mimic a real browser
3. **Session fallback**: Switch from `Fetcher` to a session-based approach with cookie handling
4. **Logging**: Warning logs help detect blocking
5. **Disable switch**: `THALIA_COVER_SEARCH_ENABLED=false` to disable without code changes

**Action:** During implementation, test with default Fetcher. If blocked, add custom User-Agent header. Document the fallback approach.

---

### Risk 2: Thalia HTML Structure Changes

**Impact:** Medium — CSS selectors stop matching, returns unavailable  
**Probability:** Medium (web pages change more frequently than APIs)

**Mitigations:**
1. **Selector failure returns unavailable**: No broken behavior, just no results from Thalia
2. **Logging**: Debug logs show which step failed (selector not matching)
3. **Minimal selectors**: Only two selectors, easy to update
4. **Graceful degradation**: Other sources unaffected

**Action:** Add a monitoring note to check Thalia source success rate periodically.

---

### Risk 3: Scrapling Threads Overwhelming Server

**Impact:** Low — Thread pool exhaustion under heavy load  
**Probability:** Low (typical usage is a few concurrent searches)

**Mitigations:**
1. **Single request per search**: Each search does one Scrapling GET
2. **`asyncio.to_thread()` uses thread pool**: Python's ThreadPoolExecutor limits concurrent threads
3. **Quick operations**: Scrapling GET typically completes in <1s
4. **Existing semaphore**: HEAD probes already concurrency-limited

**Action:** Monitor if thread pool exhaustion becomes an issue. If needed, add a dedicated semaphore for Thalia.

---

### Risk 4: Large HTML Response Size

**Impact:** Low — Increased memory usage per request  
**Probability:** Low (search result pages are typically small)

**Mitigations:**
1. **Transient**: Page content parsed and discarded after URL extraction
2. **No storage**: HTML not persisted, only parsed in memory
3. **Typical size**: Search result pages are ~10-100KB

**Action:** None needed.

---

### Risk 5: URL Rewriting Breaks Image Access

**Impact:** Medium — Thalia candidate "available" via HEAD but image fails to load in browser  
**Probability:** Low (the `00` segment pattern is documented behavior)

**Mitigations:**
1. **HEAD probe validates**: If `00` URL returns 200 with image content-type, it's likely valid
2. **Frontend renders image**: If image fails to load in browser, the user sees a broken image indicator
3. **Graceful degradation**: User can select another source

**Action:** Verify with real Thalia CDN URLs during manual testing. If `00` doesn't work, the URL rewriting can be adjusted or removed.

---

### Risk 6: Scrapling Import Time (First Request)

**Impact:** Low — First request may be slower due to Scrapling module import  
**Probability:** High (first call imports Scrapling, which has dependencies)

**Mitigations:**
1. **Import inside function**: Lazy import means Scrapling is only loaded when Thalia is actually queried
2. **One-time cost**: Module import only happens on first Thalia request
3. **Subsequent requests reuse**: Already imported module is fast

**Action:** Acceptable. Document that first Thalia search may be slightly slower.

---

## 8. Implementation Checklist

### Phase 1: Configuration & Setup
- [ ] Add `thalia_cover_search_enabled: bool = True` to `Settings` in `backend/app/config.py`
- [ ] Update `.env.example` with Thalia setting and comments
- [ ] Add `scrapling>=0.12.5` to `pyproject.toml` dependencies
- [ ] Run `cd backend && uv lock && uv sync` to update lock file

### Phase 2: Backend Implementation
- [ ] Add `_rewrite_thalia_image_url()` pure function
  - Handle `images.thalia.media` domain check
  - Replace first path segment with `00`
  - Return `None` for non-matching URLs
- [ ] Add `_fetch_thalia_page_sync()` sync function
  - Import `Fetcher` from Scrapling
  - Build search URL with ISBN-13
  - Fetch page with timeout
  - Parse `suchtreffer` attribute
  - Extract image `src` from first result
  - Rewrite URL via `_rewrite_thalia_image_url()`
  - Return image URL or `None`
  - Comprehensive debug logging at each failure point
- [ ] Add `_probe_thalia_candidate()` async function
  - Call `_fetch_thalia_page_sync()` via `asyncio.to_thread()`
  - Validate rewritten URL with `is_safe_cover_import_url()`
  - Pass URL to `_probe_candidate()` for HEAD validation
  - Return unavailable candidate if any step fails
- [ ] Update `search_cover_candidates()` function
  - Add conditional Thalia task to `asyncio.gather()`
  - Check `settings.thalia_cover_search_enabled`
  - Pass `cover_candidate_timeout_seconds` to Thalia probe
  - Add debug logging for enable/disable

### Phase 3: Testing
- [ ] Add unit tests to `backend/tests/test_cover_candidates.py`:
  - `test_cover_candidates_thalia_disabled_by_setting()` — 4 candidates, no "thalia"
  - `test_cover_candidates_thalia_enabled_and_found()` — 5 candidates, thalia available with rewritten URL
  - `test_cover_candidates_thalia_zero_results()` — suchtreffer=0
  - `test_cover_candidates_thalia_scrapling_error()` — Scrapling raises
  - `test_rewrite_thalia_image_url()` — URL rewriting edge cases
- [ ] Run pytest: `cd backend && uv run pytest tests/test_cover_candidates.py -v`
- [ ] Manual testing:
  - Test with Thalia enabled (ISBN with and without results)
  - Test with Thalia disabled
  - Test with network blocked (verify graceful degradation)
- [ ] Docker Compose rebuild and test

### Phase 4: Frontend Verification
- [ ] Open auto-search modal with Thalia enabled
- [ ] Verify 5 candidates displayed (if ISBN has matches across sources)
- [ ] Check hover overlay shows "thalia" source label
- [ ] Verify grid layout with 5 candidates renders correctly
- [ ] Test with Thalia disabled — verify 4 candidates (or 3 without hardcover)

### Phase 5: Documentation & Polish
- [ ] Update docstring in `backend/app/routers/cover_candidates.py` file header
- [ ] Add inline comments for Thalia three-step process
- [ ] Update `.env.example` with Thalia setting
- [ ] Write debug-log-friendly comments at each failure point

### Phase 6: Pre-Deployment Review
- [ ] Code review: error handling, logging, thread safety
- [ ] Verify no hardcoded URLs/tokens in code
- [ ] Check `.gitignore` excludes `.env`
- [ ] Verify graceful degradation when Scrapling fails
- [ ] Confirm timeout settings appropriate for Scrapling fetch
- [ ] Ensure `_fetch_thalia_page_sync()` catches all relevant exceptions
- [ ] Check that `asyncio.to_thread()` usage is correct for sync function

### Phase 7: Deployment
- [ ] Deploy to staging environment
- [ ] Run full regression test suite
- [ ] Monitor backend logs for Thalia errors
- [ ] Deploy to production
- [ ] Monitor error rates and response times

---

## 9. Acceptance Criteria

### Backend
- ✅ `thalia_cover_search_enabled` setting added to `config.py` (default `True`)
- ✅ Scrapling fetch function implemented with proper error handling
- ✅ CDN URL rewriting logic implemented (replace first path segment with `00`)
- ✅ URL validation via `is_safe_cover_import_url()` before HEAD probe
- ✅ Thalia probe runs in thread via `asyncio.to_thread()` (non-blocking)
- ✅ Thalia task conditionally added to `asyncio.gather()`
- ✅ All scraping failures return unavailable candidate (no exceptions raised)
- ✅ Debug logs at each failure point (fetch, parse, selector, rewrite)
- ✅ Warning logs for network/blocking errors

### Testing
- ✅ 5 unit tests pass covering all scenarios (disabled, found, zero results, scrapling error, URL rewrite)
- ✅ Manual testing confirms 5 candidates when Thalia enabled + hardcover token
- ✅ Manual testing confirms 4 candidates when Thalia disabled
- ✅ Manual testing confirms 4 candidates when Thalia enabled but hardcover disabled
- ✅ Graceful degradation on Scrapling failure (no user-visible error)
- ✅ Docker Compose integration test passes

### Frontend
- ✅ No code changes required (dynamic candidate rendering)
- ✅ Modal displays 5 candidates when Thalia and hardcover both available
- ✅ "thalia" source label appears in hover overlay
- ✅ Grid layout handles 5 candidates without overflow

### Documentation
- ✅ `.env.example` includes Thalia setting with comments
- ✅ Code docstrings explain Thalia scraping integration
- ✅ Inline comments explain URL rewriting and thread usage

### Security & Operations
- ✅ No hardcoded URLs aside from the Thalia search base URL
- ✅ All extracted URLs validated via `is_safe_cover_import_url()`
- ✅ URL rewriting ensures only `images.thalia.media` domain is targeted
- ✅ Scrapling errors logged but not exposed to frontend
- ✅ Timeout prevents hanging Scrapling requests
- ✅ Thread-based execution doesn't block event loop

---

## 10. Implementation Details Reference

### 10.1 Thalia Search URL Pattern

```
https://www.thalia.de/suche?sq={isbn13}
```

ISBN-13 only (same as hardcover). No ISBN-10 fallback needed for the search.

### 10.2 Expected HTML Snippet

```html
<dl-pageview suchbegriff="9783440513033" suchtreffer="1"></dl-pageview>
...
<suche-produktliste>
  <div>
    <ul>
      <li>
        ...
        <picture>
          <img src="https://images.thalia.media/03/-/..." alt="..." />
        </picture>
        ...
      </li>
    </ul>
  </div>
</suche-produktliste>
```

### 10.3 URL Transformation Examples

| Original URL | Rewritten URL |
|---|---|
| `https://images.thalia.media/03/-/p/12345/cover.jpg` | `https://images.thalia.media/00/-/p/12345/cover.jpg` |
| `https://images.thalia.media/07/-/p/67890/cover.jpg` | `https://images.thalia.media/00/-/p/67890/cover.jpg` |
| `https://images.thalia.media/03/-/prod/54321.jpg` | `https://images.thalia.media/00/-/prod/54321.jpg` |

### 10.4 Scrapling API Reference

```python
# Fetcher instantiation
fetcher = Fetcher(
    stealth=True,            # Optional: enable anti-bot evasion
    headers={...},           # Optional: custom headers
)

# Page fetch
page = fetcher.get(url, timeout=5)

# CSS selectors with attribute extraction
page.css('selector::attr(attribute)')  # Returns list of attribute values
page.css('selector')                   # Returns list of matching elements

# Element text extraction
element.text                          # Get text content of an element

# Check if page was successful
page.status                           # HTTP status code (if available)
```

**Note:** Scrapling API may vary slightly between versions. Check the official Scrapling documentation at implementation time for exact API details.

---

## 11. Code Review Checklist

Before submitting for review, verify:

### Security
- [ ] No hardcoded secrets in code
- [ ] No SSRF: extracted URLs validated via `is_safe_cover_import_url()`
- [ ] URL rewriting restricted to `images.thalia.media` domain
- [ ] No sensitive data in logs (URLs are not sensitive, but verify no PII)

### Error Handling
- [ ] All exception types caught in `_fetch_thalia_page_sync()`
- [ ] CSS selector failures return `None` (no exceptions propagated)
- [ ] Network errors (timeout, connection refused) handled gracefully
- [ ] Invalid `suchtreffer` values (non-numeric) handled
- [ ] Missing `dl-pageview` or image element handled
- [ ] URL rewriting rejects non-Thalia domains

### Logging
- [ ] Debug logs at each parsing step (suchtreffer value, image URL found)
- [ ] Warning logs for network/blocking errors with ISBN context
- [ ] Success logs show Thalia found URL with ISBN
- [ ] No excessive logging in happy path

### Performance
- [ ] Scrapling fetch runs in thread (not blocking event loop)
- [ ] Timeout configured for Scrapling fetch
- [ ] Parallel execution with `asyncio.gather()`
- [ ] No additional semaphore needed (HEAD probe already protected)

### Testing
- [ ] Unit tests cover happy path (found with rewritten URL)
- [ ] Unit tests cover disabled-by-setting
- [ ] Unit tests cover zero results
- [ ] Unit tests cover Scrapling exception
- [ ] Unit tests cover URL rewriting edge cases
- [ ] Tests properly mock Scrapling `Fetcher`

### Code Quality
- [ ] Type hints for all new functions
- [ ] Docstrings for all new functions
- [ ] Consistent naming conventions (prefixed with `_`)
- [ ] No dead code or commented-out sections
- [ ] Follows existing code style

---

## 12. Rollback Plan

If issues discovered in production:

### Immediate Rollback (< 1 minute)
1. Remove or comment out the Thalia task addition in `search_cover_candidates()`
2. Or set `THALIA_COVER_SEARCH_ENABLED=false` in `.env`
3. Restart backend
4. Verify auto-search returns 4 candidates only

**Impact:** Thalia source disabled, other sources unaffected

### Code Revert (if needed)
1. Revert commit adding Thalia integration
2. Remove `scrapling` from `pyproject.toml` dependencies (optional, uninstalling won't break anything if imports are lazy)
3. Redeploy previous version
4. Restart backend

**Impact:** Full rollback to previous behavior

### Debugging Steps
1. Check backend logs for Thalia errors:
   ```bash
   docker compose logs backend | grep -i thalia
   ```
2. Test Thalia search URL directly:
   ```bash
   curl -s "https://www.thalia.de/suche?sq=9783440513033" | head -50
   ```
3. Verify Scrapling import works:
   ```bash
   cd backend && uv run python -c "from scrapling import Fetcher; print('OK')"
   ```
4. Test URL rewriting:
   ```bash
   cd backend && uv run python -c "
   from app.routers.cover_candidates import _rewrite_thalia_image_url
   print(_rewrite_thalia_image_url('https://images.thalia.media/03/-/test.jpg'))
   "
   ```

---

## 13. Future Enhancements (Out of Scope)

### 13.1 Scrapling StealthFetcher
If Thalia deploys stronger anti-bot measures, switch to Scrapling's `StealthFetcher` or Playwright-based approach for JavaScript-rendered content.

### 13.2 Multiple Image Candidates
Extract images from multiple search results (not just the first) to provide more cover choices.

### 13.3 ISBN-10 Search Fallback
If ISBN-13 search returns 0 results, retry with ISBN-10 (if available) — similar to other sources' fallback strategy.

### 13.4 Thalia Product Page Scraping
Extract additional metadata (publisher, publication date) from Thalia product pages for import candidates.

### 13.5 Response Caching
Cache Thalia search results per ISBN with a short TTL to reduce repeated scraping for popular lookups.

### 13.6 Circuit Breaker
Temporarily disable Thalia after repeated scraping failures to avoid wasting resources.

### 13.7 Thalia API
If Thalia offers a public API in the future, migrate from scraping to API calls.

---

## 14. Appendix: Scrapling Dependency Details

### 14.1 Version Selection

Pin to the latest stable version available at implementation time. Scrapling follows semantic versioning.

**Installation:**
```bash
cd backend && uv add scrapling
```

This automatically updates `pyproject.toml` and `uv.lock`.

### 14.2 Scrapling Dependencies

Scrapling itself depends on:
- `httpx` (already in the project)
- `lxml` (HTML/XML parsing) — may be pulled as a transitive dependency
- `cssselect` (CSS selector support)

These are managed automatically by `uv`.

### 14.3 Verifying Installation

```bash
cd backend && uv run python -c "
from scrapling import Fetcher
print('Scrapling imported successfully')
fetcher = Fetcher()
print('Fetcher created successfully')
"
```

---

## 15. Integration Summary

The Thalia.de integration adds a fifth cover candidate source using a fundamentally different approach (web scraping vs URL pattern or API). The key architectural decision is running the synchronous Scrapling call in a thread, which keeps the existing async `asyncio.gather()` pattern intact.

**Data flow (at a glance):**
```
search_cover_candidates()
  │
  ├── AbeBooks (existing, HEAD probe)
  ├── OpenLibrary (existing, HEAD probe)
  ├── Amazon (existing, HEAD probe)
  ├── Hardcover (existing, GraphQL → HEAD)
  └── Thalia (new, Scrapling thread → URL rewrite → HEAD)
       │
       └── asyncio.to_thread() ──→ _fetch_thalia_page_sync()
              │
              ├── Fetcher.get() ──→ Thalia.de search page
              ├── page.css('dl-pageview::attr(suchtreffer)')
              ├── page.css('img::attr(src)')
              └── _rewrite_thalia_image_url()
                     │
                     └── https://images.thalia.media/00/-/...
                            │
                            └── _probe_candidate("thalia", url, client, min_size) ──→ HEAD probe
                                   │
                                   └── CoverCandidate(source="thalia", ...)
```

The Thalia source is **enabled by default** (no API token needed) and gracefully degrades to unavailable on any failure. The frontend requires no changes.

---

**End of Plan 58**
