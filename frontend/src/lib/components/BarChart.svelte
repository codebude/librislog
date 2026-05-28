<script lang="ts">
	import '$lib/chartjs/register';
	import { Bar } from 'svelte-chartjs';
	import { getDaisyColorRgb } from '$lib/chartjs/theme';
	import { themeApplyCount } from '$lib/stores/theme';
	import { onMount } from 'svelte';
	import type { Chart as ChartJS, ChartData, ChartOptions } from 'chart.js';

	let {
		labels = [],
		data = [],
		label = '',
		color = 'primary',
		emptyText = 'No data',
		height = 200,
		onChart = (_chart: ChartJS<'bar'>) => {},
	}: {
		labels: string[];
		data: number[];
		label: string;
		color: string;
		emptyText?: string;
		height?: number;
		onChart?: (chart: ChartJS<'bar'>) => void;
	} = $props();

	/**
	 * Custom pinch-zoom sensitivity. 0 = no pinch zoom, 1 = full native
	 * sensitivity. 0.25–0.4 is a comfortable range for mobile.
	 */
	const PINCH_SENSITIVITY = 0.35;

	let chart = $state<ChartJS<'bar'> | null>(null);
	let _themeSignal = $state(0);
	let chartContainer = $state<HTMLDivElement | null>(null);

	/** Native pinch tracking (plugin pinch is disabled). */
	let pinchState = $state<{
		initialDistance: number;
		initialRange: number;
		initialCenter: number;
		focalIndex: number;
	} | null>(null);

	$effect(() => {
		if (chart) {
			onChart(chart);
		}
	});

	onMount(() => {
		const unsub = themeApplyCount.subscribe((n: number) => {
			_themeSignal = n;
		});

		const container = chartContainer;
		if (!container) return unsub;

		const canvas = container.querySelector('canvas');
		if (!canvas) return unsub;

		const getDistance = (touches: TouchList) => {
			const dx = touches[0].clientX - touches[1].clientX;
			const dy = touches[0].clientY - touches[1].clientY;
			return Math.hypot(dx, dy);
		};

		const getFocalIndex = (touches: TouchList, chartWidth: number, left: number) => {
			const midX = (touches[0].clientX + touches[1].clientX) / 2 - left;
			return midX / chartWidth;
		};

		const onTouchStart = (e: TouchEvent) => {
			if (e.touches.length !== 2 || !chart) return;
			const scale = chart.scales.x;
			if (!scale) return;

			const rect = canvas.getBoundingClientRect();
			pinchState = {
				initialDistance: getDistance(e.touches),
				initialRange: scale.max - scale.min,
				initialCenter: (scale.min + scale.max) / 2,
				focalIndex: getFocalIndex(e.touches, rect.width, rect.left),
			};
		};

		const onTouchMove = (e: TouchEvent) => {
			if (e.touches.length !== 2 || !pinchState || !chart) return;
			e.preventDefault();

			const currentDistance = getDistance(e.touches);
			if (currentDistance === 0) return;

			const rawRatio = currentDistance / pinchState.initialDistance;
			// Apply dampening: small finger movements create smaller zoom changes
			const dampenedRatio = 1 + (rawRatio - 1) * PINCH_SENSITIVITY;

			const newRange = pinchState.initialRange / dampenedRatio;
			const focalOffset = (pinchState.focalIndex - 0.5) * newRange;
			const newMin = pinchState.initialCenter - newRange / 2 - focalOffset;
			const newMax = newMin + newRange;

			chart.zoomScale('x', { min: newMin, max: newMax }, 'none');
		};

		const onTouchEnd = () => {
			pinchState = null;
		};

		canvas.addEventListener('touchstart', onTouchStart, { passive: true });
		canvas.addEventListener('touchmove', onTouchMove, { passive: false });
		canvas.addEventListener('touchend', onTouchEnd, { passive: true });
		canvas.addEventListener('touchcancel', onTouchEnd, { passive: true });

		return () => {
			unsub();
			canvas.removeEventListener('touchstart', onTouchStart);
			canvas.removeEventListener('touchmove', onTouchMove);
			canvas.removeEventListener('touchend', onTouchEnd);
			canvas.removeEventListener('touchcancel', onTouchEnd);
		};
	});

	const chartData = $derived.by<ChartData<'bar'>>(() => {
		void _themeSignal;
		return {
			labels,
			datasets: [
				{
					label,
					data,
					backgroundColor: getDaisyColorRgb(color),
					borderColor: 'transparent',
					borderWidth: 0,
					borderRadius: 4,
					barPercentage: 0.7,
				},
			],
		};
	});

	const options = $derived.by<ChartOptions<'bar'>>(() => {
		void _themeSignal;
		return {
			responsive: true,
			maintainAspectRatio: false,
			animation: { duration: 0 },
			plugins: {
				legend: { display: false },
				tooltip: {
					enabled: true,
					mode: 'index' as const,
					intersect: false,
				},
				zoom: {
					pan: {
						enabled: true,
						mode: 'x' as const,
					},
					zoom: {
						wheel: { enabled: true },
						pinch: { enabled: false }, // handled manually above
						mode: 'x' as const,
					},
				},
			},
			scales: {
				x: {
					grid: { display: false },
					ticks: {
						maxRotation: 45,
						minRotation: 45,
						autoSkip: true,
						color: getDaisyColorRgb('base-content'),
					},
				},
				y: {
					beginAtZero: true,
					grid: {
						color: getDaisyColorRgb('base-200'),
					},
					ticks: {
						color: getDaisyColorRgb('base-content'),
					},
				},
			},
		};
	});

</script>

{#if data.length === 0}
	<div class="flex items-center justify-center h-40 text-base-content/50">
		<p>{emptyText}</p>
	</div>
{:else}
	<div bind:this={chartContainer} role="img" aria-label={label} class="relative select-none" style="height: {height}px">
		<Bar bind:chart={chart} data={chartData} {options} />
	</div>
{/if}
