<script lang="ts">
	import type { BasketItem } from '$lib/types';
	import { _ } from '$lib/i18n';
	import { X, ShoppingBasket } from '@lucide/svelte';
	import { formatAuthors } from '$lib/utils/authors';

	let {
		basket,
		importing,
		onRemove,
		onImport
	}: {
		basket: BasketItem[];
		importing: boolean;
		onRemove: (id: string) => void;
		onImport: () => void;
	} = $props();

	function acquisitionLabel(status: string): string {
		return $_(`acquisition.${status}` as never) as unknown as string;
	}

	function mediumLabel(medium: string | null): string | null {
		if (!medium) return null;
		return $_(`medium.${mediumToKey(medium)}` as never) as unknown as string;
	}

	function mediumToKey(medium: string): string {
		switch (medium) {
			case 'Print':
				return 'print';
			case 'eBook':
				return 'ebook';
			case 'Audiobook':
				return 'audiobook';
			case 'Comic / Graphic Novel':
				return 'comic_graphic_novel';
			case 'Magazine / Newspaper':
				return 'magazine_newspaper';
			default:
				return 'print';
		}
	}
</script>

<div class="flex flex-col gap-3 sm:pr-4">
	{#if basket.length === 0}
		<div class="flex flex-col items-center gap-2 text-center py-8">
			<ShoppingBasket class="w-8 h-8 text-base-content/30" />
			<p class="text-base-content/60 text-sm">{$_('import.basketEmpty')}</p>
		</div>
	{:else}
		<ul class="flex flex-col gap-2 max-h-80 overflow-y-auto">
			{#each basket as item}
				<li class="flex gap-3 items-start p-2 rounded-lg border border-base-200">
					{#if item.candidate.cover_url}
						<img
							src={item.candidate.cover_url}
							alt={$_('book.cover')}
							class="w-10 rounded flex-shrink-0 object-cover"
						/>
					{:else}
						<div class="w-10 h-14 bg-base-200 rounded flex-shrink-0"></div>
					{/if}
					<div class="flex-1 min-w-0">
						<p class="font-medium text-sm line-clamp-2">{item.candidate.title}</p>
						{#if item.candidate.authors?.length}
							<p class="text-xs text-base-content/60">{formatAuthors(item.candidate.authors, item.candidate.author)}</p>
						{/if}
						<div class="flex flex-wrap items-center gap-1.5 text-xs text-base-content/40">
							<span>{item.candidate.source}</span>
							{#if item.candidate.published_year}
								<span>·</span>
								<span>{item.candidate.published_year}</span>
							{/if}
							<span class="badge badge-ghost badge-xs">{acquisitionLabel(item.acquisitionStatus)}</span>
							{#if item.medium}
								<span class="badge badge-ghost badge-xs">{mediumLabel(item.medium)}</span>
							{/if}
						</div>
					</div>
					<button
						class="btn btn-ghost btn-xs btn-circle shrink-0"
						aria-label={$_('import.basketRemove')}
						title={$_('import.basketRemove')}
						disabled={importing}
						onclick={() => onRemove(item.id)}
					>
						<X class="w-4 h-4" />
					</button>
				</li>
			{/each}
		</ul>
		<div class="flex items-center justify-between gap-2 pt-2">
			<span class="text-sm text-base-content/70">
				{$_('import.basketCount', { values: { count: basket.length } })}
			</span>
			<button class="btn btn-primary btn-sm" onclick={onImport} disabled={importing || basket.length === 0}>
				{importing ? $_('import.importingBasket') : $_('import.importBasket')}
			</button>
		</div>
	{/if}
</div>