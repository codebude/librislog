<script lang="ts">
	import { version, gitSha } from '$lib/version';
	import { _ } from '$lib/i18n';
	import type { UpdateInfo } from '$lib/stores/updateCheck';

	let { updateInfo = null }: { updateInfo?: UpdateInfo | null } = $props();

	const knownSha = gitSha && gitSha !== 'unknown';
	const isPreRelease = version.includes('-');

	const displayVersion = knownSha && isPreRelease
		? `${version}+${gitSha.slice(0, 7)}`
		: version;

	const href = knownSha && isPreRelease
		? `https://github.com/codebude/librislog/commit/${gitSha}`
		: knownSha
			? `https://github.com/codebude/librislog/releases/tag/${version}`
			: null;

	const tooltip = $derived.by(() => {
		if (!updateInfo) return '';
		return $_('toasts.newVersion', { values: { version: updateInfo.latestVersion } });
	});
</script>

<span class="inline-flex items-center gap-1">
	{#if href}
		<a {href} target="_blank" rel="noopener noreferrer" class="hover:underline">{displayVersion}</a>
	{:else}
		{displayVersion}
	{/if}
	{#if updateInfo}
		<div class="tooltip tooltip-right" data-tip={tooltip}>
			<a href={updateInfo.releaseUrl} target="_blank" rel="noopener noreferrer" aria-label={tooltip}>
				<span class="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"></span>
			</a>
		</div>
	{/if}
</span>
