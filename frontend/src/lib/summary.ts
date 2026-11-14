import type { LakeSummary } from "./types";
import type { TFn } from "../i18n";

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
