# Implementation Plan: API Documentation in Settings

**Feature ID:** 20  
**Status:** Planning  
**Priority:** Medium  
**Complexity:** Medium

## Overview

This plan outlines how to make the FastAPI-generated API documentation (Swagger UI / ReDoc) accessible from the Settings page, with visual integration to match the app's look and feel.

## Current State Analysis

### Backend
- FastAPI app exists at `backend/app/main.py`
- App title: "LibrisLog API"
- Default Swagger UI available at `/docs` (not customized)
- Default ReDoc available at `/redoc` (not customized)
- Uses Traefik reverse proxy routing `/api/*` to backend
- CORS configured for frontend origins

### Frontend
- Settings page at `frontend/src/routes/settings/+page.svelte`
- Currently only contains language selection
- Uses TailwindCSS with DaisyUI components
- Card-based UI with `bg-base-100`, `shadow-sm`, `border-base-200` styling
- i18n system in place (`$_()` translation function)

### Environment
- Backend served via Docker on port 8000
- Frontend served via Docker/nginx on port 80
- Traefik routes `/api` to backend, `/` to frontend
- Production URL structure: `http://localhost:8080/api/*`

---

## Requirements

### Functional Requirements
1. **Access API Docs from Settings**: Users should be able to view API documentation from the settings page
2. **Choose Documentation Style**: Support both Swagger UI and ReDoc (user preference or toggle)
3. **Visual Integration**: Docs should match app theme (colors, fonts, spacing)
4. **Responsive Design**: Works on mobile and desktop
5. **Security**: Docs should be accessible to end users without exposing internal implementation details unnecessarily

### Non-Functional Requirements
- No performance degradation on settings page load
- Docs should load quickly (consider CDN vs self-hosted assets)
- Must work in production Docker environment with Traefik routing
- Should work offline or in restricted networks (consider self-hosting assets)

---

## Implementation Options Analysis

### Option A: Embedded iframe
**Approach**: Embed existing `/docs` or `/redoc` endpoint in an iframe within settings page

**Pros:**
- Simplest to implement
- No backend changes needed (uses existing endpoints)
- Full functionality maintained (interactive try-it-out features)
- Easy to toggle between Swagger UI and ReDoc

**Cons:**
- Limited styling customization (iframe sandboxing)
- Potential cross-origin issues if domains differ
- Cannot seamlessly match app theme colors without custom backend config
- Less integrated UX (scrolling, navigation)

**Complexity:** Low

---

### Option B: Custom Styled Docs Endpoint
**Approach**: Create custom `/api/docs` endpoint serving Swagger UI with custom CSS matching app theme

**Pros:**
- Better visual integration (custom CSS)
- Still uses native Swagger UI functionality
- Can inject DaisyUI theme variables
- Relatively straightforward backend changes

**Cons:**
- Requires backend configuration changes
- Need to maintain custom CSS
- Still somewhat separate from app (separate page/iframe)

**Complexity:** Medium

---

### Option C: In-App Swagger UI Component
**Approach**: Load Swagger UI or ReDoc JavaScript bundle directly in Svelte component, styled inline

**Pros:**
- Deepest integration with app UI
- Complete control over styling and behavior
- Can wrap in collapsible sections, tabs, etc.
- No iframe isolation issues

**Cons:**
- Requires installing Swagger UI npm package or loading from CDN
- More complex frontend implementation
- Bundle size increase (Swagger UI is ~2MB)
- Need to fetch OpenAPI spec from backend

**Complexity:** High

---

### Option D: Link to Separate Docs Page
**Approach**: Add a link/button in settings that opens docs in new tab/window

**Pros:**
- Simplest implementation (just a link)
- No integration complexity
- Docs remain fully functional

**Cons:**
- Minimal visual integration
- Jarring UX (leaves app)
- Doesn't meet "visually integrate" requirement

**Complexity:** Very Low

---

## Recommended Approach

**Hybrid of Option B + Option A**

1. **Backend**: Customize FastAPI docs endpoint with theme-aware CSS
2. **Frontend**: Embed customized endpoint in iframe with DaisyUI card styling around it
3. **Progressive Enhancement**: Start with iframe, optionally upgrade to Option C in future if deeper integration is needed

### Why This Approach?
- Balances implementation complexity with visual integration
- Maintains full Swagger UI functionality (interactive API testing)
- Achieves reasonable theme matching via custom CSS
- Can be implemented incrementally
- Doesn't significantly increase frontend bundle size
- Works in Docker/Traefik environment

---

## Detailed Implementation Plan

### Phase 1: Backend Customization

#### Step 1.1: Configure Custom Swagger UI Endpoint
**File:** `backend/app/main.py`

**Changes:**
- Import `get_swagger_ui_html` and `get_redoc_html` from `fastapi.openapi.docs`
- Disable default docs: `FastAPI(docs_url=None, redoc_url=None)`
- Create custom `/api/docs` endpoint returning Swagger UI HTML with custom CSS
- Create custom `/api/redoc` endpoint returning ReDoc HTML with custom CSS

**Custom CSS Requirements:**
- Match DaisyUI theme colors (use CSS variables for base-100, base-200, base-content, primary, etc.)
- Adjust fonts to match app (system font stack)
- Remove Swagger UI branding/watermark
- Adjust spacing/padding to match card components

**Code Pattern (from Context7):**
```python
@app.get("/api/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - API Documentation",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_favicon_url="/static/favicon.ico",  # Optional
    )
```

#### Step 1.2: Add Custom CSS Injection
**Approach:** Use inline `<style>` tag in returned HTML to override Swagger UI defaults

**File:** Create `backend/app/templates/swagger_custom.html` (Jinja2 template)

**Custom CSS Targets:**
```css
/* Match DaisyUI theme */
.swagger-ui {
  --primary: oklch(var(--p));
  --background: oklch(var(--b1));
  font-family: ui-sans-serif, system-ui, sans-serif;
}
.swagger-ui .topbar { display: none; } /* Remove branding */
.swagger-ui .info { padding: 1rem; }
```

**Alternative:** Serve custom CSS from `/static/docs-theme.css` if static files mounting is set up

#### Step 1.3: Environment Configuration
**File:** `backend/app/config.py`

**Add settings:**
```python
docs_enabled: bool = True  # Allow disabling in production if needed
docs_custom_css_url: str = ""  # Optional custom CSS override
```

**Testing:**
- Start backend: `cd backend && uv run uvicorn app.main:app --reload`
- Visit `http://localhost:8000/api/docs` and verify custom styling
- Visit `http://localhost:8000/api/redoc` and verify custom styling

---

### Phase 2: Frontend Integration

#### Step 2.1: Update Settings Page UI
**File:** `frontend/src/routes/settings/+page.svelte`

**Changes:**
1. Add new card section below language settings
2. Add toggle/tabs to switch between Swagger UI and ReDoc
3. Embed iframe pointing to `/api/docs` or `/api/redoc`
4. Style iframe container to match card design
5. Add loading indicator while iframe loads

**UI Structure:**
```svelte
<div class="card bg-base-100 shadow-sm border border-base-200">
  <div class="card-body gap-3">
    <div class="flex justify-between items-center">
      <span class="label label-text font-semibold">{$_('settings.apiDocsTitle')}</span>
      <!-- Toggle between Swagger UI and ReDoc -->
      <div class="join">
        <button class="join-item btn btn-sm" class:btn-active={docsType === 'swagger'}>
          Swagger UI
        </button>
        <button class="join-item btn btn-sm" class:btn-active={docsType === 'redoc'}>
          ReDoc
        </button>
      </div>
    </div>
    
    <div class="relative w-full" style="height: 600px;">
      {#if loading}
        <div class="flex items-center justify-center h-full">
          <span class="loading loading-spinner loading-lg"></span>
        </div>
      {/if}
      <iframe
        src={docsUrl}
        title="API Documentation"
        class="w-full h-full border border-base-300 rounded-lg"
        on:load={() => loading = false}
      />
    </div>
    
    <p class="text-xs text-base-content/60">
      {$_('settings.apiDocsHelp')}
    </p>
  </div>
</div>
```

**Component Logic:**
```typescript
let docsType: 'swagger' | 'redoc' = 'swagger';
let loading = true;
$: docsUrl = docsType === 'swagger' ? '/api/docs' : '/api/redoc';
$: if (docsUrl) loading = true; // Reset loading on URL change
```

#### Step 2.2: Add i18n Translations
**Files:**
- `frontend/src/lib/i18n/locales/en.json`
- `frontend/src/lib/i18n/locales/de.json`

**Add to "settings" section:**
```json
"apiDocsTitle": "API Documentation",
"apiDocsHelp": "Explore the backend API endpoints and schemas. Use the 'Try it out' feature to test requests.",
"apiDocsSwagger": "Swagger UI",
"apiDocsRedoc": "ReDoc"
```

**German translations:**
```json
"apiDocsTitle": "API-Dokumentation",
"apiDocsHelp": "Erkunden Sie die Backend-API-Endpunkte und Schemas. Verwenden Sie 'Try it out', um Anfragen zu testen.",
"apiDocsSwagger": "Swagger UI",
"apiDocsRedoc": "ReDoc"
```

#### Step 2.3: Optional - Collapsible Section
**Enhancement:** Make API docs section collapsible to reduce visual clutter

**Approach:** Use DaisyUI collapse component or custom accordion

```svelte
<div class="collapse collapse-arrow bg-base-100 border border-base-200">
  <input type="checkbox" bind:checked={docsExpanded} />
  <div class="collapse-title font-semibold">
    {$_('settings.apiDocsTitle')}
  </div>
  <div class="collapse-content">
    <!-- iframe content here -->
  </div>
</div>
```

---

### Phase 3: Styling & Theme Integration

#### Step 3.1: Extract DaisyUI Theme Variables
**Challenge:** Swagger UI CSS needs to match current theme (light/dark mode)

**Solution Options:**

**Option A: Hardcode Light Theme**
- Simplest: Just style for light theme matching current app
- Downside: Doesn't adapt if app adds dark mode support

**Option B: CSS Variable Bridge**
- FastAPI template reads theme from cookie/query param
- Injects appropriate CSS variables
- More complex but future-proof

**Recommended for MVP:** Option A (hardcode light theme), document Option B for future

#### Step 3.2: Custom CSS for Swagger UI
**File:** `backend/app/templates/swagger_custom.html`

**Target Styles:**
```css
<style>
  /* DaisyUI theme integration */
  :root {
    --primary-color: oklch(65.69% 0.196 275.75); /* DaisyUI primary */
    --background-color: oklch(100% 0 0); /* base-100 */
    --text-color: oklch(25.93% 0.016 285.75); /* base-content */
    --border-color: oklch(90.04% 0.005 286.32); /* base-200 */
  }

  .swagger-ui {
    font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
  }
  
  /* Hide Swagger branding */
  .swagger-ui .topbar {
    display: none;
  }
  
  /* Match card styling */
  .swagger-ui .information-container {
    padding: 1rem;
    background: var(--background-color);
  }
  
  /* Button styling to match DaisyUI */
  .swagger-ui .btn {
    border-radius: 0.5rem;
    font-weight: 600;
    text-transform: capitalize;
  }
  
  /* Adjust authorization button */
  .swagger-ui .auth-wrapper .authorize {
    background: var(--primary-color);
    color: white;
  }
  
  /* Schema section styling */
  .swagger-ui .model-box {
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
  }
  
  /* Response section */
  .swagger-ui .responses-wrapper {
    padding: 1rem;
  }
  
  /* Make it responsive */
  @media (max-width: 768px) {
    .swagger-ui .opblock-summary {
      flex-wrap: wrap;
    }
  }
</style>
```

#### Step 3.3: ReDoc Custom Styling
**File:** `backend/app/templates/redoc_custom.html`

**ReDoc is more theme-friendly out-of-box:**
```html
<script>
  Redoc.init('/api/openapi.json', {
    theme: {
      colors: {
        primary: { main: 'oklch(65.69% 0.196 275.75)' },
        background: { main: 'oklch(100% 0 0)' },
        text: { primary: 'oklch(25.93% 0.016 285.75)' }
      },
      typography: {
        fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        fontSize: '14px',
      },
      sidebar: {
        backgroundColor: 'oklch(98.04% 0.005 286.32)',
      }
    },
    hideDownloadButton: true,
    hideSingleRequestSampleTab: true,
  });
</script>
```

---

### Phase 4: Security & Runtime Considerations

#### Step 4.1: Access Control
**Current State:** API is publicly accessible (no authentication)

**Considerations:**
- **For MVP:** Docs are read-only, no sensitive data exposed → OK to be public
- **Future:** If auth is added to API, sync docs access control

**No action needed for MVP**, but document this decision:
```python
# backend/app/main.py
# Note: API docs are public. If authentication is added to the API,
# consider adding the same auth requirements to /api/docs and /api/redoc
```

#### Step 4.2: CORS Configuration
**Current State:** CORS allows localhost origins

**Required:** Ensure `/api/docs` and `/api/redoc` are accessible from frontend origin

**File:** `backend/app/main.py`

**Verify:**
```python
# Already configured - no changes needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Includes frontend origin
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Step 4.3: Traefik Routing
**Current State:** Traefik routes `/api/*` to backend

**Verify:** `/api/docs` and `/api/redoc` are correctly routed

**File:** `docker-compose.yml` (no changes needed, already configured)

**Testing:**
```bash
# Test from host
curl http://localhost:8080/api/docs  # Should return HTML
curl http://localhost:8080/api/redoc # Should return HTML
curl http://localhost:8080/api/openapi.json # Should return OpenAPI spec
```

#### Step 4.4: OpenAPI Spec Customization
**File:** `backend/app/main.py`

**Add metadata for better docs:**
```python
app = FastAPI(
    title="LibrisLog API",
    description="API for managing your personal book collection with reading states",
    version="1.0.0",
    contact={
        "name": "LibrisLog Support",
        "url": "https://github.com/yourusername/librislog",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None, # Disable default redoc
)
```

**Add tags to routers for better organization:**
```python
# In routers/books.py, import_.py, covers.py
router = APIRouter(prefix="/api/books", tags=["Books"])
router = APIRouter(prefix="/api/import", tags=["Import"])
router = APIRouter(prefix="/api/covers", tags=["Covers"])
```

---

### Phase 5: Testing & Verification

#### Step 5.1: Backend Tests
**File:** `backend/tests/test_docs.py` (new file)

**Test Cases:**
1. **Test custom docs endpoint exists**
   ```python
   def test_custom_docs_endpoint(client):
       response = client.get("/api/docs")
       assert response.status_code == 200
       assert "swagger-ui" in response.text.lower()
   ```

2. **Test custom redoc endpoint exists**
   ```python
   def test_custom_redoc_endpoint(client):
       response = client.get("/api/redoc")
       assert response.status_code == 200
       assert "redoc" in response.text.lower()
   ```

3. **Test OpenAPI spec is accessible**
   ```python
   def test_openapi_json(client):
       response = client.get("/api/openapi.json")
       assert response.status_code == 200
       data = response.json()
       assert data["info"]["title"] == "LibrisLog API"
       assert "paths" in data
   ```

4. **Test custom CSS is injected**
   ```python
   def test_docs_custom_styling(client):
       response = client.get("/api/docs")
       assert response.status_code == 200
       assert "topbar" in response.text  # Custom CSS references
       assert "DaisyUI" in response.text or "font-family" in response.text
   ```

5. **Test default docs are disabled**
   ```python
   def test_default_docs_disabled(client):
       response = client.get("/docs")  # Default location
       assert response.status_code == 404
   ```

#### Step 5.2: Frontend Tests
**Approach:** Manual testing (Playwright automation optional for future)

**Test Checklist:**
- [ ] Settings page loads without errors
- [ ] API docs card is visible
- [ ] Toggle between Swagger UI and ReDoc works
- [ ] Iframe loads and displays documentation
- [ ] Loading spinner appears and disappears
- [ ] Iframe is responsive (check mobile viewport)
- [ ] Styling matches app theme (colors, fonts, spacing)
- [ ] "Try it out" functionality works in Swagger UI
- [ ] Language switching doesn't break iframe
- [ ] Navigation within docs works (expand/collapse endpoints)

#### Step 5.3: Integration Testing
**Environment:** Docker Compose (production-like)

**Test Steps:**
1. Build and start: `docker-compose up --build`
2. Access frontend: `http://localhost:8080`
3. Navigate to Settings page
4. Verify API docs iframe loads correctly
5. Test "Try it out" with real API calls
6. Verify responses match actual API behavior

**Cross-Browser Testing:**
- Chrome/Chromium ✓
- Firefox ✓
- Safari (if available)
- Mobile browsers (Chrome mobile, Safari iOS)

#### Step 5.4: Performance Testing
**Metrics to Check:**
- Settings page load time (should be < 2s)
- Iframe load time (should be < 3s on good connection)
- Bundle size impact (frontend - should be minimal since iframe)
- Backend response time for `/api/docs` endpoint (should be < 100ms)

**Tools:**
- Chrome DevTools Network tab
- Lighthouse audit
- `docker stats` to monitor resource usage

---

### Phase 6: Documentation & Rollout

#### Step 6.1: Update Project Documentation
**File:** `README.md`

**Add section:**
```markdown
## API Documentation

The LibrisLog API documentation is available in the app:

1. Navigate to **Settings** page
2. Scroll to **API Documentation** section
3. Toggle between **Swagger UI** (interactive) and **ReDoc** (reference)

Direct access (when backend is running):
- Swagger UI: `http://localhost:8080/api/docs`
- ReDoc: `http://localhost:8080/api/redoc`
- OpenAPI Spec: `http://localhost:8080/api/openapi.json`

The documentation is automatically generated from the FastAPI backend and includes:
- All available endpoints
- Request/response schemas
- Interactive "Try it out" feature (Swagger UI only)
```

#### Step 6.2: Add Developer Notes
**File:** `backend/README.md` or `backend/docs/api-customization.md` (new)

**Content:**
```markdown
## API Documentation Customization

### Overview
Custom API docs are served at `/api/docs` (Swagger UI) and `/api/redoc` (ReDoc).
Default FastAPI docs at `/docs` and `/redoc` are disabled.

### Customization
- CSS styling: `app/templates/swagger_custom.html` and `redoc_custom.html`
- Theme colors: Match DaisyUI theme variables in CSS
- OpenAPI metadata: `app/main.py` FastAPI app initialization

### Adding New Endpoints
1. Add router with appropriate tags
2. Use Pydantic models for request/response (auto-documented)
3. Add docstrings to endpoints (appear in docs description)
4. Run `pytest tests/test_docs.py` to verify docs still work

### Future Enhancements
- Dark mode support (detect theme from cookie/query param)
- Self-hosted Swagger UI assets (for offline/air-gapped deployments)
- Authentication-aware docs (hide endpoints based on user role)
```

#### Step 6.3: User-Facing Changelog
**File:** `CHANGELOG.md` or in-app release notes

**Entry:**
```markdown
### Added
- **API Documentation in Settings**: Users can now explore the backend API directly from the Settings page
  - Toggle between Swagger UI (interactive) and ReDoc (reference-style)
  - Visually integrated with app theme
  - Try API endpoints directly from the browser
```

---

## Implementation Checklist

### Backend Changes
- [ ] Disable default FastAPI docs (`docs_url=None`, `redoc_url=None`)
- [ ] Import Swagger UI and ReDoc HTML generators
- [ ] Create `/api/docs` custom endpoint
- [ ] Create `/api/redoc` custom endpoint
- [ ] Create Jinja2 templates for custom CSS injection
- [ ] Add custom CSS matching DaisyUI theme
- [ ] Update FastAPI app metadata (title, description, version, contact)
- [ ] Add tags to existing routers
- [ ] Test custom endpoints locally
- [ ] Write backend tests (`test_docs.py`)
- [ ] Run `pytest` and ensure all tests pass

### Frontend Changes
- [ ] Update `settings/+page.svelte` with API docs card
- [ ] Add toggle for Swagger UI / ReDoc
- [ ] Implement iframe embedding with loading state
- [ ] Style card to match existing settings cards
- [ ] Add translations to `en.json`
- [ ] Add translations to `de.json`
- [ ] Test settings page in browser
- [ ] Test responsive design (mobile viewport)
- [ ] Verify iframe loads correctly in Docker environment

### Documentation & Testing
- [ ] Update `README.md` with API docs section
- [ ] Create backend API customization docs
- [ ] Add changelog entry
- [ ] Manual testing checklist completed
- [ ] Cross-browser testing completed
- [ ] Integration testing in Docker Compose
- [ ] Performance verification (load times)

### Deployment Verification
- [ ] Build Docker images: `docker-compose build`
- [ ] Start services: `docker-compose up`
- [ ] Verify Traefik routing: `curl http://localhost:8080/api/docs`
- [ ] Access frontend settings page: `http://localhost:8080/settings`
- [ ] Test API docs in production-like environment
- [ ] Check logs for errors: `docker-compose logs backend`

---

## Alternative Approaches for Future Consideration

### 1. Self-Hosted Swagger UI Assets
**When:** For air-gapped deployments or offline functionality

**How:**
- Download Swagger UI distribution from npm/CDN
- Place in `backend/static/swagger-ui/`
- Mount StaticFiles in FastAPI
- Update `swagger_js_url` and `swagger_css_url` to point to local files

**Reference:** FastAPI docs on [Custom Docs UI Assets](https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/)

### 2. Deep Integration with Svelte Component
**When:** Need more control over docs UI or want to embed docs elsewhere in app

**How:**
- Install `swagger-ui-react` or `swagger-ui-dist` npm package
- Create Svelte wrapper component
- Load OpenAPI spec from `/api/openapi.json`
- Initialize SwaggerUI programmatically

**Pros:** No iframe, seamless integration  
**Cons:** Larger bundle size, more complex state management

### 3. Authentication-Aware Docs
**When:** API gains authentication/authorization

**How:**
- Add JWT/session auth to docs endpoints
- Configure Swagger UI `persistAuthorization: true`
- Add "Authorize" button configuration with security schemes
- Hide endpoints based on user role/permissions

### 4. API Playground / Postman Collection
**When:** Users want to save/export API requests

**How:**
- Generate Postman collection from OpenAPI spec
- Offer download link in settings
- Consider embedding Postman-like UI (e.g., Hoppscotch)

---

## Risk Assessment

### Low Risk
- ✅ Iframe not loading: Fallback to external link
- ✅ Styling mismatches: Acceptable for MVP, can iterate
- ✅ CORS issues: Already configured correctly

### Medium Risk
- ⚠️ **Performance impact**: Swagger UI is heavy; iframe loading could be slow
  - **Mitigation**: Use CDN-hosted assets, add loading indicator, consider lazy-loading
- ⚠️ **Mobile UX**: Iframe scrolling on mobile can be awkward
  - **Mitigation**: Set appropriate iframe height, test on devices

### High Risk
- 🚨 **Security**: Exposing API docs could reveal internal details
  - **Mitigation**: Review OpenAPI spec for sensitive data (db schema, internal endpoints). For MVP, API is simple and public-facing, so low concern. Document for future.

---

## Estimated Effort

| Phase | Estimated Time |
|-------|----------------|
| Backend Customization | 2-3 hours |
| Frontend Integration | 2-3 hours |
| Styling & Theme Integration | 2-4 hours |
| Testing & Verification | 1-2 hours |
| Documentation | 1 hour |
| **Total** | **8-13 hours** |

---

## Dependencies & Prerequisites

### Backend
- FastAPI >= 0.100 (for `get_swagger_ui_html`, `get_redoc_html`)
- Jinja2 (for custom HTML templates) - optional, can use string formatting
- Running backend server for local testing

### Frontend
- Access to `/api/docs` and `/api/redoc` endpoints
- Modern browser with iframe support
- i18n system functioning

### Environment
- Docker Compose for integration testing
- Traefik routing configured (already done)

---

## Success Criteria

### Must Have (MVP)
- ✅ API docs accessible from Settings page
- ✅ Toggle between Swagger UI and ReDoc
- ✅ Docs load successfully in iframe
- ✅ Basic theme matching (colors, fonts)
- ✅ Works in Docker/Traefik environment
- ✅ Translations added for EN and DE
- ✅ No console errors on settings page

### Nice to Have (Future Enhancements)
- 🔲 Collapsible docs section (reduce visual clutter)
- 🔲 Dark mode support
- 🔲 Self-hosted Swagger UI assets (offline functionality)
- 🔲 Deeper Svelte integration (no iframe)
- 🔲 API authentication/authorization documentation

### Out of Scope
- ❌ GraphQL or alternative API paradigms
- ❌ API versioning in docs (v1, v2, etc.)
- ❌ Multi-language API docs (EN only for now)
- ❌ API mocking/sandbox environment

---

## Follow-Up Questions Before Implementation

1. **Preference for documentation style?**
   - Default to Swagger UI, or ReDoc, or show both with toggle?
   - **Recommendation:** Default to Swagger UI (more interactive), toggle to ReDoc

2. **Collapsible or always visible?**
   - Should API docs section be collapsed by default to reduce clutter?
   - **Recommendation:** Expanded by default (users navigated to settings intentionally)

3. **Self-hosted vs CDN assets?**
   - Use CDN (jsdelivr) for Swagger UI/ReDoc JS/CSS, or self-host for offline?
   - **Recommendation:** CDN for MVP (simpler), document self-hosting for future

4. **Security considerations?**
   - Any concerns about exposing API structure to end users?
   - **Recommendation:** OK for MVP (API is simple), revisit if sensitive endpoints added

5. **Future API authentication?**
   - If auth is planned, should docs reflect this now (placeholders)?
   - **Recommendation:** No need for MVP, handle when auth is implemented

---

## Recommendation Summary

**Proceed with Hybrid Approach (Option B + Option A):**

1. **Backend**: Customize `/api/docs` and `/api/redoc` with theme-matched CSS
2. **Frontend**: Embed in iframe within DaisyUI card on settings page
3. **Toggle**: Allow users to switch between Swagger UI and ReDoc
4. **Testing**: Comprehensive manual testing + automated backend tests
5. **Documentation**: Update README and add developer notes

**Next Steps:**
- Review this plan
- Confirm approach and preferences (questions above)
- Begin implementation with Phase 1 (Backend Customization)

---

## Plan Feedback Request

**Please choose one of the following:**

1. **✅ Approve Plan** - "I'm fine with this plan, please start implementation"
2. **✏️ Request Changes** - "Plan needs changes" (please specify what to adjust)
3. **❌ Decline Plan** - "Thanks, but don't implement this feature"

After your feedback, I can proceed accordingly.
