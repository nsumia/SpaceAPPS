"""
Precompute a lake record under data/lakes/<alias>/ (series.json, masks/, meta.json, basin.geojson).

    .venv/bin/python -m backend.scripts.precompute --lake burdur
    .venv/bin/python -m backend.scripts.precompute --lake van --start 2018 --end 2020 --out-dir /tmp/van_test

Steps: (1) lake polygon from the 1985-1990 MNDWI masks (largest component around the seed, +1 km), cached in
masks/lake_polygon.geojson; (2) per-year Aug-Sep analysis inside that polygon at the adaptive resolution in the
auto UTM zone; (3) Mann-Kendall/Sen stats; (4) HydroBASINS basin (buffer fallback flagged); (5) meta.json.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backend.core import geo, landsat
from backend.core.basin import basin_for_lake
from backend.core.lakes import LAKES, ROOT, lake_dir, lake_id
from backend.core.stats import compute_stats, sen_line

DETECT_YEARS = range(1985, 1991)


def git_version():
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "backend"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except Exception:  # noqa: BLE001
        return "unknown"


def detect_polygon(catalog, bbox, seed, max_cloud, log=print):
    """Lake polygon (lon/lat) from pooled 1985-1990 masks. Returns (polygon_ll, info)."""
    from shapely.geometry import Point, box
    lon0, lat0, lon1, lat1 = bbox
    epsg = geo.utm_epsg(seed[0], seed[1], width_deg=lon1 - lon0)
    res = geo.pick_resolution(geo.bbox_area_km2(bbox))
    crs = f"EPSG:{epsg}"
    bx = box(*bbox)
    water, valid, tf = None, None, None
    used = []
    for y in DETECT_YEARS:
        row = landsat.year_with_retries(catalog, bx, box_geojson(bx), y, 0.0, max_cloud,
                                        crs=crs, pixel_m=res, return_masks=True)
        if row.get("error") or row["n_scenes"] == 0 or row["valid_frac"] < 0.5:
            log(f"  detect {y}: skipped (scenes={row['n_scenes']} valid={row['valid_frac']} err={row['error']})")
            continue
        w, v = row["water"], row["valid"]
        water = w.astype("int32") if water is None else water + w
        valid = v.astype("int32") if valid is None else valid + v
        tf = row["transform"]; used.append(y)
        log(f"  detect {y}: box water {row['area_km2']:.1f} km2 scenes={row['n_scenes']} valid={row['valid_frac']}")
    if not used:
        raise RuntimeError("no usable 1985-1990 year for lake polygon detection")
    mask = (valid > 0) & (water / np.maximum(valid, 1) >= 0.5)
    x, y = geo.to_utm(Point(*seed), epsg).coords[0]
    col, rowi = ~tf * (x, y)
    comp = geo.select_lake_component(mask, (int(rowi), int(col)))
    utm_poly = geo.component_to_polygon_utm(comp, tf, buffer_m=1000.0, simplify_m=res)
    poly = geo.to_lonlat(utm_poly, epsg)
    info = dict(method="largest connected MNDWI>0 component (pixel water in >=50% of valid years) containing the seed, +1 km buffer",
                years_used=used, detect_resolution_m=res, detect_crs=crs,
                component_km2=round(float(comp.sum() * res ** 2 / 1e6), 1),
                box_water_km2=round(float(mask.sum() * res ** 2 / 1e6), 1),
                polygon_km2=round(utm_poly.area / 1e6, 1))
    return poly, info


def box_geojson(g):
    from shapely.geometry import mapping
    return mapping(g)


def write_geojson(path, geom, props=None):
    from shapely.geometry import mapping
    with open(path, "w") as f:
        json.dump(dict(type="Feature", properties=props or {}, geometry=mapping(geom)), f)


def save_mask(path, water, valid):
    from PIL import Image
    img = np.zeros(water.shape, "uint8")      # 0 no data, 90 land, 255 water
    img[valid] = 90
    img[water] = 255
    Image.fromarray(img).save(path, optimize=True)


def make_plot(df, stats, path, name, min_valid, ref=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ok = (df.valid_frac >= min_valid) & df.area_km2.notna()
    fig, ax = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    ax[0].plot(df.year[ok], df.area_km2[ok], "o-", color="#1f6fb4", label="Landsat Aug-Sep area")
    ax[0].plot(df.year[~ok], df.area_km2[~ok], "x", color="#999", label="low coverage / NaN")
    s = stats.get("area")
    if s:
        x = df.year[ok].values
        ax[0].plot(x, sen_line(s, x), "--", color="#c0392b", label=f"Sen {s['sen_slope_per_decade']:+.1f} km2/decade (p={s['p']:.2g})")
    if ref:
        ax[0].axhline(ref[1], color="#999", ls=":"); ax[0].text(df.year.min(), ref[1] + 1, ref[0], fontsize=8)
    ax[0].set_ylabel("Area (km2)"); ax[0].set_title(f"Lake {name}"); ax[0].legend(frameon=False); ax[0].grid(alpha=.3)
    t = df[ok & df.lst_c.notna()]
    ax[1].plot(t.year, t.lst_c, "o-", color="#d35400", label="Late-summer LST (L5 to 2012, L8/9 from 2013)")
    ax[1].axvline(2012.5, color="#555", ls=":")
    ax[1].set_ylabel("deg C"); ax[1].set_xlabel("Year"); ax[1].legend(frameon=False); ax[1].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(path, dpi=150)


def run(alias, start=1985, end=2025, out_dir=None, thresh=0.0, max_cloud=40, min_valid=0.8, rebuild_polygon=False,
        no_basin=False, plot=None, no_masks=False, legacy_box_mask=False, log=print):
    cfg = LAKES[alias]
    if legacy_box_mask and not out_dir:
        raise SystemExit("--legacy-box-mask needs --out-dir (it must not overwrite the lake record)")
    out = out_dir or lake_dir(alias)
    os.makedirs(os.path.join(out, "masks"), exist_ok=True)
    catalog = landsat.open_catalog()
    seed, bbox = cfg["seed"], cfg["bbox"]
    poly_path = os.path.join(out, "masks", "lake_polygon.geojson")
    if legacy_box_mask:      # verification mode: Stage 1 masking (whole box, 30 m), no polygon detection
        from shapely.geometry import box as _box
        poly = _box(*bbox)
        pinfo = dict(method="legacy: whole bounding box (Stage 1 masking)", polygon_km2=round(geo.bbox_area_km2(bbox), 1),
                     component_km2=round(geo.bbox_area_km2(bbox), 1))
    elif os.path.exists(poly_path) and not rebuild_polygon:
        from shapely.geometry import shape
        with open(poly_path) as f:
            feat = json.load(f)
        poly, pinfo = shape(feat["geometry"]), feat["properties"]
        log(f"lake polygon: cached ({pinfo.get('polygon_km2')} km2)")
    else:
        log("lake polygon: detecting from 1985-1990 masks")
        poly, pinfo = detect_polygon(catalog, bbox, seed, max_cloud, log)
        write_geojson(poly_path, poly, pinfo)
        log(f"lake polygon: {pinfo}")
    epsg = geo.utm_epsg(seed[0], seed[1], width_deg=bbox[2] - bbox[0])
    res = 30 if legacy_box_mask else geo.pick_resolution(pinfo["polygon_km2"])      # adaptive: by analysis-polygon area (lake + 1 km), see VALIDATION.md
    crs = f"EPSG:{epsg}"
    gj = box_geojson(poly)
    rows, scenes, grid = [], 0, None
    for y in range(start, end + 1):
        row = landsat.year_with_retries(catalog, poly, gj, y, thresh, max_cloud, crs=crs, pixel_m=res, return_masks=True)
        w, v, tf = row.pop("water", None), row.pop("valid", None), row.pop("transform", None)
        if w is not None and not no_masks:
            save_mask(os.path.join(out, "masks", f"{y}.png"), w, v)
            grid = dict(crs=crs, affine=list(tf)[:6], shape=list(w.shape), resolution_m=res)
        scenes += int(row["n_scenes"])
        log(f"{y}: area={row['area_km2']:.1f} km2 LST={row['lst_c']:.2f} C scenes={row['n_scenes']} "
            f"valid={row['valid_frac']} lst_px={row['lst_px']} err={row['error']}")
        rows.append(row)
    df = pd.DataFrame(rows)
    stats = compute_stats(df, min_valid)
    log(json.dumps(stats, indent=1))
    clean = [{k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()} for r in df.to_dict("records")]
    with open(os.path.join(out, "series.json"), "w") as f:
        json.dump(dict(lake=cfg["name"], bbox=list(bbox), window="Aug 1 - Sep 30", platforms=landsat.PLATFORMS,
                       thresh=thresh, min_valid=min_valid, resolution_m=res, crs=crs, series=clean, stats=stats), f, indent=1)
    if grid:
        with open(os.path.join(out, "masks", "grid.json"), "w") as f:
            json.dump(grid, f)
    basin = None
    if not no_basin:
        bpoly, binfo = basin_for_lake(poly, pinfo["component_km2"])
        write_geojson(os.path.join(out, "basin.geojson"), bpoly, binfo)
        c = geo.to_utm(bpoly, epsg)
        basin = dict(binfo, area_km2=round(c.area / 1e6, 1))
        log(f"basin: {basin}")
    meta = dict(lake_id=lake_id(alias), alias=alias, name=cfg["name"], country=cfg["country"],
                generated=datetime.now(timezone.utc).isoformat(timespec="seconds"), code_version=git_version(),
                resolution_m=res, thermal_erosion_m=landsat.LST_EROSION_M, utm_epsg=epsg, bbox=list(bbox), seed=list(seed),
                years=[int(start), int(end)], scene_counts=dict(total=scenes, per_year={int(r["year"]): int(r["n_scenes"]) for r in rows}),
                lake_polygon=pinfo, basin=basin, min_lst_px=int(df.lst_px[df.lst_px > 0].min()) if (df.lst_px > 0).any() else None,
                masks_encoding="PNG uint8: 0 no data, 90 land, 255 water; grid.json has crs/affine/shape")
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1, default=str)
    if plot:
        make_plot(df, stats, plot, cfg["name"], min_valid, ref=("Sabuncu 1986: 206", 206) if alias == "burdur" else None)
    return df, stats, meta


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--lake", required=True, choices=sorted(LAKES))
    p.add_argument("--start", type=int, default=1985)
    p.add_argument("--end", type=int, default=2025)
    p.add_argument("--out-dir", default=None, help="default data/lakes/<alias>")
    p.add_argument("--thresh", type=float, default=0.0)
    p.add_argument("--max-cloud", type=float, default=40)
    p.add_argument("--min-valid", type=float, default=0.8)
    p.add_argument("--rebuild-polygon", action="store_true")
    p.add_argument("--no-basin", action="store_true")
    p.add_argument("--no-masks", action="store_true")
    p.add_argument("--legacy-box-mask", action="store_true", help="verification: whole-box mask at 30 m like Stage 1 (needs --out-dir)")
    p.add_argument("--plot", default=None)
    a = p.parse_args(argv)
    run(a.lake, a.start, a.end, a.out_dir, a.thresh, a.max_cloud, a.min_valid, a.rebuild_polygon, a.no_basin,
        a.plot, a.no_masks, a.legacy_box_mask)


if __name__ == "__main__":
    main()
