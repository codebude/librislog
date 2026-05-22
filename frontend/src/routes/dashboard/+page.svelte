<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import type { Book, DashboardQuote, LibraryStats } from '$lib/types';
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import { shouldShowActionToast } from '$lib/errors';
	import { isQuoteServiceEnabled } from '$lib/stores/timezone';
	import BookCard from '$lib/components/BookCard.svelte';
	import BookDetailDialog from '$lib/components/BookDetailDialog.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';

	let loading = $state(true);
	let stats = $state<LibraryStats>({
		total_books: 0,
		books_read: 0,
		books_reading: 0,
		books_want_to_read: 0,
		books_did_not_finish: 0
	});
	let currentlyReading = $state<Book[]>([]);
	let nextToRead = $state<Book[]>([]);
	let progressMap = $state<Record<number, number>>({});
	let quoteLoading = $state(false);
	let quoteEnabled = $state(false);
	let quote = $state<DashboardQuote | null>(null);
	let tagCloud = $state<Array<{ tag: string; count: number }>>([]);
	let searchQuery = $state('');
	let searchResults = $state<Book[]>([]);
	let searchLoading = $state(false);
	let searchToken = 0;
	let searchTimer: ReturnType<typeof setTimeout> | null = null;
	let highlightedIndex = $state(-1);
	const searchListboxId = 'dashboard-search-results';
	const showSearchDropdown = $derived(searchQuery.trim().length > 0);

	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let drawerOpen = $state(false);

	const STATUS_LABEL_KEYS: Record<string, string> = {
		want_to_read: 'status.want_to_read',
		currently_reading: 'status.currently_reading',
		read: 'status.read',
		did_not_finish: 'status.did_not_finish'
	};

	const STATUS_BADGE: Record<string, string> = {
		want_to_read: 'badge-info',
		currently_reading: 'badge-warning',
		read: 'badge-success',
		did_not_finish: 'badge-error'
	};

	onMount(() => {
		const authorQuery = $page.url.searchParams.get('q');
		if (authorQuery) {
			searchQuery = authorQuery;
		}
		void loadDashboard();
	});

	async function loadProgressForBooks(books: Book[]) {
		const ids = books.map((b) => b.id);
		if (ids.length === 0) return;
		try {
			const results = await api.books.progress.latest(ids);
			for (const p of results) {
				progressMap[p.book_id] = p.current_page;
			}
		} catch {
			// progress is optional
		}
	}

	async function loadDashboard() {
		loading = true;
		try {
			const [statsData, readingBooks, wantToReadBooks] = await Promise.all([
				api.books.stats(),
				api.books.list({
					status: 'currently_reading',
					smart_sort: false,
					sort: 'date_started',
					order: 'desc'
				}),
				api.books.list({
					status: 'want_to_read',
					smart_sort: false,
					sort: 'date_added',
					order: 'asc'
				})
			]);

			stats = statsData;
			currentlyReading = readingBooks.slice(0, 5);
			nextToRead = wantToReadBooks.slice(0, 5);

			const allBooks = [...currentlyReading, ...nextToRead];
			void loadProgressForBooks(allBooks);
		} catch (e: unknown) {
			const message = e instanceof Error ? e.message : $_('common.actionFailed', { values: { action: 'load' } });
			if (shouldShowActionToast(message)) {
				toasts.add(message, 'error');
			}
		} finally {
			loading = false;
		}

		await loadQuote();
		await loadTagCloud();
	}

	async function loadTagCloud() {
		try {
			tagCloud = await api.books.tagCloud(50);
		} catch {
			tagCloud = [];
		}
	}

	function tagCloudSize(count: number): number {
		return Math.min(1.2, 0.8 + count * 0.08);
	}

	function applyTagCloudSearch(tag: string) {
		window.scrollTo({ top: 0, behavior: 'smooth' });
		if (searchQuery === tag) {
			const token = ++searchToken;
			void runSearch(tag, token);
			return;
		}
		searchQuery = tag;
	}

	async function loadQuote() {
		if (!isQuoteServiceEnabled()) {
			quoteEnabled = false;
			quote = null;
			return;
		}
		quoteLoading = true;
		try {
			const data = await api.books.dashboardQuote();
			quoteEnabled = true;
			quote = data;
		} catch (e: unknown) {
			const status = typeof e === 'object' && e !== null && 'status' in e ? (e as { status?: number }).status : undefined;
			if (status === 503) {
				quoteEnabled = false;
				quote = null;
				return;
			}
			quoteEnabled = true;
			quote = null;
		} finally {
			quoteLoading = false;
		}
	}

	function openDetailView(book: Book) {
		selectedBook = book;
		detailOpen = true;
		drawerOpen = false;
	}

	function openEditFromDetail(book: Book) {
		selectedBook = book;
		detailOpen = false;
		drawerOpen = true;
	}

	function handleSave(updated: Book) {
		selectedBook = updated;
		currentlyReading = currentlyReading.map((book) => (book.id === updated.id ? updated : book));
		nextToRead = nextToRead.map((book) => (book.id === updated.id ? updated : book));
		void loadDashboard();
	}

	function handleDelete(id: number) {
		detailOpen = false;
		drawerOpen = false;
		currentlyReading = currentlyReading.filter((book) => book.id !== id);
		nextToRead = nextToRead.filter((book) => book.id !== id);
		void loadDashboard();
	}

	async function runSearch(query: string, token: number) {
		searchLoading = true;
		try {
			const results = await api.books.list({
				q: query,
				smart_sort: false,
				sort: 'date_added',
				order: 'desc'
			});
			if (token !== searchToken) return;
			searchResults = results;
		} catch {
			if (token !== searchToken) return;
			searchResults = [];
		} finally {
			if (token === searchToken) {
				searchLoading = false;
			}
		}
	}

	$effect(() => {
		const trimmed = searchQuery.trim();
		if (searchTimer) {
			clearTimeout(searchTimer);
			searchTimer = null;
		}

		if (!trimmed) {
			searchLoading = false;
			searchResults = [];
			highlightedIndex = -1;
			return;
		}

		const token = ++searchToken;
		searchTimer = setTimeout(() => {
			void runSearch(trimmed, token);
		}, 300);

		return () => {
			if (searchTimer) {
				clearTimeout(searchTimer);
				searchTimer = null;
			}
		};
	});

	function openFromSearch(book: Book) {
		searchQuery = '';
		searchResults = [];
		searchLoading = false;
		highlightedIndex = -1;
		selectedBook = book;
		detailOpen = true;
	}

	$effect(() => {
		if (!searchQuery.trim() || searchLoading || searchResults.length === 0) {
			highlightedIndex = -1;
			return;
		}
		if (highlightedIndex < 0 || highlightedIndex >= searchResults.length) {
			highlightedIndex = 0;
		}
	});

	function onSearchKeydown(event: KeyboardEvent) {
		if (!searchQuery.trim() || searchLoading || searchResults.length === 0) {
			if (event.key === 'Escape') {
				searchQuery = '';
			}
			return;
		}

		if (event.key === 'ArrowDown') {
			event.preventDefault();
			highlightedIndex = (highlightedIndex + 1 + searchResults.length) % searchResults.length;
			return;
		}

		if (event.key === 'ArrowUp') {
			event.preventDefault();
			highlightedIndex = (highlightedIndex - 1 + searchResults.length) % searchResults.length;
			return;
		}

		if (event.key === 'Enter') {
			event.preventDefault();
			const selected = searchResults[Math.max(0, highlightedIndex)];
			if (selected) {
				void openFromSearch(selected);
			}
			return;
		}

		if (event.key === 'Escape') {
			event.preventDefault();
			searchQuery = '';
		}
	}
</script>

<div class="flex flex-col gap-6">
	<div class="hero rounded-2xl bg-base-100 shadow-sm border border-base-200">
		<div class="hero-content text-center py-10">
			<div class="max-w-2xl">
				<h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight">{$_('dashboard.title')}</h1>
				<p class="text-base-content/70 mt-2">{$_('dashboard.subtitle')}</p>
			</div>
		</div>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-3">
			<h2 class="card-title text-base">{$_('dashboard.searchAllBooks')}</h2>
			<div class="relative w-full">
				<input
					type="text"
					class="input input-bordered w-full pr-10"
					placeholder={$_('common.searchBooks')}
					bind:value={searchQuery}
					onkeydown={onSearchKeydown}
					role="combobox"
					aria-autocomplete="list"
					aria-expanded={showSearchDropdown ? 'true' : 'false'}
					aria-controls={searchListboxId}
					aria-activedescendant={
						showSearchDropdown && highlightedIndex >= 0 ? `dashboard-search-option-${searchResults[highlightedIndex]?.id ?? ''}` : undefined
					}
				/>

				{#if searchQuery.trim().length > 0}
					<button
						type="button"
						class="btn btn-ghost btn-xs btn-circle absolute right-2 top-1/2 -translate-y-1/2"
						onclick={() => {
							searchQuery = '';
						}}
						aria-label={$_('common.clearForm')}
					>
						x
					</button>
				{/if}

				{#if showSearchDropdown}
					<div class="absolute left-0 right-0 top-full mt-2 rounded-lg border border-base-200 bg-base-100 overflow-hidden shadow-lg z-20">
					{#if searchLoading}
						<div class="p-3 text-sm text-base-content/60 flex items-center gap-2">
							<span class="loading loading-spinner loading-xs"></span>
							{$_('common.search')}
						</div>
					{:else if searchResults.length === 0}
						<div class="p-3 text-sm text-base-content/60">{$_('dashboard.noSearchResults')}</div>
					{:else}
						<ul id={searchListboxId} role="listbox" class="max-h-80 overflow-y-auto">
							{#each searchResults as book, i (book.id)}
								<li role="presentation">
									<button
										type="button"
										id={`dashboard-search-option-${book.id}`}
										role="option"
										aria-selected={highlightedIndex === i}
										class="w-full text-left p-3 transition-colors flex items-start gap-3 cursor-pointer {highlightedIndex === i ? 'bg-base-200/70' : 'hover:bg-base-200/60'}"
										onclick={() => openFromSearch(book)}
										onmouseenter={() => (highlightedIndex = i)}
									>
										{#if book.cover_url}
											<img
												src={book.cover_url}
												alt={$_('book.coverOf', { values: { title: book.title } })}
												class="w-10 h-14 rounded object-cover shrink-0"
											/>
										{/if}
										<div class="min-w-0 flex-1">
											<p class="font-medium text-sm line-clamp-2">{book.title}</p>
											{#if book.author}
												<p class="text-xs text-base-content/60 truncate">{book.author}</p>
											{/if}
											<span class="badge badge-xs mt-1 {STATUS_BADGE[book.reading_status]}">
												{$_(STATUS_LABEL_KEYS[book.reading_status])}
											</span>
										</div>
									</button>
								</li>
							{/each}
						</ul>
					{/if}
					</div>
				{/if}
			</div>
		</div>
	</div>

	{#if quoteEnabled}
		<div class="card bg-gradient-to-r from-teal-600 to-cyan-700 text-white shadow-sm">
			<div class="card-body">
				<h2 class="card-title">{$_('dashboard.quoteTitle')}</h2>
				{#if quoteLoading}
					<span class="loading loading-dots loading-md"></span>
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

	<div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
		<a href="/library" class="stat bg-base-100 rounded-2xl shadow-sm border border-base-200 hover:shadow-md transition-shadow">
			<div class="stat-title">{$_('dashboard.totalBooks')}</div>
			<div class="stat-value text-primary">{stats.total_books}</div>
		</a>
		<a href="/library?status=read" class="stat bg-base-100 rounded-2xl shadow-sm border border-base-200 hover:shadow-md transition-shadow">
			<div class="stat-title">{$_('dashboard.booksRead')}</div>
			<div class="stat-value text-success">{stats.books_read}</div>
		</a>
		<a href="/library?status=want_to_read" class="stat bg-base-100 rounded-2xl shadow-sm border border-base-200 hover:shadow-md transition-shadow">
			<div class="stat-title">{$_('dashboard.booksToRead')}</div>
			<div class="stat-value text-info">{stats.books_want_to_read}</div>
		</a>
		<a href="/library?status=currently_reading" class="stat bg-base-100 rounded-2xl shadow-sm border border-base-200 hover:shadow-md transition-shadow">
			<div class="stat-title">{$_('dashboard.currentlyReading')}</div>
			<div class="stat-value text-warning">{stats.books_reading}</div>
		</a>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-4">
			<div class="flex items-center justify-between">
				<h2 class="card-title">{$_('dashboard.currentlyReading')}</h2>
				<a class="btn btn-ghost btn-sm" href="/library?status=currently_reading">{$_('dashboard.viewAll')}</a>
			</div>

			{#if loading}
				<div class="py-8 text-center"><span class="loading loading-spinner loading-md"></span></div>
			{:else if currentlyReading.length === 0}
				<p class="text-base-content/60">{$_('dashboard.noCurrentlyReading')}</p>
			{:else}
				<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
					{#each currentlyReading as book (book.id)}
						<BookCard {book} onClick={openDetailView} currentPage={progressMap[book.id] ?? 0} />
					{/each}
				</div>
			{/if}
		</div>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-4">
			<div class="flex items-center justify-between">
				<h2 class="card-title">{$_('dashboard.nextToRead')}</h2>
				<a class="btn btn-ghost btn-sm" href="/library?status=want_to_read">{$_('dashboard.viewAll')}</a>
			</div>

			{#if loading}
				<div class="py-8 text-center"><span class="loading loading-spinner loading-md"></span></div>
			{:else if nextToRead.length === 0}
				<p class="text-base-content/60">{$_('dashboard.noNextToRead')}</p>
			{:else}
				<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
					{#each nextToRead as book (book.id)}
						<BookCard {book} onClick={openDetailView} currentPage={progressMap[book.id] ?? 0} />
					{/each}
				</div>
			{/if}
		</div>
	</div>

	{#if tagCloud.length > 0}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body gap-4">
				<div class="flex items-center justify-between">
					<h2 class="card-title">{$_('dashboard.popularTags')}</h2>
				</div>
				<div class="flex flex-wrap gap-2">
					{#each tagCloud as entry (entry.tag)}
						<button
							type="button"
							class="badge badge-outline hover:badge-primary transition-colors cursor-pointer"
							style={`font-size: ${tagCloudSize(entry.count)}rem;`}
							onclick={() => applyTagCloudSearch(entry.tag)}
						>
							{entry.tag}
							<span class="ml-1 text-xs opacity-70">{entry.count}</span>
						</button>
					{/each}
				</div>
			</div>
		</div>
	{/if}
</div>

<BookDetailDialog bind:book={selectedBook} bind:open={detailOpen} onEdit={openEditFromDetail} onDelete={handleDelete} />

<BookDrawer
	bind:book={selectedBook}
	bind:open={drawerOpen}
	onSave={handleSave}
/>
