<script lang="ts">
	import { _ } from '$lib/i18n';
	import type { ImportFieldConfig } from '$lib/types';
	import { highlightPython } from '$lib/utils/prism';
	import { Info } from '@lucide/svelte';

	let {
		sourceFields,
		dbFields,
		mapping,
		onChange
	}: {
		sourceFields: string[];
		dbFields: string[];
		mapping: Record<string, ImportFieldConfig>;
		onChange: (mapping: Record<string, ImportFieldConfig>) => void;
	} = $props();

	const MANDATORY_FIELDS = ['title', 'author', 'page_count'];
	let transformOpen = $state<Record<string, boolean>>({});

	function updateSource(target: string, source: string) {
		const next = { ...mapping };
		if (source) {
			next[target] = { ...(next[target] || { transform: null }), source };
			transformOpen[target] = true;
		} else {
			next[target] = { source: '', transform: null };
		}
		onChange(next);
	}

	function updateTransform(target: string, transform: string) {
		const next = { ...mapping };
		next[target] = { ...(next[target] || { source: '' }), transform: transform || null };
		onChange(next);
		if (transform) {
			transformOpen[target] = true;
		}
	}

	$effect(() => {
		for (const [target, config] of Object.entries(mapping)) {
			if (config?.transform) {
				transformOpen[target] = true;
			}
		}
	});

	function handleKeydown(e: KeyboardEvent, target: string) {
		if (e.key === 'Tab') {
			e.preventDefault();
			const ta = e.currentTarget as HTMLTextAreaElement;
			const start = ta.selectionStart;
			const end = ta.selectionEnd;
			const val = ta.value;
			const newVal = val.substring(0, start) + '\t' + val.substring(end);
			updateTransform(target, newVal);
			requestAnimationFrame(() => {
				ta.selectionStart = ta.selectionEnd = start + 1;
			});
		}
	}

	function syncScroll(e: Event) {
		const ta = e.currentTarget as HTMLTextAreaElement;
		const pre = ta.parentElement?.querySelector('pre');
		if (pre) {
			pre.scrollTop = ta.scrollTop;
			pre.scrollLeft = ta.scrollLeft;
		}
	}
</script>

<div class="grid gap-3">
	{#each dbFields as dbField}
		{@const isMandatory = MANDATORY_FIELDS.includes(dbField)}
		{@const config = mapping[dbField] ?? { source: '', transform: null }}
		{@const currentSource = config.source ?? ''}
		{@const hasTransform = Boolean(config.transform)}
		<div class="border border-base-200 rounded-lg p-3 {isMandatory && !currentSource ? 'bg-error/5 border-error/30' : 'bg-base-100'}">
			<div class="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-2 items-center">
				<div class="text-sm break-all">
					<span class="font-medium">{dbField}</span>
					{#if isMandatory}
						<span class="text-error text-xs ml-1">*</span>
					{/if}
				</div>
				<div class="text-base-content/50 text-center">&lt;-</div>
				<select
					class="select select-bordered select-sm {isMandatory && !currentSource ? 'select-error' : ''}"
					name={`mapping-target-${dbField}`}
					aria-label={`Map source for ${dbField}`}
					value={currentSource}
					onchange={(e) => updateSource(dbField, e.currentTarget.value)}
				>
					<option value="">{$_('data.import.none')}</option>
					{#each sourceFields as source}
						<option value={source}>{source}</option>
					{/each}
				</select>
			</div>
			{#if currentSource}
				{#if dbField === 'cover_url'}
					<div class="mt-1.5 text-xs text-base-content/50 flex items-start gap-1">
						<Info class="w-3.5 h-3.5 mt-0.5 shrink-0" />
						<span>{$_('data.import.coverUrlHint')}</span>
					</div>
				{/if}
				<div class="mt-2">
					<button
						class="flex items-center gap-1 text-xs text-base-content/50 hover:text-base-content cursor-pointer"
						onclick={() => (transformOpen[dbField] = !transformOpen[dbField])}
						type="button"
					>
						<svg class="w-3 h-3 transition-transform {transformOpen[dbField] || hasTransform ? 'rotate-90' : ''}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
						{$_('data.import.transformLabel')}
					</button>
					{#if transformOpen[dbField] || hasTransform}
						<div class="mt-1.5 space-y-1.5">
							<div class="relative">
								<pre
									class="absolute inset-0 text-xs leading-relaxed py-2 px-3 m-0 overflow-hidden pointer-events-none whitespace-pre-wrap break-all border border-transparent rounded-[var(--radius-box,0.5rem)] transform-pre"
									aria-hidden="true"
								><code>{@html highlightPython(config.transform ?? '')}</code>&#8203;</pre>
								<textarea
									class="textarea textarea-bordered w-full text-xs leading-relaxed relative bg-transparent resize-y transform-textarea"
									id={`mapping-transform-${dbField}`}
									name={`mapping-transform-${dbField}`}
									aria-label={`Transform for ${dbField}`}
									placeholder={$_('data.import.transformPlaceholder')}
									value={config.transform ?? ''}
									oninput={(e) => updateTransform(dbField, e.currentTarget.value)}
									onkeydown={(e) => handleKeydown(e, dbField)}
									onscroll={syncScroll}
									rows={3}
									spellcheck={false}
								></textarea>
							</div>
							<details class="text-xs text-base-content/50">
								<summary class="cursor-pointer hover:text-base-content">{$_('data.import.transformHelp')}</summary>
								<div class="mt-1 p-2 rounded bg-base-200 space-y-0.5">
									<p><code class="text-primary">value</code> {$_('data.import.transformHelpValue')}</p>
									<p><code class="text-primary">row</code> {$_('data.import.transformHelpRow')}</p>
									<p><code class="text-primary">context</code> {$_('data.import.transformHelpContext')}</p>
									<p>{$_('data.import.transformHelpReturn')}</p>
									<p>{$_('data.import.transformHelpImports')}</p>
								</div>
							</details>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/each}
</div>

<div class="text-xs text-base-content/50 mt-1">
	<span class="text-error">*</span> {$_('data.import.requiredField')}
</div>

<style>
	:global(.hl-keyword) { color: #7c3aed; }
	:global(.hl-string) { color: #059669; }
	:global(.hl-number) { color: #d97706; }
	:global(.hl-function) { color: #2563eb; }
	:global(.hl-comment) { color: #94a3b8; font-style: italic; }

	.transform-pre,
	.transform-textarea {
		font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', 'Consolas', 'Menlo', monospace;
	}

	.transform-textarea {
		color: transparent;
		caret-color: var(--color-base-content);
	}
</style>
