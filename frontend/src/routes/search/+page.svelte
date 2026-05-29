<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import type { Book } from '$lib/types';
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import { shouldShowActionToast } from '$lib/errors';
	import BookCard from '$lib/components/BookCard.svelte';
	import BookDetailDialog from '$lib/components/BookDetailDialog.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';
	import { Search, ArrowLeft, X } from '@lucide/svelte';

	const PAGE_SIZE = 40;
	const DEBOUNCE_MS = 250;

	let searchQuery = $state('');
	let books = $state<Book[]>([]);
	let totalCount = $state(0);
	let loading = $state(false);
	let loadingMore = $state(false);
	let hasMore = $state(false);
	let nextOffset = $state(0);
	let requestVersion = 0;
	let searchTimer: ReturnType<typeof setTimeout> | null = null;

	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let drawerOpen = $state(false);

	let searchInput = $state<HTMLInputElement | null>(null);

	const numberFormatter = new Intl.NumberFormat();

	onMount(() => {
		const q = $page.url.searchParams.get('q') ?? '';
		searchQuery = q;
		if (q) {
			void performSearch(q, true);
		}
		searchInput?.focus();
	});

	async function performSearch(query: string, replace = false) {
		if (!query.trim()) {
			books = [];
			totalCount = 0;
			hasMore = false;
			return;
		}

		const version = ++requestVersion;
		if (replace) {
			loading = true;
			books = [];
			nextOffset = 0;
		} else {
			loadingMore = true;
		}

		try {
			const response = await api.books.list({
				q: query,
				smart_sort: false,
				sort: 'date_added',
				order: 'desc',
				offset: replace ? 0 : nextOffset,
				limit: PAGE_SIZE
			});
			if (version !== requestVersion) return;

			totalCount = response.total;
			if (replace) {
				books = response.books;
			} else {
				books = [...books, ...response.books];
			}
			nextOffset = books.length;
			hasMore = response.books.length === PAGE_SIZE;
		} catch (e: unknown) {
			if (version !== requestVersion) return;
			const message = e instanceof Error ? e.message : $_('import.searchFailed');
			if (shouldShowActionToast(message)) {
				toasts.add(message, 'error');
			}
			if (replace) {
				books = [];
				totalCount = 0;
			}
		} finally {
			if (version === requestVersion) {
				loading = false;
				loadingMore = false;
			}
		}
	}

	function updateUrl(query: string) {
		if (query.trim()) {
			void goto(`/search?q=${encodeURIComponent(query.trim())}`, { replaceState: true });
		} else {
			void goto('/search', { replaceState: true });
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			event.preventDefault();
			if (searchTimer) {
				clearTimeout(searchTimer);
				searchTimer = null;
			}
			updateUrl(searchQuery);
			void performSearch(searchQuery, true);
		}
	}

	// Debounced live search while typing
	$effect(() => {
		const trimmed = searchQuery.trim();

		if (searchTimer) {
			clearTimeout(searchTimer);
			searchTimer = null;
		}

		if (!trimmed) {
			books = [];
			totalCount = 0;
			hasMore = false;
			return;
		}

		searchTimer = setTimeout(() => {
			void performSearch(trimmed, true);
		}, DEBOUNCE_MS);

		return () => {
			if (searchTimer) {
				clearTimeout(searchTimer);
				searchTimer = null;
			}
		};
	});

	function loadMore() {
		if (loadingMore || !hasMore) return;
		void performSearch(searchQuery, false);
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
		books = books.map((b) => (b.id === updated.id ? updated : b));
	}

	function handleDelete(id: number) {
		detailOpen = false;
		drawerOpen = false;
		books = books.filter((b) => b.id !== id);
		totalCount = Math.max(0, totalCount - 1);
	}

	function goBack() {
		window.history.back();
	}
</script>

<svelte:head>
	<title>{searchQuery ? `${searchQuery} - ` : ''}{$_('app.title')}</title>
</svelte:head>

<div class="flex flex-col gap-6">
	<!-- Search Header -->
	<div class="flex items-center gap-4">
		<button
			type="button"
			class="btn btn-ghost btn-circle shrink-0"
			onclick={goBack}
			aria-label={$_('common.back')}
		>
			<ArrowLeft class="w-5 h-5" />
		</button>

		<div class="relative flex-1">
			<Search class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-base-content/50 pointer-events-none z-10" />
			<input
				bind:this={searchInput}
				type="text"
				class="input input-bordered w-full pl-9 pr-10"
				placeholder={$_('common.searchBooks')}
				bind:value={searchQuery}
				onkeydown={handleKeydown}
			/>

			{#if searchQuery.trim().length > 0}
				<button
					type="button"
					class="btn btn-ghost btn-xs btn-circle absolute right-2 top-1/2 -translate-y-1/2 z-10"
					onclick={() => { searchQuery = ''; }}
					aria-label={$_('common.clearForm')}
				>
					<X class="w-4 h-4" />
				</button>
			{/if}
		</div>
	</div>

	<!-- Results Info -->
	{#if searchQuery.trim() && !loading}
		<div class="text-sm text-base-content/70">
			{#if totalCount > 0}
				<span class="font-medium text-base-content">{numberFormatter.format(totalCount)}</span>
				{$_('search.resultsCount', { values: { count: totalCount } })}
			{:else}
				{$_('search.noResults')}
			{/if}
		</div>
	{/if}

	<!-- Results Grid -->
	{#if loading && books.length === 0}
		<div class="flex justify-center py-12">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if books.length > 0}
		<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
			{#each books as book (book.id)}
				<BookCard {book} onClick={openDetailView} />
			{/each}
		</div>

		<!-- Load More -->
		{#if hasMore}
			<div class="flex justify-center py-6">
				<button
					type="button"
					class="btn btn-outline"
					onclick={loadMore}
					disabled={loadingMore}
				>
					{#if loadingMore}
						<span class="loading loading-spinner loading-sm"></span>
					{:else}
						{$_('common.loadMore')}
					{/if}
				</button>
			</div>
		{/if}
	{:else if searchQuery.trim() && !loading}
		<div class="flex flex-col items-center justify-center py-16 text-base-content/50">
			<Search class="w-16 h-16 mb-4" />
			<p class="text-lg">{$_('search.noResultsFor', { values: { query: searchQuery } })}</p>
			<p class="text-sm mt-2">{$_('search.tryDifferentQuery')}</p>
		</div>
	{/if}
</div>

<BookDetailDialog bind:book={selectedBook} bind:open={detailOpen} onEdit={openEditFromDetail} onDelete={handleDelete} />

<BookDrawer bind:book={selectedBook} bind:open={drawerOpen} onSave={handleSave} />
