<script lang="ts">
  import { BarChart as LayerBarChart } from 'layerchart';
  import { onMount } from 'svelte';

  let {
    labels = [],
    data = [],
    label = '',
    color = 'primary',
    emptyText = 'No data',
    height = 200,
    transform = { mode: 'domain', axis: 'x' },
  }: {
    labels: string[];
    data: number[];
    label: string;
    color: string;
    emptyText?: string;
    height?: number;
    transform?: Record<string, unknown>;
  } = $props();

  let isTouchDevice = $state(false);
  let chartRef = $state<HTMLDivElement | null>(null);
  let touchTooltip = $state<{ label: string; value: number; x: number; y: number } | null>(null);
  let touchTooltipRef = $state<HTMLDivElement | null>(null);

  onMount(() => {
    isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  });

  function handleBarClick(_event: MouseEvent, detail: { data: { label: string; value: number } }) {
    if (!isTouchDevice) return;
    const barRect = (_event.currentTarget as Element)?.getBoundingClientRect();
    const x = barRect ? barRect.left + barRect.width / 2 : _event.clientX;
    const y = barRect ? barRect.top : _event.clientY;
    touchTooltip = {
      label: detail.data.label,
      value: detail.data.value,
      x,
      y,
    };
  }

  function handleDocumentClick(event: MouseEvent) {
    // Ignore clicks inside the chart — bar clicks are handled by onBarClick
    if (chartRef?.contains(event.target as Node)) return;
    // Ignore clicks inside the tooltip itself
    if (touchTooltipRef?.contains(event.target as Node)) return;
    touchTooltip = null;
  }

  $effect(() => {
    if (labels.length !== data.length) {
      console.warn('BarChart: labels and data length mismatch', labels.length, data.length);
    }
  });

  const varMap: Record<string, string> = {
	primary: '--color-primary',
	secondary: '--color-secondary',
	accent: '--color-accent',
	info: '--color-info',
	success: '--color-success',
	warning: '--color-warning',
	error: '--color-error',
  };

  function resolveColor(name: string): string {
    const varName = varMap[name];
    if (!varName) {
      console.warn(`BarChart: unknown color "${name}", falling back to primary`);
	  return 'var(--color-primary)';
    }
	return `var(${varName})`;
  }

  const len = $derived(Math.min(labels.length, data.length));
  const chartData = $derived(
    Array.from({ length: len }, (_, i) => ({ label: labels[i], value: data[i] ?? 0 }))
  );

  const series = $derived([
    { key: 'default', value: 'value' as const, color: resolveColor(color), label },
  ]);

  const touchStyles = 'touch-action: none; user-select: none; -webkit-user-select: none; -webkit-touch-callout: none';
  const enhancedTransform = $derived(
    transform ? { ...transform, style: touchStyles } : undefined
  );

  let chartKey = $state(0);

  function resetZoom() {
    chartKey++;
  }

</script>

<svelte:document onclick={handleDocumentClick} />

{#if data.length === 0}
  <div class="flex items-center justify-center h-40 text-base-content/50">
    <p>{emptyText}</p>
  </div>
{:else}
  <div role="img" aria-label={label} class="relative select-none" bind:this={chartRef}>
    {#key chartKey}
      <LayerBarChart
        data={chartData}
        x="label"
        y="value"
        {series}
        {height}
        bandPadding={0.3}
        transform={enhancedTransform}
        props={{
          xAxis: { tickSpacing: 80 },
          bars: { strokeWidth: 0, stroke: 'none' }
        }}
        onBarClick={handleBarClick}
      />
    {/key}

    <button
      type="button"
      class="btn btn-ghost btn-xs absolute top-1 right-1 opacity-60 hover:opacity-100"
      title="Reset zoom"
      onclick={resetZoom}
    >
      ↺
    </button>

    {#if touchTooltip}
      {@const tooltipX = touchTooltip.x}
      {@const tooltipY = touchTooltip.y - 48}
      <div
        bind:this={touchTooltipRef}
        class="fixed z-50 rounded px-2 py-1 text-sm shadow-md pointer-events-none"
        style="left: {tooltipX}px; top: {Math.max(8, tooltipY)}px; transform: translateX(-50%);"
        style:background-color="color-mix(in oklab, var(--color-surface-100, white) 90%, transparent)"
        style:color="var(--color-surface-content, currentColor)"
        style:backdrop-filter="blur(2px)"
      >
        <div class="font-medium whitespace-nowrap">{touchTooltip.label}</div>
        <div class="text-xs opacity-75 whitespace-nowrap">{touchTooltip.value}</div>
      </div>
    {/if}
  </div>
{/if}
