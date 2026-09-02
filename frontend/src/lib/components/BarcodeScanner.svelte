<script lang="ts">
	import Alert from '$lib/components/Alert.svelte';
	import { Html5QrcodeSupportedFormats, BaseLoggger } from 'html5-qrcode/esm/core';
	import { Html5QrcodeShim } from 'html5-qrcode/esm/code-decoder';
	import { _ } from '$lib/i18n';
	import { onDestroy } from 'svelte';
	import { RefreshCw, X } from '@lucide/svelte';

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

	let cameras = $state<MediaDeviceInfo[]>([]);
	let cameraIndex = $state(0);
	let selectedCameraId = $state<string | null>(null);
	let zoomSupported = $state(false);
	let zoom = $state(1);
	let zoomMax = $state(10);
	let zoomStep = $state(0.1);
	let zoomPresets = $state<number[]>([]);
	let focusContinuousSupported = $state(false);

	let decoder: Html5QrcodeShim | null = null;
	let scanTimer: ReturnType<typeof setInterval> | null = null;
	let scanCanvas: HTMLCanvasElement | null = null;

	const CAMERA_PREF_KEY = 'librislog.scanner.cameraId';
	const ZOOM_PREF_KEY = 'librislog.scanner.zoom';

	const SUPPORTED_FORMATS = [
		Html5QrcodeSupportedFormats.EAN_13,
		Html5QrcodeSupportedFormats.EAN_8,
		Html5QrcodeSupportedFormats.UPC_A,
		Html5QrcodeSupportedFormats.UPC_E,
		Html5QrcodeSupportedFormats.CODE_128
	];

	interface CameraCapabilities {
		focusMode?: string[];
		zoom?: { min?: number; max?: number; step?: number };
	}

	function normalizeIsbn(raw: string): string | null {
		const normalized = raw.trim().replaceAll('-', '').replaceAll(' ', '');
		if (/^\d{13}$/.test(normalized)) return normalized;
		if (/^\d{10}$/.test(normalized)) return normalized;
		return null;
	}

	function readCameraPref(): string | null {
		try {
			return window.localStorage.getItem(CAMERA_PREF_KEY);
		} catch {
			return null;
		}
	}

	function writeCameraPref(deviceId: string) {
		try {
			window.localStorage.setItem(CAMERA_PREF_KEY, deviceId);
		} catch {
			// ignore storage errors (e.g. private browsing)
		}
	}

	function readZoomPref(): number | null {
		try {
			const value = Number(window.localStorage.getItem(ZOOM_PREF_KEY));
			return Number.isFinite(value) ? value : null;
		} catch {
			return null;
		}
	}

	function writeZoomPref(zoomValue: number) {
		try {
			window.localStorage.setItem(ZOOM_PREF_KEY, String(zoomValue));
		} catch {
			// ignore storage errors (e.g. private browsing)
		}
	}

	function clearScanning() {
		if (scanTimer) {
			clearInterval(scanTimer);
			scanTimer = null;
		}
		decoder = null;
		scanCanvas = null;
	}

	async function stopStream() {
		clearScanning();
		if (stream) {
			for (const track of stream.getTracks()) {
				track.stop();
			}
			stream = null;
		}
	}

	async function stopScanner() {
		await stopStream();
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

	async function enumerateCameras(): Promise<MediaDeviceInfo[]> {
		const devices = await navigator.mediaDevices.enumerateDevices();
		return devices.filter((d) => d.kind === 'videoinput');
	}

	async function ensureCameraSelection() {
		let devices = await enumerateCameras();
		const hasLabels = devices.some((d) => d.kind === 'videoinput' && !!d.label);
		let permissionStream: MediaStream | null = null;
		if (!hasLabels) {
			// The first getUserMedia triggers the permission prompt, which makes
			// device labels available for a meaningful selection.
			try {
				permissionStream = await navigator.mediaDevices.getUserMedia({
					audio: false,
					video: {
						facingMode: { ideal: 'environment' },
						width: { min: 640 },
						height: { min: 480 }
					}
				});
			} catch {
				// permission denied — surface the no-camera error below
			}
			devices = await enumerateCameras();
			permissionStream?.getTracks().forEach((t) => t.stop());
		}

		cameras = devices;
		if (!cameras.length) {
			throw new Error($_('scanner.noCamera'));
		}

		const preferred = readCameraPref();
		let index = cameras.findIndex((c) => c.deviceId === preferred);
		if (index === -1) {
			index = cameras.findIndex((c) => /back|environment|rear/i.test(c.label));
		}
		if (index === -1) index = 0;
		cameraIndex = index;
		selectedCameraId = cameras[index].deviceId;
		writeCameraPref(selectedCameraId);
	}

	function roundToStep(value: number, step: number): number {
		return Number((Math.round(value / step) * step).toFixed(6));
	}

	function computeZoomPresets(min: number, max: number, step: number): number[] {
		// Common Android lens stops (ultra-wide/main/tele/macro). The device's
		// rear lenses are exposed as a single zoom range, so these presets let
		// the user switch between them.
		const stops = [0.5, 1, 2, 3, 5, 10, 20];
		const presets = new Set<number>();
		for (const stop of stops) {
			const clamped = Math.min(max, Math.max(min, stop));
			if (clamped >= min && clamped <= max) presets.add(roundToStep(clamped, step));
		}
		presets.add(min);
		presets.add(max);
		return [...presets].sort((a, b) => a - b);
	}

	async function applyTrackSettings(track: MediaStreamTrack | undefined) {
		zoomSupported = false;
		focusContinuousSupported = false;
		zoomPresets = [];
		if (!track || typeof track.getCapabilities !== 'function') return;
		const caps = track.getCapabilities() as MediaTrackCapabilities & CameraCapabilities;

		focusContinuousSupported =
			Array.isArray(caps.focusMode) && caps.focusMode.includes('continuous');

		const zoomCaps = caps.zoom;
		if (zoomCaps && typeof zoomCaps.max === 'number' && zoomCaps.max > 1) {
			const min = zoomCaps.min ?? 1;
			const step = zoomCaps.step ?? 0.1;
			zoomSupported = true;
			zoomMax = zoomCaps.max;
			zoomStep = step;
			// Restore the last selected zoom factor if it is still within range.
			const saved = readZoomPref();
			zoom = roundToStep(Math.min(zoomMax, Math.max(min, saved ?? 1)), step);
			zoomPresets = computeZoomPresets(min, zoomMax, step);
		}

		await applyTrackConstraints(track);
	}

	async function applyTrackConstraints(track: MediaStreamTrack) {
		const constraints: Record<string, unknown> = {};
		if (focusContinuousSupported) {
			constraints.advanced = [{ focusMode: 'continuous' }];
		}
		if (zoomSupported) {
			constraints.zoom = zoom;
		}
		try {
			await track.applyConstraints(constraints as unknown as MediaTrackConstraints);
		} catch {
			// combination of constraints not supported — ignore
		}
	}

	async function startStream() {
		if (!selectedCameraId) throw new Error($_('scanner.noCamera'));
		clearScanning();
		const mediaStream = await navigator.mediaDevices.getUserMedia({
			audio: false,
			video: {
				deviceId: { exact: selectedCameraId },
				width: { min: 640 },
				height: { min: 480 }
			}
		});
		stream = mediaStream;
		await applyTrackSettings(mediaStream.getVideoTracks()[0]);

		decoder = new Html5QrcodeShim(SUPPORTED_FORMATS, true, false, new BaseLoggger(false));
		scanCanvas = document.createElement('canvas');

		await waitForVideoEl();
		videoEl!.srcObject = mediaStream;
		await videoEl!.play();
		scanTimer = setInterval(scanFrame, 100);
	}

	async function startScanner() {
		if (starting || stream) return;
		if (!navigator.mediaDevices?.getUserMedia) throw new Error($_('scanner.noCamera'));
		starting = true;
		scannerError = null;
		detectionLocked = false;
		try {
			await ensureCameraSelection();
			await startStream();
		} catch (err: unknown) {
			scannerError = err instanceof Error ? err.message : $_('scanner.startError');
			await stopStream();
		} finally {
			starting = false;
		}
	}

	async function switchCamera() {
		if (starting || cameras.length < 2 || !selectedCameraId) return;
		starting = true;
		scannerError = null;
		try {
			cameraIndex = (cameraIndex + 1) % cameras.length;
			const next = cameras[cameraIndex];
			selectedCameraId = next.deviceId;
			writeCameraPref(next.deviceId);
			// Stop the previous track before requesting the new stream — otherwise
			// Android tends to hand back the old stream.
			await stopStream();
			await startStream();
		} catch (err: unknown) {
			scannerError = err instanceof Error ? err.message : $_('scanner.startError');
			await stopStream();
		} finally {
			starting = false;
		}
	}

	async function applyZoom() {
		const track = stream?.getVideoTracks()[0];
		if (!track || !zoomSupported) return;
		writeZoomPref(zoom);
		await applyTrackConstraints(track);
	}

	async function waitForVideoEl(): Promise<void> {
		const timeout = Date.now() + 5000;
		while (!videoEl && Date.now() < timeout) {
			await new Promise((r) => setTimeout(r, 50));
		}
		if (!videoEl) throw new Error($_('scanner.startError'));
	}

	$effect(() => {
		if (open && !stream && !starting && !scannerError) {
			void startScanner();
			return;
		}
		if (!open) {
			scannerError = null;
			if (stream) {
				void stopScanner();
			}
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
					<button class="btn btn-ghost btn-sm btn-circle" onclick={closeScanner} aria-label={$_('scanner.close')}><X class="w-4 h-4" /></button>
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
								class="absolute inset-0 w-full h-full object-cover"
								autoplay
								playsinline
								muted
							></video>
						</div>

						<div class="flex items-center justify-center gap-4 flex-wrap">
							{#if zoomSupported}
								<div class="flex flex-col items-center gap-2">
									<div class="flex items-center gap-1 flex-wrap justify-center" title={$_('scanner.zoom')}>
										{#each zoomPresets as preset}
											<button
												class="btn btn-xs gap-0 {Math.abs(zoom - preset) < zoomStep / 2 ? 'btn-primary' : 'btn-outline'}"
												onclick={() => {
													zoom = preset;
													void applyZoom();
												}}
												aria-label={$_('scanner.zoomLevel', { values: { zoom: preset } })}
											>{preset}x</button>
										{/each}
									</div>
									<label class="flex items-center gap-2 text-sm text-base-content/70">
										<input
											type="range"
											min={zoomPresets[0]}
											max={zoomMax}
											step={zoomStep}
											bind:value={zoom}
											oninput={() => void applyZoom()}
											class="range range-primary range-xs w-40"
											aria-label={$_('scanner.zoom')}
										/>
									</label>
								</div>
							{/if}
							{#if cameras.length > 1}
								<button
									class="btn btn-outline btn-sm gap-2"
									onclick={() => void switchCamera()}
									disabled={starting}
									aria-label={$_('scanner.switchCamera')}
								>
									<RefreshCw class="w-4 h-4" />
									{$_('scanner.switchCamera')}
								</button>
							{/if}
						</div>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}