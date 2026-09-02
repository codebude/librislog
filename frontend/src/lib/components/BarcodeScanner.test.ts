import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import BarcodeScanner from './BarcodeScanner.svelte';

// Mock html5-qrcode subpath imports
vi.mock('html5-qrcode/esm/core', () => {
	const BaseLoggger = class {
		log() {} warn() {} logError() {} logErrors() {}
	};
	return {
		Html5QrcodeSupportedFormats: {
			EAN_13: 9, EAN_8: 10, UPC_A: 14, UPC_E: 15, CODE_128: 5
		},
		BaseLoggger
	};
});

vi.mock('html5-qrcode/esm/code-decoder', () => {
	const Html5QrcodeShim = class {
		decodeAsync: () => Promise<{ text: string }>;
		constructor() {
			this.decodeAsync = function () { return Promise.resolve({ text: '' }); };
		}
	};
	return { Html5QrcodeShim };
});

const CAMERA_PREF_KEY = 'librislog.scanner.cameraId';
const ZOOM_PREF_KEY = 'librislog.scanner.zoom';

interface FakeTrack {
	deviceId: string;
	stop: ReturnType<typeof vi.fn>;
	getCapabilities: () => Record<string, unknown>;
	applyConstraints: ReturnType<typeof vi.fn>;
}

function makeTrack(deviceId: string, caps: Record<string, unknown> = {}): FakeTrack {
	return {
		deviceId,
		stop: vi.fn(),
		getCapabilities: () => caps,
		applyConstraints: vi.fn().mockResolvedValue(undefined)
	};
}

function makeStream(track: FakeTrack) {
	return {
		getTracks: () => [track],
		getVideoTracks: () => [track]
	};
}

interface Camera {
	deviceId: string;
	label: string;
}

function mockMediaDevices(
	cameras: Camera[],
	options: { labelsInitiallyHidden?: boolean; caps?: Record<string, unknown> } = {}
) {
	const enumerateDevices = vi.fn();
	const streams: ReturnType<typeof makeStream>[] = [];

	const labelled = cameras.map((c, i) => ({
		kind: 'videoinput',
		deviceId: c.deviceId,
		label: c.label,
		groupId: `group-${i}`
	}));
	const unlabelled = cameras.map((c, i) => ({
		kind: 'videoinput',
		deviceId: c.deviceId,
		label: '',
		groupId: `group-${i}`
	}));

	if (options.labelsInitiallyHidden) {
		enumerateDevices.mockResolvedValueOnce(unlabelled).mockResolvedValue(labelled);
	} else {
		enumerateDevices.mockResolvedValue(labelled);
	}

	const getUserMedia = vi.fn(async (constraints: { video?: { deviceId?: { exact?: string } } }) => {
		const id = constraints.video?.deviceId?.exact ?? cameras[0].deviceId;
		const track = makeTrack(id, options.caps ?? {});
		const stream = makeStream(track);
		streams.push(stream);
		return stream;
	});

	Object.defineProperty(navigator, 'mediaDevices', {
		configurable: true,
		value: { enumerateDevices, getUserMedia }
	});

	return { enumerateDevices, getUserMedia, streams };
}

function installMediaElementMocks() {
	if (typeof HTMLMediaElement.prototype.play === 'function') {
		vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
	} else {
		Object.defineProperty(HTMLMediaElement.prototype, 'play', {
			configurable: true,
			value: () => Promise.resolve()
		});
	}
	try {
		Object.defineProperty(HTMLMediaElement.prototype, 'srcObject', {
			configurable: true,
			get(this: HTMLMediaElement) {
				return (this as HTMLMediaElement & { _srcObject?: unknown })._srcObject ?? null;
			},
			set(this: HTMLMediaElement, value: unknown) {
				(this as HTMLMediaElement & { _srcObject?: unknown })._srcObject = value;
			}
		});
	} catch {
		// already defined non-configurably by the environment — fine for tests
	}
}

describe('BarcodeScanner', () => {
	const CAMERAS: Camera[] = [
		{ deviceId: 'cam-front', label: 'Front Camera' },
		{ deviceId: 'cam-rear', label: 'Rear Camera' },
		{ deviceId: 'cam-macro', label: 'Macro Camera' }
	];

	beforeEach(() => {
		vi.clearAllMocks();
		window.localStorage.clear();
		installMediaElementMocks();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it('requests the persisted camera with an exact deviceId', async () => {
		window.localStorage.setItem(CAMERA_PREF_KEY, 'cam-rear');
		const { getUserMedia } = mockMediaDevices(CAMERAS);

		render(BarcodeScanner, { props: { open: true } });

		await waitFor(() => {
			expect(getUserMedia).toHaveBeenCalledWith(
				expect.objectContaining({
					video: expect.objectContaining({ deviceId: { exact: 'cam-rear' } })
				})
			);
		});
	});

	it('falls back to a rear/environment camera and persists the choice', async () => {
		const { getUserMedia } = mockMediaDevices(CAMERAS);

		render(BarcodeScanner, { props: { open: true } });

		await waitFor(() => {
			expect(getUserMedia).toHaveBeenCalledWith(
				expect.objectContaining({
					video: expect.objectContaining({ deviceId: { exact: 'cam-rear' } })
				})
			);
		});
		expect(window.localStorage.getItem(CAMERA_PREF_KEY)).toBe('cam-rear');
	});

	it('cycles to the next camera and stops the previous track when switched', async () => {
		const { getUserMedia, streams } = mockMediaDevices(CAMERAS);

		render(BarcodeScanner, { props: { open: true } });

		await waitFor(() => {
			expect(getUserMedia).toHaveBeenCalledTimes(1);
		});
		expect(getUserMedia).toHaveBeenCalledWith(
			expect.objectContaining({
				video: expect.objectContaining({ deviceId: { exact: 'cam-rear' } })
			})
		);

		const switchBtn = await screen.findByRole('button', { name: /switch camera/i });
		await fireEvent.click(switchBtn);

		await waitFor(() => {
			expect(getUserMedia).toHaveBeenCalledTimes(2);
		});
		expect(getUserMedia).toHaveBeenLastCalledWith(
			expect.objectContaining({
				video: expect.objectContaining({ deviceId: { exact: 'cam-macro' } })
			})
		);
		// The previous stream's track must be stopped before requesting the new one.
		expect(streams[0].getTracks()[0].stop).toHaveBeenCalled();
		// The chosen camera is remembered for the next session.
		expect(window.localStorage.getItem(CAMERA_PREF_KEY)).toBe('cam-macro');
	});

	it('requests permission first when device labels are hidden', async () => {
		const { enumerateDevices, getUserMedia } = mockMediaDevices(CAMERAS, {
			labelsInitiallyHidden: true
		});

		render(BarcodeScanner, { props: { open: true } });

		await waitFor(() => {
			expect(enumerateDevices).toHaveBeenCalledTimes(2);
		});
		// First getUserMedia only triggers the permission prompt (no deviceId).
		expect(getUserMedia).toHaveBeenNthCalledWith(
			1,
			expect.objectContaining({
				video: expect.objectContaining({ facingMode: { ideal: 'environment' } })
			})
		);
		// The actual stream is then requested for the selected camera.
		expect(getUserMedia).toHaveBeenLastCalledWith(
			expect.objectContaining({
				video: expect.objectContaining({ deviceId: { exact: 'cam-rear' } })
			})
		);
	});

	it('exposes a zoom slider and applies zoom constraints when supported', async () => {
		const { getUserMedia } = mockMediaDevices(CAMERAS, {
			caps: { focusMode: ['continuous', 'manual'], zoom: { min: 1, max: 8, step: 1 } }
		});

		render(BarcodeScanner, { props: { open: true } });

		const slider = await screen.findByRole('slider', { name: /zoom/i });
		expect(slider).toBeInTheDocument();

		const firstStream = (await getUserMedia.mock.results[0].value) as ReturnType<typeof makeStream>;
		const track = firstStream.getVideoTracks()[0] as unknown as FakeTrack;
		// continuous focus mode is requested when the track supports it
		expect(track.applyConstraints).toHaveBeenCalledWith(
			expect.objectContaining({ advanced: expect.arrayContaining([{ focusMode: 'continuous' }]) })
		);

		await fireEvent.input(slider, { target: { value: '4' } });
		await waitFor(() => {
			expect(track.applyConstraints).toHaveBeenCalledWith(expect.objectContaining({ zoom: 4 }));
		});
	});

	it('offers rear-lens presets derived from the zoom range', async () => {
		const { getUserMedia } = mockMediaDevices(CAMERAS, {
			caps: { zoom: { min: 1, max: 8, step: 1 } }
		});

		render(BarcodeScanner, { props: { open: true } });

		// Common lens stops within [1, 8]: 1x, 2x, 3x, 5x, plus the max 8x.
		const one = await screen.findByRole('button', { name: /zoom 1x/i });
		expect(one).toBeInTheDocument();
		for (const level of ['2x', '3x', '5x', '8x']) {
			expect(screen.getByRole('button', { name: `Zoom ${level}` })).toBeInTheDocument();
		}
		expect(screen.queryByRole('button', { name: /zoom 0.5x/i })).not.toBeInTheDocument();

		const two = screen.getByRole('button', { name: 'Zoom 2x' });
		await fireEvent.click(two);

		const firstStream = (await getUserMedia.mock.results[0].value) as ReturnType<typeof makeStream>;
		const track = firstStream.getVideoTracks()[0] as unknown as FakeTrack;
		await waitFor(() => {
			expect(track.applyConstraints).toHaveBeenCalledWith(expect.objectContaining({ zoom: 2 }));
		});
		// The selected lens is remembered for the next session.
		expect(window.localStorage.getItem(ZOOM_PREF_KEY)).toBe('2');
	});

	it('restores the last selected zoom factor and highlights its lens button', async () => {
		window.localStorage.setItem(ZOOM_PREF_KEY, '5');
		const { getUserMedia } = mockMediaDevices(CAMERAS, {
			caps: { zoom: { min: 1, max: 8, step: 1 } }
		});

		render(BarcodeScanner, { props: { open: true } });

		const five = await screen.findByRole('button', { name: 'Zoom 5x' });
		expect(five).toBeInTheDocument();
		// The persisted zoom is applied to the track…
		const firstStream = (await getUserMedia.mock.results[0].value) as ReturnType<typeof makeStream>;
		const track = firstStream.getVideoTracks()[0] as unknown as FakeTrack;
		await waitFor(() => {
			expect(track.applyConstraints).toHaveBeenCalledWith(expect.objectContaining({ zoom: 5 }));
		});
		// …and the matching lens button is active.
		await waitFor(() => {
			expect(five.classList.contains('btn-primary')).toBe(true);
		});
	});

	it('clamps a persisted zoom that is out of range', async () => {
		window.localStorage.setItem(ZOOM_PREF_KEY, '50');
		const { getUserMedia } = mockMediaDevices(CAMERAS, {
			caps: { zoom: { min: 1, max: 8, step: 1 } }
		});

		render(BarcodeScanner, { props: { open: true } });

		await screen.findByRole('button', { name: 'Zoom 8x' });
		const firstStream = (await getUserMedia.mock.results[0].value) as ReturnType<typeof makeStream>;
		const track = firstStream.getVideoTracks()[0] as unknown as FakeTrack;
		await waitFor(() => {
			expect(track.applyConstraints).toHaveBeenCalledWith(expect.objectContaining({ zoom: 8 }));
		});
	});

	it('does not show zoom controls when the track has no zoom capability', async () => {
		const { getUserMedia } = mockMediaDevices(CAMERAS, { caps: {} });

		render(BarcodeScanner, { props: { open: true } });

		await waitFor(() => {
			expect(getUserMedia).toHaveBeenCalledTimes(1);
		});
		expect(screen.queryByRole('slider', { name: /zoom/i })).not.toBeInTheDocument();
	});

	it('does not show a switch button with a single camera', async () => {
		mockMediaDevices([CAMERAS[0]]);

		render(BarcodeScanner, { props: { open: true } });

		await waitFor(() => {
			expect(window.localStorage.getItem(CAMERA_PREF_KEY)).toBe('cam-front');
		});
		expect(screen.queryByRole('button', { name: /switch camera/i })).not.toBeInTheDocument();
	});
});