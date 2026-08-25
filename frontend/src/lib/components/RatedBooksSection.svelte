<script lang="ts">
	import type { Book, TopRatedBook } from '$lib/types';
	import { api } from '$lib/api';
	import { toasts } from '$lib/toasts';
	import { _ } from '$lib/i18n';
	import { formatAuthors } from '$lib/utils/authors';
	import BookDetailDialog from './BookDetailDialog.svelte';

	let { title, books }: { title: string; books: TopRatedBook[] } = $props();

	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let visibleCount = $state(10);

	const maxRating = 5;
	const step = 10;

	let visibleBooks = $derived(books.slice(0, visibleCount));
	let hasMore = $derived(visibleCount < books.length);

	function showMore() {
		visibleCount += step;
	}

	async function openCoverBook(bookId: number) {
		try {
			const book = await api.books.get(bookId);
			selectedBook = book;
			detailOpen = true;
		} catch (e: unknown) {
			const message = e instanceof Error ? e.message : String(e);
			toasts.add(message, 'error');
		}
	}

	function handleDelete(_bookId: number) {
		selectedBook = null;
		detailOpen = false;
	}
</script>

<div class="card bg-base-100 border border-base-200 shadow-sm">
	<div class="card-body">
		<h2 class="card-title text-base">{title}</h2>
		{#if books.length > 0}
			<div class="flex flex-wrap gap-2 sm:gap-4">
				{#each visibleBooks as book, idx}
					<div class="flex flex-col items-center w-[calc(50%-0.25rem)] sm:w-[calc(33.333%-0.5rem)] md:w-[calc(25%-0.75rem)] lg:w-[calc(20%-0.8rem)]">
						<span class="badge badge-primary badge-xs sm:badge-sm mb-1">{$_('statistics.rankedNumber', { values: { rank: idx + 1 } })}</span>
						<button
							type="button"
							class="cursor-pointer transition-all duration-200 hover:z-10 hover:-translate-y-1"
							aria-label={book.title}
							onclick={() => openCoverBook(book.book_id)}
						>
							<img
								src={book.cover_url ?? '/placeholder-cover.svg'}
								alt={book.title}
								class="h-20 sm:h-24 md:h-28 w-auto rounded shadow-sm ring-1 ring-base-200 bg-base-100 transition-shadow duration-200 hover:shadow-lg hover:shadow-primary/30 hover:ring-2 hover:ring-primary"
							/>
						</button>
						<div class="text-center mt-1 w-full min-w-0">
							<p class="text-xs sm:text-sm font-semibold truncate" title={book.title}>{book.title}</p>
							<p class="text-xs text-base-content/70 truncate" title={book.author ?? undefined}>{formatAuthors(book.authors, book.author ?? '-')}</p>
							<div class="flex items-center justify-center gap-0.5 text-warning">
								{#each Array(maxRating) as _, i}
									<span class="text-xs sm:text-sm">{i < book.rating ? '★' : '☆'}</span>
								{/each}
							</div>
						</div>
					</div>
				{/each}
			</div>
			{#if hasMore}
				<div class="flex justify-center mt-4">
					<button type="button" class="btn btn-outline btn-sm" onclick={showMore}>
						{$_('statistics.showMore')}
					</button>
				</div>
			{/if}
		{:else}
			<p class="text-base-content/70">{$_('statistics.noData')}</p>
		{/if}
	</div>
</div>

<BookDetailDialog bind:book={selectedBook} bind:open={detailOpen} onDelete={handleDelete} />
