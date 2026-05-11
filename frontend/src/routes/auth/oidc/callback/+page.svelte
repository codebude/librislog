<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { currentUser, setAuthKey } from '$lib/stores/auth';
	import { _, setLocale } from '$lib/i18n';

	let error = $state('');

	onMount(async () => {
		const params = new URLSearchParams(window.location.search);
		const apiKey = params.get('api_key');
		if (!apiKey) {
			error = $_('oidc.callbackMissingKey');
			return;
		}

		try {
			setAuthKey(apiKey);
			const me = await api.auth.me();
			currentUser.set(me);
			const settings = await api.profile.getSettings();
			setLocale((settings.language as 'en' | 'de') ?? 'en');
			await goto('/');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $_('auth.loginFailed');
		}
	});
</script>

<div class="min-h-screen bg-base-200 grid place-items-center p-4">
	<div class="card bg-base-100 border border-base-200 shadow-sm w-full max-w-md">
		<div class="card-body gap-4">
			<h1 class="text-xl font-semibold">{$_('oidc.signingIn')}</h1>
			{#if error}
				<div class="alert alert-error text-sm"><span>{error}</span></div>
			{/if}
			{#if !error}
				<div class="flex justify-center py-2"><span class="loading loading-spinner loading-md"></span></div>
			{/if}
		</div>
	</div>
</div>
