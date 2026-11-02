<script lang="ts">
	import Alert from '#lib/components/Alert.svelte';
	import Logo from '#lib/components/Logo.svelte';
	import { goto } from '$app/navigation';
	import { api } from '#lib/api.js';
	import { currentUser, csrfToken } from '#lib/stores/auth.js';
	import { _, locale, setLocale, SUPPORTED_LOCALES, type AppLocale } from '#lib/i18n/index.js';
	import { setTimezone, detectTimezone } from '#lib/stores/timezone.js';
	import { shouldAutoRedirectToOidc } from '#lib/utils/oidcRedirect.js';
	import {
		setThemeMode, setCustomTheme, applyThemeToDocument, saveThemeToStorage,
		sanitizeThemeMode, THEME_MODE_KEY, CUSTOM_THEME_KEY
	} from '#lib/stores/theme.js';

	let email = $state('');
	let password = $state('');
	let selectedLanguage = $state<AppLocale>('en');
	let languageChanged = $state(false);
	let loading = $state(false);
	let error = $state('');
	let oidcEnabled = $state(false);
	let oidcProviderName = $state('Single Sign-On');
	let oidcAutoRedirect = $state(false);
	let autoRedirectStarted = false;
	let passwordLoginEnabled = $state<boolean | null>(null);
	let trustedProxyAuthEnabled = $state(false);
	let configError = $state(false);

	$effect(() => {
		void (async () => {
			const [oidcResult, appResult] = await Promise.allSettled([
				api.oidc.config(),
				api.app.config()
			]);
			if (oidcResult.status === 'fulfilled') {
				oidcEnabled = oidcResult.value.enabled;
				oidcProviderName = oidcResult.value.provider_name ?? 'Single Sign-On';
				oidcAutoRedirect = oidcResult.value.auto_redirect ?? false;
			} else {
				oidcEnabled = false;
			}
			if (appResult.status === 'fulfilled') {
				passwordLoginEnabled = appResult.value.password_login_enabled;
				trustedProxyAuthEnabled = appResult.value.trusted_proxy_auth_enabled;
			} else {
				configError = true;
			}
			if (oidcResult.status === 'fulfilled' && appResult.status === 'fulfilled') {
				maybeAutoRedirectToOidc();
			}
		})();
	});

	$effect(() => {
		if (SUPPORTED_LOCALES.includes($locale as AppLocale)) {
			selectedLanguage = $locale as AppLocale;
		}
	});

	function onLanguageChange(event: Event) {
		const next = (event.currentTarget as HTMLSelectElement).value as AppLocale;
		if (!SUPPORTED_LOCALES.includes(next)) return;
		selectedLanguage = next;
		languageChanged = true;
		setLocale(next);
	}

	let forgotEmail = $state('');
	let forgotLoading = $state(false);
	let forgotSent = $state(false);
	let forgotError = $state('');
	let forgotDialog: HTMLDialogElement | undefined = $state();

	async function submit() {
		error = '';
		loading = true;
		try {
			const result = await api.auth.login({ email, password });
			currentUser.set(result.user);
			const csrf = await api.auth.csrf();
			csrfToken.set(csrf.csrf_token);
			const settings = await api.profile.getSettings();
			const detected = detectTimezone();
			const update: { language?: string; timezone?: string } = {};
			if (languageChanged) update.language = selectedLanguage;
			if (settings.timezone === 'UTC') update.timezone = detected;
			await api.profile.updateSettings(update);
			setTimezone(settings.timezone === 'UTC' ? detected : settings.timezone);

			if (settings.theme) {
				const dbMode = sanitizeThemeMode(settings.theme);
				const storedMode = localStorage.getItem(THEME_MODE_KEY);
				const storedCustom = localStorage.getItem(CUSTOM_THEME_KEY);
				if (!storedMode || storedMode !== dbMode || storedCustom !== (settings.custom_theme ?? null)) {
					setThemeMode(dbMode);
					setCustomTheme(settings.custom_theme);
					applyThemeToDocument();
					saveThemeToStorage();
				}
			}
			const localeToSet: AppLocale = languageChanged
				? selectedLanguage
				: SUPPORTED_LOCALES.includes(settings.language as AppLocale)
					? (settings.language as AppLocale)
					: 'en';
			setLocale(localeToSet);
			await goto('/');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $_('auth.loginFailed');
		} finally {
			loading = false;
		}
	}

	async function forgotSubmit() {
		forgotError = '';
		forgotSent = false;
		forgotLoading = true;
		try {
			await api.auth.forgotPassword({ email: forgotEmail, locale: selectedLanguage });
			forgotSent = true;
		} catch (e: unknown) {
			forgotError = e instanceof Error ? e.message : $_('auth.forgotError');
		} finally {
			forgotLoading = false;
		}
	}

	function openForgotDialog() {
		forgotEmail = email;
		forgotSent = false;
		forgotError = '';
		forgotDialog?.showModal();
	}

	function maybeAutoRedirectToOidc() {
		if (autoRedirectStarted) return;
		const hasOidcError = new URLSearchParams(window.location.search).has('oidc_error');
		if (
			shouldAutoRedirectToOidc({
				oidcEnabled,
				oidcAutoRedirect,
				passwordLoginEnabled,
				hasOidcError
			})
		) {
			autoRedirectStarted = true;
			startOidcLogin();
		}
	}

	function startOidcLogin() {
		window.location.assign(api.oidc.loginUrl());
	}

	$effect(() => {
		const params = new URLSearchParams(window.location.search);
		const oidcError = params.get('oidc_error');
		if (oidcError) {
			error = oidcError;
		}
	});
</script>

<div class="min-h-screen bg-base-200 grid place-items-center p-4">
	<div class="card bg-base-100 border border-base-200 shadow-sm w-full max-w-md">
		<div class="card-body gap-4">
			<div class="flex items-center justify-center gap-3">
				<Logo class="w-16 h-16" />
				<span class="text-2xl font-bold tracking-tight">{$_('app.title')}</span>
			</div>
			<h1 class="text-2xl font-bold">{$_('auth.login')}</h1>
			<label class="form-control">
				<span class="label label-text">{$_('settings.languageTitle')}</span>
				<select class="select select-bordered w-full" value={selectedLanguage} onchange={onLanguageChange}>
					{#each SUPPORTED_LOCALES as code}
						<option value={code}>{$_(`languages.${code}`)}</option>
					{/each}
				</select>
			</label>
			{#if error}
				<Alert type="error" onClose={() => (error = '')}>
					{error}
				</Alert>
			{/if}
			{#if configError}
				<Alert type="error">{$_('auth.configLoadFailed')}</Alert>
			{:else if passwordLoginEnabled === null}
				<p class="text-sm text-base-content/70">{$_('common.loadingEllipsis')}</p>
			{:else if passwordLoginEnabled}
				<form class="flex flex-col gap-4" onsubmit={(e) => { e.preventDefault(); submit(); }}>
					<label class="form-control">
						<span class="label label-text">{$_('auth.email')}</span>
						<input
							type="email"
							class="input input-bordered w-full"
							bind:value={email}
							autocomplete="username"
							required
							disabled={loading}
						/>
					</label>
					<label class="form-control">
						<span class="label label-text">{$_('auth.password')}</span>
						<input
							type="password"
							class="input input-bordered w-full"
							bind:value={password}
							autocomplete="current-password"
							required
							disabled={loading}
						/>
					</label>
					<div class="flex justify-end">
						<button type="button" class="link link-hover text-sm" onclick={openForgotDialog}>
							{$_('auth.forgotPassword')}
						</button>
					</div>
					<button type="submit" class="btn btn-primary btn-block" disabled={loading}>
						{loading ? $_('common.loadingEllipsis') : $_('auth.login')}
					</button>
					{#if oidcEnabled}
						<div class="divider text-xs">{$_('oidc.orContinueWith')}</div>
						<button type="button" class="btn btn-outline btn-block" onclick={startOidcLogin}>
							{$_('oidc.loginWithProvider', { values: { provider: oidcProviderName } })}
						</button>
					{/if}
				</form>
			{:else}
				<div class="flex flex-col gap-4">
					{#if oidcEnabled}
						<button type="button" class="btn btn-primary btn-block" onclick={startOidcLogin}>
							{$_('oidc.loginWithProvider', { values: { provider: oidcProviderName } })}
						</button>
					{:else if !trustedProxyAuthEnabled}
						<Alert type="warning">
							{$_('auth.noLoginMethodAvailable')}
						</Alert>
					{/if}
					<p class="text-sm text-base-content/70">{$_('auth.passwordLoginDisabledHint')}</p>
				</div>
			{/if}
			{#if trustedProxyAuthEnabled}
				<p class="text-sm text-base-content/70">{$_('auth.proxyManagedHint')}</p>
			{/if}
		</div>
	</div>
</div>

{#if passwordLoginEnabled}
<dialog bind:this={forgotDialog} class="modal">
	<div class="modal-box">
		<h3 class="text-lg font-bold mb-4">{$_('auth.forgotPasswordTitle')}</h3>
		{#if forgotSent}
			<div class="alert alert-success mb-4">
				<span>{$_('auth.forgotSent')}</span>
			</div>
			<div class="modal-action">
				<button class="btn" onclick={() => forgotDialog?.close()}>{$_('auth.forgotClose')}</button>
			</div>
		{:else}
			<p class="text-sm mb-4">{$_('auth.forgotPasswordInstruction')}</p>
			{#if forgotError}
				<div class="alert alert-error mb-4">
					<span>{forgotError}</span>
				</div>
			{/if}
			<label class="form-control">
				<span class="label label-text">{$_('auth.email')}</span>
				<input
					type="email"
					class="input input-bordered w-full"
					bind:value={forgotEmail}
					autocomplete="email"
					required
					disabled={forgotLoading}
				/>
			</label>
			<div class="modal-action">
				<button class="btn" onclick={() => forgotDialog?.close()} disabled={forgotLoading}>
					{$_('common.cancel')}
				</button>
				<button class="btn btn-primary" onclick={forgotSubmit} disabled={forgotLoading}>
					{forgotLoading ? $_('common.loadingEllipsis') : $_('auth.forgotSend')}
				</button>
			</div>
		{/if}
	</div>
	<form method="dialog" class="modal-backdrop">
		<button>close</button>
	</form>
</dialog>
{/if}
