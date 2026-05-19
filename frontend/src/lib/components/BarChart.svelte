<script lang="ts">
  import { BarChart as LayerBarChart } from 'layerchart';

  let {
    labels = [],
    data = [],
    label = '',
    color = 'primary',
    emptyText = 'No data',
    height = 200,
  }: {
    labels: string[];
    data: number[];
    label: string;
    color: string;
    emptyText?: string;
    height?: number;
  } = $props();

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
</script>

{#if data.length === 0}
  <div class="flex items-center justify-center h-40 text-base-content/50">
    <p>{emptyText}</p>
  </div>
{:else}
  <div role="img" aria-label={label}>
    <LayerBarChart
      data={chartData}
      x="label"
      y="value"
      {series}
      {height}
      bandPadding={0.3}
      props={{
        xAxis: { tickSpacing: 80 },
        bars: { strokeWidth: 0, stroke: 'none' }
      }}
    />
  </div>
{/if}
