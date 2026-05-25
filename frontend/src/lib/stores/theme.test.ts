import { describe, it, expect, beforeEach } from 'vitest';
import {
	setThemeMode, getThemeMode, setCustomTheme, getCustomTheme,
	getEffectiveTheme, cycleTheme, loadThemeFromStorage, saveThemeToStorage,
	applyThemeToDocument, DAISYUI_THEMES
} from './theme';

describe('theme store', () => {
	beforeEach(() => {
		setThemeMode('custom');
		setCustomTheme('librislog');
		localStorage.clear();
	});

	it('defaults to custom mode with librislog theme', () => {
		expect(getThemeMode()).toBe('custom');
		expect(getEffectiveTheme()).toBe('librislog');
	});

	it('cycles through modes starting from custom', () => {
		expect(cycleTheme()).toBe('light');
		expect(cycleTheme()).toBe('dark');
		expect(cycleTheme()).toBe('custom');
	});

	it('uses custom theme when in custom mode', () => {
		setThemeMode('custom');
		setCustomTheme('dracula');
		expect(getEffectiveTheme()).toBe('dracula');
	});

	it('falls back to librislog when custom theme is not set', () => {
		setThemeMode('custom');
		setCustomTheme(null);
		expect(getEffectiveTheme()).toBe('librislog');
	});

	it('rejects invalid custom themes', () => {
		setCustomTheme('invalid');
		expect(getCustomTheme()).toBeNull();
	});

	it('persists to and loads from localStorage', () => {
		setThemeMode('dark');
		setCustomTheme('nord');
		saveThemeToStorage();

		setThemeMode('light');
		setCustomTheme(null);

		loadThemeFromStorage();
		expect(getThemeMode()).toBe('dark');
		expect(getCustomTheme()).toBe('nord');
	});

	it('applyThemeToDocument sets data-theme on html', () => {
		setThemeMode('dark');
		applyThemeToDocument();
		expect(document.documentElement.dataset.theme).toBe('dark');
	});

	it('contains all expected daisyui themes', () => {
		expect(DAISYUI_THEMES).toContain('dracula');
		expect(DAISYUI_THEMES).toContain('nord');
		expect(DAISYUI_THEMES).toContain('sunset');
		expect(DAISYUI_THEMES).toContain('librislog');
		expect(DAISYUI_THEMES).not.toContain('light');
		expect(DAISYUI_THEMES).not.toContain('dark');
	});
});
