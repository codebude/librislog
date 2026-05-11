<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { currentUser, setAuthKey } from '$lib/stores/auth';
	import { _ } from '$lib/i18n';

	let open = $state(false);
	const user = $derived($currentUser);
	const initials = $derived(
		user ? `${user.firstname.charAt(0)}${user.lastname.charAt(0)}`.toUpperCase() : '??'
	);

	async function logout() {
		try {
			await api.auth.logout();
		} catch {
			// local logout still proceeds when server logout fails
		}
		setAuthKey(null);
		currentUser.set(null);
		open = false;
		await goto('/login');
	}
</script>

<div class="fixed top-4 right-4 z-50">
	<button
		type="button"
		class="btn btn-ghost btn-circle"
		onclick={() => (open = !open)}
		aria-label={$_('user.menu')}
	>
		<div class="w-9 h-9 rounded-full bg-primary text-primary-content text-xs grid place-items-center font-semibold">
			{initials}
		</div>
	</button>

	{#if open}
		<div class="absolute right-0 mt-2 w-40 rounded-box border border-base-200 bg-base-100 shadow z-50 p-1 origin-top-right">
			<a class="btn btn-ghost btn-sm justify-start w-full" href="/profile" onclick={() => (open = false)}>{$_('user.profile')}</a>
			<button type="button" class="btn btn-ghost btn-sm justify-start w-full" onclick={logout}>{$_('user.logout')}</button>
		</div>
	{/if}
</div>
