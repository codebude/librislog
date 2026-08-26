<script lang="ts">
	import { _ } from '$lib/i18n';
	import { CircleHelp } from '@lucide/svelte';

	let open = $state(false);

	$effect(() => {
		if (!open) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') open = false;
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	// Prefix names are intentionally hardcoded in English (never translated).
	const prefixes = [
		{ name: 'author', example: 'author:"Christoph Dittert"' },
		{ name: 'publisher', example: 'publisher:Ace' },
		{ name: 'title', example: 'title:fragezeichen' },
		{ name: 'tag', example: 'tag:cars' },
		{ name: 'language', example: 'language:en' },
		{ name: 'possession', example: 'possession:owned' },
		{ name: 'notes', example: 'notes:reading' },
		{ name: 'description', example: 'description:desert' }
	];
</script>

<div class="relative shrink-0">
	<button
		type="button"
		class="btn btn-ghost btn-circle btn-sm"
		aria-label={$_('search.help.title')}
		aria-expanded={open}
		onclick={() => (open = !open)}
	>
		<CircleHelp class="w-4 h-4" />
	</button>

	{#if open}
		<div
			class="fixed inset-0 z-40"
			role="presentation"
			onclick={() => (open = false)}
			onkeydown={(e) => {
				if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') open = false;
			}}
		></div>
		<div
			class="absolute right-0 top-full mt-2 w-72 rounded-xl bg-base-100 border border-base-200 shadow-lg z-50 p-4"
			role="dialog"
			aria-labelledby="search-help-title"
		>
			<h3 id="search-help-title" class="font-semibold text-sm mb-2">{$_('search.help.title')}</h3>
			<p class="text-xs text-base-content/70 mb-3">{$_('search.help.intro')}</p>

			<ul class="text-xs space-y-1 mb-3">
				{#each prefixes as p}
					<li>
						<code class="font-mono text-primary">{p.name}</code>
						<span class="text-base-content/70">:</span>
						<code class="font-mono text-base-content/80 break-all">{p.example}</code>
					</li>
				{/each}
			</ul>

			<p class="text-xs text-base-content/70 mb-1">
				{$_('search.help.multiWord')}
			</p>
			<p class="text-xs text-base-content/70 mb-1">
				{$_('search.help.combine')}
			</p>
			<p class="text-xs text-base-content/70">
				{$_('search.help.negate')}
			</p>
			<p class="text-xs text-base-content/50 mt-2">
				{$_('search.help.possessionValues')}
			</p>
		</div>
	{/if}
</div>