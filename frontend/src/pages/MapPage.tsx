import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useI18n } from "../i18n";
import { TREND } from "../lib/palette";
import { useIndex, useLakes } from "../hooks";
import { api } from "../lib/api";
import MapView, { type Basemap } from "../components/MapView";
import Panel, { clampWidth, type PanelLayout, type Selection } from "../components/Panel";
import Timeline from "../components/Timeline";

const loadLayout = (): PanelLayout => {
  try { const j = JSON.parse(localStorage.getItem("panelLayout") ?? ""); return { width: clampWidth(Number(j.width) || 430, window.innerWidth), expanded: !!j.expanded }; } catch { return { width: 430, expanded: false }; }
};
const yesterday = () => new Date(Date.now() - 86400_000 * 2).toISOString().slice(0, 10);

export default function MapPage() {
  const { t } = useI18n();
  const lakes = useLakes();
  const index = useIndex();
  const [sel, setSel] = useState<Selection | null>(null);
  const [basemap, setBasemap] = useState<Basemap>(typeof navigator !== "undefined" && navigator.onLine === false ? "offline" : "bluemarble"); // default NASA Blue Marble; offline/unreachable -> local country basemap (no saved choice exists)
  const [autoOffline, setAutoOffline] = useState(false);
  const [date, setDate] = useState(yesterday());
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
              <option value="vector">{t("bm.vector")}</option><option value="bluemarble">{t("bm.blue")}</option>
              <option value="viirs">{t("bm.viirs")}</option><option value="offline">{t("bm.offline")}</option>
            </select></label>
          {basemap === "viirs" && <label>{t("map.date")} <input type="date" value={date} max={yesterday()} onChange={(e) => e.target.value && setDate(e.target.value)} /></label>}
        </div>
        <div className={"stack" + (lake && years ? " above-timeline" : "")} data-testid="stack">
        {autoOffline && <div className="hint" role="status" data-testid="offline-note">{t("map.offline_auto")}</div>}
        {!sel && <div className="hint">{lakes.isLoading ? t("map.loading") : t("map.hint")}</div>}
        <div className={"legend"} data-testid="legend">
          <strong>{t("map.legend")}</strong>
          <div><i style={{ background: TREND.fast }} /> {t("leg.fast")}</div>
          <div><i style={{ background: TREND.slow }} /> {t("leg.slow")}</div>
          <div><i style={{ background: TREND.ns }} /> {t("leg.ns")}</div>
          <div><i style={{ background: TREND.inc }} /> {t("leg.inc")}</div>
          <div className="small muted">{t("leg.size")}</div>
          <div className="small muted">{t("leg.turkey")}</div>
        </div>
        </div>
        {lake && years && <Timeline lakeId={lake.id} years={years} year={y} setYear={setYear} />}
      </div>
      {sel && <Panel sel={sel} onClose={() => setSel(null)} layout={layout} onLayout={setLayout} />}
    </div>
  );
}
