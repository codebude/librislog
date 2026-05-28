	<script lang="ts">
	import { ALERT_DURATION_MS } from '$lib/constants';
	import { X } from '@lucide/svelte';

	let {
		type = 'info',
		onClose,
		duration = ALERT_DURATION_MS,
		children
	}: {
		type?: string;
		onClose?: () => void;
		duration?: number;
		children?: import('svelte').Snippet;
	} = $props();

	$effect(() => {
		if (type !== 'success' || !onClose || !duration) return;
		const timer = setTimeout(onClose, duration);
		return () => clearTimeout(timer);
	});
</script>

<div role="alert" class="alert alert-{type} relative overflow-hidden flex items-start justify-between gap-2">
	{#if type === 'success' && onClose && duration}
		<div class="progress-bar" style="animation-duration: {duration}ms"></div>
	{/if}
	<span class="flex-1">{@render children?.()}</span>
	{#if onClose}
		<button type="button" class="btn btn-ghost btn-xs btn-square shrink-0" onclick={onClose} aria-label="Close">
			<X class="w-4 h-4" />
		</button>
	{/if}
</div>

<style>
	@keyframes shrink {
		from { transform: scaleX(1); }
		to { transform: scaleX(0); }
	}
	.progress-bar {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 6px;
		background: currentColor;
		opacity: 0.2;
		transform-origin: left center;
		animation: shrink linear forwards;
	}
</style>
