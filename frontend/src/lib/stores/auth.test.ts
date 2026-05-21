import { describe, it, expect, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { currentUser, apiKey, csrfToken, loadAuthFromStorage, setAuthKey } from './auth';

describe('auth stores', () => {
	beforeEach(() => {
		currentUser.set(null);
		apiKey.set(null);
		csrfToken.set(null);
	});

	it('currentUser store holds null by default', () => {
		expect(get(currentUser)).toBeNull();
	});

	it('apiKey store holds null by default', () => {
		expect(get(apiKey)).toBeNull();
	});

	it('csrfToken store holds null by default', () => {
		expect(get(csrfToken)).toBeNull();
	});

	it('setAuthKey updates apiKey', () => {
		setAuthKey('my-key');
		expect(get(apiKey)).toBe('my-key');
		setAuthKey(null);
		expect(get(apiKey)).toBeNull();
	});

	it('loadAuthFromStorage clears apiKey', () => {
		apiKey.set('existing');
		loadAuthFromStorage();
		expect(get(apiKey)).toBeNull();
	});
});

describe('auth sync', () => {
	let channelInstance: any = null;
	let originalBroadcastChannel: any;

	beforeEach(() => {
		vi.resetModules();
		originalBroadcastChannel = globalThis.BroadcastChannel;
		class MockBroadcastChannel {
			name: string;
			onmessage: ((event: MessageEvent) => void) | null = null;
			constructor(name: string) {
				this.name = name;
				channelInstance = this;
			}
			postMessage(data: unknown) {
				if (this.onmessage) {
					this.onmessage(new MessageEvent('message', { data }));
				}
			}
		}
		// @ts-expect-error mock
		globalThis.BroadcastChannel = MockBroadcastChannel;
	});

	afterEach(() => {
		globalThis.BroadcastChannel = originalBroadcastChannel;
		channelInstance = null;
	});

	it('initAuthSync creates channel and listens for logout', async () => {
		const { initAuthSync } = await import('./auth');
		const onLogout = vi.fn();
		initAuthSync(onLogout);
		expect(channelInstance).toBeTruthy();
		expect(channelInstance.name).toBe('librislog.auth');
		channelInstance.postMessage('logout');
		expect(onLogout).toHaveBeenCalledOnce();
	});

	it('initAuthSync does nothing if BroadcastChannel undefined', async () => {
		// @ts-expect-error mock
		globalThis.BroadcastChannel = undefined;
		const { initAuthSync } = await import('./auth');
		const onLogout = vi.fn();
		initAuthSync(onLogout);
		expect(channelInstance).toBeNull();
	});

	it('broadcastLogout sends message', async () => {
		const { initAuthSync, broadcastLogout } = await import('./auth');
		const onLogout = vi.fn();
		initAuthSync(onLogout);
		broadcastLogout();
		expect(onLogout).toHaveBeenCalledOnce();
	});

	it('broadcastLogout does nothing if channel not initialized', async () => {
		const { broadcastLogout } = await import('./auth');
		expect(() => broadcastLogout()).not.toThrow();
	});

	it('initAuthSync returns early if already initialized', async () => {
		const { initAuthSync } = await import('./auth');
		const onLogout1 = vi.fn();
		const onLogout2 = vi.fn();
		initAuthSync(onLogout1);
		// Second call should return early, not create a new channel
		initAuthSync(onLogout2);
		// Only the first listener should be registered
		channelInstance.postMessage('logout');
		expect(onLogout1).toHaveBeenCalledOnce();
		expect(onLogout2).not.toHaveBeenCalled();
	});
});
