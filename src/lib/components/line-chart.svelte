<script lang="ts">
  import { LineChart } from "layerchart";
  import { scaleUtc } from "d3-scale";
  import { curveLinear } from "d3-shape";
  import * as Chart from "$lib/components/ui/chart/index.js";

  let {
    data,
    yVar,
    config,
    yDomain,
    formatDate = (v: Date) =>
      v.toLocaleDateString("en-US", { weekday: "short", day: "numeric" }),
  }: {
    data: any[];
    yVar: string;
    config?: Chart.ChartConfig;
    yDomain?: [number, number];
    formatDate?: (v: Date) => string;
  } = $props();

  const defaultConfig = {
    desktop: { label: "Desktop", color: "var(--theme-accent-strong)" },
  } satisfies Chart.ChartConfig;

  let activeConfig = $derived(config ?? defaultConfig);
</script>

<LineChart
  {data}
  x="date"
  y={yVar}
  yDomain={yDomain}
  xScale={scaleUtc()}
  yPadding={[10, 10]}
  yNice={true}
  axis={true}
  points={true}
  grid={true}
  series={[
    {
      key: "value",
      label: activeConfig.desktop?.label ?? "Value",
      color: activeConfig.desktop?.color ?? "var(--theme-accent-strong)",
    },
  ]}
  props={{
    spline: { curve: curveLinear, motion: "tween", strokeWidth: 2 },
    xAxis: {
      format: formatDate,
    },
    yAxis: {
      format: (v: number) => String(v),
    },
    highlight: { points: { r: 5 } },
  }}
>
  {#snippet tooltip()}
    <Chart.Tooltip hideLabel />
  {/snippet}
</LineChart>
