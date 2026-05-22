<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { broadcastLogout, currentUser, csrfToken } from '$lib/stores/auth';
	import { _ } from '$lib/i18n';

	let { floating = true }: { floating?: boolean } = $props();

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
		currentUser.set(null);
		csrfToken.set(null);
		broadcastLogout();
		open = false;
		await goto('/login');
	}
</script>

<div class="{floating ? 'fixed top-4 right-4 z-50' : 'relative'}">
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
		<ul
			tabindex="-1"
			class="menu menu-sm dropdown-content absolute right-0 mt-3 w-40 rounded-box bg-base-100 shadow z-50 p-2"
		>
			<li><a href="/profile" onclick={() => (open = false)}>{$_('user.profile')}</a></li>
			<li><button type="button" class="cursor-pointer" onclick={logout}>{$_('user.logout')}</button></li>
		</ul>
	{/if}
</div>
