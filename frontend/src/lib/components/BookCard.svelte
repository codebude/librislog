<script lang="ts">
	import type { Book } from '$lib/types';
	import StarRating from './StarRating.svelte';

	let { book, onClick }: { book: Book; onClick: (book: Book) => void } = $props();

	const STATUS_LABELS: Record<string, string> = {
		want_to_read: 'Want to Read',
		currently_reading: 'Reading',
		read: 'Read',
		did_not_finish: 'Did Not Finish'
	};

	const STATUS_BADGE: Record<string, string> = {
		want_to_read: 'badge-info',
		currently_reading: 'badge-warning',
		read: 'badge-success',
		did_not_finish: 'badge-error'
	};
</script>

<button
	class="card card-compact bg-base-100 shadow hover:shadow-md transition-shadow cursor-pointer w-full text-left"
	onclick={() => onClick(book)}
>
	<figure class="aspect-[2/3] bg-base-200 overflow-hidden">
		{#if book.cover_url}
			<img src={book.cover_url} alt="Cover of {book.title}" class="w-full h-full object-cover" />
		{:else}
			<div class="w-full h-full flex items-center justify-center text-base-content/30">
				<svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
				</svg>
			</div>
		{/if}
	</figure>
	<div class="card-body gap-1">
		<h2 class="card-title text-sm leading-snug line-clamp-2">{book.title}</h2>
		{#if book.author}
			<p class="text-xs text-base-content/60 truncate">{book.author}</p>
		{/if}
		<div class="flex items-center justify-between mt-1">
			<StarRating value={book.rating} readonly />
			<span class="badge badge-xs {STATUS_BADGE[book.reading_status]}">
				{STATUS_LABELS[book.reading_status]}
			</span>
		</div>
	</div>
</button>
