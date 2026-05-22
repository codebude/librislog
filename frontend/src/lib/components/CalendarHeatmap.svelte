<script lang="ts">
	import { Chart, Calendar, Svg, Tooltip } from 'layerchart';
	import CalendarCellRenderer from './CalendarCellRenderer.svelte';
	import type { DailyPages } from '$lib/types';

	let {
		data = [],
		emptyText = 'No reading data available for the past year'
	}: {
		data: DailyPages[];
		emptyText?: string;
	} = $props();

	let containerWidth = $state(0);

	const today = $derived(new Date());
	const startDate = $derived(new Date(today.getFullYear() - 1, today.getMonth(), today.getDate()));
	const maxPages = $derived(Math.max(...data.map((d) => d.pages), 0));
	const calendarCellWidth = $derived(Math.max((containerWidth - 40) / 54, 4));
	const calendarCellHeight = $derived(containerWidth >= 1400 ? 16 : containerWidth >= 1000 ? 15 : 14);

	function formatDateLabel(date: string): string {
		const [yr, mo, dy] = date.split('-').map(Number);
		return new Date(yr, mo - 1, dy).toLocaleDateString('en', {
			weekday: 'short',
			month: 'short',
			day: 'numeric',
			year: 'numeric'
		});
	}
</script>

{#if data.length === 0}
	<div class="flex items-center justify-center h-40 text-base-content/50">
		<p>{emptyText}</p>
	</div>
{:else}
  <div class="w-full select-none" bind:clientWidth={containerWidth}>
    <Chart
			data={data}
			x={(d: DailyPages) => {
				const [yr, mo, dy] = d.date.split('-').map(Number);
				return new Date(yr, mo - 1, dy);
			}}
			c={(d: DailyPages) => d.pages}
			cRange={['var(--color-base-200)', 'var(--color-primary)']}
			tooltipContext={true}
			height={140}
			padding={{ top: 24, right: 0, bottom: 0, left: 40 }}
		>
			<Svg>
				<Calendar
					start={startDate}
					end={today}
					cellSize={[calendarCellWidth, calendarCellHeight]}
					monthLabel={true}
					tooltip={false}
				>
					{#snippet children({ cells, cellSize })}
						<CalendarCellRenderer {cells} {cellSize} {maxPages} />
					{/snippet}
				</Calendar>
			</Svg>

			<Tooltip.Root anchor="top-left">
				{#snippet children({ data })}
					{#if data?.pages !== undefined}
						<Tooltip.Header value={formatDateLabel(data.date)} />
						<Tooltip.List>
							<Tooltip.Item label="Pages" value={data.pages} color="var(--color-primary)" format="integer" />
						</Tooltip.List>
					{/if}
				{/snippet}
			</Tooltip.Root>
		</Chart>
	</div>
{/if}
