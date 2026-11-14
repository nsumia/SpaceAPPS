"""
Göl Kaybı Dedektörü — CANLI VERİ katmanı.

Her çağrıda NASA API'lerinden güncel veriyi çeker:
  1. Landsat (Planetary Computer STAC)  -> son 45 günün göl alanı, geçen yılın aynı dönemiyle karşılaştırma
  2. SWOT (PO.DAAC Hydrocron API)       -> son su seviyesi ölçümü ve 1 yıllık değişim
  3. NASA POWER API                     -> su yılı (1 Ekim'den beri) yağışı ve uzun dönem ortalamaya oranı
  4. NASA GIBS WMS                      -> en güncel günlük uydu görüntüsü (VIIRS gerçek renk)

Kullanım:
    python live_data.py --lake burdur          # live_burdur.json yazar ve özet basar
Streamlit uygulaması (app.py) bu fonksiyonları önbellekli olarak çağırır.

Hiçbir anahtar gerekmez. Bir kaynak hata verirse diğerleri yine çalışır; hata JSON'a yazılır.
"""
import argparse
import io
import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

# ---------------------------------------------------------------- Göl ayarları
# bbox = (lon_min, lat_min, lon_max, lat_max).  Değerler yaklaşık: haritada kontrol edin.
# pld_id: SWOT Prior Lake Database kimliği. PLD'den bulup doldurun (None ise SWOT atlanır).
LAKES = {
    "burdur":  dict(name="Burdur",  bbox=(29.95, 37.60, 30.30, 37.85), center=(30.12, 37.72),
                    basin_points=[(29.9, 37.6), (30.2, 37.8), (30.4, 37.6), (30.1, 37.9)], pld_id=None),
    "aksehir": dict(name="Akşehir", bbox=(31.30, 38.40, 31.60, 38.65), center=(31.45, 38.53),
                    basin_points=[(31.1, 38.4), (31.4, 38.6), (31.6, 38.3), (31.3, 38.8)], pld_id=None),
    "egirdir": dict(name="Eğirdir", bbox=(30.75, 37.85, 30.95, 38.30), center=(30.85, 38.05),
                    basin_points=[(30.7, 37.9), (30.9, 38.1), (30.8, 38.4), (31.0, 37.8)], pld_id=None),
    "van":     dict(name="Van",     bbox=(42.25, 38.25, 43.75, 39.05), center=(42.95, 38.65),
                    basin_points=[(42.5, 38.4), (43.3, 38.5), (43.0, 39.1), (42.3, 38.9)], pld_id=None),
}
TIMEOUT = 60


def _ok(source, **data):
    return dict(source=source, ok=True, fetched_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), **data)


def _fail(source, err):
    return dict(source=source, ok=False, error=str(err)[:300])


# ---------------------------------------------------------------- 1. Landsat
def landsat_now(lake, days=45):
    """Son `days` günün alanı vs. geçen yılın aynı penceresi."""
    try:
        import pystac_client, planetary_computer
        from shapely.geometry import box, mapping
        from burdur_area import window_area
        cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",
                                        modifier=planetary_computer.sign_inplace)
        geom = box(*lake["bbox"]); gj = mapping(geom)
        end = date.today(); start = end - timedelta(days=days)
        now = window_area(cat, geom, gj, start.isoformat(), end.isoformat(), max_cloud=60)
        ly = window_area(cat, geom, gj, (start.replace(year=start.year - 1)).isoformat(),
                         (end.replace(year=end.year - 1)).isoformat(), max_cloud=60)
        change = None
        if now["area_km2"] == now["area_km2"] and ly["area_km2"]:  # NaN kontrolü
            change = round(100 * (now["area_km2"] - ly["area_km2"]) / ly["area_km2"], 1)
        lst_d = None
        if now["lst_c"] == now["lst_c"] and ly["lst_c"] == ly["lst_c"]:
            lst_d = round(now["lst_c"] - ly["lst_c"], 1)
        return _ok("Landsat C2 L2 (Planetary Computer)", window=f"{start}–{end}",
                   area_km2=round(now["area_km2"], 1), latest_scene=now["latest_scene"],
                   valid_frac=now["valid_frac"], last_year_area_km2=round(ly["area_km2"], 1),
                   change_vs_last_year_pct=change,
                   lst_c=now["lst_c"], last_year_lst_c=ly["lst_c"], lst_change_vs_last_year_c=lst_d,
                   lst_px=now["lst_px"])
    except Exception as e:
        return _fail("Landsat", e)


# ---------------------------------------------------------------- 2. SWOT / Hydrocron
HYDROCRON = "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries"


def swot_now(lake):
    if not lake.get("pld_id"):
        return _fail("SWOT Hydrocron", "pld_id tanımlı değil (LAKES sözlüğünde doldurun)")
    try:
        end = datetime.now(timezone.utc); start = end - timedelta(days=500)
        r = requests.get(HYDROCRON, timeout=TIMEOUT, headers={"Accept": "text/csv"}, params=dict(
            feature="PriorLake", feature_id=lake["pld_id"],
            start_time=start.strftime("%Y-%m-%dT%H:%M:%SZ"), end_time=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            fields="lake_id,time_str,wse,area_total"))
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df = df[(df.time_str != "no_data") & (df.wse > -1000)].copy()
        if df.empty:
            return _fail("SWOT Hydrocron", "geçerli ölçüm yok")
        df["t"] = pd.to_datetime(df.time_str, utc=True)
        df = df.sort_values("t")
        last = df.iloc[-1]
        year_ago = df[df.t <= last.t - pd.Timedelta(days=330)]
        d1y = round(float(last.wse - year_ago.iloc[-1].wse), 2) if len(year_ago) else None
        return _ok("SWOT L2_HR_LakeSP (Hydrocron)", last_obs=last.t.date().isoformat(),
                   wse_m=round(float(last.wse), 2), area_km2=round(float(last.area_total), 1),
                   wse_change_1y_m=d1y, n_obs=len(df),
                   series=df[["t", "wse"]].assign(t=df.t.dt.date.astype(str)).values.tolist())
    except Exception as e:
        return _fail("SWOT Hydrocron", e)


# ---------------------------------------------------------------- 3. NASA POWER
POWER = "https://power.larc.nasa.gov/api/temporal"


def _power(kind, lon, lat, start, end, param="PRECTOTCORR"):
    r = requests.get(f"{POWER}/{kind}/point", timeout=TIMEOUT, params=dict(
        parameters=param, community="AG", longitude=lon, latitude=lat, start=start, end=end, format="JSON"))
    r.raise_for_status()
    return r.json()["properties"]["parameter"][param]


def precip_now(lake):
    """Su yılı (1 Ekim'den bugüne) toplam yağış vs. 1991–2020 aynı dönem ortalaması, havza noktaları ortalaması."""
    try:
        today = date.today()
        wy_start = date(today.year if today.month >= 10 else today.year - 1, 10, 1)
        cur, clim = [], []
        for lon, lat in lake["basin_points"]:
            d = _power("daily", lon, lat, wy_start.strftime("%Y%m%d"), today.strftime("%Y%m%d"))
            vals = [v for v in d.values() if v is not None and v > -900]
            cur.append(sum(vals))
            last_day = max(k for k, v in d.items() if v is not None and v > -900)
            # Aynı takvim penceresinin 1991–2020 ortalaması (aylık veriden, kısmi ay oranlanır)
            m = _power("monthly", lon, lat, "1991", "2020")
            s = pd.Series({k: v for k, v in m.items() if not k.endswith("13")})
            s.index = pd.to_datetime(s.index, format="%Y%m")
            s = s * s.index.days_in_month          # mm/gün -> mm/ay
            months = pd.date_range(wy_start, pd.Timestamp(last_day), freq="MS")
            tot = 0.0
            for mo in months:
                frac = 1.0
                if mo.month == pd.Timestamp(last_day).month and mo.year == pd.Timestamp(last_day).year:
                    frac = pd.Timestamp(last_day).day / mo.days_in_month
                tot += s[s.index.month == mo.month].mean() * frac
            clim.append(tot)
        c, n = sum(cur) / len(cur), sum(clim) / len(clim)
        last_iso = pd.Timestamp(last_day).date().isoformat()
        return _ok("NASA POWER (PRECTOTCORR)", water_year_start=wy_start.isoformat(), data_until=last_iso,
                   precip_mm=round(float(c), 1), normal_mm=round(float(n), 1),
                   pct_of_normal=round(100 * c / n) if n else None)
    except Exception as e:
        return _fail("NASA POWER", e)


# ---------------------------------------------------------------- 4. GIBS görüntü
def gibs_image_url(lake, day=None, layer="VIIRS_NOAA20_CorrectedReflectance_TrueColor", width=900):
    """Günlük gerçek renk görüntü URL'si (WMS 1.3.0, EPSG:4326 -> BBOX sırası lat,lon). Dün varsayılan: bugünkü kapsama eksik olabilir."""
    day = day or (date.today() - timedelta(days=1))
    lon0, lat0, lon1, lat1 = lake["bbox"]
    pad = 0.05
    height = int(width * (lat1 - lat0 + 2 * pad) / (lon1 - lon0 + 2 * pad))
    return ("https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
            f"&LAYERS={layer}&STYLES=&CRS=EPSG:4326&BBOX={lat0-pad},{lon0-pad},{lat1+pad},{lon1+pad}"
            f"&WIDTH={width}&HEIGHT={height}&FORMAT=image/jpeg&TIME={day.isoformat()}")


# ---------------------------------------------------------------- Hepsi
def snapshot(key, with_landsat=True):
    lake = LAKES[key]
    out = dict(lake=lake["name"], generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               precip=precip_now(lake), swot=swot_now(lake), image_url=gibs_image_url(lake))
    if with_landsat:
        out["landsat"] = landsat_now(lake)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--lake", default="burdur", choices=LAKES)
    p.add_argument("--no-landsat", action="store_true", help="Hızlı mod: Landsat'ı atla")
    a = p.parse_args()
    s = snapshot(a.lake, with_landsat=not a.no_landsat)
    with open(f"live_{a.lake}.json", "w") as f:
        json.dump(s, f, ensure_ascii=False, indent=2, default=str)
    for k in ("landsat", "swot", "precip"):
        if k in s:
            v = s[k]
            print(f"[{k}] {'OK' if v['ok'] else 'HATA'}: " +
                  json.dumps({x: y for x, y in v.items() if x not in ("series",)}, ensure_ascii=False, default=str))
    print("Görüntü:", s["image_url"])
