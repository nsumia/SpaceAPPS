import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n";
import { useCompareIds, useLakes } from "../hooks";
import { api } from "../lib/api";
import { sortLakes, type SortKey } from "../lib/compare";
import { C, LAKE_COLOURS } from "../lib/palette";
import type { LakeSummary } from "../lib/types";

const fmt = (x: number | null | undefined, d = 1) => (x == null ? "n/a" : x.toFixed(d));

export function scatterOption(rows: LakeSummary[], t: (k: string) => string): EChartsOption {
  const pts = rows.filter((r) => r.warming_c_per_decade != null && r.trend_pct_per_decade != null);
  const mk = (turkey: boolean) => pts.filter((r) => (r.group === "turkey") === turkey).map((r) => ({
    name: r.name, value: [r.warming_c_per_decade, r.trend_pct_per_decade, r.latest_area_km2 ?? 10, r.climate_interpretable ? r.climate_explained_share : null] }));
  const ser = (turkey: boolean): any => ({
    name: t(turkey ? "cmp.turkey" : "cmp.reference"), type: "scatter", data: mk(turkey),
    symbol: turkey ? "diamond" : "circle", symbolSize: (v: number[]) => 8 + Math.sqrt(v[2]) * 0.9,
    itemStyle: { borderColor: turkey ? "#fff" : "transparent", borderWidth: 2 },
    label: { show: true, formatter: (p: any) => p.name, color: C.text, position: "right", fontSize: 10 },
  });
  return {
    backgroundColor: "transparent", textStyle: { color: C.text },
    grid: { left: 60, right: 90, top: 30, bottom: 80 },
    legend: { bottom: 0, textStyle: { color: C.muted } },
    tooltip: { formatter: (p: any) => `${p.name}<br/>${t("cmp.x")}: ${fmt(p.value[0], 2)}<br/>${t("cmp.y")}: ${fmt(p.value[1], 2)}<br/>${t("col.climate")}: ${p.value[3] == null ? t("cmp.nocl") : Math.round(100 * p.value[3]) + "%"}` },
    xAxis: { type: "value", name: t("cmp.x"), nameLocation: "middle", nameGap: 26, scale: true, axisLabel: { color: C.muted }, splitLine: { lineStyle: { color: C.grid } } },
    yAxis: { type: "value", name: t("cmp.y"), scale: true, axisLabel: { color: C.muted }, splitLine: { lineStyle: { color: C.grid } } },
    visualMap: { dimension: 3, min: 0, max: 1, calculable: false, orient: "vertical", right: 0, top: 30, text: ["100%", "0%"], textStyle: { color: C.muted },
      inRange: { color: ["#d9d9d9", "#fdb863", "#b2182b"] }, outOfRange: { color: "#555" }, formatter: ((v: number) => `${Math.round(100 * v)}%`) as any },
    series: [ser(true), ser(false)],
  };
}

export default function ComparePage() {
  const { t } = useI18n();
  const lakes = useLakes();
  const [ids, add, remove] = useCompareIds();
  const [key, setKey] = useState<SortKey>("trend_pct_per_decade");
  const [dir, setDir] = useState<1 | -1>(1);
  const all = lakes.data ?? [];
  const chosen = useMemo(() => ids.map((i) => all.find((l) => l.id === i || l.alias === i)).filter(Boolean) as LakeSummary[], [ids, all]);
  const cmp = useQuery({ queryKey: ["compare", ids], queryFn: () => api.compare(chosen.map((l) => l.id)), enabled: chosen.length > 0 });

  const lineOpt: EChartsOption = {
    backgroundColor: "transparent", textStyle: { color: C.text }, tooltip: { trigger: "axis" },
    grid: { left: 56, right: 16, top: 30, bottom: 70 }, legend: { bottom: 0, textStyle: { color: C.muted } },
    xAxis: { type: "value", name: t("ax.year"), nameLocation: "middle", nameGap: 24, min: "dataMin", max: "dataMax", axisLabel: { color: C.muted, formatter: (v: number) => String(v) }, splitLine: { show: false } },
    yAxis: { type: "value", name: "% of 1985-1990 mean", scale: true, axisLabel: { color: C.muted }, splitLine: { lineStyle: { color: C.grid } } },
    series: Object.entries(cmp.data?.series ?? {}).map(([k, s], i) => ({
      name: `${s.name}${s.reliability === "low" ? " (low reliability)" : ""}`, type: "line" as const, data: s.years.map((y, j) => [y, s.values[j]]), symbolSize: 4,
      color: LAKE_COLOURS[i % 6], lineStyle: { width: 2, type: (["solid", "dashed", "dotted"] as const)[i % 3] }, emphasis: { focus: "series" as const },
      markLine: i === 0 ? { symbol: "none", silent: true, lineStyle: { color: C.muted, type: "dotted" as const }, data: [{ yAxis: 100 }], label: { formatter: "100%", color: C.muted } } : undefined, id: k })),
  };
  const sorted = sortLakes(all, key, dir);
  const head = (k: SortKey, label: string) => (
    <th><button className="sort" onClick={() => { setDir(key === k ? (dir === 1 ? -1 : 1) : 1); setKey(k); }} aria-sort={key === k ? (dir === 1 ? "ascending" : "descending") : "none"}>
      {label}{key === k ? (dir === 1 ? " ▲" : " ▼") : ""}</button></th>);
  return (
    <div className="page compare">
      <h1>{t("cmp.title")}</h1>
      <div className="chips" data-testid="chosen">
        {chosen.length === 0 && <span className="muted">{t("cmp.empty")}</span>}
        {chosen.map((l, i) => <span key={l.id} className="chip" style={{ borderColor: LAKE_COLOURS[i % 6] }}>{l.name}<button onClick={() => remove(l.id)} aria-label={`${t("cmp.remove")} ${l.name}`}>×</button></span>)}
        <Link to="/" className="btn">{t("nav.map")}</Link>
      </div>
      <section className="chart wide">
        <h3>{t("cmp.chart")}</h3>
        {chosen.length > 0 ? <ReactECharts option={lineOpt} style={{ height: 320 }} notMerge /> : <div className="muted">{t("cmp.empty")}</div>}
        <div className="src">{t("chart.source.landsat")}</div>
        <div className="note small">{t("cmp.res")}</div>
      </section>
      <section className="chart wide">
        <h3>{t("cmp.table")}</h3>
        <table className="rank">
          <thead><tr><th />{head("name", t("col.name"))}{head("trend_pct_per_decade", t("col.trend"))}{head("trend_p", t("col.p"))}{head("emergence_year", t("col.emergence"))}
            {head("warming_c_per_decade", t("col.warming"))}{head("climate_explained_share", t("col.climate"))}</tr></thead>
          <tbody>{sorted.map((l) => {
            const inn = ids.includes(l.id);
            return (
              <tr key={l.id} className={l.group === "turkey" ? "tr-lake" : ""}>
                <td><button disabled={!inn && ids.length >= 6} title={ids.length >= 6 && !inn ? t("cmp.max") : ""} onClick={() => (inn ? remove(l.id) : add(l.id))}>{inn ? t("cmp.remove") : t("cmp.add")}</button></td>
                <td>{l.group === "turkey" ? "★ " : ""}{l.name}{l.reliability === "low" ? " ⚠" : ""}</td>
                <td>{fmt(l.trend_pct_per_decade)}</td><td>{l.trend_p == null ? "n/a" : l.trend_p < 0.001 ? "<0.001" : l.trend_p.toFixed(3)}</td>
                <td>{l.emergence_year == null ? "n/a" : (l.emergence_censored_at_ref_end ? "by " : "") + l.emergence_year}</td>
                <td>{fmt(l.warming_c_per_decade, 2)}</td>
                <td>{l.climate_interpretable && l.climate_explained_share != null ? `${Math.round(100 * l.climate_explained_share)}%` : "n/a"}</td>
              </tr>);
          })}</tbody>
        </table>
        <div className="src">★ = Turkish lake. {t("chart.source.landsat")}</div>
      </section>
      <section className="chart wide">
        <h3>{t("cmp.scatter")}</h3>
        <ReactECharts option={scatterOption(all, t)} style={{ height: 360 }} notMerge />
        <div className="src small">{t("cmp.size")}; {t("cmp.colour")}. {t("chart.source.landsat")}</div>
      </section>
    </div>
  );
}
