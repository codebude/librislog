<script lang="ts">
	import { onMount } from 'svelte';
	import type { Book, DashboardQuote, LibraryStats } from '$lib/types';
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import { shouldShowActionToast } from '$lib/errors';
	import BookCard from '$lib/components/BookCard.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';

	const DASHBOARD_QUOTE_CACHE_KEY = 'librislog.dashboard.quote';

	function getEndOfDayTimestamp(now = new Date()): number {
		const end = new Date(now);
		end.setHours(23, 59, 59, 999);
		return end.getTime();
	}

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
	let quoteLoading = $state(false);
	let quoteEnabled = $state(false);
	let quote = $state<DashboardQuote | null>(null);
	let quoteCacheRevalidated = $state(false);

	let selectedBook = $state<Book | null>(null);
	let drawerOpen = $state(false);

	onMount(() => {
		void loadDashboard();
	});

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
		} catch (e: unknown) {
			const message = e instanceof Error ? e.message : $_('common.actionFailed', { values: { action: 'load' } });
			if (shouldShowActionToast(message)) {
				toasts.add(message, 'error');
			}
		} finally {
			loading = false;
		}

		await loadQuote();
	}

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

	function openDrawer(book: Book) {
		selectedBook = book;
		drawerOpen = true;
	}

	function handleSave(updated: Book) {
		currentlyReading = currentlyReading.map((book) => (book.id === updated.id ? updated : book));
		nextToRead = nextToRead.map((book) => (book.id === updated.id ? updated : book));
		void loadDashboard();
	}

	function handleDelete(id: number) {
		currentlyReading = currentlyReading.filter((book) => book.id !== id);
		nextToRead = nextToRead.filter((book) => book.id !== id);
		void loadDashboard();
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
						<BookCard {book} onClick={openDrawer} />
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
						<BookCard {book} onClick={openDrawer} />
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>

<BookDrawer
	bind:book={selectedBook}
	bind:open={drawerOpen}
	onSave={handleSave}
	onDelete={handleDelete}
/>
