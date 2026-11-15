"""On-demand lake analysis (progressive). Writes data/custom/<lake_id>/{series.json, meta.json, masks/} after every
phase step so GET /api/lakes/{id} shows the partial result while the job runs. Results are always labelled unverified.

Phase 1: every 5th year 1985 -> end year (quick preliminary result). Phase 2: the remaining years.
The lake polygon is detected from 1985-1990 masks (largest water body in the selected area) like the precompute."""
import json
import os
from datetime import date, datetime, timezone

import pandas as pd

from backend.core import geo, landsat
from backend.core.stats import compute_stats
from backend.scripts.precompute import box_geojson, detect_polygon, save_mask, write_geojson

MIN_VALID = 0.8


def plan_years(start=1985, end=None, step=5):
    if end is None:
        t = date.today()
        end = t.year if t.month >= 10 else t.year - 1     # Aug-Sep composite must be complete
    first = list(range(start, end + 1, step))
    if end not in first:
        first.append(end)
    rest = [y for y in range(start, end + 1) if y not in first]
    return first, rest


def _write(out, name, obj):
    tmp = os.path.join(out, name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, default=str)
    os.replace(tmp, os.path.join(out, name))


def run_analysis(st, lake_id, request, progress, **kw):
    """Run the analysis; on any failure mark data/custom/<id>/meta.json analysis.status = "failed" and re-raise."""
    try:
        return _run_analysis(st, lake_id, request, progress, **kw)
    except Exception:
        mp = os.path.join(st.custom_dir, lake_id, "meta.json")
        try:
            if os.path.exists(mp):
                m = json.load(open(mp))
            else:
                os.makedirs(os.path.dirname(mp), exist_ok=True)
                m = dict(lake_id=lake_id, name=request.get("name"), group="custom", analysis=dict(unverified=True))
            m.setdefault("analysis", {})["status"] = "failed"
            _write(os.path.dirname(mp), "meta.json", m)
        except OSError:
            pass
        raise


def _run_analysis(st, lake_id, request, progress, catalog=None, analyze_year=None, detect=None, end_year=None):
    """request = {"polygon": GeoJSON geometry, "name": optional, "seed": optional [lon, lat]}.
    analyze_year / detect / catalog are injectable for offline tests."""
    from shapely.geometry import shape
    area_geom = shape(request["polygon"])
    bbox = tuple(area_geom.bounds)
    seed = request.get("seed")
    catalog = catalog if catalog is not None else landsat.open_catalog()
    out = os.path.join(st.custom_dir, lake_id)
    os.makedirs(os.path.join(out, "masks"), exist_ok=True)
    progress(phase="detecting lake polygon", progress=1.0)
    poly, pinfo = (detect or detect_polygon)(catalog, bbox, tuple(seed) if seed else None, 40)
    write_geojson(os.path.join(out, "masks", "lake_polygon.geojson"), poly, pinfo)
    c = poly.centroid
    epsg = geo.utm_epsg(c.x, c.y, width_deg=bbox[2] - bbox[0])
    crs = f"EPSG:{epsg}"
    res = geo.pick_resolution(pinfo["polygon_km2"])
    gj = box_geojson(poly)
    first, rest = plan_years(end=end_year)
    years = first + rest
    meta = dict(lake_id=lake_id, alias=None, name=request.get("name") or f"Custom lake {lake_id[-8:]}", country=None,
                group="custom", bbox=list(bbox), seed=[round(c.x, 4), round(c.y, 4)], resolution_m=res, utm_epsg=epsg,
                years=[years[0], max(years)], lake_polygon=pinfo,
                analysis=dict(status="running", unverified=True, years_done=0, years_total=len(years), phase=None,
                              note="On-demand analysis, not validated against literature or a reference; treat as preliminary."))
    rows, grid = [], None
    analyze_year = analyze_year or (lambda y: landsat.year_with_retries(catalog, poly, gj, y, 0.0, 40, crs=crs, pixel_m=res,
                                                                        return_masks=True))
    for i, y in enumerate(years):
        phase = "preliminary (every 5th year)" if y in first else "filling gaps"
        progress(phase=phase, current_year=int(y), progress=round(5 + 90 * i / len(years), 1))
        row = analyze_year(y)
        w, v, tf = row.pop("water", None), row.pop("valid", None), row.pop("transform", None)
        if w is not None:
            save_mask(os.path.join(out, "masks", f"{y}.png"), w, v)
            grid = dict(crs=crs, affine=list(tf)[:6], shape=list(w.shape), resolution_m=res)
        rows.append({k: (None if isinstance(x, float) and x != x else x) for k, x in row.items()})
        rows.sort(key=lambda r: r["year"])
        if grid:
            _write(os.path.join(out, "masks"), "grid.json", grid)
        stats = compute_stats(pd.DataFrame(rows), MIN_VALID) if len(rows) >= 10 or i == len(years) - 1 else {}
        from backend.core import stats as quality
        _write(out, "series.json", dict(lake=meta["name"], bbox=list(bbox), window="Aug 1 - Sep 30", min_valid=MIN_VALID,
                                         resolution_m=res, crs=crs, series=rows, stats=stats or None,
                                         reliability=quality.assess(rows, MIN_VALID), unverified=True))
        meta["analysis"].update(years_done=i + 1, phase=phase, status="running" if i + 1 < len(years) else "done")
        _write(out, "meta.json", dict(meta, generated=datetime.now(timezone.utc).isoformat(timespec="seconds")))


def run_sample(st, lake_id, request, progress):
    """Replay a pre-computed lake as an on-demand job: copies masks, then writes series.json/meta.json progressively
    (every 5th year first = preliminary, then the rest) with a short pause per year. No network, no Landsat.
    The record is flagged analysis.sample=true and unverified so the UI says "pre-computed sample"."""
    import shutil
    import time
    src = request["sample_of"]
    ser, meta = json.load(open(os.path.join(src, "series.json"))), json.load(open(os.path.join(src, "meta.json")))
    out = os.path.join(st.custom_dir, lake_id)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    shutil.copytree(os.path.join(src, "masks"), os.path.join(out, "masks"))
    for n in ("climate.json", "swot.json", "basin.geojson"):
        if os.path.exists(os.path.join(src, n)):
            shutil.copy(os.path.join(src, n), out)
    rows_all = ser["series"]
    yrs = [r["year"] for r in rows_all]
    first, rest = plan_years(min(yrs), max(yrs))
    order = [y for y in first if y in yrs] + [y for y in rest if y in yrs]
    note = ("PRE-COMPUTED SAMPLE: this is the stored result for " + str(meta.get("name")) + ", replayed in a few seconds "
            "to show the on-demand job flow. It was not computed just now.")
    m = dict(meta, lake_id=lake_id, alias=None, name=f"{meta.get('name')} (pre-computed sample)", group="custom",
             analysis=dict(status="running", unverified=True, sample=True, sample_of=meta.get("lake_id"), years_done=0,
                           years_total=len(order), phase=None, note=note))
    rows = []
    for i, y in enumerate(order):
        phase = "preliminary (every 5th year)" if y in first else "filling gaps"
        progress(phase=phase, current_year=int(y), progress=round(5 + 90 * i / len(order), 1))
        rows.append(next(r for r in rows_all if r["year"] == y))
        rows.sort(key=lambda r: r["year"])
        last = i + 1 == len(order)
        part = dict(ser, series=list(rows), unverified=True,
                    stats=ser.get("stats") if (last or len(rows) >= 10) else None,
                    reliability=ser.get("reliability") if last else None)
        _write(out, "series.json", part)
        m["analysis"].update(years_done=i + 1, phase=phase, status="done" if last else "running")
        _write(out, "meta.json", dict(m, generated=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        if st.sample_delay_s:
            time.sleep(st.sample_delay_s)
