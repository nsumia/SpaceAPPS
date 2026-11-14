import type { LakeSummary } from "./types";

export type SortKey = "name" | "trend_pct_per_decade" | "trend_p" | "emergence_year" | "warming_c_per_decade" | "climate_explained_share";

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
  if (s.trend_p == null || s.trend_pct_per_decade == null || s.trend_p >= 0.05) return "#9a9a9a";
  return s.trend_pct_per_decade < 0 ? (s.trend_pct_per_decade < -5 ? "#a50f15" : "#d6604d") : "#56B4E9";
}
