<script lang="ts">
	import Alert from '$lib/components/Alert.svelte';
	import { Html5QrcodeSupportedFormats, BaseLoggger } from 'html5-qrcode/esm/core';
	import { Html5QrcodeShim } from 'html5-qrcode/esm/code-decoder';
	import { _ } from '$lib/i18n';
	import { onDestroy } from 'svelte';

	let {
		open = $bindable(false),
		onDetected
	}: {
		open?: boolean;
		onDetected?: (isbn: string) => void;
	} = $props();

	let stream = $state<MediaStream | null>(null);
	let scannerError = $state<string | null>(null);
	let starting = $state(false);
	let detectionLocked = $state(false);
	let videoEl = $state<HTMLVideoElement | null>(null);

	let decoder: Html5QrcodeShim | null = null;
	let scanTimer: ReturnType<typeof setInterval> | null = null;
	let scanCanvas: HTMLCanvasElement | null = null;

	const SUPPORTED_FORMATS = [
		Html5QrcodeSupportedFormats.EAN_13,
		Html5QrcodeSupportedFormats.EAN_8,
		Html5QrcodeSupportedFormats.UPC_A,
		Html5QrcodeSupportedFormats.UPC_E,
		Html5QrcodeSupportedFormats.CODE_128
	];

	function normalizeIsbn(raw: string): string | null {
		const normalized = raw.trim().replaceAll('-', '').replaceAll(' ', '');
		if (/^\d{13}$/.test(normalized)) return normalized;
		if (/^\d{10}$/.test(normalized)) return normalized;
		return null;
	}

	async function stopScanner() {
		if (scanTimer) {
			clearInterval(scanTimer);
			scanTimer = null;
		}
		decoder = null;
		scanCanvas = null;
		if (stream) {
			for (const track of stream.getTracks()) {
				track.stop();
			}
			stream = null;
		}
	}

	async function closeScanner() {
		open = false;
		await stopScanner();
	}

	function scanFrame() {
		if (!videoEl || !decoder || !scanCanvas || detectionLocked) return;
		if (!videoEl.videoWidth || !videoEl.videoHeight) return;

		scanCanvas.width = videoEl.videoWidth;
		scanCanvas.height = videoEl.videoHeight;
		const ctx = scanCanvas.getContext('2d');
		if (!ctx) return;

		ctx.drawImage(videoEl, 0, 0);

		decoder.decodeAsync(scanCanvas).then((result) => {
			if (detectionLocked) return;
			const isbn = normalizeIsbn(result.text);
			if (!isbn) return;
			detectionLocked = true;
			onDetected?.(isbn);
			void closeScanner();
		}).catch(() => {});
	}

	async function startScanner() {
		if (starting || stream) return;
		starting = true;
		scannerError = null;
		detectionLocked = false;

		try {
			let mediaStream: MediaStream;
			try {
				mediaStream = await navigator.mediaDevices.getUserMedia({
					audio: false,
					video: {
						facingMode: { ideal: 'environment' },
						width: { min: 640 },
						height: { min: 480 }
					}
				});
			} catch {
				const devices = await navigator.mediaDevices.enumerateDevices();
				const cameras = devices.filter((d) => d.kind === 'videoinput');
				if (!cameras.length) throw new Error($_('scanner.noCamera'));
				const backCamera = cameras.find((c) =>
					c.label.toLowerCase().includes('back')
					|| c.label.toLowerCase().includes('environment')
				);
				mediaStream = await navigator.mediaDevices.getUserMedia({
					audio: false,
					video: { deviceId: { exact: (backCamera ?? cameras[0]).deviceId } }
				});
			}

			stream = mediaStream;
			decoder = new Html5QrcodeShim(SUPPORTED_FORMATS, true, false, new BaseLoggger(false));
			scanCanvas = document.createElement('canvas');

			await new Promise<void>((resolve) => {
				const check = () => {
					if (videoEl) {
						resolve();
					} else {
						requestAnimationFrame(check);
					}
				};
				requestAnimationFrame(check);
			});

			videoEl!.srcObject = mediaStream;
			await videoEl!.play();

			scanTimer = setInterval(scanFrame, 100);
		} catch (err: unknown) {
			scannerError =
				err instanceof Error ? err.message : $_('scanner.startError');
			await stopScanner();
		} finally {
			starting = false;
		}
	}

	$effect(() => {
		if (open && !stream && !starting) {
			void startScanner();
			return;
		}
		if (!open && stream) {
			void stopScanner();
		}
	});

	onDestroy(() => {
		void stopScanner();
	});
</script>

{#if open}
	<div class="fixed inset-0 z-[400]">
		<div
			class="absolute inset-0 bg-black/45"
			onclick={closeScanner}
			onkeydown={(e) => e.key === 'Escape' && closeScanner()}
			role="button"
			tabindex="0"
			aria-label={$_('scanner.close')}
		></div>

		<div class="absolute inset-0 z-[401] flex items-center justify-center p-2 sm:p-4">
			<div class="w-full max-w-4xl h-[88dvh] bg-base-100 rounded-xl shadow-2xl flex flex-col overflow-hidden" role="dialog" aria-modal="true" aria-label={$_('scanner.title')}>
				<div class="flex items-center justify-between px-4 py-3 border-b border-base-200">
					<h3 class="text-lg font-semibold">{$_('scanner.title')}</h3>
					<button class="btn btn-ghost btn-sm btn-circle" onclick={closeScanner} aria-label={$_('scanner.close')}>✕</button>
				</div>

				<div class="flex-1 min-h-0 p-4 flex flex-col gap-3 overflow-y-auto">
					<p class="text-sm text-base-content/70">
						{$_('scanner.help')}
					</p>

					{#if scannerError}
						<div class="alert alert-error text-sm">
							<span>{scannerError}</span>
						</div>
					{/if}

					{#if !scannerError}
						<div class="flex-1 min-h-72 rounded-lg bg-black overflow-hidden relative">
							<video
								bind:this={videoEl}
								class="absolute inset-0 w-full h-full object-contain"
								autoplay
								playsinline
								muted
							></video>
						</div>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
