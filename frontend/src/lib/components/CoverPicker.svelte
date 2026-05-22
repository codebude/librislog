<script lang="ts">
	import { api } from '$lib/api';
	import { _ } from '$lib/i18n';
	import { toasts } from '$lib/toasts';

	let {
		value = $bindable<string | null>(null),
		disabled = false
	}: {
		value?: string | null;
		disabled?: boolean;
	} = $props();

	let urlInput = $state('');
	let uploading = $state(false);
	let dragging = $state(false);
	let fileInput: HTMLInputElement | undefined = $state();
	const URL_PREVIEW_TIMEOUT_MS = 8000;

	async function handleFile(file: File) {
		if (disabled) return;
		uploading = true;
		try {
			value = await api.covers.upload(file);
			urlInput = '';
		} catch (e: unknown) {
			toasts.add(e instanceof Error ? e.message : $_('coverPicker.uploadFailed'), 'error');
		} finally {
			uploading = false;
		}
	}

	function onFileChange(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (file) handleFile(file);
		input.value = '';
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragging = false;
		const file = e.dataTransfer?.files?.[0];
		if (file) handleFile(file);
	}

	async function fetchUrl() {
		if (!urlInput.trim() || disabled) return;

		const candidate = urlInput.trim();
		uploading = true;
		try {
			const parsed = new URL(candidate);
			if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
				throw new Error('Unsupported URL scheme');
			}

			await new Promise<void>((resolve, reject) => {
				const image = new Image();
				const timeout = window.setTimeout(() => {
					reject(new Error('Image load timeout'));
				}, URL_PREVIEW_TIMEOUT_MS);

				image.onload = () => {
					window.clearTimeout(timeout);
					resolve();
				};
				image.onerror = () => {
					window.clearTimeout(timeout);
					reject(new Error('Image load failed'));
				};

				image.src = parsed.toString();
			});

			value = parsed.toString();
			urlInput = '';
		} catch {
			value = null;
			urlInput = '';
			toasts.add($_('coverPicker.urlInvalid'), 'error');
		} finally {
			uploading = false;
		}
	}

	function clear() {
		value = null;
		urlInput = '';
	}
</script>

<div class="flex flex-col gap-2">
	<span class="label label-text">{$_('book.cover')}</span>

	{#if value}
		<!-- Preview + clear -->
		<div class="flex items-start gap-3">
			<img
				src={value}
				alt={$_('coverPicker.previewAlt')}
				class="w-20 rounded shadow object-cover flex-shrink-0"
			/>
			{#if !disabled}
			<button
				type="button"
				class="btn btn-ghost btn-xs"
				onclick={clear}
				aria-label={$_('common.remove')}
			>{$_('common.remove')}</button>
			{/if}
		</div>
	{:else}
		<!-- Drop zone -->
		<div
			role="button"
			tabindex={disabled ? -1 : 0}
			aria-disabled={disabled}
			class="border-2 border-dashed rounded-lg p-4 text-center text-sm text-base-content/50 transition-colors
				{dragging ? 'border-primary bg-primary/10' : 'border-base-300'}
				{disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-primary'}"
			ondragover={(e) => { e.preventDefault(); dragging = true; }}
			ondragleave={() => (dragging = false)}
			ondrop={onDrop}
			onclick={() => !disabled && fileInput?.click()}
			onkeydown={(e) => e.key === 'Enter' && !disabled && fileInput?.click()}
		>
			{#if uploading}
				<span class="loading loading-spinner loading-sm"></span>
			{:else}
				<p>{$_('coverPicker.dropzone')} <span class="text-primary font-medium">{$_('coverPicker.browse')}</span></p>
			{/if}
		</div>

		<!-- Hidden file input -->
		<input
			bind:this={fileInput}
			type="file"
			name="cover-file"
			accept="image/*"
			class="hidden"
			onchange={onFileChange}
		/>

		<!-- URL input -->
		<div class="flex gap-2">
			<input
				class="input input-bordered input-sm flex-1"
				name="cover-url"
				placeholder={$_('coverPicker.pasteUrl')}
				bind:value={urlInput}
				{disabled}
				onkeydown={(e) => e.key === 'Enter' && (e.preventDefault(), fetchUrl())}
			/>
			<button
				type="button"
				class="btn btn-sm btn-outline"
				disabled={disabled || !urlInput.trim()}
				onclick={fetchUrl}
			>{$_('coverPicker.useUrl')}</button>
		</div>
	{/if}
</div>
