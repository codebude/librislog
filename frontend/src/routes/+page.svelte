<script lang="ts">
	import { page } from '$app/stores';
	import type { Book, ReadingStatus, SortField, SortOrder } from '$lib/types';
	import { api } from '$lib/api';
	import BookCard from '$lib/components/BookCard.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';
	import SearchBar from '$lib/components/SearchBar.svelte';
	import AddBookModal from '$lib/components/AddBookModal.svelte';

	// Active tab from URL param, defaulting to want_to_read
	let activeStatus = $derived<ReadingStatus>(
		($page.url.searchParams.get('status') as ReadingStatus) ?? 'want_to_read'
	);

	let books = $state<Book[]>([]);
	let loading = $state(false);
	let searchQuery = $state('');
	let sort = $state<SortField>('date_added');
	let order = $state<SortOrder>('desc');

	let selectedBook = $state<Book | null>(null);
	let drawerOpen = $state(false);
	let addBookOpen = $state(false);

	async function fetchBooks() {
		loading = true;
		try {
			books = await api.books.list({
				status: activeStatus,
				q: searchQuery || undefined,
				sort,
				order
			});
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		// Re-fetch whenever any filter changes
		void activeStatus;
		void searchQuery;
		void sort;
		void order;
		fetchBooks();
	});

	function openDrawer(book: Book) {
		selectedBook = book;
		drawerOpen = true;
	}

	function handleSave(updated: Book) {
		books = books.map((b) => (b.id === updated.id ? updated : b));
	}

	function handleDelete(id: number) {
		books = books.filter((b) => b.id !== id);
	}

	function handleAdded(book: Book) {
		if (book.reading_status === activeStatus) {
			books = [book, ...books];
		}
		addBookOpen = false;
	}

	const STATUS_LABELS: Record<string, string> = {
		want_to_read: 'Want to Read',
		currently_reading: 'Currently Reading',
		read: 'Read'
	};
</script>

<div class="flex flex-col gap-4">
	<!-- Header row -->
	<div class="flex flex-col sm:flex-row sm:items-center gap-3">
		<h1 class="text-xl font-bold">{STATUS_LABELS[activeStatus]}</h1>
		<div class="flex items-center gap-2 flex-1">
			<SearchBar
				bind:value={searchQuery}
				placeholder="Search books…"
				onSearch={(q) => (searchQuery = q)}
			/>
		</div>
		<!-- Sort controls -->
		<div class="flex items-center gap-2 text-sm">
			<select class="select select-bordered select-xs" bind:value={sort}>
				<option value="date_added">Date added</option>
				<option value="rating">Rating</option>
			</select>
			<select class="select select-bordered select-xs" bind:value={order}>
				<option value="desc">Desc</option>
				<option value="asc">Asc</option>
			</select>
		</div>
		<button class="btn btn-primary btn-sm hidden sm:flex" onclick={() => (addBookOpen = true)}>
			+ Add Book
		</button>
	</div>

	<!-- Book grid -->
	{#if loading}
		<div class="flex justify-center py-16">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if books.length === 0}
		<div class="text-center py-16 text-base-content/40">
			<p class="text-4xl mb-2">📚</p>
			<p>No books here yet.</p>
			<button class="btn btn-primary btn-sm mt-4" onclick={() => (addBookOpen = true)}>Add your first book</button>
		</div>
	{:else}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
			{#each books as book (book.id)}
				<BookCard {book} onClick={openDrawer} />
			{/each}
		</div>
	{/if}
</div>

<!-- Book detail drawer -->
<BookDrawer
	bind:book={selectedBook}
	bind:open={drawerOpen}
	onSave={handleSave}
	onDelete={handleDelete}
/>

<!-- Add book modal (desktop button inside page) -->
<AddBookModal
	bind:open={addBookOpen}
	defaultStatus={activeStatus}
	onAdded={handleAdded}
/>
