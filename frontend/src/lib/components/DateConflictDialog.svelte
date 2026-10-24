<script lang="ts">
	import { _ } from '#lib/i18n/index.js';

	let {
		open = false,
		field = 'date_started',
		existingDate,
		suggestedDate,
		onKeep,
		onUseSuggested,
		onCancel,
		onReread = undefined,
		rereadAvailable = false
	}: {
		open?: boolean;
		field?: 'date_started' | 'date_finished' | 'started_after_finished';
		existingDate: string;
		suggestedDate: string;
		onKeep?: () => void;
		onUseSuggested?: () => void;
		onCancel?: () => void;
		onReread?: () => void;
		rereadAvailable?: boolean;
	} = $props();

	const typeKey = $derived(
		field === 'date_finished' ? 'finished'
		: field === 'started_after_finished' ? 'startedAfterFinished'
		: 'started'
	);

	const i18nValues = $derived(
		typeKey === 'startedAfterFinished'
			? { finishedDate: existingDate, newStartDate: suggestedDate }
			: { oldDate: existingDate, newDate: suggestedDate }
	);

	const keepKey = $derived(
		typeKey === 'startedAfterFinished' ? 'keepFinished' : 'keepOld'
	);

	const useNewKey = $derived(
		typeKey === 'startedAfterFinished' ? 'clearAndStart' : 'useNew'
	);

	// Close on Escape right away — the modal-backdrop only receives key events
	// after it has been clicked, so listen at the window level instead.
	$effect(() => {
		if (!open) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') onCancel?.();
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});
</script>

{#if open}
	<div class="modal modal-open">
		<div class="modal-box max-w-md">
			<h3 class="text-lg font-bold">{$_(`dateConflict.${typeKey}.title`)}</h3>
			<p class="text-sm text-base-content/70 mt-2">
				{#if existingDate === suggestedDate && typeKey !== 'startedAfterFinished'}
					{$_(`dateConflict.${typeKey}.messageSame`, { values: { date: existingDate } })}
				{:else}
					{$_(`dateConflict.${typeKey}.message`, { values: i18nValues })}
				{/if}
			</p>
			<div class="modal-action flex-col sm:flex-row">
				<button type="button" class="btn btn-ghost btn-sm" onclick={onCancel}>{$_('common.cancel')}</button>
				{#if existingDate === suggestedDate && typeKey !== 'startedAfterFinished'}
					<button type="button" class="btn btn-outline btn-sm" onclick={onKeep}>
						{$_(`dateConflict.${typeKey}.${keepKey}`, { values: i18nValues })}
					</button>
				{:else}
					<button type="button" class="btn btn-outline btn-sm" onclick={onKeep}>
						{$_(`dateConflict.${typeKey}.${keepKey}`, { values: i18nValues })}
						{#if typeKey === 'startedAfterFinished'}<sup>1</sup>{/if}
					</button>
					<button type="button" class="btn btn-outline btn-sm" onclick={onUseSuggested}>
						{$_(`dateConflict.${typeKey}.${useNewKey}`, { values: i18nValues })}
						{#if typeKey === 'startedAfterFinished'}<sup>2</sup>{/if}
					</button>
				{/if}
				{#if rereadAvailable && onReread}
					<button type="button" class="btn btn-primary btn-sm" onclick={onReread}>
						{$_('dateConflict.startNewRead')}
					</button>
				{/if}
			</div>
			{#if typeKey === 'startedAfterFinished'}
				<div class="border-t border-base-200 pt-3 mt-2 text-xs text-base-content/50 space-y-1">
					<p><sup>1</sup> {$_(`dateConflict.${typeKey}.keepDesc`, { values: i18nValues })}</p>
					<p><sup>2</sup> {$_(`dateConflict.${typeKey}.clearDesc`, { values: i18nValues })}</p>
				</div>
			{/if}
		</div>
		<div class="modal-backdrop"></div>
	</div>
{/if}
