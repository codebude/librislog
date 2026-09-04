<script lang="ts">
	import { ChevronDown, ChevronUp, Search } from '@lucide/svelte';

	let {
		value = $bindable(''),
		options = [],
		name = '',
		ariaLabel = '',
		placeholder = '',
		noResultsText = '',
		selectClass = 'select select-bordered max-w-xs',
		disabled = false,
	}: {
		value?: string;
		options?: string[];
		name?: string;
		ariaLabel?: string;
		placeholder?: string;
		noResultsText?: string;
		selectClass?: string;
		disabled?: boolean;
	} = $props();

	let isOpen = $state(false);
	let query = $state('');
	let highlightedIndex = $state(-1);
	let rootEl: HTMLDivElement | undefined = $state();
	let searchEl: HTMLInputElement | undefined = $state();
	let listEl: HTMLUListElement | undefined = $state();
	let placement = $state<'below' | 'above'>('below');
	let listMaxHeight = $state('240px');
	let shouldFocusSearch = $state(false);

	const filtered = $derived(
		query.trim()
			? options.filter((o) => o.toLowerCase().includes(query.trim().toLowerCase()))
			: options,
	);

	function openDropdown(initialQuery = '', focusSearch = false) {
		if (disabled) return;
		isOpen = true;
		query = initialQuery;
		shouldFocusSearch = focusSearch;
		const list = initialQuery
			? options.filter((o) => o.toLowerCase().includes(initialQuery.toLowerCase()))
			: options;
		highlightedIndex = list.indexOf(value);
		if (rootEl) {
			const rect = rootEl.getBoundingClientRect();
			const spaceBelow = window.innerHeight - rect.bottom;
			const spaceAbove = rect.top;
			// Decide the placement once with a fixed estimate so it never
			// flips around while typing changes the list height.
			if (spaceBelow >= 264 || spaceBelow >= spaceAbove) {
				placement = 'below';
				listMaxHeight = `${Math.min(240, Math.max(96, spaceBelow - 64))}px`;
			} else {
				placement = 'above';
				listMaxHeight = `${Math.min(240, Math.max(96, spaceAbove - 64))}px`;
			}
		}
	}

	function closeDropdown() {
		isOpen = false;
		query = '';
		highlightedIndex = -1;
	}

	function selectOption(option: string) {
		value = option;
		closeDropdown();
	}

	function moveHighlight(delta: number) {
		const next = highlightedIndex + delta;
		if (next < 0) {
			highlightedIndex = 0;
		} else if (next >= filtered.length) {
			highlightedIndex = Math.max(0, filtered.length - 1);
		} else {
			highlightedIndex = next;
		}
	}

	function selectHighlightedOrFirst() {
		if (highlightedIndex >= 0 && filtered[highlightedIndex]) {
			selectOption(filtered[highlightedIndex]);
		} else if (filtered.length === 1) {
			selectOption(filtered[0]);
		}
	}

	function handleTriggerKeydown(event: KeyboardEvent) {
		if (disabled) return;
		if (!isOpen) {
			if (event.key.length === 1) {
				event.preventDefault();
				openDropdown(event.key, true);
			} else if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter') {
				event.preventDefault();
				openDropdown('', true);
			}
			return;
		}
		if (event.key === 'Escape') {
			event.preventDefault();
			closeDropdown();
		} else if (event.key === 'ArrowDown') {
			event.preventDefault();
			moveHighlight(1);
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			moveHighlight(-1);
		} else if (event.key === 'Enter') {
			event.preventDefault();
			selectHighlightedOrFirst();
		} else if (event.key.length === 1) {
			event.preventDefault();
			query = event.key;
			searchEl?.focus();
		}
	}

	function handleSearchKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			moveHighlight(1);
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			moveHighlight(-1);
		} else if (event.key === 'Enter') {
			event.preventDefault();
			selectHighlightedOrFirst();
		} else if (event.key === 'Escape') {
			event.preventDefault();
			closeDropdown();
		}
	}

	function onDocumentClick(event: MouseEvent) {
		if (rootEl && !rootEl.contains(event.target as Node)) {
			closeDropdown();
		}
	}

	$effect(() => {
		if (isOpen) {
			document.addEventListener('click', onDocumentClick);
			return () => document.removeEventListener('click', onDocumentClick);
		}
	});

	$effect(() => {
		if (isOpen && shouldFocusSearch) {
			searchEl?.focus();
		}
	});

	$effect(() => {
		if (!isOpen || highlightedIndex < 0) return;
		listEl?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' });
	});
</script>

<div bind:this={rootEl} class="relative inline-block" style="width:clamp(3rem,20rem,100%)">
	<button
		type="button"
		class="{selectClass} flex items-center justify-between gap-2 text-left"
		style="background-image:none;"
		{name}
		{disabled}
		aria-haspopup="listbox"
		aria-expanded={isOpen}
		aria-label={ariaLabel || undefined}
		onclick={() => (isOpen ? closeDropdown() : openDropdown())}
		onkeydown={handleTriggerKeydown}
	>
		<span class="truncate {value ? '' : 'opacity-60'}">{value || placeholder}</span>
		{#if isOpen}
			<ChevronUp class="w-4 h-4 shrink-0" />
		{:else}
			<ChevronDown class="w-4 h-4 shrink-0" />
		{/if}
	</button>

	{#if isOpen}
		<div
			class="absolute left-0 right-0 z-50 bg-base-100 border border-base-300 rounded-lg shadow-lg flex flex-col overflow-hidden {placement === 'below' ? 'top-full mt-1' : 'bottom-full mb-1'}"
		>
			<div class="p-2 border-b border-base-200">
				<div class="relative">
					<Search class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 opacity-50" />
					<input
						bind:this={searchEl}
						type="text"
						class="input input-bordered input-sm w-full pl-8"
						bind:value={query}
						onkeydown={handleSearchKeydown}
						{placeholder}
						autocomplete="off"
						role="combobox"
						aria-expanded={isOpen}
						aria-controls="searchable-select-list"
						aria-label={ariaLabel || undefined}
					/>
				</div>
			</div>
			<ul
				bind:this={listEl}
				id="searchable-select-list"
				class="overflow-y-auto p-1"
				style="max-height: {listMaxHeight}"
				role="listbox"
			>
				{#if filtered.length === 0}
					<li class="px-3 py-2 text-sm opacity-60">{noResultsText}</li>
				{:else}
					{#each filtered as option, i (option)}
						<li
							role="option"
							aria-selected={i === highlightedIndex}
							class="px-3 py-1.5 cursor-pointer text-sm rounded-md"
							class:bg-base-200={i !== highlightedIndex}
							style={i === highlightedIndex ? 'background-color: oklch(var(--p) / 0.1); color: oklch(var(--p));' : ''}
							onmousedown={() => selectOption(option)}
							onmouseenter={() => (highlightedIndex = i)}
						>
							{option}
						</li>
					{/each}
				{/if}
			</ul>
		</div>
	{/if}
</div>