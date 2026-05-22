<script lang="ts">
	import Alert from '$lib/components/Alert.svelte';
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

	const available = $derived(candidates.filter((c) => c.available));

	function resolutionKey(candidate: CoverCandidate): string {
		return `${candidate.source}:${candidate.url}`;
	}

	function resolutionScore(candidate: CoverCandidate): number {
		const detected = imageResolutionMap[resolutionKey(candidate)];
		if (detected) {
			const parts = detected.split('x');
			return parseInt(parts[0], 10) * parseInt(parts[1], 10);
		}
		if (candidate.width && candidate.height) return candidate.width * candidate.height;
		return 0;
	}

	const sorted = $derived.by(() => [...available].sort((a, b) => resolutionScore(b) - resolutionScore(a)));

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
		const detected = imageResolutionMap[resolutionKey(candidate)];
		if (detected) return detected;
		if (!candidate.width || !candidate.height) return 'n/a';
		return `${candidate.width}x${candidate.height}`;
	}

	function handleImageLoad(candidate: CoverCandidate, event: Event) {
		const target = event.currentTarget as HTMLImageElement;
		if (!target?.naturalWidth || !target?.naturalHeight) return;
		imageResolutionMap = {
			...imageResolutionMap,
			[resolutionKey(candidate)]: `${target.naturalWidth}x${target.naturalHeight}`
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
					<Alert type="error" onClose={onCancel}>
						{error}
					</Alert>
				{/if}

				<p class="text-sm text-base-content/70 mb-3">{$_('book.autoSearchInfo')}</p>

				{#if sorted.length === 0}
					<div class="text-sm text-base-content/60 py-4">{$_('book.autoSearchNoCandidates')}</div>
				{:else}
					<div class="grid grid-cols-2 md:grid-cols-3 gap-3">
						{#each sorted as candidate (resolutionKey(candidate))}
							<button
								type="button"
								class="card card-compact border border-base-300 hover:border-primary text-left"
								onclick={() => onSelect?.(candidate)}
							>
								<figure class="bg-base-200">
									<img
										src={candidate.url}
										alt={`Cover ${candidate.source}`}
										class="w-full aspect-[2/3] object-cover"
										loading="lazy"
										onload={(event) => handleImageLoad(candidate, event)}
									/>
								</figure>
								<div class="card-body gap-1 p-2 text-xs">
									<div class="font-semibold truncate">
										{$_('book.autoSearchSourceLabel', { values: { source: candidate.source } })}
									</div>
									<div class="text-base-content/60">
										{filesizeLabel(candidate.filesize)}
										{#if resolutionLabel(candidate) !== 'n/a'} · {resolutionLabel(candidate)}{/if}
									</div>
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
