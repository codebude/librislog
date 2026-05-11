<script lang="ts">
	import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode';
	import { onDestroy, tick } from 'svelte';

	let {
		open = $bindable(false),
		onDetected
	}: {
		open?: boolean;
		onDetected?: (isbn: string) => void;
	} = $props();

	const readerId = `barcode-scanner-reader-${Math.random().toString(36).slice(2, 10)}`;

	let scanner = $state<Html5Qrcode | null>(null);
	let scannerError = $state<string | null>(null);
	let starting = $state(false);
	let stopping = $state(false);
	let detectionLocked = $state(false);

	function normalizeIsbn(raw: string): string | null {
		const normalized = raw.trim().replaceAll('-', '').replaceAll(' ', '');
		if (/^\d{13}$/.test(normalized)) return normalized;
		if (/^\d{10}$/.test(normalized)) return normalized;
		return null;
	}

	async function stopScanner() {
		if (!scanner || stopping) return;
		stopping = true;
		try {
			const current = scanner;
			scanner = null;
			try {
				await current.stop();
			} catch {
				// Ignore stop errors during teardown.
			}
			try {
				current.clear();
			} catch {
				// Ignore clear errors during teardown.
			}
		} finally {
			stopping = false;
		}
	}

	async function closeScanner() {
		open = false;
		await stopScanner();
	}

	async function startScanner() {
		if (scanner || starting) return;
		starting = true;
		detectionLocked = false;
		scannerError = null;

		try {
			await tick();

			const nextScanner = new Html5Qrcode(readerId, {
				formatsToSupport: [
					Html5QrcodeSupportedFormats.EAN_13,
					Html5QrcodeSupportedFormats.EAN_8,
					Html5QrcodeSupportedFormats.UPC_A,
					Html5QrcodeSupportedFormats.UPC_E,
					Html5QrcodeSupportedFormats.CODE_128
				],
				verbose: false
			});

			const scanConfig = {
				fps: 10,
				aspectRatio: 16 / 9,
				qrbox: { width: 300, height: 140 },
				disableFlip: false
			};

			const onSuccess = (decodedText: string) => {
				if (detectionLocked) return;
				const isbn = normalizeIsbn(decodedText);
				if (!isbn) return;
				detectionLocked = true;
				onDetected?.(isbn);
				void closeScanner();
			};

			const onError = () => {
				// Ignore per-frame decode failures while scanning.
			};

			try {
				await nextScanner.start({ facingMode: { ideal: 'environment' } }, scanConfig, onSuccess, onError);
			} catch {
				const cameras = await Html5Qrcode.getCameras();
				if (!cameras.length) {
					throw new Error('No camera device found.');
				}
				await nextScanner.start(cameras[0].id, scanConfig, onSuccess, onError);
			}

			scanner = nextScanner;
		} catch (err: unknown) {
			scannerError =
				err instanceof Error ? err.message : 'Unable to start barcode scanner. Check camera permissions.';
			await stopScanner();
		} finally {
			starting = false;
		}
	}

	$effect(() => {
		if (open && !scanner && !starting) {
			void startScanner();
			return;
		}

		if (!open && scanner && !stopping) {
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
			aria-label="Close scanner"
		></div>

		<div class="absolute inset-0 z-[401] flex items-center justify-center p-2 sm:p-4">
			<div class="w-full max-w-4xl h-[88dvh] bg-base-100 rounded-xl shadow-2xl flex flex-col overflow-hidden" role="dialog" aria-modal="true" aria-label="Scan ISBN Barcode">
				<div class="flex items-center justify-between px-4 py-3 border-b border-base-200">
					<h3 class="text-lg font-semibold">Scan ISBN Barcode</h3>
					<button class="btn btn-ghost btn-sm btn-circle" onclick={closeScanner} aria-label="Close scanner">✕</button>
				</div>

				<div class="flex-1 min-h-0 p-4 flex flex-col gap-3 overflow-y-auto">
					<p class="text-sm text-base-content/70">
						Point your camera at a book barcode. The search starts automatically after a valid ISBN is found.
					</p>

					{#if scannerError}
						<div class="alert alert-error text-sm">
							<span>{scannerError}</span>
						</div>
					{/if}

					<div class="flex-1 min-h-72 rounded-lg bg-base-200 overflow-hidden">
						<div id={readerId} class="w-full h-full"></div>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
