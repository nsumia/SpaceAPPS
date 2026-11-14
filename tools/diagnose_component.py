"""Largest connected water component around the lake centre in a wide box, by year/threshold: is the default box clipping the lake?"""
import sys, numpy as np, planetary_computer, pystac_client, odc.stac
from scipy import ndimage as ndi
sys.path.insert(0, ".")
import burdur_area as ba
odc.stac.configure_rio(cloud_defaults=True, GDAL_HTTP_TIMEOUT="60")
cat = pystac_client.Client.open(ba.STAC_URL, modifier=planetary_computer.sign_inplace)
big = (29.80, 37.45, 30.50, 38.00)
for yr in (1986, 2020):
    items = list(cat.search(collections=["landsat-c2-l2"], bbox=big, datetime=f"{yr}-08-01/{yr}-09-30",
        query={"platform": {"in": ba.PLATFORMS}, "eo:cloud_cover": {"lt": 40}}).items())
    ds = odc.stac.load(items, bands=["green", "swir16", "qa_pixel"], bbox=big, crs=ba.CRS, resolution=30,
                       groupby="solar_day", patch_url=planetary_computer.sign).compute()
    g = ds.green.values.astype("float32") * ba.SCALE + ba.OFFSET; s = ds.swir16.values.astype("float32") * ba.SCALE + ba.OFFSET
    qa = ds.qa_pixel.values.astype("uint16"); bad = sum(((qa >> b) & 1) for b in ba.CLOUD_BITS) > 0
    m = np.where(bad | (ds.green.values == 0), np.nan, (g - s) / (g + s)); comp = np.nanmedian(m, axis=0)
    from pyproj import Transformer
    x, y = Transformer.from_crs("EPSG:4326", ba.CRS, always_xy=True).transform(30.18, 37.72)
    xs, ys = ds.x.values, ds.y.values
    ci, cj = np.argmin(abs(ys - y)), np.argmin(abs(xs - x))
    inv = Transformer.from_crs(ba.CRS, "EPSG:4326", always_xy=True).transform
    for t in (0.0, -0.1, -0.2):
        lab, _ = ndi.label(np.nan_to_num(comp, nan=-9) > t)
        c = lab == lab[ci, cj]
        jj = np.where(c.any(0))[0]; ii = np.where(c.any(1))[0]
        lo = inv(xs[jj.min()], ys[ii.max()]); hi = inv(xs[jj.max()], ys[ii.min()])
        print(f"{yr} t={t}: lake component {c.sum()*900/1e6:.1f} km2, lon {lo[0]:.3f}-{hi[0]:.3f} lat {lo[1]:.3f}-{hi[1]:.3f}", flush=True)
