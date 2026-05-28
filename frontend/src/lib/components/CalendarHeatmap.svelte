<script lang="ts">
	import '$lib/chartjs/register';
	import { Chart } from 'svelte-chartjs';
	import { mixDaisyColors, getDaisyColorRgb } from '$lib/chartjs/theme';
	import { locale } from '$lib/i18n';
	import { themeApplyCount } from '$lib/stores/theme';
	import { onMount } from 'svelte';
	import type { DailyPages } from '$lib/types';
	import type { Chart as ChartJS, ChartData, ChartOptions, ScriptableContext, TooltipItem } from 'chart.js';

	let {
		data = [],
		emptyText = 'No reading data available for the past year'
	}: {
		data: DailyPages[];
		emptyText?: string;
	} = $props();

	const today = $derived(new Date());
	const startDate = $derived.by(() => {
		const d = new Date(today);
		d.setDate(today.getDate() - 364);
		return d;
	});

	function getWeekNumber(d: Date): number {
		const start = new Date(startDate);
		const diff = d.getTime() - start.getTime();
		return Math.floor(diff / (7 * 24 * 60 * 60 * 1000));
	}

	let chart = $state<ChartJS<'matrix'> | null>(null);
	let _themeSignal = $state(0);

	onMount(() => {
		return themeApplyCount.subscribe((n: number) => {
			_themeSignal = n;
		});
	});

	const matrixData = $derived.by(() => {
		const pagesByDate = new Map<string, number>();
		for (const d of data) {
			pagesByDate.set(d.date, d.pages);
		}

		const maxPages = Math.max(...data.map((d) => d.pages), 1);
		const result: { x: number; y: number; v: number; date: string }[] = [];
		const monthLabels: { week: number; label: string }[] = [];

		const current = new Date(startDate);
		let lastMonth = -1;
		let firstWeekSet = false;
		const appLocale = $locale ?? 'en';
		while (current <= today) {
			const dateStr = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`;
			const pages = pagesByDate.get(dateStr) ?? 0;
			const week = getWeekNumber(current);
			const day = current.getDay();
			result.push({ x: week, y: day, v: pages, date: dateStr });

			if (current.getMonth() !== lastMonth) {
				lastMonth = current.getMonth();
				if (week > 0 || !firstWeekSet) {
					if (week > 0) {
						monthLabels.push({ week, label: current.toLocaleDateString(appLocale, { month: 'short' }) });
					}
					firstWeekSet = true;
				}
			}

			current.setDate(current.getDate() + 1);
		}

		return { points: result, maxPages, monthLabels };
	});

	const chartData = $derived.by<ChartData<'matrix'>>(() => {
		void _themeSignal;
		return {
			datasets: [
				{
					label: 'Pages',
					data: matrixData.points,
					backgroundColor: (ctx: ScriptableContext<'matrix'>) => {
						const raw = ctx.raw as { v: number } | undefined;
						const v = raw?.v ?? 0;
						if (v <= 0) return mixDaisyColors('--color-base-200', '--color-primary', 0);
						return mixDaisyColors('--color-base-200', '--color-primary', Math.min(v / matrixData.maxPages, 1));
					},
					borderColor: 'transparent',
					borderWidth: 1,
					width: ({ chart }: { chart: { chartArea?: { width: number } } }) => {
						const area = chart.chartArea;
						if (!area) return 10;
						return Math.max((area.width / 54) - 2, 2);
					},
					height: ({ chart }: { chart: { chartArea?: { height: number } } }) => {
						const area = chart.chartArea;
						if (!area) return 10;
						return Math.max((area.height / 8) - 2, 2);
					},
				},
			],
		};
	});

	const monthLabelPlugin = {
		id: 'monthLabels',
		afterDraw(chart: ChartJS) {
			const ctx = chart.ctx;
			const chartArea = chart.chartArea;
			if (!chartArea) return;

			const labels = matrixData.monthLabels;
			if (labels.length === 0) return;

			const xScale = chart.scales.x;
			if (!xScale) return;

			ctx.save();
			ctx.font = '11px sans-serif';
			ctx.fillStyle = getDaisyColorRgb('base-content');
			ctx.globalAlpha = 0.5;

			for (const ml of labels) {
				const x = xScale.getPixelForValue(ml.week);
					ctx.save();
					ctx.translate(x, chartArea.top - 10);
					ctx.rotate(-Math.PI / 4);
					ctx.fillText(ml.label, 0, 0);
					ctx.restore();
			}

			ctx.restore();
		}
	};

	const options = $derived.by<ChartOptions<'matrix'>>(() => {
		void _themeSignal;
		return {
			responsive: true,
			maintainAspectRatio: false,
			animation: { duration: 0 },
			layout: {
				padding: {
					top: 28,
				}
			},
			plugins: {
				legend: { display: false },
				monthLabels: {},
				tooltip: {
					callbacks: {
						title: (items: TooltipItem<'matrix'>[]) => {
							const raw = items[0]?.raw as { date: string } | undefined;
							if (!raw) return '';
							const [yr, mo, dy] = raw.date.split('-').map(Number);
							const appLocale = $locale ?? 'en';
							return new Date(yr, mo - 1, dy).toLocaleDateString(appLocale, {
								weekday: 'short',
								month: 'short',
								day: 'numeric',
								year: 'numeric',
							});
						},
						label: (item: TooltipItem<'matrix'>) => {
							const raw = item.raw as { v: number } | undefined;
							return `Pages: ${raw?.v ?? 0}`;
						},
					},
				},
			},
			scales: {
				x: {
					type: 'linear',
					offset: true,
					grid: { display: false },
					ticks: { display: false },
					border: { display: false },
				},
				y: {
					type: 'linear',
					offset: true,
					min: -0.5,
					max: 6.5,
					reverse: true,
					grid: { display: false },
					ticks: { display: false },
					border: { display: false },
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
	<div role="img" aria-label="Reading activity heatmap" class="w-full select-none" style="height: 160px;">
		<Chart type="matrix" bind:chart={chart} data={chartData} {options} plugins={[monthLabelPlugin]} />
	</div>
{/if}
