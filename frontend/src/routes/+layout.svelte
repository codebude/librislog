<script lang="ts">
	import '../app.css';
	import '$lib/chartjs/register';
	import { page } from '$app/stores';
	import { onDestroy, onMount } from 'svelte';
	import AddBookModal from '$lib/components/AddBookModal.svelte';
	import Logo from '$lib/components/Logo.svelte';
	import Toaster from '$lib/components/Toaster.svelte';
	import UserMenu from '$lib/components/UserMenu.svelte';
	import { api } from '$lib/api';
	import { currentUser, csrfToken, loadAuthFromStorage, initAuthSync } from '$lib/stores/auth';
	import { _, setupI18n } from '$lib/i18n';
	import { setTimezone, setQuoteServiceEnabled } from '$lib/stores/timezone';
	import { loadThemeFromStorage, applyThemeToDocument, setThemeMode, setCustomTheme, saveThemeToStorage, sanitizeThemeMode, THEME_MODE_KEY } from '$lib/stores/theme';
	import { LayoutDashboard, BookOpen, ScrollText, BarChart3, Settings, CloudDownload } from '@lucide/svelte';
	import { version } from '$lib/version';
	import VersionLink from '$lib/components/VersionLink.svelte';
	import { checkForUpdate, type UpdateInfo } from '$lib/stores/updateCheck';
	import { toasts } from '$lib/toasts';
	import '@fontsource/inter/300.css';
	import '@fontsource/inter/400.css';
	import '@fontsource/inter/500.css';
	import '@fontsource/inter/600.css';
	import '@fontsource/inter/700.css';

	let { children } = $props();

	if (typeof window !== 'undefined') {
		loadThemeFromStorage();
		applyThemeToDocument();
	}

	let addBookOpen = $state(false);
	let i18nReady = $state(false);
	let authReady = $state(false);
	let backendReady = $state(false);
	let versionInterval: ReturnType<typeof setInterval> | undefined;
	let updateInfo: UpdateInfo | null = $state(null);
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

	async function waitForBackend(): Promise<void> {
		for (let i = 0; i < 30; i++) {
			try {
				const res = await fetch('/api/auth/setup-required');
				if (res.ok) return;
			} catch {
				// backend not ready yet
			}
			await new Promise(r => setTimeout(r, 2000));
		}
	}

		onMount(async () => {
		initAuthSync(() => {
			currentUser.set(null);
			csrfToken.set(null);
			window.location.href = '/login';
		});

		loadAuthFromStorage();
		await setupI18n();
		i18nReady = true;

		// Wait for backend on login/setup/oidc routes so the page doesn't
		// render before the server is ready (e.g. OIDC config fetch).
		const path = $page.url.pathname;
		if (path.startsWith('/login') || path.startsWith('/setup') || path.startsWith('/auth/oidc')) {
			await waitForBackend();
		}
		backendReady = true;
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
					if (settings.theme) {
						const dbMode = sanitizeThemeMode(settings.theme);
						const storedMode = localStorage.getItem(THEME_MODE_KEY);
						const storedCustom = localStorage.getItem('custom_theme');
						if (!storedMode || storedMode !== dbMode || storedCustom !== (settings.custom_theme ?? null)) {
							setThemeMode(dbMode);
							setCustomTheme(settings.custom_theme);
							applyThemeToDocument();
							saveThemeToStorage();
						}
					}
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

		// Version change detection: poll for new deployments
		const checkVersion = async () => {
			try {
				const res = await fetch('/version.json');
				if (!res.ok) return;
				const data: { version?: string } = await res.json();
				if (data.version && data.version !== version) {
					toasts.add(
						$_('toasts.newVersion', { values: { version: data.version } }),
						'info',
						120000,
						{ label: $_('toasts.reload'), onClick: () => window.location.reload() }
					);
				}
			} catch {
				// network errors, retry later
			}
		};
		checkVersion();
		versionInterval = setInterval(checkVersion, 300000);

		checkForUpdate().then(info => { updateInfo = info; });
	});

	onDestroy(() => clearInterval(versionInterval));

	const NAV_ITEMS = $derived.by(() => {
		const items = [
			{ href: '/dashboard', labelKey: 'nav.dashboard', Icon: LayoutDashboard },
			{ href: '/library', labelKey: 'nav.library', Icon: BookOpen },
			{ href: '/timeline', labelKey: 'nav.timeline', Icon: ScrollText },
			{ href: '/statistics', labelKey: 'nav.statistics', Icon: BarChart3 }
		];
		if ($currentUser?.role === 'admin') {
			items.push({ href: '/admin', labelKey: 'admin.title', Icon: Settings });
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

		if ($page.url.pathname.startsWith('/data') && !$page.url.pathname.startsWith('/data-hygiene')) {
			return `${$_('app.title')} - ${$_('nav.data')}`;
		}

		if ($page.url.pathname.startsWith('/data-hygiene')) {
			return `${$_('app.title')} - ${$_('dataHygiene.title')}`;
		}

		if ($page.url.pathname.startsWith('/admin')) {
			return `${$_('app.title')} - ${$_('admin.title')}`;
		}

		if ($page.url.pathname.startsWith('/about')) {
			return `${$_('app.title')} - ${$_('user.about')}`;
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

{#if !i18nReady}
	<div class="min-h-screen bg-base-200 flex items-center justify-center">
		<span class="loading loading-spinner loading-lg"></span>
	</div>
{:else if !backendReady}
	<div class="min-h-screen bg-base-200 flex flex-col items-center justify-center gap-4 px-4">
		<Logo class="w-20 h-20" />
		<div class="text-center">
			<p class="text-lg font-medium">{$_('common.serverStarting')}</p>
			<p class="text-sm text-base-content/60 mt-1">{$_('common.serverStartingDesc')}</p>
		</div>
		<span class="loading loading-spinner loading-md"></span>
	</div>
{:else if !authReady}
	<div class="min-h-screen bg-base-200 flex items-center justify-center">
		<span class="loading loading-spinner loading-lg"></span>
	</div>
{:else if !showAppChrome || isPublicAuthRoute}
	{@render children()}
{:else}
<div class="min-h-screen bg-base-200 flex">
	<!-- Floating user menu (desktop) -->
	<div class="hidden md:block">
		<UserMenu {updateInfo} />
	</div>
	<!-- Sidebar (desktop) -->
	<aside class="hidden md:flex flex-col w-56 bg-base-100 shadow-md fixed top-0 left-0 h-full z-30 p-4 gap-4">
		<a href="/" class="flex items-center gap-2 py-2 px-1">
			<Logo class="w-8 h-8" />
			<div class="text-xl font-bold tracking-tight">{$_('app.title')}</div>
		</a>
		<nav class="flex flex-col gap-1 flex-1">
			{#each NAV_ITEMS as item}
				<a
					href={item.href}
					class="btn btn-ghost btn-sm justify-start gap-2 font-normal rounded-xl"
				>
					<item.Icon class="w-4 h-4" />{$_(item.labelKey)}
				</a>
			{/each}
		</nav>
		<div class="flex items-center gap-2 text-[10px] text-base-content/40 px-1 mt-auto">
			<a
				href="https://github.com/codebude/librislog"
				target="_blank"
				rel="noopener noreferrer"
				class="link link-neutral"
				aria-label="GitHub"
			>
				<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
					<path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12 24 5.37 18.63 0 12 0"/>
				</svg>
			</a>
			<span><VersionLink {updateInfo} /></span>
		</div>
	</aside>

	<!-- Main content -->
	<div class="flex-1 flex flex-col md:ml-56 min-h-screen min-w-0">
		<!-- Mobile top bar with navbar -->
		<div class="navbar md:hidden bg-base-100 shadow-sm sticky top-0 z-20">
			<div class="navbar-start">
				<a href="/" class="btn btn-ghost text-lg px-3 py-2">
					<Logo class="w-10 h-10 shrink-0" />
					<span class="font-bold tracking-tight hidden sm:inline">{$_('app.title')}</span>
				</a>
			</div>
			<div class="navbar-end gap-1">
				<UserMenu floating={false} {updateInfo} />
			</div>
		</div>

		<!-- Page content -->
		<main class="flex-1 p-4 pb-24 sm:pr-24 md:p-8 md:pb-4">
			{@render children()}
		</main>

		<!-- Mobile bottom tab bar -->
		<nav class="md:hidden fixed bottom-0 left-0 right-0 bg-base-100 border-t border-base-200 z-20 flex">
			{#each NAV_ITEMS as item}
				<a
					href={item.href}
					class="flex flex-col items-center justify-center flex-1 py-2 text-xs gap-0.5 text-base-content/60 hover:text-base-content"
				>
					<item.Icon class="w-5 h-5" />
					<span>{$_(item.labelKey)}</span>
				</a>
			{/each}
		</nav>
	</div>
</div>
{/if}

<AddBookModal bind:open={addBookOpen} onAdded={() => {}} />
<Toaster />
