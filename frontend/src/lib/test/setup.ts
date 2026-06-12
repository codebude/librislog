import { vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import '$lib/chartjs/register';

// --- Polyfill crypto.randomUUID for happy-dom ---
if (typeof crypto !== 'undefined' && !crypto.randomUUID) {
	Object.defineProperty(crypto, 'randomUUID', {
		value: () => '00000000-0000-0000-0000-000000000000',
		configurable: true,
		writable: true
	});
}

// --- Mock svelte-i18n ($lib/i18n) ---
// Use a static translator based on English locale so tests can assert on real text.
const enTranslations: Record<string, unknown> = (await import('$lib/i18n/locales/en.json')).default;

function translate(key: string, options?: { values?: Record<string, unknown> }): string {
	const keys = key.split('.');
	let value: unknown = enTranslations;
	for (const k of keys) {
		value = (value as Record<string, unknown>)?.[k];
	}
	let result = typeof value === 'string' ? value : key;
	if (options?.values) {
		for (const [k, v] of Object.entries(options.values)) {
			result = result.replace(new RegExp(`{${k}}`, 'g'), String(v));
		}
	}
	return result;
}

vi.mock('$lib/i18n', async () => {
	const { readable } = await import('svelte/store');
	return {
		_: readable(translate),
		locale: readable('en'),
		setupI18n: () => Promise.resolve(),
		setLocale: () => {},
		getConfiguredDefaultLocale: () => 'en',
		SUPPORTED_LOCALES: ['en', 'de'] as const
	};
});

// --- Mock $app/stores and $app/navigation ---
vi.mock('$app/stores', async () => {
	const { readable } = await import('svelte/store');
	return {
		page: readable({
			url: new URL('http://localhost:5173/'),
			params: {},
			route: { id: null }
		}),
		navigating: readable(null)
	};
});

vi.mock('$app/navigation', () => ({
	goto: () => Promise.resolve(),
	beforeNavigate: () => {},
	afterNavigate: () => {},
	onNavigate: () => () => {}
}));

// --- Mock animal-avatar-generator (ESM resolution issues in vitest) ---
vi.mock('animal-avatar-generator', () => ({
	default: () => '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="#8a9aae"/></svg>'
}));

// --- Reset DOM between tests ---
import { cleanup } from '@testing-library/svelte';

afterEach(() => {
	cleanup();
	vi.clearAllMocks();
});
