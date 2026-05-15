<script lang="ts">
	import { api } from '$lib/api';
	import PasswordRequirements from '$lib/components/PasswordRequirements.svelte';
	import { currentUser } from '$lib/stores/auth';
	import { _, SUPPORTED_LOCALES, setLocale } from '$lib/i18n';
	import { getPasswordChecks, passwordChecksPassed, passwordPattern } from '$lib/password';
	import { getTimezone, setTimezone, detectTimezone } from '$lib/stores/timezone';
	import type { ApiKeyMeta, OidcConfig, OidcLinkStatus } from '$lib/types';

	let firstname = $state('');
	let lastname = $state('');
	let password = $state('');
	let showPassword = $state(false);
	let profileMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);
	let language = $state('en');
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

	$effect(() => {
		if ($currentUser) {
			firstname = $currentUser.firstname;
			lastname = $currentUser.lastname;
		}
	});

	async function load() {
		const settings = await api.profile.getSettings();
		language = settings.language;
		timezone = settings.timezone;
		setTimezone(settings.timezone);
		keys = await api.profile.listApiKeys();
		oidcConfig = await api.oidc.config();
		if (oidcConfig.enabled) {
			oidcLink = await api.oidc.linkStatus();
		}
	}

	void load();

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

	$effect(() => {
		const params = new URLSearchParams(window.location.search);
		if (params.get('oidc_linked') === '1') {
			oidcMessage = { type: 'success', text: $_('oidc.linkSuccess') };
			void load();
		}
	});
</script>

<div class="max-w-3xl mx-auto flex flex-col gap-6">
	<h1 class="text-2xl font-bold">{$_('user.profile')}</h1>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<form class="card-body gap-3" onsubmit={(e) => { e.preventDefault(); saveProfile(); }}>
			<h2 class="text-lg font-semibold">{$_('user.profile')}</h2>
			{#if profileMessage}
				<div class={`alert ${profileMessage.type === 'success' ? 'alert-success' : 'alert-error'} text-sm`}>
					<span>{profileMessage.text}</span>
				</div>
			{/if}
			<input
				class="input input-bordered"
				bind:value={firstname}
				placeholder={$_('auth.firstname')}
				autocomplete="given-name"
			/>
			<input
				class="input input-bordered"
				bind:value={lastname}
				placeholder={$_('auth.lastname')}
				autocomplete="family-name"
			/>
			<input
				class="input input-bordered validator"
				type={showPassword ? 'text' : 'password'}
				bind:value={password}
				placeholder={$_('user.newPassword')}
				autocomplete="new-password"
				minlength="8"
				pattern={passwordPattern}
				title={$_('password.requirementsTitle')}
			/>
			<label class="label cursor-pointer justify-start gap-2">
				<input type="checkbox" class="checkbox checkbox-xs" bind:checked={showPassword} />
				<span class="label-text text-xs">{$_('common.showPassword')}</span>
			</label>
			<PasswordRequirements {password} />
			<button type="submit" class="btn btn-primary btn-sm self-start">{$_('common.save')}</button>
		</form>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('settings.languageTitle')}</h2>
			<select class="select select-bordered max-w-xs" bind:value={language}>
				{#each SUPPORTED_LOCALES as code}
					<option value={code}>{$_(`languages.${code}`)}</option>
				{/each}
			</select>
			<button class="btn btn-primary btn-sm self-start" onclick={saveLanguage}>{$_('common.save')}</button>
		</div>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('settings.timezone')}</h2>
			<p class="text-sm text-base-content/70">{$_('settings.timezoneHelp')}</p>
			{#if timezoneMessage}
				<div class={`alert ${timezoneMessage.type === 'success' ? 'alert-success' : 'alert-error'} text-sm max-w-xs`}>
					<span>{timezoneMessage.text}</span>
				</div>
			{/if}
			<input
				list="timezone-list"
				class="input input-bordered max-w-xs"
				bind:value={timezone}
				placeholder={$_('settings.timezonePlaceholder')}
			/>
			<datalist id="timezone-list">
				{#each allTimezones as tz}
					<option value={tz} />
				{/each}
			</datalist>
			<p class="text-xs text-base-content/50">{$_('settings.timezoneDetected', { values: { tz: browserTz } })}</p>
			<p class="text-xs text-base-content/50">{$_('settings.timezoneSelected', { values: { tz: timezone } })}</p>
			<button class="btn btn-primary btn-sm self-start" onclick={saveTimezone}>{$_('common.save')}</button>
		</div>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('user.apiKeys')}</h2>
			<p class="text-sm text-base-content/70">
				<a href="/api-docs" class="link link-primary">{$_('settings.apiDocsTitle')}</a>
			</p>
			<div class="flex gap-2">
				<input class="input input-bordered flex-1" bind:value={description} placeholder={$_('user.keyDescription')} />
				<button class="btn btn-primary btn-sm" onclick={createKey}>{$_('user.addKey')}</button>
			</div>
			{#if createdKey}
				<div class="alert alert-success flex flex-col items-start gap-2 text-xs">
					<span>{$_('user.newKeyShownOnce')}</span>
					<div class="w-full rounded border border-success/30 bg-base-300/70 px-3 py-2 font-mono text-[11px] break-all">
						{createdKey}
					</div>
					<button type="button" class="btn btn-success btn-xs" onclick={copyCreatedKey}>
						{keyCopied ? $_('common.copied') : $_('common.copy')}
					</button>
				</div>
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

	{#if oidcConfig.enabled}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body gap-3">
				<h2 class="text-lg font-semibold">{$_('oidc.profileTitle')}</h2>
				{#if oidcMessage}
					<div class={`alert ${oidcMessage.type === 'success' ? 'alert-success' : 'alert-error'} text-sm`}>
						<span>{oidcMessage.text}</span>
					</div>
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
</div>

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
