<script lang="ts">
	import type { Book, ReadingStatus } from '$lib/types';
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import { formatDate, fromDateInputValue, toDateInputValue, today as tzToday } from '$lib/date';
	import { getTimezone } from '$lib/stores/timezone';
	import type { CoverCandidate } from '$lib/types';
	import StarRating from './StarRating.svelte';
	import CoverPicker from './CoverPicker.svelte';
	import SuggestionInput from './SuggestionInput.svelte';
	import TagInput from './TagInput.svelte';
	import DateConflictDialog from './DateConflictDialog.svelte';
	import AutoSearchCoverModal from './AutoSearchCoverModal.svelte';
	import BarcodeScanner from './BarcodeScanner.svelte';

	let {
		book = $bindable(null),
		open = $bindable(false),
		onSave
	}: {
		book?: Book | null;
		open?: boolean;
		onSave?: (book: Book) => void;
	} = $props();

	let tz = $state(getTimezone());
	let today = $state(tzToday(tz));
	let saving = $state(false);
	let dateConflictOpen = $state(false);
	let conflictField = $state<'date_started' | 'date_finished' | 'started_after_finished'>('date_started');
	let conflictExistingDate = $state('');
	let conflictSuggestedDate = $state('');
	let pendingStatus = $state<ReadingStatus | null>(null);
	let pendingPayload = $state<Partial<Book> | null>(null);
	let pendingProgressBook = $state<Book | null>(null);
	let autoSearchOpen = $state(false);
	let autoSearchLoading = $state(false);
	let autoSearchError = $state<string | null>(null);
	let autoSearchCandidates = $state<CoverCandidate[]>([]);
	let autoSearchRequestId = 0;
	let scannerOpen = $state(false);

	// Editable fields
	let title = $state('');
	let subtitle = $state('');
	let author = $state('');
	let isbn = $state('');
	let notes = $state('');
	let blurb = $state('');
	let rating = $state<number | null>(null);
	let reading_status = $state<ReadingStatus>('want_to_read');
	let publisher = $state('');
	let published_year = $state('');
	let page_count = $state('');
	let language = $state('');
	let tags = $state('');
	let date_started = $state('');
	let date_finished = $state('');
	let cover_url = $state<string | null>(null);

	$effect(() => {
		if (book) {
			title = book.title;
			subtitle = book.subtitle ?? '';
			author = book.author ?? '';
			isbn = book.isbn ?? '';
			notes = book.notes ?? '';
			blurb = book.blurb ?? '';
			rating = book.rating;
			reading_status = book.reading_status;
			publisher = book.publisher ?? '';
			published_year = book.published_year !== null ? String(book.published_year) : '';
			page_count = book.page_count !== null ? String(book.page_count) : '';
			language = book.language ?? '';
			tags = book.tags ?? '';
			date_started = toDateInputValue(book.date_started, tz);
			date_finished = toDateInputValue(book.date_finished, tz);
			cover_url = book.cover_url ?? null;
			dateConflictOpen = false;
			pendingStatus = null;
			pendingPayload = null;
		}
	});

	function buildNonStatusPayload(includeDates: boolean): Partial<Book> {
		const payload: Partial<Book> = {
			title,
			subtitle: subtitle || null,
			author: author.trim(),
			isbn: isbn || null,
			publisher: publisher || null,
			published_year: published_year ? parseInt(published_year, 10) : null,
			page_count: parseInt(page_count, 10),
			language: language || null,
			tags: tags || null,
			notes: notes || null,
			blurb: blurb || null,
			rating,
			cover_url: cover_url || null
		};

		if (includeDates) {
			payload.date_started = fromDateInputValue(date_started, tz);
			payload.date_finished = fromDateInputValue(date_finished, tz);
		}

		return payload;
	}

	async function applyPendingTransition(params: {
		forceDateStarted?: string | null;
		forceDateFinished?: string | null;
		skipAutoDateStarted?: boolean;
		clearDateStarted?: boolean;
	}) {
		if (!book || !pendingStatus) return;

		const dateFinishedWasNull = !book.date_finished;
		const dfCleared = !date_finished.trim() && !!book.date_finished;
		const ds = date_started.trim();
		const df = date_finished.trim();
		const dateStartedChanged =
			ds !== toDateInputValue(book.date_started, tz);
		const dateFinishedChanged =
			df !== toDateInputValue(book.date_finished, tz);

		const transition = await api.books.transitionStatus(book.id, {
			new_status: pendingStatus,
			force_date_started: params.forceDateStarted !== undefined
				? params.forceDateStarted
				: (dateStartedChanged && ds ? fromDateInputValue(date_started, tz) : undefined),
			force_date_finished: params.forceDateFinished !== undefined
				? params.forceDateFinished
				: (dateFinishedChanged && df ? fromDateInputValue(date_finished, tz) : undefined),
			skip_auto_date_started: params.skipAutoDateStarted,
			clear_date_started: params.clearDateStarted,
			...(dfCleared ? { clear_date_finished: true } : {})
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
			const { date_started: _, date_finished: __, ...cleanPayload } = pendingPayload;
			updated = await api.books.update(book.id, cleanPayload);
		}

		book = updated;
		if (dateFinishedWasNull && updated.date_finished && updated.page_count) {
			pendingProgressBook = updated;
			dateConflictOpen = false;
			pendingStatus = null;
			pendingPayload = null;
			return;
		}
		onSave?.(updated);
		open = false;
		dateConflictOpen = false;
		pendingStatus = null;
		pendingPayload = null;
	}

	async function save() {
		if (!book) return;
		if (!author.trim()) {
			toasts.add($_('error.authorRequired'), 'error');
			return;
		}
		if (!page_count) {
			toasts.add($_('error.pageCountRequired'), 'error');
			return;
		}
		const ds = date_started.trim();
		const df = date_finished.trim();
		if (ds && df && ds > df) {
			toasts.add($_('error.dateStartedAfterFinished'), 'error');
			return;
		}
		const statusChanged = reading_status !== book.reading_status;
		const dfCleared = !df && !!book.date_finished;
		if (dfCleared && reading_status === 'read' && !statusChanged) {
			toasts.add($_('error.dateFinishedRequiredForRead'), 'error');
			return;
		}
		const dateStartedChanged =
			ds !== toDateInputValue(book.date_started, tz);
		const dateFinishedChanged =
			df !== toDateInputValue(book.date_finished, tz);
		saving = true;
		try {
			const dateFinishedWasNull = !book.date_finished;

			if (statusChanged) {
				pendingStatus = reading_status;
				pendingPayload = buildNonStatusPayload(dateStartedChanged || dateFinishedChanged);

				const transition = await api.books.transitionStatus(book.id, {
					new_status: reading_status,
					...(dfCleared ? { clear_date_finished: true } : {}),
					...(dateStartedChanged && ds ? { force_date_started: fromDateInputValue(date_started, tz) } : {}),
					...(dateFinishedChanged && df ? { force_date_finished: fromDateInputValue(date_finished, tz) } : {})
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
					const { date_started: _, date_finished: __, ...cleanPayload } = pendingPayload;
					updated = await api.books.update(book.id, cleanPayload);
				}
				book = updated;
				if (dateFinishedWasNull && updated.date_finished && updated.page_count) {
					pendingProgressBook = updated;
					pendingStatus = null;
					pendingPayload = null;
					return;
				}
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
			if (dateFinishedWasNull && updated.date_finished && updated.page_count) {
				pendingProgressBook = updated;
				return;
			}
			onSave?.(updated);
			open = false;
		} catch (e: unknown) {
			const message =
				e instanceof Error && e.message === 'error.isbnAlreadyExists'
					? $_('error.isbnAlreadyExists')
					: e instanceof Error && e.message === 'error.dateInFuture'
						? $_('error.dateInFuture')
					: e instanceof Error && e.message === 'error.dateStartedAfterFinished'
						? $_('error.dateStartedAfterFinished')
					: e instanceof Error && e.message === 'error.dateFinishedRequiredForRead'
						? $_('error.dateFinishedRequiredForRead')
					: e instanceof Error
						? e.message
						: $_('common.actionFailed', { values: { action: $_('common.save') } });
			toasts.add(
				message,
				'error'
			);
		} finally {
			saving = false;
		}
	}

	const STATUS_OPTIONS: { value: ReadingStatus; label: string }[] = [
		{ value: 'want_to_read', label: 'status.want_to_read' },
		{ value: 'currently_reading', label: 'status.currently_reading' },
		{ value: 'read', label: 'status.read' },
		{ value: 'did_not_finish', label: 'status.did_not_finish' }
	];

	const coverSearchUrl = $derived.by(() => {
		const query = `${title} ${author}`.trim();
		return `https://www.google.com/search?q=${encodeURIComponent(query)}&udm=2&tbs=isz:l`;
	});

	const isIsbnFilled = $derived.by(() => isbn.trim().length > 0);

	async function openAutoSearchModal() {
		if (!isIsbnFilled) return;
		const requestId = ++autoSearchRequestId;
		autoSearchOpen = true;
		autoSearchLoading = true;
		autoSearchError = null;
		autoSearchCandidates = [];
		try {
			const result = await api.covers.searchCandidates(isbn.trim());
			if (requestId !== autoSearchRequestId) return;
			autoSearchCandidates = result.candidates.filter((candidate) => candidate.available);
		} catch (e: unknown) {
			if (requestId !== autoSearchRequestId) return;
			autoSearchError = e instanceof Error ? e.message : $_('book.autoSearchError');
			toasts.add(autoSearchError, 'error');
		} finally {
			if (requestId !== autoSearchRequestId) return;
			autoSearchLoading = false;
		}
	}

	function closeAutoSearchModal() {
		autoSearchRequestId += 1;
		autoSearchOpen = false;
		autoSearchError = null;
		autoSearchCandidates = [];
	}

	async function importAutoSearchCandidate(candidate: CoverCandidate) {
		if (saving) return;
		saving = true;
		try {
			cover_url = await api.covers.importFromUrl(candidate.url);
			autoSearchOpen = false;
		} catch (e: unknown) {
			const message = e instanceof Error ? e.message : $_('book.autoSearchError');
			toasts.add(message, 'error');
		} finally {
			saving = false;
		}
	}
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
	<div class="fixed top-0 right-0 h-full w-full max-w-md bg-base-100 shadow-xl z-50 flex flex-col overflow-hidden">
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
		<form class="flex flex-col gap-3 px-4 pb-4 flex-1 min-h-0 overflow-y-auto" onsubmit={(e) => { e.preventDefault(); save(); }}>
			<label class="form-control">
				<span class="label label-text">{$_('book.title')}</span>
				<input class="input input-bordered input-sm" name="title" bind:value={title} required />
			</label>
			<label class="form-control">
				<span class="label label-text">{$_('book.subtitle')}</span>
				<input class="input input-bordered input-sm" name="subtitle" bind:value={subtitle} />
			</label>

			<SuggestionInput
				bind:value={author}
				name="author"
				label={$_('book.author') + ' *'}
				placeholder={$_('book.author')}
				fetchSuggestions={(q) => api.books.suggestions.authors(q)}
			/>

			<label class="form-control">
				<span class="label label-text">{$_('book.isbn')}</span>
				<div class="flex gap-2">
					<input class="input input-bordered input-sm flex-1" name="isbn" bind:value={isbn} />
					<button
						type="button"
						class="btn btn-outline btn-sm"
						onclick={() => (scannerOpen = true)}
						title={$_('import.scanIsbn')}
						aria-label={$_('import.scanIsbn')}
					>
						<svg viewBox="0 0 24 24" class="w-4 h-4" aria-hidden="true">
							<rect x="2" y="4" width="1" height="16" fill="currentColor" />
							<rect x="4" y="4" width="2" height="16" fill="currentColor" />
							<rect x="7" y="4" width="1" height="16" fill="currentColor" />
							<rect x="9" y="4" width="3" height="16" fill="currentColor" />
							<rect x="13" y="4" width="1" height="16" fill="currentColor" />
							<rect x="15" y="4" width="2" height="16" fill="currentColor" />
							<rect x="18" y="4" width="1" height="16" fill="currentColor" />
							<rect x="20" y="4" width="2" height="16" fill="currentColor" />
						</svg>
					</button>
				</div>
			</label>

			<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
				<SuggestionInput
					bind:value={publisher}
					name="publisher"
					label={$_('book.publisher')}
					placeholder={$_('book.publisher')}
					fetchSuggestions={(q) => api.books.suggestions.publishers(q)}
				/>

				<label class="form-control">
					<span class="label label-text">{$_('book.year')}</span>
					<input type="number" class="input input-bordered input-sm" name="published_year" bind:value={published_year} min="1000" max="2100" />
				</label>

				<label class="form-control">
					<span class="label label-text">{$_('book.pages')} <span class="text-error">*</span></span>
					<input type="number" class="input input-bordered input-sm" name="page_count" bind:value={page_count} min="1" required />
				</label>

				<label class="form-control">
					<span class="label label-text">{$_('book.language')}</span>
					<input
						type="text"
						class="input input-bordered input-sm"
						name="language"
						bind:value={language}
						maxlength="2"
						placeholder="EN, DE, FR..."
					/>
				</label>
			</div>

			<TagInput bind:value={tags} name="tags" disabled={saving} fetchSuggestions={(q) => api.books.suggestions.tags(q)} />

			<label class="form-control">
				<span class="label label-text">{$_('book.status')}</span>
				<select class="select select-bordered select-sm" name="status" bind:value={reading_status}>
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
				<input type="date" class="input input-bordered input-sm" name="date_started" bind:value={date_started} max={today} />
			</label>

			<label class="form-control">
				<span class="label label-text">{$_('book.dateFinished')}</span>
				<input type="date" class="input input-bordered input-sm" name="date_finished" bind:value={date_finished} max={today} />
			</label>

			<label class="form-control">
				<span class="label label-text">{$_('book.notes')}</span>
				<textarea class="textarea textarea-bordered text-sm" name="notes" rows="4" bind:value={notes}></textarea>
			</label>
			<label class="form-control">
				<span class="label label-text">{$_('book.blurb')}</span>
				<textarea class="textarea textarea-bordered text-sm" name="blurb" rows="4" bind:value={blurb}></textarea>
			</label>

			<CoverPicker bind:value={cover_url} disabled={saving} />
			<div class="-mt-1">
				<div class="flex flex-wrap gap-2">
					<a href={coverSearchUrl} target="_blank" rel="noreferrer" class="btn btn-outline btn-xs">
						{$_('book.googleCovers')}
					</a>
					<button
						type="button"
						class="btn btn-outline btn-xs"
						disabled={!isIsbnFilled || saving}
						onclick={openAutoSearchModal}
					>
						{$_('book.autoSearchCovers')}
					</button>
				</div>
			</div>

			<AutoSearchCoverModal
				bind:open={autoSearchOpen}
				loading={autoSearchLoading}
				candidates={autoSearchCandidates}
				error={autoSearchError}
				onCancel={closeAutoSearchModal}
				onSelect={importAutoSearchCandidate}
			/>

			<div class="sticky bottom-0 bg-base-100 py-3 border-t border-base-200 flex gap-2">
				<button type="button" class="btn btn-ghost btn-sm" onclick={() => (open = false)} disabled={saving}>
					{$_('common.cancel')}
				</button>
				<button type="submit" class="btn btn-primary btn-sm flex-1" disabled={saving}>
					{saving ? $_('common.saving') : $_('common.save')}
				</button>
			</div>
		</form>
	</div>

	<DateConflictDialog
		open={dateConflictOpen}
		field={conflictField}
		existingDate={formatDate(conflictExistingDate, tz)}
		suggestedDate={formatDate(conflictSuggestedDate, tz)}
		onCancel={() => {
			dateConflictOpen = false;
			pendingStatus = null;
			pendingPayload = null;
		}}
		onKeep={() => {
			dateConflictOpen = false;
			void applyPendingTransition(
				conflictField === 'started_after_finished'
					? { skipAutoDateStarted: true, clearDateStarted: true }
					: {
							forceDateStarted: conflictField === 'date_started' ? conflictExistingDate : undefined,
							forceDateFinished: conflictField === 'date_finished' ? conflictExistingDate : undefined
						}
			);
		}}
		onUseSuggested={() => {
			dateConflictOpen = false;
			void applyPendingTransition(
				conflictField === 'started_after_finished'
					? { forceDateStarted: conflictSuggestedDate, skipAutoDateStarted: true }
					: {
							forceDateStarted: conflictField === 'date_started' ? conflictSuggestedDate : undefined,
							forceDateFinished: conflictField === 'date_finished' ? conflictSuggestedDate : undefined
						}
			);
		}}
	/>

	{#if pendingProgressBook}
		{@const pbook = pendingProgressBook}
		<div class="modal modal-open">
			<div class="modal-box max-w-sm">
				<h3 class="text-lg font-bold">{$_('book.progressPromptTitle')}</h3>
				<p class="text-sm text-base-content/70 mt-2">
					{$_('book.progressPromptMessage', { values: { title: pbook.title } })}
				</p>
				<div class="modal-action">
					<button
						type="button"
						class="btn btn-ghost btn-sm"
						onclick={() => {
							onSave?.(pbook);
							open = false;
							pendingProgressBook = null;
						}}
					>
						{$_('book.progressPromptSkip')}
					</button>
					<button
						type="button"
						class="btn btn-primary btn-sm"
						onclick={async () => {
							try {
								await api.books.progress.create(pbook.id, pbook.page_count!);
							} catch {
								// silent — convenience feature
							}
							onSave?.(pbook);
							open = false;
							pendingProgressBook = null;
						}}
					>
						{$_('book.progressPromptSet')}
					</button>
				</div>
			</div>
			<button
				type="button"
				class="modal-backdrop"
				aria-label={$_('common.close')}
				onclick={() => {
					onSave?.(pbook);
					open = false;
					pendingProgressBook = null;
				}}
			></button>
		</div>
	{/if}

	<BarcodeScanner
		bind:open={scannerOpen}
		onDetected={(detected) => {
			isbn = detected;
			scannerOpen = false;
		}}
	/>
{/if}
