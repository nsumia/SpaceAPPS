// API client: response types, fetch wrapper, React Query hooks.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

// Response shapes for the endpoints that FastAPI declares as free-form dicts (FastAPI serves the full schema at /docs).
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
  forecast_year?: number | null; forecast_km2?: number | null; forecast_pct_of_ref?: number | null;
  ref_years?: number[]; recent_years?: number[]; recent_mean_km2?: number | null;
  why_selected?: string | null; mndwi_note?: string | null; resolution_m?: number | null; cadence_note?: string | null; cadence_years?: number | null;
  years_analysed?: number[] | null; window?: string[] | null; literature_direction?: string | null; our_direction?: string | null; literature_agrees?: boolean | null; literature_agreement?: string | null; validation_basis?: string | null;
}
export interface SeriesRow { year: number; area_km2: number | null; valid_frac?: number | null; lst_c?: number | null; volatile?: boolean; n_scenes?: number | null }
export interface Trend { n: number; trend: string; p: number; sen_slope_per_year: number; sen_slope_per_decade: number; intercept: number; intercept_year: number }
export interface Emergence { year: number | null; status: string; ref_mean: number; sigma: number; k: number; threshold: number; censored_at_ref_end?: boolean; censored_note?: string }
export interface Decomposition {
  ok: boolean; interpretable?: boolean; wording?: string; years?: number[]; cum_observed_loss_km2?: number[]; cum_predicted_loss_km2?: number[];
  explained_share?: number; explained_share_ci90?: [number, number]; interpretation_flags?: string[];
}
export interface ForecastMilestone { year: number; median_km2: number; lo90_km2: number; hi90_km2: number; median_pct_of_ref: number | null }
export interface Forecast {
  ok: boolean; reason?: string; horizon_year: number; n_valid: number; note: string; preliminary?: boolean;
  model?: "sen_full" | "sen_recent" | "persistence"; last_observed_year?: number; last_observed_km2?: number;
  slope_km2_per_decade?: number | null; slope_ci90_km2_per_decade?: [number, number] | null;
  years?: number[]; median?: number[]; lo90?: number[]; hi90?: number[]; lo50?: number[]; hi50?: number[];
  milestones?: ForecastMilestone[]; flags?: string[]; interpretable?: boolean;
  backtest?: { n_origins: number; n_pairs: number; max_horizon_years: number; mae_km2: Record<string, number>;
    skill_vs_persistence: Record<string, number>; chosen_skill: number; coverage90: number | null };
}
export interface LakeFull {
  summary: LakeSummary; meta: Record<string, unknown>; series: SeriesRow[];
  stats: { area?: Trend; lst_all?: Trend; lst_1985_2012?: Trend; area_emergence?: Emergence } | null;
  reliability: { reliability: string; note: string | null } | null; min_valid?: number | null;
  lst: { note: string }; climate: { decomposition?: Decomposition; note?: string; evaporation_label?: string } | null;
  swot: { ok: boolean; reason?: string } | null; forecast?: Forecast | null;
  volume: { year: number; area_km2: number; dV_km3: number; extrapolated: boolean }[] | null;
  unverified: boolean; analysis: { status: string; years_done: number; years_total: number; phase: string | null; note?: string; sample?: boolean } | null;
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

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let detail = r.statusText;
    try { const j = await r.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* not json */ }
    throw new ApiError(r.status, detail);
  }
  return r.json() as Promise<T>;
}

export const api = {
  lakes: () => req<{ lakes: LakeSummary[] }>("/api/lakes").then((r) => r.lakes),
  lake: (id: string) => req<LakeFull>(`/api/lakes/${encodeURIComponent(id)}`),
  forecast: (id: string, horizon = 2040) => req<Forecast>(`/api/lakes/${encodeURIComponent(id)}/forecast?horizon=${horizon}`),
  live: (id: string) => req<Live>(`/api/lakes/${encodeURIComponent(id)}/live`),
  mask: (id: string, year: number) => req<MaskJson>(`/api/lakes/${encodeURIComponent(id)}/masks/${year}?format=json`),
  index: () => req<GeoJSON.FeatureCollection>("/api/index"),
  identify: (lon: number, lat: number) => req<Identify>(`/api/identify?lon=${lon}&lat=${lat}`),
  analyze: (body: { lake_id?: string; polygon?: GeoJSON.Geometry }) =>
    req<Job & { status: string; result?: LakeFull; area_km2?: number }>("/api/analyze", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }),
  job: (id: string) => req<Job>(`/api/jobs/${id}`),
  compare: (ids: string[]) => req<CompareResp>(`/api/compare?ids=${ids.map(encodeURIComponent).join(",")}&metric=area_pct`),
};

export const useLakes = () => useQuery({ queryKey: ["lakes"], queryFn: api.lakes, staleTime: 60_000 });
export const useIndex = () => useQuery({ queryKey: ["index"], queryFn: api.index, staleTime: Infinity });
export const useLake = (id: string | null, running = false) =>
  useQuery({ queryKey: ["lake", id], queryFn: () => api.lake(id!), enabled: !!id, refetchInterval: running ? 1500 : false });
export const useLive = (id: string | null) =>
  useQuery({ queryKey: ["live", id], queryFn: () => api.live(id!), enabled: !!id, staleTime: 180_000, retry: 0 });

/** Compare selection (max 6) persisted in localStorage and shared via a window event. */
export function useCompareIds(): [string[], (id: string) => void, (...ids: string[]) => void] {
  const read = (): string[] => { try { return JSON.parse(localStorage.getItem("compare") ?? "[]"); } catch { return []; } };
  const [ids, setIds] = useState<string[]>(read);
  useEffect(() => {
    const h = () => setIds(read());
    window.addEventListener("compare-changed", h);
    return () => window.removeEventListener("compare-changed", h);
  }, []);
  const write = (v: string[]) => { localStorage.setItem("compare", JSON.stringify(v)); window.dispatchEvent(new Event("compare-changed")); };
  return [ids, (id) => { if (!ids.includes(id) && ids.length < 6) write([...ids, id]); }, (...rm) => write(ids.filter((x) => !rm.includes(x)))];
}
