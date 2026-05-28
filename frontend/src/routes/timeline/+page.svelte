<script lang="ts">
	import { onMount } from 'svelte';
	import dayjs from 'dayjs';
	import type { Book } from '$lib/types';
	import { api } from '$lib/api';
	import { _, locale } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import { shouldShowActionToast } from '$lib/errors';
	import { getTimezone } from '$lib/stores/timezone';
	import BookDetailDialog from '$lib/components/BookDetailDialog.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';

	const PAGE_SIZE = 40;

	let loading = $state(true);
	let loadingMore = $state(false);
	let hasMore = $state(true);
	let nextOffset = $state(0);
	let books = $state<Book[]>([]);
	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let drawerOpen = $state(false);
	let tz = $state('UTC');
	let loadMoreAnchor = $state<HTMLDivElement | null>(null);
	let observer: IntersectionObserver | null = null;
	const appLocale: string = $derived($locale ?? 'en');

	onMount(() => {
		tz = getTimezone();
		void loadTimeline();
		if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') return;
		observer = new IntersectionObserver(
			(entries) => {
				if (entries.some((e) => e.isIntersecting)) {
					void loadMoreTimeline();
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

	async function loadTimeline() {
		loading = true;
		try {
			const response = await api.books.list({
				status: 'read',
				sort: 'date_finished',
				order: 'desc',
				smart_sort: false,
				offset: 0,
				limit: PAGE_SIZE
			});
			books = response.books.filter((b) => b.date_finished !== null);
			nextOffset = response.books.length;
			hasMore = response.books.length === PAGE_SIZE;
			if (hasMore && books.length > 0) {
				await maybePrefillViewport();
			}
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : $_('common.actionFailed', { values: { action: 'load' } });
			if (shouldShowActionToast(msg)) {
				toasts.add(msg, 'error');
			}
			books = [];
		} finally {
			loading = false;
		}
	}

	async function maybePrefillViewport() {
		let safety = 0;
		while (
			hasMore &&
			!loadingMore &&
			document.documentElement.scrollHeight <= window.innerHeight + 240 &&
			safety < 4
		) {
			safety += 1;
			await loadMoreTimeline();
		}
	}

	async function loadMoreTimeline() {
		if (loadingMore || loading || !hasMore) return;
		loadingMore = true;
		try {
			const response = await api.books.list({
				status: 'read',
				sort: 'date_finished',
				order: 'desc',
				smart_sort: false,
				offset: nextOffset,
				limit: PAGE_SIZE
			});
			const filtered = response.books.filter((b) => b.date_finished !== null);
			books = [...books, ...filtered];
			nextOffset += response.books.length;
			hasMore = response.books.length === PAGE_SIZE;
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : $_('common.actionFailed', { values: { action: 'load' } });
			if (shouldShowActionToast(msg)) {
				toasts.add(msg, 'error');
			}
		} finally {
			loadingMore = false;
		}
	}

	let grouped = $derived.by(() => {
		const map = new Map<string, Book[]>();
		for (const b of books) {
			if (!b.date_finished) continue;
			const key = dayjs(b.date_finished).tz(tz).format('YYYY-MM');
			if (!map.has(key)) map.set(key, []);
			map.get(key)!.push(b);
		}
		return [...map.entries()].sort(([a], [b]) => b.localeCompare(a));
	});

	interface TimelineHeader { type: 'header'; key: string; dateFinished: string }
	interface TimelineBook { type: 'book'; book: Book }
	type TimelineItem = TimelineHeader | TimelineBook;

	let flatItems = $derived.by(() => {
		const items: TimelineItem[] = [];
		for (const [key, monthBooks] of grouped) {
			items.push({ type: 'header', key, dateFinished: monthBooks[0].date_finished! });
			for (const book of monthBooks) {
				items.push({ type: 'book', book });
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
		if (updated.reading_status !== 'read' || !updated.date_finished) {
			void loadTimeline();
			return;
		}
		books = books.map((b) => (b.id === updated.id ? updated : b));
	}

	function handleDelete(id: number) {
		detailOpen = false;
		drawerOpen = false;
		books = books.filter((b) => b.id !== id);
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
	{:else if books.length === 0}
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
			{#each flatItems as item, i (item.type === 'header' ? item.key : item.book.id)}
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
							{formatDay(item.book.date_finished!)}
						</div>
						<div class="timeline-middle">
							<svg class="text-primary h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
								<circle cx="10" cy="10" r="3" />
							</svg>
						</div>
						<div
							class="timeline-end timeline-box min-w-0 cursor-pointer hover:bg-base-200 transition-colors"
							onclick={() => openDetailView(item.book)}
							role="button"
							tabindex="0"
							onkeydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') {
									e.preventDefault();
									openDetailView(item.book);
								}
							}}
						>
							<div class="flex gap-3 items-start">
								{#if item.book.cover_url}
									<img
										src={item.book.cover_url}
										alt={item.book.title}
										class="w-10 h-14 object-cover rounded shrink-0"
									/>
								{/if}
								<div class="min-w-0">
									<p class="font-medium break-words">{item.book.title}</p>
									{#if item.book.author}
										<p class="text-sm text-base-content/70 break-words">{item.book.author}</p>
									{/if}
									{#if item.book.rating}
										<p class="text-warning text-sm">{stars(item.book.rating)}</p>
									{/if}
								</div>
							</div>
						</div>
					{/if}
					{#if i < flatItems.length - 1}<hr />{/if}
				</li>
			{/each}
		</ul>
		{#if hasMore}
			<div bind:this={loadMoreAnchor} class="h-1"></div>
		{/if}
		{#if loadingMore}
			<div class="flex justify-center py-4">
				<span class="loading loading-spinner loading-md"></span>
			</div>
		{/if}
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
