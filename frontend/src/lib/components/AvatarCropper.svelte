<script lang="ts">
	import Cropper from 'cropperjs';
	import { _ } from '#lib/i18n/index.js';
	import { Check, RotateCcw, X, ZoomIn, ZoomOut } from '@lucide/svelte';

	let {
		open,
		file,
		busy = false,
		maxDimension = 512,
		errorText = null,
		onsave,
		oncancel
	}: {
		open: boolean;
		file: File | null;
		busy?: boolean;
		maxDimension?: number;
		errorText?: string | null;
		onsave: (blob: Blob) => void | Promise<void>;
		oncancel: () => void;
	} = $props();

	const TEMPLATE = `
		<cropper-canvas background>
			<cropper-image rotatable scalable skewable translatable></cropper-image>
			<cropper-shade hidden></cropper-shade>
			<cropper-handle action="select" plain></cropper-handle>
			<cropper-selection initial-coverage="0.8" aspect-ratio="1" movable resizable>
				<cropper-grid role="grid" bordered covered></cropper-grid>
				<cropper-crosshair centered></cropper-crosshair>
				<cropper-handle action="move" theme-color="rgba(255, 255, 255, 0.35)"></cropper-handle>
				<cropper-handle action="n-resize"></cropper-handle>
				<cropper-handle action="e-resize"></cropper-handle>
				<cropper-handle action="s-resize"></cropper-handle>
				<cropper-handle action="w-resize"></cropper-handle>
				<cropper-handle action="ne-resize"></cropper-handle>
				<cropper-handle action="nw-resize"></cropper-handle>
				<cropper-handle action="se-resize"></cropper-handle>
				<cropper-handle action="sw-resize"></cropper-handle>
			</cropper-selection>
		</cropper-canvas>
	`;

	let containerEl: HTMLDivElement | undefined = $state();
	let imageEl: HTMLImageElement | undefined = $state();
	let objectUrl = $state<string | null>(null);
	let cropper: Cropper | null = null;
	let errorMessage = $state<string | null>(null);
	let saving = $state(false);

	$effect(() => {
		if (!open || !file) {
			return;
		}
		const url = URL.createObjectURL(file);
		objectUrl = url;
		return () => {
			cropper?.destroy();
			cropper = null;
			URL.revokeObjectURL(url);
		};
	});

	function initCropper() {
		if (!imageEl || !containerEl) return;
		cropper?.destroy();
		cropper = new Cropper(imageEl, {
			container: containerEl,
			template: TEMPLATE
		});
	}

	function zoom(scale: number) {
		cropper?.getCropperImage()?.$zoom(scale);
	}

	function reset() {
		cropper?.getCropperImage()?.$transform(1, 0, 0, 1, 0, 0);
		cropper?.getCropperImage()?.$center();
		cropper?.getCropperSelection()?.$reset();
	}

	async function save() {
		if (saving) return;
		if (!cropper) {
			errorMessage = $_('avatar.uploadFailed');
			return;
		}
		saving = true;
		const selection = cropper.getCropperSelection();
		if (!selection) {
			saving = false;
			return;
		}
		if (selection.width < 64 || selection.height < 64) {
			errorMessage = $_('avatar.uploadFailed');
			saving = false;
			return;
		}

		try {
			const canvas = await selection.$toCanvas({
				width: maxDimension,
				height: maxDimension
			});
			const blob = await new Promise<Blob | null>((resolve) => {
				canvas.toBlob(resolve, 'image/webp', 0.9);
			});
			if (!blob) {
				errorMessage = $_('avatar.uploadFailed');
				return;
			}
			errorMessage = null;
			await onsave(blob);
		} catch {
			errorMessage = $_('avatar.uploadFailed');
		} finally {
			saving = false;
		}
	}
</script>

{#if open}
	<div class="modal modal-open">
		<div class="modal-box max-w-lg">
			<div class="flex items-center justify-between gap-3 mb-4">
				<h3 class="text-lg font-semibold">{$_('avatar.cropTitle')}</h3>
				<button type="button" class="btn btn-ghost btn-sm btn-circle" onclick={oncancel} disabled={busy}>
					<X class="w-4 h-4" />
				</button>
			</div>

			<div bind:this={containerEl} class="relative h-72 w-full overflow-hidden rounded-xl bg-base-300">
				{#if objectUrl}
					<img
						bind:this={imageEl}
						src={objectUrl}
						alt=""
						onload={initCropper}
						class="block max-w-full"
					/>
				{/if}
			</div>

			<div class="mt-4 flex items-center justify-between gap-2">
				<div class="flex items-center gap-1">
					<button type="button" class="btn btn-ghost btn-sm" onclick={() => zoom(0.9)} disabled={busy} title={$_('avatar.cropZoomOut')}>
						<ZoomOut class="w-4 h-4" />
					</button>
					<button type="button" class="btn btn-ghost btn-sm" onclick={() => zoom(1.1)} disabled={busy} title={$_('avatar.cropZoomIn')}>
						<ZoomIn class="w-4 h-4" />
					</button>
					<button type="button" class="btn btn-ghost btn-sm" onclick={reset} disabled={busy}>
						<RotateCcw class="w-4 h-4" />
						{$_('avatar.cropReset')}
					</button>
				</div>
				<div class="flex items-center gap-2">
					<button type="button" class="btn btn-ghost" onclick={oncancel} disabled={busy}>
						{$_('avatar.cropCancel')}
					</button>
					<button type="button" class="btn btn-primary" onclick={save} disabled={busy || saving}>
						{#if busy}
							<span class="loading loading-spinner loading-xs"></span>
						{:else}
							<Check class="w-4 h-4" />
						{/if}
						{$_('avatar.cropSave')}
					</button>
				</div>
			</div>

			{#if errorText || errorMessage}
				<p class="mt-3 text-sm text-error">{errorText || errorMessage}</p>
			{/if}
		</div>
	</div>
{/if}
