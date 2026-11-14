// Hand-written response shapes for the endpoints that FastAPI declares as free-form dicts (see api/schema.d.ts for paths).
export interface LakeSummary {
  id: string; alias: string | null; name: string; country: string | null; centre: [number, number] | null;
  group: "turkey" | "reference" | "custom"; validated: boolean; unverified: boolean; years: [number, number] | null;
  latest_area_km2: number | null; latest_area_year: number | null; ref_mean_km2: number | null;
  total_loss_pct: number | null; total_loss_basis: string; trend_pct_per_decade: number | null; trend_p: number | null;
  trend_direction: string | null; emergence_year: number | null; emergence_status: string | null;
  emergence_censored_at_ref_end: boolean; emergence_note: string | null; warming_c_per_decade: number | null;
  warming_basis: string | null; warming_pooled_c_per_decade: number | null; warming_sensor_break_caveat: string;
  climate_explained_share: number | null; climate_explained_ci90: [number, number] | null; climate_interpretable: boolean;
  climate_ci_includes_zero: boolean; climate_flags: string[]; climate_wording: string | null;
  reliability: string; reliability_note: string | null; status: string | null;
}
export interface SeriesRow { year: number; area_km2: number | null; valid_frac?: number | null; lst_c?: number | null; volatile?: boolean }
export interface Trend { n: number; trend: string; p: number; sen_slope_per_year: number; sen_slope_per_decade: number; intercept: number; intercept_year: number }
export interface Emergence { year: number | null; status: string; ref_mean: number; sigma: number; k: number; threshold: number; censored_at_ref_end?: boolean; censored_note?: string }
export interface Decomposition {
  ok: boolean; interpretable?: boolean; wording?: string; years?: number[]; cum_observed_loss_km2?: number[]; cum_predicted_loss_km2?: number[];
  explained_share?: number; explained_share_ci90?: [number, number]; interpretation_flags?: string[];
}
export interface LakeFull {
  summary: LakeSummary; meta: Record<string, unknown>; series: SeriesRow[];
  stats: { area?: Trend; lst_all?: Trend; lst_1985_2012?: Trend; area_emergence?: Emergence } | null;
  reliability: { reliability: string; note: string | null } | null;
  lst: { note: string }; climate: { decomposition?: Decomposition; note?: string; evaporation_label?: string } | null;
  swot: { ok: boolean; reason?: string } | null;
  volume: { year: number; area_km2: number; dV_km3: number; extrapolated: boolean }[] | null;
  unverified: boolean; analysis: { status: string; years_done: number; years_total: number; phase: string | null; note?: string } | null;
}
export interface LiveCard { source: string; ok: boolean; error?: string; fetched_utc?: string; cached: boolean; stale: boolean; age_s: number;
  refresh_error?: string; [k: string]: unknown }
export interface Live { lake_id: string; name: string; stale: boolean; generated_utc: string; cards: Record<string, LiveCard> }
export interface MaskJson { year: number; coordinates: [number, number][]; bounds: number[]; png_data_uri: string }
export interface Job { job_id: string; lake_id: string; status: "queued" | "running" | "done" | "failed"; progress: number;
  current_year: number | null; phase: string | null; error: string | null; result_url: string }
export interface CompareResp { series: Record<string, { name: string; years: number[]; values: number[]; reference_mean?: number; reliability?: string; error?: string }>; notes: string[] }
export interface Identify { id: string; alias: string | null; name: string; polygon_area_km2: number; lake_area_km2: number | null;
  precomputed: boolean; computed: boolean; polygon: GeoJSON.Geometry }
