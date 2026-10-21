<script lang="ts">
	import { onMount } from 'svelte';
	import dayjs from 'dayjs';
	import type { Book, TimelineSessionEntry } from '#lib/types.js';
	import { api } from '#lib/api.js';
	import { _, locale } from '#lib/i18n/index.js';
	import { toasts } from '#lib/toasts.js';
	import { shouldShowActionToast } from '#lib/errors.js';
	import { getTimezone } from '#lib/stores/timezone.js';
	import { formatAuthors } from '#lib/utils/authors.js';
	import BookDetailDialog from '#lib/components/BookDetailDialog.svelte';
	import BookDrawer from '#lib/components/BookDrawer.svelte';

	let loading = $state(true);
	let entries = $state<TimelineSessionEntry[]>([]);
	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let drawerOpen = $state(false);
	let tz = $state('UTC');
	const appLocale: string = $derived($locale ?? 'en');

	onMount(() => {
		tz = getTimezone();
		void loadTimeline();
	});

	async function loadTimeline() {
		loading = true;
		try {
			entries = await api.books.sessions.completed();
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : $_('common.actionFailed', { values: { action: 'load' } });
			if (shouldShowActionToast(msg)) {
				toasts.add(msg, 'error');
			}
			entries = [];
		} finally {
			loading = false;
		}
	}

	let grouped = $derived.by(() => {
		const map = new Map<string, TimelineSessionEntry[]>();
		for (const entry of entries) {
			if (!entry.date_finished) continue;
			const key = dayjs(entry.date_finished).tz(tz).format('YYYY-MM');
			if (!map.has(key)) map.set(key, []);
			map.get(key)!.push(entry);
		}
		return [...map.entries()].sort(([a], [b]) => b.localeCompare(a));
	});

	interface TimelineHeader { type: 'header'; key: string; dateFinished: string }
	interface TimelineItem { type: 'entry'; entry: TimelineSessionEntry }
	type TimelineRow = TimelineHeader | TimelineItem;

	let flatItems = $derived.by(() => {
		const items: TimelineRow[] = [];
		for (const [key, monthEntries] of grouped) {
			items.push({ type: 'header', key, dateFinished: monthEntries[0].date_finished! });
			for (const entry of monthEntries) {
				items.push({ type: 'entry', entry });
			}
		}
		return items;
	});

	function formatMonthYear(iso: string): string {
		return dayjs(iso).tz(tz).toDate().toLocaleDateString(appLocale, {
			month: 'short',
			year: 'numeric'
		});
	}

	function formatDay(iso: string): string {
		return dayjs(iso).tz(tz).toDate().toLocaleDateString(appLocale, {
			month: 'short',
			day: 'numeric'
		});
	}

	function stars(rating: number | null): string {
		if (rating === null || rating < 1) return '';
		return '★'.repeat(rating) + '☆'.repeat(5 - rating);
	}

	async function openDetailView(entry: TimelineSessionEntry) {
		try {
			selectedBook = await api.books.get(entry.book_id);
			detailOpen = true;
			drawerOpen = false;
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : String(e);
			toasts.add(msg, 'error');
		}
	}

	function openEditFromDetail(book: Book) {
		selectedBook = book;
		detailOpen = false;
		drawerOpen = true;
	}

	function handleSave(updated: Book) {
		void loadTimeline();
	}

	function handleDelete(id: number) {
		detailOpen = false;
		drawerOpen = false;
		entries = entries.filter((e) => e.book_id !== id);
	}
</script>

<div class="flex flex-col gap-6">
	<div class="hero bg-base-100 rounded-box shadow-sm p-6">
		<div class="hero-content text-center p-0">
			<div class="max-w-md">
				<h1 class="text-2xl font-bold">{$_('timeline.title')}</h1>
				<p class="text-base-content/70 mt-2">{$_('timeline.subtitle')}</p>
				<a href="/library?status=read" class="btn btn-ghost btn-sm mt-3">{$_('timeline.viewInLibrary')}</a>
			</div>
		</div>
	</div>

	{#if loading}
		<div class="flex justify-center py-16">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if entries.length === 0}
		<div class="hero bg-base-100 rounded-box shadow-sm p-12">
			<div class="hero-content text-center">
				<div class="max-w-md">
					<p class="text-base-content/70">{$_('timeline.noReadBooks')}</p>
					<a href="/library" class="btn btn-primary btn-sm mt-4">{$_('timeline.goToLibrary')}</a>
				</div>
			</div>
		</div>
	{:else}
		<ul class="timeline timeline-vertical timeline-snap-icon overflow-x-auto max-w-full">
			{#each flatItems as item, i (item.type === 'header' ? item.key : item.entry.session_id)}
				<li>
					{#if i > 0}<hr />{/if}
					{#if item.type === 'header'}
						<div class="timeline-start text-base font-semibold">
							{formatMonthYear(item.dateFinished)}
						</div>
						<div class="timeline-middle">
							<svg class="text-primary h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
								<circle cx="10" cy="10" r="5" />
							</svg>
						</div>
					{:else}
						<div class="timeline-start text-xs sm:text-sm">
							{formatDay(item.entry.date_finished!)}
						</div>
						<div class="timeline-middle">
							<svg class="text-primary h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
								<circle cx="10" cy="10" r="3" />
							</svg>
						</div>
						<div
							class="timeline-end timeline-box min-w-0 cursor-pointer hover:bg-base-200 transition-colors"
							onclick={() => void openDetailView(item.entry)}
							role="button"
							tabindex="0"
							onkeydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') {
									e.preventDefault();
									void openDetailView(item.entry);
								}
							}}
						>
							<div class="flex gap-3 items-start">
								{#if item.entry.cover_url}
									<img
										src={item.entry.cover_url}
										alt={item.entry.title}
										class="w-10 h-14 object-cover rounded shrink-0"
									/>
								{/if}
								<div class="min-w-0">
									<p class="font-medium break-words">{item.entry.title}</p>
									{#if item.entry.author}
										<p class="text-sm text-base-content/70 break-words">{formatAuthors(item.entry.authors, item.entry.author)}</p>
									{/if}
									{#if item.entry.rating}
										<p class="text-warning text-sm">{stars(item.entry.rating)}</p>
									{/if}
									{#if item.entry.is_reread}
										<span class="badge badge-xs badge-outline badge-primary mt-1">{$_('timeline.reread')}</span>
									{/if}
								</div>
							</div>
						</div>
					{/if}
					{#if i < flatItems.length - 1}<hr />{/if}
				</li>
			{/each}
		</ul>
	{/if}
</div>

<BookDetailDialog bind:book={selectedBook} bind:open={detailOpen} onEdit={openEditFromDetail} onDelete={handleDelete} />

<BookDrawer bind:book={selectedBook} bind:open={drawerOpen} onSave={handleSave} />

<style>
	@media (max-width: 640px) {
		ul.timeline > li {
			grid-template-columns: 1.5rem 1fr !important;
			grid-template-rows: auto auto auto !important;
		}
		ul.timeline > li > .timeline-start {
			grid-column: 2 !important;
			grid-row: 1 !important;
			justify-self: start !important;
			text-align: left !important;
			padding: 0 0 0.75rem 0 !important;
		}
		ul.timeline > li > .timeline-middle {
			grid-column: 1 !important;
			grid-row: 1 / -1 !important;
			align-self: center !important;
			z-index: 2 !important;
		}
		ul.timeline > li > .timeline-end {
			grid-column: 2 !important;
			grid-row: 2 !important;
			justify-self: stretch !important;
			align-self: start !important;
			padding-top: 0.75rem !important;
		}
		ul.timeline {
			background-image: linear-gradient(to bottom, var(--color-base-300), var(--color-base-300));
			background-repeat: no-repeat;
			background-position: 12px 0;
			background-size: 4px 100%;
		}
		ul.timeline > li > hr {
			display: none !important;
		}
	}
</style>
