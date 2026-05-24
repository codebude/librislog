	<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { broadcastLogout, currentUser, csrfToken } from '$lib/stores/auth';
	import { _ } from '$lib/i18n';
	import { cycleTheme, applyThemeToDocument, saveThemeToStorage, getThemeMode, getThemeIcon, getCustomTheme, getThemeVersion } from '$lib/stores/theme';
	import { Sun, Moon, Palette } from '@lucide/svelte';

	let { floating = true }: { floating?: boolean } = $props();

	let open = $state(false);
	let themeIcon = $state(getThemeIcon());
	let themeMode = $state(getThemeMode());
	let themeVersion = $state(getThemeVersion());
	const user = $derived($currentUser);
	const initials = $derived(
		user ? `${user.firstname.charAt(0)}${user.lastname.charAt(0)}`.toUpperCase() : '??'
	);

	const themeLabel = $derived.by(() => {
		void themeVersion;
		switch (themeMode) {
			case 'light': return $_('settings.themeLight');
			case 'dark': return $_('settings.themeDark');
			case 'custom': return getCustomTheme() ? getCustomTheme()!.charAt(0).toUpperCase() + getCustomTheme()!.slice(1) : $_('settings.themeCustom');
		}
	});

	function onMenuToggle() {
		if (!open) {
			themeIcon = getThemeIcon();
			themeMode = getThemeMode();
			themeVersion = getThemeVersion();
		}
		open = !open;
	}

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

	async function toggleTheme() {
		cycleTheme();
		themeIcon = getThemeIcon();
		themeMode = getThemeMode();
		themeVersion = getThemeVersion();
		applyThemeToDocument();
		saveThemeToStorage();
		if ($currentUser) {
			try {
				const mode = getThemeMode();
				await api.profile.updateSettings({
					theme: mode,
					custom_theme: mode === 'custom' ? getCustomTheme() : null,
				});
			} catch {
				// silent fail — localStorage is primary
			}
		}
	}
</script>

<div class="{floating ? 'fixed top-4 right-4 z-50' : 'relative'}">
	<button
		type="button"
		class="btn btn-ghost btn-circle"
		onclick={onMenuToggle}
		aria-label={$_('user.menu')}
	>
		<div class="w-9 h-9 rounded-full bg-primary text-primary-content text-xs grid place-items-center font-semibold">
			{initials}
		</div>
	</button>

	{#if open}
		<ul
			tabindex="-1"
			class="menu menu-sm dropdown-content absolute right-0 mt-3 w-40 rounded-xl bg-base-100 shadow z-50 p-2"
		>
			<li><a href="/profile" onclick={() => (open = false)}>{$_('user.profile')}</a></li>
			<li><a href="/about" onclick={() => (open = false)}>{$_('user.about')}</a></li>
			<li><hr class="menu-divider opacity-30 mt-2 mb-2 rounded-none" style="padding: 0;"></li>
			<li>
				<button type="button" class="cursor-pointer flex items-center gap-2" onclick={toggleTheme}>
					{#if themeIcon === 'Sun'}<Sun class="w-4 h-4" />
					{:else if themeIcon === 'Moon'}<Moon class="w-4 h-4" />
					{:else}<Palette class="w-4 h-4" />
					{/if}
					<span>{$_('user.theme')}: {themeLabel}</span>
				</button>
			</li>
			<li><hr class="menu-divider opacity-30 mt-2 mb-2 rounded-none" style="padding: 0;"></li>
			<li><button type="button" class="cursor-pointer" onclick={logout}>{$_('user.logout')}</button></li>
		</ul>
	{/if}
</div>
