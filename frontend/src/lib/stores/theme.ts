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

let _themeMode: ThemeMode = 'light';
let _customTheme: DaisyUITheme | null = null;
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
	return VALID_MODES.includes(raw as ThemeMode) ? (raw as ThemeMode) : 'light';
}

export function getEffectiveTheme(): string {
	if (_themeMode === 'custom' && _customTheme) {
		return _customTheme;
	}
	if (_themeMode === 'custom') {
		return 'dracula';
	}
	return _themeMode;
}

export function cycleTheme(): ThemeMode {
	const order: ThemeMode[] = ['light', 'dark', 'custom'];
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

export function applyThemeToDocument() {
	const effective = getEffectiveTheme();
	document.documentElement.dataset.theme = effective;
	invalidateColorCache();
}

export function getThemeIcon(): string {
	switch (_themeMode) {
		case 'light': return 'Sun';
		case 'dark': return 'Moon';
		case 'custom': return 'Palette';
	}
	return 'Sun';
}

export { DAISYUI_THEMES };
