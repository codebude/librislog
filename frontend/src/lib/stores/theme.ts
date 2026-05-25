export type ThemeMode = 'light' | 'dark' | 'custom';
import { invalidateColorCache } from '$lib/chartjs/theme';

const DAISYUI_THEMES = [
	'cupcake', 'bumblebee', 'emerald', 'corporate', 'synthwave', 'retro',
	'cyberpunk', 'valentine', 'halloween', 'garden', 'forest', 'aqua',
	'lofi', 'pastel', 'fantasy', 'wireframe', 'black', 'luxury', 'dracula',
	'cmyk', 'autumn', 'business', 'acid', 'lemonade', 'night', 'coffee',
	'winter', 'dim', 'nord', 'sunset', 'caramellatte', 'abyss', 'silk',
	'librislog'
] as const;

export type DaisyUITheme = (typeof DAISYUI_THEMES)[number];

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

const DARK_THEMES: readonly string[] = ['synthwave', 'halloween', 'forest', 'dracula', 'black', 'luxury', 'night', 'coffee', 'dim', 'abyss', 'sunset', 'business'];

function updateFavicon() {
	const effective = getEffectiveTheme();
	const isDark = _themeMode === 'dark' || (_themeMode === 'custom' && DARK_THEMES.includes(effective));
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
