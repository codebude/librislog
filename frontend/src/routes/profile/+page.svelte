<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import PasswordRequirements from '$lib/components/PasswordRequirements.svelte';
	import { currentUser } from '$lib/stores/auth';
	import { _, SUPPORTED_LOCALES, setLocale } from '$lib/i18n';
	import { getPasswordChecks, passwordChecksPassed, passwordPattern } from '$lib/password';
	import { getTimezone, setTimezone, detectTimezone } from '$lib/stores/timezone';
	import { getThemeMode, setThemeMode, getCustomTheme, setCustomTheme, applyThemeToDocument, saveThemeToStorage, sanitizeThemeMode, restoreFromPoint, saveRestorePoint, clearRestorePoint, DAISYUI_THEMES } from '$lib/stores/theme';
	import Alert from '$lib/components/Alert.svelte';
	import { toasts } from '$lib/toasts';
	import { localizeError } from '$lib/errors';
	import type { ApiKeyMeta, OidcConfig, OidcLinkStatus } from '$lib/types';

	let firstname = $state('');
	let lastname = $state('');
	let password = $state('');
	let showPassword = $state(false);
	let profileMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);
	let language = $state('en');
	let languageMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);
	let timezone = $state(getTimezone());
	let timezoneMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);
	let description = $state('');
	let createdKey = $state<string | null>(null);
	let keyCopied = $state(false);
	let keys = $state<ApiKeyMeta[]>([]);
	let pendingDeleteKeyId = $state<number | null>(null);
	let oidcConfig = $state<OidcConfig>({ enabled: false, provider_id: null, provider_name: null });
	let oidcLink = $state<OidcLinkStatus>({ linked: false, provider_name: null, oidc_email: null, oidc_name: null });
	let oidcLoading = $state(false);
	let oidcMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);
	let themeMode = $state(getThemeMode());
	let customTheme = $state<string>(getCustomTheme() ?? 'dracula');
	let themeMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);
	let resetDataConfirmation = $state('');
	let resetDataMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);
	let deleteAccountConfirmation = $state('');
	let deleteAccountMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);
	let dangerLoading = $state(false);
	let activeSection = $state('');
	let navTop = $state(32);
	let navLeft = $state(0);

	$effect(() => {
		if ($currentUser) {
			firstname = $currentUser.firstname;
			lastname = $currentUser.lastname;
		}
	});

	function positionNav() {
		if (window.innerWidth < 1280) return;
		const nav = document.querySelector('nav[aria-label]') as HTMLElement | null;
		const content = document.querySelector('#profile-content') as HTMLElement | null;
		const firstSection = document.querySelector('#section-profile') as HTMLElement | null;
		if (!nav || !content) return;
		const cr = content.getBoundingClientRect();
		const desiredLeft = cr.right + 32;
		const maxLeft = window.innerWidth - nav.offsetWidth - 16;
		navLeft = Math.min(desiredLeft, maxLeft);
		if (firstSection) {
			navTop = Math.max(16, firstSection.getBoundingClientRect().top);
		}
	}

	function updateActiveSection() {
		const sections = document.querySelectorAll('[id^="section-"]');
		if (sections.length === 0) return;
		const scrollY = window.scrollY;
		const nav = document.querySelector('nav[aria-label]');
		const offset = nav ? nav.getBoundingClientRect().height + 32 : 150;
		let selected = sections[0];
		for (let i = sections.length - 1; i >= 0; i--) {
			const section = sections[i] as HTMLElement;
			if (section.offsetTop <= scrollY + offset) {
				selected = section;
				break;
			}
		}
		activeSection = selected.id;
	}

	$effect(() => {
		void oidcConfig; // re-run when OIDC config loads (adds/removes OIDC section in DOM)

		positionNav();
		window.addEventListener('resize', positionNav);

		updateActiveSection();

		let rAFId: number | null = null;
		const onScroll = () => {
			if (rAFId === null) {
				rAFId = requestAnimationFrame(() => {
					updateActiveSection();
					rAFId = null;
				});
			}
		};
		window.addEventListener('scroll', onScroll, { passive: true });

		return () => {
			if (rAFId !== null) cancelAnimationFrame(rAFId);
			window.removeEventListener('resize', positionNav);
			window.removeEventListener('scroll', onScroll);
		};
	});



	async function load() {
		const settings = await api.profile.getSettings();
		language = settings.language;
		timezone = settings.timezone;
		setTimezone(settings.timezone);
		themeMode = sanitizeThemeMode(settings.theme);
		setThemeMode(themeMode);
		if (themeMode === 'custom' && settings.custom_theme) {
			customTheme = settings.custom_theme;
			setCustomTheme(customTheme);
		}
		applyThemeToDocument();
		saveThemeToStorage();
		saveRestorePoint();
		keys = await api.profile.listApiKeys();
		oidcConfig = await api.oidc.config();
		if (oidcConfig.enabled) {
			oidcLink = await api.oidc.linkStatus();
		}
	}

	onMount(() => {
		void load();
	});

	$effect(() => {
		return () => {
			if (restoreFromPoint()) {
				applyThemeToDocument();
				saveThemeToStorage();
			}
		};
	});

	async function saveProfile() {
		profileMessage = null;
		const nextPassword = password.trim();
		if (nextPassword && !passwordChecksPassed(getPasswordChecks(nextPassword))) {
			profileMessage = { type: 'error', text: $_('auth.passwordComplexityError') };
			return;
		}
		const payload: { firstname?: string; lastname?: string; password?: string } = { firstname, lastname };
		if (nextPassword) payload.password = nextPassword;
		try {
			const updated = await api.profile.update(payload);
			currentUser.set(updated);
			password = '';
			profileMessage = {
				type: 'success',
				text: nextPassword ? $_('profile.passwordChangeSuccess') : $_('profile.profileSaveSuccess')
			};
		} catch (e: unknown) {
			profileMessage = {
				type: 'error',
				text: e instanceof Error ? e.message : nextPassword ? $_('profile.passwordChangeFailed') : $_('profile.profileSaveFailed')
			};
		}
	}

	async function saveLanguage() {
		const updated = await api.profile.updateSettings({ language });
		if (SUPPORTED_LOCALES.includes(updated.language as (typeof SUPPORTED_LOCALES)[number])) {
			setLocale(updated.language as (typeof SUPPORTED_LOCALES)[number]);
		}
		languageMessage = { type: 'success', text: $_('common.saved') };
	}

	const allTimezones: string[] = typeof Intl.supportedValuesOf === 'function'
		? Intl.supportedValuesOf('timeZone')
		: [];

	const browserTz = detectTimezone();

	async function saveTimezone() {
		if (!allTimezones.includes(timezone)) {
			timezoneMessage = { type: 'error', text: $_('settings.timezoneInvalid') };
			return;
		}
		timezoneMessage = null;
		await api.profile.updateSettings({ timezone });
		setTimezone(timezone);
		timezoneMessage = { type: 'success', text: $_('common.saved') };
	}

	$effect(() => {
		if (typeof window !== 'undefined') {
			setCustomTheme(customTheme);
			if (getThemeMode() === 'custom') {
				applyThemeToDocument();
			}
		}
	});

	async function saveTheme() {
		themeMessage = null;
		setThemeMode('custom');
		setCustomTheme(customTheme);
		themeMode = 'custom';
		applyThemeToDocument();
		saveThemeToStorage();
		clearRestorePoint();
		try {
			await api.profile.updateSettings({
				theme: 'custom',
				custom_theme: customTheme,
			});
			themeMessage = { type: 'success', text: $_('common.saved') };
		} catch (e: unknown) {
			themeMessage = { type: 'error', text: e instanceof Error ? e.message : $_('common.saveFailed') };
		}
	}

	async function createKey() {
		const result = await api.profile.createApiKey({ description: description || null });
		createdKey = result.key;
		keyCopied = false;
		description = '';
		keys = await api.profile.listApiKeys();
	}

	async function copyCreatedKey() {
		if (!createdKey) return;
		await navigator.clipboard.writeText(createdKey);
		keyCopied = true;
	}

	function requestDeleteKey(id: number) {
		pendingDeleteKeyId = id;
	}

	function cancelDeleteKey() {
		pendingDeleteKeyId = null;
	}

	async function confirmDeleteKey() {
		if (pendingDeleteKeyId === null) return;
		const id = pendingDeleteKeyId;
		pendingDeleteKeyId = null;
		await api.profile.deleteApiKey(id);
		keys = await api.profile.listApiKeys();
	}

	async function startOidcLink() {
		oidcMessage = null;
		try {
			const response = await api.oidc.startLink();
			window.location.href = response.redirect_url;
		} catch (e: unknown) {
			oidcMessage = { type: 'error', text: e instanceof Error ? e.message : $_('oidc.linkStartFailed') };
		}
	}

	async function unlinkOidc() {
		oidcMessage = null;
		oidcLoading = true;
		try {
			await api.oidc.unlink();
			oidcLink = await api.oidc.linkStatus();
			oidcMessage = { type: 'success', text: $_('oidc.unlinkSuccess') };
		} catch (e: unknown) {
			oidcMessage = { type: 'error', text: e instanceof Error ? e.message : $_('oidc.unlinkFailed') };
		} finally {
			oidcLoading = false;
		}
	}

	async function confirmResetData() {
		if (resetDataConfirmation.trim() !== $_('profile.dangerZone.resetData.confirmationPhrase')) {
			return;
		}
		resetDataMessage = null;
		dangerLoading = true;
		try {
			const result = await api.profile.resetData(resetDataConfirmation.trim());
			resetDataMessage = {
				type: 'success',
				text: $_('profile.dangerZone.resetData.success', {
					values: {
						books: result.deleted.books,
						tags: result.deleted.tags,
						entries: result.deleted.progress_entries
					}
				})
			};
			toasts.add($_('profile.dangerZone.resetData.success', {
				values: {
					books: result.deleted.books,
					tags: result.deleted.tags,
					entries: result.deleted.progress_entries
				}
			}), 'success');
			resetDataConfirmation = '';
			setTimeout(() => {
				window.location.href = '/dashboard';
			}, 1500);
		} catch (e: unknown) {
			const message = localizeError(e, $_, $_('profile.dangerZone.resetData.failed'));
			resetDataMessage = { type: 'error', text: message };
			toasts.add(message, 'error');
		} finally {
			dangerLoading = false;
		}
	}

	async function confirmDeleteAccount() {
		if (deleteAccountConfirmation.trim() !== $_('profile.dangerZone.deleteAccount.confirmationPhrase')) {
			return;
		}
		deleteAccountMessage = null;
		dangerLoading = true;
		try {
			await api.profile.deleteOwnAccount(deleteAccountConfirmation.trim());
			deleteAccountMessage = { type: 'success', text: $_('profile.dangerZone.deleteAccount.success') };
			toasts.add($_('profile.dangerZone.deleteAccount.success'), 'success');
			setTimeout(() => {
				window.location.href = '/login';
			}, 1000);
		} catch (e: unknown) {
			const message = localizeError(e, $_, $_('profile.dangerZone.deleteAccount.failed'));
			deleteAccountMessage = { type: 'error', text: message };
			toasts.add(message, 'error');
		} finally {
			dangerLoading = false;
		}
	}

	$effect(() => {
		const params = new URLSearchParams(window.location.search);
		if (params.get('oidc_linked') === '1') {
			oidcMessage = { type: 'success', text: $_('oidc.linkSuccess') };
			void load();
		}
	});
</script>

<div id="profile-content" class="max-w-3xl mx-auto flex flex-col gap-6">
	<h1 class="text-2xl font-bold">{$_('user.profile')}</h1>

	<div id="section-profile" class="scroll-mt-24 card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
		<form class="card-body gap-3" onsubmit={(e) => { e.preventDefault(); saveProfile(); }}>
			<h2 class="text-lg font-semibold">{$_('user.profile')}</h2>
			{#if profileMessage}
				<Alert type={profileMessage.type === 'success' ? 'success' : 'error'} onClose={() => (profileMessage = null)}>
					{profileMessage.text}
				</Alert>
			{/if}
			<input
				class="input input-bordered"
				name="firstname"
				bind:value={firstname}
				placeholder={$_('auth.firstname')}
				autocomplete="given-name"
			/>
			<input
				class="input input-bordered"
				name="lastname"
				bind:value={lastname}
				placeholder={$_('auth.lastname')}
				autocomplete="family-name"
			/>
			<input
				class="input input-bordered validator"
				name="password"
				type={showPassword ? 'text' : 'password'}
				bind:value={password}
				placeholder={$_('user.newPassword')}
				autocomplete="new-password"
				minlength="8"
				pattern={passwordPattern}
				title={$_('password.requirementsTitle')}
			/>
			<label class="label cursor-pointer justify-start gap-2">
				<input type="checkbox" class="checkbox checkbox-xs" name="show-password" bind:checked={showPassword} />
				<span class="label-text text-xs">{$_('common.showPassword')}</span>
			</label>
			<PasswordRequirements {password} />
			<button type="submit" class="btn btn-primary btn-sm self-start">{$_('common.save')}</button>
		</form>
	</div>

	<div id="section-language" class="scroll-mt-24 card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('settings.languageTitle')}</h2>
			{#if languageMessage}
				<Alert type={languageMessage.type === 'success' ? 'success' : 'error'} onClose={() => (languageMessage = null)}>
					{languageMessage.text}
				</Alert>
			{/if}
			<select class="select select-bordered max-w-xs" name="language" bind:value={language}>
				{#each SUPPORTED_LOCALES as code}
					<option value={code}>{$_(`languages.${code}`)}</option>
				{/each}
			</select>
			<button class="btn btn-primary btn-sm self-start" onclick={saveLanguage}>{$_('common.save')}</button>
		</div>
	</div>

	<div id="section-timezone" class="scroll-mt-24 card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('settings.timezone')}</h2>
			<p class="text-sm text-base-content/70">{$_('settings.timezoneHelp')}</p>
			{#if timezoneMessage}
				<Alert type={timezoneMessage.type === 'success' ? 'success' : 'error'} onClose={() => (timezoneMessage = null)}>
					{timezoneMessage.text}
				</Alert>
			{/if}
			<input
				list="timezone-list"
				name="timezone"
				class="input input-bordered max-w-xs"
				bind:value={timezone}
				placeholder={$_('settings.timezonePlaceholder')}
			/>
			<datalist id="timezone-list">
				{#each allTimezones as tz}
					<option value={tz}></option>
				{/each}
			</datalist>
			<p class="text-xs text-base-content/50">{$_('settings.timezoneDetected', { values: { tz: browserTz } })}</p>
			<p class="text-xs text-base-content/50">{$_('settings.timezoneSelected', { values: { tz: timezone } })}</p>
			<button class="btn btn-primary btn-sm self-start" onclick={saveTimezone}>{$_('common.save')}</button>
		</div>
	</div>

	<div id="section-theme" class="scroll-mt-24 card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('settings.themeTitle')}</h2>
			{#if themeMessage}
				<Alert type={themeMessage.type === 'success' ? 'success' : 'error'} onClose={() => (themeMessage = null)}>
					{themeMessage.text}
				</Alert>
			{/if}
			<span class="label">
				<span class="label-text">{$_('settings.themeSelect')}</span>
			</span>
			<select class="select select-bordered max-w-xs" name="custom-theme" bind:value={customTheme}>
				{#each [...DAISYUI_THEMES].sort() as t}
					<option value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
				{/each}
			</select>
			<button class="btn btn-primary btn-sm self-start" onclick={saveTheme}>{$_('common.save')}</button>
		</div>
	</div>

	<div id="section-api-keys" class="scroll-mt-24 card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('user.apiKeys')}</h2>
			<p class="text-sm text-base-content/70">
				<a href="/api-docs" class="link link-primary">{$_('settings.apiDocsTitle')}</a>
			</p>
			<div class="flex gap-2">
				<input class="input input-bordered flex-1" name="key-description" bind:value={description} placeholder={$_('user.keyDescription')} />
				<button class="btn btn-primary btn-sm" onclick={createKey}>{$_('user.addKey')}</button>
			</div>
			{#if createdKey}
				<Alert type="success" onClose={() => (createdKey = null)} duration={0}>
					<div class="flex flex-col items-start gap-2 text-xs">
						<span>{$_('user.newKeyShownOnce')}</span>
						<div class="w-full rounded border border-success/30 bg-base-300/70 px-3 py-2 font-mono text-[11px] break-all">
							{createdKey}
						</div>
						<button type="button" class="btn btn-success btn-xs" onclick={copyCreatedKey}>
							{keyCopied ? $_('common.copied') : $_('common.copy')}
						</button>
					</div>
				</Alert>
			{/if}
			<ul class="flex flex-col gap-2">
				{#each keys as key}
					<li class="flex items-center justify-between border border-base-200 rounded p-2 text-sm">
						<div class="min-w-0">
							<p class="font-mono">{key.key_prefix}...</p>
							<p class="text-base-content/70 truncate">{key.description ?? $_('user.noDescription')}</p>
						</div>
						<button class="btn btn-error btn-outline btn-xs" onclick={() => requestDeleteKey(key.id)}>{$_('common.delete')}</button>
					</li>
				{/each}
			</ul>
		</div>
	</div>

	<div id="section-data" class="scroll-mt-24 card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('profile.dataManagement.title')}</h2>
			<p class="text-sm text-base-content/70">{$_('profile.dataManagement.description')}</p>
			<a class="btn btn-outline btn-sm w-fit" href="/data?tab=export">{$_('profile.dataManagement.link')}</a>
			<div class="divider my-1"></div>
			<p class="text-sm text-base-content/70">{$_('dataHygiene.description')}</p>
			<a class="btn btn-outline btn-sm w-fit" href="/data-hygiene">{$_('dataHygiene.title')}</a>
		</div>
	</div>

	{#if oidcConfig.enabled}
		<div id="section-oidc" class="scroll-mt-24 card bg-base-100 border border-base-200 shadow-sm rounded-2xl">
			<div class="card-body gap-3">
				<h2 class="text-lg font-semibold">{$_('oidc.profileTitle')}</h2>
				{#if oidcMessage}
					<Alert type={oidcMessage.type === 'success' ? 'success' : 'error'} onClose={() => (oidcMessage = null)}>
						{oidcMessage.text}
					</Alert>
				{/if}
				{#if oidcLink.linked}
					<p class="text-sm text-base-content/70">
						{$_('oidc.linkedAs', { values: { provider: oidcLink.provider_name ?? oidcConfig.provider_name ?? '' } })}
						{#if oidcLink.oidc_email} ({oidcLink.oidc_email}){/if}
					</p>
					<button class="btn btn-outline btn-sm self-start" onclick={unlinkOidc} disabled={oidcLoading}>
						{$_('oidc.unlinkButton')}
					</button>
				{:else}
					<p class="text-sm text-base-content/70">{$_('oidc.notLinked')}</p>
					<button class="btn btn-outline btn-sm self-start" onclick={startOidcLink}>
						{$_('oidc.linkButton', { values: { provider: oidcConfig.provider_name ?? '' } })}
					</button>
				{/if}
			</div>
		</div>
	{/if}

	<div id="section-danger-zone" class="scroll-mt-24 card bg-error/10 border border-error/30 shadow-sm">
		<div class="card-body gap-4">
			<h2 class="text-lg font-semibold text-error">{$_('profile.dangerZone.title')}</h2>
			<p class="text-sm text-base-content/70">{$_('profile.dangerZone.subtitle')}</p>

			<div class="border border-error/20 rounded-xl p-4 flex flex-col gap-3">
				<h3 class="font-medium">{$_('profile.dangerZone.resetData.title')}</h3>
				<p class="text-sm text-base-content/70">{$_('profile.dangerZone.resetData.description')}</p>
				<p class="text-xs font-semibold text-warning">{$_('profile.dangerZone.resetData.warning')}</p>
				<input
					class="input input-bordered max-w-md"
					name="reset-data-confirmation"
					bind:value={resetDataConfirmation}
					placeholder={$_('profile.dangerZone.resetData.placeholder')}
				/>
				<p class="text-xs text-base-content/60">{$_('profile.dangerZone.resetData.hint')}</p>
				{#if resetDataMessage}
					<Alert type={resetDataMessage.type === 'success' ? 'success' : 'error'} onClose={() => (resetDataMessage = null)}>
						{resetDataMessage.text}
					</Alert>
				{/if}
				<button
					type="button"
					class="btn btn-error btn-sm self-start"
					disabled={
						dangerLoading ||
						resetDataConfirmation.trim() !== $_('profile.dangerZone.resetData.confirmationPhrase')
					}
					onclick={confirmResetData}
				>
					{$_('profile.dangerZone.resetData.button')}
				</button>
			</div>

			<div class="border border-error/20 rounded-xl p-4 flex flex-col gap-3">
				<h3 class="font-medium">{$_('profile.dangerZone.deleteAccount.title')}</h3>
				<p class="text-sm text-base-content/70">{$_('profile.dangerZone.deleteAccount.description')}</p>
				<p class="text-xs font-semibold text-error">{$_('profile.dangerZone.deleteAccount.warning')}</p>
				<input
					class="input input-bordered max-w-md"
					name="delete-account-confirmation"
					bind:value={deleteAccountConfirmation}
					placeholder={$_('profile.dangerZone.deleteAccount.placeholder')}
				/>
				<p class="text-xs text-base-content/60">{$_('profile.dangerZone.deleteAccount.hint')}</p>
				{#if deleteAccountMessage}
					<Alert type={deleteAccountMessage.type === 'success' ? 'success' : 'error'} onClose={() => (deleteAccountMessage = null)}>
						{deleteAccountMessage.text}
					</Alert>
				{/if}
				<button
					type="button"
					class="btn btn-error btn-sm self-start"
					disabled={
						dangerLoading ||
						deleteAccountConfirmation.trim() !== $_('profile.dangerZone.deleteAccount.confirmationPhrase')
					}
					onclick={confirmDeleteAccount}
				>
					{$_('profile.dangerZone.deleteAccount.button')}
				</button>
			</div>
		</div>
	</div>
</div>

<!--
	Uses xl instead of lg because at lg (1024px) the sidebar (224px) + content
	(max-w-3xl, 768px) + nav (208px) doesn't fit without horizontal overflow.
-->
<nav
	class="hidden xl:block fixed w-52"
	style:top="{navTop}px"
	style:left="{navLeft}px"
	aria-label={$_('profile.sectionNav')}
>
	<ul class="menu menu-sm bg-base-200 rounded-xl border border-base-300">
		<li class="menu-title"><span>{$_('profile.sectionNav')}</span></li>
		<li><a href="#section-profile" class:menu-active={activeSection === 'section-profile'}>{$_('user.profile')}</a></li>
		<li><a href="#section-language" class:menu-active={activeSection === 'section-language'}>{$_('settings.languageTitle')}</a></li>
		<li><a href="#section-timezone" class:menu-active={activeSection === 'section-timezone'}>{$_('settings.timezone')}</a></li>
		<li><a href="#section-theme" class:menu-active={activeSection === 'section-theme'}>{$_('settings.themeTitle')}</a></li>
		<li><a href="#section-api-keys" class:menu-active={activeSection === 'section-api-keys'}>{$_('user.apiKeys')}</a></li>
		<li><a href="#section-data" class:menu-active={activeSection === 'section-data'}>{$_('profile.dataManagement.title')}</a></li>
		{#if oidcConfig.enabled}
			<li><a href="#section-oidc" class:menu-active={activeSection === 'section-oidc'}>{$_('oidc.profileTitle')}</a></li>
		{/if}
		<li><a href="#section-danger-zone" class:menu-active={activeSection === 'section-danger-zone'}>{$_('profile.dangerZone.title')}</a></li>
	</ul>
</nav>

<dialog class="modal" class:modal-open={pendingDeleteKeyId !== null}>
	<div class="modal-box">
		<h3 class="text-lg font-bold">Do you really want to delete?</h3>
		<p class="py-3 text-sm text-base-content/70">{$_('common.confirm')}</p>
		<div class="modal-action">
			<button type="button" class="btn btn-ghost" onclick={cancelDeleteKey}>{$_('common.cancel')}</button>
			<button type="button" class="btn btn-error" onclick={confirmDeleteKey}>{$_('common.delete')}</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button type="button" onclick={cancelDeleteKey}>{$_('common.close')}</button>
	</form>
</dialog>
