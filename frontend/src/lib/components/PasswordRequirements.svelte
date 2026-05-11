<script lang="ts">
	import { _ } from '$lib/i18n';
	import {
		complexityRequirementLabels,
		getPasswordChecks,
		passwordChecksPassed,
		passwordStrengthClass,
		passwordStrengthPercent
	} from '$lib/password';

	let { password = '' } = $props<{ password: string }>();

	const checks = $derived(getPasswordChecks(password));
	const requirements = $derived(complexityRequirementLabels((key) => $_(key)));
	const passed = $derived(passwordChecksPassed(checks));
	const percent = $derived(passwordStrengthPercent(checks));
	const progressClass = $derived(passwordStrengthClass(checks));
</script>

<div class="rounded-lg border border-base-300 bg-base-200/60 p-3 flex flex-col gap-2">
	<div class="flex items-center justify-between text-xs">
		<span class="font-medium">{$_('password.requirementsTitle')}</span>
		<span class={`badge badge-xs ${passed ? 'badge-success' : 'badge-warning'}`}>
			{passed ? $_('password.strongEnough') : $_('password.notReady')}
		</span>
	</div>
	<progress class={`progress w-full ${progressClass}`} value={percent} max="100"></progress>
	<ul class="grid grid-cols-1 sm:grid-cols-2 gap-1 text-xs">
		{#each requirements as requirement}
			<li class="flex items-center gap-2">
				<span class={`badge badge-xs ${checks[requirement.key] ? 'badge-success' : 'badge-error'}`}>
					{checks[requirement.key] ? '✓' : '✕'}
				</span>
				<span class={checks[requirement.key] ? 'text-success' : 'text-base-content/80'}>{requirement.label}</span>
			</li>
		{/each}
	</ul>
</div>
