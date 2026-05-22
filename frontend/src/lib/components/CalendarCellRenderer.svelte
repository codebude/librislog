<script lang="ts">
	import { Rect, getChartContext } from 'layerchart';
	import { onMount } from 'svelte';

	let {
		cells,
		cellSize,
		maxPages
	}: {
		cells: Array<{ x: number; y: number; data: { date: string; pages?: number } }>;
		cellSize: [number, number];
		maxPages: number;
	} = $props();

	const ctx = getChartContext();
	let tapShown = false;

	function getFill(pages?: number): string {
		if (pages === undefined || pages <= 0 || maxPages <= 0) return 'var(--color-base-200)';
		const t = Math.min(pages / maxPages, 1);
		return `color-mix(in oklab, var(--color-base-200) ${100 - t * 100}%, var(--color-primary) ${t * 100}%)`;
	}

	function docClick(e: MouseEvent) {
		const target = e.target as Element | null;
		if (target && target.closest('g[role="gridcell"]')) return;
		tapShown = false;
		ctx.tooltip.hide();
	}

	onMount(() => {
		document.addEventListener('click', docClick);
		return () => document.removeEventListener('click', docClick);
	});
</script>

{#each cells as cell}
	<Rect
		x={cell.x}
		y={cell.y}
		width={cellSize[0]}
		height={cellSize[1]}
		fill={getFill(cell.data?.pages)}
		rx="2"
		role="gridcell"
		onpointermove={(e) => {
			tapShown = false;
			if (cell.data?.pages !== undefined) ctx.tooltip.show(e, cell.data);
		}}
		onpointerleave={() => {
			if (!tapShown) ctx.tooltip.hide();
		}}
		onclick={(e) => {
			if (cell.data?.pages !== undefined) {
				tapShown = true;
				ctx.tooltip.show(e, cell.data);
			}
		}}
	/>
{/each}
