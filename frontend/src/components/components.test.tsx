import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { burdurFull } from "../fixtures";
import { areaOption, ClimateChart, VolumeChart } from "./Charts";
import { LiveCards } from "./LiveCards";
import { AnalysisProgress, Badges, eta } from "./Panel";
import { makeT } from "../i18n";
import type { Live } from "../lib/types";

vi.mock("../lib/ReactECharts", () => ({ default: () => <div data-testid="echart" /> }));

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
  it("badges: validated badge shown, no 'not checked against published data' badge", () => {
    const { rerender } = render(<Badges d={burdurFull} />);
    expect(screen.getByText(/validated against published data/)).toBeInTheDocument();
    rerender(<Badges d={{ ...burdurFull, summary: { ...burdurFull.summary, validated: false } }} />);
    expect(screen.queryByText(/published data/)).toBeNull();
    expect(screen.queryByText(/not checked/)).toBeNull();
  });
  it("volume chart shows 'No data' and the reason when SWOT is unavailable", () => {
    render(<VolumeChart d={burdurFull} />);
    expect(screen.getByText("No data")).toBeInTheDocument();
    expect(screen.getByText("No SWOT PLD id")).toBeInTheDocument();
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
    render(<><ClimateChart d={burdurFull} /><VolumeChart d={burdurFull} /></>);
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
