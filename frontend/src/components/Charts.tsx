// Charts: tree-shaken ECharts wrapper (only the chart types this app uses) and the lake-panel charts.
import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, ScatterChart } from "echarts/charts";
import { GraphicComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";
import EChartsReactCore from "echarts-for-react/lib/core";
import type { EChartsReactProps } from "echarts-for-react/lib/types";
import type { EChartsOption } from "echarts";
import { C, FONT, LST5 } from "../lib/util";
import { useI18n, type TFn } from "../i18n";
import type { Forecast, LakeFull } from "../lib/api";

// Shared chart theme: flat near-black tooltip, the page font.
echarts.registerTheme("earth", {
  textStyle: { fontFamily: FONT },
  tooltip: { backgroundColor: "#0a0a0a", borderColor: "#7d7d7d", borderWidth: 1, textStyle: { color: "#ffffff", fontSize: 12 }, extraCssText: "box-shadow:none;border-radius:0;" },
});
echarts.use([LineChart, ScatterChart, GraphicComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent, LabelLayout, CanvasRenderer]);

// the package is CommonJS: depending on the bundler the default import is the component or { default: component }
const Core: React.ComponentType<any> = (EChartsReactCore as any).default ?? EChartsReactCore;

/** Wrapper that also re-fits the chart whenever its container width changes (e.g. the side panel is expanded or dragged). */
export function ReactECharts(props: EChartsReactProps) {
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

/** Years that rest on a single Landsat scene are drawn hollow and say "1 scene" in the tooltip. */
export const oneScene = (r: { n_scenes?: number | null }) => r.n_scenes != null && r.n_scenes <= 1;
const pt = (r: { year: number; n_scenes?: number | null }, v: number | null | undefined) =>
  oneScene(r) ? { value: [r.year, v], n: 1, symbol: "emptyCircle", symbolSize: 8, itemStyle: { borderWidth: 2 } } : { value: [r.year, v] };
const sceneTooltip = (t: TFn) => (ps: any) => {
  const arr = (Array.isArray(ps) ? ps : [ps]).filter((p) => p.value && p.value[1] != null && p.seriesName && p.seriesType === "line" && !p.componentType?.startsWith?.("markLine"));
  if (!arr.length) return "";
  return `${arr[0].value[0]}<br/>` + arr.map((p: any) => `${p.marker} ${p.seriesName}: ${Number(p.value[1]).toFixed(1)}${p.data?.n === 1 ? ` (${t("tip.1scene")})` : ""}`).join("<br/>");
};

const base = (t: TFn, yName: string): EChartsOption => ({
  backgroundColor: "transparent", textStyle: { color: C.text },
  grid: { left: 56, right: 18, top: 38, bottom: 78 },
  legend: { bottom: 0, textStyle: { color: C.muted, fontSize: 11 }, itemWidth: 14 },
  tooltip: { trigger: "axis" },
  xAxis: { type: "value", name: t("ax.year"), nameLocation: "middle", nameGap: 24, min: "dataMin", max: "dataMax", scale: true,
    axisLabel: { color: C.muted, formatter: (v: number) => String(v) }, axisLine: { lineStyle: { color: C.grid } }, splitLine: { show: false } },
  yAxis: { type: "value", name: yName, nameTextStyle: { color: C.muted, align: "left" }, scale: true,
    axisLabel: { color: C.muted }, splitLine: { lineStyle: { color: C.grid } } },
});

function Frame({ title, source, children, note, help }: { title: string; source: string; children: React.ReactNode; note?: React.ReactNode; help?: string }) {
  const { t } = useI18n();
  return (
    <section className="chart">
      <h4>{title}</h4>
      {help && <p className="what" data-testid="chart-help"><strong>{t("what")}:</strong> {help}</p>}
      {children}
      <div className="src">{source}</div>
      {note}
    </section>
  );
}

export function areaOption(d: LakeFull, t: TFn): EChartsOption {
  const rows = d.series.filter((r) => r.area_km2 != null);
  const a = d.stats?.area, em = d.stats?.area_emergence;
  const b = base(t, t("ax.area"));
  const x0 = rows[0]?.year ?? 1985, x1 = rows[rows.length - 1]?.year ?? 2025;
  const series: any[] = [];
  if (em && em.ref_mean != null && em.threshold != null) {            // natural variability band: ref mean +/- k sigma
    const lo = em.ref_mean - em.threshold, hi = em.ref_mean + em.threshold;
    series.push({ name: t("ser.band"), type: "line", data: [[x0, lo], [x1, lo]], showSymbol: false, silent: true, lineStyle: { opacity: 0 }, stack: "band", tooltip: { show: false } });
    series.push({ name: t("ser.band"), type: "line", data: [[x0, hi - lo], [x1, hi - lo]], showSymbol: false, silent: true, lineStyle: { opacity: 0 }, stack: "band",
      areaStyle: { color: C.climate, opacity: 0.22 }, tooltip: { show: false } });
  }
  series.push({ name: t("ser.observed"), type: "line", data: rows.map((r) => pt(r, r.area_km2)), color: C.water, symbolSize: 5, lineStyle: { width: 2 },
    markLine: em?.year != null ? { symbol: "none", lineStyle: { color: C.emergence, type: "dashed" }, data: [{ xAxis: em.year,
      label: { formatter: t(em.censored_at_ref_end ? "em.by" : "em.at", { year: em.year }), color: C.emergence, position: "insideEndTop" } }] } : undefined });
  if (a) series.push({ name: t("ser.sen"), type: "line", showSymbol: false, color: C.loss, lineStyle: { type: "dashed", width: 2 },
    data: [x0, x1].map((y) => [y, a.intercept + a.sen_slope_per_year * (y - a.intercept_year)]) });
  return { ...b, series, tooltip: { trigger: "axis", formatter: sceneTooltip(t) }, legend: { ...(b.legend as object), data: [t("ser.observed"), t("ser.sen"), t("ser.band")] } };
}

export function lstOption(d: LakeFull, t: TFn): EChartsOption {
  const rows = d.series.filter((r) => r.lst_c != null);
  const l5 = d.stats?.lst_1985_2012;
  const b = base(t, t("ax.temp"));
  const series: any[] = [{ name: t("ser.lst"), type: "line", data: rows.map((r) => pt(r, r.lst_c)), color: C.temp, symbolSize: 5,
    markLine: { symbol: "none", lineStyle: { color: C.muted, type: "dotted" }, data: [{ xAxis: 2012.5, label: { formatter: "Landsat 5 | 8", color: C.muted, position: "insideEndTop" } }] } }];
  if (l5) series.push({ name: t("ser.lst5"), type: "line", showSymbol: false, color: LST5, lineStyle: { type: "dashed" },
    data: [1985, 2012].map((y) => [y, l5.intercept + l5.sen_slope_per_year * (y - l5.intercept_year)]) });
  return { ...b, series, tooltip: { trigger: "axis", formatter: sceneTooltip(t) } };
}

export function climateOption(dec: NonNullable<NonNullable<LakeFull["climate"]>["decomposition"]>, t: TFn): EChartsOption {
  const yrs = dec.years ?? [], o = dec.cum_observed_loss_km2 ?? [], p = dec.cum_predicted_loss_km2 ?? [];
  const lo = o.map((v, i) => Math.min(v, p[i])), gap = o.map((v, i) => Math.abs(v - p[i]));
  const b = base(t, t("ax.loss"));
  return { ...b, series: [
    { name: t("ser.gap"), type: "line", stack: "g", data: yrs.map((y, i) => [y, lo[i]]), showSymbol: false, lineStyle: { opacity: 0 }, tooltip: { show: false } },
    { name: t("ser.gap"), type: "line", stack: "g", data: yrs.map((y, i) => [y, gap[i]]), showSymbol: false, lineStyle: { opacity: 0 }, areaStyle: { color: C.emergence, opacity: 0.3 }, tooltip: { show: false } },
    { name: t("ser.observed"), type: "line", data: yrs.map((y, i) => [y, o[i]]), color: C.water, symbolSize: 4, lineStyle: { width: 2 } },
    { name: t("ser.predicted"), type: "line", data: yrs.map((y, i) => [y, p[i]]), color: C.climate, symbolSize: 4, lineStyle: { type: "dashed", width: 2 } },
  ] };
}

/** Forecast chart: observed area, then the median forecast (dashed) inside its 50 % and 90 % bands. Bands start at the last observation. */
export function forecastOption(d: LakeFull, f: Forecast, t: TFn): EChartsOption {
  const mv = d.min_valid ?? 0.8;
  const rows = d.series.filter((r) => r.area_km2 != null && (r.valid_frac ?? 1) >= mv);
  const yrs = f.years ?? [], y0 = f.last_observed_year!, v0 = f.last_observed_km2!;
  const line = (a: number[] = []) => [[y0, v0], ...yrs.map((y, i) => [y, a[i]])];
  const band = (name: string, lo: number[] = [], hi: number[] = [], opacity: number): any[] => [
    { name, type: "line", stack: name, data: line(lo), showSymbol: false, silent: true, color: C.waterPale, lineStyle: { opacity: 0 }, tooltip: { show: false } },
    { name, type: "line", stack: name, data: [[y0, 0], ...yrs.map((y, i) => [y, hi[i] - lo[i]])], showSymbol: false, silent: true, color: C.waterPale, lineStyle: { opacity: 0 },
      areaStyle: { color: C.waterPale, opacity }, tooltip: { show: false } }];
  const b = base(t, t("ax.area"));
  const tip = (ps: any) => {
    const arr = Array.isArray(ps) ? ps : [ps], year = arr[0]?.value?.[0], i = yrs.indexOf(year);
    if (i < 0) return sceneTooltip(t)(arr.filter((p: any) => p.seriesName === t("ser.observed")));
    return `${year}<br/>${t("ser.fc.median")}: ${f.median![i].toFixed(1)}<br/>${t("ser.fc.b50")}: ${f.lo50![i].toFixed(1)} - ${f.hi50![i].toFixed(1)}<br/>${t("ser.fc.b90")}: ${f.lo90![i].toFixed(1)} - ${f.hi90![i].toFixed(1)}`;
  };
  return { ...b, yAxis: { ...(b.yAxis as object), scale: false, min: 0 }, tooltip: { trigger: "axis", formatter: tip },
    legend: { ...(b.legend as object), data: [t("ser.observed"), t("ser.fc.median"), t("ser.fc.b50"), t("ser.fc.b90")] },
    series: [
      ...band(t("ser.fc.b90"), f.lo90, f.hi90, 0.16), ...band(t("ser.fc.b50"), f.lo50, f.hi50, 0.3),
      { name: t("ser.observed"), type: "line", data: rows.map((r) => pt(r, r.area_km2)), color: C.water, symbolSize: 5, lineStyle: { width: 2 },
        markLine: { symbol: "none", silent: true, lineStyle: { color: C.muted, type: "dotted" }, data: [{ xAxis: y0 + 0.5, label: { formatter: t("fc.starts") + " →", color: C.muted, position: "end", rotate: 0, align: "left", padding: [0, 0, 0, 4] } }] } },
      { name: t("ser.fc.median"), type: "line", data: line(f.median), showSymbol: false, color: C.waterPale, lineStyle: { type: "dashed", width: 2 } },
    ] };
}

/** Template text for the forecast (no AI): numbers are printed only when the forecast is interpretable. */
export function forecastSentences(f: Forecast, s: LakeFull["summary"], t: TFn): string[] {
  if (!f.ok) return [t(`fc.na.${f.reason ?? "other"}`)];
  const out: string[] = [], bt = f.backtest, flags = f.flags ?? [], m = (f.milestones ?? []).at(-1);
  const cov = bt?.coverage90 == null ? "?" : Math.round(100 * bt.coverage90);
  if (!f.interpretable) out.push(t("fc.narrow", { cov }));
  else if (m) {
    const rf = s.ref_years ?? [1985, 1990];
    out.push(t(f.model === "persistence" ? "fc.flat" : "fc.trend", { year: m.year, med: m.median_km2.toFixed(0), lo: m.lo90_km2.toFixed(0), hi: m.hi90_km2.toFixed(0) })
      + (m.median_pct_of_ref != null ? " " + t("fc.pct", { pct: Math.round(m.median_pct_of_ref), r0: rf[0], r1: rf[1] }) : ""));
    if (flags.includes("trend_not_distinguishable_from_zero")) out.push(t("fc.zero"));
    if (bt) out.push(t(f.model === "persistence" ? "fc.test.flat" : "fc.test", { skill: Math.round(100 * bt.chosen_skill), cov, h: bt.max_horizon_years, n: bt.n_pairs }));
  }
  if (flags.includes("sparse_cadence")) out.push(t("fc.sparse"));
  return out;
}

export function ForecastChart({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  const f = d.forecast;
  if (!f || f.preliminary) return null;
  return (
    <Frame title={t("chart.forecast", { year: f.horizon_year })} help={t("help.forecast")} source={t("chart.source.forecast")}
      note={<><div className="chart-text" data-testid="forecast-text">{forecastSentences(f, d.summary, t).join(" ")}</div>
        <div className="note warn small">{t("fc.caveat")}</div></>}>
      {f.ok ? <ReactECharts option={forecastOption(d, f, t)} style={{ height: 270 }} notMerge /> : (
        <div className="na" role="status"><strong>{t("fc.none")}</strong></div>)}
    </Frame>
  );
}

export function AreaChart({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  const em = d.stats?.area_emergence;
  return (
    <Frame title={t("chart.area")} help={t("help.area")} source={t("chart.source.landsat")}
      note={<>{em?.censored_at_ref_end ? <div className="note small">{em.censored_note}</div> : null}
        {d.series.some(oneScene) ? <div className="small muted" data-testid="onescene-note">{t("chart.onescene")}</div> : null}</>}>
      <ReactECharts option={areaOption(d, t)} style={{ height: 260 }} notMerge />
    </Frame>
  );
}

export function LstChart({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  return (
    <Frame title={t("chart.lst")} help={t("help.lst")} source={t("chart.source.landsat")} note={<><div className="note small">{t("lst.break")}.</div><details className="small muted"><summary>{t("tech.note")}</summary>{d.lst.note}</details></>}>
      <ReactECharts option={lstOption(d, t)} style={{ height: 240 }} notMerge />
    </Frame>
  );
}

export function ClimateChart({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  const dec = d.climate?.decomposition;
  // always show the observed vs climate-predicted curves when they exist (no numeric "share explained" is printed here)
  const ok = !!dec && dec.ok && !!dec.years?.length;
  return (
    <Frame title={t("chart.climate")} help={t("help.climate")} source={t("chart.source.climate")}
      note={<div className="note small">{t("climate.note")} {d.climate?.evaporation_label}</div>}>
      {ok && dec ? <ReactECharts option={climateOption(dec, t)} style={{ height: 260 }} notMerge /> : (
        <div className="na" role="status"><strong>{t("na.data")}</strong></div>)}
    </Frame>
  );
}

export function VolumeChart({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  const v = d.volume;
  const opt: EChartsOption | null = v && v.length ? { ...base(t, t("ax.dv")), series: [
    { name: t("ax.dv"), type: "line", color: C.water, data: v.map((r) => ({ value: [r.year, r.dV_km3], itemStyle: { opacity: r.extrapolated ? 0.4 : 1 } })) }] } : null;
  return (
    <Frame title={t("chart.volume")} help={t("help.volume")} source={t("chart.source.swot")}>
      {opt ? <ReactECharts option={opt} style={{ height: 230 }} notMerge /> : (
        <div className="na" role="status"><strong>{t("volume.none")}</strong><div className="small">{d.swot?.reason ?? ""}</div></div>)}
    </Frame>
  );
}
