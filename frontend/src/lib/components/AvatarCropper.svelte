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
			<cropper-selection initial-coverage="0.8" aspect-ratio="1" border-radius="50%" movable resizable>
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
	let ready = $state(false);
	let initialImageTransform: number[] | null = null;

	$effect(() => {
		if (!open || !file) {
			return;
		}
		const url = URL.createObjectURL(file);
		objectUrl = url;
		return () => {
			cropper?.destroy();
			cropper = null;
			ready = false;
			initialImageTransform = null;
			URL.revokeObjectURL(url);
		};
	});

	function initCropper() {
		if (!imageEl || !containerEl) return;
		cropper?.destroy();
		try {
			cropper = new Cropper(imageEl, {
				container: containerEl,
				template: TEMPLATE
			});
			ready = true;
			const image = cropper.getCropperImage();
			if (image) {
				void image.$ready().then(() => {
					requestAnimationFrame(() => {
						initialImageTransform = image.$getTransform();
					});
				});
			}
		} catch (error) {
			console.error('Avatar cropper initialisation failed', error);
			errorMessage = $_('avatar.uploadFailed');
			ready = false;
		}
	}

	function zoom(scale: number) {
		cropper?.getCropperImage()?.$zoom(scale);
	}

	function reset() {
		const image = cropper?.getCropperImage();
		if (image) {
			if (initialImageTransform) {
				image.$setTransform(initialImageTransform);
			} else {
				image.$resetTransform();
				image.$center();
			}
		}
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
				canvas.toBlob((webpBlob) => {
					if (webpBlob) {
						resolve(webpBlob);
						return;
					}
					// Some browsers cannot encode WebP from a canvas. The server
					// accepts PNG and normalises it to WebP itself.
					canvas.toBlob(resolve, 'image/png');
				}, 'image/webp', 0.9);
			});
			if (!blob) {
				errorMessage = $_('avatar.uploadFailed');
				return;
			}
			errorMessage = null;
			await onsave(blob);
		} catch (error) {
			console.error('Avatar crop failed', error);
			errorMessage = $_('avatar.uploadFailed');
		} finally {
			saving = false;
		}
	}
</script>

{#if open}
	<div class="modal modal-open">
		<div class="modal-box max-w-xl">
			<div class="flex items-center justify-between gap-3 mb-4">
				<h3 class="text-lg font-semibold">{$_('avatar.cropTitle')}</h3>
				<button type="button" class="btn btn-ghost btn-sm btn-circle" onclick={oncancel} disabled={busy}>
					<X class="w-4 h-4" />
				</button>
			</div>

			<div bind:this={containerEl} class="avatar-cropper relative h-64 w-full overflow-hidden rounded-xl bg-base-300 sm:h-80">
				{#if objectUrl}
					<img
						bind:this={imageEl}
						src={objectUrl}
						alt=""
						onload={initCropper}
						onerror={() => {
							console.error('Avatar image could not be loaded');
							errorMessage = $_('avatar.invalidFormat');
							ready = false;
						}}
						class="block max-w-full"
					/>
				{/if}
			</div>

			<p class="mt-3 text-xs leading-relaxed text-base-content/55">{$_('avatar.cropHint')}</p>

			<div class="mt-4 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
				<div class="flex w-fit items-center gap-1 rounded-lg bg-base-200/60 p-1">
					<button type="button" class="btn btn-square btn-ghost btn-sm" onclick={() => zoom(-0.1)} disabled={busy} title={$_('avatar.cropZoomOut')} aria-label={$_('avatar.cropZoomOut')}>
						<ZoomOut class="w-4 h-4" />
					</button>
					<button type="button" class="btn btn-square btn-ghost btn-sm" onclick={() => zoom(0.1)} disabled={busy} title={$_('avatar.cropZoomIn')} aria-label={$_('avatar.cropZoomIn')}>
						<ZoomIn class="w-4 h-4" />
					</button>
					<button type="button" class="btn btn-ghost btn-sm" onclick={reset} disabled={busy}>
						<RotateCcw class="w-4 h-4" />
						{$_('avatar.cropReset')}
					</button>
				</div>
				<div class="flex items-center justify-end gap-2">
					<button type="button" class="btn btn-ghost" onclick={oncancel} disabled={busy}>
						{$_('avatar.cropCancel')}
					</button>
					<button type="button" class="btn btn-primary" onclick={save} disabled={busy || saving || !ready}>
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

<style>
	.avatar-cropper :global(cropper-canvas) {
		height: 100% !important;
	}
</style>
