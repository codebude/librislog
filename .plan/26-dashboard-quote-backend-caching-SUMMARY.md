# Summary: Dashboard Quote Backend Caching

## Overview

Move quote caching from frontend (localStorage) to backend (in-memory TTL cache), reducing external API load by ~76-96% while simplifying frontend code.

## Current State

- **Frontend**: Complex localStorage caching with end-of-day TTL (~24h)
- **Backend**: No caching, every request hits external API
- **Problem**: N users × M daily refreshes = unnecessary external API load

## Proposed Solution

- **Backend**: In-memory TTL cache using `cachetools` library
- **Frontend**: Simple API calls on every page load, no caching logic
- **Configuration**: TTL configurable via `.env` (default: 24 hour)

## Key Changes

### Backend
1. Add `cachetools>=5.3.0` dependency
2. New service module: `backend/app/services/quote_cache.py`
3. Update router: Return **503** when disabled (not 200 + None)
4. New config: `DASHBOARD_QUOTE_CACHE_TTL=86400` (seconds)

### Frontend
1. Remove all localStorage caching logic (~60 lines)
2. Simplify `loadQuote()` function
3. Handle 503 status (hide UI when disabled)
4. Call API on every dashboard load (backend handles caching)

## Benefits

### Performance
- **External API calls reduced**: 3,000/month → 720/month (76% reduction with 1h TTL)
- **Response time (cached)**: <10ms vs 200-8000ms
- **Cache hit rate**: ~99% (with 1h TTL)

### Architecture
- **Separation of concerns**: Backend owns caching, frontend owns UI
- **Centralized control**: TTL and cache invalidation managed server-side
- **Graceful degradation**: Fetch failures return `None` without breaking UI

### Maintainability
- **Frontend complexity**: Reduced by ~60 lines of caching logic
- **Backend observability**: Easy to add metrics/logging
- **Configuration**: Single env var controls cache behavior

## HTTP Response Model

| Scenario | Status | Response | Frontend Action |
|----------|--------|----------|-----------------|
| Feature disabled | 503 | Error | Hide quote UI |
| Cache hit | 200 | `DashboardQuote` | Show quote |
| Cache miss → fetch success | 200 | `DashboardQuote` | Show quote |
| Cache miss → fetch failure | 200 | `None` | Show fallback |

## Risk Mitigation

1. **Thread-safety**: Use `threading.Lock()` for cache writes
2. **Single-instance limitation**: Documented; use Redis if scaling to multi-instance
3. **Stale quotes**: Short TTL (1h default) prevents long-term staleness
4. **External API failures**: Graceful degradation (return `None`)

## Testing Strategy

### Backend Tests (High Priority)
- ✅ Cache hit/miss behavior
- ✅ TTL expiration
- ✅ Manual cache invalidation
- ✅ Disabled state (503 response)
- ✅ Fetch failure handling

### Frontend Tests (Medium Priority)
- ⏸️ Verify localStorage NOT used
- ⏸️ Verify 503 handling (hide UI)
- ⏸️ Verify error handling (show fallback)

## Implementation Effort

- **Backend**: 3-4 hours (new module, tests, config)
- **Frontend**: 1-2 hours (remove caching logic, update error handling)
- **Total**: 4-6 hours

## Deployment

1. Update `.env`: Add `DASHBOARD_QUOTE_CACHE_TTL=3600`
2. Backend: Install `cachetools` dependency
3. Restart backend container
4. Deploy frontend (builds automatically handle changes)

## Success Criteria

- ✅ External API calls reduced by >75%
- ✅ Cached response time <10ms
- ✅ Frontend has no localStorage caching code
- ✅ All tests pass
- ✅ 503 response when disabled

## Future Enhancements (Out of Scope)

- Cache invalidation endpoint (admin)
- Redis/Memcached for multi-instance support
- Quote history/approval queue
- Metrics/observability dashboard
- Custom quotes feature

---

**Plan Ready**: ✅ Yes  
**Review Recommended**: Architecture, HTTP status code design  
**Estimated Delivery**: 1 day (single developer)
