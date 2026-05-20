<script lang="ts">
	import type { CoverCandidate } from '$lib/types';
	import { _ } from '$lib/i18n';

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

	let imageResolutionMap = $state<Record<string, string>>({});

	function close() {
		onCancel?.();
	}

	function filesizeLabel(bytes: number | null): string {
		if (!bytes || bytes <= 0) return 'n/a';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function resolutionLabel(candidate: CoverCandidate): string {
		const key = `${candidate.source}:${candidate.url}`;
		const fromImage = imageResolutionMap[key];
		if (fromImage) return fromImage;
		if (!candidate.width || !candidate.height) return 'n/a';
		return `${candidate.width}x${candidate.height}`;
	}

	function handleImageLoad(candidate: CoverCandidate, event: Event) {
		const target = event.currentTarget as HTMLImageElement;
		if (!target?.naturalWidth || !target?.naturalHeight) return;
		imageResolutionMap = {
			...imageResolutionMap,
			[`${candidate.source}:${candidate.url}`]: `${target.naturalWidth}x${target.naturalHeight}`
		};
	}
</script>

{#if open}
	<div class="modal modal-open">
		<div class="modal-box max-w-3xl">
			<div class="flex items-center justify-between mb-3">
				<h3 class="font-bold text-lg">{$_('book.autoSearchCovers')}</h3>
				<button type="button" class="btn btn-ghost btn-xs btn-circle" onclick={close} aria-label={$_('common.close')}>✕</button>
			</div>

			{#if loading}
				<div class="flex items-center gap-3 py-8">
					<span class="loading loading-spinner loading-md"></span>
					<span>{$_('book.autoSearchLoading')}</span>
				</div>
			{:else}
				{#if error}
					<div class="alert alert-error mb-3">{error}</div>
				{/if}

				<p class="text-sm text-base-content/70 mb-3">{$_('book.autoSearchInfo')}</p>

				{#if candidates.length === 0}
					<div class="text-sm text-base-content/60 py-4">{$_('book.autoSearchNoCandidates')}</div>
				{:else}
					<div class="grid grid-cols-2 md:grid-cols-3 gap-3">
						{#each candidates.filter((candidate) => candidate.available) as candidate (candidate.source + candidate.url)}
							<button
								type="button"
								class="relative group rounded-lg overflow-hidden border border-base-300 hover:border-primary"
								onclick={() => onSelect?.(candidate)}
							>
							<img
								src={candidate.url}
								alt={`Cover ${candidate.source}`}
								class="w-full aspect-[2/3] object-cover bg-base-200"
								loading="lazy"
								onload={(event) => handleImageLoad(candidate, event)}
							/>
								<div class="absolute inset-x-0 bottom-0 bg-black/70 text-white text-xs px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity">
									<div class="font-semibold">
										{$_('book.autoSearchSourceLabel', { values: { source: candidate.source } })}
									</div>
									<div>{$_('book.autoSearchMeta', {
										values: {
											size: filesizeLabel(candidate.filesize),
											resolution: resolutionLabel(candidate)
										}
									})}</div>
								</div>
							</button>
						{/each}
					</div>
				{/if}
			{/if}

			<div class="modal-action">
				<button type="button" class="btn btn-ghost" onclick={close}>{$_('common.cancel')}</button>
			</div>
		</div>
		<button type="button" class="modal-backdrop" aria-label={$_('common.close')} onclick={close}></button>
	</div>
{/if}
