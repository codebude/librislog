<script lang="ts">
	import { _ } from '$lib/i18n';

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
	<svg class="w-4 h-4 text-base-content/40 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
		<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
	</svg>
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
		>✕</button>
	{/if}
</label>
