<script lang="ts">
	import { _ } from '$lib/i18n';

	let {
		value = $bindable(''),
		name = '',
		disabled = false,
		maxTagsCount,
		fetchSuggestions
	}: {
		value?: string;
		name?: string;
		disabled?: boolean;
		maxTagsCount?: number;
		fetchSuggestions?: (query: string) => Promise<string[]>;
	} = $props();

	let inputValue = $state('');
	let inputEl: HTMLInputElement | undefined = $state();
	let suggestions: string[] = $state([]);
	let highlightedIndex = $state(-1);
	let isOpen = $state(false);
	let isLoading = $state(false);
	let debounceTimer: ReturnType<typeof setTimeout> | undefined = $state();
	let dropdownStyle = $state('');

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

	function handleInput() {
		const commaIdx = inputValue.lastIndexOf(',');
		if (commaIdx >= 0) {
			const before = inputValue.slice(0, commaIdx).trim();
			if (before && !tags.some((t) => t.toLowerCase() === before.toLowerCase())) {
				if (!(typeof maxTagsCount === 'number' && maxTagsCount > 0 && tags.length >= maxTagsCount)) {
					setTags([...tags, before]);
				}
			}
			inputValue = inputValue.slice(commaIdx + 1).trimStart();
			suggestions = [];
			isOpen = false;
			highlightedIndex = -1;
			return;
		}

		if (!fetchSuggestions) return;
		clearTimeout(debounceTimer);
		const trimmed = inputValue.trim();
		if (!trimmed) {
			suggestions = [];
			isOpen = false;
			highlightedIndex = -1;
			return;
		}
		isLoading = true;
		debounceTimer = setTimeout(async () => {
			try {
				const results = await fetchSuggestions(trimmed);
				suggestions = results;
				isOpen = results.length > 0;
				highlightedIndex = -1;
			} catch {
				suggestions = [];
				isOpen = false;
			} finally {
				isLoading = false;
			}
		}, 250);
	}

	function selectSuggestion(tag: string) {
		if (disabled) return;
		if (tags.some((existing) => existing.toLowerCase() === tag.toLowerCase())) {
			inputValue = '';
			suggestions = [];
			isOpen = false;
			return;
		}
		if (typeof maxTagsCount === 'number' && maxTagsCount > 0 && tags.length >= maxTagsCount) {
			return;
		}
		setTags([...tags, tag]);
		inputValue = '';
		suggestions = [];
		isOpen = false;
		highlightedIndex = -1;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (isOpen) {
			if (event.key === 'ArrowDown') {
				event.preventDefault();
				highlightedIndex = Math.min(highlightedIndex + 1, suggestions.length - 1);
				return;
			}
			if (event.key === 'ArrowUp') {
				event.preventDefault();
				highlightedIndex = Math.max(highlightedIndex - 1, 0);
				return;
			}
			if (event.key === 'Enter' && highlightedIndex >= 0) {
				event.preventDefault();
				selectSuggestion(suggestions[highlightedIndex]);
				return;
			}
			if (event.key === 'Escape') {
				event.preventDefault();
				isOpen = false;
				highlightedIndex = -1;
				return;
			}
		}

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

	function handleBlur() {
		if (!fetchSuggestions) {
			addCurrentTag();
			return;
		}
		setTimeout(() => {
			isOpen = false;
			highlightedIndex = -1;
		}, 200);
	}

	function highlightMatch(text: string, query: string): string {
		if (!query.trim()) return text;
		const idx = text.toLowerCase().indexOf(query.toLowerCase());
		if (idx === -1) return text;
		const before = text.slice(0, idx);
		const match = text.slice(idx, idx + query.length);
		const after = text.slice(idx + query.length);
		return `${before}<mark class="bg-primary/20 text-primary font-medium rounded">${match}</mark>${after}`;
	}

	$effect(() => {
		if (!isOpen || !inputEl) return;
		const rect = inputEl.getBoundingClientRect();
		const spaceBelow = window.innerHeight - rect.bottom;
		const dropdownHeight = Math.min(192, suggestions.length * 36 + 16);
		if (spaceBelow >= dropdownHeight + 8) {
			dropdownStyle = `position:fixed;top:${rect.bottom + 4}px;left:${rect.left}px;width:${rect.width}px`;
		} else {
			dropdownStyle = `position:fixed;bottom:${window.innerHeight - rect.top + 4}px;left:${rect.left}px;width:${rect.width}px`;
		}
	});
</script>

<div class="flex flex-col gap-2">
	<span class="label label-text">{$_('book.tags')}</span>

	<div class="relative">
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
				name={name || 'tags'}
				class="flex-1 min-w-28 bg-transparent border-0 outline-none text-sm px-1 py-0.5"
				placeholder={tags.length === 0 ? $_('book.tagsPlaceholder') : ''}
				bind:value={inputValue}
				{disabled}
				oninput={handleInput}
				onkeydown={handleKeydown}
				onblur={handleBlur}
				autocomplete="off"
				enterkeyhint="done"
			/>
			{#if isLoading}
				<div class="absolute right-2 top-1/2 -translate-y-1/2">
					<span class="loading loading-spinner loading-xs"></span>
				</div>
			{/if}
		</div>

		{#if isOpen}
			<ul
				role="listbox"
				class="z-50 bg-base-100 border border-base-300 rounded-lg shadow-lg max-h-48 overflow-y-auto"
				style={dropdownStyle || 'position:absolute;left:0;right:0;margin-top:0.25rem'}
			>
				{#each suggestions as suggestion, i}
					<li
						role="option"
						aria-selected={i === highlightedIndex}
						class="px-3 py-2 cursor-pointer text-sm"
						class:bg-base-200={i !== highlightedIndex}
						style={i === highlightedIndex ? 'background-color: oklch(var(--p) / 0.1); color: oklch(var(--p));' : ''}
						onmousedown={() => selectSuggestion(suggestion)}
						onmouseenter={() => (highlightedIndex = i)}
					>
						{@html highlightMatch(suggestion, inputValue)}
					</li>
				{/each}
			</ul>
		{/if}
	</div>

	{#if !fetchSuggestions}
		<p class="text-xs text-base-content/60">{$_('book.tagsHint')}</p>
	{/if}
</div>
