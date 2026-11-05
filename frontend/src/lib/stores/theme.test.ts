import { describe, it, expect, beforeEach } from 'vitest';
import {
	setThemeMode, getThemeMode, setCustomTheme, getCustomTheme,
	getEffectiveTheme, cycleTheme, loadThemeFromStorage, saveThemeToStorage,
	applyThemeToDocument, isDarkThemeName, isCatppuccinTheme, themeLabel, THEME_LABELS,
	DAISYUI_THEMES, CATPPUCCIN_THEMES
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

	it('contains the four catppuccin flavors', () => {
		expect(CATPPUCCIN_THEMES).toEqual(['latte', 'frappe', 'macchiato', 'mocha']);
		for (const flavor of CATPPUCCIN_THEMES) {
			expect(DAISYUI_THEMES).toContain(flavor);
		}
	});

	it('accepts and previews a catppuccin flavor', () => {
		setThemeMode('custom');
		setCustomTheme('mocha');
		expect(getCustomTheme()).toBe('mocha');
		expect(getEffectiveTheme()).toBe('mocha');
	});

	it('labels catppuccin flavors with a prefixed display name', () => {
		expect(themeLabel('latte')).toBe('Catppuccin Latte');
		expect(themeLabel('frappe')).toBe('Catppuccin Frappé');
		expect(themeLabel('macchiato')).toBe('Catppuccin Macchiato');
		expect(themeLabel('mocha')).toBe('Catppuccin Mocha');
		expect(themeLabel('dracula')).toBe('Dracula');
		expect(themeLabel('librislog')).toBe('Librislog');
	});

	it('classifies latte as light and the other flavors as dark', () => {
		expect(isDarkThemeName('latte')).toBe(false);
		expect(isDarkThemeName('frappe')).toBe(true);
		expect(isDarkThemeName('macchiato')).toBe(true);
		expect(isDarkThemeName('mocha')).toBe(true);
		expect(isDarkThemeName('dracula')).toBe(true);
		expect(isDarkThemeName('dark')).toBe(true);
		expect(isDarkThemeName('light')).toBe(false);
		expect(isDarkThemeName('librislog')).toBe(false);
	});

	it('recognises the catppuccin group without claiming other themes', () => {
		for (const flavor of CATPPUCCIN_THEMES) {
			expect(isCatppuccinTheme(flavor)).toBe(true);
		}
		expect(isCatppuccinTheme('dracula')).toBe(false);
		expect(isCatppuccinTheme('librislog')).toBe(false);
		expect(isCatppuccinTheme('toString')).toBe(false);
	});

	it('only labels themes that exist and never inherited object members', () => {
		for (const theme of Object.keys(THEME_LABELS)) {
			expect(DAISYUI_THEMES).toContain(theme);
		}
		expect(themeLabel('constructor')).toBe('Constructor');
		expect(typeof themeLabel('__proto__')).toBe('string');
		expect(themeLabel('__proto__')).not.toBe('[object Object]');
	});

	it('restores a catppuccin flavor from localStorage', () => {
		setCustomTheme('frappe');
		saveThemeToStorage();
		setCustomTheme('librislog');

		loadThemeFromStorage();
		expect(getCustomTheme()).toBe('frappe');
	});
});
