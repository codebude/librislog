# Plan: Dashboard Page Implementation

## Overview

Implement a new Dashboard page as the application's landing page, providing users with an at-a-glance view of their reading activity, quick access to current books, and motivational content.

**Goal**: 
- Create a dashboard as the first page in the sidebar and default landing page
- Display sections for currently reading books, next books to read, and library statistics
- Integrate an optional inspirational quote feature (controllable via environment variable)
- Use DaisyUI components for consistent styling
- Ensure comprehensive test coverage for both frontend and backend

---

## Current State Analysis

### Frontend Structure

**Layout**: `frontend/src/routes/+layout.svelte`
- Current navigation has "Library" as the first menu item (line 75)
- Already implements page title logic and routing
- Uses Svelte 5 with modern reactive patterns ($state, $derived, $effect)

**Library Page**: `frontend/src/routes/library/+page.svelte`
- Implements tab-based navigation for reading statuses
- Already fetches and displays books by status
- Uses DaisyUI components (tabs, cards, buttons)
- Has search, sort, and filter functionality

**Translations**: `frontend/src/lib/i18n/locales/{en,de}.json`
- Structured translation system already in place
- Will need to add dashboard-specific keys

### Backend Structure

**Books Router**: `backend/app/routers/books.py`
- Has `list_books` endpoint (line 66) with filtering by status
- Supports query params: status, q, sort, order, smart_sort
- Returns list of books with full details
- No dedicated statistics endpoint exists yet

**Models**: `backend/app/models.py`
- Book model includes all necessary fields
- Reading statuses: want_to_read, currently_reading, read, did_not_finish
- Has date_added, date_started, date_finished timestamps
- Books are scoped by user_id

**Test Stack**:
- Backend: pytest with TestClient (FastAPI)
- Frontend: Vitest (configured in package.json)
- No Playwright E2E tests currently configured

### Environment Configuration

**File**: `.env.example`
- Uses pattern of feature toggles (e.g., OIDC_ENABLED)
- Will add DASHBOARD_QUOTE_ENABLED for quote feature

---

## Problem Statement

1. **No Landing Page**: Current app redirects root to /library, providing no overview
2. **No Statistics**: Users cannot see aggregate data about their reading habits
3. **Limited Motivation**: No inspirational elements to encourage reading
4. **Navigation Priority**: Dashboard should be the default/first page, not Library

---

## Implementation Plan

### Phase 1: Backend - Statistics Endpoint

#### 1.1 Create Statistics Schema

**New File**: `backend/app/schemas.py` (add to existing file)

```python
class LibraryStats(BaseModel):
    """Library statistics for dashboard."""
    total_books: int
    books_read: int
    books_reading: int
    books_want_to_read: int
    books_did_not_finish: int
    
    class Config:
        from_attributes = True
```

#### 1.2 Create Statistics Endpoint

**File**: `backend/app/routers/books.py` (add new endpoint)

Location: After the `list_books` endpoint (around line 124)

```python
@router.get("/stats", response_model=schemas.LibraryStats)
def get_library_stats(
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> dict:
    """
    Get aggregate statistics about the user's library.
    
    Returns counts of books by reading status and total book count.
    """
    logger.debug("get_library_stats — user_id=%s", current_user.id)
    
    from sqlmodel import func
    
    # Get total count
    total_statement = select(func.count(Book.id)).where(Book.user_id == current_user.id)
    total_books = session.exec(total_statement).one()
    
    # Get counts by status
    stats = {
        "total_books": total_books,
        "books_read": 0,
        "books_reading": 0,
        "books_want_to_read": 0,
        "books_did_not_finish": 0,
    }
    
    for status in ReadingStatus:
        count_statement = select(func.count(Book.id)).where(
            Book.user_id == current_user.id,
            Book.reading_status == status
        )
        count = session.exec(count_statement).one()
        
        if status == ReadingStatus.read:
            stats["books_read"] = count
        elif status == ReadingStatus.currently_reading:
            stats["books_reading"] = count
        elif status == ReadingStatus.want_to_read:
            stats["books_want_to_read"] = count
        elif status == ReadingStatus.did_not_finish:
            stats["books_did_not_finish"] = count
    
    logger.debug("get_library_stats — returning stats: %r", stats)
    return stats
```

**Design Decisions**:
- Returns simple counts for dashboard display
- Uses SQLModel's func.count for efficient queries
- Scoped to current user (via require_user_by_api_key)
- Separate queries per status for clarity and maintainability
- Could be optimized with single GROUP BY query if performance becomes an issue

---

### Phase 2: Frontend - Dashboard Page

#### 2.1 Create Dashboard Route

**New File**: `frontend/src/routes/dashboard/+page.svelte`

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import type { Book } from '$lib/types';
	import { api } from '$lib/api';
	import { shouldShowActionToast } from '$lib/errors';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import BookCard from '$lib/components/BookCard.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';

	interface Quote {
		quote: string;
		author: string;
		tags: string[];
	}

	interface LibraryStats {
		total_books: number;
		books_read: number;
		books_reading: number;
		books_want_to_read: number;
		books_did_not_finish: number;
	}

	let currentlyReading = $state<Book[]>([]);
	let nextToRead = $state<Book[]>([]);
	let stats = $state<LibraryStats | null>(null);
	let quote = $state<Quote | null>(null);
	let loading = $state(true);
	let quoteLoading = $state(false);
	let quoteError = $state(false);
	let selectedBook = $state<Book | null>(null);
	let drawerOpen = $state(false);

	const QUOTE_ENABLED = import.meta.env.PUBLIC_DASHBOARD_QUOTE_ENABLED === 'true';
	const QUOTE_API_URL = 'https://quoteslate.vercel.app/api/quotes/random?maxLength=100&tags=humility';

	async function fetchDashboardData() {
		loading = true;
		try {
			// Fetch currently reading books
			const readingPromise = api.books.list({
				status: 'currently_reading',
				smart_sort: true,
				sort: 'date_added',
				order: 'desc'
			});

			// Fetch next books to read (want_to_read)
			const toReadPromise = api.books.list({
				status: 'want_to_read',
				smart_sort: true,
				sort: 'date_added',
				order: 'asc'
			});

			// Fetch library statistics
			const statsPromise = api.books.getStats();

			const [reading, toRead, libraryStats] = await Promise.all([
				readingPromise,
				toReadPromise,
				statsPromise
			]);

			currentlyReading = reading;
			nextToRead = toRead.slice(0, 5); // Show max 5 books
			stats = libraryStats;
		} catch (e: unknown) {
			const message = e instanceof Error ? e.message : $_('dashboard.loadFailed');
			if (shouldShowActionToast(message)) {
				toasts.add(message, 'error');
			}
		} finally {
			loading = false;
		}
	}

	async function fetchQuote() {
		if (!QUOTE_ENABLED) return;
		
		quoteLoading = true;
		quoteError = false;
		try {
			const response = await fetch(QUOTE_API_URL);
			if (!response.ok) {
				throw new Error('Failed to fetch quote');
			}
			quote = await response.json();
		} catch (e) {
			console.error('Error loading quote:', e);
			quoteError = true;
			quote = null;
		} finally {
			quoteLoading = false;
		}
	}

	onMount(() => {
		void fetchDashboardData();
		if (QUOTE_ENABLED) {
			void fetchQuote();
		}
	});

	function openDrawer(book: Book) {
		selectedBook = book;
		drawerOpen = true;
	}

	function handleSave(updated: Book) {
		// Update in currently reading list
		const readingIndex = currentlyReading.findIndex((b) => b.id === updated.id);
		if (readingIndex !== -1) {
			if (updated.reading_status === 'currently_reading') {
				currentlyReading[readingIndex] = updated;
			} else {
				currentlyReading = currentlyReading.filter((b) => b.id !== updated.id);
			}
		}

		// Update in next to read list
		const toReadIndex = nextToRead.findIndex((b) => b.id === updated.id);
		if (toReadIndex !== -1) {
			if (updated.reading_status === 'want_to_read') {
				nextToRead[toReadIndex] = updated;
			} else {
				nextToRead = nextToRead.filter((b) => b.id !== updated.id);
			}
		}

		// Refresh stats to reflect changes
		void fetchDashboardData();
	}

	function handleDelete(deletedId: number) {
		currentlyReading = currentlyReading.filter((b) => b.id !== deletedId);
		nextToRead = nextToRead.filter((b) => b.id !== deletedId);
		void fetchDashboardData();
	}

	function navigateToLibrary(status?: string) {
		if (status) {
			void goto(`/library?status=${status}`);
		} else {
			void goto('/library');
		}
	}
</script>

<svelte:head>
	<title>{$_('app.title')} - {$_('dashboard.title')}</title>
</svelte:head>

<div class="flex flex-col gap-6 pb-4">
	<div class="flex flex-col gap-2">
		<h1 class="text-2xl md:text-3xl font-bold">{$_('dashboard.welcome')}</h1>
		<p class="text-base-content/70">{$_('dashboard.subtitle')}</p>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else}
		<!-- Quote Section -->
		{#if QUOTE_ENABLED}
			<div class="card bg-gradient-to-br from-primary/10 to-secondary/10 border border-base-300">
				<div class="card-body">
					{#if quoteLoading}
						<div class="flex items-center justify-center py-6">
							<span class="loading loading-spinner loading-md"></span>
						</div>
					{:else if quoteError}
						<div class="text-center py-4 text-base-content/50">
							<p>{$_('dashboard.quoteLoadFailed')}</p>
						</div>
					{:else if quote}
						<figure class="px-4 pt-2">
							<svg class="w-8 h-8 text-primary/30" fill="currentColor" viewBox="0 0 24 24">
								<path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z"/>
							</svg>
						</figure>
						<blockquote class="text-center">
							<p class="text-lg font-medium italic mb-2">"{quote.quote}"</p>
							<footer class="text-sm text-base-content/60">— {quote.author}</footer>
						</blockquote>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Statistics Section -->
		{#if stats}
			<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
				<button
					class="stat bg-base-100 border border-base-300 rounded-lg hover:border-primary/50 transition-colors cursor-pointer"
					onclick={() => navigateToLibrary()}
				>
					<div class="stat-figure text-primary">
						<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
						</svg>
					</div>
					<div class="stat-title">{$_('dashboard.stats.totalBooks')}</div>
					<div class="stat-value text-primary">{stats.total_books}</div>
				</button>

				<button
					class="stat bg-base-100 border border-base-300 rounded-lg hover:border-success/50 transition-colors cursor-pointer"
					onclick={() => navigateToLibrary('read')}
				>
					<div class="stat-figure text-success">
						<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
						</svg>
					</div>
					<div class="stat-title">{$_('dashboard.stats.booksRead')}</div>
					<div class="stat-value text-success">{stats.books_read}</div>
				</button>

				<button
					class="stat bg-base-100 border border-base-300 rounded-lg hover:border-info/50 transition-colors cursor-pointer"
					onclick={() => navigateToLibrary('want_to_read')}
				>
					<div class="stat-figure text-info">
						<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
						</svg>
					</div>
					<div class="stat-title">{$_('dashboard.stats.toRead')}</div>
					<div class="stat-value text-info">{stats.books_want_to_read}</div>
				</button>

				<button
					class="stat bg-base-100 border border-base-300 rounded-lg hover:border-warning/50 transition-colors cursor-pointer"
					onclick={() => navigateToLibrary('currently_reading')}
				>
					<div class="stat-figure text-warning">
						<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
						</svg>
					</div>
					<div class="stat-title">{$_('dashboard.stats.reading')}</div>
					<div class="stat-value text-warning">{stats.books_reading}</div>
				</button>
			</div>
		{/if}

		<!-- Currently Reading Section -->
		<div class="flex flex-col gap-3">
			<div class="flex items-center justify-between">
				<h2 class="text-xl font-semibold flex items-center gap-2">
					<span>📖</span>
					{$_('dashboard.currentlyReading')}
				</h2>
				{#if currentlyReading.length > 0}
					<button
						class="btn btn-sm btn-ghost"
						onclick={() => navigateToLibrary('currently_reading')}
					>
						{$_('dashboard.viewAll')} →
					</button>
				{/if}
			</div>

			{#if currentlyReading.length === 0}
				<div class="card bg-base-100 border border-base-300">
					<div class="card-body text-center py-8">
						<p class="text-base-content/60">{$_('dashboard.noCurrentlyReading')}</p>
						<button
							class="btn btn-primary btn-sm mx-auto mt-2"
							onclick={() => navigateToLibrary('want_to_read')}
						>
							{$_('dashboard.startReading')}
						</button>
					</div>
				</div>
			{:else}
				<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
					{#each currentlyReading as book (book.id)}
						<BookCard {book} onclick={() => openDrawer(book)} />
					{/each}
				</div>
			{/if}
		</div>

		<!-- Next To Read Section -->
		<div class="flex flex-col gap-3">
			<div class="flex items-center justify-between">
				<h2 class="text-xl font-semibold flex items-center gap-2">
					<span>📚</span>
					{$_('dashboard.nextToRead')}
				</h2>
				{#if nextToRead.length > 0}
					<button
						class="btn btn-sm btn-ghost"
						onclick={() => navigateToLibrary('want_to_read')}
					>
						{$_('dashboard.viewAll')} →
					</button>
				{/if}
			</div>

			{#if nextToRead.length === 0}
				<div class="card bg-base-100 border border-base-300">
					<div class="card-body text-center py-8">
						<p class="text-base-content/60">{$_('dashboard.noNextToRead')}</p>
					</div>
				</div>
			{:else}
				<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
					{#each nextToRead as book (book.id)}
						<BookCard {book} onclick={() => openDrawer(book)} />
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

{#if selectedBook}
	<BookDrawer
		book={selectedBook}
		open={drawerOpen}
		onClose={() => {
			drawerOpen = false;
			selectedBook = null;
		}}
		onSave={handleSave}
		onDelete={handleDelete}
	/>
{/if}
```

**Key Design Decisions**:
- Quote API call wrapped in try-catch with error state
- Statistics cards are clickable, navigating to filtered library views
- Shows max 5 books in "Next to Read" section (configurable)
- Uses existing BookCard and BookDrawer components
- Responsive grid layout using DaisyUI utilities
- Environment variable controls quote feature (PUBLIC_DASHBOARD_QUOTE_ENABLED)
- All async operations use proper error handling
- Uses Svelte 5 runes ($state, $derived)

#### 2.2 Update API Client

**File**: `frontend/src/lib/api.ts` (add to existing file)

Add to the books section:

```typescript
export const api = {
	books: {
		// ... existing methods ...
		
		async getStats(): Promise<LibraryStats> {
			const response = await fetch(`${API_BASE}/api/books/stats`, {
				headers: getAuthHeaders(),
			});
			if (!response.ok) {
				throw new Error('Failed to fetch library statistics');
			}
			return response.json();
		},
	},
	// ... rest of api ...
};
```

**Type Definition** (add to `frontend/src/lib/types.ts`):

```typescript
export interface LibraryStats {
	total_books: number;
	books_read: number;
	books_reading: number;
	books_want_to_read: number;
	books_did_not_finish: number;
}
```

---

### Phase 3: Update Navigation & Routing

#### 3.1 Update Sidebar Navigation

**File**: `frontend/src/routes/+layout.svelte`

**Changes**:

Line 73-82: Update NAV_ITEMS to include Dashboard first:

```typescript
const NAV_ITEMS = $derived.by(() => {
	const items = [
		{ href: '/dashboard', labelKey: 'nav.dashboard', icon: '🏠' },  // NEW: Dashboard first
		{ href: '/library', labelKey: 'nav.library', icon: '📚' },
		{ href: '/settings', labelKey: 'app.settings', icon: '⚙️' }
	];
	if ($currentUser?.role === 'admin') {
		items.push({ href: '/admin', labelKey: 'admin.title', icon: '🛠️' });
	}
	return items;
});
```

Line 84-100: Add dashboard to pageTitle function:

```typescript
function pageTitle() {
	if (!i18nReady) return 'LibrisLog';

	if ($page.url.pathname.startsWith('/dashboard')) {
		return `${$_('app.title')} - ${$_('nav.dashboard')}`;
	}

	if ($page.url.pathname.startsWith('/library')) {
		return `${$_('app.title')} - ${$_('nav.library')}`;
	}

	// ... rest of existing logic
}
```

#### 3.2 Update Root Redirect

**File**: `frontend/src/routes/+page.svelte`

Update to redirect to dashboard instead of library:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	onMount(() => {
		goto('/dashboard', { replaceState: true });
	});
</script>

<div class="min-h-screen bg-base-200 flex items-center justify-center">
	<span class="loading loading-spinner loading-lg"></span>
</div>
```

---

### Phase 4: Translations

#### 4.1 English Translations

**File**: `frontend/src/lib/i18n/locales/en.json`

Add new keys in appropriate sections:

```json
{
	"nav": {
		"dashboard": "Dashboard",
		"library": "Library",
		...
	},
	"dashboard": {
		"title": "Dashboard",
		"welcome": "Welcome back!",
		"subtitle": "Here's what's happening with your reading",
		"currentlyReading": "Currently Reading",
		"nextToRead": "Next to Read",
		"viewAll": "View all",
		"startReading": "Start reading from your list",
		"noCurrentlyReading": "No books in progress. Pick one to start!",
		"noNextToRead": "No books in your reading queue.",
		"loadFailed": "Failed to load dashboard data",
		"quoteLoadFailed": "Could not load inspirational quote",
		"stats": {
			"totalBooks": "Total Books",
			"booksRead": "Books Read",
			"toRead": "To Read",
			"reading": "Reading"
		}
	},
	...
}
```

#### 4.2 German Translations

**File**: `frontend/src/lib/i18n/locales/de.json`

```json
{
	"nav": {
		"dashboard": "Dashboard",
		"library": "Bibliothek",
		...
	},
	"dashboard": {
		"title": "Dashboard",
		"welcome": "Willkommen zurück!",
		"subtitle": "So steht es um deine Leseaktivitäten",
		"currentlyReading": "Gerade am Lesen",
		"nextToRead": "Als Nächstes lesen",
		"viewAll": "Alle anzeigen",
		"startReading": "Beginne mit einem Buch aus deiner Liste",
		"noCurrentlyReading": "Keine Bücher in Bearbeitung. Wähle eines aus!",
		"noNextToRead": "Keine Bücher in deiner Leseliste.",
		"loadFailed": "Dashboard-Daten konnten nicht geladen werden",
		"quoteLoadFailed": "Inspirierendes Zitat konnte nicht geladen werden",
		"stats": {
			"totalBooks": "Bücher Gesamt",
			"booksRead": "Gelesene Bücher",
			"toRead": "Zu lesen",
			"reading": "Lese gerade"
		}
	},
	...
}
```

---

### Phase 5: Environment Configuration

#### 5.1 Update Environment Files

**File**: `.env.example`

Add new environment variable at the end:

```bash
# Dashboard settings
DASHBOARD_QUOTE_ENABLED=true     # Enable/disable inspirational quotes on dashboard
```

**File**: `frontend/.env` (for local development, user should create this)

Users should copy from .env.example and configure.

#### 5.2 Build-Time Environment Variables

**File**: `frontend/vite.config.ts` (verify or add if needed)

Ensure PUBLIC_ prefixed variables are exposed:

```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	define: {
		'import.meta.env.PUBLIC_DASHBOARD_QUOTE_ENABLED': JSON.stringify(
			process.env.PUBLIC_DASHBOARD_QUOTE_ENABLED ?? 'true'
		),
	},
});
```

**Note**: SvelteKit automatically exposes `PUBLIC_*` env vars, so explicit definition may not be needed.

---

### Phase 6: Testing Strategy

#### 6.1 Backend Tests

**New File**: `backend/tests/test_dashboard.py`

```python
from fastapi.testclient import TestClient


def test_get_stats_returns_correct_counts(client: TestClient):
    """Test that statistics endpoint returns accurate counts."""
    # Create test books with different statuses
    client.post("/api/books", json={"title": "Book 1", "reading_status": "want_to_read"})
    client.post("/api/books", json={"title": "Book 2", "reading_status": "want_to_read"})
    client.post("/api/books", json={"title": "Book 3", "reading_status": "currently_reading"})
    client.post("/api/books", json={"title": "Book 4", "reading_status": "read"})
    client.post("/api/books", json={"title": "Book 5", "reading_status": "read"})
    client.post("/api/books", json={"title": "Book 6", "reading_status": "did_not_finish"})

    # Fetch statistics
    resp = client.get("/api/books/stats")
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["total_books"] == 6
    assert data["books_want_to_read"] == 2
    assert data["books_reading"] == 1
    assert data["books_read"] == 2
    assert data["books_did_not_finish"] == 1


def test_get_stats_returns_zero_for_empty_library(client: TestClient):
    """Test statistics with no books."""
    resp = client.get("/api/books/stats")
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["total_books"] == 0
    assert data["books_want_to_read"] == 0
    assert data["books_reading"] == 0
    assert data["books_read"] == 0
    assert data["books_did_not_finish"] == 0


def test_get_stats_filters_by_user(client: TestClient, client_user2: TestClient):
    """Test that stats are scoped to the current user."""
    # User 1 creates 3 books
    client.post("/api/books", json={"title": "User1 Book 1", "reading_status": "read"})
    client.post("/api/books", json={"title": "User1 Book 2", "reading_status": "want_to_read"})
    
    # User 2 creates 2 books
    client_user2.post("/api/books", json={"title": "User2 Book 1", "reading_status": "read"})
    
    # User 1 stats should only show their books
    resp = client.get("/api/books/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_books"] == 2
    assert data["books_read"] == 1
    assert data["books_want_to_read"] == 1
    
    # User 2 stats should only show their books
    resp2 = client_user2.get("/api/books/stats")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total_books"] == 1
    assert data2["books_read"] == 1


def test_get_stats_requires_authentication(client_no_auth: TestClient):
    """Test that stats endpoint requires authentication."""
    resp = client_no_auth.get("/api/books/stats")
    assert resp.status_code == 401


def test_stats_updates_when_book_status_changes(client: TestClient):
    """Test that stats reflect status changes."""
    # Create a book
    book_resp = client.post("/api/books", json={
        "title": "Test Book",
        "reading_status": "want_to_read"
    })
    book_id = book_resp.json()["id"]
    
    # Check initial stats
    resp = client.get("/api/books/stats")
    data = resp.json()
    assert data["books_want_to_read"] == 1
    assert data["books_read"] == 0
    
    # Update book status to read
    client.put(f"/api/books/{book_id}", json={"reading_status": "read"})
    
    # Check updated stats
    resp = client.get("/api/books/stats")
    data = resp.json()
    assert data["books_want_to_read"] == 0
    assert data["books_read"] == 1


def test_stats_updates_when_book_deleted(client: TestClient):
    """Test that stats reflect deletions."""
    # Create books
    book1 = client.post("/api/books", json={"title": "Book 1", "reading_status": "read"})
    book2 = client.post("/api/books", json={"title": "Book 2", "reading_status": "read"})
    
    # Check stats
    resp = client.get("/api/books/stats")
    data = resp.json()
    assert data["total_books"] == 2
    assert data["books_read"] == 2
    
    # Delete one book
    book1_id = book1.json()["id"]
    client.delete(f"/api/books/{book1_id}")
    
    # Check updated stats
    resp = client.get("/api/books/stats")
    data = resp.json()
    assert data["total_books"] == 1
    assert data["books_read"] == 1
```

**Test Coverage**:
- ✅ Returns accurate counts for all statuses
- ✅ Handles empty library (all zeros)
- ✅ Scopes data to current user
- ✅ Requires authentication
- ✅ Updates when book status changes
- ✅ Updates when books are deleted

**Notes**: 
- Assumes `client_user2` and `client_no_auth` fixtures exist or need to be created
- Follows existing test patterns from `test_books.py`

#### 6.2 Frontend Unit Tests

**New File**: `frontend/src/routes/dashboard/+page.test.ts`

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import { page } from '$app/stores';
import DashboardPage from './+page.svelte';
import { api } from '$lib/api';

vi.mock('$app/stores', () => ({
	page: {
		subscribe: vi.fn(),
	},
}));

vi.mock('$app/navigation', () => ({
	goto: vi.fn(),
}));

vi.mock('$lib/api', () => ({
	api: {
		books: {
			list: vi.fn(),
			getStats: vi.fn(),
		},
	},
}));

describe('Dashboard Page', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		
		// Mock API responses
		vi.mocked(api.books.list).mockResolvedValue([]);
		vi.mocked(api.books.getStats).mockResolvedValue({
			total_books: 10,
			books_read: 5,
			books_reading: 2,
			books_want_to_read: 2,
			books_did_not_finish: 1,
		});
		
		// Mock fetch for quote API
		global.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => ({
				quote: "Test quote",
				author: "Test Author",
				tags: ["humility"],
			}),
		});
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('should render dashboard with loading state initially', () => {
		render(DashboardPage);
		expect(screen.getByRole('status')).toBeInTheDocument(); // loading spinner
	});

	it('should fetch and display library statistics', async () => {
		render(DashboardPage);
		
		await waitFor(() => {
			expect(api.books.getStats).toHaveBeenCalledOnce();
		});
		
		// Check that stats are displayed
		await waitFor(() => {
			expect(screen.getByText('10')).toBeInTheDocument(); // total books
			expect(screen.getByText('5')).toBeInTheDocument(); // books read
			expect(screen.getByText('2')).toBeInTheDocument(); // want to read
		});
	});

	it('should fetch currently reading books', async () => {
		render(DashboardPage);
		
		await waitFor(() => {
			expect(api.books.list).toHaveBeenCalledWith(
				expect.objectContaining({
					status: 'currently_reading',
					smart_sort: true,
				})
			);
		});
	});

	it('should fetch next to read books', async () => {
		render(DashboardPage);
		
		await waitFor(() => {
			expect(api.books.list).toHaveBeenCalledWith(
				expect.objectContaining({
					status: 'want_to_read',
					smart_sort: true,
				})
			);
		});
	});

	it('should display message when no currently reading books', async () => {
		vi.mocked(api.books.list).mockImplementation((params) => {
			if (params?.status === 'currently_reading') {
				return Promise.resolve([]);
			}
			return Promise.resolve([]);
		});
		
		render(DashboardPage);
		
		await waitFor(() => {
			expect(screen.getByText(/no books in progress/i)).toBeInTheDocument();
		});
	});

	it('should fetch quote when enabled', async () => {
		// Set environment variable
		import.meta.env.PUBLIC_DASHBOARD_QUOTE_ENABLED = 'true';
		
		render(DashboardPage);
		
		await waitFor(() => {
			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('quoteslate.vercel.app')
			);
		});
		
		await waitFor(() => {
			expect(screen.getByText('Test quote')).toBeInTheDocument();
			expect(screen.getByText(/Test Author/)).toBeInTheDocument();
		});
	});

	it('should not fetch quote when disabled', async () => {
		import.meta.env.PUBLIC_DASHBOARD_QUOTE_ENABLED = 'false';
		
		render(DashboardPage);
		
		await waitFor(() => {
			expect(api.books.getStats).toHaveBeenCalled();
		});
		
		expect(global.fetch).not.toHaveBeenCalledWith(
			expect.stringContaining('quoteslate.vercel.app')
		);
	});

	it('should handle quote API failure gracefully', async () => {
		global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
		import.meta.env.PUBLIC_DASHBOARD_QUOTE_ENABLED = 'true';
		
		render(DashboardPage);
		
		await waitFor(() => {
			// Should show error message or hide quote section
			expect(screen.queryByText('Test quote')).not.toBeInTheDocument();
		});
	});

	it('should handle API errors gracefully', async () => {
		vi.mocked(api.books.getStats).mockRejectedValue(new Error('API error'));
		
		render(DashboardPage);
		
		await waitFor(() => {
			// Should show error toast or error state
			// Exact assertion depends on error handling implementation
			expect(api.books.getStats).toHaveBeenCalled();
		});
	});

	it('should open book drawer when book card is clicked', async () => {
		const mockBook = {
			id: 1,
			title: 'Test Book',
			reading_status: 'currently_reading',
		};
		
		vi.mocked(api.books.list).mockResolvedValue([mockBook]);
		
		const { container } = render(DashboardPage);
		
		await waitFor(() => {
			expect(screen.getByText('Test Book')).toBeInTheDocument();
		});
		
		// Click book card
		const bookCard = screen.getByText('Test Book').closest('button');
		bookCard?.click();
		
		// Drawer should be open (check for drawer component)
		await waitFor(() => {
			const drawer = container.querySelector('[role="dialog"]');
			expect(drawer).toBeInTheDocument();
		});
	});
});
```

**Test Coverage**:
- ✅ Loading state
- ✅ Statistics fetching and display
- ✅ Currently reading books fetch
- ✅ Next to read books fetch
- ✅ Empty state messages
- ✅ Quote fetching when enabled
- ✅ Quote disabled state
- ✅ Quote API failure handling
- ✅ General API error handling
- ✅ Book drawer interaction

#### 6.3 Integration/E2E Test Strategy

**Note**: Project currently doesn't have Playwright configured. If E2E tests are desired, they should be added in a separate plan/PR. For now, manual testing checklist provided.

**Manual Testing Checklist**:

**Desktop Testing**:
- [ ] Dashboard is the first item in sidebar navigation
- [ ] Dashboard loads without errors
- [ ] Statistics cards display correct counts
- [ ] Clicking stat cards navigates to filtered library views
- [ ] Currently reading section shows books
- [ ] Next to read section shows up to 5 books
- [ ] "View all" buttons navigate to library with correct status
- [ ] Quote displays when enabled (check .env)
- [ ] Quote does NOT display when disabled
- [ ] Quote failure doesn't break page
- [ ] Clicking book card opens drawer
- [ ] Editing book in drawer updates stats
- [ ] Deleting book in drawer updates stats
- [ ] Empty states display correctly

**Mobile Testing**:
- [ ] Dashboard accessible from bottom nav
- [ ] Statistics grid responsive (2 columns on mobile)
- [ ] Book grids responsive
- [ ] Quote card readable on small screens
- [ ] All buttons and cards tappable

**Internationalization**:
- [ ] All text translates to German correctly
- [ ] Switch language updates dashboard labels
- [ ] Quote author/text remain in original language

**Performance**:
- [ ] Page loads within 2 seconds
- [ ] No console errors
- [ ] API calls complete quickly
- [ ] Quote API timeout handled gracefully

**Security**:
- [ ] Dashboard requires authentication
- [ ] Stats endpoint requires authentication
- [ ] User can only see their own data

---

## Implementation Order

1. **Phase 1**: Backend statistics endpoint and tests
2. **Phase 2**: Frontend dashboard page component
3. **Phase 3**: Update navigation and routing
4. **Phase 4**: Add translations (en, de)
5. **Phase 5**: Environment configuration
6. **Phase 6**: Write and run tests
7. **Final**: Manual testing and verification

---

## Files to Create/Modify

### New Files
- ✅ `backend/tests/test_dashboard.py` - Backend tests for stats endpoint
- ✅ `frontend/src/routes/dashboard/+page.svelte` - Dashboard page component
- ✅ `frontend/src/routes/dashboard/+page.test.ts` - Frontend unit tests

### Modified Files
- ✅ `backend/app/routers/books.py` - Add `/stats` endpoint
- ✅ `backend/app/schemas.py` - Add LibraryStats schema
- ✅ `frontend/src/lib/api.ts` - Add getStats method
- ✅ `frontend/src/lib/types.ts` - Add LibraryStats interface
- ✅ `frontend/src/routes/+layout.svelte` - Update navigation, add dashboard link first
- ✅ `frontend/src/routes/+page.svelte` - Redirect to dashboard instead of library
- ✅ `frontend/src/lib/i18n/locales/en.json` - Add dashboard translations
- ✅ `frontend/src/lib/i18n/locales/de.json` - Add dashboard translations
- ✅ `.env.example` - Add DASHBOARD_QUOTE_ENABLED variable

---

## Risk Assessment

### Low Risk
- ✅ Adding new dashboard page (non-breaking addition)
- ✅ New statistics endpoint (read-only, no data modification)
- ✅ Environment variable for quote feature
- ✅ Translation additions

### Medium Risk
- ⚠️ External API dependency (quoteslate.vercel.app) - could be unreliable
- ⚠️ Navigation order change - users may be confused initially
- ⚠️ Performance with large libraries (stats queries)

### Mitigations
- Quote API wrapped in try-catch with graceful degradation
- Quote feature is optional via environment variable
- Can disable quote feature if API becomes unreliable
- Statistics queries are simple and indexed
- Could add query optimization or caching if needed
- Navigation change is intuitive (dashboard first is standard pattern)

---

## Performance Considerations

### Backend
- **Stats Endpoint**: Uses simple COUNT queries with indexed fields (user_id, reading_status)
- **Optimization Opportunity**: Could use single GROUP BY query instead of separate queries per status
- **Caching Opportunity**: Could cache stats with TTL if library updates are infrequent

### Frontend
- **API Calls**: Dashboard makes 3 API calls in parallel (currently_reading, want_to_read, stats)
- **Optimization**: Uses Promise.all for concurrent fetching
- **Quote API**: Separate from critical path, failure doesn't block dashboard
- **Rendering**: Limits "Next to Read" to 5 books to avoid large initial render

---

## Accessibility Considerations

- **Semantic HTML**: Uses proper heading hierarchy (h1, h2)
- **ARIA**: Statistics cards should have proper labels
- **Keyboard Navigation**: All interactive elements (buttons, cards) are keyboard accessible
- **Color Contrast**: Uses DaisyUI theme colors with sufficient contrast
- **Screen Readers**: All sections have descriptive headings
- **Focus Management**: Drawer focus handling already implemented in BookDrawer

---

## Future Enhancements

After successful implementation, consider:

1. **Reading Streak**: Track consecutive days of reading activity
2. **Reading Goals**: Set and track monthly/yearly reading goals
3. **Recent Activity**: Timeline of recent book actions (added, started, finished)
4. **Reading Pace**: Average books per month/year
5. **Genre Statistics**: Breakdown by genre/category
6. **Quote Favorites**: Allow users to favorite quotes
7. **Recommendations**: Suggest books based on reading history
8. **Charts/Graphs**: Visualize reading trends over time
9. **Achievements/Badges**: Gamification elements
10. **Export Stats**: Download reading statistics as CSV/PDF

---

## Backward Compatibility

**URLs**:
- Old: Root `/` redirects to `/library` 
- New: Root `/` redirects to `/dashboard`
- Library remains accessible at `/library`
- No breaking changes to library functionality

**API**:
- New `/api/books/stats` endpoint (additive, non-breaking)
- Existing endpoints unchanged

**Environment Variables**:
- New `DASHBOARD_QUOTE_ENABLED` is optional (defaults to true)

**Navigation**:
- Dashboard added as first menu item
- Library moved to second position
- All existing menu items remain

---

## Success Criteria

1. ✅ Dashboard accessible at `/dashboard`
2. ✅ Dashboard is first item in navigation menu
3. ✅ Root URL redirects to dashboard
4. ✅ Statistics endpoint returns accurate counts
5. ✅ Currently reading books display correctly
6. ✅ Next to read books display (max 5)
7. ✅ Statistics cards navigate to filtered library views
8. ✅ Quote displays when enabled (and can be disabled)
9. ✅ Quote API failure handled gracefully
10. ✅ All translations complete (English, German)
11. ✅ Backend tests pass (100% coverage for stats endpoint)
12. ✅ Frontend tests pass
13. ✅ Manual testing checklist complete
14. ✅ No console errors
15. ✅ Responsive on mobile and desktop

---

## Estimated Effort

- **Phase 1** (Backend): 1-2 hours
- **Phase 2** (Frontend Dashboard): 3-4 hours
- **Phase 3** (Navigation): 0.5 hours
- **Phase 4** (Translations): 0.5 hours
- **Phase 5** (Environment): 0.5 hours
- **Phase 6** (Testing): 2-3 hours
- **Manual Testing & QA**: 1-2 hours

**Total**: 8-12 hours

**Priority**: High (core feature, improves UX)  
**Complexity**: Medium  
**Risk Level**: Low

---

## Alternative Approaches Considered

### Option A: Dashboard as Modal/Overlay
**Description**: Show dashboard as a popup/modal when user first logs in

**Pros**:
- Non-intrusive to existing navigation
- Can be dismissed

**Cons**:
- Hidden, less discoverable
- Not always accessible
- Modal fatigue

**Decision**: ❌ Rejected - Dashboard should be a persistent first-class page

### Option B: Dashboard as Library Tab
**Description**: Add "Overview" tab to Library page

**Pros**:
- Keeps everything in Library context
- No new navigation item

**Cons**:
- Clutters library tabs
- Mixes different concerns (books list vs. overview)
- Less prominent

**Decision**: ❌ Rejected - Dashboard and Library serve different purposes

### Option C: Dedicated Dashboard Page (Recommended)
**Description**: Standalone dashboard page as first navigation item

**Pros**:
- ✅ Clear separation of concerns
- ✅ Prominent and discoverable
- ✅ Standard pattern in similar apps
- ✅ Room for future expansion (charts, goals, etc.)
- ✅ Provides overview before diving into details

**Cons**:
- Adds one extra navigation item

**Decision**: ✅ **Selected** - Best balance of usability, discoverability, and scalability

---

## Quote Feature Design

### API Choice: quoteslate.vercel.app

**Selected API**: https://quoteslate.vercel.app/api/quotes/random

**Pros**:
- ✅ Free, no API key required
- ✅ Simple JSON response
- ✅ Supports filtering by tags (using `tags=humility`)
- ✅ Supports length filtering (`maxLength=100`)
- ✅ HTTPS endpoint

**Cons**:
- ⚠️ Third-party dependency (could go down)
- ⚠️ No uptime SLA
- ⚠️ Rate limiting unknown

**Mitigations**:
- Feature is optional (can be disabled)
- Graceful error handling (failure doesn't break page)
- Loading state shown while fetching
- Error state shown if fetch fails
- Quote displayed in non-critical section

### Alternative Quote APIs Considered

1. **ZenQuotes API**: Requires API key, has rate limits
2. **Quotable API**: Similar but less filtering options
3. **Local Quote Database**: Would require maintaining quotes locally

**Decision**: quoteslate.vercel.app is the best fit for this feature's requirements

---

## Conclusion

This plan provides a comprehensive approach to implementing a dashboard page as the new landing page for LibrisLog. The dashboard will give users an at-a-glance view of their reading activity with sections for:
- Inspirational quotes (optional, controllable)
- Library statistics (total books, read, reading, to-read)
- Currently reading books
- Next books to read

The implementation is straightforward, leverages existing patterns (Svelte 5, DaisyUI, existing components), and includes thorough testing. The quote feature is optional and fails gracefully if unavailable. The dashboard becomes the new first page, providing users with a welcoming overview before diving into detailed book management.

**Next Steps**: After plan approval, begin implementation starting with backend statistics endpoint and tests.
