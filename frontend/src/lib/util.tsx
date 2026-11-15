// Shared helpers: colours, lake sorting / trend colour, the template summary sentence, the "?" help bubble.
import type { LakeSummary } from "./api";
import type { TFn } from "../i18n";

// Palette: UI colours are in styles.css. DATA colours below are separate and
// colour-blind friendly (Okabe-Ito based), chosen to read on near-black AND on the bright Blue Marble basemap.
// Meaning is also given by labels, never by colour alone. Water = cyan, temperature = orange (E69F00, different hue AND lightness from water),
// loss = Okabe-Ito vermillion #D55E00 (hue 27, darker) - deliberately NOT the CTA red-orange #fc3d23 (hue 7); emergence = reddish purple.
// Magenta is UI-only (tags, Turkey marker ring); red-orange / royal blue are UI-only.
/** Same stack as --font in styles.css (canvas text in charts cannot read CSS variables). */
export const FONT = '"Franklin Gothic", "ITC Franklin Gothic", "Franklin Gothic Medium", "Libre Franklin Variable", "Libre Franklin", Arial, sans-serif';
export const C = {
  water: "#4cc9e0", waterPale: "#a9e3f2", waterDark: "#0b5f8a",
  temp: "#E69F00", climate: "#a8a8a8", loss: "#D55E00", gain: "#56B4E9", neutral: "#b0b0b0",
  emergence: "#CC79A7", turkey: "#f472ae", text: "#ffffff", muted: "#b0b0b0", grid: "#333333", bg: "#0e0e0e", panel: "#161616", ink: "#0e0e0e",
};
/** Trend classes shared by the map markers, the legend and the compare table: fast = saturated vermillion, slow = pale peach (lightness differs). */
export const TREND = { fast: "#D55E00", slow: "#f7c9a0", ns: "#b0b0b0", inc: "#56B4E9" };
export const LST5 = "#f5c04a"; // Landsat 5 temperature trend line
export const LAKE_COLOURS = ["#56B4E9", "#E69F00", "#009E73", "#F0E442", "#CC79A7", "#D55E00"];
/** Map overlay colours: 1985 extent (lost area) pale cream, selected-year water bright cyan; both read on dark and on Blue Marble. */
export const MASK = { base: [255, 244, 214] as [number, number, number], cur: [0, 190, 230] as [number, number, number] };

export type SortKey = "name" | "forecast_pct_of_ref" | "trend_pct_per_decade" | "trend_p" | "emergence_year" | "warming_c_per_decade" | "climate_explained_share";

export function sortLakes(rows: LakeSummary[], key: SortKey, dir: 1 | -1): LakeSummary[] {
  const val = (r: LakeSummary): number | string | null => (key === "name" ? r.name : (r[key] as number | null));
  return [...rows].sort((a, b) => {
    const x = val(a), y = val(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;          // missing values always last
    if (y == null) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * dir;
  });
}

export function trendColour(s: Pick<LakeSummary, "trend_p" | "trend_pct_per_decade">): string {
  if (s.trend_p == null || s.trend_pct_per_decade == null || s.trend_p >= 0.05) return TREND.ns;
  return s.trend_pct_per_decade < 0 ? (s.trend_pct_per_decade < -5 ? TREND.fast : TREND.slow) : TREND.inc;
}

const pct = (x: number) => Math.round(Math.abs(x));

/** Template sentence built only from data values (no AI). */
export function summarySentence(s: LakeSummary, t: TFn): string {
  const parts: string[] = [];
  const rec = s.recent_years ?? [], rf = s.ref_years ?? [1985, 1990];
  const y0 = rec.length ? rec[0] : "?", y1 = rec.length ? rec[rec.length - 1] : "?";
  if (s.total_loss_pct == null) return t("sum.nodata", { name: s.name });
  const sig = s.trend_p != null && s.trend_p < 0.05;
  const p = s.trend_p == null ? "" : s.trend_p < 0.001 ? "p<0.001" : `p=${s.trend_p.toFixed(3)}`;
  const sigTxt = sig ? t("sum.significant", { p }) : t("sum.notsignificant", { p });
  parts.push(t(s.total_loss_pct >= 0 ? "sum.lost" : "sum.gained", { name: s.name, pct: pct(s.total_loss_pct), y0, y1, r0: rf[0], r1: rf[1], sig: sigTxt }));
  if (s.emergence_year != null) {
    parts.push(t(s.emergence_censored_at_ref_end ? "sum.emerged_by" : "sum.emerged", { year: s.emergence_year }));
  }
  if (s.climate_interpretable && s.climate_explained_share != null) {
    const ci = s.climate_explained_ci90;
    parts.push(t("sum.climate", { share: pct(100 * s.climate_explained_share), lo: ci ? pct(100 * ci[0]) : "?", hi: ci ? pct(100 * ci[1]) : "?" }));
  } else {
    parts.push(t("sum.climate_na"));
  }
  return parts.join(" ");
}

/** Small "?" help bubble: hover, keyboard focus or tap shows the explanation (also exposed as aria-label / title). */
export function Info({ text, label = "?" }: { text: string; label?: string }) {
  return <span className="info" tabIndex={0} role="note" aria-label={text} title={text} data-tip={text}>{label}</span>;
}
