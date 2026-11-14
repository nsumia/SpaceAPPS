import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { GeoJSONSource, ImageSource, StyleSpecification } from "maplibre-gl";
import { TerraDraw, TerraDrawPolygonMode, TerraDrawRectangleMode } from "terra-draw";
import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter";
import { api } from "../lib/api";
import { trendColour } from "../lib/compare";
import type { LakeSummary, MaskJson } from "../lib/types";
import type { Selection } from "./Panel";

maplibregl.setWorkerUrl(workerUrl);

export type Basemap = "vector" | "bluemarble" | "viirs" | "none";
export type DrawMode = "off" | "rectangle" | "polygon";
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";
const BG = "#0f141b";

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
  return { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": BG } }] };
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
  basemap: Basemap; date: string; drawMode: DrawMode; masks: { base: MaskJson; cur: MaskJson } | null;
  onSelect: (s: Selection) => void; onDraw: (g: GeoJSON.Geometry) => void; onBasemapFallback: () => void;
}

const empty: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export default function MapView(props: MapProps) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const pr = useRef(props);
  pr.current = props;
  const drawRef = useRef<TerraDraw | null>(null);
  const maskTok = useRef(0);
  const styleOk = useRef(false);

  const lakesGeo = (): GeoJSON.FeatureCollection => ({
    type: "FeatureCollection",
    features: pr.current.lakes.filter((l) => l.centre).map((l) => ({
      type: "Feature", geometry: { type: "Point", coordinates: l.centre as [number, number] },
      properties: { id: l.id, name: l.name, colour: trendColour(l), ring: l.group === "turkey" ? "#ffd166" : "#0b0f14", r: circleRadius(l.latest_area_km2), area: l.latest_area_km2 ?? 0 } })),
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
      map.addLayer({ id: "index-fill", type: "fill", source: "index", minzoom: 5.5, paint: { "fill-color": "#4aa3df", "fill-opacity": 0.16 } });
      map.addLayer({ id: "index-line", type: "line", source: "index", minzoom: 5.5, paint: { "line-color": "#7fb8e6", "line-width": 0.8, "line-opacity": 0.7 } });
      map.addLayer({ id: "hl-fill", type: "fill", source: "hl", paint: { "fill-color": "#ffffff", "fill-opacity": 0.1 } });
      map.addLayer({ id: "hl-line", type: "line", source: "hl", paint: { "line-color": "#ffffff", "line-width": 2, "line-dasharray": [2, 1] } });
      map.addLayer({ id: "lakes-circle", type: "circle", source: "lakes", paint: {
        "circle-color": ["get", "colour"], "circle-radius": ["get", "r"], "circle-opacity": 0.85, "circle-stroke-color": ["get", "ring"], "circle-stroke-width": 2 } });
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
    if (!map || !map.isStyleLoaded()) return;
    const m = pr.current.masks, tok = ++maskTok.current;
    for (const id of ["mask-cur", "mask-base"]) { if (!m && map.getLayer(id)) map.removeLayer(id); if (!m && map.getSource(id)) map.removeSource(id); }
    if (!m) return;
    const [base, cur] = await Promise.all([tintMask(m.base.png_data_uri, [169, 207, 238], 150), tintMask(m.cur.png_data_uri, [11, 61, 145], 215)]);
    if (tok !== maskTok.current || !map.isStyleLoaded()) return;
    const put = (id: string, url: string, coordinates: MaskJson["coordinates"], before?: string) => {
      const src = map.getSource(id) as ImageSource | undefined;
      if (src) src.updateImage({ url, coordinates: coordinates as any });
      else { map.addSource(id, { type: "image", url, coordinates: coordinates as any }); map.addLayer({ id, type: "raster", source: id, paint: { "raster-fade-duration": 0, "raster-resampling": "nearest" } }, before); }
    };
    put("mask-base", base, m.base.coordinates, "lakes-circle");
    put("mask-cur", cur, m.cur.coordinates, "lakes-circle");
  };

  const startDraw = () => {
    const map = mapRef.current;
    try { drawRef.current?.stop(); } catch { /* style swapped */ }
    drawRef.current = null;
    if (!map) return;
    const draw = new TerraDraw({ adapter: new TerraDrawMapLibreGLAdapter({ map }), modes: [new TerraDrawRectangleMode(), new TerraDrawPolygonMode()] });
    draw.start();
    draw.on("finish", (id) => {
      const f = draw.getSnapshot().find((x) => x.id === id);
      if (f && f.geometry.type === "Polygon") { pr.current.onDraw(f.geometry as GeoJSON.Geometry); draw.clear(); draw.setMode("static"); }
    });
    drawRef.current = draw;
    if (pr.current.drawMode !== "off") draw.setMode(pr.current.drawMode);
  };

  useEffect(() => {
    const p = pr.current;
    const map = new maplibregl.Map({ container: el.current!, style: basemapStyle(p.basemap, p.date), center: [34, 38.8], zoom: 4.6,
      attributionControl: { compact: true } });
    mapRef.current = map;
    (window as any).__map = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("style.load", () => { styleOk.current = true; syncAll(); startDraw(); });
    map.on("error", (e) => {
      const url = String((e as any).error?.url ?? (e as any).error?.message ?? "");
      if (!styleOk.current && pr.current.basemap === "vector" && /openfreemap|Failed to fetch|NetworkError|style/i.test(url)) pr.current.onBasemapFallback();
    });
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });
    map.on("mousemove", "lakes-circle", (e) => {
      map.getCanvas().style.cursor = "pointer";
      const f = e.features?.[0];
      if (f) popup.setLngLat(e.lngLat).setText(String(f.properties?.name)).addTo(map);
    });
    map.on("mouseleave", "lakes-circle", () => { map.getCanvas().style.cursor = ""; popup.remove(); });
    map.on("click", async (e) => {
      if (pr.current.drawMode !== "off") return;
      const hit = map.getLayer("lakes-circle") ? map.queryRenderedFeatures(e.point, { layers: ["lakes-circle"] })[0] : undefined;
      if (hit) { pr.current.onSelect({ id: String(hit.properties?.id), name: String(hit.properties?.name) }); return; }
      if (map.getZoom() < 5.5) return;
      try {
        const r = await api.identify(e.lngLat.lng, e.lngLat.lat);
        pr.current.onSelect({ id: r.id, name: r.name, polygon: r.polygon });
      } catch { /* no lake at this point */ }
    });
    return () => { try { drawRef.current?.stop(); } catch { /* ignore */ } map.remove(); mapRef.current = null; };
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
    const d = drawRef.current;
    if (!d) return;
    try { d.setMode(props.drawMode === "off" ? "static" : props.drawMode); } catch { /* not started */ }
  }, [props.drawMode]);
  useEffect(() => {
    const l = props.lakes.find((x) => x.id === props.selectedId);
    const map = mapRef.current;
    if (l?.centre && map && map.getZoom() < 7) map.flyTo({ center: l.centre, zoom: 8.5, duration: 900 });
  }, [props.selectedId]);

  return <div ref={el} className="map" data-testid="map" />;
}
