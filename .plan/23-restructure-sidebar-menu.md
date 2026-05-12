# Plan: Restructure Sidebar Menu with Library View

## Overview

Restructure the left sidebar menu to consolidate book list navigation into a unified "Library" view with tab-based navigation between reading statuses (Want to Read, Reading, Read, Did Not Finish). This will simplify the navigation structure and improve the user experience by reducing redundant UI elements.

**Goal**: 
- Remove the "Add Book" button from the sidebar (it's already available in the page header)
- Replace individual reading status links with a single "Library" menu entry
- Create a Library page with tab-based navigation for switching between reading statuses
- Maintain all existing functionality while improving UI consistency
- Ensure comprehensive test coverage including Playwright E2E tests

---

## Current State Analysis

### Layout Structure
**File**: `frontend/src/routes/+layout.svelte`

Current sidebar navigation (lines 73-85):
```typescript
const NAV_ITEMS = $derived.by(() => {
    const items = [
        { href: '/?status=want_to_read', labelKey: 'nav.want_to_read', icon: '📚' },
        { href: '/?status=currently_reading', labelKey: 'nav.currently_reading', icon: '📖' },
        { href: '/?status=read', labelKey: 'nav.read', icon: '✓' },
        { href: '/?status=did_not_finish', labelKey: 'nav.did_not_finish', icon: '❌' },
        { href: '/settings', labelKey: 'app.settings', icon: '⚙️' }
    ];
    if ($currentUser?.role === 'admin') {
        items.push({ href: '/admin', labelKey: 'admin.title', icon: '🛠️' });
    }
    return items;
});
```

Current sidebar structure includes:
- Desktop sidebar (lines 133-146): Shows nav items + "Add Book" button at bottom
- Mobile bottom tab bar (lines 163-174): Shows same nav items
- Mobile header (lines 151-156): Shows app title + "Add" button

### Home Page Structure
**File**: `frontend/src/routes/+page.svelte`

Current implementation:
- Uses URL search param `?status=<reading_status>` to determine active tab
- Already has inline "Add Book" button in page header (line 137-139)
- Book list view with filtering, sorting, and search
- State management using Svelte 5 runes
- Background syncing support

### Translation Files
**Files**: 
- `frontend/src/lib/i18n/locales/en.json`
- `frontend/src/lib/i18n/locales/de.json`

Current nav translations exist for individual status links but no "Library" translation yet.

---

## Problem Statement

1. **Redundant UI Elements**: "Add Book" button appears in both sidebar and page header
2. **Cluttered Navigation**: Four separate status links take up significant sidebar space
3. **Inconsistent Patterns**: Other apps typically use a single "Library" or "Books" entry with sub-navigation
4. **Mobile UX**: Bottom tab bar has many small items that could be consolidated
5. **Scalability**: Adding more navigation items would further clutter the sidebar

---

## Implementation Plan

### Phase 1: Create New Library View with Tab Navigation

#### 1.1 Create Library Route Structure

**New File**: `frontend/src/routes/library/+page.svelte`

This will be the new unified Library view that replaces the current homepage (`+page.svelte`) book list functionality.

**Implementation Details**:
```svelte
<script lang="ts">
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import type { Book, ReadingStatus, SortField, SortOrder } from '$lib/types';
    import { api } from '$lib/api';
    import { shouldShowActionToast } from '$lib/errors';
    import { _ } from '$lib/i18n';
    import { toasts } from '$lib/toasts';
    import BookCard from '$lib/components/BookCard.svelte';
    import BookDrawer from '$lib/components/BookDrawer.svelte';
    import SearchBar from '$lib/components/SearchBar.svelte';
    import AddBookModal from '$lib/components/AddBookModal.svelte';

    // Tab state from URL param, defaulting to want_to_read
    let activeStatus = $derived<ReadingStatus>(
        ($page.url.searchParams.get('status') as ReadingStatus) ?? 'want_to_read'
    );

    // ... rest of the book list logic (similar to current +page.svelte)
    
    function changeTab(status: ReadingStatus) {
        goto(`/library?status=${status}`);
    }

    const TABS = [
        { status: 'want_to_read', labelKey: 'status.want_to_read', icon: '📚' },
        { status: 'currently_reading', labelKey: 'status.currently_reading', icon: '📖' },
        { status: 'read', labelKey: 'status.read', icon: '✓' },
        { status: 'did_not_finish', labelKey: 'status.did_not_finish', icon: '❌' }
    ];
</script>

<div class="flex flex-col gap-4">
    <!-- Tab navigation using DaisyUI tabs -->
    <div role="tablist" class="tabs tabs-boxed bg-base-100">
        {#each TABS as tab}
            <button
                role="tab"
                class="tab {activeStatus === tab.status ? 'tab-active' : ''}"
                onclick={() => changeTab(tab.status)}
            >
                <span class="mr-1">{tab.icon}</span>
                {$_(tab.labelKey)}
            </button>
        {/each}
    </div>

    <!-- Header with search, filters, and Add Book button -->
    <div class="flex flex-col sm:flex-row sm:items-center gap-3">
        <h1 class="text-xl font-bold">{$_(STATUS_LABEL_KEYS[activeStatus])}</h1>
        {#if syncing}
            <span class="text-xs text-base-content/60 inline-flex items-center gap-1">
                <span class="loading loading-spinner loading-xs"></span>
                {$_('common.syncing')}
            </span>
        {/if}
        <!-- Search, sorting controls, Add Book button (existing logic) -->
    </div>

    <!-- Book grid (existing logic) -->
</div>
```

**Key Design Decisions**:
- Use DaisyUI `tabs-boxed` component for consistent styling
- Tabs positioned at the top of the content area, above the book list
- URL structure: `/library?status=<reading_status>` 
- Maintain all existing functionality: search, sorting, filtering, background sync
- Keep "Add Book" button in page header (consistent with current +page.svelte)

#### 1.2 Create Route Redirect

**New File**: `frontend/src/routes/+page.svelte`

Transform the current homepage into a redirect to the Library:

```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';

    onMount(() => {
        const status = $page.url.searchParams.get('status') ?? 'want_to_read';
        goto(`/library?status=${status}`, { replaceState: true });
    });
</script>

<div class="min-h-screen bg-base-200 flex items-center justify-center">
    <span class="loading loading-spinner loading-lg"></span>
</div>
```

**Rationale**: Redirect root to `/library` to maintain backward compatibility with existing bookmarks/links and ensure smooth transition.

---

### Phase 2: Update Sidebar Navigation

#### 2.1 Modify Layout Navigation

**File**: `frontend/src/routes/+layout.svelte`

**Changes**:

1. **Remove individual status links** (lines 75-78)
2. **Add single Library link**
3. **Remove "Add Book" button from sidebar** (line 145)
4. **Keep mobile "Add" button in header** (line 154)

```typescript
const NAV_ITEMS = $derived.by(() => {
    const items = [
        { href: '/library', labelKey: 'nav.library', icon: '📚' },  // New unified entry
        { href: '/settings', labelKey: 'app.settings', icon: '⚙️' }
    ];
    if ($currentUser?.role === 'admin') {
        items.push({ href: '/admin', labelKey: 'admin.title', icon: '🛠️' });
    }
    return items;
});
```

**Updated Desktop Sidebar** (lines 133-146):
```svelte
<aside class="hidden md:flex flex-col w-56 bg-base-100 shadow-md fixed top-0 left-0 h-full z-30 p-4 gap-4">
    <div class="text-xl font-bold tracking-tight py-2 px-1">{$_('app.title')}</div>
    <nav class="flex flex-col gap-1 flex-1">
        {#each NAV_ITEMS as item}
            <a
                href={item.href}
                class="btn btn-ghost btn-sm justify-start gap-2 font-normal"
            >
                <span>{item.icon}</span>{$_(item.labelKey)}
            </a>
        {/each}
    </nav>
    <!-- Remove: <button class="btn btn-primary btn-sm" ...>+ {$_('app.addBook')}</button> -->
</aside>
```

**Updated Mobile Bottom Tab Bar** (lines 164-174):
```svelte
<nav class="md:hidden fixed bottom-0 left-0 right-0 bg-base-100 border-t border-base-200 z-20 flex">
    {#each NAV_ITEMS as item}
        <a
            href={item.href}
            class="flex flex-col items-center justify-center flex-1 py-2 text-xs gap-0.5 text-base-content/60 hover:text-base-content"
        >
            <span class="text-lg leading-none">{item.icon}</span>
            <span>{$_(item.labelKey)}</span>
        </a>
    {/each}
</nav>
```

#### 2.2 Update Page Title Logic

**File**: `frontend/src/routes/+layout.svelte` (lines 94-116)

Add handling for `/library` route:

```typescript
function pageTitle() {
    if (!i18nReady) return 'LibrisLog';

    if ($page.url.pathname.startsWith('/library')) {
        return `${$_('app.title')} - ${$_('nav.library')}`;
    }

    if ($page.url.pathname.startsWith('/settings')) {
        return `${$_('app.title')} - ${$_('settings.title')}`;
    }

    // ... rest of existing logic
}
```

---

### Phase 3: Update Translations

#### 3.1 English Translations

**File**: `frontend/src/lib/i18n/locales/en.json`

Add new translation key in the `nav` section:

```json
{
  "nav": {
    "library": "Library",
    "want_to_read": "Want to Read",
    "currently_reading": "Reading",
    "read": "Read",
    "did_not_finish": "Did Not Finish"
  }
}
```

**Note**: Keep the existing status translations as they're still used within the Library tabs.

#### 3.2 German Translations

**File**: `frontend/src/lib/i18n/locales/de.json`

Add German translation:

```json
{
  "nav": {
    "library": "Bibliothek",
    "want_to_read": "Möchte lesen",
    "currently_reading": "Lese gerade",
    "read": "Gelesen",
    "did_not_finish": "Nicht beendet"
  }
}
```

---

### Phase 4: Testing Strategy

#### 4.1 Unit Tests

**New File**: `frontend/src/routes/library/+page.test.ts`

Test the Library component in isolation:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import { page } from '$app/stores';
import LibraryPage from './+page.svelte';

vi.mock('$app/stores', () => ({
    page: {
        subscribe: vi.fn()
    }
}));

vi.mock('$lib/api', () => ({
    api: {
        books: {
            list: vi.fn().mockResolvedValue([])
        }
    }
}));

describe('Library Page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should render tab navigation', () => {
        render(LibraryPage);
        expect(screen.getByRole('tablist')).toBeInTheDocument();
        expect(screen.getByText('Want to Read')).toBeInTheDocument();
        expect(screen.getByText('Reading')).toBeInTheDocument();
        expect(screen.getByText('Read')).toBeInTheDocument();
        expect(screen.getByText('Did Not Finish')).toBeInTheDocument();
    });

    it('should activate the correct tab based on URL param', () => {
        // Mock page store with status=currently_reading
        const mockPage = {
            url: new URL('http://localhost/library?status=currently_reading')
        };
        // Test that the "Reading" tab has tab-active class
    });

    it('should switch tabs when clicked', async () => {
        // Render component
        // Click "Read" tab
        // Verify navigation was triggered with correct URL
    });

    it('should fetch books for the active status', () => {
        // Verify api.books.list is called with correct status filter
    });
});
```

**Test Coverage**:
- Tab rendering
- Tab activation based on URL
- Tab switching navigation
- Book list rendering
- Search functionality
- Sort/filter controls
- Add book button visibility

#### 4.2 Integration Tests

**New File**: `frontend/src/lib/components/sidebar.test.ts`

Test sidebar navigation updates:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import Layout from '../../routes/+layout.svelte';

vi.mock('$app/stores', () => ({
    page: {
        subscribe: vi.fn()
    }
}));

describe('Sidebar Navigation', () => {
    it('should show Library link instead of individual status links', () => {
        render(Layout);
        
        // Should have Library link
        expect(screen.getByText('Library')).toBeInTheDocument();
        
        // Should NOT have individual status links in sidebar
        expect(screen.queryByText('Want to Read')).not.toBeInTheDocument();
        expect(screen.queryByText('Reading')).not.toBeInTheDocument();
    });

    it('should not show Add Book button in sidebar', () => {
        // Check that sidebar doesn't contain "Add Book" button
    });

    it('should show Add button in mobile header', () => {
        // Mobile viewport test
    });
});
```

#### 4.3 E2E Tests with Playwright

**New File**: `e2e/library-navigation.spec.ts`

Comprehensive end-to-end tests covering the full user journey:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Library Navigation', () => {
    test.beforeEach(async ({ page }) => {
        // Login
        await page.goto('/login');
        // Perform login...
        await expect(page).toHaveURL(/\/library/);
    });

    test('should show Library in sidebar instead of individual status links', async ({ page }) => {
        // Desktop view
        await page.setViewportSize({ width: 1280, height: 720 });
        
        const sidebar = page.locator('aside');
        await expect(sidebar.getByText('Library')).toBeVisible();
        
        // Individual status links should NOT be in sidebar
        await expect(sidebar.getByText('Want to Read')).not.toBeVisible();
        await expect(sidebar.getByText('Reading')).not.toBeVisible();
        await expect(sidebar.getByText('Read')).not.toBeVisible();
        await expect(sidebar.getByText('Did Not Finish')).not.toBeVisible();
    });

    test('should not show Add Book button in sidebar', async ({ page }) => {
        await page.setViewportSize({ width: 1280, height: 720 });
        
        const sidebar = page.locator('aside');
        await expect(sidebar.getByRole('button', { name: /add book/i })).not.toBeVisible();
    });

    test('should show tab navigation on Library page', async ({ page }) => {
        await page.goto('/library');
        
        const tablist = page.getByRole('tablist');
        await expect(tablist).toBeVisible();
        
        await expect(page.getByRole('tab', { name: /want to read/i })).toBeVisible();
        await expect(page.getByRole('tab', { name: /reading/i })).toBeVisible();
        await expect(page.getByRole('tab', { name: /read/i })).toBeVisible();
        await expect(page.getByRole('tab', { name: /did not finish/i })).toBeVisible();
    });

    test('should activate correct tab based on URL param', async ({ page }) => {
        await page.goto('/library?status=currently_reading');
        
        const readingTab = page.getByRole('tab', { name: /reading/i });
        await expect(readingTab).toHaveClass(/tab-active/);
    });

    test('should switch tabs and update URL', async ({ page }) => {
        await page.goto('/library?status=want_to_read');
        
        // Click "Read" tab
        const readTab = page.getByRole('tab', { name: /^read$/i });
        await readTab.click();
        
        await expect(page).toHaveURL(/\/library\?status=read/);
        await expect(readTab).toHaveClass(/tab-active/);
    });

    test('should show Add Book button in page header', async ({ page }) => {
        await page.goto('/library');
        
        const addBookBtn = page.getByRole('button', { name: /add book/i });
        await expect(addBookBtn).toBeVisible();
    });

    test('should add book and see it in the correct tab', async ({ page }) => {
        await page.goto('/library?status=want_to_read');
        
        // Click Add Book button
        await page.getByRole('button', { name: /add book/i }).click();
        
        // Fill form
        await page.getByLabel('Title').fill('Test Book');
        await page.getByLabel('Author').fill('Test Author');
        
        // Select status "Currently Reading"
        await page.getByLabel('Status').selectOption('currently_reading');
        
        // Submit
        await page.getByRole('button', { name: /save|add/i }).click();
        
        // Should switch to "Reading" tab automatically or see book there
        await page.goto('/library?status=currently_reading');
        await expect(page.getByText('Test Book')).toBeVisible();
    });

    test('mobile: should show Library in bottom tab bar', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        
        const bottomNav = page.locator('nav').last();
        await expect(bottomNav.getByText('Library')).toBeVisible();
        
        // Should NOT show individual status links
        await expect(bottomNav.getByText('Want to Read')).not.toBeVisible();
    });

    test('mobile: should show Add button in header', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        
        await page.goto('/library');
        const header = page.locator('header');
        await expect(header.getByRole('button', { name: /add/i })).toBeVisible();
    });

    test('should navigate from Settings back to Library', async ({ page }) => {
        await page.goto('/settings');
        
        const sidebar = page.locator('aside');
        await sidebar.getByText('Library').click();
        
        await expect(page).toHaveURL(/\/library/);
    });

    test('should preserve tab selection when navigating away and back', async ({ page }) => {
        await page.goto('/library?status=read');
        
        // Navigate to Settings
        await page.goto('/settings');
        
        // Navigate back using browser back button
        await page.goBack();
        
        // Should still be on "Read" tab
        await expect(page).toHaveURL(/\/library\?status=read/);
        await expect(page.getByRole('tab', { name: /^read$/i })).toHaveClass(/tab-active/);
    });

    test('should redirect from root to Library', async ({ page }) => {
        await page.goto('/');
        
        // Should redirect to /library
        await expect(page).toHaveURL(/\/library/);
    });

    test('should maintain status param when redirecting from root', async ({ page }) => {
        await page.goto('/?status=currently_reading');
        
        // Should redirect to /library with same status
        await expect(page).toHaveURL(/\/library\?status=currently_reading/);
    });

    test('visual regression: sidebar should look correct', async ({ page }) => {
        await page.goto('/library');
        
        const sidebar = page.locator('aside');
        await expect(sidebar).toHaveScreenshot('sidebar-library.png');
    });

    test('visual regression: Library page with tabs', async ({ page }) => {
        await page.goto('/library');
        
        await expect(page).toHaveScreenshot('library-page.png', {
            fullPage: true
        });
    });
});
```

**Test Scenarios Covered**:
1. ✅ Sidebar shows "Library" instead of individual status links
2. ✅ Sidebar does NOT show "Add Book" button
3. ✅ Library page shows tab navigation
4. ✅ Correct tab is activated based on URL param
5. ✅ Clicking tabs navigates and updates URL
6. ✅ Add Book button is visible in page header
7. ✅ Adding a book updates the correct tab/list
8. ✅ Mobile bottom tab bar shows Library
9. ✅ Mobile header shows Add button
10. ✅ Navigation between pages works correctly
11. ✅ Tab selection is preserved across navigation
12. ✅ Root URL redirects to Library
13. ✅ Status param is preserved during redirect
14. ✅ Visual regression testing for UI consistency

#### 4.4 Playwright Configuration

**New File**: `playwright.config.ts`

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: 'html',
    
    use: {
        baseURL: 'http://localhost:5173',
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
    },

    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
        {
            name: 'firefox',
            use: { ...devices['Desktop Firefox'] },
        },
        {
            name: 'webkit',
            use: { ...devices['Desktop Safari'] },
        },
        {
            name: 'Mobile Chrome',
            use: { ...devices['Pixel 5'] },
        },
        {
            name: 'Mobile Safari',
            use: { ...devices['iPhone 12'] },
        },
    ],

    webServer: {
        command: 'npm run dev',
        url: 'http://localhost:5173',
        reuseExistingServer: !process.env.CI,
    },
});
```

**Package.json Updates**:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:e2e:debug": "playwright test --debug"
  },
  "devDependencies": {
    "@playwright/test": "^1.40.0",
    "@testing-library/svelte": "^4.0.0",
    "vitest": "^4.1.6"
  }
}
```

---

### Phase 5: Documentation & Migration

#### 5.1 Update README

Add section explaining the Library navigation:

```markdown
## Navigation

### Library View

The Library provides a unified view of all your books organized by reading status:

- **Want to Read**: Books you plan to read
- **Reading**: Books you're currently reading  
- **Read**: Books you've finished
- **Did Not Finish**: Books you started but didn't complete

Switch between statuses using the tabs at the top of the Library page.

### Adding Books

Click the "Add Book" button in the page header to add new books either manually or by searching/importing from online sources.
```

#### 5.2 Migration Notes

**Backward Compatibility**:
- Old URLs like `/?status=want_to_read` will redirect to `/library?status=want_to_read`
- Bookmarks and external links will continue to work
- No database migrations needed
- No API changes required

**Breaking Changes**: None (graceful transition)

---

## Implementation Order

1. **Phase 1.1**: Create `/library` route with tab navigation
2. **Phase 1.2**: Create redirect from `/` to `/library`
3. **Phase 2**: Update sidebar navigation in `+layout.svelte`
4. **Phase 3**: Add translations
5. **Phase 4.1**: Write unit tests
6. **Phase 4.2**: Write integration tests
7. **Phase 4.3**: Configure Playwright and write E2E tests
8. **Phase 4.4**: Run full test suite and fix any issues
9. **Phase 5**: Update documentation

---

## Files to Modify

### New Files
- ✅ `frontend/src/routes/library/+page.svelte` - New Library view with tabs
- ✅ `frontend/src/routes/library/+page.test.ts` - Unit tests
- ✅ `frontend/src/lib/components/sidebar.test.ts` - Integration tests
- ✅ `e2e/library-navigation.spec.ts` - E2E tests
- ✅ `playwright.config.ts` - Playwright configuration

### Modified Files
- ✅ `frontend/src/routes/+page.svelte` - Transform to redirect
- ✅ `frontend/src/routes/+layout.svelte` - Update sidebar navigation, remove "Add Book" button
- ✅ `frontend/src/lib/i18n/locales/en.json` - Add "Library" translation
- ✅ `frontend/src/lib/i18n/locales/de.json` - Add "Bibliothek" translation
- ✅ `frontend/package.json` - Add Playwright and test scripts

---

## Testing Checklist

### Manual Testing
- [ ] Desktop: Sidebar shows "Library" link
- [ ] Desktop: Sidebar does NOT show "Add Book" button
- [ ] Desktop: Library page shows tabs
- [ ] Desktop: Clicking tabs switches view and updates URL
- [ ] Desktop: Add Book button in page header works
- [ ] Mobile: Bottom tab bar shows "Library"
- [ ] Mobile: Header shows "Add" button
- [ ] Mobile: Tabs are responsive and usable
- [ ] Navigation: Root URL redirects to /library
- [ ] Navigation: Old URLs with ?status= param redirect correctly
- [ ] Navigation: Browser back/forward works correctly
- [ ] i18n: All labels are translated in English
- [ ] i18n: All labels are translated in German

### Automated Testing
- [ ] Unit tests pass for Library component
- [ ] Integration tests pass for sidebar
- [ ] E2E tests pass on all browsers (Chrome, Firefox, Safari)
- [ ] E2E tests pass on mobile viewports
- [ ] Visual regression tests pass
- [ ] No console errors or warnings
- [ ] Performance: Page loads within acceptable time
- [ ] Accessibility: Keyboard navigation works
- [ ] Accessibility: Screen reader labels are correct

---

## Risk Assessment

### Low Risk
- ✅ Navigation restructuring (URLs remain functional via redirect)
- ✅ Translation additions (non-breaking)
- ✅ UI layout changes (no backend changes)

### Medium Risk
- ⚠️ Mobile responsiveness (need thorough testing on various devices)
- ⚠️ Browser compatibility (test on Safari, Firefox, Chrome)
- ⚠️ User confusion (different navigation pattern)

### Mitigations
- Comprehensive E2E testing across devices and browsers
- Playwright tests for visual regression
- Redirect old URLs to maintain backward compatibility
- Clear documentation of new navigation structure

---

## Success Criteria

1. ✅ Sidebar shows single "Library" entry instead of four status links
2. ✅ "Add Book" button removed from sidebar
3. ✅ Library page has functional tab navigation
4. ✅ All existing functionality preserved (search, sort, filter, add, edit, delete)
5. ✅ Mobile navigation simplified
6. ✅ All unit tests pass
7. ✅ All integration tests pass
8. ✅ All E2E tests pass (desktop + mobile)
9. ✅ No visual regressions
10. ✅ Translations complete for English and German
11. ✅ Documentation updated
12. ✅ No console errors

---

## Alternative Approaches Considered

### Option A: Dropdown Menu in Sidebar
**Description**: Keep individual status links but nest them under a "Library" dropdown

**Pros**:
- Faster access to specific status
- More traditional navigation pattern

**Cons**:
- Requires dropdown component/state management
- Still clutters sidebar
- Mobile experience still cramped

**Decision**: ❌ Rejected - Adds complexity without addressing core issue of sidebar clutter

### Option B: Accordion Menu
**Description**: Use an accordion/collapsible menu for Library sub-items

**Pros**:
- Clear hierarchy
- Can collapse when not needed

**Cons**:
- Requires additional UI state
- Extra click to access status lists
- Accordion may feel old-fashioned

**Decision**: ❌ Rejected - Adds interaction friction

### Option C: Side-by-Side Navigation (Recommended)
**Description**: Single "Library" link with tab-based sub-navigation on the page itself

**Pros**:
- ✅ Clean sidebar with minimal items
- ✅ Tab navigation is familiar and intuitive
- ✅ Reduces cognitive load
- ✅ Works well on mobile
- ✅ Matches pattern used in AddBookModal

**Cons**:
- Requires one extra click to switch status (click Library, then click tab) when navigating from another page
- However, within Library page, tab switching is fast

**Decision**: ✅ **Selected** - Best balance of simplicity, usability, and maintainability

---

## UI/UX Design Considerations

### Tab Layout Design

**Desktop Layout**:
```
┌─────────────────────────────────────────────┐
│  [📚 Want to Read] [📖 Reading] [✓ Read]    │
│  [❌ Did Not Finish]                         │
├─────────────────────────────────────────────┤
│  Title: My Books              [Search...]   │
│  [Smart Sort ☑]  [Sort: Date] [Order: ↓]   │
│                          [+ Add Book]       │
├─────────────────────────────────────────────┤
│  [Book] [Book] [Book] [Book]                │
│  [Book] [Book] [Book] [Book]                │
└─────────────────────────────────────────────┘
```

**Mobile Layout**:
```
┌────────────────┐
│ [📚][📖][✓][❌]│
├────────────────┤
│ My Books       │
│ [Search...]    │
│ [+ Add]        │
├────────────────┤
│ [Book] [Book]  │
│ [Book] [Book]  │
└────────────────┘
```

### Accessibility Features
- Tab navigation via keyboard (Arrow keys, Tab, Enter)
- ARIA roles: `role="tablist"`, `role="tab"`, `aria-selected`
- Focus indicators on tabs
- Screen reader announcements when switching tabs
- High contrast support

---

## Performance Considerations

### Expected Impact
- **Neutral**: Similar number of components rendered
- **Improvement**: Fewer sidebar items means faster initial render
- **Improvement**: URL-based tab state means no additional state management overhead

### Optimizations
- Use Svelte 5 `$derived` for tab state (already reactive)
- Maintain existing background sync strategy
- No additional API calls needed

---

## Future Enhancements

After successful implementation, consider:

1. **Bookmarked/Favorite Filter**: Add a star/favorite system
2. **Custom Lists**: Allow users to create custom reading lists beyond the four default statuses
3. **Library Statistics**: Show counts/stats for each status in tab labels (e.g., "Want to Read (23)")
4. **Drag & Drop**: Allow dragging books between tabs to change status
5. **Keyboard Shortcuts**: Add shortcuts for quick tab switching (e.g., `1-4` keys)

---

## Conclusion

This plan provides a comprehensive approach to restructuring the sidebar menu with a unified Library view. The implementation maintains all existing functionality while improving the user experience through cleaner navigation, reduced UI clutter, and better mobile usability. Extensive testing with Playwright ensures the changes are solid and regression-free.

**Estimated Effort**: 
- Development: 4-6 hours
- Testing: 3-4 hours  
- Total: 7-10 hours

**Priority**: Medium
**Complexity**: Medium
**Risk Level**: Low-Medium
