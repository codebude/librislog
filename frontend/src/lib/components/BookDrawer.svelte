<script lang="ts">
	import type { Book, ReadingStatus } from '$lib/types';
	import { api } from '$lib/api';
	import { toasts } from '$lib/toasts';
	import StarRating from './StarRating.svelte';
	import CoverPicker from './CoverPicker.svelte';

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

	// Editable fields
	let title = $state('');
	let author = $state('');
	let notes = $state('');
	let rating = $state<number | null>(null);
	let reading_status = $state<ReadingStatus>('want_to_read');
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
			date_started = book.date_started ?? '';
			date_finished = book.date_finished ?? '';
			cover_url = book.cover_url ?? null;
			confirmDelete = false;
		}
	});

	async function save() {
		if (!book) return;
		saving = true;
		try {
		const updated = await api.books.update(book.id, {
			title,
			author: author || null,
			notes: notes || null,
			rating,
			reading_status,
			date_started: date_started || null,
			date_finished: date_finished || null,
			cover_url: cover_url || null
		});
			book = updated;
			onSave?.(updated);
			open = false;
		} catch (e: unknown) {
			toasts.add(e instanceof Error ? e.message : 'Save failed');
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
			toasts.add(e instanceof Error ? e.message : 'Delete failed');
		} finally {
			deleting = false;
		}
	}

	const STATUS_OPTIONS: { value: ReadingStatus; label: string }[] = [
		{ value: 'want_to_read', label: 'Want to Read' },
		{ value: 'currently_reading', label: 'Currently Reading' },
		{ value: 'read', label: 'Read' },
		{ value: 'did_not_finish', label: 'Did Not Finish' }
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
			<button class="btn btn-ghost btn-sm btn-circle" onclick={() => (open = false)}>✕</button>
		</div>

		<!-- Meta -->
		<div class="flex gap-4 p-4">
			<div class="text-sm text-base-content/60 space-y-1">
				{#if book.publisher}<p>{book.publisher}</p>{/if}
				{#if book.published_year}<p>{book.published_year}</p>{/if}
				{#if book.page_count}<p>{book.page_count} pages</p>{/if}
				{#if book.genre}<p class="italic">{book.genre}</p>{/if}
				{#if book.isbn}<p class="font-mono text-xs">ISBN {book.isbn}</p>{/if}
			</div>
		</div>

		<!-- Editable form -->
		<form class="flex flex-col gap-3 px-4 pb-4 flex-1" onsubmit={(e) => { e.preventDefault(); save(); }}>
			<label class="form-control">
				<span class="label label-text">Title</span>
				<input class="input input-bordered input-sm" bind:value={title} required />
			</label>

			<label class="form-control">
				<span class="label label-text">Author</span>
				<input class="input input-bordered input-sm" bind:value={author} />
			</label>

			<label class="form-control">
				<span class="label label-text">Status</span>
				<select class="select select-bordered select-sm" bind:value={reading_status}>
					{#each STATUS_OPTIONS as opt}
						<option value={opt.value}>{opt.label}</option>
					{/each}
				</select>
			</label>

			<div class="form-control">
				<span class="label label-text">Rating</span>
				<StarRating value={rating} onChange={(v) => (rating = v)} />
			</div>

			<label class="form-control">
				<span class="label label-text">Date started</span>
				<input type="date" class="input input-bordered input-sm" bind:value={date_started} />
			</label>

			<label class="form-control">
				<span class="label label-text">Date finished</span>
				<input type="date" class="input input-bordered input-sm" bind:value={date_finished} />
			</label>

		<label class="form-control">
			<span class="label label-text">Notes</span>
			<textarea class="textarea textarea-bordered text-sm" rows="4" bind:value={notes}></textarea>
		</label>

		<CoverPicker bind:value={cover_url} disabled={saving} />

		<div class="flex gap-2 mt-auto pt-2">
				<button type="submit" class="btn btn-primary btn-sm flex-1" disabled={saving}>
					{saving ? 'Saving…' : 'Save'}
				</button>
				{#if !confirmDelete}
					<button
						type="button"
						class="btn btn-error btn-outline btn-sm"
						onclick={() => (confirmDelete = true)}
					>Delete</button>
				{:else}
					<button
						type="button"
						class="btn btn-error btn-sm"
						disabled={deleting}
						onclick={deleteBook}
					>{deleting ? 'Deleting…' : 'Confirm?'}</button>
					<button
						type="button"
						class="btn btn-ghost btn-sm"
						onclick={() => (confirmDelete = false)}
					>Cancel</button>
				{/if}
			</div>
		</form>
	</div>
{/if}
