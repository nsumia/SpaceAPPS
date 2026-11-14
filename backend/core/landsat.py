"""
Landsat C2 L2 water area + lake surface temperature (moved from Stage 1 burdur_area.py; behaviour preserved except
where noted in VALIDATION.md: metric 150 m erosion, qa_radsat masking, adaptive resolution/UTM).

Per year, Aug-Sep Landsat 5/8/9 scenes (4 and 7 excluded), QA_PIXEL cloud mask, MNDWI=(green-swir16)/(green+swir16)
median composite, MNDWI>thresh -> water, area = px * res^2. LST: median ST of water pixels at least 150 m
(Euclidean, metres) from non-water, in deg C.
Verified assets: thermal `lwir` (L5) / `lwir11` (L8/9), NIR `nir08`; odc-stac returns raw DN (scaled here).
qa_radsat bits (read from the STAC item `classification:bitfields`, 2026-11-14): L5 green=1 swir16(band5)=4
thermal(band6)=5 dropped=9; L8/9 green=2 swir16(band6)=5, no thermal bit is listed.
"""
import sys
import time
import warnings

import numpy as np

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
PLATFORMS = ["landsat-5", "landsat-8", "landsat-9"]      # landsat-4/7 explicitly excluded
EXCLUDED_PLATFORMS = {"landsat-4", "landsat-7"}
THERMAL_ASSET = {"landsat-5": "lwir", "landsat-8": "lwir11", "landsat-9": "lwir11"}
SCALE, OFFSET = 0.0000275, -0.2           # surface reflectance
ST_SCALE, ST_OFFSET = 0.00341802, 149.0   # surface temperature (Kelvin)
CLOUD_BITS = (1, 3, 4)                    # dilated cloud, cloud, cloud shadow
# qa_radsat bit indices by thermal family: bits that make green/swir16 (water) or thermal unusable
RADSAT_BITS = {"lwir": dict(water=(1, 4, 9), thermal=(5, 9)), "lwir11": dict(water=(2, 5), thermal=())}
PIXEL_M = 30
LST_EROSION_M = 150
LST_MIN_PX = 50
DEFAULT_CRS = "EPSG:32636"
RETRIES = 2
HTTP_TIMEOUT = "60"
SLAB_ELEMS = 30_000_000                   # max time*rows*cols per processing slab (memory bound)


def _bits(a, bits):
    a = np.asarray(a).astype("uint16")
    out = np.zeros(a.shape, bool)
    for b in bits:
        out |= ((a >> b) & 1).astype(bool)
    return out


def composites(green, swir, qa, st, sat_water=None, sat_thermal=None):
    """Median composites over time. Returns (mndwi_median, st_median_celsius or None). Inputs raw DN (time,y,x)."""
    green = np.asarray(green, dtype="float32"); swir = np.asarray(swir, dtype="float32")
    bad = _bits(qa, CLOUD_BITS)
    if sat_water is not None:
        bad |= np.asarray(sat_water, bool)
    good = ~bad & (green != 0) & (swir != 0)
    g = green * SCALE + OFFSET
    s = swir * SCALE + OFFSET
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mndwi = np.where(good, (g - s) / (g + s), np.nan)
        comp = np.nanmedian(mndwi, axis=0)
        st_comp = None
        if st is not None:
            st = np.asarray(st, dtype="float32")
            ok = good & (st > 0)
            if sat_thermal is not None:
                ok &= ~np.asarray(sat_thermal, bool)
            st_c = np.where(ok, st * ST_SCALE + ST_OFFSET, np.nan)
            st_comp = np.nanmedian(st_c, axis=0) - 273.15
    return comp, st_comp


def finish(comp, st_comp, thresh=0.0, inside=None, pixel_m=PIXEL_M, erosion_m=LST_EROSION_M, min_px=LST_MIN_PX):
    """From composites to water mask, area and LST. Returns dict incl. 'water' and 'valid' bool arrays."""
    from scipy.ndimage import distance_transform_edt
    if inside is None:
        inside = np.ones(comp.shape, bool)
    valid = inside & np.isfinite(comp)
    water = valid & (comp > thresh)
    lst, n_core = np.nan, 0
    if st_comp is not None:
        # metric erosion: keep water pixels whose centre is >= erosion_m from the nearest non-water pixel
        # (zero padding, so the array edge counts as non-water, like binary_erosion's border_value=0)
        dist = distance_transform_edt(np.pad(water, 1))[1:-1, 1:-1] * pixel_m
        core = (dist > erosion_m if erosion_m > 0 else water) & water & np.isfinite(st_comp)
        n_core = int(core.sum())
        if n_core >= min_px:
            lst = float(np.median(st_comp[core]))
    return dict(area_km2=float(water.sum() * pixel_m ** 2 / 1e6),
                valid_frac=round(float(valid.sum() / max(inside.sum(), 1)), 3),
                lst_c=round(lst, 2) if lst == lst else np.nan, lst_px=n_core, water=water, valid=valid)


def analyze_arrays(green, swir, qa, st, thresh=0.0, inside=None, pixel_m=PIXEL_M, erosion_m=LST_EROSION_M,
                   min_px=LST_MIN_PX, sat_water=None, sat_thermal=None, return_masks=False):
    """Pure numpy core (raw DN stacks (time,y,x); st may be None). Returns dict(area_km2, valid_frac, lst_c, lst_px)."""
    comp, st_comp = composites(green, swir, qa, st, sat_water, sat_thermal)
    r = finish(comp, st_comp, thresh, inside, pixel_m, erosion_m, min_px)
    if not return_masks:
        r.pop("water"); r.pop("valid")
    return r


def load_geometry(path, default_bbox=None):
    import json
    from shapely.geometry import box, mapping, shape
    if path is None:
        geom = box(*default_bbox)
    else:
        with open(path) as f:
            gj = json.load(f)
        feat = gj["features"][0] if gj.get("type") == "FeatureCollection" else gj
        geom = shape(feat.get("geometry", feat))
    return geom, mapping(geom)


def open_catalog():
    import dask
    import odc.stac
    import planetary_computer
    import pystac_client
    dask.config.set(scheduler="threads", num_workers=4)       # limited concurrency
    odc.stac.configure_rio(cloud_defaults=True, GDAL_HTTP_TIMEOUT=HTTP_TIMEOUT,
                           GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2")
    return pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace, timeout=60)


EXCLUDE_ITEMS = set()      # scene ids with unreadable assets (set per lake from LAKES[..]["exclude_items"])


def search_items(catalog, geom_json, start, end, max_cloud=40):
    # signed URLs are used lazily for minutes: drop cached SAS tokens that expire within 20 min so they cannot die mid-load
    try:
        from planetary_computer import sas
        for k in [k for k, v in sas.TOKEN_CACHE.items() if v.ttl() < 1200]:
            del sas.TOKEN_CACHE[k]
    except Exception:  # noqa: BLE001
        pass
    items = list(catalog.search(
        collections=["landsat-c2-l2"], intersects=geom_json, datetime=f"{start}/{end}",
        query={"platform": {"in": PLATFORMS}, "eo:cloud_cover": {"lt": max_cloud}}).items())
    # belt and braces: never trust the server filter alone
    return [i for i in items if i.properties.get("platform") in THERMAL_ASSET and i.id not in EXCLUDE_ITEMS]


def _empty(**kw):
    return dict(area_km2=np.nan, n_scenes=0, valid_frac=0.0, lst_c=np.nan, lst_px=0, latest_scene=None, **kw)


def window_area(catalog, geom, geom_json, start, end, thresh=0.0, max_cloud=40, crs=DEFAULT_CRS,
                pixel_m=PIXEL_M, return_masks=False):
    """Area + LST in the lon/lat polygon `geom` for the date window. With return_masks the row also carries
    'water'/'valid' arrays and 'transform' (affine, `crs`). Rows are processed in slabs to bound memory."""
    import odc.stac
    import planetary_computer
    from rasterio.features import geometry_mask
    from shapely.ops import transform as shp_transform
    from pyproj import Transformer

    items = search_items(catalog, geom_json, start, end, max_cloud)
    if not items:
        return _empty()
    lazy = []
    for thermal in ("lwir", "lwir11"):
        fam = [i for i in items if THERMAL_ASSET[i.properties["platform"]] == thermal]
        if fam:
            d = odc.stac.load(fam, bands=["green", "swir16", "qa_pixel", "qa_radsat", thermal], bbox=geom.bounds,
                              crs=crs, resolution=pixel_m, groupby="solar_day", chunks={"x": 1024, "y": 1024},
                              patch_url=planetary_computer.sign)
            lazy.append((thermal, d.rename({thermal: "st"})))
    n_t = sum(d.sizes["time"] for _, d in lazy)
    ny, nx = lazy[0][1].sizes["y"], lazy[0][1].sizes["x"]
    geobox = lazy[0][1].odc.geobox
    to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    inside = geometry_mask([shp_transform(to_utm, geom)], out_shape=(ny, nx), transform=geobox.affine, invert=True)
    rows_per = max(int(SLAB_ELEMS // max(n_t * nx, 1)), 64)
    comp = np.full((ny, nx), np.nan, "float32"); st_comp = np.full((ny, nx), np.nan, "float32")
    for y0 in range(0, ny, rows_per):
        sl = slice(y0, min(y0 + rows_per, ny))
        parts = {k: [] for k in ("green", "swir", "qa", "st", "sw", "stt")}
        for thermal, d in lazy:
            s = d.isel(y=sl).compute()
            bits = RADSAT_BITS[thermal]
            rs = s["qa_radsat"].values
            parts["green"].append(s["green"].values); parts["swir"].append(s["swir16"].values)
            parts["qa"].append(s["qa_pixel"].values); parts["st"].append(s["st"].values)
            parts["sw"].append(_bits(rs, bits["water"]))
            parts["stt"].append(_bits(rs, bits["thermal"]) if bits["thermal"] else np.zeros(rs.shape, bool))
        cat = {k: np.concatenate(v, axis=0) for k, v in parts.items()}
        c, t = composites(cat["green"], cat["swir"], cat["qa"], cat["st"], cat["sw"], cat["stt"])
        comp[sl], st_comp[sl] = c, t
    row = finish(comp, st_comp, thresh, inside, pixel_m)
    row["n_scenes"] = int(n_t)
    row["n_items"] = len(items)
    row["latest_scene"] = max(str(i.datetime.date()) for i in items if i.datetime)
    if return_masks:
        row["transform"] = geobox.affine
    else:
        row.pop("water"); row.pop("valid")
    return row


def year_with_retries(catalog, geom, geom_json, year, thresh, max_cloud, window=("08-01", "09-30"), **kw):
    err = None
    for attempt in range(RETRIES + 1):
        try:
            row = window_area(catalog, geom, geom_json, f"{year}-{window[0]}", f"{year}-{window[1]}", thresh, max_cloud, **kw)
            return dict(year=year, error=None, **row)
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:300]
            print(f"{year}: attempt {attempt + 1} failed: {err}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return dict(year=year, **_empty(), error=err)
