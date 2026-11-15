import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useI18n } from "../i18n";
import { SPECTRUM_MAX, spectrumCss, TREND_NS, VIIRS_MIN_DATE, clampDate } from "../lib/util";
import { api, useIndex, useLakes } from "../lib/api";
import MapView, { circleRadius, sizeRange, SIZE_KEY_AREAS, type Basemap } from "../components/MapView";
import Panel, { clampWidth, type PanelLayout, type Selection } from "../components/Panel";

const loadLayout = (): PanelLayout => {
  try { const j = JSON.parse(localStorage.getItem("panelLayout") ?? ""); return { width: clampWidth(Number(j.width) || 430, window.innerWidth), expanded: !!j.expanded }; } catch { return { width: 430, expanded: false }; }
};
const yesterday = () => new Date(Date.now() - 86400_000 * 2).toISOString().slice(0, 10);

/** Legend size key: one SVG circle per sample area, drawn at the exact pixel radius the map uses (circleRadius) incl. the 2 px white ring. */
function SizeKey({ t }: { t: (k: string, v?: Record<string, string | number>) => string }) {
  const { min, max } = sizeRange();
  const rs = SIZE_KEY_AREAS.map((a) => circleRadius(a));
  const h = 2 * Math.max(...rs) + 4;
  return (
    <div className="sizekey" data-testid="size-key">
      <div className="sizekey-title"><strong>{t("leg.size.title")}</strong></div>
      <div className="small">{t("leg.size.rule")}</div>
      <div className="sizekey-row" style={{ height: h }}>
        {SIZE_KEY_AREAS.map((a, i) => (
          <figure key={a} data-r={rs[i]}>
            <svg width={2 * rs[i] + 4} height={2 * rs[i] + 4} aria-hidden="true">
              <circle cx={rs[i] + 2} cy={rs[i] + 2} r={rs[i]} fill={TREND_NS} stroke="#fff" strokeWidth={2} />
            </svg>
            <figcaption className="small">{a.toLocaleString("en")} km²</figcaption>
          </figure>))}
      </div>
      <div className="small muted">{t("leg.size.clamp", { min: Math.round(min).toLocaleString("en"), max: Math.round(max).toLocaleString("en") })}</div>
    </div>);
}

function Timeline({ lakeId, years, year, setYear }: { lakeId: string; years: [number, number]; year: number; setYear: (y: number) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [playing, setPlaying] = useState(false);
  const yr = useRef(year);
  yr.current = year;
  useEffect(() => {
    if (!playing) return;
    let stop = false;
    (async () => {
      while (!stop) {
        const next = yr.current >= years[1] ? years[0] : yr.current + 1;
        try { await qc.fetchQuery({ queryKey: ["mask", lakeId, next], queryFn: () => api.mask(lakeId, next), staleTime: Infinity }); } catch { /* missing year */ }
        if (stop) return;
        setYear(next);
        await new Promise((r) => setTimeout(r, 450));
      }
    })();
    return () => { stop = true; };
  }, [playing, lakeId]);
  return (
    <div className="timeline" data-testid="timeline">
      <button onClick={() => setPlaying((p) => !p)} aria-label={playing ? t("timeline.pause") : t("timeline.play")}>{playing ? "❚❚" : "▶"}</button>
      <input type="range" min={years[0]} max={years[1]} value={year} onChange={(e) => setYear(+e.target.value)} aria-label={t("timeline.year")} />
      <strong>{year}</strong>
      <span className="small muted">{t("timeline.legend")}</span>
    </div>
  );
}

export default function MapPage() {
  const { t } = useI18n();
  const lakes = useLakes();
  const index = useIndex();
  const [sel, setSel] = useState<Selection | null>(null);
  const [basemap, setBasemap] = useState<Basemap>(typeof navigator !== "undefined" && navigator.onLine === false ? "offline" : "bluemarble"); // default NASA Blue Marble; offline/unreachable -> local country basemap (no saved choice exists)
  const [autoOffline, setAutoOffline] = useState(false);
  const [date, setDate] = useState(yesterday());
  const [draft, setDraft] = useState(date); // what the date input shows while typing; only in-range dates reach the map
  const maxDate = yesterday();
  const [year, setYear] = useState(2025);
  const [layout, setLayoutState] = useState<PanelLayout>(loadLayout);
  const setLayout = (l: PanelLayout) => { setLayoutState(l); try { localStorage.setItem("panelLayout", JSON.stringify(l)); } catch { /* private mode */ } };

  const lake = lakes.data?.find((l) => l.id === sel?.id);
  const years = lake?.years ?? null;
  const y = years ? Math.min(Math.max(year, years[0]), years[1]) : year;
  const base = useQuery({ queryKey: ["mask", lake?.id, years?.[0]], queryFn: () => api.mask(lake!.id, years![0]), enabled: !!lake && !!years, staleTime: Infinity });
  const cur = useQuery({ queryKey: ["mask", lake?.id, y], queryFn: () => api.mask(lake!.id, y), enabled: !!lake && !!years, staleTime: Infinity });
  const masks = base.data && cur.data ? { base: base.data, cur: cur.data } : null;

  const select = (s: Selection) => { setSel(s); const l = lakes.data?.find((x) => x.id === s.id); if (l?.years) setYear(l.years[1]); };
  return (
    <div className="mappage">
      <div className="mapwrap">
        <MapView lakes={lakes.data ?? []} index={index.data} selectedId={sel?.id ?? null} highlight={sel?.polygon ?? null}
          basemap={basemap} date={date} masks={masks} onSelect={select}
          onBasemapFallback={() => { setBasemap("offline"); setAutoOffline(true); }} />
        <div className="toolbar" data-testid="toolbar">
          <label title={t("map.basemap.help")}>{t("map.basemap")}
            <select value={basemap} onChange={(e) => { setBasemap(e.target.value as Basemap); setAutoOffline(false); }}>
              <option value="vector">{t("bm.vector")}</option><option value="vectorlight">{t("bm.vectorlight")}</option><option value="bluemarble">{t("bm.blue")}</option>
              <option value="viirs">{t("bm.viirs")}</option><option value="offline">{t("bm.offline")}</option>
            </select></label>
          {basemap === "viirs" && <label title={t("map.date.min", { date: VIIRS_MIN_DATE })}>{t("map.date")} <input type="date" value={draft} min={VIIRS_MIN_DATE} max={maxDate} data-testid="viirs-date"
            onChange={(e) => { setDraft(e.target.value); const c = clampDate(e.target.value, VIIRS_MIN_DATE, maxDate); if (c && c === e.target.value) setDate(c); }}
            onBlur={() => { const c = clampDate(draft, VIIRS_MIN_DATE, maxDate) ?? date; setDraft(c); setDate(c); }} /></label>}
        </div>
        <div className={"stack" + (lake && years ? " above-timeline" : "")} data-testid="stack">
        {autoOffline && <div className="hint" role="status" data-testid="offline-note">{t("map.offline_auto")}</div>}
        {!sel && <div className="hint">{lakes.isLoading ? t("map.loading") : t("map.hint")}</div>}
        <div className={"legend"} data-testid="legend">
          <strong>{t("map.legend")}</strong>
          <div className="spectrum" style={{ background: spectrumCss() }} role="img" aria-label={t("leg.aria", { max: SPECTRUM_MAX })} data-testid="spectrum" />
          <div className="spectrum-ticks small" aria-hidden="true">
            {[-20, -10, 0, 10, 20].map((v) => <span key={v} style={{ left: `${((v + SPECTRUM_MAX) / (2 * SPECTRUM_MAX)) * 100}%` }}>{v > 0 ? "+" : v < 0 ? "\u2212" : ""}{Math.abs(v)}</span>)}
          </div>
          <div className="spectrum-ends"><span>{t("leg.shrinking")}</span><span>{t("leg.growing")}</span></div>
          <div className="spectrum-unit small">{t("leg.unit")}</div>
          <div><i className="ns" style={{ background: TREND_NS }} /> {t("leg.ns")}</div>
          <SizeKey t={t} />
        </div>
        </div>
        {lake && years && <Timeline lakeId={lake.id} years={years} year={y} setYear={setYear} />}
      </div>
      {sel && <Panel sel={sel} onClose={() => setSel(null)} layout={layout} onLayout={setLayout} />}
    </div>
  );
}
