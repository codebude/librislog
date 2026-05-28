	<script lang="ts">
	import type { Book, ReadingStatus, LibraryStats, SortField, SortOrder } from '$lib/types';
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount, onDestroy } from 'svelte';
	import { toasts } from '$lib/toasts';
	import { shouldShowActionToast } from '$lib/errors';
	import BookCard from '$lib/components/BookCard.svelte';
	import BookListItem from '$lib/components/BookListItem.svelte';
	import BookDetailDialog from '$lib/components/BookDetailDialog.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';
	import AddBookModal from '$lib/components/AddBookModal.svelte';
	import SearchBar from '$lib/components/SearchBar.svelte';
	import { BookOpen as BookOpenIcon, Book as BookIcon, Check, X } from '@lucide/svelte';

	type Tab = {
		status: ReadingStatus;
		labelKey: string;
		Icon: typeof BookOpenIcon;
	};

	const TABS: Tab[] = [
		{ status: 'want_to_read', labelKey: 'status.want_to_read', Icon: BookOpenIcon },
		{ status: 'currently_reading', labelKey: 'status.currently_reading', Icon: BookIcon },
		{ status: 'read', labelKey: 'status.read', Icon: Check },
		{ status: 'did_not_finish', labelKey: 'status.did_not_finish', Icon: X }
	];

	const STATUS_LABEL_KEYS: Record<string, string> = {
		want_to_read: 'status.want_to_read',
		currently_reading: 'status.currently_reading',
		read: 'status.read',
		did_not_finish: 'status.did_not_finish'
	};

	const PAGE_SIZE = 40;

	let activeStatus = $derived<ReadingStatus>(
		($page.url.searchParams.get('status') as ReadingStatus) ?? 'want_to_read'
	);
	let requestedBookId = $derived.by(() => {
		const raw = $page.url.searchParams.get('bookId');
		if (!raw) return null;
		const parsed = Number.parseInt(raw, 10);
		return Number.isNaN(parsed) ? null : parsed;
	});

	let books = $state<Book[]>([]);
	let progressMap = $state<Record<number, number>>({});
	let statusCounts = $state<LibraryStats | null>(null);
	let loading = $state(false);

	let loadingMore = $state(false);
	let hasMore = $state(true);
	let nextOffset = $state(0);
	let viewMode = $state<'large' | 'small' | 'list'>(
		typeof window !== 'undefined' &&
		(localStorage.getItem('libraryViewMode') === 'small' || localStorage.getItem('libraryViewMode') === 'list')
			? (localStorage.getItem('libraryViewMode') as 'large' | 'small' | 'list')
			: 'large'
	);

	function setViewMode(mode: 'large' | 'small' | 'list') {
		viewMode = mode;
		if (typeof window !== 'undefined') {
			localStorage.setItem('libraryViewMode', mode);
		}
	}
	let totalCount = $state(0);
	let searchQuery = $state('');
	let smartSort = $state(true);
	let sort = $state<SortField>('date_added');
	let order = $state<SortOrder>('desc');
	let loadMoreAnchor = $state<HTMLDivElement | null>(null);
	let requestVersion = 0;
	let observer: IntersectionObserver | null = null;
	const numberFormatter = new Intl.NumberFormat();

	function formatCount(value: number | null): string {
		if (value === null) return '...';
		return numberFormatter.format(value);
	}

	function getStatusCount(status: ReadingStatus): number | null {
		if (!statusCounts) return null;
		switch (status) {
			case 'want_to_read':
				return statusCounts.books_want_to_read;
			case 'currently_reading':
				return statusCounts.books_reading;
			case 'read':
				return statusCounts.books_read;
			case 'did_not_finish':
				return statusCounts.books_did_not_finish;
		}
	}

	async function refreshStatusCounts() {
		try {
			statusCounts = await api.books.stats();
		} catch {
			statusCounts = null;
		}
	}

	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let drawerOpen = $state(false);
	let addBookOpen = $state(false);

	function changeTab(status: ReadingStatus) {
		if (status === activeStatus) return;
		void goto(`/library?status=${status}`);
	}

	async function fetchProgressForBatch(batch: Book[], version: number, replace = false) {
		const ids = batch.map((b) => b.id);
		if (ids.length === 0) {
			if (replace) {
				progressMap = {};
			}
			return;
		}

		const results = await api.books.progress.latest(ids);
		if (version !== requestVersion) return;

		const map: Record<number, number> = replace ? {} : { ...progressMap };
		for (const p of results) {
			map[p.book_id] = p.current_page;
		}
		progressMap = map;
	}

	async function maybePrefillViewport(version: number) {
		if (typeof window === 'undefined') return;
		let safety = 0;
		while (
			version === requestVersion &&
			hasMore &&
			!loadingMore &&
			document.documentElement.scrollHeight <= window.innerHeight + 240 &&
			safety < 4
		) {
			safety += 1;
			await loadMoreBooks();
		}
	}

	async function fetchBooks() {
		const version = ++requestVersion;
		loading = true;
		try {
			const response = await api.books.list({
				status: activeStatus,
				q: searchQuery || undefined,
				smart_sort: smartSort,
				sort,
				order,
				offset: 0,
				limit: PAGE_SIZE
			});
			if (version !== requestVersion) return;

			totalCount = response.total;
			books = response.books;
			nextOffset = response.books.length;
			hasMore = response.books.length === PAGE_SIZE;
			await fetchProgressForBatch(response.books, version, true);
			await maybePrefillViewport(version);
		} catch (e: unknown) {
			if (version !== requestVersion) return;
			const message = e instanceof Error ? e.message : $_('import.searchFailed');
			if (shouldShowActionToast(message)) {
				toasts.add(message, 'error');
			}
		} finally {
			loading = false;
		}
	}

	async function loadMoreBooks() {
		if (loadingMore || loading || !hasMore) return;
		const version = requestVersion;
		loadingMore = true;
		try {
			const response = await api.books.list({
				status: activeStatus,
				q: searchQuery || undefined,
				smart_sort: smartSort,
				sort,
				order,
				offset: nextOffset,
				limit: PAGE_SIZE
			});
			if (version !== requestVersion) return;

			books = [...books, ...response.books];
			nextOffset += response.books.length;
			hasMore = response.books.length === PAGE_SIZE;
			await fetchProgressForBatch(response.books, version);
		} catch (e: unknown) {
			if (version !== requestVersion) return;
			const message = e instanceof Error ? e.message : $_('import.searchFailed');
			if (shouldShowActionToast(message)) {
				toasts.add(message, 'error');
			}
		} finally {
			if (version === requestVersion) {
				loadingMore = false;
			}
		}
	}

	$effect(() => {
		void activeStatus;
		void searchQuery;
		void smartSort;
		void sort;
		void order;
		fetchBooks();
	});

	$effect(() => {
		const bookId = requestedBookId;
		if (!bookId) return;
		const match = books.find((b) => b.id === bookId);
		if (!match) return;
		selectedBook = match;
		detailOpen = true;
		drawerOpen = false;
	});

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
		if (updated.reading_status !== activeStatus) {
			detailOpen = false;
			drawerOpen = false;
			books = books.filter((b) => b.id !== updated.id);
		} else {
			books = books.map((b) => (b.id === updated.id ? updated : b));
		}
		void refreshStatusCounts();
	}

	function handleDelete(id: number) {
		detailOpen = false;
		drawerOpen = false;
		books = books.filter((b) => b.id !== id);
		void refreshStatusCounts();
	}

	function handleAdded(book: Book) {
		if (book.reading_status === activeStatus) {
			books = [book, ...books];
		}
		addBookOpen = false;
		void refreshStatusCounts();
	}

	onMount(() => {
		void refreshStatusCounts();

		if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
			return;
		}

		observer = new IntersectionObserver(
			(entries) => {
				if (entries.some((entry) => entry.isIntersecting)) {
					void loadMoreBooks();
				}
			},
			{ root: null, rootMargin: '300px 0px', threshold: 0 }
		);

		return () => {
			observer?.disconnect();
			observer = null;
		};
	});

	$effect(() => {
		const anchor = loadMoreAnchor;
		if (!anchor || !observer) return;
		observer.observe(anchor);
		return () => observer?.unobserve(anchor);
	});
</script>

<div class="flex flex-col gap-4">
	<div role="tablist" class="tabs tabs-boxed bg-base-100 overflow-x-auto">
		{#each TABS as tab}
			<button
				type="button"
				role="tab"
				aria-selected={activeStatus === tab.status}
				class="tab whitespace-nowrap {activeStatus === tab.status ? 'tab-active' : ''}"
				onclick={() => changeTab(tab.status)}
			>
				<tab.Icon class="w-4 h-4 mr-1" />
				{$_(tab.labelKey)} ({formatCount(getStatusCount(tab.status))})
			</button>
		{/each}
	</div>

	<div class="flex flex-col sm:flex-row sm:items-center gap-4">
		<h1 class="text-xl font-bold">{$_(STATUS_LABEL_KEYS[activeStatus])}</h1>

		<div class="flex items-center gap-2 flex-1">
			<SearchBar
				bind:value={searchQuery}
				placeholder={$_('common.searchBooks')}
				onSearch={(q) => (searchQuery = q)}
			/>
			{#if searchQuery}
				<span class="text-sm text-base-content/50 whitespace-nowrap shrink-0">
					{totalCount} {totalCount === 1 ? $_('common.result') : $_('common.results')}
				</span>
			{/if}
		</div>
		<div class="join" role="group" aria-label="View mode">
			<button
				class="btn btn-sm join-item"
				class:btn-active={viewMode === 'large'}
				onclick={() => setViewMode('large')}
				aria-label="Large cards"
			>
				<svg class="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
					<rect x="1" y="1" width="6" height="6" rx="1"/>
					<rect x="9" y="1" width="6" height="6" rx="1"/>
					<rect x="1" y="9" width="6" height="6" rx="1"/>
					<rect x="9" y="9" width="6" height="6" rx="1"/>
				</svg>
			</button>
			<button
				class="btn btn-sm join-item"
				class:btn-active={viewMode === 'small'}
				onclick={() => setViewMode('small')}
				aria-label="Small cards"
			>
				<svg class="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
					<rect x="1" y="1" width="4" height="4" rx="0.5"/>
					<rect x="6" y="1" width="4" height="4" rx="0.5"/>
					<rect x="11" y="1" width="4" height="4" rx="0.5"/>
					<rect x="1" y="6" width="4" height="4" rx="0.5"/>
					<rect x="6" y="6" width="4" height="4" rx="0.5"/>
					<rect x="11" y="6" width="4" height="4" rx="0.5"/>
					<rect x="1" y="11" width="4" height="4" rx="0.5"/>
					<rect x="6" y="11" width="4" height="4" rx="0.5"/>
					<rect x="11" y="11" width="4" height="4" rx="0.5"/>
				</svg>
			</button>
			<button
				class="btn btn-sm join-item"
				class:btn-active={viewMode === 'list'}
				onclick={() => setViewMode('list')}
				aria-label="List view"
			>
				<svg class="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
					<rect x="1" y="2" width="14" height="2" rx="0.5"/>
					<rect x="1" y="7" width="14" height="2" rx="0.5"/>
					<rect x="1" y="12" width="14" height="2" rx="0.5"/>
				</svg>
			</button>
		</div>
		<div class="flex items-center gap-2 text-sm">
			<label class="label cursor-pointer gap-2">
				<span class="label-text text-xs">{$_('sort.smart')}</span>
				<input type="checkbox" class="toggle toggle-xs" name="smart-sort" bind:checked={smartSort} />
			</label>
			<select class="select select-bordered select-xs" name="sort-field" bind:value={sort} disabled={smartSort}>
				<option value="date_added">{$_('common.dateAdded')}</option>
				<option value="title">{$_('book.title')}</option>
				<option value="date_started">{$_('book.dateStarted')}</option>
				<option value="date_finished">{$_('book.dateFinished')}</option>
				<option value="rating">{$_('common.rating')}</option>
			</select>
			<select class="select select-bordered select-xs" name="sort-order" bind:value={order} disabled={smartSort}>
				<option value="desc">{$_('common.desc')}</option>
				<option value="asc">{$_('common.asc')}</option>
			</select>
		</div>
		<button class="btn btn-primary btn-sm" onclick={() => (addBookOpen = true)}>
			+ {$_('app.addBook')}
		</button>
	</div>

	{#if loading}
		<div class="flex justify-center py-16">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if books.length === 0}
		<div class="text-center py-16 text-base-content/40">
			<BookOpenIcon class="w-12 h-12 mx-auto mb-2 opacity-50" />
			<p>{$_('common.noBooksYet')}</p>
			<button class="btn btn-primary btn-sm mt-4" onclick={() => (addBookOpen = true)}>{$_('common.addFirstBook')}</button>
		</div>
	{:else if viewMode === 'list'}
		<div class="flex flex-col gap-1.5">
			{#each books as book (book.id)}
				<BookListItem {book} onClick={openDetailView} currentPage={progressMap[book.id] ?? 0} />
			{/each}
		</div>
		<div bind:this={loadMoreAnchor} class="h-1"></div>
		{#if loadingMore}
			<div class="flex justify-center py-4">
				<span class="loading loading-spinner loading-md"></span>
			</div>
		{/if}
	{:else}
		<div
			class="grid gap-4 {viewMode === 'small'
				? 'grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 gap-3'
				: 'grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5'}"
		>
			{#each books as book (book.id)}
				<BookCard {book} onClick={openDetailView} currentPage={progressMap[book.id] ?? 0} compact={viewMode === 'small'} />
			{/each}
		</div>
		<div bind:this={loadMoreAnchor} class="h-1"></div>
		{#if loadingMore}
			<div class="flex justify-center py-4">
				<span class="loading loading-spinner loading-md"></span>
			</div>
		{/if}
	{/if}
</div>

<BookDetailDialog bind:book={selectedBook} bind:open={detailOpen} onEdit={openEditFromDetail} onDelete={handleDelete} />

<BookDrawer
	bind:book={selectedBook}
	bind:open={drawerOpen}
	onSave={handleSave}
/>

<AddBookModal
	bind:open={addBookOpen}
	defaultStatus={activeStatus}
	onAdded={handleAdded}
/>
