<script lang="ts">
	import { _ } from '$lib/i18n';

	let {
		value = $bindable(''),
		values = $bindable<string[] | undefined>(undefined),
		name = '',
		disabled = false,
		maxTagsCount,
		fetchSuggestions,
		label,
		placeholder,
		hint
	}: {
		value?: string;
		values?: string[];
		name?: string;
		disabled?: boolean;
		maxTagsCount?: number;
		fetchSuggestions?: (query: string) => Promise<string[]>;
		label?: string;
		placeholder?: string;
		hint?: string;
	} = $props();

	const listMode = $derived(values !== undefined);

	let inputValue = $state('');
	let inputEl: HTMLInputElement | undefined = $state();
	let suggestions: string[] = $state([]);
	let highlightedIndex = $state(-1);
	let isOpen = $state(false);
	let isLoading = $state(false);
	let debounceTimer: ReturnType<typeof setTimeout> | undefined = $state();
	let dropdownStyle = $state('');

	const chips = $derived.by(() => {
		if (listMode) return values ?? [];
		return value
			.split(',')
			.map((tag) => tag.trim())
			.filter(Boolean);
	});

	function setChips(next: string[]) {
		if (listMode) {
			values = next;
		} else {
			value = next.join(', ');
		}
	}

	function addCurrentChip() {
		if (disabled) return;
		const next = inputValue.trim();
		if (!next) return;

		if (chips.some((existing) => existing.toLowerCase() === next.toLowerCase())) {
			inputValue = '';
			return;
		}

		if (typeof maxTagsCount === 'number' && maxTagsCount > 0 && chips.length >= maxTagsCount) {
			inputValue = '';
			return;
		}

		setChips([...chips, next]);
		inputValue = '';
	}

	function removeChip(chip: string) {
		if (disabled) return;
		setChips(chips.filter((entry) => entry !== chip));
	}

	function handleInput() {
		// In list mode commas are literal characters (author names may contain
		// them); only Enter/Tab/suggestion add a chip.
		if (listMode) {
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
			return;
		}

		const commaIdx = inputValue.lastIndexOf(',');
		if (commaIdx >= 0) {
			const before = inputValue.slice(0, commaIdx).trim();
			if (before && !chips.some((t) => t.toLowerCase() === before.toLowerCase())) {
				if (!(typeof maxTagsCount === 'number' && maxTagsCount > 0 && chips.length >= maxTagsCount)) {
					setChips([...chips, before]);
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

	function selectSuggestion(chip: string) {
		if (disabled) return;
		if (chips.some((existing) => existing.toLowerCase() === chip.toLowerCase())) {
			inputValue = '';
			suggestions = [];
			isOpen = false;
			return;
		}
		if (typeof maxTagsCount === 'number' && maxTagsCount > 0 && chips.length >= maxTagsCount) {
			return;
		}
		setChips([...chips, chip]);
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

		if (event.key === 'Enter' || event.key === 'Tab' || (!listMode && event.key === ',')) {
			event.preventDefault();
			addCurrentChip();
			return;
		}

		if (event.key === 'Backspace' && inputValue === '' && chips.length > 0) {
			event.preventDefault();
			setChips(chips.slice(0, -1));
		}
	}

	function handleBlur() {
		if (!fetchSuggestions) {
			addCurrentChip();
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

<div class="flex flex-col gap-1" role="combobox" aria-expanded={isOpen} aria-controls="suggestion-list">
	<span class="label label-text">{label ?? $_('book.tags')}</span>

	<div class="relative">
		<div
			class="min-h-10 w-full rounded-lg border border-base-300 bg-base-100 px-2 py-1.5 flex flex-wrap items-center gap-1.5 cursor-text focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 {disabled ? 'opacity-60 cursor-not-allowed' : ''}"
		>
			{#each chips as chip (chip)}
				<span class="inline-flex items-center gap-1.5 rounded-lg border border-base-300 bg-base-200/70 text-base-content px-2 py-1 text-xs max-w-full shadow-sm">
					<span class="break-all">{chip}</span>
					{#if !disabled}
						<button
							type="button"
							class="h-4 w-4 inline-flex items-center justify-center rounded text-base-content/70 hover:text-base-content hover:bg-base-300/80"
							onclick={() => removeChip(chip)}
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
				aria-label={label}
				class="flex-1 min-w-28 bg-transparent border-0 outline-none text-sm px-1 py-0.5"
				placeholder={chips.length === 0 ? (placeholder ?? $_('book.tagsPlaceholder')) : ''}
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
						class="mx-1 my-0.5 px-3 py-2 cursor-pointer text-sm rounded-md border-2 transition-colors"
						class:bg-base-200={i !== highlightedIndex}
						class:border-base-300={i !== highlightedIndex}
						class:text-primary={i === highlightedIndex}
						class:font-semibold={i === highlightedIndex}
						style={
							i === highlightedIndex
								? 'background-color: oklch(var(--p) / 0.14); border-color: oklch(var(--p)); box-shadow: 0 0 0 1px oklch(var(--p) / 0.35);'
								: ''
						}
						onmousedown={() => selectSuggestion(suggestion)}
						onmouseenter={() => (highlightedIndex = i)}
					>
						{@html highlightMatch(suggestion, inputValue)}
					</li>
				{/each}
			</ul>
		{/if}
	</div>

	{#if hint !== undefined || !fetchSuggestions}
		<p class="text-xs text-base-content/60">{hint ?? $_('book.tagsHint')}</p>
	{/if}
</div>
