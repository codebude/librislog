export interface OidcAutoRedirectOptions {
	oidcEnabled: boolean;
	oidcAutoRedirect: boolean;
	passwordLoginEnabled: boolean | null;
	hasOidcError: boolean;
}

/**
 * Automatic OIDC redirect is only safe when OIDC is the only usable sign-in
 * method and the previous attempt did not already fail with an error.
 */
export function shouldAutoRedirectToOidc(options: OidcAutoRedirectOptions): boolean {
	return (
		options.oidcEnabled &&
		options.oidcAutoRedirect &&
		options.passwordLoginEnabled === false &&
		!options.hasOidcError
	);
}
