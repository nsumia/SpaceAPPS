import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useI18n } from "../i18n";
import { useIndex, useLakes } from "../hooks";
import { api } from "../lib/api";
import MapView, { type Basemap, type DrawMode } from "../components/MapView";
import Panel, { type Selection } from "../components/Panel";
import Timeline from "../components/Timeline";

const yesterday = () => new Date(Date.now() - 86400_000 * 2).toISOString().slice(0, 10);

export default function MapPage() {
  const { t } = useI18n();
  const lakes = useLakes();
  const index = useIndex();
  const [sel, setSel] = useState<Selection | null>(null);
  const [basemap, setBasemap] = useState<Basemap>("vector");
  const [date, setDate] = useState(yesterday());
  const [draw, setDraw] = useState<DrawMode>("off");
  const [year, setYear] = useState(2025);

  const lake = lakes.data?.find((l) => l.id === sel?.id);
  const years = lake?.years ?? null;
  const y = years ? Math.min(Math.max(year, years[0]), years[1]) : year;
  const base = useQuery({ queryKey: ["mask", lake?.id, years?.[0]], queryFn: () => api.mask(lake!.id, years![0]), enabled: !!lake && !!years, staleTime: Infinity });
  const cur = useQuery({ queryKey: ["mask", lake?.id, y], queryFn: () => api.mask(lake!.id, y), enabled: !!lake && !!years, staleTime: Infinity });
  const masks = base.data && cur.data ? { base: base.data, cur: cur.data } : null;

  const select = (s: Selection) => { setSel(s); setDraw("off"); const l = lakes.data?.find((x) => x.id === s.id); if (l?.years) setYear(l.years[1]); };
  return (
    <div className="mappage">
      <div className="mapwrap">
        <MapView lakes={lakes.data ?? []} index={index.data} selectedId={sel?.id ?? null} highlight={sel?.polygon ?? null}
          basemap={basemap} date={date} drawMode={draw} masks={masks} onSelect={select}
          onDraw={(g) => { setSel({ id: null, name: t("map.draw"), polygon: g }); setDraw("off"); }}
          onBasemapFallback={() => setBasemap("none")} />
        <div className="toolbar" data-testid="toolbar">
          <label>{t("map.basemap")}
            <select value={basemap} onChange={(e) => setBasemap(e.target.value as Basemap)}>
              <option value="vector">{t("bm.vector")}</option><option value="bluemarble">{t("bm.blue")}</option>
              <option value="viirs">{t("bm.viirs")}</option><option value="none">{t("bm.none")}</option>
            </select></label>
          {basemap === "viirs" && <label>{t("map.date")} <input type="date" value={date} max={yesterday()} onChange={(e) => e.target.value && setDate(e.target.value)} /></label>}
          <div className="seg" role="group" aria-label={t("map.draw")}>
            <span>{t("map.draw")}</span>
            <button className={draw === "rectangle" ? "on" : ""} onClick={() => setDraw(draw === "rectangle" ? "off" : "rectangle")} data-testid="draw-rect">{t("map.rect")}</button>
            <button className={draw === "polygon" ? "on" : ""} onClick={() => setDraw(draw === "polygon" ? "off" : "polygon")} data-testid="draw-poly">{t("map.poly")}</button>
            {sel && <button onClick={() => { setSel(null); setDraw("off"); }}>{t("map.clear")}</button>}
          </div>
        </div>
        <div className="legend">
          <strong>{t("map.legend")}</strong>
          <div><i style={{ background: "#a50f15" }} /> {t("leg.fast")}</div>
          <div><i style={{ background: "#d6604d" }} /> {t("leg.slow")}</div>
          <div><i style={{ background: "#9a9a9a" }} /> {t("leg.ns")}</div>
          <div><i style={{ background: "#56B4E9" }} /> {t("leg.inc")}</div>
          <div className="small muted">{t("leg.size")}</div>
          <div className="small muted">{t("leg.turkey")}</div>
        </div>
        {!sel && <div className="hint">{lakes.isLoading ? t("map.loading") : t("map.hint")}</div>}
        {lake && years && <Timeline lakeId={lake.id} years={years} year={y} setYear={setYear} />}
      </div>
      {sel && <Panel sel={sel} onClose={() => setSel(null)} />}
    </div>
  );
}
