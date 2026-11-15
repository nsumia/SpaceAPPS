import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { burdurFull } from "../fixtures";
import { AreaChart, areaOption, ClimateChart, ForecastChart } from "./Charts";
import { AnalysisProgress, eta, LiveCards } from "./Panel";
import { makeT } from "../i18n";
import * as PanelMod from "./Panel";
import * as ChartsMod from "./Charts";
import type { Live } from "../lib/api";

vi.mock("echarts-for-react/lib/core", () => ({ default: () => <div data-testid="echart" /> }));

describe("charts", () => {
  it("climate chart always shows the curves, with no 'Not computable' block, reasons, technical line or toggle", () => {
    render(<ClimateChart d={burdurFull} />);
    expect(screen.getByTestId("echart")).toBeInTheDocument();
    expect(screen.queryByText(/not computable/i)).toBeNull();
    expect(screen.queryByText(/weak_reference_skill/)).toBeNull();
    expect(screen.queryByText(/Why:|Reason:/)).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.getByText(/sign, not proof/)).toBeInTheDocument();
  });
  it("area chart labels a left-censored emergence line 'by 1997' and draws the Sen line", () => {
    const o: any = areaOption(burdurFull, makeT("en"));
    const obs = o.series.find((s: any) => s.markLine);
    expect(obs.markLine.data[0].xAxis).toBe(1997);
    expect(obs.markLine.data[0].label.formatter).toBe("clearly changed by 1997");
    expect(o.series.some((s: any) => s.name === "overall trend (Sen slope)")).toBe(true);
    expect(o.xAxis.name).toBe("Year");
    expect(o.yAxis.name).toBe("Area (km²)");
  });
});

describe("chart help", () => {
  it("every panel chart has a 'What this shows' caption", () => {
    render(<><ClimateChart d={burdurFull} /><AreaChart d={burdurFull} /></>);
    expect(screen.getAllByTestId("chart-help").length).toBe(2);
    expect(screen.getAllByText("What this shows:").length).toBe(2);
  });
});

describe("live cards and progress", () => {
  const live: Live = { lake_id: "burdur", name: "Burdur", stale: false, generated_utc: "x", cards: {
    landsat: { source: "Landsat C2 L2", ok: true, cached: true, stale: false, age_s: 60, area_km2: 120.5, latest_scene: "2026-11-01", lst_c: 12.3, change_vs_last_year_pct: -2.1 },
    swot: { source: "SWOT", ok: false, error: "no pld_id", cached: false, stale: false, age_s: 0 },
    precip: { source: "NASA POWER", ok: true, cached: false, stale: true, age_s: 9000, precip_mm: 210, pct_of_normal: 95, data_until: "2026-11-12", refresh_error: "timeout" } } };
  it("shows source, data date, cache and stale labels and 'no data' for failed sources", () => {
    render(<LiveCards live={live} loading={false} />);
    expect(screen.getAllByTestId("cache-tag").length).toBe(2);              // two Landsat-based cards
    expect(screen.getByText("stale")).toBeInTheDocument();
    expect(screen.getByText("120.5")).toBeInTheDocument();
    expect(screen.getAllByText(/2026-11-01/).length).toBe(2);
    expect(screen.getByText(/no pld_id/)).toBeInTheDocument();
  });
  it("shows a spinner while the first live call runs", () => {
    render(<LiveCards loading />);
    expect(screen.getByRole("status")).toHaveTextContent(/30 s/);
  });
  it("shows progress, year and ETA", () => {
    expect(eta(50, 0, 60_000)).toBe("60 s");
    expect(eta(2, 0, 60_000)).toBeNull();
    render(<AnalysisProgress started={Date.now() - 30_000} job={{ job_id: "j", lake_id: "l", status: "running", progress: 40, current_year: 2005, phase: "filling gaps", error: null, result_url: "" }} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByText(/year: 2005/)).toBeInTheDocument();
  });
});

describe("forecast chart", () => {
  const yrs = Array.from({ length: 15 }, (_, i) => 2026 + i);
  const ok = { ok: true, horizon_year: 2040, n_valid: 40, note: "x", model: "sen_recent" as const, last_observed_year: 2025, last_observed_km2: 116.5, interpretable: true,
    years: yrs, median: yrs.map((y) => 116 - 2 * (y - 2025)), lo90: yrs.map((y) => 110 - 2 * (y - 2025)), hi90: yrs.map((y) => 122 - 2 * (y - 2025)),
    lo50: yrs.map((y) => 113 - 2 * (y - 2025)), hi50: yrs.map((y) => 119 - 2 * (y - 2025)), flags: [],
    milestones: [{ year: 2040, median_km2: 87, lo90_km2: 83, hi90_km2: 89, median_pct_of_ref: 43 }] };
  it("draws the chart with a plain-language sentence and the 'not a projection' caveat", () => {
    render(<ForecastChart d={{ ...burdurFull, forecast: ok }} />);
    expect(screen.getByTestId("echart")).toBeInTheDocument();
    expect(screen.getByTestId("forecast-text")).toHaveTextContent(/2040/);
  });
  it("shows 'No forecast' and no chart when the series is not reliable enough", () => {
    render(<ForecastChart d={{ ...burdurFull, forecast: { ok: false, reason: "unreliable_area_series", horizon_year: 2040, n_valid: 20, note: "x" } }} />);
    expect(screen.queryByTestId("echart")).toBeNull();
    expect(screen.getByText("No forecast")).toBeInTheDocument();
  });
});

describe("removed UI: top badges and SWOT volume section", () => {
  it("no Badges/VolumeChart components and no badge/volume strings in EN or TR", () => {
    expect((PanelMod as any).Badges).toBeUndefined();
    expect((ChartsMod as any).VolumeChart).toBeUndefined();
    for (const lang of ["en", "tr"] as const) {
      const t = makeT(lang);
      for (const k of ["badge.validated", "badge.rel.ok", "badge.rel.low", "badge.rel.unknown", "chart.volume", "volume.none", "help.volume"])
        expect(t(k)).toBe(k);
    }
  });
});
