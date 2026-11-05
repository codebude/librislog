export type ThemeMode = 'light' | 'dark' | 'custom';
import { invalidateColorCache } from '#lib/chartjs/theme.js';

const BUILTIN_THEMES = [
	'cupcake', 'bumblebee', 'emerald', 'corporate', 'synthwave', 'retro',
	'cyberpunk', 'valentine', 'halloween', 'garden', 'forest', 'aqua',
	'lofi', 'pastel', 'fantasy', 'wireframe', 'black', 'luxury', 'dracula',
	'cmyk', 'autumn', 'business', 'acid', 'lemonade', 'night', 'coffee',
	'winter', 'dim', 'nord', 'sunset', 'caramellatte', 'abyss', 'silk',
	'librislog'
] as const;

/** Catppuccin flavors, registered in app.css from the official daisyUI port. */
export const CATPPUCCIN_THEMES = ['latte', 'frappe', 'macchiato', 'mocha'] as const;

const DAISYUI_THEMES = [...BUILTIN_THEMES, ...CATPPUCCIN_THEMES] as const;

export type DaisyUITheme = (typeof DAISYUI_THEMES)[number];

/** Whether a theme name belongs to the Catppuccin group in the picker. */
export function isCatppuccinTheme(theme: string): boolean {
	return (CATPPUCCIN_THEMES as readonly string[]).includes(theme);
}

/** Display names for themes whose raw daisyUI name is not self-explanatory. */
export const THEME_LABELS: Partial<Record<DaisyUITheme, string>> = {
	latte: 'Catppuccin Latte',
	frappe: 'Catppuccin Frappé',
	macchiato: 'Catppuccin Macchiato',
	mocha: 'Catppuccin Mocha'
};

/** Human-readable label for a theme name, falling back to a capitalised name. */
export function themeLabel(theme: string): string {
	return Object.hasOwn(THEME_LABELS, theme)
		? (THEME_LABELS[theme as DaisyUITheme] as string)
		: theme.charAt(0).toUpperCase() + theme.slice(1);
}

export const THEME_MODE_KEY = 'librislog_theme_mode';
export const CUSTOM_THEME_KEY = 'librislog_custom_theme';

let _themeMode: ThemeMode = 'custom';
let _customTheme: DaisyUITheme | null = 'librislog';
let _version = 0;

export function getThemeMode(): ThemeMode {
	return _themeMode;
}

export function setThemeMode(mode: ThemeMode) {
	_themeMode = mode;
}

export function getCustomTheme(): DaisyUITheme | null {
	return _customTheme;
}

export function getThemeVersion(): number {
	return _version;
}

export function setCustomTheme(theme: DaisyUITheme | string | null) {
	if (theme && DAISYUI_THEMES.includes(theme as DaisyUITheme)) {
		_customTheme = theme as DaisyUITheme;
	} else {
		_customTheme = null;
	}
	_version++;
}

const VALID_MODES: ThemeMode[] = ['light', 'dark', 'custom'];

export function sanitizeThemeMode(raw: string): ThemeMode {
	return VALID_MODES.includes(raw as ThemeMode) ? (raw as ThemeMode) : 'custom';
}

export function getEffectiveTheme(): string {
	if (_themeMode === 'custom' && _customTheme) {
		return _customTheme;
	}
	if (_themeMode === 'custom') {
		return 'librislog';
	}
	return _themeMode;
}

export function cycleTheme(): ThemeMode {
	const order: ThemeMode[] = ['custom', 'light', 'dark'];
	const idx = order.indexOf(_themeMode);
	_themeMode = order[(idx + 1) % order.length];
	return _themeMode;
}

export function loadThemeFromStorage() {
	try {
		const storedMode = localStorage.getItem(THEME_MODE_KEY) as ThemeMode | null;
		if (storedMode && ['light', 'dark', 'custom'].includes(storedMode)) {
			_themeMode = storedMode;
		}
		const storedCustom = localStorage.getItem(CUSTOM_THEME_KEY);
		if (storedCustom && DAISYUI_THEMES.includes(storedCustom as DaisyUITheme)) {
			_customTheme = storedCustom as DaisyUITheme;
		}
	} catch {
		// localStorage unavailable
	}
}

export function saveThemeToStorage() {
	try {
		localStorage.setItem(THEME_MODE_KEY, _themeMode);
		if (_customTheme) {
			localStorage.setItem(CUSTOM_THEME_KEY, _customTheme);
		} else {
			localStorage.removeItem(CUSTOM_THEME_KEY);
		}
	} catch {
		// localStorage unavailable
	}
}

import { writable } from 'svelte/store';

export const themeApplyCount = writable(0);

const DARK_THEMES: readonly string[] = ['synthwave', 'halloween', 'forest', 'dracula', 'black', 'luxury', 'night', 'coffee', 'dim', 'abyss', 'sunset', 'business', 'frappe', 'macchiato', 'mocha'];

/** Fallback classification for custom daisyUI theme names (`dark` included). */
export function isDarkThemeName(theme: string): boolean {
	return theme === 'dark' || DARK_THEMES.includes(theme);
}

/**
 * Resolve whether the applied theme is dark from the theme's own
 * `color-scheme`, so newly added themes need no entry in DARK_THEMES.
 */
function currentThemeIsDark(): boolean {
	if (_themeMode === 'dark') return true;
	if (_themeMode !== 'custom') return false;
	if (typeof document !== 'undefined' && typeof getComputedStyle === 'function') {
		const scheme = getComputedStyle(document.documentElement).getPropertyValue('color-scheme').trim();
		if (scheme === 'dark' || scheme === 'light') return scheme === 'dark';
	}
	return isDarkThemeName(getEffectiveTheme());
}

function updateFavicon() {
	const isDark = currentThemeIsDark();
	const href = isDark ? '/favicon/favicon-dark.svg' : '/favicon/favicon.svg';
	const link = document.querySelector('link[rel="icon"][type="image/svg+xml"]') as HTMLLinkElement | null;
	if (link && link.href !== new URL(href, location.href).href) {
		link.href = href;
	}
}

export function applyThemeToDocument() {
	const effective = getEffectiveTheme();
	document.documentElement.dataset.theme = effective;
	invalidateColorCache();
	updateFavicon();
	themeApplyCount.update(n => n + 1);
}

export function getThemeIcon(): string {
	switch (_themeMode) {
		case 'light': return 'Sun';
		case 'dark': return 'Moon';
		case 'custom': return 'Palette';
	}
	return 'Sun';
}

/** Restore-point for profile page so the preview can be reverted on navigation */
let _restorePoint: { mode: ThemeMode; custom: DaisyUITheme | null } | null = null;

export function saveRestorePoint(): void {
	_restorePoint = { mode: _themeMode, custom: _customTheme };
}

export function clearRestorePoint(): void {
	_restorePoint = null;
}

export function restoreFromPoint(): boolean {
	if (!_restorePoint) return false;
	_themeMode = _restorePoint.mode;
	_customTheme = _restorePoint.custom;
	_restorePoint = null;
	return true;
}

export { DAISYUI_THEMES };
