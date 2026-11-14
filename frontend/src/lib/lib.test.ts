import { describe, expect, it } from "vitest";
import { makeT } from "../i18n";
import { burdur } from "../fixtures";
import { summarySentence } from "./summary";
import { sortLakes, trendColour } from "./compare";
import { circleRadius } from "../components/MapView";

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
  it("colours trends: dark red fast loss, grey not significant, blue increase", () => {
    expect(trendColour({ trend_p: 0.001, trend_pct_per_decade: -10 })).toBe("#a50f15");
    expect(trendColour({ trend_p: 0.5, trend_pct_per_decade: -10 })).toBe("#9a9a9a");
    expect(trendColour({ trend_p: 0.01, trend_pct_per_decade: 4 })).toBe("#56B4E9");
  });
  it("sizes markers by area within bounds", () => {
    expect(circleRadius(4000)).toBeGreaterThan(circleRadius(100));
    expect(circleRadius(1e9)).toBe(24);
  });
});
