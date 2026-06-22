<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { _ } from 'svelte-i18n';
	import { api } from '$lib/api';
	import Alert from '$lib/components/Alert.svelte';

	let token = $state($page.url.searchParams.get('token') || '');
	let password = $state('');
	let confirmPassword = $state('');
	let loading = $state(false);
	let success = $state(false);
	let error = $state('');

	let noToken = $derived(token.length === 0);

	async function submit() {
		error = '';
		if (password !== confirmPassword) {
			error = $_('common.passwordsDoNotMatch');
			return;
		}
		loading = true;
		try {
			await api.auth.resetPassword({ token, password });
			success = true;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $_('auth.resetPasswordError');
		} finally {
			loading = false;
		}
	}
</script>

<div class="flex items-center justify-center min-h-screen p-4">
	<div class="card bg-base-200 shadow-xl w-full max-w-sm">
		<div class="card-body">
			{#if noToken}
				<div class="alert alert-error mb-4">
					<span>{$_('auth.resetPasswordMissingToken')}</span>
				</div>
				<button class="btn btn-primary btn-block" onclick={() => goto('/login')}>
					{$_('auth.login')}
				</button>
			{:else if success}
				<div class="alert alert-success mb-4">
					<span>{$_('auth.resetPasswordSuccess')}</span>
				</div>
				<button class="btn btn-primary btn-block" onclick={() => goto('/login')}>
					{$_('auth.login')}
				</button>
			{:else}
				<h2 class="card-title mb-4">{$_('auth.resetPasswordTitle')}</h2>
				<p class="text-sm mb-4">{$_('auth.resetPasswordInstruction')}</p>
				{#if error}
					<Alert type="error" onClose={() => (error = '')}>
						{error}
					</Alert>
				{/if}
				<form class="flex flex-col gap-4" onsubmit={(e) => { e.preventDefault(); submit(); }}>
					<label class="form-control">
						<span class="label label-text">{$_('auth.password')}</span>
						<input
							type="password"
							class="input input-bordered w-full"
							bind:value={password}
							autocomplete="new-password"
							required
							disabled={loading}
						/>
					</label>
					<label class="form-control">
						<span class="label label-text">{$_('common.confirmPassword')}</span>
						<input
							type="password"
							class="input input-bordered w-full"
							bind:value={confirmPassword}
							autocomplete="new-password"
							required
							disabled={loading}
						/>
					</label>
					<button type="submit" class="btn btn-primary btn-block" disabled={loading}>
						{loading ? $_('common.loadingEllipsis') : $_('auth.resetPasswordSubmit')}
					</button>
				</form>
			{/if}
		</div>
	</div>
</div>
