<script lang="ts">
	import { _ } from '$lib/i18n';

	let {
		value = $bindable(''),
		disabled = false,
		maxTagsCount
	}: {
		value?: string;
		disabled?: boolean;
		maxTagsCount?: number;
	} = $props();

	let inputValue = $state('');
	let inputEl: HTMLInputElement | undefined = $state();

	const tags = $derived.by(() =>
		value
			.split(',')
			.map((tag) => tag.trim())
			.filter(Boolean)
	);

	function setTags(nextTags: string[]) {
		value = nextTags.join(', ');
	}

	function addCurrentTag() {
		if (disabled) return;
		const next = inputValue.trim();
		if (!next) return;

		if (tags.some((existing) => existing.toLowerCase() === next.toLowerCase())) {
			inputValue = '';
			return;
		}

		if (typeof maxTagsCount === 'number' && maxTagsCount > 0 && tags.length >= maxTagsCount) {
			inputValue = '';
			return;
		}

		setTags([...tags, next]);
		inputValue = '';
	}

	function removeTag(tag: string) {
		if (disabled) return;
		setTags(tags.filter((entry) => entry !== tag));
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === 'Tab' || event.key === ',') {
			event.preventDefault();
			addCurrentTag();
			return;
		}

		if (event.key === 'Backspace' && inputValue === '' && tags.length > 0) {
			event.preventDefault();
			setTags(tags.slice(0, -1));
		}
	}

</script>

<div class="flex flex-col gap-2">
	<span class="label label-text">{$_('book.tags')}</span>

	<div
		class="min-h-10 w-full rounded-lg border border-base-300 bg-base-100 px-2 py-1.5 flex flex-wrap items-center gap-1.5 cursor-text focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 {disabled ? 'opacity-60 cursor-not-allowed' : ''}"
	>
		{#each tags as tag (tag)}
			<span class="inline-flex items-center gap-1.5 rounded-lg border border-base-300 bg-base-200/70 text-base-content px-2 py-1 text-xs max-w-full shadow-sm">
				<span class="break-all">{tag}</span>
				{#if !disabled}
					<button
						type="button"
						class="h-4 w-4 inline-flex items-center justify-center rounded text-base-content/70 hover:text-base-content hover:bg-base-300/80"
						onclick={() => removeTag(tag)}
						aria-label={$_('common.remove')}
					>
						×
					</button>
				{/if}
			</span>
		{/each}

		<input
			bind:this={inputEl}
			type="text"
			class="flex-1 min-w-28 bg-transparent border-0 outline-none text-sm px-1 py-0.5"
			placeholder={tags.length === 0 ? $_('book.tagsPlaceholder') : ''}
			bind:value={inputValue}
			{disabled}
			onkeydown={handleKeydown}
			onblur={addCurrentTag}
		/>
	</div>

	<p class="text-xs text-base-content/60">{$_('book.tagsHint')}</p>
</div>
