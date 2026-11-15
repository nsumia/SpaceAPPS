import { describe, expect, it } from "vitest";
import { makeT } from "../i18n";
import { burdur } from "../fixtures";
import { sortLakes, summarySentence, trendValue, SPECTRUM, SPECTRUM_MAX, spectrumExpression, spectrumCss, TREND_NS, clampDate, VIIRS_MIN_DATE } from "./util";
import { circleRadius, sizeRange, SIZE_KEY_AREAS, basemapStyle } from "../components/MapView";

describe("summary sentence", () => {
  const t = makeT("en");
  it("uses data values, 'by <year>' for censored emergence and says climate share is not computable", () => {
    const s = summarySentence(burdur, t);
    expect(s).toContain("Burdur: the mean area of its last 3 valid years (2023-2025) is 41% below its 1985-1990 average");
    expect(s).not.toContain("since 1985");
    expect(s).toContain("significant, p<0.001");
    expect(s).toContain("by 1997");
    expect(s).toContain("not computable");
  });
  it("reports climate share with CI when interpretable and a Turkish variant exists", () => {
    const s = summarySentence({ ...burdur, climate_interpretable: true, climate_explained_share: 0.35, climate_explained_ci90: [0.2, 0.5], emergence_censored_at_ref_end: false }, t);
    expect(s).toContain("about 35%");
    expect(s).toContain("20-50%");
    expect(s).toContain("separated from natural variability in 1997");
    expect(summarySentence(burdur, makeT("tr"))).toContain("ortalamasının %41 altında");
  });
  it("calls an insignificant trend not significant and handles gains", () => {
    const s = summarySentence({ ...burdur, total_loss_pct: -12, trend_p: 0.4 }, t);
    expect(s).toContain("12% above its 1985-1990 average");
    expect(s).toContain("not significant, p=0.400");
  });
});

describe("compare helpers", () => {
  it("sorts with missing values always last in both directions", () => {
    const rows = [{ ...burdur, name: "A", emergence_year: null }, { ...burdur, name: "B", emergence_year: 2000 }, { ...burdur, name: "C", emergence_year: 1990 }];
    expect(sortLakes(rows, "emergence_year", 1).map((r) => r.name)).toEqual(["C", "B", "A"]);
    expect(sortLakes(rows, "emergence_year", -1).map((r) => r.name)).toEqual(["B", "C", "A"]);
  });
  it("trend value: clamped Sen slope, null (grey) when missing or not significant", () => {
    expect(trendValue({ trend_p: 0.001, trend_pct_per_decade: -10 })).toBe(-10);
    expect(trendValue({ trend_p: 0.001, trend_pct_per_decade: -28 })).toBe(-SPECTRUM_MAX);
    expect(trendValue({ trend_p: 0.01, trend_pct_per_decade: 40 })).toBe(SPECTRUM_MAX);
    expect(trendValue({ trend_p: 0.5, trend_pct_per_decade: -10 })).toBeNull();
    expect(trendValue({ trend_p: null, trend_pct_per_decade: null })).toBeNull();
  });
  it("spectrum: ascending stops, interpolate expression with grey fallback, legend gradient from the same stops", () => {
    const v = SPECTRUM.map(([x]) => x);
    expect(v).toEqual([...v].sort((a, b) => a - b));
    expect(v[0]).toBe(-SPECTRUM_MAX); expect(v[v.length - 1]).toBe(SPECTRUM_MAX);
    const ex = spectrumExpression() as any[];
    expect(ex[0]).toBe("case"); expect(ex[2][0]).toBe("interpolate"); expect(ex[3]).toBe(TREND_NS); // owner request 2026-11-15: darker grey (was #7a7a7a)
    expect(TREND_NS).toBe("#4a4a4a");
    expect(SPECTRUM.find(([x]) => x === 0)?.[1]).toBe("#f7f7f7");
    expect(spectrumCss()).toMatch(/^linear-gradient\(90deg, #67001f 0\.00%.*#053061 100\.00%\)$/);
  });
  it("sizes markers by area within bounds", () => {
    expect(circleRadius(4000)).toBeGreaterThan(circleRadius(100));
    expect(circleRadius(1e9)).toBe(24);
  });
  it("circle AREA is proportional to lake area inside the stated range, clamped outside", () => {
    const { min, max } = sizeRange();
    expect(min).toBeLessThan(max);
    expect(circleRadius(min)).toBeCloseTo(6, 6); expect(circleRadius(max)).toBeCloseTo(24, 6);
    for (const a of [min, 2 * min, 400, max / 4]) expect(circleRadius(4 * a) / circleRadius(a)).toBeCloseTo(2, 6); // 4x area = 2x radius
    expect(circleRadius(min / 10)).toBe(6); expect(circleRadius(max * 10)).toBe(24); expect(circleRadius(null)).toBe(6);
    for (const a of SIZE_KEY_AREAS) expect(a).toBeGreaterThanOrEqual(min), expect(a).toBeLessThanOrEqual(max);
    expect(circleRadius(SIZE_KEY_AREAS[1]) ** 2 / circleRadius(SIZE_KEY_AREAS[0]) ** 2).toBeCloseTo(SIZE_KEY_AREAS[1] / SIZE_KEY_AREAS[0], 6);
  });
  it("basemaps: dark and light OpenFreeMap vector styles", () => {
    expect(basemapStyle("vector", "2026-01-01")).toBe("https://tiles.openfreemap.org/styles/dark");
    expect(basemapStyle("vectorlight", "2026-01-01")).toBe("https://tiles.openfreemap.org/styles/positron");
  });
  it("VIIRS date: first daily image of the layer, typed dates are clamped", () => {
    expect(VIIRS_MIN_DATE).toBe("2018-01-05");
    expect(clampDate("2010-03-01", VIIRS_MIN_DATE, "2026-11-13")).toBe("2018-01-05");
    expect(clampDate("2030-03-01", VIIRS_MIN_DATE, "2026-11-13")).toBe("2026-11-13");
    expect(clampDate("2022-03-01", VIIRS_MIN_DATE, "2026-11-13")).toBe("2022-03-01");
    expect(clampDate("", VIIRS_MIN_DATE, "2026-11-13")).toBeNull();
    expect(clampDate("not-a-date", VIIRS_MIN_DATE, "2026-11-13")).toBeNull();
  });
});

import { scatterOption, scatterPoints, shareColour, markerSize, shortName } from "../pages/ComparePage";
import type { LakeSummary } from "./api";

describe("compare scatter", () => {
  const mk = (o: Partial<LakeSummary>): LakeSummary => ({ ...burdur, group: "reference", ...o } as LakeSummary);
  const rows = [
    mk({ id: "a", name: "Urmia", warming_c_per_decade: 0.5, trend_pct_per_decade: -14, climate_interpretable: false, climate_explained_share: null, latest_area_km2: 2700 }),
    mk({ id: "b", name: "Dead Sea", warming_c_per_decade: 0.6, trend_pct_per_decade: -3, climate_interpretable: true, climate_explained_share: 0.4, latest_area_km2: 593 }),
    mk({ id: "c", name: "Van", group: "turkey", warming_c_per_decade: 0.6, trend_pct_per_decade: -0.3, climate_interpretable: false, climate_explained_share: 0.9, latest_area_km2: 3500 }),
    mk({ id: "d", name: "Akşehir", group: "turkey", warming_c_per_decade: 1, trend_pct_per_decade: -28, climate_interpretable: false, climate_explained_share: null, latest_area_km2: 0 }),
    mk({ id: "e", name: "Aral Sea (South / Large Aral)", warming_c_per_decade: null, trend_pct_per_decade: -24, latest_area_km2: 3700 }),
  ];
  it("gives every plotted lake a visible symbol (size > 0, opaque fill, visible border), incl. 'not computable' ones", () => {
    const o: any = scatterOption(rows, makeT("en"));
    const pts = o.series.flatMap((s: any) => s.data);
    expect(pts.length).toBe(4);
    for (const p of pts) {
      expect(p.symbolSize).toBeGreaterThanOrEqual(10);
      expect(p.symbolSize).toBeLessThanOrEqual(30);
      expect(p.itemStyle.color).toMatch(/^(rgb\(|#)/);
      expect(p.itemStyle.color).not.toBe("transparent");
      expect(p.itemStyle.borderColor).toMatch(/^#/);
      expect(p.itemStyle.borderWidth).toBeGreaterThan(0);
      expect(p.itemStyle.opacity).toBe(1);
      expect(p.value.every((v: unknown) => typeof v === "number")).toBe(true);
    }
    const urmia = pts.find((p: any) => p.full === "Urmia");
    expect(urmia.share).toBeNull();                       // not computable -> hollow grey, not invisible
    expect(urmia.itemStyle.borderColor).toBe("#c8c8c8");
    expect(o.series.every((s: any) => s.labelLayout?.hideOverlap)).toBe(true);
    expect(o.series.length).toBe(1);                      // one uniform series: no Turkish/reference split
    expect(o.series[0].symbol).toBe("circle");
    expect(pts.find((p: any) => p.full === "Van").symbolSize).toBe(markerSize(3500));
  });
  it("lake table sort is uniform: ties and missing values fall back to name, no group ordering", () => {
    const r = (name: string, g: string, v: number | null) => ({ ...burdur, name, group: g, trend_pct_per_decade: v } as LakeSummary);
    const out = sortLakes([r("Zed", "turkey", null), r("Beta", "reference", -5), r("Alpha", "turkey", -5), r("Mu", "reference", null)], "trend_pct_per_decade", 1);
    expect(out.map((x) => x.name)).toEqual(["Alpha", "Beta", "Mu", "Zed"]);
  });
  it("lists lakes without warming values as excluded instead of dropping them silently", () => {
    const { shown, excluded } = scatterPoints(rows);
    expect(shown.length).toBe(4);
    expect(excluded.map((l) => l.name)).toEqual(["Aral Sea (South / Large Aral)"]);
  });
  it("colour and size helpers behave", () => {
    expect(shareColour(0)).not.toBe(shareColour(1));
    expect(shareColour(null)).toBe("#0e0e0e");
    expect(markerSize(0)).toBe(10); expect(markerSize(1e6)).toBe(24); expect(markerSize(3500)).toBeLessThan(24);
    expect(shortName("Aral Sea (South / Large Aral)")).toBe("Aral Sea (South)");
  });
});
