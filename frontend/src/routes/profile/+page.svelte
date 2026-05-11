<script lang="ts">
	import { api } from '$lib/api';
	import { currentUser } from '$lib/stores/auth';
	import { _, SUPPORTED_LOCALES, setLocale } from '$lib/i18n';
	import type { ApiKeyMeta } from '$lib/types';

	let firstname = $state('');
	let lastname = $state('');
	let email = $state('');
	let language = $state('en');
	let description = $state('');
	let createdKey = $state<string | null>(null);
	let keys = $state<ApiKeyMeta[]>([]);

	$effect(() => {
		if ($currentUser) {
			firstname = $currentUser.firstname;
			lastname = $currentUser.lastname;
			email = $currentUser.email;
		}
	});

	async function load() {
		const settings = await api.profile.getSettings();
		language = settings.language;
		keys = await api.profile.listApiKeys();
	}

	void load();

	async function saveProfile() {
		const updated = await api.profile.update({ firstname, lastname, email });
		currentUser.set(updated);
	}

	async function saveLanguage() {
		const updated = await api.profile.updateSettings({ language });
		if (SUPPORTED_LOCALES.includes(updated.language as (typeof SUPPORTED_LOCALES)[number])) {
			setLocale(updated.language as (typeof SUPPORTED_LOCALES)[number]);
		}
	}

	async function createKey() {
		const result = await api.profile.createApiKey({ description: description || null });
		createdKey = result.key;
		description = '';
		keys = await api.profile.listApiKeys();
	}

	async function deleteKey(id: number) {
		await api.profile.deleteApiKey(id);
		keys = await api.profile.listApiKeys();
	}
</script>

<div class="max-w-3xl mx-auto flex flex-col gap-6">
	<h1 class="text-2xl font-bold">{$_('user.profile')}</h1>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('user.profile')}</h2>
			<input class="input input-bordered" bind:value={firstname} placeholder={$_('auth.firstname')} />
			<input class="input input-bordered" bind:value={lastname} placeholder={$_('auth.lastname')} />
			<input class="input input-bordered" bind:value={email} placeholder={$_('auth.email')} />
			<button class="btn btn-primary btn-sm self-start" onclick={saveProfile}>{$_('common.save')}</button>
		</div>
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
			<h2 class="text-lg font-semibold">{$_('user.apiKeys')}</h2>
			<p class="text-sm text-base-content/70">{$_('user.primaryKeyHidden')}</p>
			<div class="flex gap-2">
				<input class="input input-bordered flex-1" bind:value={description} placeholder={$_('user.keyDescription')} />
				<button class="btn btn-primary btn-sm" onclick={createKey}>{$_('user.addKey')}</button>
			</div>
			{#if createdKey}
				<div class="alert alert-success text-xs break-all"><span>{$_('user.newKeyShownOnce')}: {createdKey}</span></div>
			{/if}
			<ul class="flex flex-col gap-2">
				{#each keys as key}
					<li class="flex items-center justify-between border border-base-200 rounded p-2 text-sm">
						<div class="min-w-0">
							<p class="font-mono">{key.key_prefix}...</p>
							<p class="text-base-content/70 truncate">{key.description ?? $_('user.noDescription')}</p>
						</div>
						{#if !key.is_primary}
							<button class="btn btn-error btn-outline btn-xs" onclick={() => deleteKey(key.id)}>{$_('common.delete')}</button>
						{/if}
					</li>
				{/each}
			</ul>
		</div>
	</div>
</div>
