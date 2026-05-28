<script lang="ts">
	let {
		value = $bindable(''),
		label = '',
		placeholder = '',
		name = '',
		disabled = false,
		fetchSuggestions = async (_q: string): Promise<string[]> => []
	}: {
		value?: string;
		label?: string;
		placeholder?: string;
		name?: string;
		disabled?: boolean;
		fetchSuggestions?: (query: string) => Promise<string[]>;
	} = $props();

	let inputValue = $state('');
	let suggestions: string[] = $state([]);
	let highlightedIndex = $state(-1);
	let isOpen = $state(false);
	let isLoading = $state(false);
	let debounceTimer: ReturnType<typeof setTimeout> | undefined = $state();
	let containerEl: HTMLDivElement | undefined = $state();
	let dropdownStyle = $state('');
	let inputEl: HTMLInputElement | undefined = $state();

	$effect(() => {
		inputValue = value;
	});

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

	function handleInput() {
		value = inputValue;
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

	function selectSuggestion(suggestion: string) {
		inputValue = suggestion;
		value = suggestion;
		suggestions = [];
		isOpen = false;
		highlightedIndex = -1;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (!isOpen) return;

		if (event.key === 'ArrowDown') {
			event.preventDefault();
			highlightedIndex = Math.min(highlightedIndex + 1, suggestions.length - 1);
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			highlightedIndex = Math.max(highlightedIndex - 1, 0);
		} else if (event.key === 'Enter' && highlightedIndex >= 0) {
			event.preventDefault();
			selectSuggestion(suggestions[highlightedIndex]);
		} else if (event.key === 'Escape') {
			event.preventDefault();
			isOpen = false;
			highlightedIndex = -1;
		}
	}

	function handleBlur() {
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
		return `${before}<mark class="bg-primary-100 text-primary font-medium rounded">${match}</mark>${after}`;
	}
</script>

<div bind:this={containerEl} class="flex flex-col gap-1" role="combobox" aria-expanded={isOpen} aria-controls="suggestion-list">
	{#if label}
		<span class="label label-text">{label}</span>
	{/if}
	<div class="relative">
		<input
			type="text"
			class="input input-bordered w-full"
			bind:this={inputEl}
			bind:value={inputValue}
			oninput={handleInput}
			onkeydown={handleKeydown}
			onblur={handleBlur}
			{placeholder}
			{disabled}
			{name}
			autocomplete="off"
			role="searchbox"
			aria-autocomplete="list"
			aria-controls="suggestion-list"
		/>
		{#if isLoading}
			<div class="absolute right-2 top-1/2 -translate-y-1/2">
				<span class="loading loading-spinner loading-xs"></span>
			</div>
		{/if}
		{#if isOpen}
			<ul
				id="suggestion-list"
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
</div>
