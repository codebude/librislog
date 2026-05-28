<script lang="ts">
	import Alert from '$lib/components/Alert.svelte';
	import Logo from '$lib/components/Logo.svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import PasswordRequirements from '$lib/components/PasswordRequirements.svelte';
	import { getPasswordChecks, passwordChecksPassed, passwordPattern } from '$lib/password';
	import { isValidEmailFormat } from '$lib/validation';
	import { currentUser, csrfToken } from '$lib/stores/auth';
	import { _, locale, setLocale, SUPPORTED_LOCALES, type AppLocale } from '$lib/i18n';
	import { setTimezone, detectTimezone } from '$lib/stores/timezone';

	let firstname = $state('');
	let lastname = $state('');
	let email = $state('');
	let password = $state('');
	let showPassword = $state(false);
	let selectedLanguage = $state<AppLocale>('en');
	let loading = $state(false);
	let error = $state('');

	$effect(() => {
		if (SUPPORTED_LOCALES.includes($locale as AppLocale)) {
			selectedLanguage = $locale as AppLocale;
		}
	});

	function onLanguageChange(event: Event) {
		const next = (event.currentTarget as HTMLSelectElement).value as AppLocale;
		if (!SUPPORTED_LOCALES.includes(next)) return;
		selectedLanguage = next;
		setLocale(next);
	}

	async function submit() {
		error = '';
		if (!isValidEmailFormat(email)) {
			error = $_('auth.invalidEmailError');
			return;
		}
		const passwordToValidate = password.trim();
		if (!passwordChecksPassed(getPasswordChecks(passwordToValidate))) {
			error = $_('auth.passwordComplexityError');
			return;
		}
		loading = true;
		try {
			const result = await api.auth.setup({ firstname, lastname, email, password: passwordToValidate });
			currentUser.set(result.user);
			const csrf = await api.auth.csrf();
			csrfToken.set(csrf.csrf_token);
			const detected = detectTimezone();
			await api.profile.updateSettings({ language: selectedLanguage, timezone: detected });
			setTimezone(detected);
			setLocale(selectedLanguage);
			await goto('/');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $_('auth.setupFailed');
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-screen bg-base-200 grid place-items-center p-4">
	<div class="card bg-base-100 border border-base-200 shadow-sm w-full max-w-md">
		<div class="card-body gap-4">
			<div class="flex items-center justify-center gap-3">
				<Logo class="w-16 h-16" />
				<span class="text-2xl font-bold tracking-tight">{$_('app.title')}</span>
			</div>
			<h1 class="text-2xl font-bold">{$_('auth.setupTitle')}</h1>
			<label class="form-control max-w-xs">
				<span class="label label-text">{$_('settings.languageTitle')}</span>
				<select class="select select-bordered" value={selectedLanguage} onchange={onLanguageChange}>
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
			<form class="flex flex-col gap-3" onsubmit={(e) => { e.preventDefault(); submit(); }}>
				<label class="form-control">
					<span class="label label-text">{$_('auth.firstname')} *</span>
					<input
						class="input input-bordered"
						placeholder={$_('auth.firstname')}
						bind:value={firstname}
						autocomplete="given-name"
						required
					/>
				</label>
				<label class="form-control">
					<span class="label label-text">{$_('auth.lastname')} *</span>
					<input
						class="input input-bordered"
						placeholder={$_('auth.lastname')}
						bind:value={lastname}
						autocomplete="family-name"
						required
					/>
				</label>
				<label class="form-control">
					<span class="label label-text">{$_('auth.email')} *</span>
					<input
						type="email"
						class="input input-bordered"
						placeholder={$_('auth.email')}
						bind:value={email}
						autocomplete="username"
						required
					/>
				</label>
				<label class="form-control">
					<span class="label label-text">{$_('auth.password')} *</span>
				<input
					type={showPassword ? 'text' : 'password'}
					class="input input-bordered validator"
					placeholder={$_('auth.password')}
					bind:value={password}
					autocomplete="new-password"
					required
					minlength="8"
					pattern={passwordPattern}
					title={$_('password.requirementsTitle')}
				/>
				</label>
				<label class="label cursor-pointer justify-start gap-2">
					<input type="checkbox" class="checkbox checkbox-xs" bind:checked={showPassword} />
					<span class="label-text text-xs">{$_('common.showPassword')}</span>
				</label>
				<PasswordRequirements {password} />
				<button type="submit" class="btn btn-primary" disabled={loading}>
					{loading ? $_('common.loadingEllipsis') : $_('auth.createAdmin')}
				</button>
			</form>
		</div>
	</div>
</div>
