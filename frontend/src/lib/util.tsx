// Shared helpers: colours, lake sorting / trend colour, the template summary sentence, the "?" help bubble.
import type { LakeSummary } from "./api";
import type { TFn } from "../i18n";

// Palette: UI colours are in styles.css. DATA colours below are separate and
// colour-blind friendly (Okabe-Ito based), chosen to read on near-black AND on the bright Blue Marble basemap.
// Meaning is also given by labels, never by colour alone. Water = cyan, temperature = orange (E69F00, different hue AND lightness from water),
// loss = Okabe-Ito vermillion #D55E00 (hue 27, darker) - deliberately NOT the CTA red-orange #fc3d23 (hue 7); emergence = reddish purple.
// Magenta is UI-only (tags); red-orange / royal blue are UI-only.
/** Same stack as --font in styles.css (canvas text in charts cannot read CSS variables). */
export const FONT = '"Franklin Gothic", "ITC Franklin Gothic", "Franklin Gothic Medium", "Libre Franklin Variable", "Libre Franklin", Arial, sans-serif';
export const C = {
  water: "#4cc9e0", waterPale: "#a9e3f2", waterDark: "#0b5f8a",
  temp: "#E69F00", climate: "#a8a8a8", loss: "#D55E00", gain: "#56B4E9", neutral: "#b0b0b0",
  emergence: "#CC79A7", turkey: "#f472ae", text: "#ffffff", muted: "#b0b0b0", grid: "#333333", bg: "#0e0e0e", panel: "#161616", ink: "#0e0e0e",
};
/** Trend classes shared by the map markers, the legend and the compare table: fast = saturated vermillion, slow = pale peach (lightness differs). */
/** Dot colour of lakes without a significant trend (map dots AND legend swatch). Dark grey: readable with the white ring + dark halo on
 * Blue Marble, VIIRS, dark vector and light vector basemaps, and clearly darker than the white-ish zero of the ramp (was #7a7a7a). */
export const TREND_NS = "#4a4a4a";
/** First daily image of the GIBS layer VIIRS_NOAA20_CorrectedReflectance_TrueColor (the layer MapView uses).
 * Source: NASA GIBS WMTS GetCapabilities https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml,
 * layer Time dimension: <Value>2018-01-05/2018-02-21/P1D</Value> (first of five daily ranges; read 2026-11-15). The ranges have
 * 2-day gaps (2018-02-22/23, 2018-03-13, 2020-01-01, 2022-01-13); such days return no tile. */
export const VIIRS_MIN_DATE = "2018-01-05";
/** Clamp an ISO date (YYYY-MM-DD) into [min, max]; null for empty / unparsable input. ISO strings compare lexicographically. */
export function clampDate(v: string, min: string, max: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v) || Number.isNaN(Date.parse(v))) return null;
  return v < min ? min : v > max ? max : v;
}
/** Clamp of the spectrum, %/decade: the strongest loss in the data is -28, 6 of 17 lakes lose more than 10; gains are all < 1.5, so a symmetric +-20 keeps small gains light blue. */
export const SPECTRUM_MAX = 20;
/** Continuous diverging dot colour ramp by trend (%/decade): ColorBrewer RdBu, dark red (strong loss) -> white (0) -> dark blue (strong gain).
 * Stops are ascending and symmetric, smooth through white (no hinge). Used for the MapLibre interpolate expression AND the legend gradient. */
export const SPECTRUM: [number, string][] = [
  [-20, "#67001f"], [-15, "#b2182b"], [-10, "#d6604d"], [-5, "#f4a582"], [-2, "#fddbc7"],
  [0, "#f7f7f7"],
  [2, "#d1e5f0"], [5, "#92c5de"], [10, "#4393c3"], [15, "#2166ac"], [20, "#053061"],
];
/** MapLibre data-driven colour: property "trend" (number, absent = grey). */
export const spectrumExpression = (): unknown[] => ["case", ["has", "trend"],
  ["interpolate", ["linear"], ["get", "trend"], ...SPECTRUM.flat()], TREND_NS];
/** CSS gradient for the legend bar (left = -SPECTRUM_MAX, right = +SPECTRUM_MAX). */
export const spectrumCss = (): string =>
  `linear-gradient(90deg, ${SPECTRUM.map(([v, c]) => `${c} ${(((v + SPECTRUM_MAX) / (2 * SPECTRUM_MAX)) * 100).toFixed(2)}%`).join(", ")})`;
export const LST5 = "#f5c04a"; // Landsat 5 temperature trend line
export const LAKE_COLOURS = ["#56B4E9", "#E69F00", "#009E73", "#F0E442", "#CC79A7", "#D55E00"];
/** Map overlay colours: 1985 extent (lost area) pale cream, selected-year water bright cyan; both read on dark and on Blue Marble. */
export const MASK = { base: [255, 244, 214] as [number, number, number], cur: [0, 190, 230] as [number, number, number] };

export type SortKey = "name" | "forecast_pct_of_ref" | "trend_pct_per_decade" | "trend_p" | "emergence_year" | "warming_c_per_decade" | "climate_explained_share";

export function sortLakes(rows: LakeSummary[], key: SortKey, dir: 1 | -1): LakeSummary[] {
  const val = (r: LakeSummary): number | string | null => (key === "name" ? r.name : (r[key] as number | null));
  return [...rows].sort((a, b) => {
    const x = val(a), y = val(b);
    const byName = a.name.localeCompare(b.name);   // uniform tie-break for every lake, regardless of API order / group
    if (x == null && y == null) return byName;
    if (x == null) return 1;          // missing values always last
    if (y == null) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * dir || byName;
  });
}

/** Per-lake value that drives the dot colour: Sen's slope of the lake area as % of the reference area per decade
 * (LakeSummary.trend_pct_per_decade). null = no data or not significant (p >= 0.05) -> neutral grey. Clamped to +-SPECTRUM_MAX. */
export function trendValue(s: Pick<LakeSummary, "trend_p" | "trend_pct_per_decade">): number | null {
  if (s.trend_p == null || s.trend_pct_per_decade == null || s.trend_p >= 0.05) return null;
  return Math.max(-SPECTRUM_MAX, Math.min(SPECTRUM_MAX, s.trend_pct_per_decade));
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
