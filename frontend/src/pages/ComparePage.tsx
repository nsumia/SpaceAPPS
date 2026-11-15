import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactECharts from "../lib/ReactECharts";
import type { EChartsOption } from "echarts";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n";
import { useCompareIds, useLakes } from "../hooks";
import { api } from "../lib/api";
import { sortLakes, type SortKey } from "../lib/compare";
import { C, LAKE_COLOURS } from "../lib/palette";
import type { LakeSummary } from "../lib/types";
import { Info } from "../components/Info";

const fmt = (x: number | null | undefined, d = 1) => (x == null ? "n/a" : x.toFixed(d));
const sgn = (x: number, d = 1) => (x > 0 ? "+" : "") + x.toFixed(d);
/** Short label: drop the bracketed qualifier ("Aral Sea (South / Large Aral)" -> "Aral Sea (South)" would be ambiguous, so keep the first bracket word). */
export const shortName = (n: string) => n.replace(/\s*\((\w+)[^)]*\)/, " ($1)").replace(/^Custom lake /, "Custom ");
const HOLLOW = { fill: "#171915", line: "#c9c4b4" };
/** climate share 0..1 -> colour (light yellow -> orange -> dark red). null / not interpretable -> hollow grey marker. */
export function shareColour(share: number | null): string {
  if (share == null || Number.isNaN(share)) return HOLLOW.fill;
  const s = Math.min(1, Math.max(0, share));
  const stops = [[253, 224, 139], [244, 109, 67], [215, 48, 39]];
  const k = s * 2, i = Math.min(1, Math.floor(k)), f = k - i;
  const c = stops[i].map((v, j) => Math.round(v + (stops[i + 1][j] - v) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
/** Marker size from area on a log scale, clamped so no lake is a speck or a giant. */
export const markerSize = (area: number | null | undefined) => Math.min(24, Math.max(10, 4 + 4.2 * Math.log10(Math.max(area ?? 1, 1) + 1)));
export const pWords = (p: number | null | undefined, t: (k: string) => string) =>
  p == null ? t("na.data") : `${t(p < 0.05 ? "sig.yes.long" : "sig.no.long")} (p ${p < 0.001 ? "< 0.001" : "= " + p.toFixed(3)})`;

export function scatterPoints(rows: LakeSummary[]) {
  const ok = (r: LakeSummary) => r.warming_c_per_decade != null && r.trend_pct_per_decade != null;
  return { shown: rows.filter(ok), excluded: rows.filter((r) => !ok(r)) };
}

export function scatterOption(rows: LakeSummary[], t: (k: string) => string): EChartsOption {
  const { shown } = scatterPoints(rows);
  const mk = (turkey: boolean) => shown.filter((r) => (r.group === "turkey") === turkey).map((r) => {
    const share = r.climate_interpretable ? r.climate_explained_share : null;
    const hollow = share == null;
    return { name: shortName(r.name), full: r.name, country: r.country, p: r.trend_p, share, area: r.latest_area_km2,
      value: [r.warming_c_per_decade, r.trend_pct_per_decade], symbolSize: markerSize(r.latest_area_km2) + (turkey ? 4 : 0),
      itemStyle: { color: shareColour(share), borderColor: hollow ? HOLLOW.line : turkey ? C.sand : "#14110a", borderWidth: hollow ? 2 : turkey ? 3 : 1.5, opacity: 1 } };
  });
  const ser = (turkey: boolean): any => ({
    name: t(turkey ? "cmp.turkey" : "cmp.reference"), type: "scatter", data: mk(turkey), z: turkey ? 5 : 3,
    symbol: turkey ? "diamond" : "circle",
    label: { show: true, formatter: (p: any) => p.name, color: turkey ? C.sand : C.text, fontWeight: turkey ? "bold" : "normal", position: "top", fontSize: 11, distance: 3 },
    labelLayout: { hideOverlap: true, moveOverlap: "shiftY" },
    labelLine: { show: false },
    emphasis: { focus: "self", scale: 1.3, label: { show: true, fontSize: 13 } },
    markLine: turkey ? { silent: true, symbol: "none", label: { show: false }, lineStyle: { color: C.muted, type: "dashed", width: 1 }, data: [{ xAxis: 0 }, { yAxis: 0 }] } : undefined,
  });
  return {
    backgroundColor: "transparent", textStyle: { color: C.text },
    grid: { left: 64, right: 24, top: 24, bottom: 56 },
    tooltip: { confine: true, formatter: (p: any) => { const d = p.data; if (!d) return "";
      return `<b>${d.full}</b>${d.country ? ` (${d.country})` : ""}<br/>${t("tip.warming")}: ${sgn(d.value[0], 2)} °C ${t("tip.perdec")}<br/>${t("tip.trend")}: ${sgn(d.value[1])} % ${t("tip.perdec")}<br/>${t("tip.sig")} ${pWords(d.p, t)}<br/>${t("tip.climate")}: ${d.share == null ? t("tip.nocl") : Math.round(100 * d.share) + " %"}<br/>${t("tip.area")}: ${d.area == null ? t("na.data") : Math.round(d.area).toLocaleString("en") + " km²"}`; } },
    xAxis: { type: "value", name: t("cmp.x"), nameLocation: "middle", nameGap: 30, nameTextStyle: { color: C.text }, scale: true, axisLabel: { color: C.muted, formatter: (v: number) => sgn(v, 1) }, splitLine: { lineStyle: { color: C.grid } } },
    yAxis: { type: "value", name: t("cmp.y"), nameLocation: "middle", nameGap: 44, nameTextStyle: { color: C.text }, scale: true, axisLabel: { color: C.muted, formatter: (v: number) => `${v}%` }, splitLine: { lineStyle: { color: C.grid } } },
    graphic: [{ type: "text", right: 30, bottom: 62, silent: true, style: { text: `↘ ${t("cmp.quad")}`, fill: "#ffb3a5", font: "12px IBM Plex Sans, system-ui" } }],
    series: [ser(false), ser(true)],
  };
}

export function ScatterLegend({ excluded }: { excluded: LakeSummary[] }) {
  const { t } = useI18n();
  return (
    <div className="scatter-legend" data-testid="scatter-legend">
      <span><i className="mk diamond" /> {t("cmp.leg.turkey")}</span>
      <span><i className="mk circle" /> {t("cmp.leg.reference")}</span>
      <span><i className="mk hollow" /> {t("cmp.leg.na")}</span>
      <span className="grad-wrap">{t("cmp.leg.colour")}: {t("cmp.leg.low")} <i className="grad" /> {t("cmp.leg.high")}</span>
      <span>{t("cmp.leg.size")}</span>
      {excluded.length > 0 && <div className="excluded" data-testid="scatter-excluded"><strong>{t("cmp.excluded")}</strong>{" "}
        {excluded.map((l) => `${shortName(l.name)} (${t(l.warming_c_per_decade == null ? "cmp.ex.warming" : "cmp.ex.trend")})`).join("; ")}</div>}
    </div>
  );
}

export default function ComparePage() {
  const { t } = useI18n();
  const lakes = useLakes();
  const [ids, add, remove] = useCompareIds();
  const [key, setKey] = useState<SortKey>("trend_pct_per_decade");
  const [dir, setDir] = useState<1 | -1>(1);
  const [grp, setGrp] = useState<"all" | "turkey" | "reference">("all");
  const all = lakes.data ?? [];
  const chosen = useMemo(() => ids.map((i) => all.find((l) => l.id === i || l.alias === i)).filter(Boolean) as LakeSummary[], [ids, all]);
  const cmp = useQuery({ queryKey: ["compare", ids], queryFn: () => api.compare(chosen.map((l) => l.id)), enabled: chosen.length > 0 });

  const lineOpt: EChartsOption = {
    backgroundColor: "transparent", textStyle: { color: C.text }, tooltip: { trigger: "axis" },
    grid: { left: 60, right: 20, top: 34, bottom: 78 }, legend: { bottom: 0, textStyle: { color: C.muted } },
    xAxis: { type: "value", name: t("ax.year"), nameLocation: "middle", nameGap: 24, min: "dataMin", max: "dataMax", axisLabel: { color: C.muted, formatter: (v: number) => String(v) }, splitLine: { show: false } },
    yAxis: { type: "value", name: t("cmp.ylabel"), scale: true, axisLabel: { color: C.muted }, splitLine: { lineStyle: { color: C.grid } } },
    series: Object.entries(cmp.data?.series ?? {}).map(([k, s], i) => ({
      name: `${s.name}${s.reliability === "low" ? t("cmp.lowrel.suffix") : ""}`, type: "line" as const, data: s.years.map((y, j) => [y, s.values[j]]), symbolSize: 4,
      color: LAKE_COLOURS[i % 6], lineStyle: { width: 2, type: (["solid", "dashed", "dotted"] as const)[i % 3] }, emphasis: { focus: "series" as const },
      markLine: i === 0 ? { symbol: "none", silent: true, lineStyle: { color: C.muted, type: "dotted" as const }, data: [{ yAxis: 100 }], label: { formatter: "100%", color: C.muted, position: "insideStartTop" as const } } : undefined, id: k })),
  };
  const sorted = sortLakes(all, key, dir).filter((l) => grp === "all" || l.group === grp);
  const head = (k: SortKey, label: string, tip?: string) => (
    <th aria-sort={key === k ? (dir === 1 ? "ascending" : "descending") : "none"}><button className="sort" onClick={() => { setDir(key === k ? (dir === 1 ? -1 : 1) : 1); setKey(k); }}>
      {label}{key === k ? (dir === 1 ? " ▲" : " ▼") : ""}</button>{tip && <> <Info text={tip} /></>}</th>);
  return (
    <div className="page compare">
      <h1>{t("cmp.title")}</h1>
      <div className="chips" data-testid="chosen">
        {chosen.length === 0 && <span className="muted">{t("cmp.empty")}</span>}
        {chosen.map((l, i) => <span key={l.id} className="chip" style={{ borderColor: LAKE_COLOURS[i % 6] }}>{l.name}<button onClick={() => remove(l.id, l.alias ?? "")} aria-label={`${t("cmp.remove")} ${l.name}`}>×</button></span>)}
        <Link to="/" className="btn">{t("nav.map")}</Link>
      </div>
      <section className="chart wide">
        <h3>{t("cmp.chart")}</h3>
        <p className="what"><strong>{t("what")}:</strong> {t("cmp.chart.help")}</p>
        {chosen.length > 0 ? <ReactECharts option={lineOpt} style={{ height: 360 }} notMerge /> : <div className="muted">{t("cmp.empty")}</div>}
        <div className="src">{t("chart.source.landsat")}</div>
        <div className="note small">{t("cmp.res")}</div>
      </section>
      <section className="chart wide">
        <h3>{t("cmp.table")}</h3>
        <p className="what">{t("cmp.table.help")}</p>
        <div className="seg" role="group" aria-label={t("col.group")} data-testid="group-filter">
          {(["all", "turkey", "reference"] as const).map((g) => <button key={g} className={grp === g ? "on" : ""} onClick={() => setGrp(g)}>{t(`grp.${g}`)}</button>)}
        </div>
        <table className="rank">
          <thead><tr><th />{head("name", t("col.name"))}{head("trend_pct_per_decade", t("col.trend"), t("tip.col.trend"))}{head("trend_p", t("col.p"), t("tip.col.p"))}{head("emergence_year", t("col.emergence"), t("tip.col.emergence"))}
            {head("warming_c_per_decade", t("col.warming"), t("tip.col.warming"))}{head("climate_explained_share", t("col.climate"), t("tip.col.climate"))}</tr></thead>
          <tbody>{sorted.map((l) => {
            const inn = ids.includes(l.id) || (!!l.alias && ids.includes(l.alias));
            return (
              <tr key={l.id} className={l.group === "turkey" ? "tr-lake" : ""}>
                <td><button disabled={!inn && ids.length >= 6} title={ids.length >= 6 && !inn ? t("cmp.max") : ""} onClick={() => (inn ? remove(l.id, l.alias ?? "") : add(l.id))}>{inn ? t("cmp.remove") : t("cmp.add")}</button></td>
                <td>{l.group === "turkey" ? "★ " : ""}{l.name}{l.reliability === "low" ? <span title={t("tip.lowrel")} aria-label={t("tip.lowrel")}> ⚠</span> : ""} <span className="muted small">{l.group === "reference" ? `${l.country ?? ""}${l.cadence_years && l.cadence_years > 1 ? `, ${t("cmp.cadence", { n: l.cadence_years })}` : ""}` : ""}</span></td>
                <td>{l.trend_pct_per_decade == null ? <span className="muted">{t("na.data")}</span> : fmt(l.trend_pct_per_decade)}</td>
                <td>{l.trend_p == null ? <span className="muted">{t("na.data")}</span> : <>{t(l.trend_p < 0.05 ? "sig.yes" : "sig.no")} <span className="muted small">(p {l.trend_p < 0.001 ? "< 0.001" : "= " + l.trend_p.toFixed(3)})</span></>}</td>
                <td>{l.emergence_year == null ? <span className="muted">{t("na.data")}</span> : (l.emergence_censored_at_ref_end ? t("cmp.by") + " " : "") + l.emergence_year}</td>
                <td>{l.warming_c_per_decade == null ? <span className="muted">{t("na.data")}</span> : fmt(l.warming_c_per_decade, 2)}</td>
                <td>{l.climate_interpretable && l.climate_explained_share != null ? `${Math.round(100 * l.climate_explained_share)}%` : <span className="muted">{t("na.climate")}</span>}</td>
              </tr>);
          })}</tbody>
        </table>
        <div className="src">{t("cmp.turkey.note")} {t("chart.source.landsat")}</div>
      </section>
      <section className="chart wide">
        <h3>{t("cmp.scatter")}</h3>
        <p className="what" data-testid="scatter-help"><strong>{t("what")}:</strong> {t("cmp.scatter.help")}</p>
        <ReactECharts option={scatterOption(all.filter((l) => l.group !== "custom"), t)} style={{ height: 460 }} notMerge />
        <ScatterLegend excluded={scatterPoints(all.filter((l) => l.group !== "custom")).excluded} />
        <div className="src small">{t("ui.sign")} {t("chart.source.landsat")}</div>
      </section>
    </div>
  );
}
