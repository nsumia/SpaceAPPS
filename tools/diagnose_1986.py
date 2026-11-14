"""Why 1986 area (173 km2) is below Sabuncu's 206 km2: test box, threshold, season, shoreline sensitivity."""
import sys, numpy as np, planetary_computer, pystac_client, odc.stac
sys.path.insert(0, ".")
import burdur_area as ba
from shapely.geometry import box, mapping
odc.stac.configure_rio(cloud_defaults=True, GDAL_HTTP_TIMEOUT="60")
cat = pystac_client.Client.open(ba.STAC_URL, modifier=planetary_computer.sign_inplace)
def run(label, bbox, start, end, thresh=0.0, year=None):
    g = box(*bbox); r = ba.window_area(cat, g, mapping(g), start, end, thresh)
    print(f"{label:55s} area={r['area_km2']:.1f} lst={r['lst_c']} scenes={r['n_scenes']} valid={r['valid_frac']}", flush=True)
big = (29.80, 37.45, 30.50, 38.00)
for yr, (s, e) in {"1986 Aug-Sep": ("1986-08-01", "1986-09-30"), "1986 Jun-Jul": ("1986-06-01", "1986-07-31")}.items():
    run(f"{yr} default box t=0", ba.DEFAULT_BBOX, s, e)
    run(f"{yr} big box t=0", big, s, e)
    for t in (-0.2, -0.1, 0.1):
        run(f"{yr} big box t={t}", big, s, e, t)
