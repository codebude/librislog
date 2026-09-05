<script lang="ts">
	import { Calendar } from '@lucide/svelte';
	import SegmentedDateInput from './SegmentedDateInput.svelte';

	let {
		value = $bindable(''),
		invalid = $bindable(false),
		hasInput = $bindable(false),
		name = '',
		min = undefined,
		max = undefined,
		disabled = false,
		required = false,
		inputClass = 'input input-bordered input-sm w-full',
		ariaLabel = ''
	}: {
		value?: string;
		invalid?: boolean;
		hasInput?: boolean;
		name?: string;
		min?: string;
		max?: string;
		disabled?: boolean;
		required?: boolean;
		inputClass?: string;
		ariaLabel?: string;
	} = $props();

	let pickerInputEl: HTMLInputElement | undefined = $state();

	function openNativePicker() {
		if (disabled || !pickerInputEl) return;
		try {
			pickerInputEl.showPicker();
		} catch {
			pickerInputEl.focus();
			pickerInputEl.click();
		}
	}
</script>

<div class="flex items-center gap-2">
	<div class="flex-1 min-w-0 relative">
		<SegmentedDateInput
			{name}
			bind:value
			bind:invalid
			bind:hasInput
			{min}
			{max}
			{disabled}
			{required}
			{inputClass}
			{ariaLabel}
		/>
		<!-- Positioned over the date input so the native picker opens next to the field -->
		<input
			bind:this={pickerInputEl}
			type="date"
			class="absolute inset-0 opacity-0 pointer-events-none -z-10"
			bind:value
			{min}
			{max}
			{disabled}
			{required}
			aria-hidden="true"
			tabindex="-1"
		/>
	</div>

	<button
		type="button"
		class="btn btn-outline btn-sm"
		onclick={openNativePicker}
		disabled={disabled}
		aria-label={`Open date picker${ariaLabel ? ` for ${ariaLabel}` : ''}`}
		title="Open date picker"
	>
		<Calendar class="w-4 h-4" />
	</button>
</div>
