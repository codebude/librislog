<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" class={className}>
	<!-- Book cover -->
	<path
		d="M 18 22
		   L 82 18
		   Q 88 18 88 24
		   L 88 76
		   Q 88 82 82 82
		   L 18 86
		   Q 12 86 12 80
		   L 12 28
		   Q 12 22 18 22 Z"
		class="fill-neutral"
	/>
	<!-- Pages (top edge) -->
	<path
		d="M 18 22
		   L 82 18
		   Q 86 18 86 22
		   L 86 24
		   Q 86 28 82 28
		   L 18 32
		   Q 14 32 14 28
		   L 14 26
		   Q 14 22 18 22 Z"
		class="fill-base-100"
	/>
	<!-- Spine highlight -->
	<path
		d="M 12 28
		   L 12 80
		   Q 12 86 18 86
		   L 20 86
		   Q 14 86 14 80
		   L 14 28
		   Q 14 22 20 22
		   L 18 22
		   Q 12 22 12 28 Z"
		class="fill-neutral/70"
	/>
	<!-- Bookmark -->
	<path
		d="M 50 18
		   L 62 16
		   L 62 42
		   L 56 36
		   L 50 42
		   Z"
		class="fill-primary"
	/>
	<!-- Text lines on cover -->
	<rect x="22" y="44" width="44" height="6" rx="3" class="fill-neutral/40" />
	<rect x="22" y="56" width="36" height="6" rx="3" class="fill-neutral/40" />
	<rect x="22" y="68" width="28" height="6" rx="3" class="fill-neutral/40" />
	<!-- Checkmark badge background -->
	<circle cx="74" cy="70" r="16" class="fill-primary" />
	<!-- Checkmark -->
	<path
		d="M 65 70
		   L 71 76
		   L 83 64"
		fill="none"
		stroke-width="4"
		stroke-linecap="round"
		stroke-linejoin="round"
		class="stroke-primary-content"
	/>
</svg>

<script lang="ts">
	let { class: className = 'w-8 h-8' }: { class?: string } = $props();
</script>
