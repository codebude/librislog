import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';
import CallbackPage from './+page.svelte';

const mockMe = vi.fn();
const mockCsrf = vi.fn();
const mockGetSettings = vi.fn();
const mockUpdateSettings = vi.fn();
const mockSetTimezone = vi.fn();

vi.mock('#lib/api.js', () => ({
	api: {
		auth: {
			me: (...args: unknown[]) => mockMe(...args),
			csrf: (...args: unknown[]) => mockCsrf(...args)
		},
		profile: {
			getSettings: (...args: unknown[]) => mockGetSettings(...args),
			updateSettings: (...args: unknown[]) => mockUpdateSettings(...args)
		}
	}
}));

vi.mock('#lib/stores/timezone.js', () => ({
	setTimezone: (...args: unknown[]) => mockSetTimezone(...args),
	getTimezone: () => 'Europe/Berlin',
	detectTimezone: () => 'Europe/Berlin',
	setQuoteServiceEnabled: () => {},
	isQuoteServiceEnabled: () => false
}));

function mockSettings(overrides: Record<string, unknown> = {}) {
	mockGetSettings.mockResolvedValue({
		user_id: 1,
		language: 'en',
		timezone: 'UTC',
		timezone_configured: false,
		theme: 'light',
		custom_theme: null,
		...overrides
	});
}

describe('OIDC callback timezone handling', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockMe.mockResolvedValue({ id: 1, email: 'test@example.com' });
		mockCsrf.mockResolvedValue({ csrf_token: 'token' });
		mockUpdateSettings.mockResolvedValue({});
	});

	it('auto-detects the timezone when the user has not configured one', async () => {
		mockSettings({ timezone: 'UTC', timezone_configured: false });
		render(CallbackPage);

		await waitFor(() => expect(mockSetTimezone).toHaveBeenCalled());

		expect(mockUpdateSettings).toHaveBeenCalledWith({
			timezone: 'Europe/Berlin',
			timezone_configured: false
		});
		expect(mockSetTimezone).toHaveBeenCalledWith('Europe/Berlin');
	});

	it('keeps an explicitly configured UTC timezone', async () => {
		mockSettings({ timezone: 'UTC', timezone_configured: true });
		render(CallbackPage);

		await waitFor(() => expect(mockSetTimezone).toHaveBeenCalled());

		expect(mockUpdateSettings).not.toHaveBeenCalled();
		expect(mockSetTimezone).toHaveBeenCalledWith('UTC');
	});

	it('keeps a custom timezone the user has configured', async () => {
		mockSettings({ timezone: 'America/New_York', timezone_configured: true });
		render(CallbackPage);

		await waitFor(() => expect(mockSetTimezone).toHaveBeenCalled());

		expect(mockUpdateSettings).not.toHaveBeenCalled();
		expect(mockSetTimezone).toHaveBeenCalledWith('America/New_York');
	});
});
