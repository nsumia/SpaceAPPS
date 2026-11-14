import type { LakeFull, LakeSummary } from "./lib/types";

export const burdur: LakeSummary = {
  id: "burdur", alias: "burdur", name: "Burdur", country: "TR", centre: [30.17, 37.75], group: "turkey", validated: true, unverified: false,
  years: [1985, 2025], latest_area_km2: 122.6, latest_area_year: 2025, ref_mean_km2: 200.5, total_loss_pct: 41.2, total_loss_basis: "x",
  trend_pct_per_decade: -10.5, trend_p: 3e-6, trend_direction: "decreasing", emergence_year: 1997, emergence_status: "emerged",
  emergence_censored_at_ref_end: true, emergence_note: "left-censored", warming_c_per_decade: 1.04, warming_basis: "Landsat 5 only", warming_pooled_c_per_decade: 1.2,
  warming_sensor_break_caveat: "step", climate_explained_share: null, climate_explained_ci90: null, climate_interpretable: false, climate_ci_includes_zero: false,
  climate_flags: [], climate_wording: "not computable / not interpretable: weak_reference_skill", reliability: "ok", reliability_note: null, status: "precomputed",
};

export const burdurFull: LakeFull = {
  summary: burdur, meta: {}, series: Array.from({ length: 41 }, (_, i) => ({ year: 1985 + i, area_km2: 200 - 2 * i, lst_c: 23 + 0.1 * i })),
  stats: { area: { n: 41, trend: "decreasing", p: 3e-6, sen_slope_per_year: -2.1, sen_slope_per_decade: -21, intercept: 196, intercept_year: 1985 },
    area_emergence: { year: 1997, status: "emerged", ref_mean: 189.6, sigma: 1.6, k: 2, threshold: 3.2, censored_at_ref_end: true, censored_note: "left-censored note" } },
  reliability: { reliability: "ok", note: null }, lst: { note: "caveat text" },
  climate: { decomposition: { ok: true, interpretable: false, wording: "not computable / not interpretable: weak_reference_skill", years: [2000, 2001],
    cum_observed_loss_km2: [1, 2], cum_predicted_loss_km2: [2, 4] }, note: "n" },
  swot: { ok: false, reason: "No SWOT PLD id" }, volume: null, unverified: false, analysis: null,
};
