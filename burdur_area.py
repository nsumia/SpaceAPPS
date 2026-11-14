"""
Lake Loss Detective - Stage 1 working module (fixed copy of legacy/burdur_area.py; legacy/ is untouched).

Usage:
    .venv/bin/python burdur_area.py --start 2020 --end 2020
    .venv/bin/python burdur_area.py --start 1985 --end 2025 --out data/lakes/burdur/series.json

Method: per year, Aug-Sep Landsat 5/8/9 C2 L2 scenes (Landsat 4 and 7 are excluded on purpose), QA_PIXEL
cloud mask, MNDWI=(green-swir16)/(green+swir16) median composite, MNDWI>thresh -> water, area = px * 900 m2.
Lake surface temperature: median ST of water pixels eroded by 150 m, in deg C.

Verified against real STAC items (tools/verify_assets.py): thermal asset is `lwir` (L5) / `lwir11` (L8/9),
NIR is `nir08` (not used here), scale/offset confirmed. odc-stac returns raw DN, so scaling is done here.
"""
import argparse
import json
import sys
import time

import numpy as np
import pandas as pd

# (lon_min, lat_min, lon_max, lat_max). Excludes Yarisli Lake (~37.56N 29.96E). East edge 30.45: in 1986 the lake reaches 30.389E (diagnosed; the first box ended at 30.30 and clipped it).
DEFAULT_BBOX = (29.95, 37.60, 30.45, 37.90)
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
PLATFORMS = ["landsat-5", "landsat-8", "landsat-9"]      # landsat-4/7 explicitly excluded
EXCLUDED_PLATFORMS = {"landsat-4", "landsat-7"}
THERMAL_ASSET = {"landsat-5": "lwir", "landsat-8": "lwir11", "landsat-9": "lwir11"}
SCALE, OFFSET = 0.0000275, -0.2           # surface reflectance
ST_SCALE, ST_OFFSET = 0.00341802, 149.0   # surface temperature (Kelvin)
CLOUD_BITS = (1, 3, 4)                    # dilated cloud, cloud, cloud shadow
PIXEL_M = 30
LST_EROSION_M = 150
LST_MIN_PX = 50
CRS = "EPSG:32636"
RETRIES = 2
HTTP_TIMEOUT = "60"


def analyze_arrays(green, swir, qa, st, thresh=0.0, inside=None, pixel_m=PIXEL_M,
                   erosion_m=LST_EROSION_M, min_px=LST_MIN_PX):
    """Pure numpy core. Inputs are raw DN stacks of shape (time, y, x) (st may be None).
    Returns dict(area_km2, valid_frac, lst_c, lst_px)."""
    from scipy.ndimage import binary_erosion
    green = np.asarray(green, dtype="float32"); swir = np.asarray(swir, dtype="float32")
    qa = np.asarray(qa).astype("uint16")
    bad = np.zeros(qa.shape, bool)
    for b in CLOUD_BITS:
        bad |= ((qa >> b) & 1).astype(bool)
    good = ~bad & (green != 0) & (swir != 0)
    g = green * SCALE + OFFSET
    s = swir * SCALE + OFFSET
    with np.errstate(invalid="ignore", divide="ignore"):
        mndwi = np.where(good, (g - s) / (g + s), np.nan)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            comp = np.nanmedian(mndwi, axis=0)
    if inside is None:
        inside = np.ones(comp.shape, bool)
    valid = inside & np.isfinite(comp)
    water = valid & (comp > thresh)
    lst, n_core = np.nan, 0
    if st is not None:
        st = np.asarray(st, dtype="float32")
        st_c = np.where(good & (st > 0), st * ST_SCALE + ST_OFFSET, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            st_comp = np.nanmedian(st_c, axis=0) - 273.15
        it = max(int(round(erosion_m / pixel_m)), 0)
        core = (binary_erosion(water, iterations=it) if it else water) & np.isfinite(st_comp)
        n_core = int(core.sum())
        if n_core >= min_px:
            lst = float(np.median(st_comp[core]))
    return dict(area_km2=float(water.sum() * pixel_m ** 2 / 1e6),
                valid_frac=round(float(valid.sum() / max(inside.sum(), 1)), 3),
                lst_c=round(lst, 2) if lst == lst else np.nan, lst_px=n_core)


def load_geometry(path):
    from shapely.geometry import box, shape, mapping
    if path is None:
        geom = box(*DEFAULT_BBOX)
    else:
        with open(path) as f:
            gj = json.load(f)
        feat = gj["features"][0] if gj.get("type") == "FeatureCollection" else gj
        geom = shape(feat.get("geometry", feat))
    return geom, mapping(geom)


def window_area(catalog, geom, geom_json, start, end, thresh=0.0, max_cloud=40):
    import odc.stac
    import planetary_computer
    import xarray as xr
    from rasterio.features import geometry_mask
    from shapely.ops import transform as shp_transform
    from pyproj import Transformer

    items = list(catalog.search(
        collections=["landsat-c2-l2"], intersects=geom_json, datetime=f"{start}/{end}",
        query={"platform": {"in": PLATFORMS}, "eo:cloud_cover": {"lt": max_cloud}}).items())
    # belt and braces: never trust the server filter alone
    items = [i for i in items if i.properties.get("platform") in THERMAL_ASSET]
    if not items:
        return dict(area_km2=np.nan, n_scenes=0, valid_frac=0.0, lst_c=np.nan, lst_px=0)
    parts = []
    for thermal in ("lwir", "lwir11"):
        fam = [i for i in items if THERMAL_ASSET[i.properties["platform"]] == thermal]
        if not fam:
            continue
        d = odc.stac.load(fam, bands=["green", "swir16", "qa_pixel", thermal], bbox=geom.bounds, crs=CRS,
                          resolution=PIXEL_M, groupby="solar_day", chunks={"x": 2048, "y": 2048},
                          patch_url=planetary_computer.sign)
        parts.append(d.rename({thermal: "st"}))
    ds = parts[0] if len(parts) == 1 else xr.concat(parts, dim="time")
    ds = ds.compute()
    to_utm = Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform
    inside = geometry_mask([shp_transform(to_utm, geom)], out_shape=ds["green"].shape[1:],
                           transform=ds.odc.geobox.affine, invert=True)
    row = analyze_arrays(ds["green"].values, ds["swir16"].values, ds["qa_pixel"].values, ds["st"].values,
                         thresh=thresh, inside=inside)
    row["n_scenes"] = int(ds.sizes["time"])
    row["n_items"] = len(items)
    return row


def year_with_retries(catalog, geom, geom_json, year, thresh, max_cloud):
    err = None
    for attempt in range(RETRIES + 1):
        try:
            row = window_area(catalog, geom, geom_json, f"{year}-08-01", f"{year}-09-30", thresh, max_cloud)
            return dict(year=year, error=None, **row)
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:300]
            print(f"{year}: attempt {attempt + 1} failed: {err}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return dict(year=year, area_km2=np.nan, n_scenes=0, valid_frac=0.0, lst_c=np.nan, lst_px=0, error=err)


def trend(values, years):
    import pymannkendall as mk
    v = np.asarray(values, float)
    if len(v) < 10:
        return None
    r = mk.hamed_rao_modification_test(v)
    return dict(n=int(len(v)), trend=r.trend, p=float(r.p), sen_slope_per_year=float(r.slope),
                sen_slope_per_decade=float(r.slope * 10), intercept=float(r.intercept),
                first_year=int(years[0]), last_year=int(years[-1]))


def compute_stats(df, min_valid=0.8):
    d = df[(df.valid_frac >= min_valid) & df.area_km2.notna()]
    out = {"area": trend(d.area_km2.values, d.year.values)}
    t = d[d.lst_c.notna()]
    out["lst_all"] = trend(t.lst_c.values, t.year.values)
    # L5 -> L8 break (L8 launched 2013; no L5 data after 2011/12): trend before / after separately
    for name, sub in (("lst_1985_2012", t[t.year <= 2012]), ("lst_2013_2025", t[t.year >= 2013])):
        out[name] = trend(sub.lst_c.values, sub.year.values)
    return out


def plot(df, stats, path, min_valid=0.8):
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
        ax[0].plot(x, s["intercept"] + s["sen_slope_per_year"] * (x - x[0]), "--", color="#c0392b",
                   label=f"Sen {s['sen_slope_per_decade']:+.1f} km2/decade (p={s['p']:.2g})")
    ax[0].axhline(206, color="#999", ls=":"); ax[0].text(1985, 207, "Sabuncu 1986: 206", fontsize=8)
    ax[0].set_ylabel("Area (km2)"); ax[0].set_title("Lake Burdur"); ax[0].legend(frameon=False); ax[0].grid(alpha=.3)
    t = df[ok & df.lst_c.notna()]
    ax[1].plot(t.year, t.lst_c, "o-", color="#d35400", label="Late-summer LST (L5 to 2012, L8/9 from 2013)")
    ax[1].axvline(2012.5, color="#555", ls=":")
    ax[1].set_ylabel("deg C"); ax[1].set_xlabel("Year"); ax[1].legend(frameon=False); ax[1].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(path, dpi=150)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--geojson", default=None)
    p.add_argument("--name", default="Burdur")
    p.add_argument("--start", type=int, default=1985)
    p.add_argument("--end", type=int, default=2025)
    p.add_argument("--thresh", type=float, default=0.0)
    p.add_argument("--max-cloud", type=float, default=40)
    p.add_argument("--min-valid", type=float, default=0.8)
    p.add_argument("--out", default=None, help="series.json path")
    p.add_argument("--plot", default=None)
    a = p.parse_args()

    import dask
    import odc.stac
    import pystac_client
    import planetary_computer
    dask.config.set(scheduler="threads", num_workers=4)       # limited concurrency
    odc.stac.configure_rio(cloud_defaults=True, GDAL_HTTP_TIMEOUT=HTTP_TIMEOUT,
                           GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2")
    catalog = pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace, timeout=60)
    geom, geom_json = load_geometry(a.geojson)
    rows = []
    for y in range(a.start, a.end + 1):
        row = year_with_retries(catalog, geom, geom_json, y, a.thresh, a.max_cloud)
        print(f"{y}: area={row['area_km2']:.1f} km2 LST={row['lst_c']:.2f} C scenes={row['n_scenes']} "
              f"valid={row['valid_frac']} err={row['error']}", flush=True)
        rows.append(row)
    df = pd.DataFrame(rows)
    stats = compute_stats(df, a.min_valid)
    print(json.dumps(stats, indent=1))
    if a.out:
        import os
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        clean = [{k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()}
                 for r in df.to_dict("records")]
        with open(a.out, "w") as f:
            json.dump(dict(lake=a.name, bbox=list(DEFAULT_BBOX if a.geojson is None else geom.bounds),
                           window="Aug 1 - Sep 30", platforms=PLATFORMS, thresh=a.thresh,
                           min_valid=a.min_valid, series=clean, stats=stats), f, indent=1)
    if a.plot:
        plot(df, stats, a.plot, a.min_valid)


if __name__ == "__main__":
    main()
