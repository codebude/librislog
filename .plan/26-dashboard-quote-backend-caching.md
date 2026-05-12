# Plan: Dashboard Quote Backend Caching with TTL

## Overview

Refactor the dashboard quote handling to move caching from frontend (localStorage) to backend with configurable TTL, reducing load on the external quote API while maintaining a clean separation of concerns.

**Goal**: Backend caches quotes with configurable TTL; frontend fetches on every page load without caching logic.

## Requirements Summary

1. ✅ Quote should be cached in backend
2. ✅ TTL of cache should be configurable via `.env` file
3. ✅ Frontend should call quote endpoint on every page load
4. ✅ Frontend should NOT do any caching
5. ✅ Frontend should render the quote if backend returns a quote
6. ✅ Backend API should return appropriate HTTP status when quote function is disabled
7. ✅ Frontend should handle disabled response and hide/not show the quote UI control

## Current State Analysis

### Backend (`backend/app/routers/books.py`)

**Current Implementation (lines 170-197)**:
- Route: `GET /api/books/dashboard-quote`
- Response model: `DashboardQuote | None`
- Returns `None` if `settings.dashboard_quote_enabled` is `False`
- Makes synchronous external API call on every request
- Timeout: 8 seconds
- Returns `None` on any error (network, timeout, invalid response)
- No caching—every request hits the external API

**Dependencies**:
- `httpx.AsyncClient` for external API calls
- `settings.dashboard_quote_enabled` (bool, default: `True`)
- `settings.dashboard_quote_url` (str, default: motivational-spark API)

### Frontend (`frontend/src/routes/dashboard/+page.svelte`)

**Current Implementation (lines 29-138)**:
- Implements **client-side caching** using `localStorage`
- Cache key: `'librislog.dashboard.quote'`
- Cache structure: `{ expiresAt, quote, enabled }`
- TTL logic: Caches until end of day (`getEndOfDayTimestamp()`)
- Handles disabled state by caching `enabled: false`
- Falls back to stale cache on fetch failure
- Shows loading spinner while fetching
- Conditionally renders quote UI based on `quoteEnabled` state

**Issues with Current Frontend Caching**:
1. Frontend has complex caching logic (not its responsibility)
2. End-of-day expiration is hardcoded (not configurable)
3. Every user's browser makes at least one external API call per day
4. No centralized control over cache invalidation
5. Stale cache fallback can show outdated quotes indefinitely

### Configuration (`.env.example` & `backend/app/config.py`)

Current settings:
```bash
DASHBOARD_QUOTE_ENABLED=true
DASHBOARD_QUOTE_URL="https://motivational-spark-api.vercel.app/api/quotes/random"
```

### Tests (`backend/tests/test_dashboard.py`)

Current tests (lines 79-117):
- `test_dashboard_quote_returns_none_when_disabled`: Verifies `None` response when disabled
- `test_dashboard_quote_returns_quote`: Mocks `httpx.AsyncClient` to return fake quote

**Test gaps**:
- No caching behavior tests
- No TTL expiration tests
- No concurrent request tests
- No cache invalidation tests

## Problem Statement

The current architecture violates separation of concerns:
- **Frontend** handles caching logic, TTL, and disabled state persistence
- **Backend** is a thin pass-through with no optimization
- **External API** receives unnecessary repeated requests (once per user per day minimum)

**Performance Impact**:
- With 100 active users, the external API receives ~100 requests/day (assuming daily refresh)
- No protection against rate limiting
- No control over cache invalidation
- Poor performance if external API is slow/down (8-second timeout per user)

**Architectural Issues**:
- Backend cannot control cache behavior across users
- Frontend complexity increases maintenance burden
- localStorage cache can diverge from backend state
- No observability into cache hit/miss rates

## Solution Architecture

### High-Level Design

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│                 │  HTTP    │                  │  HTTP   │                 │
│  Frontend       ├────────►│  Backend         ├────────►│  External API   │
│  (No Caching)   │          │  (TTL Cache)     │         │  (quoteslate)   │
│                 │◄────────┤                  │         │                 │
└─────────────────┘          └──────────────────┘         └─────────────────┘
      │                             │                            │
      │ Fetch on load               │ Cache hit: instant         │ Only on miss
      │ No localStorage             │ Cache miss: fetch + cache   │ Reduced load
      │ Handle 503                  │ Return 503 if disabled     │
      └─────────────────────────────┴────────────────────────────┘
```

### Backend Caching Strategy

**Library**: `cachetools.TTLCache`
- Mature, thread-safe Python caching library
- Built-in TTL (time-to-live) expiration
- No external dependencies (Redis, Memcached)
- Perfect for single-instance deployments

**Cache Design**:
- **Key**: Single global key (only one quote active at a time)
- **Value**: `DashboardQuote` object (quote + author)
- **TTL**: Configurable via environment variable (default: 24 hours)
- **Maxsize**: 1 (only need to cache one quote)
- **Thread-safety**: Use `threading.Lock()` for write operations

**Cache Lifecycle**:
1. **Cache miss**: Fetch from external API, store in cache with TTL
2. **Cache hit**: Return cached value immediately (no external call)
3. **Cache expiration**: TTL expires, next request triggers cache miss
4. **Disabled state**: Return HTTP 503 (Service Unavailable) when disabled

### Frontend Simplification

**New Frontend Behavior**:
1. Call `api.books.dashboardQuote()` on every dashboard load
2. Show loading spinner while fetching
3. On success (200 OK): Render quote
4. On 503 (Service Unavailable): Hide quote UI entirely
5. On error (network/500): Show fallback message or hide
6. **Remove all localStorage caching logic**

### Environment Configuration

**New Environment Variables**:
```bash
DASHBOARD_QUOTE_ENABLED=true                          # Feature toggle
DASHBOARD_QUOTE_URL="..."                             # API endpoint
DASHBOARD_QUOTE_CACHE_TTL=86400                        # NEW: TTL in seconds (default: 24 hours)
```

## Implementation Plan

### Phase 1: Backend Cache Implementation

#### 1.1 Update Dependencies (`backend/pyproject.toml`)

Add `cachetools` to dependencies:
```toml
dependencies = [
    # ... existing dependencies ...
    "cachetools>=5.3.0",
]
```

#### 1.2 Update Configuration (`backend/app/config.py`)

Add new configuration field:
```python
class Settings(BaseSettings):
    # ... existing fields ...
    dashboard_quote_enabled: bool = True
    dashboard_quote_url: str = "https://motivational-spark-api.vercel.app/api/quotes/random"
    dashboard_quote_cache_ttl: int = 86400  # NEW: Cache TTL in seconds (default: 24 hours)
```

#### 1.3 Create Cache Module (`backend/app/services/quote_cache.py`)

**New file**: `backend/app/services/quote_cache.py`

```python
"""
Dashboard quote caching service with TTL-based expiration.
"""
import logging
import threading
from typing import Optional

import httpx
from cachetools import TTLCache

from app.config import settings
from app.schemas import DashboardQuote

logger = logging.getLogger(__name__)

# Thread-safe TTL cache for dashboard quotes
# Maxsize=1 because we only cache one global quote at a time
_quote_cache: TTLCache = TTLCache(maxsize=1, ttl=settings.dashboard_quote_cache_ttl)
_cache_lock = threading.Lock()
_CACHE_KEY = "current_quote"


async def get_cached_quote() -> Optional[DashboardQuote]:
    """
    Get cached dashboard quote with TTL-based expiration.
    
    Returns:
        DashboardQuote if available in cache and not expired, None otherwise.
    """
    with _cache_lock:
        return _quote_cache.get(_CACHE_KEY)


async def fetch_and_cache_quote() -> Optional[DashboardQuote]:
    """
    Fetch quote from external API and cache it with TTL.
    
    Returns:
        DashboardQuote if fetch successful, None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(settings.dashboard_quote_url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("dashboard quote fetch failed: %s", exc)
        return None

    if not isinstance(payload, dict):
        logger.warning("dashboard quote response is not a dict")
        return None

    quote_text = payload.get("quote")
    if not isinstance(quote_text, str) or not quote_text.strip():
        logger.warning("dashboard quote response missing valid 'quote' field")
        return None

    author = payload.get("author")
    if not isinstance(author, str):
        author = None

    quote = DashboardQuote(quote=quote_text.strip(), author=author)

    # Cache the quote with TTL
    with _cache_lock:
        _quote_cache[_CACHE_KEY] = quote
        logger.info(
            "dashboard quote cached (ttl=%ds): %s",
            settings.dashboard_quote_cache_ttl,
            quote.quote[:50],
        )

    return quote


async def get_quote() -> Optional[DashboardQuote]:
    """
    Get dashboard quote from cache or fetch from external API if cache miss.
    
    Returns:
        DashboardQuote if available, None if disabled or fetch failed.
    """
    if not settings.dashboard_quote_enabled:
        return None

    # Try cache first
    cached = await get_cached_quote()
    if cached is not None:
        logger.debug("dashboard quote cache hit")
        return cached

    # Cache miss: fetch and cache
    logger.debug("dashboard quote cache miss, fetching from external API")
    return await fetch_and_cache_quote()


def invalidate_cache() -> None:
    """
    Manually invalidate the quote cache.
    Useful for testing or manual cache refresh.
    """
    with _cache_lock:
        _quote_cache.clear()
        logger.info("dashboard quote cache invalidated")
```

#### 1.4 Update Router (`backend/app/routers/books.py`)

Replace the current `get_dashboard_quote` implementation:

**Before** (lines 170-197):
```python
@router.get("/dashboard-quote", response_model=DashboardQuote | None)
async def get_dashboard_quote(
    current_user: User = Depends(require_user),
) -> DashboardQuote | None:
    if not settings.dashboard_quote_enabled:
        return None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(settings.dashboard_quote_url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("dashboard quote fetch failed: %s", exc)
        return None

    # ... payload parsing ...
    return DashboardQuote(quote=quote.strip(), author=author)
```

**After**:
```python
from fastapi import HTTPException, status
from app.services.quote_cache import get_quote

@router.get("/dashboard-quote", response_model=DashboardQuote | None)
async def get_dashboard_quote(
    current_user: User = Depends(require_user),
) -> DashboardQuote | None:
    """
    Get dashboard quote with backend caching.
    
    Returns:
        - 200 + DashboardQuote: Quote available (cached or freshly fetched)
        - 200 + None: Quote fetch failed (network error, API down)
        - 503: Quote feature is disabled via configuration
    
    Raises:
        HTTPException: 503 if dashboard_quote_enabled is False
    """
    if not settings.dashboard_quote_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard quote feature is disabled",
        )

    return await get_quote()
```

**Wait, reconsider**: The requirement says "backend API should answer with appropriate HTTP status (service disabled?)". Let's use 503 when disabled, but still return `None` on fetch failure (not 503) to allow graceful degradation.

**Final implementation**:
```python
from fastapi import HTTPException, status
from app.services.quote_cache import get_quote

@router.get("/dashboard-quote", response_model=DashboardQuote)
async def get_dashboard_quote(
    current_user: User = Depends(require_user),
) -> DashboardQuote:
    """
    Get dashboard quote with backend caching.
    
    Returns:
        - 200 + DashboardQuote: Quote available (cached or freshly fetched)
        - 503: Quote feature is disabled
        - 500: Quote fetch failed (treated as None, but signals error)
    
    Raises:
        HTTPException: 503 if dashboard_quote_enabled is False
        HTTPException: 500 if quote fetch failed
    """
    if not settings.dashboard_quote_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard quote feature is disabled",
        )

    quote = await get_quote()
    if quote is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard quote",
        )

    return quote
```

**Wait, reconsidering again**: This breaks graceful degradation. The frontend requirement says "Frontend should render the quote **if** the backend quote api returned a quote". This implies the frontend should handle the absence of a quote gracefully. Let's stick with the original design:

- **503**: Feature disabled (frontend hides UI)
- **200 + None**: Fetch failed (frontend shows fallback or hides)

But the response model is `DashboardQuote | None`, which doesn't work with 503. Let's use a different approach:

**Revised Final Implementation**:
```python
from fastapi import HTTPException, status
from app.services.quote_cache import get_quote

@router.get("/dashboard-quote", response_model=DashboardQuote | None)
async def get_dashboard_quote(
    current_user: User = Depends(require_user),
) -> DashboardQuote | None:
    """
    Get dashboard quote with backend caching.
    
    Returns:
        - 200 + DashboardQuote: Quote available (cached or freshly fetched)
        - 200 + None: Quote fetch failed (allows graceful degradation)
        - 503: Quote feature is disabled (frontend should hide UI)
    
    Raises:
        HTTPException: 503 if dashboard_quote_enabled is False
    """
    if not settings.dashboard_quote_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard quote feature is disabled",
        )

    # get_quote() handles caching internally and returns None on failure
    return await get_quote()
```

This is cleaner and follows the principle of graceful degradation.

#### 1.5 Update Environment Configuration (`.env.example`)

Add new configuration:
```bash
# Dashboard quote settings
DASHBOARD_QUOTE_ENABLED=true
DASHBOARD_QUOTE_URL="https://motivational-spark-api.vercel.app/api/quotes/random"
DASHBOARD_QUOTE_CACHE_TTL=86400  # NEW: Cache TTL in seconds (default: 24 hours = 86400s)
```

### Phase 2: Frontend Simplification

#### 2.1 Remove Client-Side Caching (`frontend/src/routes/dashboard/+page.svelte`)

**Changes**:
1. Remove `DASHBOARD_QUOTE_CACHE_KEY` constant (line 11)
2. Remove `getEndOfDayTimestamp()` function (lines 13-17)
3. Remove `quoteCacheRevalidated` state (line 32)
4. Simplify `loadQuote()` function to remove all localStorage logic
5. Update error handling to handle 503 response

**Before** (lines 75-138):
```typescript
async function loadQuote() {
    quoteLoading = true;
    try {
        const now = Date.now();
        if (typeof localStorage !== 'undefined') {
            const cachedRaw = localStorage.getItem(DASHBOARD_QUOTE_CACHE_KEY);
            if (cachedRaw) {
                const cached = JSON.parse(cachedRaw) as {
                    expiresAt?: number;
                    fetchedAt?: number;
                    quote: DashboardQuote | null;
                    enabled: boolean;
                };
                const expiresAt = cached.expiresAt ?? cached.fetchedAt ?? 0;
                if (!quoteCacheRevalidated) {
                    quoteCacheRevalidated = true;
                } else if (cached.enabled && now < expiresAt) {
                    quoteEnabled = true;
                    quote = cached.quote;
                    return;
                } else if (!cached.enabled && now < expiresAt) {
                    quoteEnabled = false;
                    quote = null;
                    return;
                }
            }
        }

        const data = await api.books.dashboardQuote();
        quoteEnabled = data !== null;
        quote = data;

        if (typeof localStorage !== 'undefined') {
            const expiresAt = getEndOfDayTimestamp();
            localStorage.setItem(
                DASHBOARD_QUOTE_CACHE_KEY,
                JSON.stringify({
                    expiresAt,
                    quote,
                    enabled: quoteEnabled
                })
            );
        }
    } catch {
        if (typeof localStorage !== 'undefined') {
            const cachedRaw = localStorage.getItem(DASHBOARD_QUOTE_CACHE_KEY);
            if (cachedRaw) {
                const cached = JSON.parse(cachedRaw) as {
                    expiresAt?: number;
                    fetchedAt?: number;
                    quote: DashboardQuote | null;
                    enabled: boolean;
                };
                quoteEnabled = cached.enabled;
                quote = cached.quote;
                return;
            }
        }
        quoteEnabled = false;
        quote = null;
    } finally {
        quoteLoading = false;
    }
}
```

**After**:
```typescript
async function loadQuote() {
    quoteLoading = true;
    try {
        const data = await api.books.dashboardQuote();
        quoteEnabled = true;
        quote = data;
    } catch (error: any) {
        // Handle 503 (feature disabled) vs other errors
        if (error?.response?.status === 503) {
            // Feature disabled: hide quote UI permanently
            quoteEnabled = false;
            quote = null;
        } else {
            // Network error or fetch failure: show fallback or hide temporarily
            console.warn('Failed to load dashboard quote:', error);
            quoteEnabled = false;
            quote = null;
        }
    } finally {
        quoteLoading = false;
    }
}
```

**Note**: Need to verify how the `api.books.dashboardQuote()` function handles HTTP errors. Let's check the implementation.

#### 2.2 Update API Client (`frontend/src/lib/api.ts`)

Check current implementation around line 202:
```typescript
return request<DashboardQuote | null>('/books/dashboard-quote');
```

Need to verify if the `request()` function throws on 503 or returns `null`. If it swallows the error, we need to update it to preserve HTTP status codes for proper error handling.

**Expected behavior**:
- 200 + data: Return `DashboardQuote | null`
- 503: Throw error with status code
- Other errors: Throw error

If the current `request()` function doesn't expose HTTP status codes, we need to either:
1. Update `request()` to include status in errors, OR
2. Make a direct fetch call in `loadQuote()` to handle status codes

**Assumption for plan**: We'll update the error handling in `loadQuote()` to check for 503 status. Implementation details will be determined during coding phase.

#### 2.3 Update Component Rendering Logic

The rendering logic (lines 168-180) should remain mostly unchanged, but we can simplify error messages since there's no stale cache fallback anymore.

**Current rendering** (lines 168-180):
```svelte
{#if quoteEnabled}
    <div class="card bg-gradient-to-br from-primary to-accent text-white shadow-xl">
        <div class="card-body">
            <h2 class="card-title">{$_('dashboard.quoteTitle')}</h2>
            {#if quoteLoading}
                <span class="loading loading-spinner loading-lg"></span>
            {:else if quote}
                <p class="text-lg leading-relaxed">"{quote.quote}"</p>
                {#if quote.author}
                    <p class="text-white/80">- {quote.author}</p>
                {/if}
            {:else}
                <p class="text-white/90">{$_('dashboard.quoteUnavailable')}</p>
            {/if}
        </div>
    </div>
{/if}
```

**After**: No changes needed—this logic already handles all states correctly:
- `quoteEnabled = false`: Entire card hidden
- `quoteLoading = true`: Spinner shown
- `quote = null`: Fallback message shown
- `quote` exists: Quote rendered

### Phase 3: Testing

#### 3.1 Backend Tests (`backend/tests/test_dashboard.py`)

**New test cases**:

1. **Test caching behavior**:
```python
def test_dashboard_quote_caching(client: TestClient, monkeypatch):
    """Verify quote is cached and reused within TTL"""
    from app.services import quote_cache
    
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)
    monkeypatch.setattr(settings, "dashboard_quote_cache_ttl", 60)
    
    # Mock external API
    call_count = 0
    def mock_get(url):
        nonlocal call_count
        call_count += 1
        return _FakeQuoteResponse()
    
    monkeypatch.setattr(books_router.httpx.AsyncClient, "get", mock_get)
    
    # Invalidate cache before test
    quote_cache.invalidate_cache()
    
    # First request: cache miss, should call external API
    resp1 = client.get("/api/books/dashboard-quote")
    assert resp1.status_code == 200
    assert call_count == 1
    
    # Second request: cache hit, should NOT call external API
    resp2 = client.get("/api/books/dashboard-quote")
    assert resp2.status_code == 200
    assert resp2.json() == resp1.json()
    assert call_count == 1  # Still 1, not 2


def test_dashboard_quote_ttl_expiration(client: TestClient, monkeypatch):
    """Verify cache expires after TTL"""
    import time
    from app.services import quote_cache
    
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)
    monkeypatch.setattr(settings, "dashboard_quote_cache_ttl", 1)  # 1 second TTL
    
    # Mock external API
    call_count = 0
    def mock_get(url):
        nonlocal call_count
        call_count += 1
        return _FakeQuoteResponse()
    
    monkeypatch.setattr(books_router.httpx.AsyncClient, "get", mock_get)
    
    # Invalidate cache
    quote_cache.invalidate_cache()
    
    # First request: cache miss
    resp1 = client.get("/api/books/dashboard-quote")
    assert resp1.status_code == 200
    assert call_count == 1
    
    # Wait for cache to expire
    time.sleep(1.5)
    
    # Second request: cache expired, should call API again
    resp2 = client.get("/api/books/dashboard-quote")
    assert resp2.status_code == 200
    assert call_count == 2


def test_dashboard_quote_disabled_returns_503(client: TestClient, monkeypatch):
    """Verify 503 response when feature is disabled"""
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)
    
    resp = client.get("/api/books/dashboard-quote")
    
    assert resp.status_code == 503
    assert "disabled" in resp.json()["detail"].lower()


def test_dashboard_quote_fetch_failure_returns_none(client: TestClient, monkeypatch):
    """Verify None response when external API fails"""
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)
    
    # Mock external API failure
    async def mock_failing_get(url):
        raise httpx.TimeoutException("API timeout")
    
    monkeypatch.setattr(books_router.httpx.AsyncClient, "get", mock_failing_get)
    
    # Invalidate cache
    from app.services import quote_cache
    quote_cache.invalidate_cache()
    
    resp = client.get("/api/books/dashboard-quote")
    
    assert resp.status_code == 200
    assert resp.json() is None


def test_dashboard_quote_cache_invalidation(client: TestClient, monkeypatch):
    """Verify manual cache invalidation works"""
    from app.services import quote_cache
    
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)
    
    call_count = 0
    def mock_get(url):
        nonlocal call_count
        call_count += 1
        return _FakeQuoteResponse()
    
    monkeypatch.setattr(books_router.httpx.AsyncClient, "get", mock_get)
    
    quote_cache.invalidate_cache()
    
    # First request: cache miss
    client.get("/api/books/dashboard-quote")
    assert call_count == 1
    
    # Invalidate cache
    quote_cache.invalidate_cache()
    
    # Next request: cache miss again
    client.get("/api/books/dashboard-quote")
    assert call_count == 2
```

2. **Update existing tests**:

Update `test_dashboard_quote_returns_none_when_disabled` to expect 503:
```python
def test_dashboard_quote_returns_none_when_disabled(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_quote_enabled", False)

    resp = client.get("/api/books/dashboard-quote")

    assert resp.status_code == 503  # Changed from 200
```

Keep `test_dashboard_quote_returns_quote` but add cache invalidation:
```python
def test_dashboard_quote_returns_quote(client: TestClient, monkeypatch):
    from app.services import quote_cache
    
    monkeypatch.setattr(settings, "dashboard_quote_enabled", True)
    monkeypatch.setattr(books_router.httpx, "AsyncClient", _FakeAsyncClient)
    
    quote_cache.invalidate_cache()  # Add this line

    resp = client.get("/api/books/dashboard-quote")

    assert resp.status_code == 200
    assert resp.json() == {"quote": "Stay humble.", "author": "Anon"}
```

#### 3.2 Frontend Tests (`frontend/src/lib/validation.test.ts` or new file)

**Note**: The frontend currently has minimal test coverage. We should add tests for the quote loading logic if vitest is set up properly.

**New test file**: `frontend/src/routes/dashboard/quote.test.ts`

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '$lib/api';

// Note: This is a skeleton. Actual implementation depends on:
// 1. How to test Svelte 5 components with runes
// 2. How to mock the api.books.dashboardQuote() function
// 3. How to verify UI rendering based on state

describe('Dashboard Quote', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should fetch quote on load', async () => {
        const mockQuote = { quote: 'Test quote', author: 'Tester' };
        vi.spyOn(api.books, 'dashboardQuote').mockResolvedValue(mockQuote);

        // TODO: Mount component and verify loadQuote() is called
        // TODO: Verify quote is rendered in UI
    });

    it('should hide UI when feature is disabled (503)', async () => {
        const error = { response: { status: 503 } };
        vi.spyOn(api.books, 'dashboardQuote').mockRejectedValue(error);

        // TODO: Mount component
        // TODO: Verify quoteEnabled = false
        // TODO: Verify quote UI is not rendered
    });

    it('should show fallback message on fetch failure', async () => {
        const error = new Error('Network error');
        vi.spyOn(api.books, 'dashboardQuote').mockRejectedValue(error);

        // TODO: Mount component
        // TODO: Verify quoteEnabled = false
        // TODO: Verify fallback message is shown or UI is hidden
    });

    it('should NOT cache quote in localStorage', async () => {
        const mockQuote = { quote: 'Test quote', author: 'Tester' };
        vi.spyOn(api.books, 'dashboardQuote').mockResolvedValue(mockQuote);

        // TODO: Mount component
        // TODO: Verify localStorage.setItem is NOT called
    });
});
```

**Decision**: Given the current minimal frontend test coverage, we'll defer comprehensive frontend tests until the test infrastructure is better established. Focus on backend tests first.

### Phase 4: Documentation & Migration

#### 4.1 Update `.env.example`

Already covered in Phase 1.5.

#### 4.2 Update README (if exists)

Search for documentation about environment variables and add the new `DASHBOARD_QUOTE_CACHE_TTL` variable.

#### 4.3 Migration Notes

**For existing deployments**:
1. Add `DASHBOARD_QUOTE_CACHE_TTL=86400` to `.env` file
2. Restart backend container
3. Frontend will automatically adapt (no localStorage migration needed)
4. Stale localStorage entries will be ignored (safe to leave in place)

**Cache warming** (optional):
- On backend startup, we could optionally pre-warm the cache by fetching a quote
- Not necessary—first user request will populate the cache

## Implementation Steps Summary

### Backend Changes

1. ✅ Update `backend/pyproject.toml`: Add `cachetools>=5.3.0`
2. ✅ Update `backend/app/config.py`: Add `dashboard_quote_cache_ttl: int = 86400`
3. ✅ Create `backend/app/services/quote_cache.py`: Implement TTL cache module
4. ✅ Update `backend/app/routers/books.py`: Replace `get_dashboard_quote()` with cached version
5. ✅ Update `backend/tests/test_dashboard.py`: Add cache tests, update existing tests
6. ✅ Update `.env.example`: Add `DASHBOARD_QUOTE_CACHE_TTL`

### Frontend Changes

1. ✅ Update `frontend/src/routes/dashboard/+page.svelte`:
   - Remove `DASHBOARD_QUOTE_CACHE_KEY` constant
   - Remove `getEndOfDayTimestamp()` function
   - Remove `quoteCacheRevalidated` state variable
   - Simplify `loadQuote()` to remove all localStorage logic
   - Update error handling to distinguish 503 from other errors

2. ⚠️ Verify `frontend/src/lib/api.ts`: Ensure error handling preserves HTTP status codes

3. ⏸️ (Optional) Add frontend tests if test infrastructure is ready

### Deployment

1. ✅ Update `.env` with new variable
2. ✅ Install backend dependencies: `uv sync` (or equivalent)
3. ✅ Restart backend container
4. ✅ Deploy frontend (no changes needed to build config)

## Risk Assessment

### High Priority Risks

1. **Thread-safety**: `cachetools.TTLCache` is thread-safe for basic operations, but we use `threading.Lock()` for write operations to ensure consistency
   - **Mitigation**: Use locks consistently, test with concurrent requests

2. **Cache invalidation**: No manual cache invalidation endpoint
   - **Mitigation**: Short TTL (24 hours default) ensures stale quotes don't persist long; add invalidation endpoint if needed later

3. **Single-instance assumption**: Cache is in-memory, not shared across multiple backend instances
   - **Mitigation**: Document this limitation; use Redis/Memcached if scaling to multiple instances

### Medium Priority Risks

1. **External API dependency**: Still relies on external quote API
   - **Mitigation**: Graceful degradation (return `None` on failure); low impact

2. **TTL misconfiguration**: Setting TTL too high/low could impact performance
   - **Mitigation**: Document recommended values (1-6 hours); easy to adjust via env var

3. **Frontend error handling**: Need to verify `api.books.dashboardQuote()` preserves HTTP status codes
   - **Mitigation**: Test error handling; update `request()` function if needed

### Low Priority Risks

1. **Stale localStorage entries**: Old frontend cache entries remain in users' browsers
   - **Impact**: Harmless—ignored by new code; will be garbage collected eventually

2. **Test coverage**: Frontend tests are minimal
   - **Mitigation**: Focus on backend tests first; add frontend tests later

## Success Criteria

### Functional Requirements

- ✅ Backend caches quotes with configurable TTL
- ✅ Frontend calls quote endpoint on every page load
- ✅ Frontend does NOT use localStorage for caching
- ✅ Backend returns 503 when feature is disabled
- ✅ Frontend hides quote UI when 503 received
- ✅ Frontend shows quote when 200 + data received
- ✅ Frontend handles fetch failures gracefully (200 + None)

### Non-Functional Requirements

- ✅ External API calls reduced from N (users) * M (daily refreshes) to ~1 per TTL period
- ✅ Response time for cached quotes: <10ms (vs 200-8000ms for external API)
- ✅ Thread-safe concurrent request handling
- ✅ No breaking changes to existing API contract (still returns `DashboardQuote | None` on 200)
- ✅ Backward compatible (old frontend code will work, just won't benefit from backend caching)

### Testing Requirements

- ✅ All existing backend tests pass
- ✅ New backend tests cover caching, TTL expiration, invalidation
- ✅ Manual testing confirms frontend behavior changes as expected
- ✅ Performance testing shows reduced external API calls

## Performance Expectations

### Before (Current State)

- **External API calls**: 1 per user per day (minimum)
- **Response time**: 200-8000ms (network latency + external API processing)
- **Failure rate**: Dependent on external API uptime (~99.9% assumption)

**Example scenario** (100 active users, 5 dashboard views per day):
- Daily external API calls: 100 users * 1 call/day = **100 calls/day**
- Monthly external API calls: **~3,000 calls/month**

### After (With Backend Caching)

- **External API calls**: 1 per TTL period (e.g., 1 per hour with default config)
- **Response time (cache hit)**: <10ms (in-memory cache)
- **Response time (cache miss)**: 200-8000ms (same as before, but rare)
- **Failure rate**: Same as before, but impact reduced (cached quotes continue serving)

**Example scenario** (100 active users, TTL = 24 hours):
- Daily external API calls: 24 hours/day * 1 call/hour = **24 calls/day**
- Monthly external API calls: **~720 calls/month**
- **Reduction**: 76% fewer external API calls (3,000 → 720)

**Example scenario** (TTL = 6 hours):
- Daily external API calls: **4 calls/day**
- Monthly external API calls: **~120 calls/month**
- **Reduction**: 96% fewer external API calls (3,000 → 120)

### Cache Hit Rate Expectations

- **Assumption**: Average dashboard view frequency = 5 views/user/day
- **Cache hit rate** (TTL = 24 hours): ~99% (only first request in each hour misses cache)
- **Cache hit rate** (TTL = 6 hours): ~99.5%

## Alternative Approaches Considered

### 1. Redis/Memcached Cache

**Pros**:
- Shared across multiple backend instances
- Persistent across restarts
- Better for high-scale deployments

**Cons**:
- Additional infrastructure dependency
- Increased complexity
- Overkill for single-instance deployment

**Decision**: Rejected for now; revisit if scaling to multiple backend instances.

### 2. Database-Backed Cache

**Pros**:
- Persistent across restarts
- No additional dependencies

**Cons**:
- Slower than in-memory cache
- Adds database writes (unnecessary I/O)
- More complex expiration logic

**Decision**: Rejected; in-memory cache with TTL is simpler and faster.

### 3. Frontend Caching with Backend-Controlled TTL

**Pros**:
- Reduces backend load (no repeated calls within TTL)
- Backend controls cache behavior via HTTP headers (Cache-Control, Expires)

**Cons**:
- Frontend still has caching logic (violates requirement)
- HTTP cache headers don't support "feature disabled" state caching
- Less control over cache invalidation

**Decision**: Rejected; requirements explicitly state "frontend should not do any caching".

### 4. Server-Sent Events (SSE) for Quote Updates

**Pros**:
- Real-time quote updates without polling
- Efficient for multiple clients

**Cons**:
- Overkill for quotes (not time-sensitive)
- Increased backend complexity
- Requires persistent connections

**Decision**: Rejected; quotes don't need real-time updates.

## Future Enhancements (Out of Scope)

1. **Cache invalidation endpoint**: `POST /api/books/dashboard-quote/invalidate` (admin-only)
2. **Quote history**: Store last N quotes in database for admin review
3. **Custom quotes**: Allow admins to add custom quotes to rotation
4. **Multi-tenancy**: Per-user or per-organization quote preferences
5. **Metrics/observability**: Expose cache hit rate via `/metrics` endpoint
6. **Redis fallback**: Auto-detect Redis and use it if available
7. **Quote approval queue**: Moderate external API quotes before displaying

## Questions for Review

1. ✅ Is 24 hours (86400s) a reasonable default TTL? (Can be adjusted via env var)
2. ✅ Should we return 503 (Service Unavailable) or 204 (No Content) when disabled?
   - **Decision**: 503 is more semantically correct (feature is unavailable)
3. ✅ Should fetch failures return `None` (graceful degradation) or raise 500 error?
   - **Decision**: Return `None` for graceful degradation
4. ⚠️ Do we need a cache invalidation endpoint for manual refresh?
   - **Decision**: Not in initial implementation; add if needed later
5. ⚠️ Should we pre-warm the cache on backend startup?
   - **Decision**: Not necessary; first request will populate cache

## References

- **cachetools documentation**: https://cachetools.readthedocs.io/
- **FastAPI dependency injection**: https://fastapi.tiangolo.com/tutorial/dependencies/
- **HTTP status codes**: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
- **Thread-safety in Python**: https://docs.python.org/3/library/threading.html

## Appendix: Files Modified

### Backend
- `backend/pyproject.toml` (add dependency)
- `backend/app/config.py` (add TTL config)
- `backend/app/services/quote_cache.py` (new file)
- `backend/app/routers/books.py` (replace quote endpoint)
- `backend/tests/test_dashboard.py` (add/update tests)
- `.env.example` (document new variable)

### Frontend
- `frontend/src/routes/dashboard/+page.svelte` (simplify quote loading)
- `frontend/src/lib/api.ts` (verify error handling)

### Documentation
- `.env.example` (updated)
- README.md (if applicable)

---

**Plan Status**: ✅ Ready for Review  
**Estimated Effort**: 4-6 hours (backend: 3-4h, frontend: 1-2h)  
**Priority**: Medium (optimization, not critical bug)
