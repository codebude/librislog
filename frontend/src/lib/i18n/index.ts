import { addMessages, init, locale, register, waitLocale, _ } from 'svelte-i18n';
import { api } from '$lib/api';

export const SUPPORTED_LOCALES = ['en', 'de', 'zh', 'es', 'fr'] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

const DEFAULT_LOCALE: AppLocale = 'en';
const LOCALE_STORAGE_KEY = 'librislog_locale';

const envLocale = (import.meta.env.PUBLIC_DEFAULT_LOCALE as string | undefined)?.toLowerCase();
const configuredDefaultLocale: AppLocale = isSupportedLocale(envLocale) ? envLocale : DEFAULT_LOCALE;

register('en', () => import('./locales/en.json'));
register('de', () => import('./locales/de.json'));
register('zh', () => import('./locales/zh.json'));
register('es', () => import('./locales/es.json'));
register('fr', () => import('./locales/fr.json'));

addMessages('en', {});

let initialized = false;

function isSupportedLocale(value: string | null | undefined): value is AppLocale {
	return !!value && (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

function loadStoredLocale(): AppLocale | null {
	try {
		const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
		if (isSupportedLocale(stored)) return stored;
	} catch {
		// localStorage unavailable (SSR, private mode, etc.)
	}
	return null;
}

function storeLocale(value: AppLocale) {
	try {
		localStorage.setItem(LOCALE_STORAGE_KEY, value);
	} catch {
		// localStorage unavailable
	}
}

export async function setupI18n() {
	if (initialized) {
		await waitLocale();
		return;
	}

	let initialLocale = configuredDefaultLocale;
	try {
		const settings = await api.profile.getSettings();
		if (isSupportedLocale(settings.language)) {
			initialLocale = settings.language;
		}
	} catch {
		const stored = loadStoredLocale();
		if (stored) {
			initialLocale = stored;
		}
	}

	init({
		fallbackLocale: 'en',
		initialLocale
	});

	initialized = true;

	locale.subscribe((value) => {
		if (isSupportedLocale(value)) {
			storeLocale(value);
		}
	});

	await waitLocale();
}

export function setLocale(nextLocale: AppLocale) {
	locale.set(nextLocale);
}

export function getConfiguredDefaultLocale() {
	return configuredDefaultLocale;
}

export { _, locale };
