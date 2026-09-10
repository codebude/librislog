<script lang="ts">
	import AdaptiveDateInput from '$lib/components/AdaptiveDateInput.svelte';
	import { _ } from '$lib/i18n';
	import {
		PUBLIC_PROFILE_SECTIONS,
		PUBLIC_PROFILE_STATISTICS,
		PUBLIC_PROFILE_STATISTICS_GROUPS,
		defaultPublicProfileVisibilityConfig,
		type PublicProfileStatisticsGroup
	} from '$lib/publicProfile/sections';
	import { toDateInputValue, today } from '$lib/date';
	import { getTimezone } from '$lib/stores/timezone';
	import type {
		PublicProfileAudience,
		PublicProfileLink,
		PublicProfileSectionKey,
		PublicProfileStatisticsKey,
		PublicProfileVisibilityConfig
	} from '$lib/types';
	import { Globe, Info, Lock } from '@lucide/svelte';

	let {
		open = $bindable(false),
		link = null,
		onSave,
		onClose
	}: {
		open?: boolean;
		link?: PublicProfileLink | null;
		onSave: (payload: {
			name: string;
			audience: PublicProfileAudience;
			visibility_config: PublicProfileVisibilityConfig;
			expires_at: string | null;
		}) => void;
		onClose: () => void;
	} = $props();

	let name = $state('');
	let audience = $state<PublicProfileAudience>('public');
	let sections = $state<PublicProfileSectionKey[]>([]);
	let statistics = $state<PublicProfileStatisticsKey[]>([]);
	let unlimited = $state(true);
	let expiresValue = $state('');
	let expiresInvalid = $state(false);
	let expiresHasInput = $state(false);
	let tz = $state('UTC');
	let dialogEl = $state<HTMLDialogElement | null>(null);
	let nameTouched = $state(false);

	function resetFromLink(value: PublicProfileLink | null) {
		const defaults = defaultPublicProfileVisibilityConfig();
		if (value) {
			name = value.name;
			audience = value.audience;
			sections = [...value.visibility_config.sections];
			statistics = [...value.visibility_config.statistics];
			unlimited = !value.expires_at;
			expiresValue = value.expires_at ? toDateInputValue(value.expires_at, tz) : '';
		} else {
			name = '';
			audience = 'public';
			sections = [...defaults.sections];
			statistics = [...defaults.statistics];
			unlimited = true;
			expiresValue = '';
		}
		expiresInvalid = false;
		expiresHasInput = false;
		nameTouched = false;
	}

	$effect(() => {
		if (typeof window !== 'undefined') {
			tz = getTimezone();
		}
		if (open) {
			resetFromLink(link);
		}
	});

	$effect(() => {
		if (!open) return;
		dialogEl?.querySelector<HTMLInputElement>('#share-link-name')?.focus();
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				e.preventDefault();
				onClose();
			}
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	function onBackdropClick(e: MouseEvent) {
		if (e.target === dialogEl) {
			onClose();
		}
	}

	function toggleSection(key: PublicProfileSectionKey) {
		if (sections.includes(key)) {
			sections = sections.filter((s) => s !== key);
			if (key === 'statistics') {
				statistics = [];
			}
		} else {
			sections = [...sections, key];
			if (key === 'statistics' && statistics.length === 0) {
				statistics = [
					...PUBLIC_PROFILE_STATISTICS.filter((s) => s.defaultOn).map((s) => s.key)
				];
			}
		}
	}

	function toggleStatistic(key: PublicProfileStatisticsKey) {
		statistics = statistics.includes(key)
			? statistics.filter((s) => s !== key)
			: [...statistics, key];
	}

	function allSectionsSelected(): boolean {
		return PUBLIC_PROFILE_SECTIONS.every((s) => sections.includes(s.key));
	}

	function setAllSections(checked: boolean) {
		sections = checked
			? PUBLIC_PROFILE_SECTIONS.map((s) => s.key)
			: [];
		if (!checked) {
			statistics = [];
		}
	}

	function statsForGroup(group: PublicProfileStatisticsGroup) {
		return PUBLIC_PROFILE_STATISTICS.filter((s) => s.group === group);
	}

	function allStatsInGroupSelected(group: PublicProfileStatisticsGroup): boolean {
		const groupKeys = statsForGroup(group).map((s) => s.key);
		return groupKeys.length > 0 && groupKeys.every((k) => statistics.includes(k));
	}

	function setAllStatsInGroup(group: PublicProfileStatisticsGroup, checked: boolean) {
		const groupKeys = statsForGroup(group).map((s) => s.key);
		statistics = checked
			? [...new Set([...statistics, ...groupKeys])]
			: statistics.filter((k) => !groupKeys.includes(k));
	}

	function handleSave() {
		if (!name.trim()) return;
		if (!unlimited && (expiresInvalid || expiresValue.length !== 10)) return;
		let expires_at: string | null = null;
		if (!unlimited && expiresValue.length === 10) {
			expires_at = new Date(expiresValue + 'T23:59:59').toISOString();
		}
		onSave({
			name: name.trim(),
			audience,
			visibility_config: { sections, statistics },
			expires_at
		});
	}
</script>

{#if open}
	<dialog
		class="modal modal-open"
		bind:this={dialogEl}
		onclick={onBackdropClick}
		aria-modal="true"
		aria-label={link ? $_('publicProfile.dialogTitleEdit') : $_('publicProfile.dialogTitleCreate')}
	>
		<div class="modal-box w-11/12 max-w-2xl max-h-[90vh] overflow-y-auto">
			<form method="dialog">
				<button class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onclick={onClose} aria-label={$_('common.close')}>✕</button>
			</form>
			<h3 class="font-bold text-lg">{link ? $_('publicProfile.dialogTitleEdit') : $_('publicProfile.dialogTitleCreate')}</h3>

			<form class="flex flex-col gap-6 mt-4" onsubmit={(e) => { e.preventDefault(); handleSave(); }}>
				<div>
<label class="label" for="share-link-name">
					<span class="label-text font-medium">{$_('publicProfile.dialogName')} <span class="text-error">*</span></span>
				</label>
				<input
					id="share-link-name"
					class="input w-full {nameTouched && !name.trim() ? 'input-error' : 'input-bordered'}"
					name="share-link-name"
						bind:value={name}
						autocomplete="off"
						maxlength="255"
						required
						placeholder={$_('publicProfile.dialogNamePlaceholder')}
						onblur={() => { nameTouched = true; }}
					/>
					{#if nameTouched && !name.trim()}
						<p class="text-xs text-error mt-1">{$_('common.required')}</p>
					{/if}
				</div>

				<fieldset class="border border-base-300 rounded-xl p-4">
					<legend class="px-1 text-sm font-semibold">{$_('publicProfile.accessGroup')}</legend>
					<div class="flex flex-col gap-2">
						<label class="flex items-center gap-3 cursor-pointer border border-base-200 rounded-lg p-3">
							<input type="radio" class="radio radio-primary" name="share-link-audience" bind:group={audience} value="public" />
							<div class="flex items-center gap-2 flex-1 min-w-0">
								<Globe class="w-4 h-4 shrink-0 text-base-content/60" />
								<span class="text-sm font-medium">{$_('publicProfile.audiencePublic')}</span>
							</div>
							<span class="tooltip tooltip-left" data-tip={$_('publicProfile.audiencePublicTooltip')}><Info class="w-3.5 h-3.5 text-base-content/40" /></span>
						</label>
						<label class="flex items-center gap-3 cursor-pointer border border-base-200 rounded-lg p-3">
							<input type="radio" class="radio radio-primary" name="share-link-audience" bind:group={audience} value="authenticated" />
							<div class="flex items-center gap-2 flex-1 min-w-0">
								<Lock class="w-4 h-4 shrink-0 text-base-content/60" />
								<span class="text-sm font-medium">{$_('publicProfile.audienceAuthenticated')}</span>
							</div>
							<span class="tooltip tooltip-left" data-tip={$_('publicProfile.audienceAuthenticatedTooltip')}><Info class="w-3.5 h-3.5 text-base-content/40" /></span>
						</label>
					</div>
				</fieldset>

				<fieldset class="border border-base-300 rounded-xl p-4">
					<legend class="px-1 text-sm font-semibold">{$_('publicProfile.contentGroup')}</legend>
					<div class="flex items-center justify-between mb-1">
						<span class="text-xs text-base-content/60">{$_('publicProfile.selectAllSections')}</span>
						<div class="flex gap-1">
							<button type="button" class="btn btn-xs btn-ghost" onclick={() => setAllSections(true)}>{$_('publicProfile.selectAllSections')}</button>
							<button type="button" class="btn btn-xs btn-ghost" onclick={() => setAllSections(false)}>{$_('publicProfile.selectNoneSections')}</button>
						</div>
					</div>
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-1">
						{#each PUBLIC_PROFILE_SECTIONS as def}
							<label class="flex items-center gap-2 text-sm cursor-pointer min-w-0">
								<input
									type="checkbox"
									class="checkbox checkbox-sm"
									name="share-link-section"
									value={def.key}
									checked={sections.includes(def.key)}
									onchange={() => toggleSection(def.key)}
								/>
								<span class="truncate">{$_(def.i18nKey)}</span>
								<span class="tooltip tooltip-right ml-auto" data-tip={$_(def.tooltipKey)}><Info class="w-3.5 h-3.5 text-base-content/40 shrink-0" /></span>
							</label>
						{/each}
					</div>

					{#if sections.includes('statistics')}
						<div class="mt-4 border-t border-base-200 pt-3">
							{#each PUBLIC_PROFILE_STATISTICS_GROUPS as group}
								<div class="flex items-center gap-2 mb-1">
									<span class="text-sm font-semibold text-base-content/70">{$_(group.labelKey)}</span>
									<button
										type="button"
										class="btn btn-xs btn-ghost"
										onclick={() => setAllStatsInGroup(group.group, !allStatsInGroupSelected(group.group))}
									>
										{allStatsInGroupSelected(group.group) ? $_('publicProfile.selectNoneStats') : $_('publicProfile.selectAllStats')}
									</button>
								</div>
								<div class="grid grid-cols-1 sm:grid-cols-2 gap-1 mb-2">
									{#each statsForGroup(group.group) as stat}
										<label class="flex items-center gap-2 text-sm cursor-pointer min-w-0">
											<input
												type="checkbox"
												class="checkbox checkbox-xs"
												name="share-link-statistic"
												value={stat.key}
												checked={statistics.includes(stat.key)}
												onchange={() => toggleStatistic(stat.key)}
											/>
											<span class="truncate">{$_(stat.i18nKey)}</span>
										</label>
									{/each}
								</div>
							{/each}
						</div>
					{/if}
				</fieldset>

				<fieldset class="border border-base-300 rounded-xl p-4">
					<legend class="px-1 text-sm font-semibold">{$_('publicProfile.validityGroup')}</legend>
					<div class="flex flex-col gap-3">
						<label class="flex items-center gap-3 cursor-pointer">
							<input type="radio" class="radio radio-primary" name="share-link-validity" bind:group={unlimited} value={true} />
							<span class="text-sm font-medium">{$_('publicProfile.unlimited')}</span>
						</label>
						<label class="flex items-center gap-3 cursor-pointer">
							<input type="radio" class="radio radio-primary" name="share-link-validity" bind:group={unlimited} value={false} />
							<span class="text-sm font-medium">{$_('publicProfile.validUntil')}</span>
						</label>
						<div class="pl-7">
							<AdaptiveDateInput
								inputClass="input input-bordered max-w-56"
								name="share-link-expires"
								bind:value={expiresValue}
								bind:invalid={expiresInvalid}
								bind:hasInput={expiresHasInput}
								min={today(tz)}
								disabled={unlimited}
								ariaLabel={$_('publicProfile.validUntil')}
							/>
							{#if !unlimited && expiresInvalid && expiresHasInput}
								<p class="text-xs text-error mt-1">{$_('error.invalidDate')}</p>
							{/if}
						</div>
					</div>
				</fieldset>

				<div class="modal-action m-0 pt-2">
					<button type="button" class="btn" onclick={onClose}>{$_('common.cancel')}</button>
					<button
						type="submit"
						class="btn btn-primary"
						disabled={!name.trim() || (!unlimited && (expiresInvalid || expiresValue.length !== 10))}
					>
						{$_('common.save')}
					</button>
				</div>
			</form>
		</div>
	</dialog>
{/if}