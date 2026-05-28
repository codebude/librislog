	<script lang="ts">
	import type { Book, ReadingStatus } from '$lib/types';
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';
	import ImportSearch from './ImportSearch.svelte';
	import BarcodeScanner from './BarcodeScanner.svelte';
	import CoverPicker from './CoverPicker.svelte';
	import TagInput from './TagInput.svelte';
	import SuggestionInput from './SuggestionInput.svelte';
	import { ScanBarcode, X } from '@lucide/svelte';

	let {
		open = $bindable(false),
		defaultStatus = 'want_to_read' as ReadingStatus,
		onAdded
	}: {
		open?: boolean;
		defaultStatus?: ReadingStatus;
		onAdded?: (book: Book) => void;
	} = $props();

	let activeTab = $state<'manual' | 'import'>('manual');
	let submitting = $state(false);
	let scannerOpen = $state(false);
	let scannedIsbn = $state<string | null>(null);

	// Manual form state
	let title = $state('');
	let subtitle = $state('');
	let author = $state('');
	let isbn = $state('');
	let publisher = $state('');
	let published_year = $state('');
	let page_count = $state('');
	let language = $state('');
	let tags = $state('');
	let notes = $state('');
	let blurb = $state('');
	let rating = $state('');
	let status = $state<ReadingStatus>('want_to_read');
	let cover_url = $state<string | null>(null);
	$effect(() => { status = defaultStatus; });

	function reset() {
		title = '';
		subtitle = '';
		author = '';
		isbn = '';
		publisher = '';
		published_year = '';
		page_count = '';
		language = '';
		tags = '';
		notes = '';
		blurb = '';
		rating = '';
		status = defaultStatus;
		cover_url = null;
		activeTab = 'manual';
	}

	async function submitManual() {
		if (!title.trim()) return;
		if (!author.trim()) return;
		if (!page_count) return;
		submitting = true;
		try {
			const book = await api.books.create({
				title: title.trim(),
				subtitle: subtitle || null,
				author: author.trim(),
				isbn: isbn || null,
				publisher: publisher || null,
				published_year: published_year ? parseInt(published_year) : null,
				page_count: parseInt(page_count),
				language: language || null,
				tags: tags || null,
				notes: notes || null,
				blurb: blurb || null,
				rating: rating ? parseInt(rating) : null,
				reading_status: status,
				cover_url: cover_url || null
			});
			onAdded?.(book);
			open = false;
			reset();
		} catch (e: unknown) {
			const message =
				e instanceof Error && e.message === 'error.isbnAlreadyExists'
					? $_('error.isbnAlreadyExists')
					: e instanceof Error
						? e.message
						: $_('addModal.failedAdd');
			toasts.add(message, 'error');
		} finally {
			submitting = false;
		}
	}

	const STATUS_OPTIONS: { value: ReadingStatus; label: string }[] = [
		{ value: 'want_to_read', label: 'status.want_to_read' },
		{ value: 'currently_reading', label: 'status.currently_reading' },
		{ value: 'read', label: 'status.read' },
		{ value: 'did_not_finish', label: 'status.did_not_finish' }
	];
</script>

{#if open}
	<div class="modal modal-open">
		<div class="modal-box w-full max-w-3xl max-h-[90dvh] overflow-y-auto">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-bold">{$_('app.addBook')}</h3>
				<button class="btn btn-ghost btn-sm btn-circle" onclick={() => { open = false; }} aria-label={$_('common.close')}><X class="w-4 h-4" /></button>
			</div>

			<!-- Tabs -->
			<div role="tablist" class="tabs tabs-boxed mb-4">
				<button
					role="tab"
					class="tab {activeTab === 'manual' ? 'tab-active' : ''}"
					onclick={() => (activeTab = 'manual')}
				>{$_('addModal.manual')}</button>
				<button
					role="tab"
					class="tab {activeTab === 'import' ? 'tab-active' : ''}"
					onclick={() => (activeTab = 'import')}
				>{$_('addModal.searchImport')}</button>
			</div>

			{#if activeTab === 'manual'}
				<form onsubmit={(e) => { e.preventDefault(); submitManual(); }} class="flex flex-col gap-4">
					<label class="flex flex-col gap-1">
						<span class="label label-text">{$_('book.title')} <span class="text-error">*</span></span>
						<input class="input input-bordered" name="title" bind:value={title} required />
					</label>
					<label class="flex flex-col gap-1">
						<span class="label label-text">{$_('book.subtitle')}</span>
						<input class="input input-bordered" name="subtitle" bind:value={subtitle} />
					</label>
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
						<SuggestionInput
							bind:value={author}
							name="author"
							label={$_('book.author') + ' *'}
							placeholder={$_('book.author')}
							fetchSuggestions={(q) => api.books.suggestions.authors(q)}
						/>
						<label class="flex flex-col gap-1">
							<span class="label label-text">{$_('book.isbn')}</span>
							<div class="flex gap-2">
								<input class="input input-bordered flex-1" name="isbn" bind:value={isbn} />
								<button
									type="button"
									class="btn btn-outline"
									onclick={() => (scannerOpen = true)}
									title={$_('import.scanIsbn')}
									aria-label={$_('import.scanIsbn')}
								>
									<ScanBarcode class="w-4 h-4" />
								</button>
							</div>
						</label>
						<SuggestionInput
							bind:value={publisher}
							name="publisher"
							label={$_('book.publisher')}
							placeholder={$_('book.publisher')}
							fetchSuggestions={(q) => api.books.suggestions.publishers(q)}
						/>
						<label class="flex flex-col gap-1">
							<span class="label label-text">{$_('book.year')}</span>
							<input type="number" class="input input-bordered" name="published_year" bind:value={published_year} max="2100" />
						</label>
						<label class="flex flex-col gap-1">
							<span class="label label-text">{$_('book.pages')} <span class="text-error">*</span></span>
							<input type="number" class="input input-bordered" name="page_count" bind:value={page_count} min="1" required />
						</label>
						<label class="flex flex-col gap-1">
							<span class="label label-text">{$_('book.language')}</span>
							<input
								type="text"
								class="input input-bordered"
								name="language"
								bind:value={language}
								maxlength="2"
								placeholder="EN, DE, FR..."
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="label label-text">{$_('common.rating')} (1-5)</span>
							<input type="number" class="input input-bordered" name="rating" bind:value={rating} min="1" max="5" />
						</label>
					</div>
				<TagInput bind:value={tags} name="tags" disabled={submitting} fetchSuggestions={(q) => api.books.suggestions.tags(q)} />
				<label class="flex flex-col gap-1">
					<span class="label label-text">{$_('book.status')}</span>
					<select class="select select-bordered" name="status" bind:value={status}>
						{#each STATUS_OPTIONS as opt}
							<option value={opt.value}>{$_(opt.label)}</option>
						{/each}
				</select>
				</label>
				<label class="flex flex-col gap-1">
					<span class="label label-text">{$_('book.notes')}</span>
					<textarea class="textarea textarea-bordered" name="notes" rows="2" bind:value={notes}></textarea>
				</label>
				<label class="flex flex-col gap-1">
					<span class="label label-text">{$_('book.blurb')}</span>
					<textarea class="textarea textarea-bordered" name="blurb" rows="3" bind:value={blurb}></textarea>
				</label>

				<CoverPicker bind:value={cover_url} disabled={submitting} />

				<div class="modal-action mt-2">
					<button type="button" class="btn btn-ghost btn-sm" onclick={reset}>
						{$_('common.clearForm')}
					</button>
					<button type="submit" class="btn btn-primary btn-sm" disabled={submitting}>
						{submitting ? $_('addModal.adding') : $_('app.addBook')}
					</button>
				</div>
				</form>
			{:else}
			<ImportSearch
				onOpenScanner={() => {
					scannerOpen = true;
				}}
				scannedIsbn={scannedIsbn}
				onScannedHandled={() => {
					scannedIsbn = null;
				}}
				onImport={(book) => {
					onAdded?.(book);
					open = false;
					reset();
				}}
			/>
			<div class="mt-3 text-center">
				<a href="/data?tab=import" class="link link-primary text-sm">{$_('addModal.importFromFile')}</a>
			</div>
		{/if}
		</div>
	<BarcodeScanner
		bind:open={scannerOpen}
		onDetected={(detected) => {
			scannedIsbn = detected;
			isbn = detected;
		}}
	/>
		<!-- Click-outside to close -->
		<div class="modal-backdrop" role="button" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (open = false)}></div>
	</div>
{/if}
