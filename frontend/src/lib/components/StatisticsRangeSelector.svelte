<script lang="ts">
	import { _ } from '$lib/i18n';
	import AdaptiveDateInput from './AdaptiveDateInput.svelte';
	import type { StatisticsRange } from '$lib/types';

	let {
		range = $bindable<StatisticsRange>('alltime'),
		customFrom = $bindable(''),
		customTo = $bindable(''),
		invalid = $bindable(false),
		disabled = false,
		refreshing = false
	}: {
		range?: StatisticsRange;
		customFrom?: string;
		customTo?: string;
		invalid?: boolean;
		disabled?: boolean;
		refreshing?: boolean;
	} = $props();

	const options: Array<[StatisticsRange, string]> = [
		['alltime', 'statistics.rangeAllTime'],
		['3years', 'statistics.rangeLast3Years'],
		['1year', 'statistics.rangeLastYear'],
		['6months', 'statistics.rangeLast6Months'],
		['30days', 'statistics.rangeLast30Days'],
		['custom', 'statistics.rangeCustom']
	];

	$effect(() => {
		invalid = range === 'custom' && !!customFrom && !!customTo && customFrom > customTo;
	});
</script>

<div class="flex w-full flex-col gap-3 rounded-xl border border-base-300 bg-base-200/30 p-3 sm:flex-row sm:items-end sm:gap-4">
	<label class="form-control w-full sm:w-64 sm:shrink-0">
		<span class="label-text flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">
			{$_('statistics.rangeLabel')}
			{#if refreshing}
				<span class="loading loading-spinner loading-xs" aria-label={$_('statistics.refreshing')}></span>
			{/if}
		</span>
		<select class="select select-bordered select-sm" bind:value={range} {disabled}>
			{#each options as [value, label]}
				<option {value}>{$_(label)}</option>
			{/each}
		</select>
	</label>

	{#if range === 'custom'}
		<div class="grid grid-cols-1 gap-3 sm:flex-1 sm:grid-cols-2">
			<label class="form-control">
				<span class="label-text text-xs">{$_('statistics.from')}</span>
				<AdaptiveDateInput bind:value={customFrom} max={customTo || undefined} disabled={disabled} ariaLabel={$_('statistics.from')} />
			</label>
			<label class="form-control">
				<span class="label-text text-xs">{$_('statistics.to')}</span>
				<AdaptiveDateInput bind:value={customTo} min={customFrom || undefined} disabled={disabled} ariaLabel={$_('statistics.to')} />
			</label>
		</div>
		{#if invalid}
			<p class="text-error text-xs sm:col-span-2" role="alert">{$_('statistics.invalidDateRange')}</p>
		{/if}
	{/if}
</div>
