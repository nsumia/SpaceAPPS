import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { burdurFull } from "../fixtures";
import { AreaChart, areaOption, ClimateChart, ForecastChart } from "./Charts";
import { AnalysisProgress, eta, LiveCards } from "./Panel";
import { GLOSSARY, I18nProvider, makeT } from "../i18n";
import MethodsPage from "../pages/MethodsPage";
import App from "../App";
import { MemoryRouter } from "react-router-dom";
import * as PanelMod from "./Panel";
import * as ChartsMod from "./Charts";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Live } from "../lib/api";

vi.mock("../lib/api", async (orig) => {
  const m = await orig<typeof import("../lib/api")>();
  const low = { ...burdurFull, summary: { ...burdurFull.summary, reliability: "low", reliability_note: "10 of 39 valid years jump by more than 15 %" },
    reliability: { reliability: "low", note: "10 of 39 valid years jump by more than 15 % of the 1985-1990 mean. Single-year areas are NOT reliable." } };
  return { ...m, useLakes: () => ({ data: [{ id: "burdur", alias: "burdur" }] }), useLake: () => ({ data: low }), useLive: () => ({ data: undefined, isLoading: true }),
    useCompareIds: () => [[], () => {}, () => {}] };
});
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
    precip: { source: "NASA POWER", ok: true, cached: false, stale: true, age_s: 9000, precip_mm: 210, pct_of_normal: 95, data_until: "2026-11-12", refresh_error: "timeout" } } };
  it("shows source and data date, no cache/stale labels", () => {
    render(<LiveCards live={live} loading={false} />);
    expect(screen.queryByTestId("cache-tag")).toBeNull();
    expect(screen.queryByText(/^(stale|cache|eski|önbellek)$/i)).toBeNull();
    expect(screen.queryByText("timeout")).toBeNull();
    expect(screen.getByText(/NASA POWER/)).toBeInTheDocument();
    expect(screen.getByText("120.5")).toBeInTheDocument();
    expect(screen.getAllByText(/2026-11-01/).length).toBe(2);
    expect(screen.queryByText(/no pld_id|SWOT water level/)).toBeNull();
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

describe("panel reliability note", () => {
  it("does not render the backend low-reliability warning", () => {
    const { container } = render(<QueryClientProvider client={new QueryClient()}><I18nProvider><PanelMod.default sel={{ id: "burdur" }} onClose={() => {}} /></I18nProvider></QueryClientProvider>);
    expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/jump by more than|NOT reliable/);
  });
});

describe("forecast chart", () => {
  const yrs = Array.from({ length: 15 }, (_, i) => 2026 + i);
  const ok = { ok: true, horizon_year: 2040, n_valid: 40, note: "x", model: "sen_recent" as const, last_observed_year: 2025, last_observed_km2: 116.5, interpretable: true,
    years: yrs, median: yrs.map((y) => 116 - 2 * (y - 2025)), lo90: yrs.map((y) => 110 - 2 * (y - 2025)), hi90: yrs.map((y) => 122 - 2 * (y - 2025)),
    lo50: yrs.map((y) => 113 - 2 * (y - 2025)), hi50: yrs.map((y) => 119 - 2 * (y - 2025)), flags: [],
    milestones: [{ year: 2040, median_km2: 87, lo90_km2: 83, hi90_km2: 89, median_pct_of_ref: 43 }] };
  it("draws the chart with a plain-language sentence and no disclaimer note", () => {
    const { container } = render(<ForecastChart d={{ ...burdurFull, forecast: ok }} />);
    expect(screen.getByTestId("echart")).toBeInTheDocument();
    expect(screen.getByTestId("forecast-text")).toHaveTextContent(/2040/);
    expect(container.textContent).not.toMatch(/A forecast, not a fact|does not know future rainfall/);
    expect(container.querySelector(".note")).toBeNull();
    for (const lang of ["en", "tr"] as const) expect(makeT(lang)("fc.caveat")).toBe("fc.caveat");
  });
  it("shows 'No forecast' and no chart when the series is not reliable enough", () => {
    render(<ForecastChart d={{ ...burdurFull, forecast: { ok: false, reason: "unreliable_area_series", horizon_year: 2040, n_valid: 20, note: "x" } }} />);
    expect(screen.queryByTestId("echart")).toBeNull();
    expect(screen.getByText("No forecast")).toBeInTheDocument();
  });
});

describe("removed UI: top badges and SWOT volume section", () => {
  it("live cards have no SWOT water level card and no live.swot strings", () => {
    for (const lang of ["en", "tr"] as const) { const t = makeT(lang); for (const k of ["live.swot", "live.swot1y"]) expect(t(k)).toBe(k); }
  });
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

describe("removed UI: summary disclaimer, cache/stale labels, limitations section", () => {
  it("summary title is just Summary / Ozet; cache and stale strings are gone", () => {
    expect(makeT("en")("sum.title")).toBe("Summary");
    expect(makeT("tr")("sum.title")).toBe("Özet");
    for (const lang of ["en", "tr"] as const) {
      const t = makeT(lang);
      for (const k of ["live.cache", "live.stale", "tip.cache", "tip.stale"]) expect(t(k)).toBe(k);
    }
  });
  it("About page shows the page title, Project summary, How to read this app, Plain-language glossary and Data sources, in that order (EN and TR)", () => {
    const SUMMARY_EN = "Metalimnion is a visual analysis app which simplifies the viewing and observation of lakes worldwide and significant changes that have affected said lakes. Metalimnion is a sophisticated app that can display individual measurements of area and surface temperature over the years and analyze these measurements to attribute changes to climatological phenomena or human activity. The analyses are then evaluated on the basis of reliability and are summarized. All analyzed lakes are shown on the various available easy-to-navigate maps with helpful circles and name descriptors. It addresses the challenge by making significant changes regarding lakes much easier to view and reason about, especially for non-experts. It allows everyone to see the change and future predictions concerning water area and surface temperature allowing them to act against the day by day shrinking of water resources, which are already very limited. This matters because global water trends affect many living things worldwide, and more attention must be drawn to crucial concerns such as this if we, the people, want to tend to our planet well.";
    for (const lang of ["en", "tr"] as const) {
      const { container, unmount } = render(<I18nProvider initial={lang}><MethodsPage /></I18nProvider>);
      expect(container.querySelector("h1")?.textContent).toBe(lang === "en" ? "About" : "Hakkında");
      const heads = [...container.querySelectorAll("h2")].map((h) => h.textContent);
      expect(heads).toEqual(lang === "en" ? ["Project summary", "How to read this app", "Plain-language glossary", "Data sources"] : ["Proje özeti", "Bu uygulama nasıl okunur", "Sade dille sözlük", "Veri kaynakları"]);
      expect([...container.querySelectorAll("h3")].map((h) => h.textContent)).toEqual(lang === "en" ? ["NASA", "NASA Partnered", "Non-NASA"] : ["NASA", "NASA Ortaklı", "NASA dışı"]);
      const t = makeT(lang);
      expect(container.querySelectorAll("p").length).toBe(3);
      expect(container.querySelectorAll("p")[0].textContent).toBe(t("sum.proj.body"));
      expect(container.querySelectorAll("p")[1].textContent).toBe(t("how.body"));
      expect(container.querySelectorAll("p")[2].textContent).toBe(t("gl.intro"));
      if (lang === "en") {
        expect(container.querySelectorAll("p")[0].textContent).toBe(SUMMARY_EN);
      } else {
        expect(container.querySelectorAll("p")[0].textContent).toMatch(/^Metalimnion, dünya genelindeki göllerin/);
      }
      expect(container.textContent).not.toMatch(/Report Summary|Update III/);
      for (const name of [/limitations|sınırlamalar/i, /^method$|^yöntem$/i, /validation|doğrulama/i]) {
        expect(screen.queryByRole("heading", { name })).toBeNull();
      }
      expect(container.querySelector("table, ul")).toBeNull();
      expect(container.querySelectorAll("ol").length).toBe(3);
      expect(container.textContent).not.toMatch(/Live cards come from public APIs|Akşehir is flagged low reliability|Landsat Collection 2|Sabuncu/);
      unmount();
    }
  });
  it("About Data sources: 10 items in order, exact hrefs, new-tab links, no doi.org (EN and TR)", () => {
    const GIBS = "https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api";
    const EXPECTED: [string, string][] = [
      ["NASA POWER monthly API", "https://power.larc.nasa.gov/"],
      ["MERRA-2 tavg1_2d_lnd_Nx (NASA GMAO)", "https://www.earthdata.nasa.gov/data/catalog/ges-disc-m2t1nxlnd-5.12.4"],
      ["NASA GIBS, layer VIIRS NOAA-20 Corrected Reflectance True Color", GIBS],
      ["NASA GIBS, layer Blue Marble Shaded Relief and Bathymetry", GIBS],
      ["Landsat 4-5 TM Collection 2 Level-2 (NASA/USGS)", "https://www.usgs.gov/centers/eros/science/usgs-eros-archive-landsat-archives-landsat-4-5-tm-collection-2-level-2-science"],
      ["Landsat 8-9 OLI/TIRS Collection 2 Level-2 (NASA/USGS)", "https://www.usgs.gov/centers/eros/science/usgs-eros-archive-landsat-archives-landsat-8-9-olitirs-collection-2-level-2"],
      ["Microsoft Planetary Computer", "https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2"],
      ["HydroBASINS (HydroSHEDS)", "https://www.hydrosheds.org/products/hydrobasins"],
      ["Natural Earth 10m lakes and countries", "https://www.naturalearthdata.com/downloads/10m-physical-vectors/"],
      ["OpenFreeMap", "https://openfreemap.org/"],
    ];
    for (const lang of ["en", "tr"] as const) {
      const { container, unmount } = render(<I18nProvider initial={lang}><MethodsPage /></I18nProvider>);
      const links = [...container.querySelectorAll("a")];
      expect(links.map((a) => [a.textContent, a.getAttribute("href")])).toEqual(EXPECTED);
      const lis = [...container.querySelectorAll("ol li")];
      expect(lis.length).toBe(10);
      lis.forEach((li, i) => { expect(li.querySelector("a")).toBe(links[i]); expect(li.textContent!.length).toBeGreaterThan(links[i].textContent!.length + 5); });
      const ols = [...container.querySelectorAll("ol")];
      expect(ols.map((o) => o.querySelectorAll("li").length)).toEqual([4, 2, 4]);
      expect(ols.map((o) => o.getAttribute("start"))).toEqual(["1", "5", "7"]);
      expect(ols[1].textContent).toMatch(/^Landsat 4-5 TM.*Landsat 8-9 OLI\/TIRS/);
      for (const a of links) {
        expect(a.getAttribute("target")).toBe("_blank");
        expect(a.getAttribute("rel")).toBe("noopener noreferrer");
        expect(a.getAttribute("href")).not.toContain("doi.org");
      }
      expect(container.innerHTML).not.toContain("doi.org");
      expect([...container.querySelectorAll("ol")].map((o) => o.textContent).join(" ")).not.toMatch(/SWOT/);
      expect(container.textContent).not.toMatch(/SWOT/i); // whole About page, EN and TR
      if (lang === "tr") {
        expect(container.textContent).toContain("Su alanı ve yüzey sıcaklığı, 1985-2012.");
        expect(container.textContent).toContain("Çevrimiçi vektör altlık harita.");
        expect(container.textContent).not.toMatch(/Water area|Online vector/);
      }
      unmount();
    }
  });
  it("About glossary: one dt/dd pair per GLOSSARY entry, in order, EN and TR", () => {
    expect(GLOSSARY.length).toBe(13);
    expect(GLOSSARY.map((g) => g[0])).toEqual(["Landsat", "MNDWI", "Sen slope", "p-value / significant", "σ (sigma) and normal range", "Emergence year", "Surface temperature (LST)", "Sensor break", "P−E", "EVLAND", "Climate share", "Not computable", "Reliability"]);
    for (const lang of ["en", "tr"] as const) {
      const { container, unmount } = render(<I18nProvider initial={lang}><MethodsPage /></I18nProvider>);
      const dl = container.querySelector("dl.glossary")!;
      expect(dl).not.toBeNull();
      expect(dl.querySelectorAll("dt").length).toBe(GLOSSARY.length);
      expect(dl.querySelectorAll("dd").length).toBe(GLOSSARY.length);
      expect([...dl.querySelectorAll("dt")].map((e) => e.textContent)).toEqual(GLOSSARY.map((g) => g[0]));
      expect([...dl.querySelectorAll("dd")].map((e) => e.textContent)).toEqual(GLOSSARY.map((g) => g[lang === "tr" ? 2 : 1]));
      expect(container.querySelector("h2#glossary")?.textContent).toBe(lang === "en" ? "Plain-language glossary" : "Sade dille sözlük");
      expect(container.querySelector("dl.glossary")!.textContent).not.toMatch(/1997|censored/);
      expect(container.textContent).not.toMatch(/\(see About\)|Hakkında sayfasına bakın/);
      unmount();
    }
    expect(makeT("en")("gl.intro")).toBe("Short explanations of the technical words used in this app.");
    expect(makeT("tr")("gl.intro")).toBe("Bu uygulamada geçen teknik sözcüklerin kısa açıklamaları.");
  });
});

describe("About section route", () => {
  it("nav shows About / Hakkında linking /about, and /methods redirects to /about", async () => {
    for (const [lang, label] of [["en", "About"], ["tr", "Hakkında"]] as const) {
      const { unmount } = render(<I18nProvider initial={lang}><MemoryRouter initialEntries={["/methods"]}><App /></MemoryRouter></I18nProvider>);
      const link = screen.getByRole("link", { name: label });
      expect(link.getAttribute("href")).toBe("/about");
      await waitFor(() => expect(link.getAttribute("aria-current")).toBe("page"));
      expect(await screen.findByRole("heading", { level: 1, name: label })).toBeTruthy();
      unmount();
    }
  });
});

describe("no per-lake method limitation note", () => {
  it("RefInfo ignores mndwi_note (EN and TR) and the ref.mndwi key is gone", () => {
    const sum = { ...burdurFull.summary, why_selected: "why text", cadence_note: "every year", mndwi_note: "MNDWI limitation: salt crust SECRET-NOTE" };
    for (const lang of ["en", "tr"] as const) {
      const { container, unmount } = render(<I18nProvider initial={lang}><PanelMod.RefInfo s={sum} /></I18nProvider>);
      expect(container.textContent).toContain("why text");
      expect(container.textContent).not.toMatch(/SECRET-NOTE|Method limitation|Yöntem sınırlaması/);
      expect(container.querySelector(".note.warn")).toBeNull();
      expect(makeT(lang)("ref.mndwi")).toBe("ref.mndwi");
      unmount();
    }
  });
});

describe("removed UI: Turkish / reference lake distinction", () => {
  it("group strings are gone in EN and TR, legend size key and light basemap strings exist", () => {
    for (const lang of ["en", "tr"] as const) {
      const t = makeT(lang);
      for (const k of ["cmp.turkey", "cmp.reference", "grp.all", "grp.turkey", "grp.reference", "col.group", "leg.turkey", "cmp.leg.turkey", "cmp.leg.reference"]) expect(t(k)).toBe(k);
      for (const k of ["bm.vectorlight", "leg.size.title", "leg.size.rule", "leg.size.clamp", "map.date.min"]) expect(t(k)).not.toBe(k);
    }
    expect(makeT("en")("bm.vectorlight")).toBe("Vector (light)");
    expect(makeT("tr")("bm.vectorlight")).toBe("Vektör (açık)");
  });
  it("Methods page no longer talks about reference lakes", () => {
    const { container } = render(<I18nProvider initial="en"><MethodsPage /></I18nProvider>);
    expect(container.textContent).not.toMatch(/reference lakes/i);
  });
});

describe("null numbers from the server (NaN is sent as null)", () => {
  const t = makeT("en");
  const nullStats = { n: 41, trend: "no trend", p: null, sen_slope_per_year: null, sen_slope_per_decade: null, intercept: null, intercept_year: 1985 };
  it("area and LST options skip a Sen line whose numbers are null instead of crashing", () => {
    const d = { ...burdurFull, stats: { area: nullStats, lst_1985_2012: nullStats } };
    const a: any = areaOption(d, t);
    expect(a.series.map((s: any) => s.name)).not.toContain(t("ser.sen"));
    const l: any = ChartsMod.lstOption(d, t);
    expect(l.series.map((s: any) => s.name)).not.toContain(t("ser.lst5"));
  });
  it("forecast tooltip and sentences tolerate null values", () => {
    const yrs = [2026, 2027];
    const f = { ok: true, horizon_year: 2027, n_valid: 40, note: "x", model: "sen_recent" as const, last_observed_year: 2025, last_observed_km2: 100, interpretable: true,
      years: yrs, median: [null, 90], lo90: [null, 80], hi90: [null, 95], lo50: [null, 85], hi50: [null, 92], flags: [],
      milestones: [{ year: 2027, median_km2: null, lo90_km2: null, hi90_km2: null, median_pct_of_ref: null }],
      backtest: { n_origins: 5, n_pairs: 10, max_horizon_years: 5, mae_km2: {}, skill_vs_persistence: {}, chosen_skill: null, coverage90: null } };
    const o: any = ChartsMod.forecastOption({ ...burdurFull, forecast: f }, f, t);
    const tip = o.tooltip.formatter([{ value: [2026, 1], seriesName: "x" }]);
    expect(tip).not.toMatch(/NaN|undefined|null/);
    expect(() => ChartsMod.forecastSentences(f, burdurFull.summary, t)).not.toThrow();
    expect(() => render(<ForecastChart d={{ ...burdurFull, forecast: f }} />)).not.toThrow();
  });
  it("the failed-analysis message reads cleanly in EN and TR and leaks no server wording", () => {
    for (const lang of ["en", "tr"] as const) {
      const msg = makeT(lang)("an.failed.msg");
      expect(msg).not.toBe("an.failed.msg");
      expect(msg).not.toMatch(/server log|analysis failed/i);
    }
  });
});
