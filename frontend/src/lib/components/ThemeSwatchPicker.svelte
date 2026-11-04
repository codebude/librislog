<script lang="ts">
	import { Check } from '@lucide/svelte';

	import { themeLabel } from '#lib/stores/theme.js';

	interface ThemeGroup {
		label: string;
		themes: readonly string[];
	}

	let {
		selected,
		groups,
		onSelect,
		name = 'custom-theme',
		labelledBy
	}: {
		selected: string | null;
		groups: ThemeGroup[];
		onSelect?: (theme: string) => void;
		name?: string;
		labelledBy?: string;
	} = $props();

	function headingId(label: string): string {
		return `theme-group-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
	}
</script>

<div
	class="max-w-3xl p-1 sm:max-h-80 sm:overflow-y-auto"
	role="radiogroup"
	aria-labelledby={labelledBy}
>
	<div class="flex flex-col gap-3">
		{#each groups as group (group.label)}
			<div
				class="flex flex-col gap-1.5"
				role="group"
				aria-labelledby={headingId(group.label)}
				data-theme-group={group.label}
			>
				<p id={headingId(group.label)} class="text-xs font-semibold tracking-wide text-base-content/60 uppercase">
					{group.label}
				</p>
				<div class="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
					{#each group.themes as theme (theme)}
						{@const label = themeLabel(theme)}
						{@const shortLabel = label.startsWith(`${group.label} `)
							? label.slice(group.label.length + 1)
							: label}
						<label
							class="group relative flex cursor-pointer flex-col gap-1.5 rounded-xl border p-2 transition focus-within:ring-2 focus-within:ring-primary/60 {selected ===
							theme
								? 'border-primary bg-primary/5 ring-2 ring-primary/30'
								: 'border-base-300 hover:border-primary/50'}"
							data-theme-option={theme}
						>
							<input
								type="radio"
								{name}
								value={theme}
								checked={selected === theme}
								class="sr-only"
								onchange={() => onSelect?.(theme)}
							/>
							<span
								class="pointer-events-none flex h-9 gap-1 rounded-md border border-base-300 p-1"
								data-theme={theme}
								aria-hidden="true"
							>
								<span class="flex flex-1 flex-col justify-center gap-1 rounded bg-base-100 px-1">
									<span class="h-1 w-3/4 rounded-full bg-base-content/70"></span>
									<span class="h-1 w-1/2 rounded-full bg-base-content/40"></span>
								</span>
								<span class="flex w-5 flex-col gap-1">
									<span class="flex-1 rounded bg-primary"></span>
									<span class="flex-1 rounded bg-secondary"></span>
								</span>
								<span class="w-1.5 rounded bg-accent"></span>
							</span>
							<span class="flex items-center justify-between gap-1">
								<span
									class="min-w-0 truncate text-[11px] leading-tight {selected === theme
										? 'font-semibold text-base-content'
										: 'text-base-content/80'}">{shortLabel}</span
								>
								{#if selected === theme}
									<Check class="h-3.5 w-3.5 shrink-0 text-primary" />
								{/if}
							</span>
						</label>
					{/each}
				</div>
			</div>
		{/each}
	</div>
</div>
