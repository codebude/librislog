<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { currentUser, setAuthKey } from '$lib/stores/auth';
	import { _ } from '$lib/i18n';

	let email = $state('');
	let password = $state('');
	let loading = $state(false);
	let error = $state('');

	async function submit() {
		error = '';
		loading = true;
		try {
			const result = await api.auth.login({ email, password });
			setAuthKey(result.api_key);
			currentUser.set(result.user);
			await goto('/');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $_('auth.loginFailed');
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-screen bg-base-200 grid place-items-center p-4">
	<div class="card bg-base-100 border border-base-200 shadow-sm w-full max-w-md">
		<div class="card-body gap-4">
			<h1 class="text-2xl font-bold">{$_('auth.login')}</h1>
			{#if error}
				<div class="alert alert-error text-sm"><span>{error}</span></div>
			{/if}
			<form class="flex flex-col gap-3" onsubmit={(e) => { e.preventDefault(); submit(); }}>
				<label class="form-control">
					<span class="label label-text">{$_('auth.email')}</span>
					<input type="email" class="input input-bordered" bind:value={email} required disabled={loading} />
				</label>
				<label class="form-control">
					<span class="label label-text">{$_('auth.password')}</span>
					<input type="password" class="input input-bordered" bind:value={password} required disabled={loading} />
				</label>
				<button type="submit" class="btn btn-primary" disabled={loading}>
					{loading ? $_('common.loadingEllipsis') : $_('auth.login')}
				</button>
			</form>
		</div>
	</div>
</div>
