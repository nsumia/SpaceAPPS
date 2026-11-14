import { useState } from "react";
import ReactECharts from "../lib/ReactECharts";
import type { EChartsOption } from "echarts";
import { C } from "../lib/palette";
import { useI18n, type TFn } from "../i18n";
import type { LakeFull } from "../lib/types";

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
  grid: { left: 52, right: 14, top: 34, bottom: 52 },
  legend: { bottom: 0, textStyle: { color: C.muted, fontSize: 10 }, itemWidth: 14 },
  tooltip: { trigger: "axis" },
  xAxis: { type: "value", name: t("ax.year"), nameLocation: "middle", nameGap: 24, min: "dataMin", max: "dataMax", scale: true,
    axisLabel: { color: C.muted, formatter: (v: number) => String(v) }, axisLine: { lineStyle: { color: C.grid } }, splitLine: { show: false } },
  yAxis: { type: "value", name: yName, nameTextStyle: { color: C.muted, align: "left" }, scale: true,
    axisLabel: { color: C.muted }, splitLine: { lineStyle: { color: C.grid } } },
});

function Frame({ title, source, children, note }: { title: string; source: string; children: React.ReactNode; note?: React.ReactNode }) {
  return (
    <section className="chart">
      <h4>{title}</h4>
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
    markLine: { symbol: "none", lineStyle: { color: C.muted, type: "dotted" }, data: [{ xAxis: 2012.5, label: { formatter: "L5 / L8", color: C.muted } }] } }];
  if (l5) series.push({ name: t("ser.lst5"), type: "line", showSymbol: false, color: "#f5c04a", lineStyle: { type: "dashed" },
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

export function AreaChart({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  const em = d.stats?.area_emergence;
  return (
    <Frame title={t("chart.area")} source={t("chart.source.landsat")}
      note={<>{em?.censored_at_ref_end ? <div className="note small">{em.censored_note}</div> : null}
        {d.series.some(oneScene) ? <div className="small muted" data-testid="onescene-note">{t("chart.onescene")}</div> : null}</>}>
      <ReactECharts option={areaOption(d, t)} style={{ height: 230 }} notMerge />
    </Frame>
  );
}

export function LstChart({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  return (
    <Frame title={t("chart.lst")} source={t("chart.source.landsat")} note={<div className="note small">{t("lst.break")}. {d.lst.note}</div>}>
      <ReactECharts option={lstOption(d, t)} style={{ height: 210 }} notMerge />
    </Frame>
  );
}

export function ClimateChart({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  const [show, setShow] = useState(false);
  const dec = d.climate?.decomposition;
  const ok = !!dec && dec.ok && dec.interpretable !== false;
  return (
    <Frame title={t("chart.climate")} source={t("chart.source.climate")}
      note={<div className="note small">{t("climate.note")} {d.climate?.evaporation_label}</div>}>
      {ok && dec ? <ReactECharts option={climateOption(dec, t)} style={{ height: 230 }} notMerge /> : (
        <div className="na" role="status">
          <strong>{t("climate.na")}</strong>
          <div>{t("climate.reason")}: {dec?.wording ?? "no climate data"}</div>
          {dec?.ok && (
            <label className="small"><input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} /> {t("climate.show")}</label>)}
          {show && dec?.ok && <ReactECharts option={climateOption(dec, t)} style={{ height: 210 }} notMerge />}
        </div>)}
    </Frame>
  );
}

export function VolumeChart({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  const v = d.volume;
  const opt: EChartsOption | null = v && v.length ? { ...base(t, t("ax.dv")), series: [
    { name: "dV", type: "line", color: C.water, data: v.map((r) => ({ value: [r.year, r.dV_km3], itemStyle: { opacity: r.extrapolated ? 0.4 : 1 } })) }] } : null;
  return (
    <Frame title={t("chart.volume")} source={t("chart.source.swot")}>
      {opt ? <ReactECharts option={opt} style={{ height: 200 }} notMerge /> : (
        <div className="na" role="status"><strong>{t("volume.none")}</strong><div className="small">{d.swot?.reason ?? ""}</div></div>)}
    </Frame>
  );
}
