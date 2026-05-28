<script lang="ts">
	import Alert from '$lib/components/Alert.svelte';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { currentUser, csrfToken } from '$lib/stores/auth';
	import { _, setLocale } from '$lib/i18n';
	import { setTimezone, detectTimezone } from '$lib/stores/timezone';

	let error = $state('');

	onMount(async () => {
		try {
			const me = await api.auth.me();
			currentUser.set(me);
			const csrf = await api.auth.csrf();
			csrfToken.set(csrf.csrf_token);
			const settings = await api.profile.getSettings();
			setLocale((settings.language as 'en' | 'de') ?? 'en');
			const detected = detectTimezone();
			if (settings.timezone === 'UTC') {
				await api.profile.updateSettings({ timezone: detected });
				setTimezone(detected);
			} else {
				setTimezone(settings.timezone);
			}
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
				<Alert type="error" onClose={() => (error = '')}>
					{error}
				</Alert>
			{/if}
			{#if !error}
				<div class="flex justify-center py-2"><span class="loading loading-spinner loading-md"></span></div>
			{/if}
		</div>
	</div>
</div>
