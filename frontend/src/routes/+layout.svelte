<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import AddBookModal from '$lib/components/AddBookModal.svelte';
	import Toaster from '$lib/components/Toaster.svelte';
	import UserMenu from '$lib/components/UserMenu.svelte';
	import { api } from '$lib/api';
	import { currentUser, csrfToken, loadAuthFromStorage, initAuthSync } from '$lib/stores/auth';
	import { _, setupI18n } from '$lib/i18n';
	import { setTimezone, setQuoteServiceEnabled } from '$lib/stores/timezone';
	import { version, gitSha } from '$lib/version';

	let { children } = $props();

	let addBookOpen = $state(false);
	let i18nReady = $state(false);
	let authReady = $state(false);
	const isPublicAuthRoute = $derived(
		$page.url.pathname.startsWith('/setup') ||
			$page.url.pathname.startsWith('/login') ||
			$page.url.pathname.startsWith('/auth/oidc')
	);
	const showAppChrome = $derived(!isPublicAuthRoute && $currentUser !== null);

	// Expose a way for pages to trigger open
	// We use context to share this across routes
	import { setContext } from 'svelte';
	setContext('openAddBook', () => (addBookOpen = true));

		onMount(async () => {
		initAuthSync(() => {
			currentUser.set(null);
			csrfToken.set(null);
			window.location.href = '/login';
		});

		loadAuthFromStorage();
		await setupI18n();
		i18nReady = true;

		const path = $page.url.pathname;
		const isSetupRoute = path.startsWith('/setup');
		const isLoginRoute = path.startsWith('/login');
		const isOidcCallbackRoute = path.startsWith('/auth/oidc');
		const publicAuthRoute = isSetupRoute || isLoginRoute || isOidcCallbackRoute;

		try {
			const setup = await api.auth.setupRequired();
			if (setup.required && !isSetupRoute) {
				window.location.href = '/setup';
				return;
			}

			if (!setup.required && isSetupRoute) {
				try {
					const me = await api.auth.me();
					currentUser.set(me);
					const csrf = await api.auth.csrf();
					csrfToken.set(csrf.csrf_token);
					window.location.href = '/';
					return;
				} catch {
					currentUser.set(null);
					csrfToken.set(null);
					window.location.href = '/login';
					return;
				}
			}

			if (!setup.required && isLoginRoute) {
				try {
					const me = await api.auth.me();
					currentUser.set(me);
					const csrf = await api.auth.csrf();
					csrfToken.set(csrf.csrf_token);
					window.location.href = '/';
					return;
				} catch {
					currentUser.set(null);
					csrfToken.set(null);
				}
			}

			if (!setup.required && !publicAuthRoute) {
				try {
					const me = await api.auth.me();
					currentUser.set(me);
					const csrf = await api.auth.csrf();
					csrfToken.set(csrf.csrf_token);
					const settings = await api.profile.getSettings();
					setTimezone(settings.timezone);
					setQuoteServiceEnabled(settings.quote_service_enabled);
				} catch {
					csrfToken.set(null);
					window.location.href = '/login';
					return;
				}
			}
		} catch {
			if (!publicAuthRoute) {
				csrfToken.set(null);
				window.location.href = '/login';
				return;
			}
		} finally {
			authReady = true;
		}
	});

	const NAV_ITEMS = $derived.by(() => {
		const items = [
			{ href: '/dashboard', labelKey: 'nav.dashboard', icon: '🏠' },
			{ href: '/library', labelKey: 'nav.library', icon: '📚' },
			{ href: '/timeline', labelKey: 'nav.timeline', icon: '📖' },
			{ href: '/statistics', labelKey: 'nav.statistics', icon: '📊' }
		];
		if ($currentUser?.role === 'admin') {
			items.push({ href: '/admin', labelKey: 'admin.title', icon: '🛠️' });
		}
		return items;
	});

	function pageTitle() {
		if (!i18nReady) return 'LibrisLog';

		if ($page.url.pathname.startsWith('/dashboard')) {
			return `${$_('app.title')} - ${$_('nav.dashboard')}`;
		}

		if ($page.url.pathname.startsWith('/library')) {
			return `${$_('app.title')} - ${$_('nav.library')}`;
		}

		if ($page.url.pathname.startsWith('/api-docs')) {
			return `${$_('app.title')} - ${$_('settings.apiDocsTitle')}`;
		}

		if ($page.url.pathname.startsWith('/timeline')) {
			return `${$_('app.title')} - ${$_('nav.timeline')}`;
		}

		if ($page.url.pathname.startsWith('/statistics')) {
			return `${$_('app.title')} - ${$_('nav.statistics')}`;
		}

		if ($page.url.pathname.startsWith('/data')) {
			return `${$_('app.title')} - ${$_('nav.data')}`;
		}

		if ($page.url.pathname.startsWith('/admin')) {
			return `${$_('app.title')} - ${$_('admin.title')}`;
		}

		if ($page.url.pathname.startsWith('/login')) {
			return `${$_('app.title')} - ${$_('auth.login')}`;
		}

		if ($page.url.pathname.startsWith('/setup')) {
			return `${$_('app.title')} - ${$_('auth.setupTitle')}`;
		}

		return $_('app.title');
	}
</script>

<svelte:head>
	<title>{pageTitle()}</title>
</svelte:head>

{#if !i18nReady || !authReady}
	<div class="min-h-screen bg-base-200 flex items-center justify-center">
		<span class="loading loading-spinner loading-lg"></span>
	</div>
{:else if !showAppChrome || isPublicAuthRoute}
	{@render children()}
{:else}
<div class="min-h-screen bg-base-200 flex">
	<UserMenu />
	<!-- Sidebar (desktop) -->
	<aside class="hidden md:flex flex-col w-56 bg-base-100 shadow-md fixed top-0 left-0 h-full z-30 p-4 gap-4">
		<div class="flex items-center gap-2 py-2 px-1">
			<img src="/logo.png" alt="LibrisLog" class="w-8 h-8 rounded" />
			<div class="text-xl font-bold tracking-tight">{$_('app.title')}</div>
		</div>
		<nav class="flex flex-col gap-1 flex-1">
			{#each NAV_ITEMS as item}
				<a
					href={item.href}
					class="btn btn-ghost btn-sm justify-start gap-2 font-normal"
				>
					<span>{item.icon}</span>{$_(item.labelKey)}
				</a>
			{/each}
		</nav>
		<div class="text-[10px] text-base-content/40 px-1 mt-auto">
			{version}{#if gitSha && gitSha !== 'unknown' && !version.includes(gitSha.slice(0, 7))} ({gitSha.slice(0, 7)}){/if}
		</div>
	</aside>

	<!-- Main content -->
	<div class="flex-1 flex flex-col md:ml-56 min-h-screen">
		<!-- Mobile top bar -->
		<header class="md:hidden flex items-center justify-between px-4 py-3 bg-base-100 shadow-sm sticky top-0 z-20">
			<div class="flex items-center gap-2">
				<img src="/logo.png" alt="LibrisLog" class="w-7 h-7 rounded" />
				<span class="text-lg font-bold tracking-tight">{$_('app.title')}</span>
			</div>
		</header>

		<!-- Page content -->
		<main class="flex-1 p-4 pb-24 sm:pr-24 md:pb-4">
			{@render children()}
		</main>

		<!-- Mobile bottom tab bar -->
		<nav class="md:hidden fixed bottom-0 left-0 right-0 bg-base-100 border-t border-base-200 z-20 flex">
			{#each NAV_ITEMS as item}
				<a
					href={item.href}
					class="flex flex-col items-center justify-center flex-1 py-2 text-xs gap-0.5 text-base-content/60 hover:text-base-content"
				>
					<span class="text-lg leading-none">{item.icon}</span>
					<span>{$_(item.labelKey)}</span>
				</a>
			{/each}
		</nav>
	</div>
</div>
{/if}

<AddBookModal bind:open={addBookOpen} onAdded={() => {}} />
<Toaster />
