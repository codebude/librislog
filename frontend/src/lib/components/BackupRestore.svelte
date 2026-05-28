<script lang="ts">
	import { _ } from '$lib/i18n';
	import { api } from '$lib/api';
	import { toasts } from '$lib/toasts';
	import { localizeError } from '$lib/errors';

	let backupInProgress = $state(false);
	let restoreFile = $state<File | null>(null);
	let restoreInProgress = $state(false);
	let showRestoreConfirmModal = $state(false);
	let restoreValidation = $state<{ valid: boolean; metadata?: Record<string, unknown>; error?: string } | null>(null);

	async function downloadBackup() {
		backupInProgress = true;
		try {
			const blob = await api.admin.downloadBackup();
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = `librislog-backup-${new Date().toISOString().replace(/:/g, '-').slice(0, 19)}.zip`;
			document.body.appendChild(link);
			link.click();
			link.remove();
			URL.revokeObjectURL(url);
			toasts.add($_('admin.backup.success'), 'success');
		} catch (err: unknown) {
			toasts.add(err instanceof Error ? err.message : $_('admin.backup.failed'), 'error');
		} finally {
			backupInProgress = false;
		}
	}

	async function validateAndConfirmRestore() {
		if (!restoreFile) return;
		try {
			const validation = await api.admin.validateBackup(restoreFile);
			if (validation.valid) {
				restoreValidation = validation;
				showRestoreConfirmModal = true;
			} else {
				toasts.add(validation.error || $_('admin.restore.invalidBackup'), 'error');
			}
		} catch (err: unknown) {
			toasts.add(localizeError(err, $_, $_('admin.restore.validationFailed')), 'error');
		}
	}

	async function executeRestore() {
		if (!restoreFile) return;
		showRestoreConfirmModal = false;
		restoreInProgress = true;
		try {
			const result = await api.admin.restoreBackup(restoreFile);
			toasts.add($_('admin.restore.success', { values: { books: String(result.restored_books) } }), 'success');
			setTimeout(() => window.location.reload(), 2000);
		} catch (err: unknown) {
			toasts.add(localizeError(err, $_, $_('admin.restore.failed')), 'error');
		} finally {
			restoreInProgress = false;
			restoreFile = null;
		}
	}

	function cancelRestore() {
		showRestoreConfirmModal = false;
		restoreValidation = null;
	}
</script>

<div class="flex flex-col gap-6">
	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-4">
			<h2 class="card-title">{$_('admin.backup.title')}</h2>
			<p class="text-sm text-base-content/70">{$_('admin.backup.description')}</p>
			{#if backupInProgress}
				<progress class="progress progress-primary" max="100"></progress>
				<span class="text-sm text-base-content/70">{$_('admin.backup.inProgress')}</span>
			{:else}
				<button class="btn btn-primary btn-sm self-start" onclick={downloadBackup}>
					{$_('admin.backup.download')}
				</button>
			{/if}
		</div>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-4">
			<h2 class="card-title">{$_('admin.restore.title')}</h2>
			<p class="text-sm text-base-content/70">{$_('admin.restore.description')}</p>
			<div class="alert alert-warning text-sm">
				<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
				</svg>
				<span>{$_('admin.restore.warning')}</span>
			</div>
			{#if restoreInProgress}
				<div class="flex flex-col gap-2">
					<progress class="progress progress-primary" max="100"></progress>
					<span class="text-sm text-base-content/70">{$_('admin.restore.inProgress')}</span>
				</div>
			{:else}
				<input
					type="file"
					name="restore-file"
					class="file-input file-input-bordered file-input-sm"
					accept=".zip"
					onchange={(e) => {
						const files = e.currentTarget.files;
						restoreFile = files?.[0] || null;
					}}
				/>
				{#if restoreFile}
					<button class="btn btn-warning btn-sm self-start" onclick={validateAndConfirmRestore}>
						{$_('admin.restore.upload')}
					</button>
				{/if}
			{/if}
		</div>
	</div>
</div>

<dialog class="modal" class:modal-open={showRestoreConfirmModal}>
	<div class="modal-box">
		<h3 class="text-lg font-bold">{$_('admin.restore.confirmTitle')}</h3>
		<p class="py-3 text-sm text-base-content/70">{$_('admin.restore.confirmBody')}</p>
		{#if restoreValidation?.metadata}
			<div class="bg-base-200 rounded p-3 text-xs font-mono mb-3">
				<div>{$_('admin.restore.backupDate')}: {String(restoreValidation.metadata.timestamp ?? '')}</div>
				<div>{$_('admin.restore.backupVersion')}: {String(restoreValidation.metadata.app_version ?? '')}</div>
				<div>{$_('admin.restore.coversCount')}: {String(restoreValidation.metadata.covers_count ?? '')}</div>
			</div>
		{/if}
		<div class="alert alert-error text-sm mb-3">
			<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>
			<span>{$_('admin.restore.confirmWarning')}</span>
		</div>
		<div class="modal-action">
			<button type="button" class="btn btn-ghost" onclick={cancelRestore}>{$_('common.cancel')}</button>
			<button type="button" class="btn btn-warning" onclick={executeRestore}>{$_('admin.restore.confirm')}</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button type="button">{$_('common.close')}</button>
	</form>
</dialog>
