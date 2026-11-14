"""Live data layer (moved from legacy/live_data.py; full live endpoints are Stage 4).
Fixes vs legacy: imports backend.core.landsat (was burdur_area), window_area now returns latest_scene,
POWER via climate.py (mm/day x days, EVLAND added), SWOT via swot.py with fill filtering, lake boxes from lakes.py.
Each source fails independently; the error goes into the JSON."""
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from backend.core import climate, landsat, swot
from backend.core.lakes import LAKES


def _ok(source, **data):
    return dict(source=source, ok=True, fetched_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), **data)


def _fail(source, err):
    return dict(source=source, ok=False, error=str(err)[:300])


def landsat_now(lake, days=45):
    """Area/LST of the last `days` days vs the same window a year earlier."""
    try:
        from shapely.geometry import box, mapping
        from backend.core import geo
        cat = landsat.open_catalog()
        geom = box(*lake["bbox"]); gj = mapping(geom)
        seed = lake["seed"]
        epsg = geo.utm_epsg(seed[0], seed[1])
        res = geo.pick_resolution(geo.bbox_area_km2(lake["bbox"]))
        end = date.today(); start = end - timedelta(days=days)
        kw = dict(max_cloud=60, crs=f"EPSG:{epsg}", pixel_m=res)
        now = landsat.window_area(cat, geom, gj, start.isoformat(), end.isoformat(), **kw)
        ly = landsat.window_area(cat, geom, gj, start.replace(year=start.year - 1).isoformat(),
                                 end.replace(year=end.year - 1).isoformat(), **kw)
        change = None
        if now["area_km2"] == now["area_km2"] and ly["area_km2"] == ly["area_km2"] and ly["area_km2"]:
            change = round(100 * (now["area_km2"] - ly["area_km2"]) / ly["area_km2"], 1)
        lst_d = None
        if now["lst_c"] == now["lst_c"] and ly["lst_c"] == ly["lst_c"]:
            lst_d = round(now["lst_c"] - ly["lst_c"], 1)
        return _ok("Landsat C2 L2 (Planetary Computer)", window=f"{start} to {end}", area_km2=round(now["area_km2"], 1),
                   latest_scene=now["latest_scene"], valid_frac=now["valid_frac"],
                   last_year_area_km2=round(ly["area_km2"], 1), change_vs_last_year_pct=change,
                   lst_c=now["lst_c"], last_year_lst_c=ly["lst_c"], lst_change_vs_last_year_c=lst_d, lst_px=now["lst_px"])
    except Exception as e:  # noqa: BLE001
        return _fail("Landsat", e)


def swot_now(lake):
    if not lake.get("pld_id"):
        return _fail("SWOT Hydrocron", "no pld_id for this lake (Stage 3: PLD lookup)")
    try:
        df = swot.recent(lake["pld_id"])
        if df.empty:
            return _fail("SWOT Hydrocron", "no valid observations")
        last = df.iloc[-1]
        ago = df[df.t <= last.t - pd.Timedelta(days=330)]
        d1y = round(float(last.wse - ago.iloc[-1].wse), 2) if len(ago) else None
        return _ok("SWOT L2_HR_LakeSP (Hydrocron)", last_obs=last.t.date().isoformat(), wse_m=round(float(last.wse), 2),
                   area_km2=round(float(last.area_total), 1), wse_change_1y_m=d1y, n_obs=len(df),
                   series=[[str(t.date()), float(w)] for t, w in zip(df.t, df.wse)])
    except Exception as e:  # noqa: BLE001
        return _fail("SWOT Hydrocron", e)


def precip_now(lake, basin_points=None):
    """Water-year (since 1 Oct, or 1 Apr in the south) precipitation vs 1991-2020 same-period mean, at basin points
    (default: the lake seed). POWER daily mm/day summed (1 value = 1 day); normal from monthly mm/day x days."""
    try:
        pts = basin_points or [lake["seed"]]
        south = lake["seed"][1] < 0
        today = date.today()
        wy0 = climate.water_year_start(today, south)
        cur, nor = [], []
        for lon, lat in pts:
            dd = climate.power("daily", lon, lat, wy0.strftime("%Y%m%d"), today.strftime("%Y%m%d"), params=("PRECTOTCORR",))["PRECTOTCORR"]
            ok = {k: v for k, v in dd.items() if v is not None and v > climate.FILL + 1}
            last_day = pd.Timestamp(max(ok))
            cur.append(sum(ok.values()))
            mm = climate.monthly_mm(climate.power("monthly", lon, lat, "1991", "2020", params=("PRECTOTCORR",))["PRECTOTCORR"])
            tot = 0.0
            for mo in pd.date_range(wy0, last_day, freq="MS"):
                frac = last_day.day / mo.days_in_month if (mo.year, mo.month) == (last_day.year, last_day.month) else 1.0
                tot += mm[mm.index.month == mo.month].mean() * frac
            nor.append(tot)
        c, n = sum(cur) / len(cur), sum(nor) / len(nor)
        return _ok("NASA POWER (PRECTOTCORR)", water_year_start=wy0.isoformat(), data_until=last_day.date().isoformat(),
                   precip_mm=round(float(c), 1), normal_mm=round(float(n), 1), pct_of_normal=round(100 * c / n) if n else None)
    except Exception as e:  # noqa: BLE001
        return _fail("NASA POWER", e)


def gibs_image_url(lake, day=None, layer="VIIRS_NOAA20_CorrectedReflectance_TrueColor", width=900):
    """Daily true-colour WMS 1.3.0 EPSG:4326 URL; BBOX order is lat_min,lon_min,lat_max,lon_max (verified; a wrong
    order returns a wrong picture, not an error). Defaults to yesterday."""
    day = day or (date.today() - timedelta(days=1))
    lon0, lat0, lon1, lat1 = lake["bbox"]
    pad = 0.05
    height = int(width * (lat1 - lat0 + 2 * pad) / (lon1 - lon0 + 2 * pad))
    return ("https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
            f"&LAYERS={layer}&STYLES=&CRS=EPSG:4326&BBOX={lat0-pad},{lon0-pad},{lat1+pad},{lon1+pad}"
            f"&WIDTH={width}&HEIGHT={height}&FORMAT=image/jpeg&TIME={day.isoformat()}")


def snapshot(key, with_landsat=True):
    lake = LAKES[key]
    out = dict(lake=lake["name"], generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               precip=precip_now(lake), swot=swot_now(lake), image_url=gibs_image_url(lake))
    if with_landsat:
        out["landsat"] = landsat_now(lake)
    return out
