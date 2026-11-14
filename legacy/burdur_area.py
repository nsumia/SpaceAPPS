"""
Göl Kaybı Dedektörü — Aşama 1: Landsat ile yıllık göl alanı serisi + trend testi.

Kullanım:
    pip install pystac-client planetary-computer odc-stac pymannkendall shapely pandas matplotlib dask
    python burdur_area.py                       # Burdur, yaklaşık kutu ile
    python burdur_area.py --geojson burdur.geojson --name Burdur
    python burdur_area.py --start 1985 --end 2025

Çıktılar:  <name>_area.csv, <name>_area.png  ve terminalde trend özeti.

Yöntem:
  - Her yıl için Ağustos–Eylül Landsat 5/8/9 Collection 2 Level-2 sahneleri (Landsat 7 atlanır: SLC-off şeritleri).
  - Bulut / gölge / genişletilmiş bulut pikselleri QA_PIXEL ile maskelenir.
  - MNDWI = (Green - SWIR1) / (Green + SWIR1); yıllık medyan kompozit; MNDWI > eşik -> su.
  - Alan = su piksel sayısı x 900 m².  Geçerli piksel oranı düşük yıllar işaretlenir.
  - Trend: Hamed-Rao düzeltmeli Mann-Kendall (otokorelasyona dayanıklı) + Sen eğimi.
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd

# Burdur Gölü için yaklaşık kutu (lon_min, lat_min, lon_max, lat_max). Mümkünse elle çizilmiş poligon kullanın.
DEFAULT_BBOX = (29.95, 37.60, 30.30, 37.85)
PLATFORMS = ["landsat-5", "landsat-8", "landsat-9"]
SCALE, OFFSET = 0.0000275, -0.2           # Collection 2 L2 yüzey yansıtımı
CLOUD_BITS = (1, 3, 4)                     # dilated cloud, cloud, cloud shadow
ST_SCALE, ST_OFFSET = 0.00341802, 149.0    # Collection 2 L2 yüzey sıcaklığı (Kelvin)
LST_EROSION = 5                            # kıyı karışımını önlemek için su maskesini 5 piksel (150 m) aşındır
LST_MIN_PX = 50                            # bundan az saf su pikseli varsa sıcaklık raporlanmaz


def load_geometry(path):
    from shapely.geometry import box, shape, mapping
    if path is None:
        geom = box(*DEFAULT_BBOX)
        print("UYARI: GeoJSON verilmedi, yaklaşık kutu kullanılıyor. Komşu su kütleleri karışabilir.")
    else:
        with open(path) as f:
            gj = json.load(f)
        feat = gj["features"][0] if gj.get("type") == "FeatureCollection" else gj
        geom = shape(feat.get("geometry", feat))
    return geom, mapping(geom)


def year_area(catalog, geom, geom_json, year, thresh, max_cloud):
    row = window_area(catalog, geom, geom_json, f"{year}-08-01", f"{year}-09-30", thresh, max_cloud)
    row.pop("latest_scene", None)
    return dict(year=year, **row)


def window_area(catalog, geom, geom_json, start, end, thresh=0.0, max_cloud=40):
    """İstenen tarih aralığındaki (YYYY-MM-DD) Landsat sahnelerinden göl alanı."""
    import odc.stac
    import planetary_computer
    from rasterio.features import geometry_mask

    search = catalog.search(
        collections=["landsat-c2-l2"],
        intersects=geom_json,
        datetime=f"{start}/{end}",
        query={"platform": {"in": PLATFORMS}, "eo:cloud_cover": {"lt": max_cloud}},
    )
    items = list(search.items())
    if not items:
        return dict(area_km2=np.nan, n_scenes=0, valid_frac=0.0, lst_c=np.nan, lst_px=0, latest_scene=None)
    latest = max(i.datetime for i in items).date().isoformat()

    # Termal bant adı sensöre göre değişir: Landsat 5 TM -> "lwir", Landsat 8/9 OLI-TIRS -> "lwir11".
    # Aileleri ayrı yükleyip termal bandı "st" olarak adlandırıyoruz, sonra zaman ekseninde birleştiriyoruz.
    import xarray as xr
    parts = []
    for thermal, plats in (("lwir", {"landsat-5"}), ("lwir11", {"landsat-8", "landsat-9"})):
        fam = [i for i in items if i.properties.get("platform") in plats]
        if not fam:
            continue
        d = odc.stac.load(
            fam,
            bands=["green", "swir16", "qa_pixel", thermal],
            bbox=geom.bounds,
            crs="EPSG:32636",
            resolution=30,
            groupby="solar_day",
            chunks={"x": 2048, "y": 2048},
            patch_url=planetary_computer.sign,
        )
        parts.append(d.rename({thermal: "st"}))
    ds = parts[0] if len(parts) == 1 else xr.concat(parts, dim="time")

    qa = ds["qa_pixel"].astype("uint16")
    bad = sum(((qa >> b) & 1) for b in CLOUD_BITS) > 0
    nodata = (ds["green"] == 0) | (ds["swir16"] == 0)
    good = ~bad & ~nodata
    g = ds["green"].astype("float32") * SCALE + OFFSET
    s = ds["swir16"].astype("float32") * SCALE + OFFSET
    mndwi = ((g - s) / (g + s)).where(good)
    # Yüzey sıcaklığı (Kelvin): DN * 0.00341802 + 149.0 ;  0 = nodata
    st_k = (ds["st"].astype("float32") * ST_SCALE + ST_OFFSET).where(good & (ds["st"] > 0))
    comp = mndwi.median("time", skipna=True).compute().values
    st_comp = st_k.median("time", skipna=True).compute().values - 273.15

    # Poligon maskesi (kutu dışında kalan pikselleri at)
    transform = ds.odc.geobox.affine
    from shapely.ops import transform as shp_transform
    from pyproj import Transformer
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32636", always_xy=True).transform
    geom_utm = shp_transform(to_utm, geom)
    inside = geometry_mask([geom_utm], out_shape=comp.shape, transform=transform, invert=True)

    valid = inside & np.isfinite(comp)
    water = valid & (comp > thresh)

    # Göl yüzey sıcaklığı: kıyıdan uzak "saf su" pikselleri (termal piksel ~100 m -> 5 piksel = 150 m aşındırma)
    from scipy.ndimage import binary_erosion
    core = binary_erosion(water, iterations=LST_EROSION) & np.isfinite(st_comp)
    n_core = int(core.sum())
    lst = float(np.median(st_comp[core])) if n_core >= LST_MIN_PX else np.nan
    return dict(
        area_km2=float(water.sum() * 900 / 1e6),
        n_scenes=len(items),
        valid_frac=round(float(valid.sum() / max(inside.sum(), 1)), 3),
        lst_c=round(lst, 2) if lst == lst else np.nan,
        lst_px=n_core,
        latest_scene=latest,
    )


def trend_summary(df, min_valid):
    import pymannkendall as mk
    d = df[(df.valid_frac >= min_valid) & df.area_km2.notna()]
    if len(d) < 10:
        print("Trend için yeterli yıl yok.")
        return None
    r = mk.hamed_rao_modification_test(d.area_km2.values)
    first, last = d.iloc[0], d.iloc[-1]
    print("\n=== TREND ÖZETİ ===")
    print(f"Yıllar: {int(first.year)}–{int(last.year)}  (kullanılan yıl: {len(d)})")
    print(f"Alan: {first.area_km2:.1f} km² -> {last.area_km2:.1f} km²  "
          f"({100 * (last.area_km2 - first.area_km2) / first.area_km2:+.1f} %)")
    print(f"Sen eğimi: {r.slope * 10:+.2f} km²/on yıl")
    print(f"Mann-Kendall (Hamed-Rao): eğilim={r.trend}, p={r.p:.4g}")

    t = d[d.lst_c.notna()]
    if len(t) >= 10:
        rt = mk.hamed_rao_modification_test(t.lst_c.values)
        print(f"\nGöl yüzey sıcaklığı (yaz sonu, saf su pikselleri): kullanılan yıl {len(t)}")
        print(f"Sen eğimi: {rt.slope * 10:+.2f} °C/on yıl   eğilim={rt.trend}, p={rt.p:.4g}")
    return r


def plot(df, name, r, min_valid):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ok = df.valid_frac >= min_valid
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(df.year[ok], df.area_km2[ok], "o-", color="#1f6fb4", label="Landsat yaz sonu alanı")
    ax.plot(df.year[~ok], df.area_km2[~ok], "x", color="#999", label="Düşük kapsama (trend dışı)")
    if r is not None:
        d = df[ok & df.area_km2.notna()]
        x0 = d.year.values[0]
        ax.plot(d.year, r.intercept + r.slope * (d.year - x0), "--", color="#c0392b",
                label=f"Sen eğimi {r.slope * 10:+.1f} km²/on yıl (p={r.p:.2g})")
    ax.set_title(f"{name} Gölü yüzey alanı (Landsat, Ağu–Eyl)")
    ax.set_xlabel("Yıl"); ax.set_ylabel("Alan (km²)")
    ax.grid(alpha=0.3); ax.legend(frameon=False)
    fig.tight_layout()
    out = f"{name.lower()}_area.png"
    fig.savefig(out, dpi=150)
    print(f"Grafik: {out}")

    t = df[ok & df.lst_c.notna()]
    if len(t) >= 5:
        import pymannkendall as mk
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.plot(t.year, t.lst_c, "o-", color="#d35400", label="Yaz sonu göl yüzey sıcaklığı")
        if len(t) >= 10:
            rt = mk.hamed_rao_modification_test(t.lst_c.values)
            ax.plot(t.year, rt.intercept + rt.slope * (t.year - t.year.values[0]), "--", color="#7f1d1d",
                    label=f"Sen eğimi {rt.slope * 10:+.2f} °C/on yıl (p={rt.p:.2g})")
        ax.set_title(f"{name} Gölü yüzey sıcaklığı (Landsat termal, Ağu–Eyl)")
        ax.set_xlabel("Yıl"); ax.set_ylabel("°C")
        ax.grid(alpha=0.3); ax.legend(frameon=False)
        fig.tight_layout()
        out = f"{name.lower()}_lst.png"
        fig.savefig(out, dpi=150)
        print(f"Grafik: {out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--geojson", default=None)
    p.add_argument("--name", default="Burdur")
    p.add_argument("--start", type=int, default=1985)
    p.add_argument("--end", type=int, default=2025)
    p.add_argument("--thresh", type=float, default=0.0, help="MNDWI su eşiği")
    p.add_argument("--max-cloud", type=float, default=40)
    p.add_argument("--min-valid", type=float, default=0.8, help="Trende alınacak min. geçerli piksel oranı")
    a = p.parse_args()

    import pystac_client
    import planetary_computer
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    geom, geom_json = load_geometry(a.geojson)

    rows = []
    for y in range(a.start, a.end + 1):
        try:
            row = year_area(catalog, geom, geom_json, y, a.thresh, a.max_cloud)
        except Exception as e:  # tek bir yılın hatası tüm işi durdurmasın
            print(f"{y}: HATA {e}", file=sys.stderr)
            row = dict(year=y, area_km2=np.nan, n_scenes=0, valid_frac=0.0, lst_c=np.nan, lst_px=0)
        print(f"{y}: {row['area_km2']:.1f} km²  LST={row['lst_c']:.1f} °C  sahne={row['n_scenes']}  "
              f"geçerli={row['valid_frac']}")
        rows.append(row)

    df = pd.DataFrame(rows)
    out = f"{a.name.lower()}_area.csv"
    df.to_csv(out, index=False)
    print(f"Tablo: {out}")
    r = trend_summary(df, a.min_valid)
    plot(df, a.name, r, a.min_valid)


if __name__ == "__main__":
    main()
