<script lang="ts">
	import type { Book, ReadingStatus } from '$lib/types';
	import { api } from '$lib/api';
	import { toasts } from '$lib/toasts';
	import ImportSearch from './ImportSearch.svelte';
	import BarcodeScanner from './BarcodeScanner.svelte';
	import CoverPicker from './CoverPicker.svelte';

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
	let author = $state('');
	let isbn = $state('');
	let publisher = $state('');
	let published_year = $state('');
	let page_count = $state('');
	let genre = $state('');
	let notes = $state('');
	let rating = $state('');
	let status = $state<ReadingStatus>('want_to_read');
	let cover_url = $state<string | null>(null);
	$effect(() => { status = defaultStatus; });

	function reset() {
		title = '';
		author = '';
		isbn = '';
		publisher = '';
		published_year = '';
		page_count = '';
		genre = '';
		notes = '';
		rating = '';
		status = defaultStatus;
		cover_url = null;
		activeTab = 'manual';
	}

	async function submitManual() {
		if (!title.trim()) return;
		submitting = true;
		try {
			const book = await api.books.create({
				title: title.trim(),
				author: author || null,
				isbn: isbn || null,
				publisher: publisher || null,
				published_year: published_year ? parseInt(published_year) : null,
				page_count: page_count ? parseInt(page_count) : null,
				genre: genre || null,
				notes: notes || null,
				rating: rating ? parseInt(rating) : null,
				reading_status: status,
				cover_url: cover_url || null
			});
			onAdded?.(book);
			open = false;
			reset();
		} catch (e: unknown) {
			toasts.add(e instanceof Error ? e.message : 'Failed to add book', 'error');
		} finally {
			submitting = false;
		}
	}

	const STATUS_OPTIONS: { value: ReadingStatus; label: string }[] = [
		{ value: 'want_to_read', label: 'Want to Read' },
		{ value: 'currently_reading', label: 'Currently Reading' },
		{ value: 'read', label: 'Read' },
		{ value: 'did_not_finish', label: 'Did Not Finish' }
	];
</script>

{#if open}
	<div class="modal modal-open">
		<div class="modal-box w-full max-w-lg">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-bold">Add Book</h3>
				<button class="btn btn-ghost btn-sm btn-circle" onclick={() => { open = false; }}>✕</button>
			</div>

			<!-- Tabs -->
			<div role="tablist" class="tabs tabs-boxed mb-4">
				<button
					role="tab"
					class="tab {activeTab === 'manual' ? 'tab-active' : ''}"
					onclick={() => (activeTab = 'manual')}
				>Manual</button>
				<button
					role="tab"
					class="tab {activeTab === 'import' ? 'tab-active' : ''}"
					onclick={() => (activeTab = 'import')}
				>Search & Import</button>
			</div>

			{#if activeTab === 'manual'}
				<form onsubmit={(e) => { e.preventDefault(); submitManual(); }} class="flex flex-col gap-2">
					<label class="form-control">
						<span class="label label-text">Title <span class="text-error">*</span></span>
						<input class="input input-bordered input-sm" bind:value={title} required />
					</label>
					<div class="grid grid-cols-2 gap-2">
						<label class="form-control">
							<span class="label label-text">Author</span>
							<input class="input input-bordered input-sm" bind:value={author} />
						</label>
						<label class="form-control">
							<span class="label label-text">ISBN</span>
							<input class="input input-bordered input-sm" bind:value={isbn} />
						</label>
						<label class="form-control">
							<span class="label label-text">Publisher</span>
							<input class="input input-bordered input-sm" bind:value={publisher} />
						</label>
						<label class="form-control">
							<span class="label label-text">Year</span>
							<input type="number" class="input input-bordered input-sm" bind:value={published_year} min="1000" max="2100" />
						</label>
						<label class="form-control">
							<span class="label label-text">Pages</span>
							<input type="number" class="input input-bordered input-sm" bind:value={page_count} min="1" />
						</label>
						<label class="form-control">
							<span class="label label-text">Rating (1–5)</span>
							<input type="number" class="input input-bordered input-sm" bind:value={rating} min="1" max="5" />
						</label>
					</div>
					<label class="form-control">
						<span class="label label-text">Genre</span>
						<input class="input input-bordered input-sm" bind:value={genre} />
					</label>
					<label class="form-control">
						<span class="label label-text">Status</span>
						<select class="select select-bordered select-sm" bind:value={status}>
							{#each STATUS_OPTIONS as opt}
								<option value={opt.value}>{opt.label}</option>
							{/each}
				</select>
				</label>
				<label class="form-control">
					<span class="label label-text">Notes</span>
					<textarea class="textarea textarea-bordered text-sm" rows="2" bind:value={notes}></textarea>
				</label>

				<CoverPicker bind:value={cover_url} disabled={submitting} />

				<div class="modal-action mt-2">
					<button type="button" class="btn btn-ghost btn-sm" onclick={reset}>
						Clear Form
					</button>
					<button type="submit" class="btn btn-primary btn-sm" disabled={submitting}>
						{submitting ? 'Adding…' : 'Add Book'}
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
		{/if}
		</div>
		<BarcodeScanner
			bind:open={scannerOpen}
			onDetected={(isbn) => {
				scannedIsbn = isbn;
			}}
		/>
		<!-- Click-outside to close -->
		<div class="modal-backdrop" role="button" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (open = false)}></div>
	</div>
{/if}
