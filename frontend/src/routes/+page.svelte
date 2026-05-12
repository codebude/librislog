<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	onMount(async () => {
		const status = $page.url.searchParams.get('status');
		if (status) {
			await goto(`/library?status=${status}`, { replaceState: true });
			return;
		}
		await goto('/dashboard', { replaceState: true });
	});
</script>

<div class="min-h-screen bg-base-200 flex items-center justify-center">
	<span class="loading loading-spinner loading-lg"></span>
</div>
