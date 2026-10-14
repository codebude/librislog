<script lang="ts">
	import { _ } from '#lib/i18n/index.js';

	let fallbackGroupCounter = 0;

	function createInputGroupName(): string {
		if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
			return `rating-${crypto.randomUUID()}`;
		}
		fallbackGroupCounter += 1;
		return `rating-${fallbackGroupCounter}`;
	}

	let { value = $bindable(null), readonly = false, onChange }: {
		value?: number | null;
		readonly?: boolean;
		onChange?: (rating: number) => void;
	} = $props();

	const inputGroupName = createInputGroupName();
</script>

<div class="rating rating-sm" title={!readonly ? $_('common.clickToRate') : undefined}>
	{#each [1, 2, 3, 4, 5] as star}
		<input
			type="radio"
			name={inputGroupName}
			class="mask mask-star-2 bg-warning transition-all duration-150 {readonly ? 'cursor-default' : 'cursor-pointer hover:scale-125 hover:bg-amber-600 active:scale-95 active:bg-amber-400'}"
			checked={value === star}
			disabled={readonly}
			onclick={() => !readonly && onChange?.(star)}
			aria-label={$_('common.starLabel', { values: { star } })}
		/>
	{/each}
</div>
