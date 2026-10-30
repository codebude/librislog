import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import LoginPage from './+page.svelte';

const mockOidcConfig = vi.fn();
const mockAppConfig = vi.fn();

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
			login: vi.fn(),
			csrf: vi.fn(),
			forgotPassword: vi.fn()
		},
		profile: {
			getSettings: vi.fn(),
			updateSettings: vi.fn()
		}
	}
}));

function mockConfig({
	passwordLoginEnabled = true,
	oidcEnabled = true,
	trustedProxyAuthEnabled = false,
	autoRedirect = false
} = {}) {
	mockOidcConfig.mockResolvedValue({
		enabled: oidcEnabled,
		provider_id: oidcEnabled ? 'oidc' : null,
		provider_name: oidcEnabled ? 'Pocket ID' : null,
		auto_redirect: autoRedirect
	});
	mockAppConfig.mockResolvedValue({
		embed_enabled: true,
		dashboard_quote_enabled: true,
		thalia_cover_search_enabled: false,
		password_login_enabled: passwordLoginEnabled,
		trusted_proxy_auth_enabled: trustedProxyAuthEnabled
	});
}

describe('Login page authentication methods', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows the password form when password login is enabled', async () => {
		mockConfig();
		render(LoginPage);

		await waitFor(() => {
			expect(screen.getAllByLabelText('Email').length).toBeGreaterThan(0);
		});
		expect(screen.getByLabelText('Password')).toBeInTheDocument();
		expect(screen.getByText('Forgot password?')).toBeInTheDocument();
		expect(screen.getByText('Continue with Pocket ID')).toBeInTheDocument();
	});

	it('hides the password form and forgot-password link when disabled', async () => {
		mockConfig({ passwordLoginEnabled: false });
		render(LoginPage);

		await waitFor(() => {
			expect(screen.getByText('Continue with Pocket ID')).toBeInTheDocument();
		});
		expect(screen.queryByLabelText('Email')).not.toBeInTheDocument();
		expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
		expect(screen.queryByText('Forgot password?')).not.toBeInTheDocument();
		expect(screen.getByText(/Password login is disabled/i)).toBeInTheDocument();
	});

	it('warns when no login method is available', async () => {
		mockConfig({ passwordLoginEnabled: false, oidcEnabled: false });
		render(LoginPage);

		await waitFor(() => {
			expect(screen.getByText(/No sign-in method is currently configured/i)).toBeInTheDocument();
		});
	});

	it('shows an error instead of the form when config cannot be loaded', async () => {
		mockOidcConfig.mockResolvedValue({
			enabled: false,
			provider_id: null,
			provider_name: null,
			auto_redirect: false
		});
		mockAppConfig.mockRejectedValue(new Error('config unavailable'));
		render(LoginPage);

		await waitFor(() => {
			expect(screen.getByText(/Could not load the sign-in configuration/i)).toBeInTheDocument();
		});
		expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
	});

	it('auto-redirects to OIDC when password login is disabled', async () => {
		mockConfig({ passwordLoginEnabled: false, oidcEnabled: true, autoRedirect: true });
		const assign = vi.spyOn(window.location, 'assign').mockImplementation(() => {});
		render(LoginPage);

		await waitFor(() => {
			expect(assign).toHaveBeenCalledWith('/api/oidc/login');
		});
		assign.mockRestore();
	});

	it('does not auto-redirect when password login is enabled', async () => {
		mockConfig({ passwordLoginEnabled: true, oidcEnabled: true, autoRedirect: true });
		const assign = vi.spyOn(window.location, 'assign').mockImplementation(() => {});
		render(LoginPage);

		await waitFor(() => {
			expect(screen.getByText('Continue with Pocket ID')).toBeInTheDocument();
		});
		expect(assign).not.toHaveBeenCalled();
		assign.mockRestore();
	});

	it('does not auto-redirect after an OIDC error', async () => {
		window.history.replaceState({}, '', '/login?oidc_error=OIDC%20failed');
		mockConfig({ passwordLoginEnabled: false, oidcEnabled: true, autoRedirect: true });
		const assign = vi.spyOn(window.location, 'assign').mockImplementation(() => {});
		render(LoginPage);

		await waitFor(() => {
			expect(screen.getByText(/OIDC failed/i)).toBeInTheDocument();
		});
		expect(assign).not.toHaveBeenCalled();
		assign.mockRestore();
		window.history.replaceState({}, '', '/login');
	});

	it('mentions proxy-managed access when proxy auth is enabled', async () => {
		mockConfig({ passwordLoginEnabled: false, oidcEnabled: false, trustedProxyAuthEnabled: true });
		render(LoginPage);

		await waitFor(() => {
			expect(screen.getByText(/managed by your reverse proxy/i)).toBeInTheDocument();
		});
		expect(screen.queryByText(/No sign-in method is currently configured/i)).not.toBeInTheDocument();
	});
});
