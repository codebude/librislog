<script lang="ts">
	import '../app.css';
	import type { ReadingStatus } from '$lib/types';
	import AddBookModal from '$lib/components/AddBookModal.svelte';

	let { children } = $props();

	let addBookOpen = $state(false);

	// Expose a way for pages to trigger open
	// We use context to share this across routes
	import { setContext } from 'svelte';
	setContext('openAddBook', () => (addBookOpen = true));

	const NAV_ITEMS: { status: ReadingStatus; label: string; icon: string }[] = [
		{ status: 'want_to_read', label: 'Want to Read', icon: '📚' },
		{ status: 'currently_reading', label: 'Reading', icon: '📖' },
		{ status: 'read', label: 'Read', icon: '✓' }
	];
</script>

<div class="min-h-screen bg-base-200 flex">
	<!-- Sidebar (desktop) -->
	<aside class="hidden md:flex flex-col w-56 bg-base-100 shadow-md fixed top-0 left-0 h-full z-30 p-4 gap-4">
		<div class="text-xl font-bold tracking-tight py-2 px-1">LibrisLog</div>
		<nav class="flex flex-col gap-1 flex-1">
			{#each NAV_ITEMS as item}
				<a
					href="/?status={item.status}"
					class="btn btn-ghost btn-sm justify-start gap-2 font-normal"
				>
					<span>{item.icon}</span>{item.label}
				</a>
			{/each}
		</nav>
		<button class="btn btn-primary btn-sm" onclick={() => (addBookOpen = true)}>+ Add Book</button>
	</aside>

	<!-- Main content -->
	<div class="flex-1 flex flex-col md:ml-56 min-h-screen">
		<!-- Mobile top bar -->
		<header class="md:hidden flex items-center justify-between px-4 py-3 bg-base-100 shadow-sm sticky top-0 z-20">
			<span class="text-lg font-bold tracking-tight">LibrisLog</span>
			<button class="btn btn-primary btn-sm" onclick={() => (addBookOpen = true)}>+ Add</button>
		</header>

		<!-- Page content -->
		<main class="flex-1 p-4 pb-24 md:pb-4">
			{@render children()}
		</main>

		<!-- Mobile bottom tab bar -->
		<nav class="md:hidden fixed bottom-0 left-0 right-0 bg-base-100 border-t border-base-200 z-20 flex">
			{#each NAV_ITEMS as item}
				<a
					href="/?status={item.status}"
					class="flex flex-col items-center justify-center flex-1 py-2 text-xs gap-0.5 text-base-content/60 hover:text-base-content"
				>
					<span class="text-lg leading-none">{item.icon}</span>
					<span>{item.label}</span>
				</a>
			{/each}
		</nav>
	</div>
</div>

<AddBookModal bind:open={addBookOpen} onAdded={() => {}} />
