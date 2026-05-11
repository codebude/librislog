# API Documentation in Settings - Summary

**Feature ID:** 20  
**Status:** Planning  
**Estimated Effort:** 8-13 hours  
**Complexity:** Medium

## Goal
Make FastAPI-generated API documentation (Swagger UI / ReDoc) accessible from the Settings page, with visual integration matching the app's look and feel.

## Recommended Approach
**Hybrid: Custom Backend Endpoints + Frontend Iframe Embedding**

### Backend (Phase 1)
- Disable default FastAPI docs at `/docs` and `/redoc`
- Create custom endpoints at `/api/docs` and `/api/redoc`
- Inject custom CSS matching DaisyUI theme (colors, fonts, spacing)
- Add OpenAPI metadata (title, description, tags)

### Frontend (Phase 2)
- Add new card section to Settings page (`settings/+page.svelte`)
- Embed iframe pointing to custom docs endpoints
- Add toggle to switch between Swagger UI and ReDoc
- Add loading indicator and responsive styling
- Add i18n translations (EN, DE)

### Styling (Phase 3)
- Match DaisyUI theme colors (base-100, base-200, primary)
- Hide Swagger UI branding/topbar
- Adjust fonts to system font stack
- Ensure mobile responsiveness

### Security & Runtime (Phase 4)
- Verify CORS configuration (already OK)
- Confirm Traefik routing works for `/api/docs`
- Document access control decisions (docs are public for MVP)

### Testing (Phase 5)
- Backend: Automated tests for custom endpoints (`test_docs.py`)
- Frontend: Manual testing checklist (loading, toggling, styling)
- Integration: Docker Compose environment testing
- Performance: Verify load times < 3s

### Documentation (Phase 6)
- Update README with API docs section
- Add developer notes on customization
- Update changelog

## Key Files Modified

### Backend
- `backend/app/main.py` - Custom docs endpoints, disable defaults
- `backend/app/templates/swagger_custom.html` - Custom CSS (new)
- `backend/app/templates/redoc_custom.html` - Custom CSS (new)
- `backend/tests/test_docs.py` - Tests for docs endpoints (new)

### Frontend
- `frontend/src/routes/settings/+page.svelte` - Add docs card with iframe
- `frontend/src/lib/i18n/locales/en.json` - Add translations
- `frontend/src/lib/i18n/locales/de.json` - Add translations

### Documentation
- `README.md` - Add API docs access instructions
- `backend/docs/api-customization.md` - Developer guide (new)

## Implementation Phases

1. **Backend Customization** (2-3h)
   - Custom docs endpoints with theme CSS
   
2. **Frontend Integration** (2-3h)
   - Settings page UI with iframe embedding
   
3. **Styling & Theme** (2-4h)
   - CSS customization, responsive design
   
4. **Security & Runtime** (included in above)
   - CORS, Traefik verification
   
5. **Testing** (1-2h)
   - Automated + manual testing
   
6. **Documentation** (1h)
   - README, developer notes, changelog

## Success Criteria (MVP)
- ✅ API docs accessible from Settings page
- ✅ Toggle between Swagger UI and ReDoc works
- ✅ Docs visually match app theme (colors, fonts)
- ✅ Works in Docker/Traefik production environment
- ✅ No console errors, responsive on mobile
- ✅ Translations added for EN and DE

## Alternative Approaches Considered

| Option | Pros | Cons | Complexity |
|--------|------|------|------------|
| **A: Embedded iframe** | Simple, no backend changes | Limited styling control | Low |
| **B: Custom styled endpoint** | Good theme integration, native functionality | Requires backend changes | Medium ⭐ |
| **C: In-app Svelte component** | Deep integration, full control | Large bundle size, complex | High |
| **D: External link** | Simplest | Minimal integration, jarring UX | Very Low |

**Selected: Hybrid of B + A** (custom endpoint + iframe) - balances integration with simplicity

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Performance impact (slow loading) | Medium | Use CDN assets, add loading indicator |
| Mobile iframe UX issues | Medium | Test on devices, set appropriate height |
| Security (exposing API structure) | Low | Review OpenAPI spec, document for future |

## Future Enhancements (Out of Scope for MVP)
- 🔲 Collapsible docs section
- 🔲 Dark mode support
- 🔲 Self-hosted Swagger UI assets (offline)
- 🔲 Authentication-aware docs
- 🔲 Deeper Svelte integration (no iframe)

## Questions Before Implementation

1. **Default documentation style?** Swagger UI (interactive) or ReDoc (reference)?  
   → Recommend: Swagger UI default, with toggle

2. **Collapsible or always visible?** Reduce clutter vs immediate access?  
   → Recommend: Expanded by default

3. **CDN vs self-hosted assets?** Online dependency vs offline capability?  
   → Recommend: CDN for MVP, document self-hosting option

4. **Security concerns?** OK to expose API structure to users?  
   → Recommend: OK for MVP (simple public API)

## Next Steps

**Please provide feedback:**
1. **✅ Approve Plan** - "I'm fine with this plan, please start implementation"
2. **✏️ Request Changes** - "Plan needs changes" (specify what to adjust)
3. **❌ Decline Plan** - "Thanks, but don't implement this feature"

After approval, implementation will proceed with Phase 1 (Backend Customization).
