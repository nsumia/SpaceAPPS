"""Geometry helpers: auto UTM, adaptive resolution, lake component selection, lake polygon."""
import hashlib
import math
import warnings

import numpy as np

RES_THRESHOLDS = ((500.0, 30), (5000.0, 60))   # km2 -> metres; anything larger -> 120 m
RES_MAX = 120
WIDE_LAKE_DEG = 6.0


def utm_epsg(lon, lat, width_deg=None):
    """UTM EPSG from the lake centre: 326xx north, 327xx south. Warns when the box is wider than ~6 deg."""
    zone = min(int((lon + 180.0) // 6.0) + 1, 60)
    if width_deg is not None and width_deg > WIDE_LAKE_DEG:
        warnings.warn(f"box is {width_deg:.1f} deg wide (> {WIDE_LAKE_DEG} deg): one UTM zone distorts the edges", stacklevel=2)
    return (32600 if lat >= 0 else 32700) + zone


def bbox_area_km2(bbox):
    lon0, lat0, lon1, lat1 = bbox
    latm = math.radians((lat0 + lat1) / 2)
    return abs((lon1 - lon0) * 111.32 * math.cos(latm) * (lat1 - lat0) * 110.57)


def pick_resolution(area_km2):
    """<500 km2 -> 30 m, <5000 km2 -> 60 m, else 120 m."""
    for limit, res in RES_THRESHOLDS:
        if area_km2 < limit:
            return res
    return RES_MAX


def custom_lake_id(lon, lat):
    return "custom-" + hashlib.sha1(f"{lon:.3f},{lat:.3f}".encode()).hexdigest()[:8]


def select_lake_component(mask, seed_rc, max_snap_px=50):
    """Largest connected (8-neighbour) water component containing the seed pixel (row, col).
    A seed on land snaps to the nearest water pixel within max_snap_px (else ValueError).
    Returns a bool array the shape of mask."""
    from scipy import ndimage as ndi
    mask = np.asarray(mask, bool)
    lab, n = ndi.label(mask, structure=np.ones((3, 3), int))
    if n == 0:
        raise ValueError("no water in mask")
    r, c = (int(seed_rc[0]), int(seed_rc[1]))
    r = min(max(r, 0), mask.shape[0] - 1); c = min(max(c, 0), mask.shape[1] - 1)
    if lab[r, c] == 0:
        dist, (ir, ic) = ndi.distance_transform_edt(lab == 0, return_indices=True)
        if dist[r, c] > max_snap_px:
            raise ValueError(f"seed is {dist[r, c]:.0f} px from the nearest water")
        r, c = int(ir[r, c]), int(ic[r, c])
    return lab == lab[r, c]


def component_to_polygon_utm(comp, transform, buffer_m=1000.0, simplify_m=None):
    """Vectorise a component (rasterio affine transform, UTM metres), fill holes, buffer. Returns a shapely geometry in UTM."""
    from rasterio.features import shapes
    from shapely.geometry import Polygon, shape
    from shapely.ops import unary_union
    polys = [Polygon(shape(g).exterior) for g, v in shapes(comp.astype("uint8"), mask=comp, transform=transform) if v == 1]
    geom = unary_union(polys)
    if simplify_m:
        geom = geom.simplify(simplify_m)
    return geom.buffer(buffer_m)


def to_lonlat(geom_utm, epsg):
    from pyproj import Transformer
    from shapely.ops import transform
    return transform(Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True).transform, geom_utm)


def to_utm(geom_ll, epsg):
    from pyproj import Transformer
    from shapely.ops import transform
    return transform(Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True).transform, geom_ll)
