import { get, writable } from 'svelte/store';
import type { UserSettings } from '$lib/types';
import { api } from '$lib/api';

export const userSettings = writable<UserSettings | null>(null);

let pendingLoad: Promise<UserSettings> | null = null;

export function loadUserSettings(force = false): Promise<UserSettings> {
	const current = get(userSettings);
	if (!force && current) return Promise.resolve(current);
	if (!force && pendingLoad) return pendingLoad;
	if (!api.profile?.getSettings) {
		return Promise.reject(new Error('User settings are unavailable'));
	}

	pendingLoad = api.profile.getSettings().then((settings) => {
		userSettings.set(settings);
		return settings;
	}).finally(() => {
		pendingLoad = null;
	});
	return pendingLoad;
}

export function setUserSettings(settings: UserSettings): void {
	userSettings.set(settings);
}
