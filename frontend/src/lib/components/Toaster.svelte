	<script lang="ts">
	import { _ } from '$lib/i18n';
	import { toasts, type ToastLevel } from '$lib/toasts';
	import { X } from '@lucide/svelte';

	const CLASSES: Record<ToastLevel, string> = {
		error: 'alert-error',
		warning: 'alert-warning',
		success: 'alert-success',
		info: 'alert-info'
	};
</script>

<div class="toast toast-top toast-end z-[100] pointer-events-none">
	{#each $toasts as toast (toast.id)}
		<div class="alert {CLASSES[toast.level]} shadow-lg pointer-events-auto max-w-sm flex-wrap">
			<span class="text-sm">{toast.message}</span>
			<div class="flex gap-1 ml-auto">
				{#if toast.action}
					<button
						class="btn btn-ghost btn-xs"
						onclick={() => { toast.action!.onClick(); toasts.remove(toast.id); }}
					>{toast.action.label}</button>
				{/if}
				<button
					class="btn btn-ghost btn-xs"
					onclick={() => toasts.remove(toast.id)}
					aria-label={$_('toasts.dismiss')}
				><X class="w-4 h-4" /></button>
			</div>
		</div>
	{/each}
</div>
