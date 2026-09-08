	<script lang="ts">
	import type { CoverCandidate } from '$lib/types';
	import { _ } from '$lib/i18n';
	import { X } from '@lucide/svelte';
	import CoverCandidateGrid from './CoverCandidateGrid.svelte';

	let {
		open = $bindable(false),
		loading = false,
		candidates = [],
		error = null,
		onCancel,
		onSelect
	}: {
		open?: boolean;
		loading?: boolean;
		candidates?: CoverCandidate[];
		error?: string | null;
		onCancel?: () => void;
		onSelect?: (candidate: CoverCandidate) => void;
	} = $props();

	function close() {
		onCancel?.();
	}

	// Close on Escape right away — the modal-backdrop only receives key events
	// after it has been clicked, so listen at the window level instead.
	$effect(() => {
		if (!open) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') close();
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});
</script>

{#if open}
	<div class="modal modal-open">
		<div class="modal-box max-w-3xl">
			<div class="flex items-center justify-between mb-3">
				<h3 class="font-bold text-lg">{$_('book.autoSearchCovers')}</h3>
				<button type="button" class="btn btn-ghost btn-xs btn-circle" onclick={close} aria-label={$_('common.close')}><X class="w-3 h-3" /></button>
			</div>

			{#if loading}
				<div class="flex items-center gap-3 py-8">
					<span class="loading loading-spinner loading-md"></span>
					<span>{$_('book.autoSearchLoading')}</span>
				</div>
			{:else}
				<p class="text-sm text-base-content/70 mb-3">{$_('book.autoSearchInfo')}</p>

				<CoverCandidateGrid {candidates} {loading} {error} {onSelect} />
			{/if}

			<div class="modal-action">
				<button type="button" class="btn btn-ghost" onclick={close}>{$_('common.cancel')}</button>
			</div>
		</div>
		<div class="modal-backdrop"></div>
	</div>
{/if}
