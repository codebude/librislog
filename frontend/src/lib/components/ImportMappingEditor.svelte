<script lang="ts">
	let {
		sourceFields,
		dbFields,
		mapping,
		onChange
	}: {
		sourceFields: string[];
		dbFields: string[];
		mapping: Record<string, string>;
		onChange: (mapping: Record<string, string>) => void;
	} = $props();

	function update(source: string, target: string) {
		const next = { ...mapping };
		if (!target) {
			delete next[source];
		} else {
			next[source] = target;
		}
		onChange(next);
	}
</script>

<div class="grid gap-2">
	{#each sourceFields as source}
		<div class="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-2 items-center border border-base-200 rounded-lg p-2">
			<div class="font-medium text-sm break-all">{source}</div>
			<div class="text-base-content/50 text-center">-&gt;</div>
			<select
				class="select select-bordered select-sm"
				name={`mapping-${source}`}
				value={mapping[source] ?? ''}
				onchange={(e) => update(source, e.currentTarget.value)}
			>
				<option value="">(skip)</option>
				{#each dbFields as dbField}
					<option value={dbField}>{dbField}</option>
				{/each}
			</select>
		</div>
	{/each}
</div>
