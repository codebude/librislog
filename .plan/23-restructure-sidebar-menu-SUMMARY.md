# Summary: Restructure Sidebar Menu with Library View

## Goal
Simplify navigation by consolidating four individual reading status links into a single "Library" menu entry with tab-based sub-navigation, and remove the redundant "Add Book" button from the sidebar.

## Key Changes

### 1. Sidebar Navigation
- **Remove**: "Want to Read", "Reading", "Read", "Did Not Finish" individual links
- **Remove**: "Add Book" button at bottom of sidebar
- **Add**: Single "Library" menu entry (📚 icon)
- **Result**: Cleaner, less cluttered sidebar with only 2-3 main items

### 2. New Library View
- **Create**: New `/library` route with tab-based navigation
- **Tabs**: Want to Read | Reading | Read | Did Not Finish
- **URL**: `/library?status=<reading_status>`
- **Features**: All existing functionality (search, sort, filter, add book)
- **Design**: Uses DaisyUI `tabs-boxed` component for consistency

### 3. Homepage Redirect
- **Change**: Root `/` redirects to `/library`
- **Compatibility**: Preserves old `/?status=` URLs via redirect
- **Behavior**: Maintains status param during redirect

### 4. Mobile Experience
- **Bottom Tab Bar**: Shows "Library" instead of four status links
- **Header**: Keeps "Add" button (unchanged)
- **Tabs**: Responsive and touch-friendly on mobile devices

## Files Affected

### New Files (5)
1. `frontend/src/routes/library/+page.svelte` - Library view with tabs
2. `frontend/src/routes/library/+page.test.ts` - Unit tests
3. `frontend/src/lib/components/sidebar.test.ts` - Integration tests
4. `e2e/library-navigation.spec.ts` - E2E tests
5. `playwright.config.ts` - Playwright configuration

### Modified Files (5)
1. `frontend/src/routes/+page.svelte` - Redirect to /library
2. `frontend/src/routes/+layout.svelte` - Update navigation
3. `frontend/src/lib/i18n/locales/en.json` - Add "Library" translation
4. `frontend/src/lib/i18n/locales/de.json` - Add "Bibliothek" translation
5. `frontend/package.json` - Add Playwright dependency

## Implementation Phases

### Phase 1: Create Library View
- Build new `/library` route with tab navigation
- Migrate all book list functionality from current homepage
- Add redirect from `/` to `/library`

### Phase 2: Update Sidebar
- Modify `NAV_ITEMS` to show single "Library" entry
- Remove "Add Book" button from desktop sidebar
- Update mobile bottom tab bar

### Phase 3: Translations
- Add "Library" / "Bibliothek" translations
- Update page title logic

### Phase 4: Comprehensive Testing
- Unit tests for Library component
- Integration tests for sidebar changes
- **Playwright E2E tests** covering:
  - Navigation flow
  - Tab switching
  - Mobile responsiveness
  - Visual regression
  - Backward compatibility

### Phase 5: Documentation
- Update README with new navigation structure
- Add migration notes

## Testing Strategy

### Automated Tests
- ✅ **Unit Tests**: Library component logic
- ✅ **Integration Tests**: Sidebar rendering
- ✅ **E2E Tests (Playwright)**: Full user journeys
  - Desktop navigation
  - Mobile navigation
  - Tab switching
  - Book operations (add/edit/delete)
  - Visual regression
  - Multi-browser (Chrome, Firefox, Safari)

### Manual Testing Checklist
- Desktop sidebar displays correctly
- Mobile bottom bar works
- Tabs switch views properly
- URL updates on tab click
- Add Book button functions
- Translations correct in both languages
- No console errors

## Risk Assessment

**Risk Level**: Low-Medium

**Risks**:
- User confusion from changed navigation pattern
- Mobile responsiveness issues
- Browser compatibility

**Mitigations**:
- Comprehensive Playwright testing on multiple browsers/devices
- Visual regression tests
- Backward-compatible URL redirects
- Clear documentation

## Success Criteria

1. ✅ Sidebar shows "Library" instead of 4 status links
2. ✅ "Add Book" button removed from sidebar (remains in page header)
3. ✅ Functional tab navigation in Library view
4. ✅ All existing features work (search, sort, add, edit, delete)
5. ✅ Mobile navigation simplified
6. ✅ 100% test pass rate (unit + integration + E2E)
7. ✅ No visual regressions
8. ✅ Translations complete
9. ✅ Zero console errors
10. ✅ Documentation updated

## Why This Approach?

**Alternative approaches considered**:
- ❌ Dropdown menu: Adds complexity, still clutters sidebar
- ❌ Accordion menu: Extra friction, feels dated
- ✅ **Tab-based navigation**: Clean, intuitive, mobile-friendly

**Benefits**:
- Reduces sidebar clutter (4 links → 1 link)
- Removes redundant "Add Book" button
- Provides familiar tab pattern (already used in AddBookModal)
- Improves mobile usability
- Maintains all functionality
- Backward compatible

## Estimated Effort

- **Development**: 4-6 hours
- **Testing**: 3-4 hours
- **Total**: 7-10 hours

## Dependencies

- DaisyUI (already installed)
- Playwright (needs installation)
- @testing-library/svelte (needs installation)

## Next Steps

1. Install Playwright: `npm install -D @playwright/test`
2. Install testing library: `npm install -D @testing-library/svelte`
3. Create `/library` route
4. Update sidebar navigation
5. Add translations
6. Write tests (unit → integration → E2E)
7. Run full test suite
8. Update documentation
9. Deploy

---

**Plan Status**: ✅ Ready for Implementation  
**Created**: 2026-05-12  
**Plan File**: `23-restructure-sidebar-menu.md`
