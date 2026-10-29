<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '#lib/api.js';
	import { _ } from '#lib/i18n/index.js';
	import { toasts } from '#lib/toasts.js';
	import { localizeError } from '#lib/errors.js';
	import Alert from '#lib/components/Alert.svelte';
	import BookDetailDialog from '#lib/components/BookDetailDialog.svelte';
	import BookDrawer from '#lib/components/BookDrawer.svelte';
	import SearchBar from '#lib/components/SearchBar.svelte';
	import TagInput from '#lib/components/TagInput.svelte';
	import { LoaderCircle } from '@lucide/svelte';
	import { chunk, findCaseVariants } from '#lib/utils/tagBatch.js';
	import type { Book, Medium, ReadingStatus, AcquisitionStatus } from '#lib/types.js';
	import type { TagListEntry } from '#lib/types.js';

	const PAGE_SIZE = 50;
	const CHUNK_SIZE = 500;

	let searchQuery = $state('');
	let statusFilter = $state<ReadingStatus | ''>('');
	let mediumFilter = $state<Medium | ''>('');
	let acquisitionFilter = $state<AcquisitionStatus | ''>('');
	let tagFilter = $state('');
	let tagMode = $state<'has' | 'lacks'>('has');

	let books = $state<Book[]>([]);
	let total = $state(0);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let offset = $state(0);
	let hasMore = $state(false);
	let loadToken = 0;

	let selectedIds = $state<Set<number>>(new Set());
	let allMatchingIds = $state<number[] | null>(null);

	let selectedBook = $state<Book | null>(null);
	let detailOpen = $state(false);
	let drawerOpen = $state(false);
	let detailLoadingBookId = $state<number | null>(null);

	let availableTags = $state<TagListEntry[]>([]);

	let addTags = $state<string[]>([]);
	let removeTags = $state<string[]>([]);

	let batchUpdating = $state(false);
	let showConfirm = $state(false);
	let progressText = $state('');

	const selectedCount = $derived(
		allMatchingIds !== null ? allMatchingIds.length : selectedIds.size
	);

	const caseVariants = $derived(findCaseVariants(addTags, availableTags.map((t) => t.name)));

	const overlapTags = $derived(
		addTags.filter((t) => removeTags.some((r) => r.toLowerCase() === t.toLowerCase()))
	);

	const hasWork = $derived(addTags.length > 0 || removeTags.length > 0);

	const allSelectedLoaded = $derived(books.length > 0 && selectedIds.size === books.length);

	async function loadTags() {
		try {
			const res = await api.tags.list({ limit: 5000 });
			availableTags = res.tags;
		} catch (e: unknown) {
			// non-fatal; suggestions endpoint still works
			availableTags = [];
		}
	}

	async function loadData(reset: boolean = true) {
		const token = ++loadToken;
		if (reset) {
			offset = 0;
			selectedIds = new Set();
			allMatchingIds = null;
		}
		loading = true;
		error = null;
		try {
			const res = await api.books.list({
				q: searchQuery || undefined,
				status: statusFilter || undefined,
				medium: mediumFilter || undefined,
				acquisition_status: acquisitionFilter || undefined,
				tag: tagFilter && tagMode === 'has' ? tagFilter : undefined,
				exclude_tag: tagFilter && tagMode === 'lacks' ? tagFilter : undefined,
				offset,
				limit: PAGE_SIZE,
				sort: 'title',
				order: 'asc',
				smart_sort: false
			});
			if (token !== loadToken) return;
			if (reset) {
				books = res.books;
			} else {
				books = [...books, ...res.books];
			}
			total = res.total;
			hasMore = offset + PAGE_SIZE < total;
		} catch (e: unknown) {
			if (token !== loadToken) return;
			error = localizeError(e, $_, $_('tagEditor.loadFailed'));
			if (reset) books = [];
			else offset = Math.max(0, offset - PAGE_SIZE);
		} finally {
			if (token === loadToken) loading = false;
		}
	}

	onMount(() => {
		void loadTags();
		void loadData(true);
	});

	function resetFilters() {
		searchQuery = '';
		statusFilter = '';
		mediumFilter = '';
		acquisitionFilter = '';
		tagFilter = '';
		tagMode = 'has';
		void loadData(true);
	}

	function toggleBook(id: number) {
		const next = new Set(selectedIds);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		selectedIds = next;
		allMatchingIds = null;
	}

	function toggleSelectAllLoaded() {
		if (selectedIds.size === books.length && books.length > 0) {
			selectedIds = new Set();
		} else {
			selectedIds = new Set(books.map((b) => b.id));
		}
		allMatchingIds = null;
	}

	async function selectAllMatching() {
		try {
			const res = await api.books.ids({
				q: searchQuery || undefined,
				status: statusFilter || undefined,
				medium: mediumFilter || undefined,
				acquisition_status: acquisitionFilter || undefined,
				tag: tagFilter && tagMode === 'has' ? tagFilter : undefined,
				exclude_tag: tagFilter && tagMode === 'lacks' ? tagFilter : undefined
			});
			allMatchingIds = res.ids;
			selectedIds = new Set();
		} catch (e: unknown) {
			toasts.add(localizeError(e, $_, $_('tagEditor.loadFailed')), 'error');
		}
	}

	function clearSelection() {
		selectedIds = new Set();
		allMatchingIds = null;
	}

	async function openBookDetails(book: Book) {
		detailLoadingBookId = book.id;
		try {
			selectedBook = await api.books.get(book.id);
			detailOpen = true;
			drawerOpen = false;
		} catch (e: unknown) {
			toasts.add(localizeError(e, $_, $_('tagEditor.loadFailed')), 'error');
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
		await loadTags();
	}

	function handleDelete(id: number) {
		detailOpen = false;
		drawerOpen = false;
		selectedIds = new Set([...selectedIds].filter((bookId) => bookId !== id));
		void loadData(true);
	}

	function loadMore() {
		const nextOffset = offset + PAGE_SIZE;
		offset = nextOffset;
		void loadData(false);
	}

	const previewBooks = $derived(
		allMatchingIds !== null
			? []
			: books.filter((b) => selectedIds.has(b.id)).slice(0, 10)
	);

	function openConfirm() {
		if (!hasWork) {
			toasts.add($_('tagEditor.noTagsEntered'), 'warning');
			return;
		}
		if (overlapTags.length > 0) {
			toasts.add($_('tagEditor.overlapError'), 'error');
			return;
		}
		if (selectedCount === 0) {
			toasts.add($_('tagEditor.noSelection'), 'warning');
			return;
		}
		showConfirm = true;
	}

	async function confirmBatchUpdate() {
		batchUpdating = true;
		progressText = '';

		const ids =
			allMatchingIds !== null
				? allMatchingIds
				: [...selectedIds];

		const batches = chunk(ids, CHUNK_SIZE);
		let totalChanged = 0;
		let totalLinksAdded = 0;
		let totalLinksRemoved = 0;
		const createdTags = new Set<string>();
		const deletedTags = new Set<string>();
		let completedChunks = 0;

		try {
			for (let i = 0; i < batches.length; i++) {
				progressText = $_('tagEditor.progress', {
					values: { current: i + 1, total: batches.length }
				});
				const res = await api.tags.batch({
					book_ids: batches[i],
					add: addTags,
					remove: removeTags
				});
				totalChanged += res.books_changed;
				totalLinksAdded += res.links_added;
				totalLinksRemoved += res.links_removed;
				res.created_tags.forEach((t) => createdTags.add(t));
				res.deleted_tags.forEach((t) => deletedTags.add(t));
				completedChunks = i + 1;
			}

			const parts: string[] = [];
			if (totalChanged > 0) parts.push($_('tagEditor.changed', { values: { count: totalChanged } }));
			if (totalLinksAdded > 0) parts.push($_('tagEditor.linksAdded', { values: { count: totalLinksAdded } }));
			if (totalLinksRemoved > 0) parts.push($_('tagEditor.linksRemoved', { values: { count: totalLinksRemoved } }));
			if (deletedTags.size > 0) parts.push($_('tagEditor.deletedTags', { values: { tags: [...deletedTags].join(', ') } }));
			toasts.add(parts.length ? parts.join(' · ') : $_('tagEditor.noChanges'), 'success');

			addTags = [];
			removeTags = [];
			clearSelection();
			await loadTags();
			await loadData(true);
		} catch (e: unknown) {
			const msg = $_('tagEditor.updateFailedPartial', {
				values: { completed: completedChunks, total: batches.length }
			});
			toasts.add(localizeError(e, $_, msg), 'error');
			await loadTags();
			await loadData(true);
		} finally {
			batchUpdating = false;
			progressText = '';
			showConfirm = false;
		}
	}

	function useExistingSpelling(existing: string, current: string) {
		const idx = addTags.findIndex((t) => t.toLowerCase() === current.toLowerCase());
		if (idx >= 0) {
			const next = [...addTags];
			next[idx] = existing;
			addTags = next;
		}
	}
</script>

<div class="flex flex-col gap-6 max-w-5xl mx-auto pb-28">
	<div class="hero rounded-2xl bg-base-100 shadow-sm border border-base-200">
		<div class="hero-content text-center py-10">
			<div class="max-w-2xl">
				<h1 class="text-2xl sm:text-3xl font-bold tracking-tight">{$_('tagEditor.title')}</h1>
				<p class="text-base-content/70 mt-2">{$_('tagEditor.description')}</p>
			</div>
		</div>
	</div>

	<!-- Filters -->
	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-3">
			<h2 class="card-title text-base">{$_('tagEditor.sectionFilters')}</h2>
			<div class="flex flex-col gap-3">
				<SearchBar bind:value={searchQuery} onSearch={(q) => { searchQuery = q; void loadData(true); }} />
				<div class="flex flex-wrap gap-2 items-center">
					<select
						class="select select-bordered select-sm"
						bind:value={statusFilter}
						onchange={() => void loadData(true)}
						aria-label={$_('tagEditor.statusFilter')}
					>
						<option value="">{$_('tagEditor.allStatuses')}</option>
						<option value="want_to_read">{$_('status.want_to_read')}</option>
						<option value="currently_reading">{$_('status.currently_reading')}</option>
						<option value="read">{$_('status.read')}</option>
						<option value="did_not_finish">{$_('status.did_not_finish')}</option>
					</select>

					<select
						class="select select-bordered select-sm"
						bind:value={mediumFilter}
						onchange={() => void loadData(true)}
						aria-label={$_('tagEditor.mediumFilter')}
					>
						<option value="">{$_('tagEditor.allMedia')}</option>
						<option value="Print">{$_('medium.print')}</option>
						<option value="eBook">{$_('medium.ebook')}</option>
						<option value="Audiobook">{$_('medium.audiobook')}</option>
						<option value="Comic / Graphic Novel">{$_('medium.comic_graphic_novel')}</option>
						<option value="Magazine / Newspaper">{$_('medium.magazine_newspaper')}</option>
					</select>

					<select
						class="select select-bordered select-sm"
						bind:value={acquisitionFilter}
						onchange={() => void loadData(true)}
						aria-label={$_('tagEditor.acquisitionFilter')}
					>
						<option value="">{$_('tagEditor.allAcquisition')}</option>
						<option value="owned">{$_('acquisition.owned')}</option>
						<option value="borrowed">{$_('acquisition.borrowed')}</option>
						<option value="digital_access">{$_('acquisition.digital_access')}</option>
						<option value="to_acquire">{$_('acquisition.to_acquire')}</option>
					</select>

					<select
						class="select select-bordered select-sm"
						bind:value={tagFilter}
						onchange={() => void loadData(true)}
						aria-label={$_('tagEditor.tagFilter')}
					>
						<option value="">{$_('tagEditor.allTags')}</option>
						{#each availableTags as t (t.name)}
							<option value={t.name}>{t.name} ({t.count})</option>
						{/each}
					</select>

					{#if tagFilter}
						<div class="join">
							<button
								class="btn btn-xs join-item {tagMode === 'has' ? 'btn-primary' : 'btn-ghost'}"
								onclick={() => { tagMode = 'has'; void loadData(true); }}
							>{$_('tagEditor.tagHas')}</button>
							<button
								class="btn btn-xs join-item {tagMode === 'lacks' ? 'btn-primary' : 'btn-ghost'}"
								onclick={() => { tagMode = 'lacks'; void loadData(true); }}
							>{$_('tagEditor.tagLacks')}</button>
						</div>
					{/if}

					<button class="btn btn-ghost btn-xs" onclick={resetFilters}>
						{$_('tagEditor.resetFilters')}
					</button>
				</div>
			</div>
		</div>
	</div>

	{#if loading && books.length === 0}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body items-center py-10">
				<span class="loading loading-spinner loading-lg"></span>
				<p>{$_('tagEditor.loading')}</p>
			</div>
		</div>
	{:else if error && books.length === 0}
		<Alert type="error" onClose={() => (error = null)}>{error}</Alert>
	{:else if !loading && books.length === 0}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body py-10 text-center">
				<p class="text-base-content/60">{$_('tagEditor.noBooks')}</p>
			</div>
		</div>
	{:else}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body p-0 overflow-x-auto">
				<table class="table table-sm">
					<thead>
						<tr>
							<th class="w-8">
								<input
									type="checkbox"
									class="checkbox checkbox-xs"
									checked={allSelectedLoaded && allMatchingIds === null}
									disabled={allMatchingIds !== null}
									onchange={toggleSelectAllLoaded}
									aria-label={$_('tagEditor.selectAllLoaded')}
								/>
							</th>
							<th>{$_('book.title')}</th>
							<th class="hidden lg:table-cell">{$_('book.authorsLabel')}</th>
							<th class="hidden xl:table-cell">{$_('book.tags')}</th>
							<th class="hidden xl:table-cell">{$_('book.status')}</th>
						</tr>
					</thead>
					<tbody>
						{#each books as book (book.id)}
							<tr class="hover">
								<td>
									<input
										type="checkbox"
										class="checkbox checkbox-xs"
										checked={selectedIds.has(book.id) || allMatchingIds !== null}
										disabled={allMatchingIds !== null}
										onchange={() => toggleBook(book.id)}
										aria-label={book.title}
									/>
								</td>
								<td class="font-medium break-words min-w-0">
									<button
										class="link link-hover text-left"
										onclick={() => void openBookDetails(book)}
										disabled={detailLoadingBookId === book.id}
									>
										{#if detailLoadingBookId === book.id}
											<span class="loading loading-spinner loading-xs"></span>
										{:else}
											{book.title}
										{/if}
									</button>
								</td>
								<td class="hidden lg:table-cell max-w-[180px] truncate">
									{book.authors?.join(', ') ?? book.author ?? '—'}
								</td>
								<td class="hidden xl:table-cell">
									<div class="flex flex-wrap gap-1">
										{#if book.tags}
											{@const tags = book.tags.split(',').map((t) => t.trim()).filter(Boolean)}
											{#each tags.slice(0, 4) as tag (tag)}
												<span class="badge badge-outline badge-xs">{tag}</span>
											{/each}
											{#if tags.length > 4}
												<span class="badge badge-ghost badge-xs">+{tags.length - 4}</span>
											{/if}
										{:else}
											<span class="text-base-content/40 text-xs">—</span>
										{/if}
									</div>
								</td>
								<td class="hidden xl:table-cell text-xs">{$_(`status.${book.reading_status}`)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if hasMore}
				<div class="card-body border-t border-base-200 flex flex-row items-center justify-between">
					<span class="text-xs text-base-content/60">
						{$_('tagEditor.showingCount', { values: { shown: books.length, total } })}
					</span>
					<button class="btn btn-outline btn-sm" onclick={loadMore} disabled={loading}>
						{#if loading}
							<LoaderCircle class="w-4 h-4 animate-spin" />
						{/if}
						{$_('tagEditor.loadMore')}
					</button>
				</div>
			{/if}
		</div>

		{#if total > selectedCount && selectedCount > 0 && allMatchingIds === null}
			<div class="text-xs text-base-content/60 px-2">
				{$_('tagEditor.moreAvailable', { values: { total } })}
			</div>
		{/if}
	{/if}

	<!-- Select all matching -->
	{#if total > PAGE_SIZE && !loading}
		<div class="flex flex-wrap gap-2 items-center justify-between">
			{#if allMatchingIds === null}
				<button class="btn btn-ghost btn-sm" onclick={selectAllMatching}>
					{$_('tagEditor.selectAllMatching', { values: { count: total } })}
				</button>
			{:else}
				<span class="text-sm font-medium">
					{$_('tagEditor.allMatchingSelected', { values: { count: allMatchingIds.length } })}
				</span>
				<button class="btn btn-ghost btn-sm" onclick={clearSelection}>
					{$_('tagEditor.clearSelection')}
				</button>
			{/if}
		</div>
	{/if}
</div>

<!-- Batch action bar -->
{#if selectedCount > 0}
	<div class="fixed bottom-0 left-0 right-0 z-40 flex justify-center pointer-events-none p-4">
		<div class="bg-base-100 border border-base-300 shadow-xl rounded-2xl p-4 flex flex-wrap items-center gap-3 pointer-events-auto max-w-4xl w-full">
			<span class="text-sm font-medium whitespace-nowrap">
				{$_('tagEditor.nSelected', { values: { count: selectedCount } })}
			</span>

			<div class="flex-1 min-w-[180px] flex flex-col gap-1">
				<TagInput
					bind:values={addTags}
					name="add-tags"
					placeholder={$_('tagEditor.addPlaceholder')}
					fetchSuggestions={(q) => api.books.suggestions.tags(q)}
				/>
				{#if caseVariants.length > 0}
					<div class="text-xs text-warning">
						{#each caseVariants as v (v.name)}
							<div class="flex items-center gap-1">
								<span>{$_('tagEditor.caseVariant', { values: { name: v.name, existing: v.existing } })}</span>
								<button class="link link-primary" onclick={() => useExistingSpelling(v.existing, v.name)}>
									{$_('tagEditor.useExisting')}
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<div class="flex-1 min-w-[180px]">
				<TagInput
					bind:values={removeTags}
					name="remove-tags"
					placeholder={$_('tagEditor.removePlaceholder')}
					fetchSuggestions={(q) =>
						Promise.resolve(
							availableTags
								.map((t) => t.name)
								.filter((n) => n.toLowerCase().includes(q.toLowerCase()))
						)}
				/>
			</div>

			{#if overlapTags.length > 0}
				<div class="text-xs text-error w-full">
					{$_('tagEditor.overlapError')}
				</div>
			{/if}

			<button
				class="btn btn-primary btn-sm"
				onclick={openConfirm}
				disabled={batchUpdating || !hasWork}
			>
				{#if batchUpdating}
					<LoaderCircle class="w-4 h-4 animate-spin" />
				{/if}
				{$_('tagEditor.apply')}
			</button>
		</div>
	</div>
{/if}

<!-- Confirmation dialog -->
<dialog class="modal" class:modal-open={showConfirm}>
	<div class="modal-box">
		<h3 class="text-lg font-bold">
			{$_('tagEditor.confirmTitle', { values: { count: selectedCount } })}
		</h3>
		<p class="py-2 text-sm">
			{$_('tagEditor.confirmBody', {
				values: {
					add: addTags.length ? addTags.join(', ') : '—',
					remove: removeTags.length ? removeTags.join(', ') : '—'
				}
			})}
		</p>
		{#if allMatchingIds !== null}
			<p class="text-sm text-base-content/70 italic">
				{$_('tagEditor.confirmAllMatching', { values: { count: allMatchingIds.length } })}
			</p>
		{:else}
			<ul class="list-disc list-inside text-sm text-base-content/70 space-y-1 max-h-40 overflow-y-auto">
				{#each previewBooks as book (book.id)}
					<li>{book.title}</li>
				{/each}
				{#if selectedCount > previewBooks.length}
					<li class="italic opacity-60">{$_('tagEditor.andXMore', { values: { count: selectedCount - previewBooks.length } })}</li>
				{/if}
			</ul>
		{/if}
		{#if caseVariants.length > 0}
			<div class="mt-2 text-xs text-warning">
				{$_('tagEditor.caseVariantWarning')}
			</div>
		{/if}
		{#if progressText}
			<div class="mt-2 text-sm font-medium">{progressText}</div>
		{/if}
		<div class="modal-action">
			<button class="btn btn-ghost btn-sm" onclick={() => (showConfirm = false)} disabled={batchUpdating}>
				{$_('tagEditor.confirmCancel')}
			</button>
			<button class="btn btn-primary btn-sm" onclick={confirmBatchUpdate} disabled={batchUpdating}>
				{#if batchUpdating}
					<LoaderCircle class="w-4 h-4 animate-spin" />
				{/if}
				{$_('tagEditor.confirmApply')}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button onclick={() => { if (!batchUpdating) showConfirm = false; }}>{$_('common.close')}</button>
	</form>
</dialog>

<BookDetailDialog bind:book={selectedBook} bind:open={detailOpen} onEdit={openEditFromDetail} onDelete={handleDelete} />
<BookDrawer bind:book={selectedBook} bind:open={drawerOpen} onSave={handleSave} />