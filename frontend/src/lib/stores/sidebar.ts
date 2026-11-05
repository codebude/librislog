import { get, writable, type Readable } from 'svelte/store';

export const SIDEBAR_COLLAPSED_KEY = 'librislog_sidebar_collapsed';

const state = writable(false);

/** Whether the desktop sidebar is collapsed to an icon rail. */
export const sidebarCollapsed: Readable<boolean> = { subscribe: state.subscribe };

function persist(value: boolean): void {
	try {
		localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? '1' : '0');
	} catch {
		// localStorage unavailable
	}
}

/** Restore the collapsed state saved for this browser. */
export function loadSidebarFromStorage(): void {
	try {
		state.set(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1');
	} catch {
		// localStorage unavailable
	}
}

export function setSidebarCollapsed(value: boolean): void {
	state.set(value);
	persist(value);
}

export function toggleSidebar(): void {
	const next = !get(state);
	state.set(next);
	persist(next);
}
