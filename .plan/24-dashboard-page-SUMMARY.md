# Plan Summary: Dashboard Page Implementation

## Overview
Implement a new Dashboard page as the application's landing/start page, providing an at-a-glance overview of reading activity.

## Key Features

### 1. Dashboard Components
- **Welcome Section**: Personalized greeting and subtitle
- **Inspirational Quote**: Optional quote from quoteslate.vercel.app API (controllable via env var)
- **Statistics Cards**: 4 clickable cards showing:
  - Total Books in Library
  - Books Read
  - Books to Read (Want to Read)
  - Currently Reading
- **Currently Reading Section**: Display all books with status "currently_reading"
- **Next to Read Section**: Display up to 5 books from "want_to_read" queue

### 2. Navigation Changes
- Dashboard becomes first menu item (before Library)
- Root URL (`/`) redirects to `/dashboard` instead of `/library`
- Library remains accessible at `/library`

### 3. Backend Addition
- **New Endpoint**: `GET /api/books/stats`
  - Returns aggregate statistics scoped to current user
  - Simple COUNT queries on indexed fields
  - Response schema: `LibraryStats` (total_books, books_read, books_reading, books_want_to_read, books_did_not_finish)

### 4. Environment Configuration
- **New Variable**: `DASHBOARD_QUOTE_ENABLED=true`
- Quote feature is optional and fails gracefully
- No API key required for quote service

## Technical Approach

### Backend (FastAPI/Python)
- New `/stats` endpoint in `books.py` router
- Add `LibraryStats` schema to `schemas.py`
- Uses SQLModel `func.count()` for efficient aggregation
- User-scoped queries (via `require_user_by_api_key`)

### Frontend (SvelteKit/TypeScript)
- New route: `frontend/src/routes/dashboard/+page.svelte`
- Uses existing components: `BookCard`, `BookDrawer`
- DaisyUI components: stats cards, gradients, responsive grids
- Svelte 5 patterns: `$state`, `$derived`, `$effect`
- Parallel API calls with `Promise.all`
- External quote API with graceful error handling

### Styling
- DaisyUI components for consistency
- Responsive grid layouts (2 cols mobile, 4 cols desktop)
- Clickable stat cards with hover effects
- Gradient background for quote section
- SVG icons for visual hierarchy

## Files to Create
1. `backend/tests/test_dashboard.py` - Stats endpoint tests
2. `frontend/src/routes/dashboard/+page.svelte` - Dashboard component
3. `frontend/src/routes/dashboard/+page.test.ts` - Frontend unit tests

## Files to Modify
1. `backend/app/routers/books.py` - Add stats endpoint
2. `backend/app/schemas.py` - Add LibraryStats schema
3. `frontend/src/lib/api.ts` - Add getStats method
4. `frontend/src/lib/types.ts` - Add LibraryStats interface
5. `frontend/src/routes/+layout.svelte` - Update navigation order
6. `frontend/src/routes/+page.svelte` - Redirect to dashboard
7. `frontend/src/lib/i18n/locales/en.json` - Add translations
8. `frontend/src/lib/i18n/locales/de.json` - Add translations
9. `.env.example` - Add DASHBOARD_QUOTE_ENABLED

## Testing Strategy

### Backend Tests (pytest)
- ✅ Stats accuracy across all statuses
- ✅ Empty library (all zeros)
- ✅ Multi-user data isolation
- ✅ Authentication requirement
- ✅ Stats update on book status change
- ✅ Stats update on book deletion

### Frontend Tests (Vitest)
- ✅ Loading state
- ✅ Stats fetching and display
- ✅ Books fetching (currently reading, next to read)
- ✅ Empty state handling
- ✅ Quote enabled/disabled toggle
- ✅ Quote API failure handling
- ✅ Book drawer interaction
- ✅ Error handling

### Manual Testing
- Desktop/mobile responsiveness
- Navigation flow
- Internationalization (en, de)
- Quote feature on/off
- Performance (API call timing)
- Security (authentication)

## Risk Assessment

**Low Risk**:
- Additive changes (no breaking modifications)
- Read-only statistics endpoint
- Optional quote feature

**Medium Risk**:
- External quote API dependency (mitigated: optional, graceful failure)
- Navigation order change (mitigated: dashboard-first is standard pattern)

## Success Criteria
1. Dashboard accessible and loads without errors
2. Statistics display accurate counts
3. Currently reading and next to read sections populate correctly
4. Quote displays when enabled, hidden when disabled
5. Quote API failures don't break page
6. Stats cards navigate to filtered library views
7. All tests pass (backend + frontend)
8. Translations complete (en, de)
9. Responsive on all screen sizes
10. No console errors

## Estimated Effort
- Backend (endpoint + tests): 1-2 hours
- Frontend (dashboard page): 3-4 hours
- Navigation/routing updates: 0.5 hours
- Translations: 0.5 hours
- Environment config: 0.5 hours
- Testing: 2-3 hours
- Manual QA: 1-2 hours

**Total: 8-12 hours**

**Priority**: High  
**Complexity**: Medium  
**Risk**: Low

## Next Steps
1. Review and approve plan
2. Implement backend statistics endpoint
3. Write backend tests
4. Implement frontend dashboard page
5. Update navigation and routing
6. Add translations
7. Configure environment variables
8. Run test suite
9. Manual testing and verification
10. Deploy and monitor

---

**See full plan**: `24-dashboard-page.md` for complete implementation details, code examples, and comprehensive test scenarios.
