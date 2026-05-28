<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { _, locale } from '$lib/i18n';
	import { api } from '$lib/api';
	import type { Book, DailyPagesResponse, StatisticsResponse } from '$lib/types';
	import { toasts } from '$lib/toasts';
	import { formatLanguageCode } from '$lib/utils/language';
	import BarChart from '$lib/components/BarChart.svelte';
	import CalendarHeatmap from '$lib/components/CalendarHeatmap.svelte';
	import BookDetailDialog from '$lib/components/BookDetailDialog.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';
	import { RotateCcw } from '@lucide/svelte';

	type Segment = {
		label: string;
		value: number;
		className: string;
	};

	type Point = {
		label: string;
		value: number;
	};

	let loading = $state(true);
	let stats = $state<StatisticsResponse | null>(null);
	let calendarData = $state<DailyPagesResponse | null>(null);
	let calendarLoading = $state(false);
	let activeBookId = $state<number | null>(null);
	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let drawerOpen = $state(false);
	let pagesChart = $state<import('chart.js').Chart<'bar'> | null>(null);
	let booksMonthChart = $state<import('chart.js').Chart<'bar'> | null>(null);
	let booksYearChart = $state<import('chart.js').Chart<'bar'> | null>(null);

	onMount(() => {
		let active = true;
		void loadStatistics(() => active);
		void loadCalendarData(() => active);
		return () => {
			active = false;
		};
	});

	async function loadStatistics(isActive: () => boolean) {
		loading = true;
		try {
			const data = await api.statistics.get();
			if (isActive()) {
				stats = data;
			}
		} catch (e: unknown) {
			if (isActive()) {
				const message = e instanceof Error ? e.message : $_('common.actionFailed', { values: { action: 'load' } });
				toasts.add(message, 'error');
				stats = null;
			}
		} finally {
			if (isActive()) {
				loading = false;
			}
		}
	}

	async function loadCalendarData(isActive: () => boolean) {
		calendarLoading = true;
		try {
			const data = await api.statistics.getPagesPerDay(365);
			if (isActive()) {
				calendarData = data;
			}
		} catch (e: unknown) {
			if (isActive()) {
				const message = e instanceof Error ? e.message : String(e);
				console.error('Failed to load calendar data:', message);
				calendarData = null;
			}
		} finally {
			if (isActive()) {
				calendarLoading = false;
			}
		}
	}

	const appLocale: string = $derived($locale ?? 'en');

	function formatNumber(value: number | null | undefined, maximumFractionDigits = 2, minimumFractionDigits = 0): string {
		if (value === null || value === undefined) return '-';
		return new Intl.NumberFormat(appLocale, { maximumFractionDigits, minimumFractionDigits }).format(value);
	}

	function formatMonthLabel(value: string | null | undefined): string {
		if (!value) return '-';
		const [year, month] = value.split('-');
		const dt = new Date(Date.UTC(Number(year), Number(month) - 1, 1));
		if (Number.isNaN(dt.getTime())) return value;
		return dt.toLocaleDateString(appLocale, { month: 'short', year: 'numeric' });
	}

	function safePercentage(value: number, sum: number): number {
		if (sum <= 0) return 0;
		return (value / sum) * 100;
	}

	const languageSegments = $derived.by<Segment[]>(() => {
		if (!stats) return [];
		const colors = ['bg-primary', 'bg-secondary', 'bg-accent', 'bg-info', 'bg-success', 'bg-warning', 'bg-error'];
		return stats.language_distribution.map((entry, idx) => ({
			label: entry.language ? formatLanguageCode(entry.language, appLocale) : $_('statistics.unknownLanguage'),
			value: entry.count,
			className: colors[idx % colors.length]
		}));
	});

	const statusSegments = $derived.by<Segment[]>(() => {
		if (!stats) return [];
		return [
			{ label: $_('status.want_to_read'), value: stats.status_distribution.want_to_read, className: 'bg-info' },
			{ label: $_('status.currently_reading'), value: stats.status_distribution.currently_reading, className: 'bg-warning' },
			{ label: $_('status.read'), value: stats.status_distribution.read, className: 'bg-success' },
			{ label: $_('status.did_not_finish'), value: stats.status_distribution.did_not_finish, className: 'bg-error' }
		].filter((item) => item.value > 0);
	});

	const pageSegments = $derived.by<Segment[]>(() => {
		if (!stats) return [];
		return [
			{ label: $_('statistics.pagesToRead'), value: stats.page_buckets.pages_to_read, className: 'bg-info' },
			{ label: $_('statistics.pagesRead'), value: stats.page_buckets.pages_read, className: 'bg-success' },
			{ label: $_('statistics.pagesWasted'), value: stats.page_buckets.pages_wasted, className: 'bg-error' }
		].filter((item) => item.value > 0);
	});

	function toPoints(source: Array<{ month: string; pages: number }> | Array<{ month: string; count: number }>): Point[] {
		return source.map((entry) => ({
			label: formatMonthLabel(entry.month),
			value: 'pages' in entry ? entry.pages : entry.count
		}));
	}

	function toYearPoints(source: Array<{ year: number; count: number }>): Point[] {
		return source.map((entry) => ({
			label: String(entry.year),
			value: entry.count
		}));
	}

	function openCoverBook(bookId: number) {
		void loadAndOpenBook(bookId);
	}

	async function loadAndOpenBook(bookId: number) {
		try {
			const book = await api.books.get(bookId);
			selectedBook = book;
			detailOpen = true;
		} catch (e: unknown) {
			const message = e instanceof Error ? e.message : String(e);
			toasts.add(message, 'error');
		}
	}

	function openEditFromDetail(book: Book) {
		selectedBook = book;
		detailOpen = false;
		drawerOpen = true;
	}

	function handleDelete(_bookId: number) {
		selectedBook = null;
		detailOpen = false;
	}

	function openAuthorSearch(author: string) {
		const qs = new URLSearchParams({ q: author });
		void goto(`/dashboard?${qs.toString()}`);
	}

	const pagesReadPoints = $derived(stats ? toPoints(stats.pages_read_per_month) : []);
	const booksByMonthPoints = $derived(stats ? toPoints(stats.books_finished_per_month) : []);
	const booksByYearPoints = $derived(stats ? toYearPoints(stats.books_finished_per_year) : []);

	function total(segments: Segment[]): number {
		return segments.reduce((acc, curr) => acc + curr.value, 0);
	}
</script>

<div class="flex flex-col gap-6">
	<div class="hero rounded-2xl bg-base-100 shadow-sm border border-base-200">
		<div class="hero-content text-center py-10">
			<div class="max-w-2xl">
				<h1 class="text-2xl sm:text-3xl font-bold tracking-tight">{$_('statistics.title')}</h1>
				<p class="text-base-content/70 mt-2">{$_('statistics.subtitle')}</p>
			</div>
		</div>
	</div>

	{#if loading}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body items-center py-10">
				<span class="loading loading-spinner loading-lg"></span>
				<p>{$_('statistics.loading')}</p>
			</div>
		</div>
	{:else if !stats}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body py-10 text-center">
				<p>{$_('statistics.noData')}</p>
			</div>
		</div>
	{:else}
		{@const s = stats}
		{#if s.status_distribution.want_to_read + s.status_distribution.currently_reading + s.status_distribution.read + s.status_distribution.did_not_finish === 0}
			<div class="card bg-base-100 border border-base-200 shadow-sm">
				<div class="card-body py-10 text-center">
					<p>{$_('statistics.noData')}</p>
				</div>
			</div>
		{:else}
		<div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
			<div class="stat bg-base-100 rounded-2xl shadow-sm border border-base-200">
				<div class="stat-title">{$_('statistics.avgBooksPerMonth')}</div>
				<div class="stat-value text-primary text-2xl">{formatNumber(stats.avg_books_per_month, 2, 1)}</div>
			</div>
			<div class="stat bg-base-100 rounded-2xl shadow-sm border border-base-200">
				<div class="stat-title">{$_('statistics.busiestMonth')}</div>
				<div class="stat-value text-success text-2xl">{formatMonthLabel(stats.busiest_month)}</div>
				<div class="stat-desc">{$_('statistics.booksCount', { values: { count: stats.busiest_month_count ?? 0 } })}</div>
			</div>
			<div class="stat bg-base-100 rounded-2xl shadow-sm border border-base-200">
				<div class="stat-title">{$_('statistics.avgPageCount')}</div>
				<div class="stat-value text-info text-2xl">{formatNumber(stats.avg_page_count, 0)}</div>
			</div>
			<div class="stat bg-base-100 rounded-2xl shadow-sm border border-base-200">
				<div class="stat-title">{$_('statistics.mostPopularLanguage')}</div>
				<div class="stat-value text-warning text-2xl">
					{stats.most_popular_language ? formatLanguageCode(stats.most_popular_language, appLocale) : '-'}
				</div>
				<div class="stat-desc">{formatNumber(stats.most_popular_language_count, 0)}</div>
			</div>
		</div>

		<div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
			<div class="card bg-base-100 border border-base-200 shadow-sm">
				<div class="card-body">
					<h2 class="card-title text-base">{$_('statistics.languageDistribution')}</h2>
					<div role="img" aria-label={$_('statistics.languageDistribution')} class="flex h-8 w-full overflow-hidden rounded-xl bg-base-200">
						{#if total(languageSegments) === 0}
							<div class="w-full h-full"></div>
						{:else}
							{#each languageSegments as segment}
								<div class={`h-full ${segment.className}`} style={`width:${safePercentage(segment.value, total(languageSegments))}%`}></div>
							{/each}
						{/if}
					</div>
					<div class="flex flex-wrap gap-3 text-sm">
						{#each languageSegments as segment}
							<div class="flex items-center gap-2">
								<span class={`inline-block w-3 h-3 rounded ${segment.className}`}></span>
								<span>{segment.label}: {formatNumber(segment.value, 0)}</span>
							</div>
						{/each}
					</div>
				</div>
			</div>

			<div class="card bg-base-100 border border-base-200 shadow-sm">
				<div class="card-body">
					<h2 class="card-title text-base">{$_('statistics.statusDistribution')}</h2>
					<div role="img" aria-label={$_('statistics.statusDistribution')} class="flex h-8 w-full overflow-hidden rounded-xl bg-base-200">
						{#if total(statusSegments) === 0}
							<div class="w-full h-full"></div>
						{:else}
							{#each statusSegments as segment}
								<div class={`h-full ${segment.className}`} style={`width:${safePercentage(segment.value, total(statusSegments))}%`}></div>
							{/each}
						{/if}
					</div>
					<div class="flex flex-wrap gap-3 text-sm">
						{#each statusSegments as segment}
							<div class="flex items-center gap-2">
								<span class={`inline-block w-3 h-3 rounded ${segment.className}`}></span>
								<span>{segment.label}: {formatNumber(segment.value, 0)}</span>
							</div>
						{/each}
					</div>
				</div>
			</div>
		</div>

		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body">
				<h2 class="card-title text-base">{$_('statistics.pageBuckets')}</h2>
				<div role="img" aria-label={$_('statistics.pageBuckets')} class="flex h-8 w-full overflow-hidden rounded-xl bg-base-200">
					{#if total(pageSegments) === 0}
						<div class="w-full h-full"></div>
					{:else}
						{#each pageSegments as segment}
							<div class={`h-full ${segment.className}`} style={`width:${safePercentage(segment.value, total(pageSegments))}%`}></div>
						{/each}
					{/if}
				</div>
				<div class="flex flex-wrap gap-3 text-sm">
					{#each pageSegments as segment}
						<div class="flex items-center gap-2">
							<span class={`inline-block w-3 h-3 rounded ${segment.className}`}></span>
							<span>{segment.label}: {formatNumber(segment.value, 0)}</span>
						</div>
					{/each}
				</div>
				<p class="text-xs text-base-content/70">{$_('statistics.pagesWastedFootnote')}</p>
			</div>
		</div>

		<div class="grid grid-cols-1 gap-4">
			<div class="card bg-base-100 border border-base-200 shadow-sm">
				<div class="card-body relative">
					<h2 class="card-title text-base pr-12">{$_('statistics.pagesReadPerMonth')}</h2>
					<button
						type="button"
						class="btn btn-ghost btn-xs absolute top-4 right-4 opacity-60 hover:opacity-100 z-10"
						title={$_('statistics.resetZoom')}
						onclick={() => pagesChart?.resetZoom()}
						disabled={!pagesChart}
					>
						<RotateCcw class="h-4 w-4" />
					</button>
					<BarChart
						labels={pagesReadPoints.map((p) => p.label)}
						data={pagesReadPoints.map((p) => p.value)}
						label={$_('statistics.pagesReadPerMonth')}
						color="primary"
						emptyText={$_('statistics.noData')}
						onChart={(c) => pagesChart = c}
					/>
				</div>
			</div>

			<div class="card bg-base-100 border border-base-200 shadow-sm">
				<div class="card-body relative">
					<h2 class="card-title text-base pr-12">{$_('statistics.booksFinishedPerMonth')}</h2>
					<button
						type="button"
						class="btn btn-ghost btn-xs absolute top-4 right-4 opacity-60 hover:opacity-100 z-10"
						title={$_('statistics.resetZoom')}
						onclick={() => booksMonthChart?.resetZoom()}
						disabled={!booksMonthChart}
					>
						<RotateCcw class="h-4 w-4" />
					</button>
					<BarChart
						labels={booksByMonthPoints.map((p) => p.label)}
						data={booksByMonthPoints.map((p) => p.value)}
						label={$_('statistics.booksFinishedPerMonth')}
						color="secondary"
						emptyText={$_('statistics.noData')}
						onChart={(c) => booksMonthChart = c}
					/>
				</div>
			</div>

			<div class="card bg-base-100 border border-base-200 shadow-sm">
				<div class="card-body relative">
					<h2 class="card-title text-base pr-12">{$_('statistics.booksFinishedPerYear')}</h2>
					<button
						type="button"
						class="btn btn-ghost btn-xs absolute top-4 right-4 opacity-60 hover:opacity-100 z-10"
						title={$_('statistics.resetZoom')}
						onclick={() => booksYearChart?.resetZoom()}
						disabled={!booksYearChart}
					>
						<RotateCcw class="h-4 w-4" />
					</button>
					<BarChart
						labels={booksByYearPoints.map((p) => p.label)}
						data={booksByYearPoints.map((p) => p.value)}
						label={$_('statistics.booksFinishedPerYear')}
						color="accent"
						emptyText={$_('statistics.noData')}
						onChart={(c) => booksYearChart = c}
					/>
				</div>
			</div>
		</div>

		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body gap-4">
				<h2 class="card-title text-base">{$_('statistics.topAuthors')}</h2>
				{#if stats.top_authors.length > 0}
					<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
						{#each stats.top_authors as author, idx}
							<div class="rounded-xl border border-base-200 p-3 bg-base-200/40">
								<div class="flex items-center gap-2 mb-2">
									<span class="badge badge-primary badge-sm">{$_('statistics.rankedNumber', { values: { rank: idx + 1 } })}</span>
									<button
										type="button"
										class="font-semibold text-base leading-tight truncate hover:underline text-left"
										onclick={() => openAuthorSearch(author.author)}
									>
										{author.author}
									</button>
								</div>
								<div class="text-sm text-base-content/70 mb-2">
									{$_('statistics.booksCount', { values: { count: author.book_count } })}
								</div>
								{#if author.covers.length > 0}
									<!-- Covers overlap with -ml-3 to save space, pl-3 keeps the first cover fully visible. -->
									<div
										class="flex items-end overflow-hidden pt-4 pb-1 pl-3"
										role="group"
										aria-label={$_('statistics.coversForAuthor', { values: { author: author.author } })}
										ontouchmove={(e) => {
											const touch = e.touches[0];
											const el = document.elementFromPoint(touch.clientX, touch.clientY);
											const button = el?.closest('[data-book-id]');
											if (button) {
												activeBookId = parseInt(button.getAttribute('data-book-id')!, 10);
											} else {
												activeBookId = null;
											}
										}}
										ontouchend={() => { activeBookId = null; }}
										ontouchcancel={() => { activeBookId = null; }}
									>
										{#each author.covers as cover, coverIdx}
										<button
											type="button"
											class="cursor-pointer transition-all duration-200 hover:z-50 {coverIdx > 0 ? '-ml-3' : ''} hover:-translate-y-1 {activeBookId === cover.book_id ? 'z-50 -translate-y-1' : ''}"
											style:z-index={activeBookId === cover.book_id ? 50 : coverIdx + 1}
											data-book-id={cover.book_id}
											onclick={() => openCoverBook(cover.book_id)}
										>
											<img
												src={cover.cover_url}
												alt={$_('book.coverForAuthor', { values: { author: author.author, index: coverIdx + 1 } })}
												class="h-24 w-auto rounded shadow-sm ring-1 ring-base-200 bg-base-100 transition-shadow duration-200 hover:shadow-lg hover:shadow-primary/30 hover:ring-2 hover:ring-primary {activeBookId === cover.book_id ? 'shadow-lg shadow-primary/30 ring-2 ring-primary' : ''}"
											/>
											</button>
										{/each}
									</div>
								{:else}
									<p class="text-sm text-base-content/60">{$_('statistics.noData')}</p>
								{/if}
							</div>
						{/each}
					</div>
				{:else}
					<p class="text-base-content/70">{$_('statistics.noData')}</p>
				{/if}
			</div>
		</div>

		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body">
				<h2 class="card-title text-base">{$_('statistics.pagesReadCalendar')}</h2>
				{#if calendarLoading}
					<div class="flex items-center justify-center h-40">
						<span class="loading loading-spinner loading-md"></span>
					</div>
				{:else if calendarData}
					<CalendarHeatmap data={calendarData.data} />
					<div class="flex flex-wrap gap-4 text-sm text-base-content/70 mt-2">
						<span>
							<strong>{formatNumber(calendarData.total_pages, 0)}</strong>
							{$_('statistics.pagesOver')}
							<strong>{calendarData.total_days}</strong>
							{$_('statistics.daysLabel')}
						</span>
						<span>
							{$_('statistics.avgPerDay')}
							<strong>{formatNumber(calendarData.total_pages / Math.max(calendarData.days_with_activity, 1), 1)}</strong>
							{$_('statistics.pagesPerDay')}
						</span>
						<span>
							{$_('statistics.avgPerDayAll')}
							<strong>{formatNumber(calendarData.total_pages / Math.max(calendarData.total_days, 1), 1)}</strong>
							{$_('statistics.pagesPerDay')}
						</span>
					</div>
				{:else}
					<div class="text-center py-8 text-base-content/50">
						<p>{$_('statistics.noCalendarData')}</p>
					</div>
				{/if}
			</div>
		</div>
		{/if}
	{/if}
</div>

<BookDetailDialog
	bind:book={selectedBook}
	bind:open={detailOpen}
	onEdit={openEditFromDetail}
	onDelete={handleDelete}
/>

<BookDrawer bind:book={selectedBook} bind:open={drawerOpen} />
