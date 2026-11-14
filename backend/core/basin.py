"""Basin polygon from HydroBASINS (levels 6-7), with a flagged buffer fallback."""
import os
import urllib.request

import numpy as np

HYBAS_URL = "https://data.hydrosheds.org/file/hydrobasins/standard/hybas_{reg}_lev01-12_v1c.zip"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "hydrobasins")
MIN_OVERLAP = 0.10          # a basin counts if it holds >= 10 % of the lake polygon area
BUFFER_FALLBACK_KM = 25.0


def zip_path(region="eu"):
    return os.path.abspath(os.path.join(RAW_DIR, f"hybas_{region}_lev01-12_v1c.zip"))


def ensure_zip(region="eu", download=True):
    p = zip_path(region)
    if os.path.exists(p) and os.path.getsize(p) > 1e6:
        return p
    if not download:
        raise FileNotFoundError(p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".part"
    urllib.request.urlretrieve(HYBAS_URL.format(reg=region), tmp)      # ~360 MB, cached afterwards, gitignored
    os.replace(tmp, p)
    return p


def extract_level(region, level, download=True):
    """Extract one level's shp/shx/dbf/prj (no .sbn/.sbx: the level-6 spatial index is rejected by GDAL) next to the zip."""
    import zipfile
    zp = ensure_zip(region, download)
    d = os.path.join(os.path.dirname(zp), f"lev{level:02d}")
    shp = os.path.join(d, f"hybas_{region}_lev{level:02d}_v1c.shp")
    if not os.path.exists(shp):
        os.makedirs(d, exist_ok=True)
        with zipfile.ZipFile(zp) as z:
            for ext in ("shp", "shx", "dbf", "prj"):
                z.extract(f"hybas_{region}_lev{level:02d}_v1c.{ext}", d)
    return shp


def select_basins(polys, lake_geom, min_overlap=MIN_OVERLAP):
    """Pure function: indices of basin polygons that overlap >= min_overlap of the lake area (plus the best one)."""
    la = lake_geom.area
    ov = np.array([p.intersection(lake_geom).area / la if p.intersects(lake_geom) else 0.0 for p in polys])
    if ov.size == 0 or ov.max() == 0:
        return []
    keep = set(np.flatnonzero(ov >= min_overlap)) | {int(ov.argmax())}
    return sorted(keep)


def basin_for_lake(lake_ll, area_km2, region="eu", download=True):
    """Return (polygon lon/lat, info dict). Falls back to a lake buffer (flagged fallback=True) on any failure."""
    from pyogrio import raw
    from shapely import from_wkb
    from shapely.ops import unary_union
    level = 7 if area_km2 < 1000 else 6
    try:
        path = extract_level(region, level, download)
        meta, _, geoms, _ = raw.read(path, bbox=tuple(lake_ll.bounds), columns=[])[:4]
        polys = [from_wkb(g) for g in geoms]
        idx = select_basins(polys, lake_ll)
        if not idx:
            raise ValueError("no basin intersects the lake polygon")
        geom = unary_union([polys[i] for i in idx])
        return geom, dict(source="HydroBASINS v1c", region=region, level=level, n_basins=len(idx), fallback=False)
    except Exception as e:  # noqa: BLE001
        from backend.core.geo import to_lonlat, to_utm, utm_epsg
        c = lake_ll.centroid
        epsg = utm_epsg(c.x, c.y)
        geom = to_lonlat(to_utm(lake_ll, epsg).buffer(BUFFER_FALLBACK_KM * 1000), epsg)
        return geom, dict(source=f"buffer {BUFFER_FALLBACK_KM:.0f} km around lake polygon", fallback=True,
                          fallback_reason=f"{type(e).__name__}: {e}"[:200])
