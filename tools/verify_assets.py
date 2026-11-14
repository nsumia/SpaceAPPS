"""Stage 1 assumption check: print asset keys and raster:bands scale/offset of real Landsat items."""
import planetary_computer, pystac_client
cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",
                                modifier=planetary_computer.sign_inplace)
BBOX = [30.0, 37.6, 30.3, 37.85]
for plat, yr in (("landsat-5", 1986), ("landsat-5", 2010), ("landsat-8", 2021), ("landsat-9", 2023)):
    items = list(cat.search(collections=["landsat-c2-l2"], bbox=BBOX, datetime=f"{yr}-08-01/{yr}-09-30",
                            query={"platform": {"eq": plat}}).items())
    if not items:
        print(plat, yr, "NO ITEMS"); continue
    it = items[0]
    print(f"\n{plat} {yr} {it.id} ({len(items)} items) platform={it.properties['platform']}")
    print(" keys:", sorted(it.assets))
    for k in ("lwir", "lwir11", "green", "swir16", "nir08", "nir", "qa_pixel"):
        a = it.assets.get(k)
        if a is None:
            print(f" {k}: MISSING"); continue
        rb = a.extra_fields.get("raster:bands", [{}])[0]
        print(f" {k}: scale={rb.get('scale')} offset={rb.get('offset')} nodata={rb.get('nodata')} unit={rb.get('unit')}")
