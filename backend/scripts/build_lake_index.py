"""Build data/index/lakes.geojson, the lake index used by GET /api/identify.

Sources (see the Stage 4 report for why):
  1. precomputed lakes: data/lakes/*/masks/lake_polygon.geojson (exact analysis polygon, precomputed=true)
  2. Natural Earth 10m lakes (public domain, ~2.3 MB zip, ~1,350 larger lakes world-wide), simplified
  3. optional --hydrolakes <HydroLAKES_polys_v10.shp>: lakes >= --min-km2 (default 50). The full HydroLAKES polygons
     zip is ~820 MB; it was NOT downloaded for the committed index. The reader is here so it can be added later.
lake_id of an index lake = custom_lake_id(representative point) = the id POST /api/analyze {lake_id} will use.
Natural Earth lakes that overlap a precomputed lake (>30 % of the smaller area) are dropped as duplicates.

    .venv/bin/python -m backend.scripts.build_lake_index [--ne-zip PATH] [--hydrolakes SHP]
"""
import argparse
import io
import json
import os
import zipfile

from shapely.geometry import mapping, shape
import shapely.ops

from backend.core.geo import custom_lake_id
from backend.core.lakes import LAKES_DIR, ROOT

NE_URL = "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_lakes.zip"
OUT = os.path.join(ROOT, "data", "index", "lakes.geojson")
SIMPLIFY_DEG = 0.004
MIN_KM2 = 5.0


def area_km2(g):
    import pyproj
    t = pyproj.Transformer.from_crs(4326, 6933, always_xy=True).transform
    return shapely.ops.transform(t, g).area / 1e6


def round_coords(g, nd=4):
    from shapely import set_precision
    return set_precision(g, 10 ** -nd)


def precomputed():
    out = []
    for alias in sorted(os.listdir(LAKES_DIR)):
        pp = os.path.join(LAKES_DIR, alias, "masks", "lake_polygon.geojson")
        mp = os.path.join(LAKES_DIR, alias, "meta.json")
        if not (os.path.exists(pp) and os.path.exists(mp)):
            continue
        meta = json.load(open(mp))
        g = shape(json.load(open(pp))["geometry"]).simplify(0.001)
        out.append(dict(id=meta["lake_id"], alias=alias, name=meta["name"], country=meta.get("country"),
                        polygon_area_km2=round(area_km2(g), 1), precomputed=True, source="precomputed", geom=g))
    return out


def read_shapefile(path, name_fields, area_field=None, min_km2=0.0, source=""):
    import pyogrio.raw
    import shapely
    meta, _, geoms, fields = pyogrio.raw.read(path)
    cols = dict(zip(meta["fields"], fields))
    out = []
    for i, wkb in enumerate(geoms):
        g = shapely.from_wkb(wkb) if wkb is not None else None
        if g is None or g.is_empty:
            continue
        a = float(cols[area_field][i]) if area_field and area_field in cols else area_km2(g)
        if a < min_km2:
            continue
        name = next((str(cols[f][i]) for f in name_fields if f in cols and cols[f][i] not in (None, "") and str(cols[f][i]) != "nan"), None)
        out.append(dict(name=name, polygon_area_km2=round(a, 1), source=source, geom=g.simplify(SIMPLIFY_DEG)))
    return out


def build(ne_zip=None, hydrolakes=None, min_km2_hl=50.0, out=OUT, work_dir=None):
    pre = precomputed()
    feats = list(pre)
    ext = []
    work = work_dir or os.path.join(ROOT, "data", "raw", "ne_lakes")
    os.makedirs(work, exist_ok=True)
    shp = os.path.join(work, "ne_10m_lakes.shp")
    if not os.path.exists(shp):
        if ne_zip:
            data = open(ne_zip, "rb").read()
        else:
            import requests
            data = requests.get(NE_URL, timeout=120).content
        zipfile.ZipFile(io.BytesIO(data)).extractall(work)
    ext += read_shapefile(shp, ("name", "name_alt"), min_km2=MIN_KM2, source="Natural Earth 10m lakes")
    if hydrolakes:
        ext += read_shapefile(hydrolakes, ("Lake_name",), "Lake_area", min_km2_hl, "HydroLAKES v1.0")
    for e in ext:
        small = [p for p in pre if e["geom"].intersects(p["geom"])
                 and e["geom"].intersection(p["geom"]).area > 0.3 * min(e["geom"].area, p["geom"].area)]
        if small:
            continue
        pt = e["geom"].representative_point()
        e.update(id=custom_lake_id(pt.x, pt.y), alias=None, country=None, precomputed=False)
        feats.append(e)
    seen, features = set(), []
    for f in feats:
        if f["id"] in seen:
            continue
        seen.add(f["id"])
        g = round_coords(f["geom"])
        features.append(dict(type="Feature", geometry=mapping(g),
                             properties={k: f[k] for k in ("id", "alias", "name", "country", "polygon_area_km2", "precomputed", "source")}))
    features.sort(key=lambda x: -x["properties"]["polygon_area_km2"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(dict(type="FeatureCollection", features=features, note="lake index for /api/identify; see build_lake_index.py"),
                  fh, separators=(",", ":"))
    return len(features), os.path.getsize(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ne-zip")
    ap.add_argument("--hydrolakes")
    ap.add_argument("--min-km2", type=float, default=50.0)
    a = ap.parse_args()
    print(build(a.ne_zip, a.hydrolakes, a.min_km2))
