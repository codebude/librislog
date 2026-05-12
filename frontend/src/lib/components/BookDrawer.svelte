<script lang="ts">
	import type { Book, ReadingStatus } from '$lib/types';
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import { formatDate, fromDateInputValue, toDateInputValue } from '$lib/date';
	import StarRating from './StarRating.svelte';
	import CoverPicker from './CoverPicker.svelte';
	import DateConflictDialog from './DateConflictDialog.svelte';

	let {
		book = $bindable(null),
		open = $bindable(false),
		onSave,
		onDelete
	}: {
		book?: Book | null;
		open?: boolean;
		onSave?: (book: Book) => void;
		onDelete?: (id: number) => void;
	} = $props();

	let saving = $state(false);
	let deleting = $state(false);
	let confirmDelete = $state(false);
	let dateConflictOpen = $state(false);
	let conflictField = $state<'date_started' | 'date_finished'>('date_started');
	let conflictExistingDate = $state('');
	let conflictSuggestedDate = $state('');
	let pendingStatus = $state<ReadingStatus | null>(null);
	let pendingPayload = $state<Partial<Book> | null>(null);

	// Editable fields
	let title = $state('');
	let author = $state('');
	let notes = $state('');
	let rating = $state<number | null>(null);
	let reading_status = $state<ReadingStatus>('want_to_read');
	let publisher = $state('');
	let published_year = $state('');
	let page_count = $state('');
	let genre = $state('');
	let date_started = $state('');
	let date_finished = $state('');
	let cover_url = $state<string | null>(null);

	$effect(() => {
		if (book) {
			title = book.title;
			author = book.author ?? '';
			notes = book.notes ?? '';
			rating = book.rating;
			reading_status = book.reading_status;
			publisher = book.publisher ?? '';
			published_year = book.published_year !== null ? String(book.published_year) : '';
			page_count = book.page_count !== null ? String(book.page_count) : '';
			genre = book.genre ?? '';
			date_started = toDateInputValue(book.date_started);
			date_finished = toDateInputValue(book.date_finished);
			cover_url = book.cover_url ?? null;
			confirmDelete = false;
			dateConflictOpen = false;
			pendingStatus = null;
			pendingPayload = null;
		}
	});

	function buildNonStatusPayload(includeDates: boolean): Partial<Book> {
		const payload: Partial<Book> = {
			title,
			author: author || null,
			publisher: publisher || null,
			published_year: published_year ? parseInt(published_year, 10) : null,
			page_count: page_count ? parseInt(page_count, 10) : null,
			genre: genre || null,
			notes: notes || null,
			rating,
			cover_url: cover_url || null
		};

		if (includeDates) {
			payload.date_started = fromDateInputValue(date_started);
			payload.date_finished = fromDateInputValue(date_finished);
		}

		return payload;
	}

	async function applyPendingTransition(params: {
		forceDateStarted?: string | null;
		forceDateFinished?: string | null;
	}) {
		if (!book || !pendingStatus) return;

		const transition = await api.books.transitionStatus(book.id, {
			new_status: pendingStatus,
			force_date_started: params.forceDateStarted,
			force_date_finished: params.forceDateFinished
		});

		if (transition.date_conflict) {
			conflictField = transition.date_conflict.field;
			conflictExistingDate = transition.date_conflict.existing_date;
			conflictSuggestedDate = transition.date_conflict.suggested_date;
			dateConflictOpen = true;
			return;
		}

		let updated = transition.book;
		if (pendingPayload && Object.keys(pendingPayload).length > 0) {
			updated = await api.books.update(book.id, pendingPayload);
		}

		book = updated;
		onSave?.(updated);
		open = false;
		dateConflictOpen = false;
		pendingStatus = null;
		pendingPayload = null;
	}

	async function save() {
		if (!book) return;
		saving = true;
		try {
			const statusChanged = reading_status !== book.reading_status;
			const dateStartedChanged =
				fromDateInputValue(date_started) !== (book.date_started ?? null);
			const dateFinishedChanged =
				fromDateInputValue(date_finished) !== (book.date_finished ?? null);

			if (statusChanged) {
				pendingStatus = reading_status;
				pendingPayload = buildNonStatusPayload(dateStartedChanged || dateFinishedChanged);

				const transition = await api.books.transitionStatus(book.id, {
					new_status: reading_status
				});

				if (transition.date_conflict) {
					conflictField = transition.date_conflict.field;
					conflictExistingDate = transition.date_conflict.existing_date;
					conflictSuggestedDate = transition.date_conflict.suggested_date;
					dateConflictOpen = true;
					return;
				}

				let updated = transition.book;
				if (pendingPayload && Object.keys(pendingPayload).length > 0) {
					updated = await api.books.update(book.id, pendingPayload);
				}
				book = updated;
				onSave?.(updated);
				open = false;
				pendingStatus = null;
				pendingPayload = null;
				return;
			}

			const updated = await api.books.update(book.id, {
				...buildNonStatusPayload(true),
				reading_status
			});
			book = updated;
			onSave?.(updated);
			open = false;
		} catch (e: unknown) {
			toasts.add(
				e instanceof Error
					? e.message
					: $_('common.actionFailed', { values: { action: $_('common.save') } }),
				'error'
			);
		} finally {
			saving = false;
		}
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

	const STATUS_OPTIONS: { value: ReadingStatus; label: string }[] = [
		{ value: 'want_to_read', label: 'status.want_to_read' },
		{ value: 'currently_reading', label: 'status.currently_reading' },
		{ value: 'read', label: 'status.read' },
		{ value: 'did_not_finish', label: 'status.did_not_finish' }
	];
</script>

{#if open && book}
	<!-- Backdrop -->
	<div
		class="fixed inset-0 bg-black/40 z-40"
		role="button"
		tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (open = false)}
	></div>

	<!-- Drawer panel -->
	<div class="fixed top-0 right-0 h-full w-full max-w-md bg-base-100 shadow-xl z-50 flex flex-col overflow-y-auto">
		<!-- Header -->
		<div class="flex items-center justify-between p-4 border-b border-base-200">
			<h2 class="text-lg font-bold truncate">{book.title}</h2>
			<button
				class="btn btn-ghost btn-sm btn-circle"
				onclick={() => (open = false)}
				aria-label={$_('common.close')}
			>✕</button>
		</div>

		<!-- Editable form -->
		<form class="flex flex-col gap-3 px-4 pb-4 flex-1" onsubmit={(e) => { e.preventDefault(); save(); }}>
			<label class="form-control">
				<span class="label label-text">{$_('book.title')}</span>
				<input class="input input-bordered input-sm" bind:value={title} required />
			</label>

			<label class="form-control">
				<span class="label label-text">{$_('book.author')}</span>
				<input class="input input-bordered input-sm" bind:value={author} />
			</label>

			<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
				<label class="form-control sm:col-span-2">
					<span class="label label-text">{$_('book.publisher')}</span>
					<input class="input input-bordered input-sm" bind:value={publisher} />
				</label>

				<label class="form-control">
					<span class="label label-text">{$_('book.year')}</span>
					<input type="number" class="input input-bordered input-sm" bind:value={published_year} min="1000" max="2100" />
				</label>

				<label class="form-control">
					<span class="label label-text">{$_('book.pages')}</span>
					<input type="number" class="input input-bordered input-sm" bind:value={page_count} min="1" />
				</label>
			</div>

			<label class="form-control">
				<span class="label label-text">{$_('book.genre')}</span>
				<input class="input input-bordered input-sm" bind:value={genre} />
			</label>

			{#if book.isbn}
				<p class="text-xs text-base-content/60">{$_('book.isbn')}: <span class="font-mono">{book.isbn}</span></p>
			{/if}

			<label class="form-control">
				<span class="label label-text">{$_('book.status')}</span>
				<select class="select select-bordered select-sm" bind:value={reading_status}>
					{#each STATUS_OPTIONS as opt}
						<option value={opt.value}>{$_(opt.label)}</option>
					{/each}
				</select>
			</label>

			<div class="form-control">
				<span class="label label-text">{$_('common.rating')}</span>
				<StarRating value={rating} onChange={(v) => (rating = v)} />
			</div>

			<label class="form-control">
				<span class="label label-text">{$_('book.dateStarted')}</span>
				<input type="date" class="input input-bordered input-sm" bind:value={date_started} />
			</label>

			<label class="form-control">
				<span class="label label-text">{$_('book.dateFinished')}</span>
				<input type="date" class="input input-bordered input-sm" bind:value={date_finished} />
			</label>

			<label class="form-control">
				<span class="label label-text">{$_('book.notes')}</span>
				<textarea class="textarea textarea-bordered text-sm" rows="4" bind:value={notes}></textarea>
			</label>

			<CoverPicker bind:value={cover_url} disabled={saving} />

			<div class="flex gap-2 mt-auto pt-2">
				<button type="submit" class="btn btn-primary btn-sm flex-1" disabled={saving}>
					{saving ? $_('common.saving') : $_('common.save')}
				</button>
				{#if !confirmDelete}
					<button
						type="button"
						class="btn btn-error btn-outline btn-sm"
						onclick={() => (confirmDelete = true)}
					>{$_('common.delete')}</button>
				{:else}
					<button
						type="button"
						class="btn btn-error btn-sm"
						disabled={deleting}
						onclick={deleteBook}
					>{deleting ? $_('common.deleting') : $_('common.confirm')}</button>
					<button
						type="button"
						class="btn btn-ghost btn-sm"
						onclick={() => (confirmDelete = false)}
					>{$_('common.cancel')}</button>
				{/if}
			</div>
		</form>
	</div>

	<DateConflictDialog
		open={dateConflictOpen}
		field={conflictField}
		existingDate={formatDate(conflictExistingDate)}
		suggestedDate={formatDate(conflictSuggestedDate)}
		onCancel={() => {
			dateConflictOpen = false;
			pendingStatus = null;
			pendingPayload = null;
		}}
		onKeep={() => {
			dateConflictOpen = false;
			void applyPendingTransition({
				forceDateStarted: conflictField === 'date_started' ? conflictExistingDate : undefined,
				forceDateFinished: conflictField === 'date_finished' ? conflictExistingDate : undefined
			});
		}}
		onUseSuggested={() => {
			dateConflictOpen = false;
			void applyPendingTransition({
				forceDateStarted: conflictField === 'date_started' ? conflictSuggestedDate : undefined,
				forceDateFinished: conflictField === 'date_finished' ? conflictSuggestedDate : undefined
			});
		}}
	/>
{/if}
