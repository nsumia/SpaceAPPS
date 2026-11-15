// Tree-shaken ECharts: only the chart types/components this app uses (line, scatter, grid, legend, tooltip, markLine,
// label layout, canvas renderer). Imported only by lazy chunks (Charts, ComparePage), so it stays out of the main bundle.
import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, ScatterChart } from "echarts/charts";
import { GraphicComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";
import EChartsReactCore from "echarts-for-react/lib/core";
import type { EChartsReactProps } from "echarts-for-react/lib/types";

// Shared dark "Earth observation" theme: navy tooltips, Inter, tabular look. Chart-specific colours live in palette.ts / Charts.tsx.
echarts.registerTheme("earth", {
  textStyle: { fontFamily: "Inter Variable, system-ui, sans-serif" },
  tooltip: { backgroundColor: "#050d15", borderColor: "#35607e", borderWidth: 1, textStyle: { color: "#e8f1f7", fontSize: 12 }, extraCssText: "box-shadow:0 6px 22px rgba(0,0,0,.5);border-radius:8px;" },
});
echarts.use([LineChart, ScatterChart, GraphicComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent, LabelLayout, CanvasRenderer]);

// the package is CommonJS: depending on the bundler the default import is the component or { default: component }
const Core: React.ComponentType<any> = (EChartsReactCore as any).default ?? EChartsReactCore;

/** Wrapper that also re-fits the chart whenever its container width changes (e.g. the side panel is expanded or dragged). */
export default function ReactECharts(props: EChartsReactProps) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<any>(null);
  useEffect(() => {
    if (!box.current || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => { try { chart.current?.getEchartsInstance?.().resize(); } catch { /* disposed */ } });
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);
  return <div ref={box} style={{ width: "100%" }}><Core ref={chart} echarts={echarts} theme="earth" {...props} /></div>;
}
