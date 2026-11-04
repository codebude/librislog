import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { get } from 'svelte/store';

import {
	SIDEBAR_COLLAPSED_KEY,
	sidebarCollapsed,
	loadSidebarFromStorage,
	setSidebarCollapsed,
	toggleSidebar
} from './sidebar';

describe('sidebar store', () => {
	beforeEach(() => {
		localStorage.clear();
		loadSidebarFromStorage();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('defaults to expanded', () => {
		expect(get(sidebarCollapsed)).toBe(false);
	});

	it('toggles and persists the collapsed state', () => {
		toggleSidebar();
		expect(get(sidebarCollapsed)).toBe(true);
		expect(localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe('1');

		toggleSidebar();
		expect(get(sidebarCollapsed)).toBe(false);
		expect(localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe('0');
	});

	it('persists an explicit state', () => {
		setSidebarCollapsed(true);
		expect(get(sidebarCollapsed)).toBe(true);
		expect(localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe('1');
	});

	it('restores the stored state', () => {
		localStorage.setItem(SIDEBAR_COLLAPSED_KEY, '1');
		loadSidebarFromStorage();
		expect(get(sidebarCollapsed)).toBe(true);
	});

	it('treats missing or unreadable values as expanded', () => {
		for (const value of [null, '0', 'true', 'collapsed']) {
			toggleSidebar();
			expect(get(sidebarCollapsed)).toBe(true);
			if (value === null) {
				localStorage.removeItem(SIDEBAR_COLLAPSED_KEY);
			} else {
				localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value);
			}
			loadSidebarFromStorage();
			expect(get(sidebarCollapsed)).toBe(false);
		}
	});

	it('keeps the in-memory state when storage rejects writes', () => {
		vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
			throw new Error('storage blocked');
		});

		expect(() => setSidebarCollapsed(true)).not.toThrow();
		expect(get(sidebarCollapsed)).toBe(true);
	});

	it('keeps the in-memory state when storage rejects reads', () => {
		setSidebarCollapsed(true);
		vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
			throw new Error('storage blocked');
		});

		expect(() => loadSidebarFromStorage()).not.toThrow();
		expect(get(sidebarCollapsed)).toBe(true);
	});
});
