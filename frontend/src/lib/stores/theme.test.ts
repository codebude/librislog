import { describe, it, expect, beforeEach } from 'vitest';
import {
	setThemeMode, getThemeMode, setCustomTheme, getCustomTheme,
	getEffectiveTheme, cycleTheme, loadThemeFromStorage, saveThemeToStorage,
	applyThemeToDocument, DAISYUI_THEMES
} from './theme';

describe('theme store', () => {
	beforeEach(() => {
		setThemeMode('light');
		setCustomTheme(null);
		localStorage.clear();
	});

	it('defaults to light mode', () => {
		expect(getThemeMode()).toBe('light');
		expect(getEffectiveTheme()).toBe('light');
	});

	it('cycles through modes', () => {
		expect(cycleTheme()).toBe('dark');
		expect(cycleTheme()).toBe('custom');
		expect(cycleTheme()).toBe('light');
	});

	it('uses custom theme when in custom mode', () => {
		setThemeMode('custom');
		setCustomTheme('dracula');
		expect(getEffectiveTheme()).toBe('dracula');
	});

	it('falls back to dracula when custom theme is not set', () => {
		setThemeMode('custom');
		setCustomTheme(null);
		expect(getEffectiveTheme()).toBe('dracula');
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
		expect(DAISYUI_THEMES).not.toContain('light');
		expect(DAISYUI_THEMES).not.toContain('dark');
	});
});
