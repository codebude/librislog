	<script lang="ts">
	import { _ } from '$lib/i18n';
	import { Search, X } from '@lucide/svelte';

	let {
		value = $bindable(''),
		placeholder,
		onSearch
	}: {
		value?: string;
		placeholder?: string;
		onSearch?: (q: string) => void;
	} = $props();

	let debounce: ReturnType<typeof setTimeout>;
	const effectivePlaceholder = $derived(placeholder ?? $_('common.search'));

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement;
		value = target.value;
		clearTimeout(debounce);
		debounce = setTimeout(() => onSearch?.(value), 300);
	}
</script>

<label class="input input-bordered input-sm flex items-center gap-2 w-full">
	<Search class="w-4 h-4 text-base-content/40 flex-shrink-0" />
	<input
		type="text"
		name="search"
		class="grow bg-transparent outline-none text-sm"
		placeholder={effectivePlaceholder}
		{value}
		oninput={handleInput}
	/>
	{#if value}
		<button
			class="text-base-content/40 hover:text-base-content"
			onclick={() => { value = ''; onSearch?.(''); }}
			aria-label={$_('common.search')}
		><X class="w-4 h-4" /></button>
	{/if}
</label>
