import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { GeoJSONSource, ImageSource, StyleSpecification } from "maplibre-gl";
import { api, type LakeSummary, type MaskJson } from "../lib/api";
import { MASK, spectrumExpression, trendValue } from "../lib/util";
import type { Selection } from "./Panel";

maplibregl.setWorkerUrl(workerUrl);

export type Basemap = "vector" | "bluemarble" | "viirs" | "offline";
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";
const BG = "#0e0e0e";

export function basemapStyle(bm: Basemap, date: string): StyleSpecification | string {
  const raster = (id: string, tiles: string, maxzoom: number, attribution: string): StyleSpecification => ({
    version: 8,
    sources: { [id]: { type: "raster", tiles: [tiles], tileSize: 256, maxzoom, attribution } },
    layers: [{ id: "bg", type: "background", paint: { "background-color": BG } }, { id, type: "raster", source: id }],
  });
  if (bm === "vector") return "https://tiles.openfreemap.org/styles/dark";
  if (bm === "bluemarble")
    return raster("gibs", `${GIBS}/BlueMarble_ShadedRelief_Bathymetry/default/2004-08-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg`, 8, "NASA GIBS Blue Marble");
  if (bm === "viirs")
    return raster("gibs", `${GIBS}/VIIRS_NOAA20_CorrectedReflectance_TrueColor/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`, 9, "NASA GIBS VIIRS NOAA-20");
  // offline: local Natural Earth 50m country borders served by the API (no external host)
  return { version: 8, sources: { countries: { type: "geojson", data: "/api/basemap/countries" } }, layers: [
    { id: "bg", type: "background", paint: { "background-color": BG } },
    { id: "countries-fill", type: "fill", source: "countries", paint: { "fill-color": "#1c1c1c" } },
    { id: "countries-line", type: "line", source: "countries", paint: { "line-color": "#7d7d7d", "line-width": 0.9 } }] };
}

export function circleRadius(area: number | null): number {
  return Math.max(6, Math.min(24, 4 + Math.sqrt(area ?? 20) * 0.55));
}

/** Turn the uint8 mask PNG (255 water, 90 land, 0 no data) into a translucent single-colour overlay. */
export async function tintMask(uri: string, rgb: [number, number, number], alpha: number): Promise<string> {
  const img = new Image();
  img.src = uri;
  await img.decode();
  const c = document.createElement("canvas");
  c.width = img.width; c.height = img.height;
  const ctx = c.getContext("2d")!;
  ctx.drawImage(img, 0, 0);
  const d = ctx.getImageData(0, 0, c.width, c.height);
  for (let i = 0; i < d.data.length; i += 4) {
    const water = d.data[i] > 200 && d.data[i + 3] > 0;
    d.data[i] = rgb[0]; d.data[i + 1] = rgb[1]; d.data[i + 2] = rgb[2]; d.data[i + 3] = water ? alpha : 0;
  }
  ctx.putImageData(d, 0, 0);
  return c.toDataURL("image/png");
}

export interface MapProps {
  lakes: LakeSummary[]; index?: GeoJSON.FeatureCollection; selectedId: string | null; highlight: GeoJSON.Geometry | null;
  basemap: Basemap; date: string; masks: { base: MaskJson; cur: MaskJson } | null;
  onSelect: (s: Selection) => void; onBasemapFallback: () => void;
}

const empty: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export default function MapView(props: MapProps) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const pr = useRef(props);
  pr.current = props;
  const maskTok = useRef(0);
  const styleOk = useRef(false);

  const lakesGeo = (): GeoJSON.FeatureCollection => ({
    type: "FeatureCollection",
    features: pr.current.lakes.filter((l) => l.centre).map((l) => ({
      type: "Feature", geometry: { type: "Point", coordinates: l.centre as [number, number] },
      properties: { id: l.id, name: l.name, ...(trendValue(l) != null ? { trend: trendValue(l) } : {}), ring: l.group === "turkey" ? "#f472ae" : "#ffffff", r: circleRadius(l.latest_area_km2), area: l.latest_area_km2 ?? 0 } })),
  });

  const syncAll = () => {
    const map = mapRef.current;
    if (!map) return;
    if (!map.isStyleLoaded()) { map.once("idle", syncAll); return; }
    const p = pr.current;
    if (!map.getSource("lakes")) {
      map.addSource("index", { type: "geojson", data: empty });
      map.addSource("lakes", { type: "geojson", data: empty });
      map.addSource("hl", { type: "geojson", data: empty });
      // Fit the OpenFreeMap dark style to the navy theme (guarded: ids may differ between style versions).
      for (const [id, prop, col] of [["background", "background-color", BG], ["water", "fill-color", "#0a1830"], ["landcover_wood", "fill-color", "#161616"], ["landuse_park", "fill-color", "#161616"]] as const)
        if (map.getLayer(id)) { try { map.setPaintProperty(id, prop, col); } catch { /* keep the stock colour */ } }
      map.addLayer({ id: "index-fill", type: "fill", source: "index", minzoom: 5.5, paint: { "fill-color": "#4cc9e0", "fill-opacity": 0.22 } });
      map.addLayer({ id: "index-line", type: "line", source: "index", minzoom: 5.5, paint: { "line-color": "#a9e3f2", "line-width": 1, "line-opacity": 0.85 } });
      map.addLayer({ id: "hl-fill", type: "fill", source: "hl", paint: { "fill-color": "#ffffff", "fill-opacity": 0.1 } });
      map.addLayer({ id: "hl-line", type: "line", source: "hl", paint: { "line-color": "#ffffff", "line-width": 2, "line-dasharray": [2, 1] } });
      map.addLayer({ id: "lakes-halo", type: "circle", source: "lakes", paint: { "circle-color": "#0e0e0e", "circle-opacity": 0.5, "circle-radius": ["+", ["get", "r"], 4], "circle-blur": 0.6 } });
      map.addLayer({ id: "lakes-circle", type: "circle", source: "lakes", paint: {
        "circle-color": spectrumExpression() as never, "circle-radius": ["get", "r"], "circle-opacity": 0.92, "circle-stroke-color": ["get", "ring"], "circle-stroke-width": 2 } });
      map.addLayer({ id: "lakes-sel", type: "circle", source: "lakes", filter: ["==", ["get", "id"], ""], paint: {
        "circle-color": "rgba(0,0,0,0)", "circle-radius": ["+", ["get", "r"], 4], "circle-stroke-color": "#ffffff", "circle-stroke-width": 2.5 } });
    }
    (map.getSource("lakes") as GeoJSONSource).setData(lakesGeo());
    if (p.index) (map.getSource("index") as GeoJSONSource).setData(p.index);
    (map.getSource("hl") as GeoJSONSource).setData(p.highlight ? { type: "Feature", geometry: p.highlight, properties: {} } : empty);
    map.setFilter("lakes-sel", ["==", ["get", "id"], p.selectedId ?? ""]);
    syncMasks();
  };

  const syncMasks = async () => {
    const map = mapRef.current;
    if (!map) return;
    if (!map.isStyleLoaded()) { map.once("idle", syncMasks); return; } // raster tiles still loading (Blue Marble): retry when idle
    const m = pr.current.masks, tok = ++maskTok.current;
    for (const id of ["mask-cur", "mask-base"]) { if (!m && map.getLayer(id)) map.removeLayer(id); if (!m && map.getSource(id)) map.removeSource(id); }
    if (!m) return;
    const [base, cur] = await Promise.all([tintMask(m.base.png_data_uri, MASK.base, 170), tintMask(m.cur.png_data_uri, MASK.cur, 235)]);
    if (tok !== maskTok.current) return;
    if (!map.isStyleLoaded()) { map.once("idle", syncMasks); return; }
    const put = (id: string, url: string, coordinates: MaskJson["coordinates"], before?: string) => {
      const src = map.getSource(id) as ImageSource | undefined;
      if (src) src.updateImage({ url, coordinates: coordinates as any });
      else { map.addSource(id, { type: "image", url, coordinates: coordinates as any }); map.addLayer({ id, type: "raster", source: id, paint: { "raster-fade-duration": 0, "raster-resampling": "nearest" } }, before); }
    };
    put("mask-base", base, m.base.coordinates, "lakes-halo");
    put("mask-cur", cur, m.cur.coordinates, "lakes-halo");
  };

  useEffect(() => {
    const p = pr.current;
    const map = new maplibregl.Map({ container: el.current!, style: basemapStyle(p.basemap, p.date), center: [34, 38.8], zoom: 4.6,
      attributionControl: { compact: true } });
    mapRef.current = map;
    (window as any).__map = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("style.load", () => { styleOk.current = true; syncAll(); });
    let netErrors = 0;
    map.on("error", (e) => {
      const err = (e as any).error;
      const url = String(err?.url ?? err?.message ?? "");
      if (pr.current.basemap === "offline") return;
      if (!styleOk.current && pr.current.basemap === "vector" && /openfreemap|Failed to fetch|NetworkError|style/i.test(url)) { pr.current.onBasemapFallback(); return; }
      // tile servers unreachable after the style loaded (GIBS, OpenFreeMap tiles): after a few failures use the offline basemap
      if (/Failed to fetch|NetworkError|Load failed|ERR_INTERNET|ERR_NAME|ERR_FAILED/i.test(String(err?.message ?? "")) && ++netErrors >= 3) pr.current.onBasemapFallback();
    });
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });
    map.on("mousemove", "lakes-circle", (e) => {
      map.getCanvas().style.cursor = "pointer";
      const f = e.features?.[0];
      if (f) popup.setLngLat(e.lngLat).setText(String(f.properties?.name)).addTo(map);
    });
    map.on("mouseleave", "lakes-circle", () => { map.getCanvas().style.cursor = ""; popup.remove(); });
    map.on("click", async (e) => {
      const hit = map.getLayer("lakes-circle") ? map.queryRenderedFeatures(e.point, { layers: ["lakes-circle"] })[0] : undefined;
      if (hit) { pr.current.onSelect({ id: String(hit.properties?.id), name: String(hit.properties?.name) }); return; }
      if (map.getZoom() < 5.5) return;
      try {
        const r = await api.identify(e.lngLat.lng, e.lngLat.lat);
        pr.current.onSelect({ id: r.id, name: r.name, polygon: r.polygon });
      } catch { /* no lake at this point */ }
    });
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => map.resize()) : null;
    ro?.observe(el.current!);
    return () => { ro?.disconnect(); map.remove(); mapRef.current = null; };
  }, []);

  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    styleOk.current = false;
    mapRef.current?.setStyle(basemapStyle(props.basemap, props.date));
  }, [props.basemap, props.date]);
  useEffect(() => { syncAll(); }, [props.lakes, props.index, props.selectedId, props.highlight]);
  useEffect(() => { syncMasks(); }, [props.masks]);
  useEffect(() => {
    const l = props.lakes.find((x) => x.id === props.selectedId);
    const map = mapRef.current;
    if (l?.centre && map && map.getZoom() < 7) map.flyTo({ center: l.centre, zoom: 8.5, duration: 900 });
  }, [props.selectedId]);

  return <div ref={el} className="map" data-testid="map" />;
}
