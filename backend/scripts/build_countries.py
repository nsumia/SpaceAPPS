"""Offline basemap: Natural Earth 50m admin-0 countries -> data/index/countries.geojson (simplified, 2-decimal coords).
  curl -O https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip ; unzip ; 
  .venv/bin/python -m backend.scripts.build_countries <path/to/ne_50m_admin_0_countries.shp>
Natural Earth is public domain. Served by GET /api/basemap/countries when the online basemaps are unreachable."""
import json
import sys

import numpy as np
import pyogrio.raw
import shapely
from shapely.geometry import mapping

from backend.core.lakes import ROOT


def main(shp, out=f"{ROOT}/data/index/countries.geojson", tol=0.02):
    meta, _, geoms, fields = pyogrio.raw.read(shp, columns=["NAME"])
    names = fields[0]
    feats = []
    for wkb, name in zip(geoms, names):
        g = shapely.from_wkb(wkb).simplify(tol, preserve_topology=True)
        g = shapely.set_precision(g, 0.01)
        if g.is_empty:
            continue
        feats.append(dict(type="Feature", properties=dict(name=str(name)), geometry=mapping(g)))
    with open(out, "w") as f:
        json.dump(dict(type="FeatureCollection", features=feats), f, separators=(",", ":"))
    print(len(feats), "countries ->", out)


if __name__ == "__main__":
    main(sys.argv[1])
