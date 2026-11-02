<script lang="ts">
	import AnimalAvatar from '#lib/components/AnimalAvatar.svelte';

	let {
		avatarUrl = null,
		seed,
		size = 36,
		class: className = ''
	}: {
		avatarUrl?: string | null;
		seed: string;
		size?: number;
		class?: string;
	} = $props();

	let failed = $state(false);

	$effect(() => {
		void avatarUrl;
		failed = false;
	});
</script>

{#if avatarUrl && !failed}
	<div class="{className} rounded-full overflow-hidden ring-2 ring-primary">
		<img
			src={avatarUrl}
			alt=""
			width={size}
			height={size}
			class="w-full h-full object-cover"
			referrerpolicy="no-referrer"
			onerror={() => (failed = true)}
		/>
	</div>
{:else}
	<AnimalAvatar {seed} {size} class={className} />
{/if}
