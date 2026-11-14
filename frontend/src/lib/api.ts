import type { paths } from "../api/schema";
import type { CompareResp, Identify, Job, LakeFull, LakeSummary, Live, MaskJson } from "./types";

export type ApiPath = keyof paths;
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
