<script lang="ts">
	import generateAvatar from 'animal-avatar-generator';
	
	let {
		seed,
		size = 36,
		class: className = ''
	}: {
		seed: string;
		size?: number;
		class?: string;
	} = $props();

	// Muted, desaturated palettes matching the librislog calmreader theme
	const avatarSvg = $derived(
		generateAvatar(seed, {
			size,
			round: true,
			blackout: true,
			avatarColors: ['#8a9aae', '#9a8b82', '#8a9a8a', '#889a96', '#968a9a', '#8294a0'],
			backgroundColors: ['#edeae6', '#e6e3df', '#e4e7e5', '#e8e6ea', '#e5e8e5']
		})
	);
</script>

<div class="{className} rounded-full overflow-hidden ring-2 ring-primary">
	{@html avatarSvg}
</div>
