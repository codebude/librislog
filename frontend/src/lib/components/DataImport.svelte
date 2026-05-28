<script lang="ts">
	import { onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import { api } from '$lib/api';
	import { toasts } from '$lib/toasts';
	import ImportMappingEditor from '$lib/components/ImportMappingEditor.svelte';
	import { highlightJson } from '$lib/utils/prism';
	import type {
		DataImportEvent,
		DataImportMappingListItem,
		DataImportParseResponse,
		DataImportValidateResponse,
		DataImportPreviewResponse,
		ImportFieldConfig
	} from '$lib/types';

	let selectedFile = $state<File | null>(null);
	let parsing = $state(false);
	let parsed = $state<DataImportParseResponse | null>(null);
	let mapping = $state<Record<string, ImportFieldConfig>>({});
	let dbFields = $state<string[]>([]);
	let preview = $state<DataImportPreviewResponse | null>(null);
	let loadingPreview = $state(false);
	let validating = $state(false);
	let validation = $state<DataImportValidateResponse | null>(null);
	let importMode = $state<'rollback_all' | 'continue_on_error'>('rollback_all');
	let importing = $state(false);
	let importProgress = $state(0);
	let importTotal = $state(0);
	let importProcessed = $state(0);
	let importResult = $state<{ imported: number; failed: number; failures: Array<{ row: number; error: string }> } | null>(null);
	let createProgressForRead = $state(false);
	let mappingName = $state('');
	let mappings = $state<DataImportMappingListItem[]>([]);
	let loadingMappings = $state(false);
	let selectedMappingId = $state('');
	let selectedMappingIsPredefined = $derived(mappings.find((m) => String(m.id) === selectedMappingId)?.is_predefined ?? false);
	let showAllValidation = $state(false);
	let showAllFailures = $state(false);
	let importAbortController = $state<AbortController | null>(null);
	let dragging = $state(false);
	let fileInput: HTMLInputElement | undefined = $state();
	let pendingDeleteMappingId = $state<number | null>(null);
	let pendingImportStart = $state(false);
	let previewMappingSnapshot = $state<string | null>(null);
	let isPreviewStale = $derived(previewMappingSnapshot !== null && previewMappingSnapshot !== JSON.stringify(mapping));

	function resetFlow() {
		parsed = null;
		mapping = {};
		dbFields = [];
		validation = null;
		importing = false;
		importProgress = 0;
		importProcessed = 0;
		importTotal = 0;
		importResult = null;
		showAllValidation = false;
		showAllFailures = false;
	}

	async function refreshMappings() {
		loadingMappings = true;
		try {
			mappings = await api.data.listMappings();
		} catch (err: unknown) {
			toasts.add(err instanceof Error ? err.message : $_('data.import.errors.loadMappingsFailed'), 'error');
		} finally {
			loadingMappings = false;
		}
	}

	onMount(() => {
		void refreshMappings();
	});

	async function parseFile() {
		if (!selectedFile) return;
		parsing = true;
		validation = null;
		importResult = null;
		try {
			parsed = await api.data.parseImportFile(selectedFile);
			const suggest = await api.data.suggestMapping(parsed.file_id);
			mapping = suggest.suggested_mapping;
			dbFields = suggest.db_fields;
			await refreshMappings();
		} catch (err: unknown) {
			toasts.add(err instanceof Error ? err.message : $_('data.import.errors.parseFailed'), 'error');
		} finally {
			parsing = false;
		}
	}

	async function saveMapping() {
		if (!parsed || !mappingName.trim()) return;
		try {
			const saved = await api.data.saveMapping({
				name: mappingName.trim(),
				source_fields: parsed.source_fields,
				mapping
			});
			mappingName = '';
			selectedMappingId = String(saved.id);
			await refreshMappings();
			toasts.add($_('data.import.mappingSaved'), 'success');
		} catch (err: unknown) {
			toasts.add(err instanceof Error ? err.message : $_('data.import.errors.saveMappingFailed'), 'error');
		}
	}

	let missingMappingFields = $state<Array<{ target: string; source: string }>>([]);

	async function loadMapping(id: number) {
		try {
			const saved = await api.data.getMapping(id);
			mapping = saved.mapping;
			missingMappingFields = Object.entries(saved.mapping)
				.filter(([, config]) => config.source && !parsed?.source_fields.includes(config.source))
				.map(([target, config]) => ({ target, source: config.source }));
			if (!saved.is_predefined) {
				mappingName = saved.name;
			}
		} catch (err: unknown) {
			toasts.add(err instanceof Error ? err.message : $_('data.import.errors.loadMappingFailed'), 'error');
		}
	}

	async function loadSelectedMapping() {
		const id = Number(selectedMappingId);
		if (!Number.isFinite(id) || id === 0) return;
		await loadMapping(id);
	}

	function openDeleteMappingModal() {
		const id = Number(selectedMappingId);
		if (!Number.isFinite(id) || id === 0 || selectedMappingIsPredefined) return;
		pendingDeleteMappingId = id;
	}

	function closeDeleteMappingModal() {
		pendingDeleteMappingId = null;
	}

	async function confirmDeleteMapping() {
		const id = pendingDeleteMappingId;
		if (!id || id <= 0) return;
		try {
			await api.data.deleteMapping(id);
			selectedMappingId = '';
			closeDeleteMappingModal();
			await refreshMappings();
			toasts.add($_('data.import.mappingDeleted'), 'success');
		} catch (err: unknown) {
			toasts.add(err instanceof Error ? err.message : $_('data.import.errors.deleteMappingFailed'), 'error');
		}
	}

	async function simulate() {
		if (!parsed) return;
		validating = true;
		try {
			validation = await api.data.validateImport({ file_id: parsed.file_id, mapping, create_progress_for_read: createProgressForRead });
			showAllValidation = false;
		} catch (err: unknown) {
			toasts.add(err instanceof Error ? err.message : $_('data.import.errors.validateFailed'), 'error');
		} finally {
			validating = false;
		}
	}

	function openImportModal() {
		if (!parsed) return;
		pendingImportStart = true;
	}

	function closeImportModal() {
		pendingImportStart = false;
	}

	async function confirmImport() {
		if (!parsed) return;
		pendingImportStart = false;
		importing = true;
		importResult = null;
		importProgress = 0;
		importTotal = 0;
		importProcessed = 0;
		showAllFailures = false;
		importAbortController?.abort();
		importAbortController = new AbortController();
		try {
			for await (const event of api.data.executeImport({
				file_id: parsed.file_id,
				mapping,
				import_mode: importMode,
				create_progress_for_read: createProgressForRead,
				signal: importAbortController.signal
			})) {
				handleImportEvent(event);
			}
		} catch (err: unknown) {
			if (err instanceof Error && err.name === 'AbortError') {
				toasts.add($_('data.import.cancelled'), 'error');
			} else {
				toasts.add(err instanceof Error ? err.message : $_('data.import.errors.executeFailed'), 'error');
			}
		} finally {
			importAbortController = null;
			importing = false;
		}
	}

	function cancelImport() {
		importAbortController?.abort();
	}

	$effect(() => {
		return () => {
			importAbortController?.abort();
		};
	});

	function handleImportEvent(event: DataImportEvent) {
		if (event.event === 'start') {
			importTotal = event.total_rows;
			importProcessed = 0;
			importProgress = 0;
			return;
		}
		if (event.event === 'progress') {
			importProcessed = event.processed;
			importTotal = event.total;
			importProgress = event.percent;
			return;
		}
		if (event.event === 'complete') {
			importProgress = 100;
			importResult = {
				imported: event.imported,
				failed: event.failed,
				failures: event.failures.map((item) => ({ row: item.row, error: item.error }))
			};
			toasts.add($_('data.import.completed', { values: { imported: event.imported, failed: event.failed } }), 'success');
			return;
		}
		const message = event.message.startsWith('error.') ? $_(event.message) : event.message;
		toasts.add(message, 'error');
	}

	const visibleWarnings = $derived.by(() => {
		if (!validation) return [];
		return showAllValidation ? validation.warnings : validation.warnings.slice(0, 8);
	});

	const visibleErrors = $derived.by(() => {
		if (!validation) return [];
		return showAllValidation ? validation.errors : validation.errors.slice(0, 8);
	});

	const visibleFailures = $derived.by(() => {
		if (!importResult) return [];
		return showAllFailures ? importResult.failures : importResult.failures.slice(0, 8);
	});

	function formatError(err: string): string {
		if (err.startsWith('\x1f')) {
			const idx = err.indexOf('\x1f', 1);
			if (idx !== -1) {
				const field = err.slice(1, idx);
				const error = err.slice(idx + 1);
				return $_('data.import.transformError', { values: { field, error } });
			}
		}
		return err;
	}

	async function fetchPreview() {
		if (!parsed) return;
		loadingPreview = true;
		try {
			preview = await api.data.previewImport({ file_id: parsed.file_id, mapping });
			previewMappingSnapshot = JSON.stringify(mapping);
		} catch (err: unknown) {
			toasts.add(err instanceof Error ? err.message : $_('data.import.errors.previewFailed'), 'error');
		} finally {
			loadingPreview = false;
		}
	}

	function resetPreview() {
		preview = null;
		previewMappingSnapshot = null;
	}
</script>

<div class="grid gap-4 min-w-0">
	<div class="card bg-base-100 border border-base-200 shadow-sm min-w-0">
		<div class="card-body gap-3 min-w-0">
			<h2 class="card-title">{$_('data.import.title')}</h2>
			<p class="text-sm text-base-content/70">{$_('data.import.description')}</p>
			<div class="flex flex-wrap items-center gap-2">
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					role="button"
					tabindex={0}
					class="border-2 border-dashed rounded-lg p-4 text-center text-sm text-base-content/50 transition-colors flex-1 min-w-64
						{dragging ? 'border-primary bg-primary/10' : 'border-base-300'}
						cursor-pointer hover:border-primary"
					ondragover={(e) => { e.preventDefault(); dragging = true; }}
					ondragleave={() => (dragging = false)}
					ondrop={(e) => {
						e.preventDefault();
						dragging = false;
						const file = e.dataTransfer?.files?.[0];
						if (file) {
							selectedFile = file;
							resetFlow();
						}
					}}
					onclick={() => fileInput?.click()}
					onkeydown={(e) => e.key === 'Enter' && fileInput?.click()}
				>
					{#if selectedFile}
						<p class="text-base-content">{selectedFile.name}</p>
					{:else}
						<p>{$_('data.import.dropzone')} <span class="text-primary font-medium">{$_('data.import.browse')}</span></p>
					{/if}
				</div>
				<input
					bind:this={fileInput}
					type="file"
					name="import-file"
					class="hidden"
					accept=".csv,.json"
					aria-label={$_('data.import.fileInputLabel')}
					onchange={(e) => {
						selectedFile = e.currentTarget.files?.[0] ?? null;
						resetFlow();
					}}
				/>
				<button class="btn btn-primary btn-sm" onclick={parseFile} disabled={!selectedFile || parsing}>
					{parsing ? $_('data.import.parsing') : $_('data.import.parse')}
				</button>
			</div>
			{#if parsed}
				<p class="text-xs text-base-content/60 flex items-center gap-2">
					<span>{$_('data.import.fileSummary', { values: { rows: parsed.row_count, fields: parsed.source_fields.length } })}</span>
					<button class="btn btn-ghost btn-xs" onclick={() => { resetFlow(); selectedFile = null; if (fileInput) fileInput.value = ''; }}>{$_('data.import.changeFile')}</button>
				</p>
			{/if}
		</div>
	</div>

	{#if parsed}
		<div class="card bg-base-100 border border-base-200 shadow-sm min-w-0">
		<div class="card-body gap-3 min-w-0">
				<h3 class="font-semibold">{$_('data.import.mappingTitle')}</h3>
				<div class="rounded-lg border border-base-200 bg-base-200/30 p-3 space-y-3">
					<p class="text-sm font-semibold text-base-content">{$_('data.import.mappingActionsTitle')}</p>
					<div class="grid md:grid-cols-[1fr_auto] gap-2 items-end">
						<label class="form-control">
							<span class="label-text text-xs">{$_('data.import.mappingName')}</span>
							<input class="input input-bordered input-sm" name="mapping-name" bind:value={mappingName} />
						</label>
						<button class="btn btn-outline btn-sm" onclick={saveMapping} disabled={!mappingName.trim()}>
							{$_('data.import.saveMapping')}
						</button>
					</div>

					<div class="grid md:grid-cols-[1fr_auto_auto] gap-2 items-end">
						<label class="form-control">
							<span class="label-text text-xs">{$_('data.import.loadSavedMapping')}</span>
							<select class="select select-bordered select-sm" name="load-mapping" bind:value={selectedMappingId} disabled={mappings.length === 0}>
								<option value="">{$_('data.import.selectMapping')}</option>
								{#each mappings as item}
									<option value={String(item.id)}>
										{item.is_predefined ? `${item.name} (${$_('data.import.readonlyMapping')})` : item.name}
									</option>
								{/each}
							</select>
						</label>
						<button class="btn btn-outline btn-sm" onclick={loadSelectedMapping} disabled={!selectedMappingId}>
							{$_('data.import.loadMapping')}
						</button>
						<button class="btn btn-outline btn-error btn-sm" onclick={openDeleteMappingModal} disabled={!selectedMappingId || selectedMappingIsPredefined}>
							{$_('data.import.deleteMapping')}
						</button>
					</div>
					{#if missingMappingFields.length > 0}
						<div class="alert alert-warning text-sm p-3 flex items-start gap-2">
							<div class="flex-1">
								<p class="font-medium">{$_('data.import.missingFieldsTitle')}</p>
								<ul class="list-disc pl-4 mt-1 text-xs">
									{#each missingMappingFields as m}
										<li>{$_('data.import.missingFieldEntry', { values: { target: m.target, source: m.source } })}</li>
									{/each}
								</ul>
							</div>
							<button class="btn btn-ghost btn-xs btn-square shrink-0" onclick={() => (missingMappingFields = [])} aria-label={$_('common.close')}>✕</button>
						</div>
					{/if}
					{#if mappings.length === 0}
						<p class="text-xs text-base-content/60">{$_('data.import.noSavedMappings')}</p>
					{/if}
				</div>

				<div class="min-w-0">
					<ImportMappingEditor sourceFields={parsed.source_fields} {dbFields} {mapping} onChange={(next) => (mapping = next)} />
				</div>
			</div>
		</div>

		<div class="card bg-base-100 border border-base-200 shadow-sm min-w-0">
			<div class="card-body gap-3">
				<div class="flex flex-wrap items-center gap-2">
					<h3 class="font-semibold">{$_('data.import.previewTitle')}</h3>
					<button class="btn btn-outline btn-sm" onclick={fetchPreview} disabled={loadingPreview}>
						{loadingPreview ? $_('data.import.previewLoading') : $_('data.import.previewButton')}
					</button>
					{#if isPreviewStale}
						<span class="badge badge-warning badge-sm">{$_('data.import.previewStale')}</span>
					{/if}
				</div>
				{#if preview}
					{#if (preview.errors ?? []).length > 0}
						<div class="alert alert-warning text-sm">
							{#each preview.errors ?? [] as err}
								<p>{formatError(err)}</p>
							{/each}
						</div>
					{/if}
					{#each preview.preview_rows as row}
						<div class="border border-base-200 rounded-lg p-3">
							<p class="text-xs font-semibold text-base-content/60 mb-2">{$_('data.import.previewRow', { values: { row: row.row_number } })}</p>
							<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
								<div>
									<p class="text-xs text-base-content/50 mb-1">{$_('data.import.previewSource')}</p>
									<pre class="text-xs font-mono bg-base-200 p-2 rounded overflow-x-auto">{@html highlightJson(JSON.stringify(row.source, null, 2))}</pre>
								</div>
								<div>
									<p class="text-xs text-base-content/50 mb-1">{$_('data.import.previewTransformed')}</p>
									<pre class="text-xs font-mono bg-base-200 p-2 rounded overflow-x-auto">{@html highlightJson(JSON.stringify(row.transformed, null, 2))}</pre>
								</div>
							</div>
							{#if (row.errors ?? []).length > 0}
								<div class="mt-2 text-xs text-error">
									{#each row.errors as err}
										<p>• {formatError(err)}</p>
									{/each}
								</div>
							{/if}
						</div>
					{/each}
				{/if}
			</div>
		</div>

		<div class="card bg-base-100 border border-base-200 shadow-sm min-w-0">
			<div class="card-body gap-3">
				<h3 class="font-semibold">{$_('data.import.validationTitle')}</h3>
				<div class="flex flex-wrap gap-2 items-center">
					<button class="btn btn-primary btn-sm" onclick={simulate} disabled={validating}>
						{validating ? $_('data.import.validating') : $_('data.import.simulate')}
					</button>
					<select class="select select-bordered select-sm" name="import-mode" bind:value={importMode}>
						<option value="rollback_all">{$_('data.import.rollbackAll')}</option>
						<option value="continue_on_error">{$_('data.import.continueOnError')}</option>
					</select>
					<label class="label cursor-pointer gap-2">
						<input type="checkbox" class="checkbox checkbox-sm" name="create-progress" bind:checked={createProgressForRead} />
						<span class="label-text text-xs">{$_('data.import.createProgressForRead')}</span>
					</label>
					<button class="btn btn-secondary btn-sm" onclick={openImportModal} disabled={importing || !!(validation && !validation.valid)}>
						{importing ? $_('data.import.importing') : $_('data.import.importNow')}
					</button>
					{#if importing}
						<button class="btn btn-outline btn-sm" onclick={cancelImport}>
							{$_('common.cancel')}
						</button>
					{/if}
				</div>

				{#if validation}
					<div class="text-sm">
						<div class={validation.valid ? 'text-success' : 'text-error'}>
							{validation.valid ? $_('data.import.validationOk') : $_('data.import.validationNotOk')}
						</div>
						{#if validation.warnings.length > 0}
							<ul class="list-disc pl-5 text-warning">
								{#each visibleWarnings as warning}
									<li>{warning}</li>
								{/each}
							</ul>
						{/if}
						{#if validation.errors.length > 0}
							<ul class="list-disc pl-5 text-error">
								{#each visibleErrors as error}
									<li>{formatError(error)}</li>
								{/each}
							</ul>
						{/if}
						{#if validation.warnings.length > 8 || validation.errors.length > 8}
							<button class="btn btn-link btn-xs px-0" onclick={() => (showAllValidation = !showAllValidation)}>
								{showAllValidation
									? $_('data.import.showLess')
									: $_('data.import.showAllIssues', { values: { count: validation.warnings.length + validation.errors.length } })}
							</button>
						{/if}
					</div>
				{/if}

				{#if importing || importResult}
					<progress class="progress progress-primary w-full" value={importProgress} max="100"></progress>
					<p class="text-xs text-base-content/60">{importProcessed}/{importTotal} ({importProgress.toFixed(1)}%)</p>
				{/if}

				{#if importResult}
					<div class="text-sm">
						<p>{$_('data.import.completed', { values: { imported: importResult.imported, failed: importResult.failed } })}</p>
						{#if importResult.failures.length > 0}
							<ul class="list-disc pl-5 text-error">
								{#each visibleFailures as failure}
									<li>{$_('data.import.errorRow', { values: { row: failure.row } })} {formatError(failure.error)}</li>
								{/each}
							</ul>
							{#if importResult.failures.length > 8}
								<button class="btn btn-link btn-xs px-0" onclick={() => (showAllFailures = !showAllFailures)}>
									{showAllFailures
										? $_('data.import.showLess')
										: $_('data.import.showAllFailures', { values: { count: importResult.failures.length } })}
								</button>
							{/if}
						{/if}
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>

<dialog class="modal" class:modal-open={pendingDeleteMappingId !== null}>
	<div class="modal-box">
		<h3 class="text-lg font-bold">{$_('data.import.deleteMappingTitle')}</h3>
		<p class="py-3 text-sm text-base-content/70">{$_('data.import.deleteMappingConfirm')}</p>
		<div class="modal-action">
			<button type="button" class="btn btn-ghost" onclick={closeDeleteMappingModal}>{$_('common.cancel')}</button>
			<button type="button" class="btn btn-error" onclick={confirmDeleteMapping}>{$_('data.import.deleteMapping')}</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button type="button" onclick={closeDeleteMappingModal}>{$_('common.close')}</button>
	</form>
</dialog>

<dialog class="modal" class:modal-open={pendingImportStart}>
	<div class="modal-box">
		<h3 class="text-lg font-bold">{$_('data.import.confirmImportTitle')}</h3>
		<p class="py-3 text-sm text-base-content/70">{$_('data.import.confirmDestructive')}</p>
		<div class="modal-action">
			<button type="button" class="btn btn-ghost" onclick={closeImportModal}>{$_('common.cancel')}</button>
			<button type="button" class="btn btn-secondary" onclick={confirmImport}>{$_('data.import.importNow')}</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button type="button" onclick={closeImportModal}>{$_('common.close')}</button>
	</form>
</dialog>

<style>
	:global(.hl-json-key) { color: #7c3aed; }
	:global(.hl-json-string) { color: #059669; }
	:global(.hl-json-number) { color: #d97706; }
	:global(.hl-json-bool) { color: #2563eb; }
</style>
