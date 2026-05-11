<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { _ } from '$lib/i18n';

	let error = $state('');

	onMount(async () => {
		const params = new URLSearchParams(window.location.search);
		const err = params.get('error');
		if (err) {
			error = err;
			return;
		}

		await goto('/profile?oidc_linked=1');
	});
</script>

<div class="min-h-screen bg-base-200 grid place-items-center p-4">
	<div class="card bg-base-100 border border-base-200 shadow-sm w-full max-w-md">
		<div class="card-body gap-4">
			<h1 class="text-xl font-semibold">{$_('oidc.linkingAccount')}</h1>
			{#if error}
				<div class="alert alert-error text-sm"><span>{error}</span></div>
				<a href="/profile" class="btn btn-outline btn-sm self-start">{$_('user.profile')}</a>
			{:else}
				<div class="flex justify-center py-2"><span class="loading loading-spinner loading-md"></span></div>
			{/if}
		</div>
	</div>
</div>
