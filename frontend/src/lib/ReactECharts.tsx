// Tree-shaken ECharts: only the chart types/components this app uses (line, scatter, grid, legend, tooltip, markLine,
// visualMap, canvas renderer). Imported only by lazy chunks (Charts, ComparePage), so it stays out of the main bundle.
import * as echarts from "echarts/core";
import { LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import EChartsReactCore from "echarts-for-react/lib/core";
import type { EChartsReactProps } from "echarts-for-react/lib/types";

echarts.use([LineChart, ScatterChart, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent, CanvasRenderer]);

// the package is CommonJS: depending on the bundler the default import is the component or { default: component }
const Core: React.ComponentType<any> = (EChartsReactCore as any).default ?? EChartsReactCore;

export default function ReactECharts(props: EChartsReactProps) {
  return <Core echarts={echarts} {...props} />;
}
