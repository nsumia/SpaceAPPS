"""Metalimnion API. Run: .venv/bin/uvicorn backend.api.main:app   (OpenAPI UI at /docs)"""
import hashlib
import json
import os
from contextlib import asynccontextmanager
from functools import partial
from typing import Literal, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from backend.api import live_cache, store
from backend.api.jobs import JobManager
from backend.api.store import Settings

MAX_POLYGON_KM2 = 20_000.0
DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
SPA_ROUTES = ("compare", "methods")


# Response models, so the OpenAPI schema (and openapi-typescript) carry real types for /api/lakes.
class LakeSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    alias: Optional[str] = None
    name: Optional[str] = None
    country: Optional[str] = None
    centre: Optional[list[float]] = None
    group: Literal["turkey", "reference", "custom"]
    validated: bool
    unverified: bool
    years: Optional[list[int]] = None
    latest_area_km2: Optional[float] = None
    latest_area_year: Optional[int] = None
    ref_mean_km2: Optional[float] = None
    ref_years: list[int] = []
    recent_years: list[int] = []
    recent_mean_km2: Optional[float] = None
    total_loss_pct: Optional[float] = None
    total_loss_basis: str
    trend_pct_per_decade: Optional[float] = None
    trend_p: Optional[float] = None
    trend_direction: Optional[str] = None
    emergence_year: Optional[int] = None
    emergence_status: Optional[str] = None
    emergence_censored_at_ref_end: bool = False
    emergence_note: Optional[str] = None
    warming_c_per_decade: Optional[float] = None
    warming_basis: Optional[str] = None
    warming_pooled_c_per_decade: Optional[float] = None
    warming_sensor_break_caveat: str
    climate_explained_share: Optional[float] = None
    climate_explained_ci90: Optional[list[float]] = None
    climate_interpretable: bool = False
    climate_ci_includes_zero: bool = False
    climate_flags: list[str] = []
    climate_wording: Optional[str] = None
    reliability: str
    reliability_note: Optional[str] = None
    status: Optional[str] = None
    why_selected: Optional[str] = None
    mndwi_note: Optional[str] = None
    resolution_m: Optional[int] = None
    cadence_note: Optional[str] = None
    cadence_years: Optional[int] = None
    years_analysed: Optional[list[int]] = None
    window: Optional[list[str]] = None
    literature_direction: Optional[str] = None
    our_direction: Optional[str] = None
    literature_agrees: Optional[bool] = None
    literature_agreement: Optional[str] = None
    validation_basis: Optional[str] = None
    forecast_year: Optional[int] = None
    forecast_km2: Optional[float] = None
    forecast_pct_of_ref: Optional[float] = None


class LakesResponse(BaseModel):
    lakes: list[LakeSummary]


def polygon_area_km2(geom):
    import pyproj
    import shapely.ops
    t = pyproj.Transformer.from_crs(4326, 6933, always_xy=True).transform
    return shapely.ops.transform(t, geom).area / 1e6


def parse_polygon(obj):
    """GeoJSON Polygon/MultiPolygon/Feature -> (shapely geom, geometry dict). Raises ValueError with a clear message."""
    from shapely.geometry import shape
    if not isinstance(obj, dict):
        raise ValueError("polygon must be a GeoJSON object")
    if obj.get("type") == "Feature":
        obj = obj.get("geometry") or {}
    if obj.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("polygon must be a GeoJSON Polygon or MultiPolygon")
    try:
        g = shape(obj)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"invalid GeoJSON geometry: {e}") from e
    if g.is_empty or not g.is_valid:
        raise ValueError("polygon is empty or self-intersecting")
    minx, miny, maxx, maxy = g.bounds
    if not (-180 <= minx and maxx <= 180 and -90 <= miny and maxy <= 90):
        raise ValueError("coordinates must be lon/lat (EPSG:4326)")
    return g, dict(type=obj["type"], coordinates=obj["coordinates"])


def polygon_id(g):
    from shapely import set_precision
    return "custom-" + hashlib.sha1(set_precision(g, 1e-4).wkb).hexdigest()[:8]


def load_index(path):
    from shapely import STRtree
    from shapely.geometry import shape
    if not os.path.exists(path):
        return None
    feats = json.load(open(path))["features"]
    geoms = [shape(f["geometry"]) for f in feats]
    return feats, geoms, STRtree(geoms)


def create_app(settings=None, runner=None):
    if os.environ.get("LLD_OFFLINE") == "1":          # demo/test: behave like a machine without internet
        from backend.core import offline
        offline.block_network()
    import logging
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)      # job errors (log.exception) must reach the server log
    st = settings or Settings()
    idx = {"v": None, "loaded": False}

    def index():
        if not idx["loaded"]:
            idx["v"], idx["loaded"] = load_index(st.index_path), True
        return idx["v"]

    def _runner(jid, lake_id, request, progress):
        from backend.jobs.runner import run_analysis, run_sample
        if request.get("sample_of"):
            return run_sample(st, lake_id, request, progress)
        return run_analysis(st, lake_id, request, progress)

    jobs_holder = {}

    @asynccontextmanager
    async def lifespan(app):
        os.makedirs(os.path.dirname(st.jobs_db), exist_ok=True)
        jobs_holder["m"] = JobManager(st.jobs_db, runner or _runner, max_concurrent=2, start=st.start_worker)
        app.state.jobs = jobs_holder["m"]
        yield
        jobs_holder["m"].close()

    app = FastAPI(title="Metalimnion API", version="0.4.0", lifespan=lifespan,
                  description="Lake area / surface temperature / climate attribution from Landsat, NASA POWER, SWOT. "
                              "On-demand (custom) results are unverified.")
    app.state.settings = st
    app.add_middleware(GZipMiddleware, minimum_size=2000)

    def jobs():
        # TestClient without a `with` block does not run lifespan; create lazily
        if "m" not in jobs_holder:
            os.makedirs(os.path.dirname(st.jobs_db), exist_ok=True)
            jobs_holder["m"] = JobManager(st.jobs_db, runner or _runner, max_concurrent=2, start=st.start_worker)
            app.state.jobs = jobs_holder["m"]
        return jobs_holder["m"]

    def need(key):
        if not store.resolve(st, key):
            raise HTTPException(404, f"unknown lake '{key}' (use an alias such as 'burdur' or a lake id from /api/lakes)")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/lakes", summary="Summary of all computed lakes", response_model=LakesResponse)
    def lakes():
        return {"lakes": store.list_lakes(st)}

    @app.get("/api/lakes/{lake_id}", summary="Full record: series, stats, climate, swot, meta")
    def lake(lake_id: str):
        need(lake_id)
        return store.full(st, lake_id)

    @app.get("/api/lakes/{lake_id}/forecast", summary="Area forecast: backtested statistical extrapolation with 50/90 % bands")
    def forecast(lake_id: str, horizon: int = Query(2040, ge=2026, le=2060, description="last forecast year")):
        need(lake_id)
        return store.forecast(st, lake_id, horizon)

    @app.get("/api/lakes/{lake_id}/masks/{year}", summary="Yearly water mask as PNG (or JSON with bounds)")
    def mask(lake_id: str, year: int, format: str = Query("png", pattern="^(png|json)$")):
        need(lake_id)
        if format == "json":
            m = store.mask_json(st, lake_id, year)
            if not m:
                raise HTTPException(404, f"no mask for {lake_id} in {year}")
            return m
        m = store.mask_info(st, lake_id, year)
        if not m:
            raise HTTPException(404, f"no mask for {lake_id} in {year}")
        png, info = m
        return FileResponse(png, media_type="image/png",
                            headers={"X-Mask-Coordinates": json.dumps(info["coordinates"]),
                                     "X-Mask-Bounds": json.dumps(info["bounds"])})

    @app.get("/api/lakes/{lake_id}/live", summary="Live cards (cached 3 h; stale: true when a source fails)")
    def live(lake_id: str):
        need(lake_id)
        rec = store.record(st, lake_id)
        return live_cache.get_live(st, rec["meta"].get("lake_id", lake_id), rec["meta"])

    @app.get("/api/lakes/{lake_id}/snapshot.jpg", summary="Stored VIIRS true-colour picture (works offline)")
    def snapshot(lake_id: str):
        need(lake_id)
        rec = store.record(st, lake_id)
        p = live_cache.snapshot_path(st, rec["meta"].get("lake_id", lake_id))
        if not p:
            raise HTTPException(404, "no stored snapshot for this lake (run backend/scripts/prefetch.py)")
        return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/api/basemap/countries", summary="Offline basemap: Natural Earth 50m country borders (GeoJSON)")
    def countries():
        p = os.path.join(os.path.dirname(st.index_path), "countries.geojson")
        if not os.path.exists(p):
            raise HTTPException(503, "offline basemap missing: run backend/scripts/build_countries.py")
        return FileResponse(p, media_type="application/geo+json", headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/api/index", summary="Lake index (GeoJSON polygons, for the map layer)")
    def lake_index():
        if not os.path.exists(st.index_path):
            raise HTTPException(503, "lake index missing: run backend/scripts/build_lake_index.py")
        return FileResponse(st.index_path, media_type="application/geo+json")

    @app.get("/api/identify", summary="Lake at a point, from the lake index")
    def identify(lon: float = Query(..., ge=-180, le=180), lat: float = Query(..., ge=-90, le=90)):
        from shapely.geometry import Point, mapping
        ix = index()
        if ix is None:
            raise HTTPException(503, "lake index missing: run backend/scripts/build_lake_index.py")
        feats, geoms, tree = ix
        hits = [i for i in tree.query(Point(lon, lat), predicate="intersects")]
        if not hits:
            raise HTTPException(404, "no lake at this point in the lake index")
        i = sorted(hits, key=lambda j: (not feats[j]["properties"]["precomputed"], feats[j]["properties"]["polygon_area_km2"]))[0]
        p = feats[i]["properties"]
        computed = store.resolve(st, p["id"]) is not None
        latest = store.latest_area(st, p["id"]) if computed else (None, None)
        return dict(id=p["id"], alias=p["alias"], name=p["name"], polygon_area_km2=p["polygon_area_km2"],
                    lake_area_km2=latest[0], lake_area_year=latest[1], precomputed=p["precomputed"],
                    computed=computed, source=p["source"], polygon=feats[i]["geometry"])

    def job_view(j):
        return dict(job_id=j["id"], lake_id=j["lake_id"], status=j["status"], progress=j["progress"] or 0.0,
                    current_year=j["current_year"], phase=j["phase"],
                    error=("analysis failed; see the server log for details" if j["status"] == "failed" else None),
                    result_url=f"/api/lakes/{j['lake_id']}")

    def start_sample(alias):
        """Replay of a pre-computed lake as a job (progress, years, preliminary -> full), a few seconds. Always labelled."""
        src = store.resolve(st, alias)
        if not src or src[1] or alias.startswith(store.SAMPLE_PREFIX):
            raise HTTPException(404, f"no pre-computed lake '{alias}' to use as a sample")
        lake_id = store.SAMPLE_PREFIX + os.path.basename(src[0])
        job, created = jobs().submit(lake_id, dict(sample_of=src[0], name=os.path.basename(src[0])))
        return JSONResponse(dict(job_view(job), status=job["status"], attached_to_existing=not created, unverified=True,
                                 sample=True), status_code=202)

    @app.post("/api/analyze", summary="Start an on-demand analysis (or return the computed result)")
    def analyze(body: dict = Body(..., examples=[{"lake_id": "burdur"}, {"polygon": {"type": "Polygon", "coordinates": []}}])):
        lake_key, poly = body.get("lake_id"), body.get("polygon")
        if body.get("sample"):
            return start_sample(str(body["sample"]))
        if bool(lake_key) == bool(poly):
            raise HTTPException(422, "send exactly one of {lake_id} or {polygon}")
        request = {}
        if lake_key:
            if store.resolve(st, lake_key):
                rec = store.record(st, lake_key)
                if not rec["custom"] or (rec["meta"].get("analysis") or {}).get("status") == "done":
                    return dict(status="done", lake_id=rec["meta"].get("lake_id", lake_key), job_id=None,
                                unverified=rec["custom"], result=store.full(st, lake_key))
            ix = index()
            hit = None
            if ix:
                hit = next((f for f in ix[0] if f["properties"]["id"] == lake_key), None)
            if not hit:
                raise HTTPException(404, f"lake '{lake_key}' is not computed and not in the lake index")
            g, geom = parse_polygon(hit["geometry"])
            request = dict(polygon=geom, name=hit["properties"]["name"], seed=[g.representative_point().x, g.representative_point().y])
            lake_id = lake_key
        else:
            try:
                g, geom = parse_polygon(poly)
            except ValueError as e:
                raise HTTPException(422, str(e)) from e
            lake_id = polygon_id(g)
            request = dict(polygon=geom)
        a = polygon_area_km2(g)
        if a > MAX_POLYGON_KM2:
            raise HTTPException(422, f"area of {a:,.0f} km2 is larger than the {MAX_POLYGON_KM2:,.0f} km2 limit: "
                                     "please select a smaller area around the lake")
        done = store.resolve(st, lake_id)
        if done and (store.record(st, lake_id)["meta"].get("analysis") or {}).get("status") == "done":
            return dict(status="done", lake_id=lake_id, job_id=None, unverified=True, result=store.full(st, lake_id))
        job, created = jobs().submit(lake_id, request)
        return JSONResponse(dict(job_view(job), status=job["status"], attached_to_existing=not created, unverified=True,
                                 area_km2=round(a, 1)), status_code=202)

    @app.get("/api/jobs/{job_id}", summary="Job status")
    def job(job_id: str):
        j = jobs().get(job_id)
        if not j:
            raise HTTPException(404, f"unknown job '{job_id}'")
        return job_view(j)

    @app.get("/api/compare", summary="Normalised series: % area vs 1985-1990 mean, LST anomaly")
    def compare(ids: str = Query(..., description="comma-separated lake ids/aliases, max 6"),
                metric: str = Query("area_pct", pattern="^(area_pct|lst_anomaly)$")):
        keys = [k.strip() for k in ids.split(",") if k.strip()]
        if not keys or len(keys) > 6:
            raise HTTPException(422, "give 1 to 6 lake ids")
        series, missing = store.compare(st, keys, metric)
        if missing:
            raise HTTPException(404, f"unknown lake(s): {', '.join(missing)}")
        notes = ["Normalised to the mean of 1985-1990 (area: 100 % = that mean; LST: degrees C difference to that mean). Lakes without valid 1985-1990 years (reference_years in the response) use their first 3 valid years instead."]
        if metric == "lst_anomaly":
            notes.append(store.LST_SENSOR_BREAK)
        return dict(metric=metric, base_period=list(store.REF), series=series, notes=notes)

    dist = os.path.abspath(st.dist_dir if getattr(st, "dist_dir", None) else DIST)
    index_html = os.path.join(dist, "index.html")
    if os.path.exists(index_html):          # built frontend: one port for the demo
        for route in SPA_ROUTES:
            app.add_api_route("/" + route, lambda: FileResponse(index_html), include_in_schema=False)
        if os.path.isdir(os.path.join(dist, "assets")):
            app.mount("/assets", StaticFiles(directory=os.path.join(dist, "assets")), name="assets")
        for icon in ("logo-64.png", "favicon-32.png", "apple-touch-icon.png"):      # team logo + icons from frontend/public
            if os.path.exists(os.path.join(dist, icon)):
                app.add_api_route("/" + icon, lambda icon=icon: FileResponse(os.path.join(dist, icon), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}), include_in_schema=False)
        app.add_api_route("/", lambda: FileResponse(index_html), include_in_schema=False)
    return app


app = create_app()
