<script lang="ts">
	import { _ } from '$lib/i18n';
	import { api } from '$lib/api';
	import { toasts } from '$lib/toasts';
	import type { DataExportDataset, DataExportFormat } from '$lib/types';

	let selected = $state<DataExportDataset[]>(['books']);
	let format = $state<DataExportFormat>('json');
	let exporting = $state(false);

	const datasets: Array<{ value: DataExportDataset; label: string }> = [
		{ value: 'books', label: 'data.export.datasets.books' },
		{ value: 'progress', label: 'data.export.datasets.progress' },
		{ value: 'tags', label: 'data.export.datasets.tags' },
		{ value: 'covers', label: 'data.export.datasets.covers' }
	];

	function toggle(dataset: DataExportDataset) {
		if (selected.includes(dataset)) {
			selected = selected.filter((item) => item !== dataset);
		} else {
			selected = [...selected, dataset];
		}
	}

	function timestampedFilename() {
		const stamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
		return `librislog-export-${stamp}.zip`;
	}

	async function runExport() {
		if (selected.length === 0) {
			toasts.add($_('data.export.errors.noDatasets'), 'error');
			return;
		}
		exporting = true;
		try {
			const blob = await api.data.exportData({ datasets: selected, format });
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = timestampedFilename();
			document.body.appendChild(link);
			link.click();
			link.remove();
			URL.revokeObjectURL(url);
			toasts.add($_('data.export.success'), 'success');
		} catch (err: unknown) {
			toasts.add(err instanceof Error ? err.message : $_('data.export.errors.failed'), 'error');
		} finally {
			exporting = false;
		}
	}
</script>

<div class="card bg-base-100 border border-base-200 shadow-sm">
	<div class="card-body gap-4">
		<h2 class="card-title">{$_('data.export.title')}</h2>
		<p class="text-sm text-base-content/70">{$_('data.export.description')}</p>

		<div class="grid gap-2">
			{#each datasets as option}
				<label class="label cursor-pointer justify-start gap-3 border border-base-200 rounded-lg px-3 py-2">
					<input
						type="checkbox"
						class="checkbox checkbox-sm"
						checked={selected.includes(option.value)}
						onchange={() => toggle(option.value)}
					/>
					<span class="label-text">{$_(option.label)}</span>
				</label>
			{/each}
		</div>

		<div class="flex flex-wrap gap-3">
			<label class="label cursor-pointer gap-2">
				<input type="radio" class="radio radio-sm" bind:group={format} value="json" />
				<span class="label-text">JSON</span>
			</label>
			<label class="label cursor-pointer gap-2">
				<input type="radio" class="radio radio-sm" bind:group={format} value="csv" />
				<span class="label-text">CSV</span>
			</label>
		</div>

		{#if exporting}
			<progress class="progress progress-primary w-full"></progress>
		{/if}

		<div>
			<button class="btn btn-primary btn-sm" onclick={runExport} disabled={exporting || selected.length === 0}>
				{exporting ? $_('data.export.exporting') : $_('data.export.button')}
			</button>
		</div>
	</div>
</div>
