<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { base } from '$app/paths';
	import { _, setLocale, SUPPORTED_LOCALES, locale } from '$lib/i18n';
	import { api } from '$lib/api';
	import AnimalAvatar from '$lib/components/AnimalAvatar.svelte';
	import { Moon, Palette, Star, Sun } from '@lucide/svelte';
	import {
		applyThemeToDocument,
		cycleTheme,
		getThemeMode,
		saveThemeToStorage,
		type ThemeMode
	} from '$lib/stores/theme';
	import { getTimezone } from '$lib/stores/timezone';
	import { formatDate } from '$lib/date';
	import { formatAuthors } from '$lib/utils/authors';
	import { formatLanguageCode } from '$lib/utils/language';
	import {
		PUBLIC_PROFILE_SECTIONS,
		PUBLIC_PROFILE_STATISTICS,
		PUBLIC_PROFILE_STATISTICS_GROUPS
	} from '$lib/publicProfile/sections';
	import type { PublicProfileBook, PublicProfileResponse, PublicProfileSectionKey } from '$lib/types';

	const GITHUB_URL = 'https://github.com/codebude/librislog';

	const GITHUB_ANCHOR = `<a class="link link-neutral ml-1" href="${GITHUB_URL}" target="_blank" rel="noopener noreferrer">LibrisLog</a>`;

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

	const MEDIUM_LABEL_KEYS: Record<string, string> = {
		'Print': 'medium.print',
		'eBook': 'medium.ebook',
		'Audiobook': 'medium.audiobook',
		'Comic / Graphic Novel': 'medium.comic_graphic_novel',
		'Magazine / Newspaper': 'medium.magazine_newspaper'
	};

	const DIST_COLORS = ['bg-primary', 'bg-secondary', 'bg-accent', 'bg-info', 'bg-success', 'bg-warning', 'bg-error'];

	const THEME_ICONS: Record<ThemeMode, typeof Sun> = {
		light: Sun,
		dark: Moon,
		custom: Palette
	};

	let profile = $state<PublicProfileResponse | null>(null);
	let status = $state<'loading' | 'ready' | 'not_found' | 'login_required' | 'error'>('loading');
	let tz = $state('UTC');
	let currentThemeMode = $state<ThemeMode>(getThemeMode());
	let lastReadLimit = $state(5);
	let libraryLimit = $state(8);
	let libraryQuery = $state('');
	let timelineLimit = $state(5);
	let trendRange = $state<'12months' | '3years' | 'alltime'>('12months');
	let previousLocale = $state<string | null>(null);

	const ThemeIcon = $derived(THEME_ICONS[currentThemeMode] ?? Sun);
	const appLocale = $derived($locale ?? 'en');

	function toggleTheme() {
		currentThemeMode = cycleTheme();
		applyThemeToDocument();
		saveThemeToStorage();
	}

	function formatNumber(value: number | null | undefined, maximumFractionDigits = 2): string {
		if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
		return new Intl.NumberFormat(appLocale, { maximumFractionDigits }).format(value);
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
		return Math.min(100, Math.max(3, (value / sum) * 100));
	}

	function actualPercentage(value: number, sum: number): number {
		return sum > 0 ? (value / sum) * 100 : 0;
	}

	async function load() {
		status = 'loading';
		try {
			profile = await api.publicProfile.get($page.params.token ?? '');
			if (profile.language && SUPPORTED_LOCALES.includes(profile.language as (typeof SUPPORTED_LOCALES)[number])) {
				previousLocale = $locale ?? null;
				setLocale(profile.language as (typeof SUPPORTED_LOCALES)[number]);
			}
			status = 'ready';
		} catch (e: unknown) {
			const err = e as Error & { status?: number };
			if (err.status === 401) {
				status = 'login_required';
			} else if (err.status === 404) {
				status = 'not_found';
			} else {
				status = 'error';
			}
		}
	}

	onMount(() => {
		tz = getTimezone();
		void load();
	});

	onDestroy(() => {
		if (previousLocale && SUPPORTED_LOCALES.includes(previousLocale as (typeof SUPPORTED_LOCALES)[number])) {
			setLocale(previousLocale as (typeof SUPPORTED_LOCALES)[number]);
		}
	});

	function hasSection(key: PublicProfileSectionKey): boolean {
		return profile?.visibility_config.sections.includes(key) ?? false;
	}

	function statValue(key: string): unknown {
		return profile?.statistics?.[key];
	}

	const currentlyReading = $derived(
		(profile?.books ?? []).filter((b) => b.reading_status === 'currently_reading')
	);

	const lastReadAll = $derived(
		(profile?.books ?? [])
			.filter((b) => b.reading_status === 'read' && b.date_finished)
			.sort((a, b) => (a.date_finished! < b.date_finished! ? 1 : -1))
	);

	const lastRead = $derived(lastReadAll.slice(0, lastReadLimit));

	const timelineBooks = $derived(
		(profile?.books ?? [])
			.filter((b) => b.reading_status === 'read' && b.date_finished)
			.sort((a, b) => (a.date_finished! < b.date_finished! ? -1 : 1))
	);

	const libraryBooks = $derived(profile?.books ?? []);

	const filteredBooks = $derived(
		libraryBooks.filter((b) => {
			const q = libraryQuery.trim().toLowerCase();
			if (!q) return true;
			return b.title.toLowerCase().includes(q) || (b.authors ?? []).join(' ').toLowerCase().includes(q);
		})
	);

	const timelineMonths = $derived(
		[...timelineBooks.slice(-timelineLimit).reduce((map, book) => {
			const key = book.date_finished!.slice(0, 7);
			if (!map.has(key)) map.set(key, []);
			map.get(key)!.push(book);
			return map;
		}, new Map<string, PublicProfileBook[]>())]
			.sort(([a], [b]) => (a < b ? 1 : -1))
	);

	function timelineHiddenCount(monthKey: string, visibleCount: number): number {
		return timelineBooks.filter((book) => book.date_finished!.slice(0, 7) === monthKey).length - visibleCount;
	}

	const summaryStats = $derived(PUBLIC_PROFILE_STATISTICS.filter((s) => s.group === 'summary' && statValue(s.key) !== undefined).map((s) => s.key));
	const distributionStats = $derived(PUBLIC_PROFILE_STATISTICS.filter((s) => s.group === 'distribution' && statValue(s.key) !== undefined).map((s) => s.key));
	const trendStats = $derived(PUBLIC_PROFILE_STATISTICS.filter((s) => s.group === 'trends' && statValue(s.key) !== undefined).map((s) => s.key));
	const ratingStats = $derived(PUBLIC_PROFILE_STATISTICS.filter((s) => s.group === 'ratings' && statValue(s.key) !== undefined).map((s) => s.key));
	const ratingSummaryKeys = $derived(ratingStats.filter((key) => key === 'books_with_rating' || key === 'books_without_rating' || key === 'average_rating'));
	const ratedBookKeys = $derived(ratingStats.filter((key) => key === 'top_rated_books' || key === 'worst_rated_books'));

	function distributionRows(key: string): { label: string; value: number; className: string }[] {
		const raw = statValue(key) as Record<keyof Record<string, number> | string, unknown> | undefined;
		if (!raw) return [];
		if (key === 'language_distribution') {
			const list = raw as unknown as { language: string | null; count: number }[];
			return list.map((entry, idx) => ({
				label: entry.language ? formatLanguageCode(entry.language, appLocale) : $_('statistics.unknownLanguage'),
				value: entry.count,
				className: DIST_COLORS[idx % DIST_COLORS.length]
			}));
		}
		if (key === 'medium_distribution') {
			const list = raw as unknown as { medium: string | null; count: number }[];
			return list.map((entry, idx) => ({
				label: entry.medium ? $_(MEDIUM_LABEL_KEYS[entry.medium] ?? entry.medium) : $_('statistics.unknownMedium'),
				value: entry.count,
				className: DIST_COLORS[idx % DIST_COLORS.length]
			}));
		}
		const mappings: Record<string, [string, string?][]> = {
			status_distribution: [
				[$_('status.want_to_read'), 'bg-info'],
				[$_('status.currently_reading'), 'bg-warning'],
				[$_('status.read'), 'bg-success'],
				[$_('status.did_not_finish'), 'bg-error']
			],
			acquisition_status_distribution: [
				[$_('acquisition.owned'), 'bg-primary'],
				[$_('acquisition.borrowed'), 'bg-secondary'],
				[$_('acquisition.digital_access'), 'bg-info'],
				[$_('acquisition.to_acquire'), 'bg-warning']
			],
			page_buckets: [
				[$_('statistics.pagesToRead'), 'bg-info'],
				[$_('statistics.pagesRead'), 'bg-success'],
				[$_('statistics.pagesWasted'), 'bg-error']
			]
		};
		const fixed = mappings[key] ?? [];
		const direct = (raw as Record<string, number>);
		if (key === 'status_distribution') {
			return (mappings.status_distribution as [string, string][])
				.map(([label, className], idx) => ({
					label,
					value: direct[['want_to_read', 'currently_reading', 'read', 'did_not_finish'][idx]],
					className
				}))
				.filter((row) => row.value > 0);
		}
		if (key === 'acquisition_status_distribution') {
			return (mappings.acquisition_status_distribution as [string, string][])
				.map(([label, className], idx) => ({
					label,
					value: direct[['owned', 'borrowed', 'digital_access', 'to_acquire'][idx]],
					className
				}))
				.filter((row) => row.value > 0);
		}
		if (key === 'page_buckets') {
			return (mappings.page_buckets as [string, string][])
				.map(([label, className], idx) => ({
					label,
					value: direct[['pages_to_read', 'pages_read', 'pages_wasted'][idx]],
					className
				}))
				.filter((row) => row.value > 0);
		}
		return fixed.map(([label, className], idx) => ({
			label,
			value: direct[Object.keys(direct)[idx]],
			className: className ?? DIST_COLORS[idx % DIST_COLORS.length]
		}));
	}

	function trendPoints(key: string): { label: string; value: number }[] {
		const raw = statValue(key) as { month: string; pages: number }[] | { month: string; count: number }[] | { year: number; count: number }[] | undefined;
		if (!raw) return [];
		const isYearly = raw.length > 0 && 'year' in raw[0];
		const rangeSize = trendRange === '12months' ? (isYearly ? 1 : 12) : trendRange === '3years' ? (isYearly ? 3 : 36) : null;
		const latest = isYearly
			? Math.max(...raw.map((entry) => (entry as { year: number }).year))
			: Math.max(...raw.map((entry) => {
				const [year, month] = (entry as { month: string }).month.split('-').map(Number);
				return year * 12 + month;
			}));
		const first = rangeSize === null ? null : latest - rangeSize + 1;

		return raw.filter((entry) => {
			if (first === null) return true;
			if (isYearly) return (entry as { year: number }).year >= first;
			const [year, month] = (entry as { month: string }).month.split('-').map(Number);
			return year * 12 + month >= first;
		}).map((entry) => ({
			label: 'year' in entry ? String(entry.year) : formatMonthLabel((entry as { month: string }).month),
			value: 'pages' in entry ? entry.pages : entry.count
		}));
	}

	function barWidth(value: number, max: number): string {
		if (max <= 0) return '4px';
		return `${Math.max(4, Math.round((value / max) * 100))}px`;
	}
</script>

<svelte:head>
	<title>
		{profile && (hasSection('username') || hasSection('user_info'))
			? `${profile.owner.firstname} ${profile.owner.lastname} - ${$_('app.title')}`
			: $_('app.title')}
	</title>
</svelte:head>

<div class="min-h-screen bg-base-200 text-base-content">
	<header class="sticky top-0 z-30 bg-base-100/90 backdrop-blur border-b border-base-200">
		<div class="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
			<a href={base + '/'} class="flex items-center gap-2">
				<span class="text-lg font-bold tracking-tight">{$_('app.title')}</span>
			</a>
			<div class="flex items-center gap-2">
				<button
					class="btn btn-ghost btn-sm btn-circle"
					aria-label={$_('publicProfile.page.themeToggle')}
					title={$_('publicProfile.page.themeToggle')}
					onclick={toggleTheme}
				>
					<ThemeIcon class="w-4 h-4" />
				</button>
				<a
					class="btn btn-ghost btn-sm"
					href={GITHUB_URL}
					target="_blank"
					rel="noopener noreferrer"
					aria-label={$_('publicProfile.page.githubLink')}
				>
					<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12 24 5.37 18.63 0 12 0"/></svg>
				</a>
			</div>
		</div>
	</header>

	<main class="max-w-3xl mx-auto px-4 py-6 pb-16 flex flex-col gap-6">
		{#if status === 'loading'}
			<div class="flex flex-col items-center justify-center gap-4 py-24">
				<span class="loading loading-spinner loading-lg"></span>
				<p class="text-sm text-base-content/60">{$_('publicProfile.page.loading')}</p>
			</div>
		{:else if status === 'not_found'}
			<div class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
				<div class="card-body items-center text-center gap-3 py-16">
					<p class="text-4xl">🔗</p>
					<h1 class="text-lg font-semibold">{$_('publicProfile.page.notFound')}</h1>
					<p class="text-sm text-base-content/60">{$_('publicProfile.page.notFoundDesc')}</p>
				</div>
			</div>
		{:else if status === 'login_required'}
			<div class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
				<div class="card-body items-center text-center gap-3 py-16">
					<p class="text-3xl">🔒</p>
					<h1 class="text-lg font-semibold">{$_('publicProfile.page.loginRequired')}</h1>
					<p class="text-sm text-base-content/60">{$_('publicProfile.page.loginRequiredDesc')}</p>
					<a class="btn btn-primary mt-2" href={base + '/login'}>{$_('publicProfile.page.loginButton')}</a>
				</div>
			</div>
		{:else if status === 'error'}
			<div class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
				<div class="card-body items-center text-center gap-3 py-16">
					<h1 class="text-lg font-semibold">{$_('publicProfile.page.errorTitle')}</h1>
					<p class="text-sm text-base-content/60">{$_('publicProfile.page.errorDesc')}</p>
					<button class="btn btn-primary btn-sm mt-2" onclick={load}>{$_('publicProfile.page.retry')}</button>
				</div>
			</div>
		{:else if profile}
			{#if profile.expires_at}
				<p class="text-xs text-base-content/50">
					{$_('publicProfile.page.expiresHint', { values: { date: new Date(profile.expires_at).toLocaleDateString() } })}
				</p>
			{/if}

			{#if hasSection('username')}
				<h1 class="text-2xl font-bold tracking-tight">{profile.owner.firstname} {profile.owner.lastname}</h1>
			{/if}

			{#if hasSection('user_info')}
				<section class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
					<div class="card-body">
						<div class="flex items-center gap-4">
							<AnimalAvatar
								seed={`${profile.owner.firstname} ${profile.owner.lastname}`}
								size={56}
								class="h-14 w-14 shrink-0"
							/>
							<div class="min-w-0">
								<h2 class="card-title text-lg font-semibold">{$_('publicProfile.sections.userInfo')}</h2>
								<p class="truncate text-sm text-base-content/70">
									{profile.owner.firstname} {profile.owner.lastname}
								</p>
							</div>
						</div>
					</div>
				</section>
			{/if}

			{#if hasSection('currently_reading')}
				<section class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
					<div class="card-body">
						<h2 class="card-title text-lg font-semibold">{$_('publicProfile.sections.currentlyReading')}</h2>
						{#if currentlyReading.length === 0}
							<p class="text-sm text-base-content/50">{$_('publicProfile.page.noCurrentlyReading')}</p>
						{:else}
							<ul class="flex flex-col gap-3">
								{#each currentlyReading as book}
									<li class="flex gap-3">
										<figure class="w-12 h-16 rounded-lg overflow-hidden bg-base-200 shrink-0">
											{#if book.cover_url}
												<img src={book.cover_url} alt={$_('book.coverOf', { values: { title: book.title } })} class="w-full h-full object-cover" loading="lazy" />
											{/if}
										</figure>
										<div class="min-w-0 flex-1">
											<p class="font-medium leading-tight line-clamp-2">{book.title}</p>
											<p class="text-xs text-base-content/50 truncate">{formatAuthors(book.authors)}</p>
											{#if book.date_started}
												<p class="text-xs text-base-content/50">{$_('publicProfile.sections.currentlyReadingStarted', { values: { date: formatDate(book.date_started, tz) } })}</p>
											{/if}
										</div>
									</li>
								{/each}
							</ul>
						{/if}
					</div>
				</section>
			{/if}

			{#if hasSection('last_read')}
				<section class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
					<div class="card-body">
						<h2 class="card-title text-lg font-semibold">{$_('publicProfile.sections.lastRead')}</h2>
						{#if lastRead.length === 0}
							<p class="text-sm text-base-content/50">{$_('publicProfile.page.noLastRead')}</p>
						{:else}
							<ul class="grid grid-cols-2 md:grid-cols-3 gap-3">
								{#each lastRead as book}
									<li class="flex gap-3 p-3 rounded-xl border border-base-200 bg-base-200/40 min-w-0">
										<figure class="w-10 h-14 rounded-lg overflow-hidden bg-base-100 shrink-0">
											{#if book.cover_url}
												<img src={book.cover_url} alt={$_('book.coverOf', { values: { title: book.title } })} class="w-full h-full object-cover" loading="lazy" />
											{/if}
										</figure>
										<div class="min-w-0 flex-1">
											<p class="font-medium leading-tight line-clamp-2 text-sm">{book.title}</p>
											<p class="text-xs text-base-content/50 truncate">{formatAuthors(book.authors)}</p>
											{#if book.date_finished}
												<p class="text-xs text-base-content/50">{$_('publicProfile.page.finishedOn', { values: { date: formatDate(book.date_finished, tz) } })}</p>
											{/if}
										</div>
									</li>
								{/each}
							</ul>
							{#if lastReadAll.length > lastRead.length}
								<button class="btn btn-ghost btn-sm self-start mt-1" onclick={() => (lastReadLimit += 10)}>
									{$_('publicProfile.page.showMore')}
								</button>
							{/if}
						{/if}
					</div>
				</section>
			{/if}

			{#if hasSection('reading_timeline')}
				<section class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
					<div class="card-body">
						<h2 class="card-title text-lg font-semibold">{$_('publicProfile.sections.readingTimeline')}</h2>
						{#if timelineBooks.length === 0}
							<p class="text-sm text-base-content/50">{$_('publicProfile.page.emptyLibrary')}</p>
						{:else}
							<ol class="grid min-w-0 gap-3 sm:grid-cols-2">
								{#each timelineMonths as [monthKey, books]}
									<li class="min-w-0 rounded-xl border border-base-200 p-4">
										<div class="flex items-center gap-2">
											<span aria-hidden="true" class="h-2.5 w-2.5 shrink-0 rounded-full bg-primary"></span>
											<h3 class="min-w-0 flex-1 truncate text-sm font-semibold">{formatMonthLabel(monthKey)}</h3>
											<span class="badge badge-ghost badge-sm tabular-nums">{books.length}</span>
										</div>
										<div class="mt-3 divide-y divide-base-200">
											{#each books as book}
													<div class="flex min-w-0 items-center gap-3 py-2 first:pt-0 last:pb-0">
														{#if book.cover_url}
															<img src={book.cover_url} alt="" class="h-12 w-8 shrink-0 rounded object-cover" loading="lazy" />
														{:else}
															<div class="h-12 w-8 shrink-0 rounded bg-base-200"></div>
														{/if}
														<div class="min-w-0 flex-1">
															<p class="truncate text-sm font-medium">{book.title}</p>
															<p class="truncate text-xs text-base-content/50">({formatAuthors(book.authors)})</p>
														</div>
													</div>
											{/each}
										</div>
										{#if timelineHiddenCount(monthKey, books.length) > 0}
											<p class="mt-2 text-xs italic text-base-content/50">{$_('publicProfile.page.timelineMore', { values: { count: timelineHiddenCount(monthKey, books.length) } })}</p>
										{/if}
									</li>
								{/each}
							</ol>
							{#if timelineBooks.length > timelineLimit}
								<button class="btn btn-ghost btn-sm self-start mt-1" onclick={() => (timelineLimit += 5)}>
									{$_('publicProfile.page.showMore')}
								</button>
							{/if}
						{/if}
					</div>
				</section>
			{/if}

			{#if hasSection('full_library')}
				<section class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
					<div class="card-body">
						<h2 class="card-title text-lg font-semibold">{$_('publicProfile.sections.fullLibrary')}</h2>
						{#if (profile.books ?? []).length === 0}
							<p class="text-sm text-base-content/50">{$_('publicProfile.page.emptyLibrary')}</p>
						{:else}
							<input
								type="search"
								placeholder={$_('import.searchByTitleOrAuthor')}
								class="input input-bordered input-sm w-full max-w-sm"
								bind:value={libraryQuery}
								oninput={() => (libraryLimit = 8)}
							/>
							{#if filteredBooks.length === 0}
								<p class="text-sm text-base-content/50">{$_('search.noResultsFor', { values: { query: libraryQuery.trim() } })}</p>
							{:else}
								<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
									{#each filteredBooks.slice(0, libraryLimit) as book}
										<div class="flex flex-col gap-1">
											<figure class="aspect-[2/3] rounded-xl overflow-hidden bg-base-200">
												{#if book.cover_url}
													<img src={book.cover_url} alt={$_('book.coverOf', { values: { title: book.title } })} class="w-full h-full object-cover" loading="lazy" />
												{/if}
											</figure>
											<p class="text-xs font-medium leading-tight line-clamp-2">{book.title}</p>
											<p class="text-[11px] text-base-content/50 truncate">{formatAuthors(book.authors)}</p>
											<span class={`badge badge-xs ${STATUS_BADGE[book.reading_status]}`}>{$_(STATUS_LABEL_KEYS[book.reading_status])}</span>
										</div>
									{/each}
								</div>
								{#if filteredBooks.length > libraryLimit}
									<button class="btn btn-ghost btn-sm self-center mt-2" onclick={() => (libraryLimit += 8)}>
										{$_('publicProfile.page.showMore')}
									</button>
								{/if}
							{/if}
						{/if}
					</div>
				</section>
			{/if}

			{#if hasSection('statistics') && profile.statistics}
				<section class="flex flex-col gap-4">
					{#if summaryStats.length > 0}
						<article class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
							<div class="card-body">
								<h2 class="card-title text-lg font-semibold">{$_('publicProfile.statGroups.summary')}</h2>
								<div class="stats stats-vertical sm:stats-horizontal shadow-none bg-transparent">
									{#each summaryStats as key}
										<div class="stat">
											<div class="stat-title text-xs">{$_(PUBLIC_PROFILE_STATISTICS.find((s) => s.key === key)!.i18nKey)}</div>
											{#if key === 'busiest_month'}
												<div class="stat-value text-2xl">{formatMonthLabel(statValue(key) as string)}</div>
												<div class="stat-desc">{$_('statistics.booksCount', { values: { count: formatNumber(statValue(key + '_count') as number) } })}</div>
											{:else if key === 'most_popular_language'}
												<div class="stat-value text-2xl">{(statValue(key) as string) ? formatLanguageCode(statValue(key) as string, appLocale) : '-'}</div>
												<div class="stat-desc">{formatNumber(statValue(key + '_count') as number)}</div>
											{:else}
												<div class="stat-value text-2xl">{formatNumber(statValue(key) as number)}</div>
												<div class="stat-desc invisible" aria-hidden="true">&nbsp;</div>
											{/if}
										</div>
									{/each}
								</div>
							</div>
						</article>
					{/if}

					{#if distributionStats.length > 0}
						<article class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
							<div class="card-body flex min-w-0 flex-col gap-5">
								<h2 class="card-title text-lg font-semibold">{$_('publicProfile.statGroups.distribution')}</h2>
								<div class="columns-1 min-w-0 gap-4 md:columns-2">
									{#each distributionStats as key}
										{@const rows = distributionRows(key)}
										{@const distTotal = rows.reduce<number>((sum, row) => sum + row.value, 0)}
										{#if rows.length > 0}
											<section class="mb-4 inline-block w-full break-inside-avoid rounded-xl border border-base-200 p-4 align-top">
												<h3 class="text-sm font-semibold">{$_(PUBLIC_PROFILE_STATISTICS.find((s) => s.key === key)!.i18nKey)}</h3>
												<div class="mt-4 flex flex-col gap-3">
													{#each rows as row}
														<div>
															<div class="flex items-center justify-between gap-3 text-xs">
																<span class="flex min-w-0 items-center gap-2">
																	<span aria-hidden="true" class={`h-2 w-2 shrink-0 rounded-full ${row.className}`}></span>
																	<span class="truncate text-base-content/70" title={row.label}>{row.label}</span>
																</span>
																<span class="shrink-0 tabular-nums">
																	<span class="font-semibold">{formatNumber(row.value)}</span>
																	<span class="ml-1 text-base-content/50">{formatNumber(actualPercentage(row.value, distTotal), 0)}%</span>
																</span>
															</div>
															<div class="mt-1.5 h-2 overflow-hidden rounded-full bg-base-200">
																<div class={`h-full rounded-full ${row.className}`} style="width: {safePercentage(row.value, distTotal)}%"></div>
															</div>
														</div>
													{/each}
												</div>
											</section>
										{/if}
									{/each}
								</div>
							</div>
						</article>
					{/if}

					{#if trendStats.length > 0}
						<article class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
							<div class="card-body flex flex-col gap-4">
								<div class="flex flex-wrap items-center justify-between gap-3">
									<h2 class="card-title text-lg font-semibold">{$_('publicProfile.statGroups.trends')}</h2>
									<label>
										<select class="select select-bordered select-sm" aria-label={$_('statistics.rangeLabel')} bind:value={trendRange}>
											<option value="12months">{$_('statistics.rangeLast12Months')}</option>
											<option value="3years">{$_('statistics.rangeLast3Years')}</option>
											<option value="alltime">{$_('statistics.rangeAllTime')}</option>
										</select>
									</label>
								</div>
								{#each trendStats as key}
									{@const points = trendPoints(key)}
									{@const max = points.reduce((m, p) => Math.max(m, p.value), 0)}
									{#if points.length > 0}
										<div class="flex flex-col gap-1">
											<h3 class="text-sm font-medium text-base-content/70">{$_(PUBLIC_PROFILE_STATISTICS.find((s) => s.key === key)!.i18nKey)}</h3>
										<div class="flex items-end gap-1 h-24 overflow-visible">
											{#each points as point}
												<button
													type="button"
													class="trend-bar group relative flex-1 flex flex-col items-center gap-1 min-w-0 rounded border-0 bg-transparent p-0 text-inherit focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
													title={`${point.label}: ${formatNumber(point.value, 0)}`}
													aria-label={`${point.label}: ${formatNumber(point.value, 0)}`}
												>
													<div class="w-full bg-primary/80 rounded-t" style="height: {barWidth(point.value, max)}"></div>
													<span role="tooltip" class="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 -translate-x-1/2 whitespace-nowrap rounded bg-neutral px-2 py-1 text-[11px] text-neutral-content opacity-0 shadow-sm transition-opacity group-hover:opacity-100 group-focus:opacity-100">
														{point.label}: {formatNumber(point.value, 0)}
													</span>
												</button>
											{/each}
											</div>
											<div class="flex gap-1">
												{#each points as point}
													<div class="flex-1 min-w-0 text-center text-[10px] text-base-content/50 truncate">{point.label}</div>
												{/each}
											</div>
										</div>
									{/if}
								{/each}
							</div>
						</article>
					{/if}

					{#if ratingStats.length > 0}
						<article class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
							<div class="card-body flex min-w-0 flex-col gap-5">
								<h2 class="card-title text-lg font-semibold">{$_('publicProfile.statGroups.ratings')}</h2>
								{#if ratingSummaryKeys.length > 0}
									<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
										{#each ratingSummaryKeys as key}
											{@const i18nKey = PUBLIC_PROFILE_STATISTICS.find((s) => s.key === key)!.i18nKey}
											<div class="rounded-xl bg-base-200/60 px-4 py-3">
												<p class="text-xs font-medium uppercase tracking-wide text-base-content/60">{$_(i18nKey)}</p>
												<p class="mt-1 text-2xl font-semibold tabular-nums">{key === 'average_rating' ? formatNumber(statValue(key) as number) : formatNumber(statValue(key) as number, 0)}</p>
											</div>
										{/each}
									</div>
								{/if}

								{#if ratingStats.includes('top_authors')}
									{@const authors = statValue('top_authors') as { author: string; book_count: number }[]}
									{#if authors.length > 0}
										<section class="rounded-xl border border-base-200 p-4">
											<h3 class="text-sm font-semibold">{$_('statistics.topAuthors')}</h3>
											<div class="mt-3 divide-y divide-base-200">
												{#each authors as author, idx}
													<div class="flex items-center gap-3 py-2 first:pt-0 last:pb-0">
														<span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">{idx + 1}</span>
														<span class="min-w-0 flex-1 truncate text-sm font-medium">{author.author}</span>
														<span class="badge badge-ghost badge-sm shrink-0">{$_('statistics.booksCount', { values: { count: author.book_count } })}</span>
													</div>
												{/each}
											</div>
										</section>
									{/if}
								{/if}

								{#if ratedBookKeys.length > 0}
									<div class="grid min-w-0 gap-4 sm:grid-cols-2">
										{#each ratedBookKeys as key}
											{@const i18nKey = PUBLIC_PROFILE_STATISTICS.find((s) => s.key === key)!.i18nKey}
											{@const books = statValue(key) as { title: string; author: string | null; rating: number; cover_url: string | null }[]}
											{#if books.length > 0}
												<section class="min-w-0 rounded-xl border border-base-200 p-4">
													<h3 class="text-sm font-semibold">{$_(i18nKey)}</h3>
													<div class="mt-3 flex flex-col divide-y divide-base-200">
														{#each books.slice(0, 5) as book}
															<div class="flex min-w-0 items-center gap-3 py-2 first:pt-0 last:pb-0">
																{#if book.cover_url}
																	<img src={book.cover_url} alt="" class="h-12 w-8 shrink-0 rounded object-cover" loading="lazy" />
																{:else}
																	<div class="h-12 w-8 shrink-0 rounded bg-base-200"></div>
																{/if}
																<div class="min-w-0 flex-1">
																	<p class="truncate text-sm font-medium">{book.title}</p>
																	{#if book.author}<p class="truncate text-xs text-base-content/50">{book.author}</p>{/if}
																</div>
																<span class="inline-flex shrink-0 items-center gap-1 text-warning font-semibold tabular-nums">
																	<Star class="h-3.5 w-3.5 fill-current" aria-hidden="true" />
																	{book.rating ?? '-'}
																</span>
															</div>
														{/each}
													</div>
												</section>
											{/if}
										{/each}
									</div>
								{/if}
							</div>
						</article>
					{/if}
				</section>
			{/if}
		{/if}
	</main>

	<footer class="border-t border-base-200 py-6">
		<div class="max-w-3xl mx-auto px-4 flex items-center justify-center text-xs text-base-content/50">
			{@html $_('publicProfile.page.shareHint', { values: { app: GITHUB_ANCHOR } })}
		</div>
	</footer>
</div>

<style>
	.trend-bar:hover > [role='tooltip'],
	.trend-bar:focus > [role='tooltip'] {
		opacity: 1;
	}
</style>
