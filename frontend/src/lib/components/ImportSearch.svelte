<script lang="ts">
	import type { Book, BookImportCandidate, ReadingStatus, SearchStage } from '$lib/types';
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import { ScanBarcode } from '@lucide/svelte';

	let {
		onImport,
		onOpenScanner,
		scannedIsbn = null,
		onScannedHandled
	}: {
		onImport?: (book: Book) => void;
		onOpenScanner?: () => void;
		scannedIsbn?: string | null;
		onScannedHandled?: () => void;
	} = $props();

	let query = $state('');
	let searchType = $state<'title' | 'isbn'>('title');
	let results = $state<BookImportCandidate[]>([]);
	let stages = $state<SearchStage[]>([]);
	let searching = $state(false);
	let supplementingGoogle = $state(false);
	let googleSupplementSearched = $state(false);
	let supplementAddedCount = $state<number | null>(null);
	let importing = $state<string | null>(null);
	let cameraSupported = $state(false);
	let lastHandledScannedIsbn = $state<string | null>(null);
	let importedIsbns = $state<Set<string>>(new Set());
	let importedTitleAuthors = $state<Set<string>>(new Set());
	let hasOlResults = $derived(results.some((r) => r.source === 'open_library'));

	onMount(async () => {
		cameraSupported =
			typeof navigator !== 'undefined' &&
			window.isSecureContext &&
			!!navigator.mediaDevices &&
			typeof navigator.mediaDevices.getUserMedia === 'function';
		await refreshImportedLookups();
	});

	$effect(() => {
		if (!scannedIsbn || scannedIsbn === lastHandledScannedIsbn) return;
		lastHandledScannedIsbn = scannedIsbn;
		searchType = 'isbn';
		query = scannedIsbn;
		toasts.add($_('import.scannedIsbn', { values: { isbn: scannedIsbn } }), 'success');
		void search();
		onScannedHandled?.();
	});

	function stageLabel(s: SearchStage): string {
		if (s.stage === 'open_library') {
			if (s.status === 'searching') return $_('import.sourceOpenLibrarySearching');
			if ('reason' in s) return $_('import.sourceBackendError', { values: { source: 'Open Library' } });
			return $_('import.resultCount', {
				values: { source: 'Open Library', count: s.count, suffix: s.count === 1 ? '' : 's' }
			});
		}
		if (s.stage === 'hardcover') {
			if (s.status === 'searching') return $_('import.sourceHardcoverSearching');
			if (s.status === 'skipped') return $_('import.sourceHardcoverSkipped');
			if ('reason' in s) return $_('import.sourceBackendError', { values: { source: 'Hardcover' } });
			return $_('import.resultCount', {
				values: { source: 'Hardcover', count: s.count, suffix: s.count === 1 ? '' : 's' }
			});
		}
		if (s.stage === 'google_books') {
			if (s.status === 'searching') return $_('import.sourceGoogleSearching');
			if (s.status === 'skipped') return $_('import.sourceSkipped');
			if ('reason' in s) return $_('import.sourceBackendError', { values: { source: 'Google Books' } });
			return $_('import.resultCount', {
				values: { source: 'Google Books', count: s.count, suffix: s.count === 1 ? '' : 's' }
			});
		}
		if (s.stage === 'error') return $_('import.sourceError', { values: { message: s.message } });
		return '';
	}

	function stageIcon(s: SearchStage): string {
		if (s.stage === 'open_library' || s.stage === 'hardcover' || s.stage === 'google_books') {
			if (s.status === 'searching') return '◌';
			if (s.status === 'skipped') return '—';
			if ('reason' in s) return '!';
			return '✓';
		}
		if (s.stage === 'error') return '✗';
		return '';
	}

	function stageClass(s: SearchStage): string {
		if (s.stage === 'error') return 'text-error';
		if (s.stage === 'hardcover' && s.status === 'skipped') return 'text-base-content/40';
		if (s.stage === 'google_books' && s.status === 'skipped') return 'text-base-content/40';
	if (
		(s.stage === 'open_library' || s.stage === 'hardcover' || s.stage === 'google_books') &&
		s.status === 'searching'
	)
		return 'text-base-content/60 animate-pulse';
	if ((s.stage === 'open_library' || s.stage === 'hardcover' || s.stage === 'google_books') && 'reason' in s) {
		return 'text-warning';
	}
	return 'text-base-content/70';
}

	function normalize(value: string | null | undefined): string {
		return (value ?? '').trim().toLowerCase();
	}

	function normalizeIsbn(value: string | null | undefined): string {
		return normalize(value).replaceAll('-', '').replaceAll(' ', '');
	}

	function candidateKey(candidate: BookImportCandidate): string {
		const isbn = normalizeIsbn(candidate.isbn);
		if (isbn) return `isbn:${isbn}`;
		return `ta:${normalize(candidate.title)}|${normalize(candidate.author)}`;
	}

	function titleAuthorKey(title: string | null | undefined, author: string | null | undefined): string {
		return `${normalize(title)}|${normalize(author)}`;
	}

	function updateImportedLookups(books: Book[]) {
		const isbnSet = new Set<string>();
		const titleAuthorSet = new Set<string>();
		for (const book of books) {
			const isbn = normalizeIsbn(book.isbn);
			if (isbn) isbnSet.add(isbn);
			if (book.author) titleAuthorSet.add(titleAuthorKey(book.title, book.author));
		}
		importedIsbns = isbnSet;
		importedTitleAuthors = titleAuthorSet;
	}

	async function refreshImportedLookups() {
		try {
			const response = await api.books.list();
			updateImportedLookups(response.books);
		} catch {
			// Best-effort only; search and import still works without markers.
		}
	}

	function markAsImported(book: Book) {
		const nextIsbns = new Set(importedIsbns);
		const nextTitleAuthors = new Set(importedTitleAuthors);
		const isbn = normalizeIsbn(book.isbn);
		if (isbn) nextIsbns.add(isbn);
		if (book.author) nextTitleAuthors.add(titleAuthorKey(book.title, book.author));
		importedIsbns = nextIsbns;
		importedTitleAuthors = nextTitleAuthors;
	}

	function isAlreadyImported(candidate: BookImportCandidate): boolean {
		const isbn = normalizeIsbn(candidate.isbn);
		if (isbn && importedIsbns.has(isbn)) return true;
		if (!candidate.author) return false;
		return importedTitleAuthors.has(titleAuthorKey(candidate.title, candidate.author));
	}

	function mergeCandidates(
		existing: BookImportCandidate[],
		incoming: BookImportCandidate[]
	): BookImportCandidate[] {
		const seen = new Set(existing.map(candidateKey));
		const merged = [...existing];
		for (const candidate of incoming) {
			const key = candidateKey(candidate);
			if (!seen.has(key)) {
				seen.add(key);
				merged.push(candidate);
			}
		}
		return merged;
	}

	async function runSearch(mode: 'auto' | 'google_only', mergeResults: boolean) {
		try {
			for await (const event of api.import.searchStream(query.trim(), searchType, mode)) {
				if (event.stage === 'complete') {
					results = mergeResults ? mergeCandidates(results, event.results) : event.results;
				} else {
					stages = stages.filter((s) => s.stage !== event.stage);
					stages = [...stages, event];
				}
			}
		} catch (e: unknown) {
			toasts.add(e instanceof Error ? e.message : $_('import.searchFailed'), 'error');
		}
	}

	async function search() {
		if (!query.trim()) return;
		searching = true;
		supplementingGoogle = false;
		googleSupplementSearched = false;
		supplementAddedCount = null;
		results = [];
		stages = [];
		try {
			await runSearch('auto', false);
		} finally {
			searching = false;
		}
	}

	async function searchGoogleToo() {
		if (!query.trim() || searching || supplementingGoogle || googleSupplementSearched) return;
		supplementingGoogle = true;
		const beforeCount = results.length;
		try {
			await runSearch('google_only', true);
			supplementAddedCount = Math.max(0, results.length - beforeCount);
			googleSupplementSearched = true;
		} finally {
			supplementingGoogle = false;
		}
	}

	async function importBook(candidate: BookImportCandidate, status: ReadingStatus) {
		const key = candidate.isbn ?? candidate.title;
		importing = key;
		try {
			const book = await api.import.importBook(candidate, status);
			markAsImported(book);
			onImport?.(book);
		} catch (e: unknown) {
			const message =
				e instanceof Error && e.message === 'error.isbnAlreadyExists'
					? $_('error.isbnAlreadyExists')
					: e instanceof Error
						? e.message
						: $_('import.importFailed');
			toasts.add(message, 'error');
		} finally {
			importing = null;
		}
	}
</script>

<div class="flex flex-col gap-3 sm:pr-4">
	<div class="flex flex-col sm:flex-row sm:items-center gap-2 grow basis-[0] min-w-[240px]">
		<input
			type="text"
			name="import-query"
			class="input input-bordered w-full sm:w-auto sm:grow sm:min-w-0"
			placeholder={searchType === 'isbn' ? $_('import.enterIsbn') : $_('import.searchByTitleOrAuthor')}
			bind:value={query}
			onkeydown={(e) => e.key === 'Enter' && search()}
		/>
		<div class="flex gap-2 w-full sm:w-auto">
			<select class="select select-bordered min-w-fit max-sm:flex-1" name="import-type" bind:value={searchType}>
				<option value="title">{$_('book.title')}</option>
				<option value="isbn">{$_('book.isbn')}</option>
			</select>
			<button class="btn btn-primary shrink-0 max-sm:flex-1" onclick={search} disabled={searching}>
				{searching ? $_('common.loadingEllipsis') : $_('common.search')}
			</button>
		</div>
	</div>
	{#if cameraSupported}
		<div class="flex flex-col items-center sm:flex-row sm:items-center gap-3">
			<div class="flex items-center gap-2 text-sm text-base-content/50 select-none">
				<div class="h-px w-8 bg-base-300 sm:hidden"></div>
				<span>{$_('import.or')}</span>
				<div class="h-px w-8 bg-base-300 sm:hidden"></div>
			</div>
			<button
				class="btn btn-outline"
				onclick={() => onOpenScanner?.()}
				disabled={searching}
				title={$_('import.scanIsbn')}
				aria-label={$_('import.scanIsbn')}
			>
				<ScanBarcode class="w-4 h-4" />
				<span>{$_('import.scan')}</span>
			</button>
		</div>
	{/if}

	{#if stages.length > 0}
		<ul class="flex flex-col gap-1 text-sm">
			{#each stages as s}
				<li class="flex items-center gap-2 {stageClass(s)}">
					<span class="w-4 text-center shrink-0">{stageIcon(s)}</span>
					<span>{stageLabel(s)}</span>
				</li>
			{/each}
		</ul>
	{/if}

	{#if hasOlResults && !googleSupplementSearched}
		<div class="flex justify-start">
			<button class="btn btn-outline btn-sm" onclick={searchGoogleToo} disabled={searching || supplementingGoogle}>
				{supplementingGoogle ? $_('import.googleSearching') : $_('import.googleToo')}
			</button>
		</div>
	{/if}

	{#if googleSupplementSearched && supplementAddedCount !== null}
		<p class="text-xs text-base-content/60">
			{$_('import.googleAdded', { values: { count: supplementAddedCount } })}
		</p>
	{/if}

	{#if results.length === 0 && !searching && stages.length === 0}
		<p class="text-base-content/50 text-sm text-center py-4">{$_('import.noResultsYet')}</p>
	{:else if results.length === 0 && !searching && stages.length > 0}
		<p class="text-base-content/50 text-sm text-center py-2">{$_('import.noBooksFound')}</p>
	{/if}

	<ul class="flex flex-col gap-2 max-h-80 overflow-y-auto">
		{#each results as candidate}
			{@const key = candidate.isbn ?? candidate.title}
			{@const alreadyImported = isAlreadyImported(candidate)}
			<li
				class="flex gap-3 items-start p-2 rounded-lg border {alreadyImported
					? 'border-success/40 bg-success/5'
					: 'border-base-200'}"
			>
				{#if candidate.cover_url}
					<img
						src={candidate.cover_url}
						alt={$_('book.cover')}
						class="w-10 rounded flex-shrink-0 object-cover"
					/>
				{:else}
					<div class="w-10 h-14 bg-base-200 rounded flex-shrink-0"></div>
				{/if}
				<div class="flex-1 min-w-0">
					<p class="font-medium text-sm line-clamp-2">{candidate.title}</p>
					{#if candidate.author}
						<p class="text-xs text-base-content/60">{candidate.author}</p>
					{/if}
					<div class="flex flex-wrap items-center gap-1.5 text-xs text-base-content/40">
						<span>{candidate.source}</span>
						{#if candidate.published_year}
							<span>·</span>
							<span>{candidate.published_year}</span>
						{/if}
						{#if candidate.language}
							<span>·</span>
							<span class="badge badge-ghost badge-xs">{candidate.language}</span>
						{/if}
						{#if candidate.page_count}
							<span>·</span>
							<span>{candidate.page_count} {$_('book.pages').toLowerCase()}</span>
						{/if}
					</div>
					{#if alreadyImported}
						<div class="mt-1">
							<span class="badge badge-success badge-outline badge-xs">{$_('import.alreadyImported')}</span>
						</div>
					{/if}
				</div>
				<div class="flex flex-col gap-1">
					<button
						class="btn btn-xs {alreadyImported ? 'btn-success btn-outline' : 'btn-primary'}"
						disabled={alreadyImported || importing === key}
						title={alreadyImported ? $_('import.alreadyImported') : ''}
						onclick={() => importBook(candidate, 'want_to_read')}
					>
						{importing === key
							? $_('common.loadingEllipsis')
							: alreadyImported
								? $_('import.imported')
								: $_('app.add')}
					</button>
				</div>
			</li>
		{/each}
	</ul>
</div>
