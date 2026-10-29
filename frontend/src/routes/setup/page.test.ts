import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import SetupPage from './+page.svelte';

const mockOidcConfig = vi.fn();
const mockAppConfig = vi.fn();

vi.mock('#lib/api.js', () => ({
	api: {
		oidc: {
			config: (...args: unknown[]) => mockOidcConfig(...args)
		},
		app: {
			config: (...args: unknown[]) => mockAppConfig(...args)
		},
		auth: {
			setup: vi.fn(),
			csrf: vi.fn()
		},
		profile: {
			updateSettings: vi.fn()
		}
	}
}));

function mockConfig({ passwordLoginEnabled = true, oidcEnabled = true } = {}) {
	mockOidcConfig.mockResolvedValue({
		enabled: oidcEnabled,
		provider_id: oidcEnabled ? 'oidc' : null,
		provider_name: oidcEnabled ? 'Pocket ID' : null
	});
	mockAppConfig.mockResolvedValue({
		embed_enabled: true,
		dashboard_quote_enabled: true,
		thalia_cover_search_enabled: false,
		password_login_enabled: passwordLoginEnabled,
		trusted_proxy_auth_enabled: false
	});
}

describe('Setup page authentication warning', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('does not warn when password login is enabled', async () => {
		mockConfig();
		render(SetupPage);

		await waitFor(() => {
			expect(screen.getByText('Create Admin Account')).toBeInTheDocument();
		});
		expect(screen.queryByText(/Password login is disabled/i)).not.toBeInTheDocument();
	});

	it('warns to link single sign-on before logging out', async () => {
		mockConfig({ passwordLoginEnabled: false });
		render(SetupPage);

		await waitFor(() => {
			expect(screen.getByText(/Link your single sign-on account in Profile/i)).toBeInTheDocument();
		});
	});

	it('warns when password login is disabled and OIDC is unavailable', async () => {
		mockConfig({ passwordLoginEnabled: false, oidcEnabled: false });
		render(SetupPage);

		await waitFor(() => {
			expect(screen.getByText(/no single sign-on provider is configured/i)).toBeInTheDocument();
		});
	});

	it('warns when the login configuration cannot be checked', async () => {
		mockOidcConfig.mockRejectedValue(new Error('unavailable'));
		mockAppConfig.mockRejectedValue(new Error('unavailable'));
		render(SetupPage);

		await waitFor(() => {
			expect(screen.getByText(/Could not verify the password login setting/i)).toBeInTheDocument();
		});
	});
});
