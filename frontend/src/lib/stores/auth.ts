import { writable } from 'svelte/store';
import type { User } from '#lib/types.js';

export const currentUser = writable<User | null>(null);
export const apiKey = writable<string | null>(null);
export const csrfToken = writable<string | null>(null);

export function loadAuthFromStorage() {
	apiKey.set(null);
}

export function setAuthKey(key: string | null) {
	apiKey.set(key);
}

const CHANNEL_NAME = 'librislog.auth';
const MESSAGE_LOGOUT = 'logout';
let authChannel: BroadcastChannel | null = null;

export function initAuthSync(onLogout: () => void) {
	if (typeof BroadcastChannel === 'undefined') return;
	if (authChannel) return;
	authChannel = new BroadcastChannel(CHANNEL_NAME);
	authChannel.onmessage = (event) => {
		if (event.data === MESSAGE_LOGOUT) {
			onLogout();
		}
	};
}

export function broadcastLogout() {
	if (!authChannel) return;
	authChannel.postMessage(MESSAGE_LOGOUT);
}
