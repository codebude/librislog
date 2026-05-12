<script lang="ts">
	import type { Book } from '$lib/types';
	import { _ } from '$lib/i18n';
	import { formatDate } from '$lib/date';
	import { api } from '$lib/api';
	import { toasts } from '$lib/toasts';
	import StarRating from './StarRating.svelte';

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

	let confirmDelete = $state(false);
	let deleting = $state(false);

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

	$effect(() => {
		if (book) {
			confirmDelete = false;
		}
	});

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
</script>

{#if open && book}
	<div
		class="fixed inset-0 bg-black/40 z-40"
		role="button"
		tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (open = false)}
	></div>

	<div class="fixed top-0 right-0 h-full w-full max-w-md bg-base-100 shadow-xl z-50 flex flex-col overflow-y-auto">
		<div class="flex items-center justify-between p-4 border-b border-base-200">
			<h2 class="text-lg font-bold truncate">{book.title}</h2>
			<button
				class="btn btn-ghost btn-sm btn-circle"
				onclick={() => (open = false)}
				aria-label={$_('common.close')}
			>✕</button>
		</div>

		<div class="p-4 flex-1 flex flex-col gap-4">
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

			<div>
				<div class="text-xs text-base-content/60 mb-1">{$_('common.rating')}</div>
				<StarRating value={book.rating} readonly />
			</div>

			<div class="grid grid-cols-2 gap-3 text-sm">
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

			<div class="text-sm">
				<div class="text-xs text-base-content/60">{$_('book.isbn')}</div>
				<div class="font-mono break-all">{book.isbn ?? '-'}</div>
			</div>

			<div class="grid grid-cols-2 gap-3 text-sm">
				<div>
					<div class="text-xs text-base-content/60">{$_('book.dateStarted')}</div>
					<div>{book.date_started ? formatDate(book.date_started) : '-'}</div>
				</div>
				<div>
					<div class="text-xs text-base-content/60">{$_('book.dateFinished')}</div>
					<div>{book.date_finished ? formatDate(book.date_finished) : '-'}</div>
				</div>
			</div>

			<div>
				<div class="text-xs text-base-content/60 mb-1">{$_('book.notes')}</div>
				<div class="text-sm whitespace-pre-wrap break-words rounded border border-base-200 p-2 min-h-12">
					{book.notes ?? '-'}
				</div>
			</div>
		</div>

		<div class="p-4 border-t border-base-200 flex gap-2">
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
{/if}
