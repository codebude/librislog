<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { base } from '$app/paths';
	import { _, locale } from '$lib/i18n';
	import { api } from '$lib/api';
	import { Moon, Palette, Sun } from '@lucide/svelte';
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
	let libraryLimit = $state(24);

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

	async function load() {
		status = 'loading';
		try {
			profile = await api.publicProfile.get($page.params.token ?? '');
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

	const timelineMonths = $derived(
		[...timelineBooks.reduce((map, book) => {
			const key = book.date_finished!.slice(0, 7);
			if (!map.has(key)) map.set(key, []);
			map.get(key)!.push(book);
			return map;
		}, new Map<string, PublicProfileBook[]>())]
			.sort(([a], [b]) => (a < b ? 1 : -1))
	);

	const summaryStats = $derived(PUBLIC_PROFILE_STATISTICS.filter((s) => s.group === 'summary' && statValue(s.key) !== undefined).map((s) => s.key));
	const distributionStats = $derived(PUBLIC_PROFILE_STATISTICS.filter((s) => s.group === 'distribution' && statValue(s.key) !== undefined).map((s) => s.key));
	const trendStats = $derived(PUBLIC_PROFILE_STATISTICS.filter((s) => s.group === 'trends' && statValue(s.key) !== undefined).map((s) => s.key));
	const ratingStats = $derived(PUBLIC_PROFILE_STATISTICS.filter((s) => s.group === 'ratings' && statValue(s.key) !== undefined).map((s) => s.key));

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
		return raw.map((entry) => ({
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
					href="https://github.com/codebude/librislog"
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
					<div class="card-body gap-1">
						<h2 class="card-title text-lg font-semibold">{$_('publicProfile.sections.userInfo')}</h2>
						<p class="text-sm text-base-content/70">
							{profile.owner.firstname} {profile.owner.lastname}
						</p>
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
							<ul class="flex flex-col gap-3">
								{#each lastRead as book}
									<li class="flex gap-3">
										<figure class="w-12 h-16 rounded-lg overflow-hidden bg-base-200 shrink-0">
											{#if book.cover_url}
												<img src={book.cover_url} alt={$_('book.coverOf', { values: { title: book.title } })} class="w-full h-full object-cover" loading="lazy" />
											{/if}
										</figure>
										<div class="min-w-0 flex-1">
											<p class="font-medium leading-tight line-clamp-2">{book.title}</p>
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
							<ol class="timeline timeline-vertical">
								{#each timelineMonths as [monthKey, books]}
									<li>
										<div class="timeline-middle">
											<span class="badge badge-sm badge-ghost">{formatMonthLabel(monthKey)}</span>
										</div>
										<div class="timeline-end mb-6 flex flex-col gap-1 text-sm">
											{#each books as book}
												<p class="truncate"><span class="font-medium">{book.title}</span> {formatAuthors(book.authors)}</p>
											{/each}
										</div>
										<hr />
									</li>
								{/each}
							</ol>
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
							<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
								{#each (profile.books ?? []).slice(0, libraryLimit) as book}
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
							{#if (profile.books?.length ?? 0) > libraryLimit}
								<button class="btn btn-ghost btn-sm self-center mt-2" onclick={() => (libraryLimit += 24)}>
									{$_('publicProfile.page.showMore')}
								</button>
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
									{#each summaryStats as key, i}
										<div class="stat">
											<div class="stat-title text-xs">{$_(PUBLIC_PROFILE_STATISTICS.find((s) => s.key === key)!.i18nKey)}</div>
											{#if key === 'busiest_month'}
												<div class="stat-value text-2xl">{formatMonthLabel(statValue(key) as string)}</div>
												<div class="stat-desc">{$_('statistics.booksCount', { values: { count: formatNumber(statValue(key + '_count') as number) } })}</div>
											{:else if key === 'most_popular_language'}
												<div class="stat-value text-2xl">{(statValue(key) as string) ? formatLanguageCode(statValue(key) as string, appLocale) : '-'}</div>
												<div class="stat-desc">{formatNumber(statValue(key + '_count') as number)}</div>
											{:else if i === 0}
												<div class="stat-value text-2xl">{formatNumber(statValue(key) as number)}</div>
											{:else}
												<div class="stat-value text-2xl">{formatNumber(statValue(key) as number)}</div>
											{/if}
										</div>
									{/each}
								</div>
							</div>
						</article>
					{/if}

					{#if distributionStats.length > 0}
						<article class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
							<div class="card-body flex flex-col gap-4">
								<h2 class="card-title text-lg font-semibold">{$_('publicProfile.statGroups.distribution')}</h2>
								{#each distributionStats as key}
									{@const rows = distributionRows(key)}
									{@const distTotal = rows.reduce<number>((sum, row) => sum + row.value, 0)}
									{#if rows.length > 0}
										<div class="flex flex-col gap-1">
											<h3 class="text-sm font-medium text-base-content/70">{$_(PUBLIC_PROFILE_STATISTICS.find((s) => s.key === key)!.i18nKey)}</h3>
											{#each rows as row}
												<div class="flex items-center gap-2 text-xs">
													<span class="w-32 shrink-0 truncate" title={row.label}>{row.label}</span>
													<div class="flex-1 h-3 bg-base-300 rounded-full overflow-hidden">
														<div class={`h-full ${row.className} rounded-full`} style="width: {safePercentage(row.value, distTotal)}%"></div>
													</div>
													<span class="w-10 shrink-0 text-right tabular-nums">{formatNumber(row.value)}</span>
												</div>
											{/each}
										</div>
									{/if}
								{/each}
							</div>
						</article>
					{/if}

					{#if trendStats.length > 0}
						<article class="card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
							<div class="card-body flex flex-col gap-4">
								<h2 class="card-title text-lg font-semibold">{$_('publicProfile.statGroups.trends')}</h2>
								{#each trendStats as key}
									{@const points = trendPoints(key)}
									{@const max = points.reduce((m, p) => Math.max(m, p.value), 0)}
									{#if points.length > 0}
										<div class="flex flex-col gap-1">
											<h3 class="text-sm font-medium text-base-content/70">{$_(PUBLIC_PROFILE_STATISTICS.find((s) => s.key === key)!.i18nKey)}</h3>
											<div class="flex items-end gap-1 h-24 overflow-hidden">
												{#each points as point}
													<div class="flex-1 flex flex-col items-center gap-1 min-w-0">
														<div class="w-full bg-primary/80 rounded-t" style="height: {barWidth(point.value, max)}"></div>
													</div>
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
							<div class="card-body flex flex-col gap-4">
								<h2 class="card-title text-lg font-semibold">{$_('publicProfile.statGroups.ratings')}</h2>
								{#each ratingStats as key}
									{@const i18nKey = PUBLIC_PROFILE_STATISTICS.find((s) => s.key === key)!.i18nKey}
									{#if key === 'books_with_rating' || key === 'books_without_rating' || key === 'average_rating'}
										<div class="flex items-center gap-2 text-sm">
											<span class="text-base-content/70">{$_(i18nKey)}</span>
											<span class="font-semibold tabular-nums">{key === 'average_rating' ? formatNumber(statValue(key) as number) : formatNumber(statValue(key) as number, 0)}</span>
										</div>
									{:else if key === 'top_authors'}
										{@const authors = statValue(key) as { author: string; book_count: number }[]}
										{#if authors.length > 0}
											<div class="flex flex-col gap-1">
												<h3 class="text-sm font-medium text-base-content/70">{$_(i18nKey)}</h3>
												{#each authors as author, idx}
													<p class="text-sm"><span class="font-medium">{author.author}</span> <span class="text-base-content/50">({$_('statistics.booksCount', { values: { count: author.book_count } })})</span></p>
												{/each}
											</div>
										{/if}
									{:else if key === 'top_rated_books' || key === 'worst_rated_books'}
										{@const books = statValue(key) as { title: string; author: string | null; rating: number; cover_url: string | null }[]}
										{#if books.length > 0}
											<div class="flex flex-col gap-1">
												<h3 class="text-sm font-medium text-base-content/70">{$_(i18nKey)}</h3>
												{#each books.slice(0, 5) as book}
													<p class="flex items-center gap-2 text-sm min-w-0">
														<span class="text-warning font-semibold">{book.rating ?? '-'}</span>
														<span class="truncate font-medium">{book.title}</span>
														{#if book.author}<span class="text-base-content/50 truncate">{book.author}</span>{/if}
													</p>
												{/each}
											</div>
										{/if}
									{/if}
								{/each}
							</div>
						</article>
					{/if}
				</section>
			{/if}
		{/if}
	</main>

	<footer class="border-t border-base-200 py-6">
		<div class="max-w-3xl mx-auto px-4 flex items-center justify-center gap-2 text-xs text-base-content/50">
			{$_('publicProfile.page.shareHint')}
			<a class="link link-neutral inline-flex items-center gap-1" href="https://github.com/codebude/librislog" target="_blank" rel="noopener noreferrer">
				{$_('publicProfile.page.githubLink')}
			</a>
		</div>
	</footer>
</div>