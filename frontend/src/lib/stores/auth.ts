import { writable } from 'svelte/store';
import type { User } from '$lib/types';

const API_KEY_STORAGE = 'librislog.api_key';

export const currentUser = writable<User | null>(null);
export const apiKey = writable<string | null>(null);

export function loadAuthFromStorage() {
	if (typeof sessionStorage === 'undefined') return;
	const key = sessionStorage.getItem(API_KEY_STORAGE);
	if (key) apiKey.set(key);
}

export function setAuthKey(key: string | null) {
	apiKey.set(key);
	if (typeof sessionStorage === 'undefined') return;
	if (key) {
		sessionStorage.setItem(API_KEY_STORAGE, key);
	} else {
		sessionStorage.removeItem(API_KEY_STORAGE);
	}
}
