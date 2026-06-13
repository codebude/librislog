<script lang="ts">
	import { base } from '$app/paths';
	import { _ } from '$lib/i18n';

	type DocsView = 'swagger' | 'redoc';
	let docsView = $state<DocsView>('swagger');
	let docsLoading = $state(true);

	const docsUrl = $derived(docsView === 'swagger' ? `${base}/api/docs` : `${base}/api/redoc`);

	function onDocsViewChange(event: Event) {
		docsView = (event.currentTarget as HTMLSelectElement).value as DocsView;
		docsLoading = true;
	}
</script>

<div class="max-w-5xl mx-auto flex flex-col gap-6">
	<div>
		<h1 class="text-2xl font-bold">{$_('settings.apiDocsTitle')}</h1>
		<p class="text-sm text-base-content/70 mt-1">{$_('settings.apiDocsHelp')}</p>
	</div>

	<div class="card bg-base-100 shadow-sm border border-base-200">
		<div class="card-body gap-3">
			<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
				<div>
					<h2 class="text-lg font-semibold">{$_('settings.apiDocsTitle')}</h2>
					<p class="text-xs text-base-content/60 mt-1">{$_('settings.apiDocsHelp')}</p>
				</div>
				<div class="flex items-center gap-2">
					<span class="text-xs text-base-content/60">{$_('settings.apiDocsViewLabel')}</span>
					<select class="select select-bordered select-sm" value={docsView} onchange={onDocsViewChange}>
						<option value="swagger">Swagger UI</option>
						<option value="redoc">ReDoc</option>
					</select>
				</div>
			</div>

			<div class="relative rounded-lg border border-base-200 overflow-hidden bg-base-200 min-h-[28rem]">
				{#if docsLoading}
					<div class="absolute inset-0 z-10 grid place-items-center bg-base-200/80">
						<span class="loading loading-spinner loading-md" aria-label={$_('settings.apiDocsLoading')}></span>
					</div>
				{/if}
				<iframe
					src={docsUrl}
					title={$_('settings.apiDocsFrameTitle')}
					class="w-full h-[70vh] min-h-[28rem] bg-base-100"
					onload={() => {
						docsLoading = false;
					}}
				></iframe>
			</div>

			<a href={docsUrl} target="_blank" rel="noreferrer" class="link link-primary text-xs self-start">
				{$_('settings.apiDocsOpenNewTab')}
			</a>
		</div>
	</div>
</div>
