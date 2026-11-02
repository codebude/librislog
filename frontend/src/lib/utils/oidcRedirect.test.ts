import { describe, it, expect } from 'vitest';
import { shouldAutoRedirectToOidc } from './oidcRedirect.js';

const base = {
	oidcEnabled: true,
	oidcAutoRedirect: true,
	passwordLoginEnabled: false,
	hasOidcError: false
};

describe('shouldAutoRedirectToOidc', () => {
	it('redirects when OIDC is the only sign-in method and auto-redirect is on', () => {
		expect(shouldAutoRedirectToOidc(base)).toBe(true);
	});

	it('does not redirect while password login is enabled', () => {
		expect(shouldAutoRedirectToOidc({ ...base, passwordLoginEnabled: true })).toBe(false);
	});

	it('does not redirect while the login configuration is still loading', () => {
		expect(shouldAutoRedirectToOidc({ ...base, passwordLoginEnabled: null })).toBe(false);
	});

	it('does not redirect when OIDC is disabled', () => {
		expect(shouldAutoRedirectToOidc({ ...base, oidcEnabled: false })).toBe(false);
	});

	it('does not redirect when auto-redirect is disabled', () => {
		expect(shouldAutoRedirectToOidc({ ...base, oidcAutoRedirect: false })).toBe(false);
	});

	it('does not redirect after an OIDC error', () => {
		expect(shouldAutoRedirectToOidc({ ...base, hasOidcError: true })).toBe(false);
	});
});
