<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { currentUser, setAuthKey } from '$lib/stores/auth';
	import { _ } from '$lib/i18n';

	let firstname = $state('');
	let lastname = $state('');
	let email = $state('');
	let password = $state('');
	let loading = $state(false);
	let error = $state('');

	async function submit() {
		error = '';
		loading = true;
		try {
			const result = await api.auth.setup({ firstname, lastname, email, password });
			setAuthKey(result.api_key);
			currentUser.set(result.user);
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
			<h1 class="text-2xl font-bold">{$_('auth.setupTitle')}</h1>
			{#if error}
				<div class="alert alert-error text-sm"><span>{error}</span></div>
			{/if}
			<form class="flex flex-col gap-3" onsubmit={(e) => { e.preventDefault(); submit(); }}>
				<input class="input input-bordered" placeholder={$_('auth.firstname')} bind:value={firstname} required />
				<input class="input input-bordered" placeholder={$_('auth.lastname')} bind:value={lastname} required />
				<input type="email" class="input input-bordered" placeholder={$_('auth.email')} bind:value={email} required />
				<input type="password" class="input input-bordered" placeholder={$_('auth.password')} bind:value={password} required />
				<button type="submit" class="btn btn-primary" disabled={loading}>
					{loading ? $_('common.loadingEllipsis') : $_('auth.createAdmin')}
				</button>
			</form>
		</div>
	</div>
</div>
