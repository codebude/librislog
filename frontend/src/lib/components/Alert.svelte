<script lang="ts">
	import { ALERT_DURATION_MS } from '$lib/constants';

	let {
		type = 'info',
		onClose,
		children
	}: {
		type?: string;
		onClose?: () => void;
		children?: import('svelte').Snippet;
	} = $props();

	$effect(() => {
		if (type !== 'success' || !onClose) return;
		const timer = setTimeout(onClose, ALERT_DURATION_MS);
		return () => clearTimeout(timer);
	});
</script>

<div class="alert alert-{type} flex items-center justify-between gap-2">
	<span class="flex-1">{@render children?.()}</span>
	{#if onClose}
		<button type="button" class="btn btn-ghost btn-xs btn-square shrink-0" onclick={onClose} aria-label="Close">
			<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>
	{/if}
</div>
