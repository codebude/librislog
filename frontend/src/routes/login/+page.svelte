<script lang="ts">
	import Alert from '$lib/components/Alert.svelte';
	import Logo from '$lib/components/Logo.svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { currentUser, csrfToken } from '$lib/stores/auth';
	import { _, locale, setLocale, SUPPORTED_LOCALES, type AppLocale } from '$lib/i18n';
	import { setTimezone, detectTimezone } from '$lib/stores/timezone';
	import {
		setThemeMode, setCustomTheme, applyThemeToDocument, saveThemeToStorage,
		sanitizeThemeMode, THEME_MODE_KEY, CUSTOM_THEME_KEY
	} from '$lib/stores/theme';

	let email = $state('');
	let password = $state('');
	let selectedLanguage = $state<AppLocale>('en');
	let languageChanged = $state(false);
	let loading = $state(false);
	let error = $state('');
	let oidcEnabled = $state(false);
	let oidcProviderName = $state('Single Sign-On');

	$effect(() => {
		void (async () => {
			try {
				const cfg = await api.oidc.config();
				oidcEnabled = cfg.enabled;
				oidcProviderName = cfg.provider_name ?? 'Single Sign-On';
			} catch {
				oidcEnabled = false;
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

	function startOidcLogin() {
		window.location.href = api.oidc.loginUrl();
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
		</div>
	</div>
</div>
