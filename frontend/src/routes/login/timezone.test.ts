import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import LoginPage from './+page.svelte';

const mockOidcConfig = vi.fn();
const mockAppConfig = vi.fn();
const mockLogin = vi.fn();
const mockCsrf = vi.fn();
const mockGetSettings = vi.fn();
const mockUpdateSettings = vi.fn();
const mockSetTimezone = vi.fn();

vi.mock('#lib/api.js', () => ({
	api: {
		oidc: {
			config: (...args: unknown[]) => mockOidcConfig(...args),
			loginUrl: () => '/api/oidc/login'
		},
		app: {
			config: (...args: unknown[]) => mockAppConfig(...args)
		},
		auth: {
			login: (...args: unknown[]) => mockLogin(...args),
			csrf: (...args: unknown[]) => mockCsrf(...args),
			forgotPassword: vi.fn()
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

function mockConfig() {
	mockOidcConfig.mockResolvedValue({
		enabled: true,
		provider_id: 'oidc',
		provider_name: 'Pocket ID',
		auto_redirect: false
	});
	mockAppConfig.mockResolvedValue({
		embed_enabled: true,
		dashboard_quote_enabled: true,
		thalia_cover_search_enabled: false,
		password_login_enabled: true,
		trusted_proxy_auth_enabled: false
	});
}

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

async function prepareLogin(settings: Record<string, unknown> = {}) {
	mockConfig();
	mockLogin.mockResolvedValue({ user: { id: 1 } });
	mockCsrf.mockResolvedValue({ csrf_token: 'token' });
	mockSettings(settings);
	mockUpdateSettings.mockResolvedValue({});
	render(LoginPage);
}

async function submitLogin() {
	await waitFor(() => {
		expect(screen.getAllByLabelText('Email').length).toBeGreaterThan(0);
	});
	await fireEvent.input(screen.getAllByLabelText('Email')[0], {
		target: { value: 'test@example.com' }
	});
	await fireEvent.input(screen.getByLabelText('Password'), {
		target: { value: 'secret' }
	});
	await fireEvent.click(screen.getByRole('button', { name: 'Login' }));
}

describe('Login page timezone handling', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('auto-detects the timezone when the user has not configured one', async () => {
		await prepareLogin({ timezone: 'UTC', timezone_configured: false });
		await submitLogin();
		await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalled());

		expect(mockUpdateSettings).toHaveBeenCalledWith({
			timezone: 'Europe/Berlin',
			timezone_configured: false
		});
		expect(mockSetTimezone).toHaveBeenCalledWith('Europe/Berlin');
	});

	it('keeps a custom timezone the user has configured', async () => {
		await prepareLogin({ timezone: 'America/New_York', timezone_configured: true });
		await submitLogin();
		await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalled());

		expect(mockUpdateSettings.mock.calls[0][0]).not.toHaveProperty('timezone');
		expect(mockUpdateSettings.mock.calls[0][0]).not.toHaveProperty('timezone_configured');
		expect(mockSetTimezone).toHaveBeenCalledWith('America/New_York');
	});

	it('keeps an explicitly configured UTC timezone', async () => {
		await prepareLogin({ timezone: 'UTC', timezone_configured: true });
		await submitLogin();
		await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalled());

		expect(mockUpdateSettings.mock.calls[0][0]).not.toHaveProperty('timezone');
		expect(mockUpdateSettings.mock.calls[0][0]).not.toHaveProperty('timezone_configured');
		expect(mockSetTimezone).toHaveBeenCalledWith('UTC');
	});

	it('falls back to the UTC check when the backend omits the flag', async () => {
		await prepareLogin({ timezone: 'UTC', timezone_configured: undefined });
		await submitLogin();
		await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalled());

		expect(mockUpdateSettings).toHaveBeenCalledWith({
			timezone: 'Europe/Berlin',
			timezone_configured: false
		});
		expect(mockSetTimezone).toHaveBeenCalledWith('Europe/Berlin');
	});

	it('keeps a custom timezone when the backend omits the flag', async () => {
		await prepareLogin({ timezone: 'America/New_York', timezone_configured: undefined });
		await submitLogin();
		await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalled());

		expect(mockUpdateSettings.mock.calls[0][0]).not.toHaveProperty('timezone');
		expect(mockUpdateSettings.mock.calls[0][0]).not.toHaveProperty('timezone_configured');
		expect(mockSetTimezone).toHaveBeenCalledWith('America/New_York');
	});
});
