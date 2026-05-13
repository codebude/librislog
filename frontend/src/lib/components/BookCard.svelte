<script lang="ts">
	import type { Book } from '$lib/types';
	import { _ } from '$lib/i18n';
	import StarRating from './StarRating.svelte';

	let {
		book,
		onClick,
		currentPage = 0
	}: {
		book: Book;
		onClick: (book: Book) => void;
		currentPage?: number;
	} = $props();

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

	const progressPercent = $derived(
		book.page_count && currentPage > 0 ? Math.round((currentPage / book.page_count) * 100) : 0
	);
</script>

<button
	class="card card-compact bg-base-100 shadow hover:shadow-md transition-shadow cursor-pointer w-full text-left"
	onclick={() => onClick(book)}
>
	<figure class="aspect-[2/3] bg-base-200 overflow-hidden">
		{#if book.cover_url}
			<img
				src={book.cover_url}
				alt={$_('book.coverOf', { values: { title: book.title } })}
				class="w-full h-full object-cover"
			/>
		{:else}
			<div class="w-full h-full flex items-center justify-center text-base-content/30">
				<svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
				</svg>
			</div>
		{/if}
	</figure>
	<div class="card-body gap-1 overflow-hidden">
		<h2 class="card-title text-sm leading-snug line-clamp-2">{book.title}</h2>
		{#if book.author}
			<p class="text-xs text-base-content/60 truncate">{book.author}</p>
		{/if}
		<div class="flex flex-wrap items-center gap-2 mt-1 min-w-0">
			<div class="shrink-0">
				<StarRating value={book.rating} readonly />
			</div>
			<span class="badge badge-xs {STATUS_BADGE[book.reading_status]} shrink-0 max-w-full overflow-hidden text-ellipsis whitespace-nowrap">
				{$_(STATUS_LABEL_KEYS[book.reading_status])}
			</span>
		</div>
		{#if progressPercent > 0}
			<div class="w-full h-1.5 bg-base-200 rounded-full mt-1 overflow-hidden">
				<div
					class="h-full bg-primary rounded-full transition-all duration-300"
					style="width: {progressPercent}%"
				></div>
			</div>
		{/if}
		<p class="text-[11px] text-base-content/50 mt-1">{$_('book.openDetailsHint')}</p>
	</div>
</button>
