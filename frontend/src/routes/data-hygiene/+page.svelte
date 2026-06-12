<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import { localizeError } from '$lib/errors';
	import Alert from '$lib/components/Alert.svelte';
	import BookDetailDialog from '$lib/components/BookDetailDialog.svelte';
	import BookDrawer from '$lib/components/BookDrawer.svelte';
	import { LoaderCircle, X } from '@lucide/svelte';
	import type { Book, HygieneAttribute, HygieneMissingBook } from '$lib/types';

	const ATTRIBUTES: { key: HygieneAttribute; labelKey: string }[] = [
		{ key: 'author', labelKey: 'dataHygiene.attributes.author' },
		{ key: 'isbn', labelKey: 'dataHygiene.attributes.isbn' },
		{ key: 'publisher', labelKey: 'dataHygiene.attributes.publisher' },
		{ key: 'published_year', labelKey: 'dataHygiene.attributes.published_year' },
		{ key: 'blurb', labelKey: 'dataHygiene.attributes.blurb' },
		{ key: 'language', labelKey: 'dataHygiene.attributes.language' },
		{ key: 'subtitle', labelKey: 'dataHygiene.attributes.subtitle' },
		{ key: 'page_count', labelKey: 'dataHygiene.attributes.page_count' },
		{ key: 'cover_url', labelKey: 'dataHygiene.attributes.cover_url' },
	];

	let selectedAttributes = $state<HygieneAttribute[]>([]);
	let matchMode = $state<'any' | 'all'>('any');
	let books = $state<HygieneMissingBook[]>([]);
	let total = $state(0);
	let totalMissingPerAttribute = $state<Record<string, number>>({});
	let loading = $state(true);
	let error = $state<string | null>(null);
	let offset = $state(0);
	let pageSize = $state(50);
	let selectedBookIds = $state<Set<number>>(new Set());
	let batchField = $state<HygieneAttribute | null>(null);
	let batchValue = $state('');
	let batchFieldWasAutoSelected = $state(false);
	let showBatchConfirm = $state(false);
	let batchUpdating = $state(false);
	let dataLoaded = $state(false);
	let hasMore = $state(false);
	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let drawerOpen = $state(false);
	let detailLoadingBookId = $state<number | null>(null);
	let coverViewer = $state<{ title: string; coverUrl: string } | null>(null);

	const effectiveAttributes = $derived(
		selectedAttributes.length > 0 ? selectedAttributes : ATTRIBUTES.map(a => a.key)
	);

	async function loadData(reset: boolean = true) {
		if (reset) {
			offset = 0;
			selectedBookIds = new Set();
		}
		loading = true;
		error = null;
		try {
			const result = await api.hygiene.listMissing({
				attributes: effectiveAttributes,
				match: matchMode,
				offset,
				limit: pageSize,
			});
			if (reset) {
				books = result.books;
			} else {
				books = [...books, ...result.books];
			}
			total = result.total;
			totalMissingPerAttribute = result.total_missing_per_attribute;
			dataLoaded = true;
			hasMore = offset + pageSize < total;
		} catch (e: unknown) {
			error = localizeError(e, $_, $_('dataHygiene.loadFailed'));
			dataLoaded = false;
			if (reset) books = [];
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		void loadData(true);
	});

	function toggleAttribute(attr: HygieneAttribute) {
		if (selectedAttributes.includes(attr)) {
			selectedAttributes = selectedAttributes.filter(a => a !== attr);
		} else {
			selectedAttributes = [...selectedAttributes, attr];
		}
		void loadData(true);
	}

	function toggleSelectAll() {
		if (selectedBookIds.size === books.length && books.length > 0) {
			selectedBookIds = new Set();
		} else {
			selectedBookIds = new Set(books.map(b => b.id));
		}
	}

	function toggleBook(id: number) {
		const next = new Set(selectedBookIds);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		selectedBookIds = next;
	}

	let confirmPreviewBooks = $state<string[]>([]);

	function openBatchConfirm() {
		if (!batchField) {
			toasts.add($_('dataHygiene.noFieldSelected'), 'warning');
			return;
		}
		if (batchField === 'author' && !batchValue.trim()) {
			toasts.add($_('dataHygiene.authorRequired'), 'warning');
			return;
		}
		if (batchField === 'page_count' && (isNaN(parseInt(batchValue)) || parseInt(batchValue) < 1)) {
			toasts.add($_('dataHygiene.pageCountPositive'), 'warning');
			return;
		}
		if (!batchValue.trim() && batchField !== 'page_count' && batchField !== 'published_year') {
			toasts.add($_('dataHygiene.noValueEntered'), 'warning');
			return;
		}
		const preview = books
			.filter(b => selectedBookIds.has(b.id))
			.slice(0, 10)
			.map(b => b.title);
		confirmPreviewBooks = preview;
		showBatchConfirm = true;
	}

	async function confirmBatchUpdate() {
		if (!batchField) return;
		showBatchConfirm = false;
		batchUpdating = true;
		try {
			const result = await api.hygiene.batchUpdate({
				book_ids: [...selectedBookIds],
				field: batchField,
				value: batchValue || null,
			});
			toasts.add(
				$_('dataHygiene.success', {
					values: { updated: result.updated, skipped: result.skipped },
				}),
				'success'
			);
			selectedBookIds = new Set();
			batchField = null;
			batchValue = '';
			await loadData(true);
		} catch (e: unknown) {
			toasts.add(localizeError(e, $_, $_('dataHygiene.updateFailed')), 'error');
		} finally {
			batchUpdating = false;
		}
	}

	function loadMore() {
		offset += pageSize;
		void loadData(false);
	}

	async function openBookDetails(book: HygieneMissingBook) {
		detailLoadingBookId = book.id;
		try {
			selectedBook = await api.books.get(book.id);
			detailOpen = true;
			drawerOpen = false;
		} catch (e: unknown) {
			toasts.add(localizeError(e, $_, $_('dataHygiene.loadBookDetailsFailed')), 'error');
		} finally {
			detailLoadingBookId = null;
		}
	}

	function openEditFromDetail(book: Book) {
		selectedBook = book;
		detailOpen = false;
		drawerOpen = true;
	}

	async function handleSave(updated: Book) {
		selectedBook = updated;
		detailOpen = false;
		drawerOpen = false;
		await loadData(true);
	}

	function handleDelete(id: number) {
		detailOpen = false;
		drawerOpen = false;
		selectedBookIds = new Set([...selectedBookIds].filter(bookId => bookId !== id));
		void loadData(true);
	}

	function openCoverViewer(book: HygieneMissingBook) {
		if (!book.cover_url) return;
		coverViewer = {
			title: book.title,
			coverUrl: book.cover_url,
		};
	}

	function closeCoverViewer() {
		coverViewer = null;
	}

	const allComplete = $derived(
		dataLoaded && total === 0 && Object.values(totalMissingPerAttribute).every(c => c === 0)
	);

	const selectedCount = $derived(selectedBookIds.size);
	const missingAttrsOfSelected = $derived.by(() => {
		const set = new Set<HygieneAttribute>();
		for (const b of books) {
			if (selectedBookIds.has(b.id)) {
				for (const a of b.missing_attributes) set.add(a);
			}
		}
		return [...set];
	});

	$effect(() => {
		if (missingAttrsOfSelected.length === 1) {
			batchField = missingAttrsOfSelected[0];
			batchFieldWasAutoSelected = true;
			return;
		}

		if (missingAttrsOfSelected.length > 1 && batchFieldWasAutoSelected) {
			batchField = null;
			batchFieldWasAutoSelected = false;
			return;
		}

		if (batchField && !missingAttrsOfSelected.includes(batchField)) {
			batchField = null;
			batchFieldWasAutoSelected = false;
		}
	});
</script>

<div class="flex flex-col gap-6 max-w-5xl mx-auto">
	<div class="hero rounded-2xl bg-base-100 shadow-sm border border-base-200">
		<div class="hero-content text-center py-10">
			<div class="max-w-2xl">
				<h1 class="text-2xl sm:text-3xl font-bold tracking-tight">{$_('dataHygiene.title')}</h1>
				<p class="text-base-content/70 mt-2">{$_('dataHygiene.description')}</p>
			</div>
		</div>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body">
			<h2 class="card-title text-base">{$_('dataHygiene.sectionFilters')}</h2>
			<div class="flex flex-wrap gap-2 items-center">
				{#each ATTRIBUTES as attr}
					<button
						class="btn btn-xs {selectedAttributes.includes(attr.key) ? 'btn-primary' : 'btn-outline'}"
						onclick={() => toggleAttribute(attr.key)}
					>
						{$_(attr.labelKey)}
						<span class="opacity-60">({totalMissingPerAttribute[attr.key] ?? '?'})</span>
					</button>
				{/each}
				<button class="btn btn-ghost btn-xs gap-1" onclick={() => { matchMode = matchMode === 'any' ? 'all' : 'any'; void loadData(true); }}>
					{$_(matchMode === 'any' ? 'dataHygiene.matchAny' : 'dataHygiene.matchAll')}
					<svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M6 9l6 6 6-6"/>
					</svg>
				</button>
			</div>
		</div>
	</div>

	<!-- Loading state -->
	{#if loading && books.length === 0}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body items-center py-10">
				<span class="loading loading-spinner loading-lg"></span>
				<p>{$_('dataHygiene.loading')}</p>
			</div>
		</div>
	<!-- Error state -->
	{:else if error && books.length === 0}
		<Alert type="error" onClose={() => (error = null)}>
			{error}
		</Alert>
	<!-- All complete state -->
	{:else if allComplete}
		<Alert type="success">
			{$_(selectedAttributes.length > 0 ? 'dataHygiene.allSetFiltered' : 'dataHygiene.allSet')}
		</Alert>
	<!-- Empty results -->
	{:else if !loading && books.length === 0}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body py-10 text-center">
				<p class="text-base-content/60">{$_('dataHygiene.noMissingBooks')}</p>
			</div>
		</div>
	<!-- Results table -->
	{:else}
		<div class="divider text-base-content/60 text-xs uppercase tracking-widest font-semibold">{$_('dataHygiene.sectionResults')}</div>

		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body p-0 overflow-x-auto">
				<table class="table table-sm">
					<thead>
						<tr>
							<th class="w-8">
								<input
									type="checkbox"
									class="checkbox checkbox-xs"
									checked={selectedBookIds.size === books.length && books.length > 0}
									onchange={toggleSelectAll}
									aria-label={selectedBookIds.size === books.length ? $_('dataHygiene.deselectAll') : $_('dataHygiene.selectAll')}
								/>
							</th>
							<th>{$_('book.title')}</th>
							<th class="hidden lg:table-cell">{$_('book.author')}</th>
							<th class="hidden lg:table-cell">{$_('book.isbn')}</th>
							<th class="hidden xl:table-cell">{$_('book.publisher')}</th>
							<th>{$_('dataHygiene.tableHeaderMissing')}</th>
							<th class="w-20 xl:w-28">{$_('dataHygiene.actions')}</th>
						</tr>
					</thead>
					<tbody>
						{#each books as book (book.id)}
							<tr class="hover">
								<td>
									<div class="flex items-center">
										<input
											type="checkbox"
											class="checkbox checkbox-xs"
											checked={selectedBookIds.has(book.id)}
											onchange={() => toggleBook(book.id)}
											aria-label={$_('common.search')}
										/>
									</div>
								</td>
								<td class="font-medium break-words min-w-0">{book.title}</td>
								<td class="hidden lg:table-cell max-w-[180px] truncate">{book.author || '—'}</td>
								<td class="hidden lg:table-cell font-mono text-xs">{book.isbn || '—'}</td>
								<td class="hidden xl:table-cell max-w-[150px] truncate">{book.publisher || '—'}</td>
								<td>
									<div class="flex flex-wrap gap-1">
										{#each book.missing_attributes as attr}
											<span class="badge badge-outline badge-xs">{$_(ATTRIBUTES.find(a => a.key === attr)?.labelKey ?? attr)}</span>
										{/each}
									</div>
								</td>
								<td>
									<div class="flex items-center gap-1 sm:gap-2">
										<button
											class="btn btn-ghost btn-xs gap-1"
											onclick={() => void openBookDetails(book)}
											disabled={detailLoadingBookId === book.id}
											aria-label={$_('dataHygiene.openDetails')}
											title={$_('dataHygiene.openDetails')}
										>
											{#if detailLoadingBookId === book.id}
												<span class="loading loading-spinner loading-xs"></span>
											{:else}
												<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
													<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/>
													<circle cx="12" cy="12" r="3"/>
												</svg>
											{/if}
											<span class="hidden xl:inline">{$_('dataHygiene.detailsShort')}</span>
										</button>
										<button
											class="btn btn-ghost btn-xs gap-1"
											onclick={() => openCoverViewer(book)}
											disabled={!book.cover_url}
											aria-label={$_('dataHygiene.viewCover')}
											title={book.cover_url ? $_('dataHygiene.viewCover') : $_('dataHygiene.noCover')}
										>
											<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
												<rect x="3" y="3" width="18" height="18" rx="2"/>
												<circle cx="8.5" cy="8.5" r="1.5"/>
												<path d="M21 15l-5-5L5 21"/>
											</svg>
											<span class="hidden xl:inline">{$_('dataHygiene.coverShort')}</span>
										</button>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if hasMore}
				<div class="card-body border-t border-base-200 flex flex-row items-center justify-between">
					<span class="text-xs text-base-content/60">
						{$_('dataHygiene.showingCount', {
							values: { shown: books.length, total }
						})}
					</span>
					<button
						class="btn btn-outline btn-sm"
						onclick={loadMore}
						disabled={loading}
					>
						{#if loading}
							<LoaderCircle class="w-4 h-4 animate-spin" />
						{/if}
						{$_('dataHygiene.loadMore')}
					</button>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Batch action bar -->
	{#if selectedCount > 0}
		<div class="fixed bottom-0 left-0 right-0 z-40 flex justify-center pointer-events-none p-4">
			<div class="bg-base-100 border border-base-300 shadow-xl rounded-2xl p-4 flex flex-wrap items-center gap-3 pointer-events-auto max-w-3xl w-full">
				<span class="text-sm font-medium whitespace-nowrap">
					{$_('dataHygiene.nSelected', { values: { count: selectedCount } })}
				</span>

				<select
					class="select select-bordered select-xs w-44 sm:w-52 flex-none"
					bind:value={batchField}
					onchange={() => (batchFieldWasAutoSelected = false)}
					aria-label={$_('dataHygiene.batchFieldLabel')}
				>
					<option value={null}>{$_('dataHygiene.batchFieldPlaceholder')}</option>
					{#each missingAttrsOfSelected as attr}
						<option value={attr}>{$_(ATTRIBUTES.find(a => a.key === attr)?.labelKey ?? attr)}</option>
					{/each}
				</select>

				{#if batchField === 'page_count' || batchField === 'published_year'}
					<input
						type="number"
						class="input input-bordered input-xs w-24"
						bind:value={batchValue}
						placeholder={$_('dataHygiene.batchValuePlaceholder')}
						aria-label={$_('dataHygiene.batchValueLabel')}
					/>
				{:else}
					<input
						type="text"
						class="input input-bordered input-xs flex-1 min-w-[140px]"
						bind:value={batchValue}
						placeholder={$_('dataHygiene.batchValuePlaceholder')}
						aria-label={$_('dataHygiene.batchValueLabel')}
						list={batchField === 'author' ? 'author-suggestions' : batchField === 'publisher' ? 'publisher-suggestions' : undefined}
					/>
				{/if}

				<button
					class="btn btn-primary btn-sm"
					onclick={openBatchConfirm}
					disabled={batchUpdating}
				>
					{$_('dataHygiene.applyBatch')}
				</button>
			</div>
		</div>
	{/if}
</div>

{#if coverViewer}
	<div
		class="fixed inset-0 z-[120] bg-black/70 backdrop-blur-sm"
		role="button"
		tabindex="-1"
		onclick={closeCoverViewer}
		onkeydown={(e) => e.key === 'Escape' && closeCoverViewer()}
	></div>
	<div class="fixed inset-0 z-[130] p-3 sm:p-6 flex items-center justify-center pointer-events-none">
		<div class="w-full max-w-4xl pointer-events-auto">
			<div class="relative bg-base-100 rounded-2xl shadow-2xl border border-base-300 overflow-hidden">
				<button
					class="btn btn-ghost btn-sm btn-circle absolute top-2 right-2 z-10 bg-base-100/90 shadow"
					onclick={closeCoverViewer}
					aria-label={$_('common.close')}
				>
					<X class="w-4 h-4" />
				</button>
				<div class="bg-base-200/60 px-4 py-2 text-sm font-medium truncate">{coverViewer.title}</div>
				<div class="p-2 sm:p-4 bg-base-200/40">
					<img
						src={coverViewer.coverUrl}
						alt={$_('book.coverOf', { values: { title: coverViewer.title } })}
						class="w-full max-h-[78dvh] object-contain rounded-xl"
					/>
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- Confirmation dialog -->
<dialog class="modal" class:modal-open={showBatchConfirm}>
	<div class="modal-box">
		<h3 class="text-lg font-bold">
			{$_('dataHygiene.confirmTitle', { values: { count: selectedCount } })}
		</h3>
		<p class="py-2 text-sm">
			{$_('dataHygiene.confirmBody', {
				values: { field: batchField ? $_(ATTRIBUTES.find(a => a.key === batchField)?.labelKey ?? batchField) : '—', value: batchValue || '—' }
			})}
		</p>
		<ul class="list-disc list-inside text-sm text-base-content/70 space-y-1 max-h-40 overflow-y-auto">
			{#each confirmPreviewBooks as title}
				<li>{title}</li>
			{/each}
			{#if selectedCount > confirmPreviewBooks.length}
				<li class="italic opacity-60">{$_('dataHygiene.andXMore', { values: { count: selectedCount - confirmPreviewBooks.length } })}</li>
			{/if}
		</ul>
		<div class="modal-action">
			<button class="btn btn-ghost btn-sm" onclick={() => (showBatchConfirm = false)}>
				{$_('dataHygiene.confirmCancel')}
			</button>
			<button class="btn btn-primary btn-sm" onclick={confirmBatchUpdate} disabled={batchUpdating}>
				{$_('dataHygiene.confirmApply')}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button onclick={() => (showBatchConfirm = false)}>{$_('common.close')}</button>
	</form>
</dialog>

<BookDetailDialog bind:book={selectedBook} bind:open={detailOpen} onEdit={openEditFromDetail} onDelete={handleDelete} />
<BookDrawer bind:book={selectedBook} bind:open={drawerOpen} onSave={handleSave} />
