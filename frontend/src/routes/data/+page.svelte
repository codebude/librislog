<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { _ } from '$lib/i18n';
	import DataExport from '$lib/components/DataExport.svelte';
	import DataImport from '$lib/components/DataImport.svelte';

	const activeTab = $derived(($page.url.searchParams.get('tab') === 'import' ? 'import' : 'export') as 'import' | 'export');

	async function setTab(tab: 'import' | 'export') {
		const url = new URL(window.location.href);
		url.searchParams.set('tab', tab);
		await goto(`${url.pathname}?${url.searchParams.toString()}`, {
			replaceState: true,
			noScroll: true,
			keepFocus: true
		});
	}
</script>

<div class="flex flex-col gap-4 max-w-5xl mx-auto">
	<div class="hero rounded-2xl bg-base-100 shadow-sm border border-base-200">
		<div class="hero-content text-center py-8">
			<div>
				<h1 class="text-3xl font-bold">{$_('data.title')}</h1>
				<p class="text-base-content/70">{$_('data.subtitle')}</p>
			</div>
		</div>
	</div>

	<div role="tablist" class="tabs tabs-boxed w-fit">
		<button role="tab" class={`tab ${activeTab === 'export' ? 'tab-active' : ''}`} onclick={() => setTab('export')}>
			{$_('data.tabs.export')}
		</button>
		<button role="tab" class={`tab ${activeTab === 'import' ? 'tab-active' : ''}`} onclick={() => setTab('import')}>
			{$_('data.tabs.import')}
		</button>
	</div>

	{#if activeTab === 'export'}
		<DataExport />
	{:else}
		<DataImport />
	{/if}
</div>
