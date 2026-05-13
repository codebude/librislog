<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import type { Book, ReadingStatus, SortField, SortOrder } from '$lib/types';
	import { api } from '$lib/api';
	import { shouldShowActionToast } from '$lib/errors';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import BookCard from '$lib/components/BookCard.svelte';
	import BookDetailDialog from '$lib/components/BookDetailDialog.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';
	import SearchBar from '$lib/components/SearchBar.svelte';
	import AddBookModal from '$lib/components/AddBookModal.svelte';

	type Tab = {
		status: ReadingStatus;
		labelKey: string;
		icon: string;
	};

	const TABS: Tab[] = [
		{ status: 'want_to_read', labelKey: 'status.want_to_read', icon: '📚' },
		{ status: 'currently_reading', labelKey: 'status.currently_reading', icon: '📖' },
		{ status: 'read', labelKey: 'status.read', icon: '✓' },
		{ status: 'did_not_finish', labelKey: 'status.did_not_finish', icon: '❌' }
	];

	const STATUS_LABEL_KEYS: Record<string, string> = {
		want_to_read: 'status.want_to_read',
		currently_reading: 'status.currently_reading',
		read: 'status.read',
		did_not_finish: 'status.did_not_finish'
	};

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
	let loading = $state(false);
	let syncing = $state(false);
	let searchQuery = $state('');
	let smartSort = $state(true);
	let sort = $state<SortField>('date_added');
	let order = $state<SortOrder>('desc');

	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let drawerOpen = $state(false);
	let addBookOpen = $state(false);

	function changeTab(status: ReadingStatus) {
		if (status === activeStatus) return;
		void goto(`/library?status=${status}`);
	}

	async function fetchBooks(background = false) {
		if (background) {
			syncing = true;
		} else {
			loading = true;
		}
		try {
			books = await api.books.list({
				status: activeStatus,
				q: searchQuery || undefined,
				smart_sort: smartSort,
				sort,
				order
			});
			const ids = books.map((b) => b.id);
			if (ids.length > 0) {
				const results = await api.books.progress.latest(ids);
				const map: Record<number, number> = {};
				for (const p of results) {
					map[p.book_id] = p.current_page;
				}
				progressMap = map;
			}
		} catch (e: unknown) {
			const message = e instanceof Error ? e.message : $_('import.searchFailed');
			if (shouldShowActionToast(message)) {
				toasts.add(message, 'error');
			}
		} finally {
			if (background) {
				syncing = false;
			} else {
				loading = false;
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
		void fetchBooks(true);
	}

	function handleDelete(id: number) {
		detailOpen = false;
		drawerOpen = false;
		books = books.filter((b) => b.id !== id);
		void fetchBooks(true);
	}

	function handleAdded(book: Book) {
		if (book.reading_status === activeStatus) {
			books = [book, ...books];
		}
		addBookOpen = false;
		void fetchBooks(true);
	}
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
				<span class="mr-1">{tab.icon}</span>
				{$_(tab.labelKey)}
			</button>
		{/each}
	</div>

	<div class="flex flex-col sm:flex-row sm:items-center gap-3">
		<h1 class="text-xl font-bold">{$_(STATUS_LABEL_KEYS[activeStatus])}</h1>
		{#if syncing}
			<span class="text-xs text-base-content/60 inline-flex items-center gap-1">
				<span class="loading loading-spinner loading-xs"></span>
				{$_('common.syncing')}
			</span>
		{/if}
		<div class="flex items-center gap-2 flex-1">
			<SearchBar
				bind:value={searchQuery}
				placeholder={$_('common.searchBooks')}
				onSearch={(q) => (searchQuery = q)}
			/>
		</div>
		<div class="flex items-center gap-2 text-sm">
			<label class="label cursor-pointer gap-2">
				<span class="label-text text-xs">{$_('sort.smart')}</span>
				<input type="checkbox" class="toggle toggle-xs" bind:checked={smartSort} />
			</label>
			<select class="select select-bordered select-xs" bind:value={sort} disabled={smartSort}>
				<option value="date_added">{$_('common.dateAdded')}</option>
				<option value="title">{$_('book.title')}</option>
				<option value="date_started">{$_('book.dateStarted')}</option>
				<option value="date_finished">{$_('book.dateFinished')}</option>
				<option value="rating">{$_('common.rating')}</option>
			</select>
			<select class="select select-bordered select-xs" bind:value={order} disabled={smartSort}>
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
			<p class="text-4xl mb-2">📚</p>
			<p>{$_('common.noBooksYet')}</p>
			<button class="btn btn-primary btn-sm mt-4" onclick={() => (addBookOpen = true)}>{$_('common.addFirstBook')}</button>
		</div>
	{:else}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
			{#each books as book (book.id)}
				<BookCard {book} onClick={openDetailView} currentPage={progressMap[book.id] ?? 0} />
			{/each}
		</div>
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
