<script lang="ts">
	import { onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import { api } from '$lib/api';
	import { toasts } from '$lib/toasts';
	import type { Book, CoverCandidate } from '$lib/types';
	import { ArrowLeft, ExternalLink, SkipForward } from '@lucide/svelte';
	import CoverCandidateGrid from '$lib/components/CoverCandidateGrid.svelte';
	import { formatAuthors } from '$lib/utils/authors';

	let loading = $state(true);
	let advancing = $state(false);
	let books = $state<Book[]>([]);
	let totalMissing = $state(0);
	let currentIndex = $state(0);
	let displayRemaining = $state(0);
	let saving = $state(false);
	let manualUrl = $state('');

	let candidates = $state<CoverCandidate[]>([]);
	let candidatesLoading = $state(false);
	let candidatesError = $state<string | null>(null);

	let lastSearchedBookId: number | null = null;

	const currentBook = $derived(books[currentIndex] ?? null);
	const hasMoreBooks = $derived(currentIndex < totalMissing);
	const googleSearchUrl = $derived.by(() => {
		if (!currentBook) return '';
		const parts = [currentBook.title, formatAuthors(currentBook.authors, currentBook.author)].filter(Boolean);
		return `https://www.google.com/search?q=${encodeURIComponent(parts.join(' '))}&udm=2&tbs=isz:l`;
	});

	const step = 10;

	onMount(() => {
		loadMissingBooks(0);
	});

	async function loadMissingBooks(offset: number) {
		try {
			const result = await api.books.list({
				has_cover: false,
				sort: 'title',
				order: 'asc',
				limit: step,
				offset
			});
			if (offset === 0) {
				books = result.books;
				totalMissing = result.total;
				displayRemaining = result.total;
			} else {
				books = [...books, ...result.books];
			}
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : String(e);
			toasts.add(msg, 'error');
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		const book = currentBook;
		if (!book) {
			candidates = [];
			candidatesLoading = false;
			candidatesError = null;
			return;
		}
		if (book.id === lastSearchedBookId) return;
		lastSearchedBookId = book.id;

		manualUrl = '';

		if (!book.isbn) {
			candidates = [];
			candidatesLoading = false;
			candidatesError = null;
			return;
		}

		candidatesLoading = true;
		candidatesError = null;
		candidates = [];
		let cancelled = false;

		api.covers.searchCandidates(book.isbn).then((result) => {
			if (cancelled) return;
			candidates = result.candidates;
			candidatesLoading = false;
		}).catch((e: unknown) => {
			if (cancelled) return;
			candidatesError = e instanceof Error ? e.message : String(e);
			candidatesLoading = false;
		});

		return () => { cancelled = true; };
	});

	function resolutionScore(c: CoverCandidate): number {
		if (c.width && c.height) return c.width * c.height;
		return 0;
	}

	async function saveCover(coverUrl: string) {
		if (!currentBook || saving) return;
		saving = true;
		try {
			const localUrl = await api.covers.importFromUrl(coverUrl);
			await api.books.update(currentBook.id, { cover_url: localUrl });
			toasts.add($_('missingCovers.coverSaved'), 'success');
			displayRemaining = Math.max(0, displayRemaining - 1);
			await advanceToNextBook();
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : String(e);
			toasts.add($_('missingCovers.coverSaveFailed') + ': ' + msg, 'error');
		} finally {
			saving = false;
		}
	}

	function handleCandidateSelect(candidate: CoverCandidate) {
		saveCover(candidate.url);
	}

	async function handleManualUrlSave() {
		if (!manualUrl.trim()) return;
		let parsed: URL;
		try {
			parsed = new URL(manualUrl.trim());
		} catch {
			toasts.add($_('missingCovers.manualUrlInvalid'), 'error');
			return;
		}
		if (!['http:', 'https:'].includes(parsed.protocol)) {
			toasts.add($_('missingCovers.manualUrlInvalid'), 'error');
			return;
		}
		saveCover(manualUrl.trim());
	}

	async function advanceToNextBook() {
		if (currentIndex + 1 >= books.length && books.length < totalMissing) {
			advancing = true;
			try {
				await loadMissingBooks(books.length);
			} finally {
				advancing = false;
			}
		}
		currentIndex++;
	}

	async function skip() {
		if (!saving) {
			await advanceToNextBook();
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (saving || advancing) return;

		if (event.key === 'ArrowRight') {
			event.preventDefault();
			skip();
			return;
		}

		const num = parseInt(event.key, 10);
		if (num >= 1 && num <= 9) {
			const idx = num - 1;
			const sorted = [...candidates.filter(c => c.available)].sort(
				(a, b) => resolutionScore(b) - resolutionScore(a)
			);
			if (idx < sorted.length) {
				event.preventDefault();
				saveCover(sorted[idx].url);
			}
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="max-w-5xl mx-auto px-4 py-6">
	<a href="/profile" class="inline-flex items-center gap-1 text-sm text-base-content/60 hover:text-base-content mb-4">
		<ArrowLeft class="w-3 h-3" /> {$_('common.back')}
	</a>

	{#if loading}
		<div class="flex items-center justify-center py-16">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if !hasMoreBooks && displayRemaining <= 0}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body items-center text-center py-12">
				<h1 class="text-2xl font-bold">{$_('missingCovers.allDone')}</h1>
				<p class="text-base-content/70 mt-2">{$_('missingCovers.allDoneSub')}</p>
				<a href="/library" class="btn btn-primary mt-6">{$_('nav.library')}</a>
			</div>
		</div>
	{:else if !hasMoreBooks}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body items-center text-center py-12">
				<h1 class="text-xl font-bold">{$_('missingCovers.header', { values: { count: displayRemaining } })}</h1>
				<p class="text-base-content/70 mt-2">{$_('missingCovers.allDoneSub')}</p>
				<a href="/missing-covers" class="btn btn-primary mt-6">{$_('nav.library')}</a>
			</div>
		</div>
	{:else if currentBook}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body">
				<h1 class="text-xl font-bold">{$_('missingCovers.header', { values: { count: displayRemaining } })}</h1>

				{#if advancing}
					<div class="flex items-center gap-3 py-8">
						<span class="loading loading-spinner loading-md"></span>
						<span>{$_('missingCovers.loadingBook')}</span>
					</div>
				{:else}
					<div class="mt-4">
						<p class="text-lg font-semibold">{currentBook.title}</p>
						<p class="text-sm text-base-content/70">{formatAuthors(currentBook.authors, currentBook.author)}</p>
						<p class="text-xs text-base-content/50 mt-1">
							{currentBook.isbn ? $_('missingCovers.isbnLabel', { values: { isbn: currentBook.isbn } }) : $_('missingCovers.noIsbn')}
						</p>
					</div>

					<div class="mt-4">
						{#if currentBook.isbn}
							<CoverCandidateGrid
								{candidates}
								loading={candidatesLoading}
								error={candidatesError}
								onSelect={handleCandidateSelect}
								disabled={saving}
								emptyMessage={$_('missingCovers.noCandidates')}
							/>
						{:else}
							<div class="text-sm text-base-content/60 py-4">{$_('missingCovers.noCandidates')}</div>
						{/if}
					</div>

					<div class="mt-4 flex flex-col sm:flex-row gap-3 items-start sm:items-end">
						<div class="flex-1 w-full sm:w-auto">
							<label for="manual-url" class="text-xs text-base-content/60 mb-1 block">{$_('missingCovers.manualUrlLabel')}</label>
							<div class="flex gap-2">
								<input
									id="manual-url"
									type="url"
									class="input input-bordered input-sm flex-1"
									placeholder={$_('missingCovers.manualUrlPlaceholder')}
									bind:value={manualUrl}
									disabled={saving || advancing}
								/>
								<button
									type="button"
									class="btn btn-primary btn-sm"
									onclick={handleManualUrlSave}
									disabled={saving || advancing || !manualUrl.trim()}
								>{$_('missingCovers.manualUrlSave')}</button>
							</div>
						</div>

						<div class="flex gap-2 w-full sm:w-auto">
							<a
								href={googleSearchUrl}
								target="_blank"
								rel="noopener noreferrer"
								class="btn btn-outline btn-sm"
								aria-label={$_('missingCovers.searchGoogleAria')}
							>
								{$_('missingCovers.searchGoogle')} <ExternalLink class="w-3 h-3" />
							</a>
							<button
								type="button"
								class="btn btn-ghost btn-sm"
								onclick={skip}
								disabled={saving || advancing}
								aria-label={$_('missingCovers.skipAria')}
							>
								<SkipForward class="w-3 h-3" /> {$_('missingCovers.skip')}
							</button>
						</div>
					</div>

					<p class="text-xs text-base-content/40 mt-4">{$_('missingCovers.keyboardHint')}</p>
				{/if}
			</div>
		</div>
	{/if}
</div>