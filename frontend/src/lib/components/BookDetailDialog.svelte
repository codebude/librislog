<script lang="ts">
	import type { Book, ReadingProgressEntry } from '$lib/types';
	import { _ } from '$lib/i18n';
	import { locale } from '$lib/i18n';
	import { formatDate, formatDateTime } from '$lib/date';
	import { getTimezone } from '$lib/stores/timezone';
	import { api } from '$lib/api';
	import { toasts } from '$lib/toasts';
	import { formatLanguageCode } from '$lib/utils/language';
	import StarRating from './StarRating.svelte';
	import { LineChart as LayerLineChart } from 'layerchart';
	import { curveCatmullRom } from 'd3-shape';

	const tz = getTimezone();

	let {
		book = $bindable(null),
		open = $bindable(false),
		onEdit,
		onDelete
	}: {
		book?: Book | null;
		open?: boolean;
		onEdit?: (book: Book) => void;
		onDelete?: (id: number) => void;
	} = $props();

	let blurbExpanded = $state(false);
	let confirmDelete = $state(false);
	let deleting = $state(false);
	let progressEntries: ReadingProgressEntry[] = $state([]);
	let currentPage = $state(0);
	let latestDbPage = $state(0);
	let progressLoading = $state(false);
	let logModalOpen = $state(false);
	let deletingEntry = $state<number | null>(null);
	let pendingDeleteEntry = $state<number | null>(null);

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

	function splitTags(raw: string | null): string[] {
		if (!raw) return [];
		return raw
			.split(',')
			.map((tag) => tag.trim())
			.filter(Boolean);
	}

	async function loadProgress() {
		if (!book) return;
		progressLoading = true;
		try {
			progressEntries = await api.books.progress.list(book.id);
			if (progressEntries.length > 0) {
				currentPage = progressEntries[0].page;
				latestDbPage = progressEntries[0].page;
			} else {
				currentPage = 0;
				latestDbPage = 0;
			}
		} catch {
			progressEntries = [];
			currentPage = 0;
			latestDbPage = 0;
		} finally {
			progressLoading = false;
		}
	}

	async function saveProgress() {
		if (!book || !book.page_count || currentPage === latestDbPage) return;
		try {
			const entry = await api.books.progress.create(book.id, currentPage);
			latestDbPage = currentPage;
			progressEntries = [entry, ...progressEntries.filter((e) => e.id !== entry.id)];
		} catch (e: unknown) {
			toasts.add(
				e instanceof Error ? e.message : $_('common.actionFailed', { values: { action: $_('common.save') } }),
				'error'
			);
		}
	}

	function handlePageBlur() {
		void saveProgress();
	}

	function handleSliderInput(event: Event) {
		const target = event.target as HTMLInputElement;
		currentPage = parseInt(target.value, 10);
	}

	async function deleteLogEntry(entryId: number) {
		if (!book || deletingEntry !== null) return;
		deletingEntry = entryId;
		try {
			await api.books.progress.delete(book.id, entryId);
			progressEntries = progressEntries.filter((e) => e.id !== entryId);
			if (progressEntries.length > 0 && latestDbPage === entryId) {
				latestDbPage = progressEntries[0].page;
			} else if (progressEntries.length === 0) {
				latestDbPage = 0;
			}
		} catch (e: unknown) {
			toasts.add(
				e instanceof Error ? e.message : $_('common.actionFailed', { values: { action: $_('common.delete') } }),
				'error'
			);
		} finally {
			deletingEntry = null;
		}
	}

	function handleProgressLogDelete(entryId: number) {
		pendingDeleteEntry = entryId;
	}

	function cancelDeleteEntry() {
		pendingDeleteEntry = null;
	}

	function openEdit() {
		if (!book) return;
		open = false;
		onEdit?.(book);
	}

	async function deleteBook() {
		if (!book) return;
		deleting = true;
		try {
			await api.books.delete(book.id);
			onDelete?.(book.id);
			open = false;
		} catch (e: unknown) {
			toasts.add(
				e instanceof Error
					? e.message
					: $_('common.actionFailed', { values: { action: $_('common.delete') } }),
				'error'
			);
		} finally {
			deleting = false;
		}
	}

	const uniqueDays = $derived.by(() => {
		const seen = new Set<string>();
		return progressEntries.filter((e) => {
			const day = formatDate(e.created_at, tz);
			if (seen.has(day)) return false;
			seen.add(day);
			return true;
		}).reverse();
	});

	const lineChartData = $derived.by(() => {
		if (uniqueDays.length < 1) return [];
		const oldestEntry = uniqueDays[0];
		const useStartDate = !!book?.date_started && formatDate(book.date_started, tz) < formatDate(oldestEntry.created_at, tz);
		const rawStart = useStartDate ? book.date_started : (book?.date_added ?? null);
		if (!rawStart) return [];
		const virtualEntry: ReadingProgressEntry = {
			id: 0,
			book_id: book?.id ?? 0,
			page: 0,
			created_at: rawStart,
			updated_at: rawStart
		};
		const entries = [virtualEntry, ...uniqueDays];
		return entries.map((e) => ({
			date: formatDate(e.created_at, tz),
			page: e.page
		}));
	});

	$effect(() => {
		if (open && book) {
			confirmDelete = false;
			blurbExpanded = false;
			void loadProgress();
		}
		if (!open && book && currentPage !== latestDbPage) {
			void saveProgress();
		}
	});
</script>

{#if open && book}
	<div
		class="fixed inset-0 bg-black/40 z-40"
		role="button"
		tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (open = false)}
	></div>

	<div class="fixed top-0 right-0 h-full w-full max-w-md bg-base-100 shadow-xl z-50 flex flex-col overflow-hidden">
		<div class="flex items-center justify-between p-4 border-b border-base-200">
			<div class="min-w-0 flex-1">
				<h2 class="text-lg font-bold truncate">{book.title}</h2>
				{#if book.subtitle}
					<p class="text-sm text-base-content/50 italic truncate">{book.subtitle}</p>
				{/if}
			</div>
			<button
				class="btn btn-ghost btn-sm btn-circle shrink-0"
				onclick={() => (open = false)}
				aria-label={$_('common.close')}
			>✕</button>
		</div>

		<div class="p-4 flex-1 min-h-0 overflow-y-auto flex flex-col gap-4">
			<div class="rounded-lg bg-base-200 overflow-hidden aspect-[2/3] w-40 self-center">
				{#if book.cover_url}
					<img
						src={book.cover_url}
						alt={$_('book.coverOf', { values: { title: book.title } })}
						class="w-full h-full object-cover"
					/>
				{/if}
			</div>

			<div class="flex items-center justify-between gap-2">
				<div class="text-sm text-base-content/70">{book.author ?? '-'}</div>
				<span class="badge badge-sm {STATUS_BADGE[book.reading_status]}">{$_(STATUS_LABEL_KEYS[book.reading_status])}</span>
			</div>

			<div class="text-sm">
				<div class="text-xs text-base-content/60">{$_('book.isbn')}</div>
				<div class="font-mono break-all">{book.isbn ?? '-'}</div>
			</div>

			<div>
				<div class="text-xs text-base-content/60 mb-1">{$_('common.rating')}</div>
				<StarRating value={book.rating} readonly />
			</div>

			<div class="grid grid-cols-2 gap-3 text-sm">
				<div>
					<div class="text-xs text-base-content/60">{$_('book.language')}</div>
					<div>{formatLanguageCode(book.language, $locale ?? 'en')}</div>
				</div>
				<div>
					<div class="text-xs text-base-content/60">{$_('book.publisher')}</div>
					<div>{book.publisher ?? '-'}</div>
				</div>
				<div>
					<div class="text-xs text-base-content/60">{$_('book.year')}</div>
					<div>{book.published_year ?? '-'}</div>
				</div>
				<div>
					<div class="text-xs text-base-content/60">{$_('book.pages')}</div>
					<div>{book.page_count ?? '-'}</div>
				</div>
				<div>
					<div class="text-xs text-base-content/60">{$_('book.dateStarted')}</div>
					<div>{book.date_started ? formatDate(book.date_started, tz) : '-'}</div>
				</div>
				<div>
					<div class="text-xs text-base-content/60">{$_('book.dateFinished')}</div>
					<div>{book.date_finished ? formatDate(book.date_finished, tz) : '-'}</div>
				</div>
				<div>
					<div class="text-xs text-base-content/60">{$_('book.tags')}</div>
					{#if splitTags(book.tags).length > 0}
						<div class="flex flex-wrap gap-1">
							{#each splitTags(book.tags) as tag (tag)}
								<span class="badge badge-outline badge-primary h-auto py-1 px-2 max-w-full whitespace-normal break-all leading-tight">{tag}</span>
							{/each}
						</div>
					{:else}
						<div>-</div>
					{/if}
				</div>
			</div>

			<!-- Reading Progress Block -->
			<div class="border-t border-base-200 pt-3 {!book.page_count ? 'opacity-50 pointer-events-none' : ''}">
				<div class="text-xs text-base-content/60 mb-2">{$_('book.readingProgress')}</div>

				{#if !book.page_count}
					<p class="text-sm text-base-content/50 italic">{$_('book.setPageCountFirst')}</p>
				{:else if progressLoading}
					<div class="flex items-center gap-2 text-sm text-base-content/50">
						<span class="loading loading-spinner loading-xs"></span>
						{$_('common.loadingEllipsis')}
					</div>
				{:else}
					<div class="flex items-center gap-2">
						<span class="text-sm font-mono">
							<input
								type="number"
								class="input input-bordered input-sm w-20 text-center"
								bind:value={currentPage}
								min="0"
								max={book.page_count}
								onblur={handlePageBlur}
							/>
							<span class="mx-1">/</span>
							{book.page_count}
						</span>
						<button
							type="button"
							class="btn btn-ghost btn-xs"
							onclick={() => (logModalOpen = true)}
						>{$_('book.progressLog')}</button>
					</div>

					<input
						type="range"
						min="0"
						max={book.page_count}
						class="range range-primary range-xs mt-2"
						value={currentPage}
						oninput={handleSliderInput}
						onchange={handlePageBlur}
					/>
				{/if}
			</div>

			{#if lineChartData.length >= 2}
				<div class="border-t border-base-200 pt-3">
					<div class="text-xs text-base-content/60 mb-2">{$_('book.progressGraph')}</div>
					<div class="border border-base-300 rounded-xl bg-base-100">
						<LayerLineChart
							data={lineChartData}
							x="date"
							y="page"
							height={200}
							points
							series={[{ key: 'default', value: 'page', color: 'var(--color-primary)', label: $_('book.currentPage') }]}
							yDomain={[0, Math.max(...lineChartData.map((d) => d.page), book?.page_count ?? 1)]}
							props={{ xAxis: { tickSpacing: 80 }, spline: { curve: curveCatmullRom } }}
						/>
					</div>
				</div>
			{/if}

			<div>
				<div class="text-xs text-base-content/60 mb-1">{$_('book.notes')}</div>
				<div class="text-sm whitespace-pre-wrap break-words rounded border border-base-200 p-2 min-h-12">
					{book.notes ?? '-'}
				</div>
			</div>

			{#if book.blurb}
				<div class="divider my-1"></div>
				<h3 class="text-sm font-semibold mb-2">{$_('book.about')}</h3>
				{@const MAX_BLURB_LENGTH = 300}
				{@const isTruncated = book.blurb.length > MAX_BLURB_LENGTH}
				{@const displayBlurb = blurbExpanded || !isTruncated
					? book.blurb
					: book.blurb.slice(0, MAX_BLURB_LENGTH) + '...'}
				<div class="text-sm whitespace-pre-wrap break-words rounded border border-base-200 p-3">
					{displayBlurb}
					{#if isTruncated}
						<button
							type="button"
							class="link link-primary text-xs ml-2"
							onclick={() => (blurbExpanded = !blurbExpanded)}
						>
							{blurbExpanded ? $_('common.readLess') : $_('common.readMore')}
						</button>
					{/if}
				</div>
			{/if}
		</div>

		<div class="sticky bottom-0 bg-base-100 p-4 border-t border-base-200 flex gap-2">
			<button type="button" class="btn btn-primary btn-sm flex-1" onclick={openEdit}>{$_('common.edit')}</button>
			{#if !confirmDelete}
				<button
					type="button"
					class="btn btn-error btn-outline btn-sm"
					onclick={() => (confirmDelete = true)}
				>{$_('common.delete')}</button>
			{:else}
				<button type="button" class="btn btn-error btn-sm" disabled={deleting} onclick={deleteBook}
					>{deleting ? $_('common.deleting') : $_('common.confirm')}</button
				>
				<button type="button" class="btn btn-ghost btn-sm" onclick={() => (confirmDelete = false)}
					>{$_('common.cancel')}</button
				>
			{/if}
		</div>
	</div>

	<!-- Progress Log Modal -->
	{#if logModalOpen}
		<div
			class="fixed inset-0 bg-black/40 z-50"
			role="button"
			tabindex="-1"
			onclick={() => (logModalOpen = false)}
			onkeydown={(e) => e.key === 'Escape' && (logModalOpen = false)}
		></div>
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
			<div class="bg-base-100 rounded-xl shadow-xl max-w-sm w-full max-h-96 overflow-y-auto pointer-events-auto" role="dialog" aria-label={$_('book.progressLog')}>
				<div class="sticky top-0 bg-base-100 z-10 flex items-center justify-between p-4 border-b border-base-200">
					<h3 class="font-bold text-sm">{$_('book.progressLog')}</h3>
					<button
						type="button"
						class="btn btn-ghost btn-xs btn-circle"
						onclick={() => (logModalOpen = false)}
						aria-label={$_('common.close')}
					>✕</button>
				</div>
				<div class="p-4">
					{#if progressEntries.length === 0}
						<p class="text-sm text-base-content/60 text-center py-4">{$_('book.progressLogEmpty')}</p>
					{:else}
						<table class="table table-xs">
							<thead>
								<tr>
									<th>{$_('book.logDate')}</th>
									<th>{$_('book.logPage')}</th>
									<th></th>
								</tr>
							</thead>
							<tbody>
								{#each progressEntries as entry (entry.id)}
									<tr>
										<td class="text-xs">{formatDateTime(entry.created_at, tz)}</td>
										<td class="font-mono text-sm">{entry.page}</td>
										<td class="text-right">
											{#if pendingDeleteEntry === entry.id}
												<span class="text-xs text-base-content/60 mr-2">{$_('book.deleteEntryConfirm')}</span>
												<button
													type="button"
													class="btn btn-error btn-xs"
													disabled={deletingEntry === entry.id}
													onclick={() => { pendingDeleteEntry = null; void deleteLogEntry(entry.id); }}
												>
													{deletingEntry === entry.id ? '...' : $_('common.confirm')}
												</button>
												<button
													type="button"
													class="btn btn-ghost btn-xs"
													disabled={deletingEntry === entry.id}
													onclick={cancelDeleteEntry}
												>{$_('common.cancel')}</button>
											{:else}
												<button
													type="button"
													class="btn btn-ghost btn-xs text-error"
													disabled={deletingEntry !== null}
													onclick={() => handleProgressLogDelete(entry.id)}
												>
													{$_('book.deleteEntry')}
												</button>
											{/if}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					{/if}
				</div>
			</div>
		</div>
	{/if}
{/if}
