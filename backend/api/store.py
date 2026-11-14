"""Read access to lake records (precomputed data/lakes/<alias>/ and on-demand data/custom/<id>/), summaries, masks,
compare. Pure functions over a Settings object so tests can point them at temp dirs."""
import base64
import json
import os
from dataclasses import dataclass, field

import numpy as np

from backend.core.lakes import ROOT

# Lakes whose area series was checked against literature (VALIDATION.md section 2, Burdur: Sabuncu 2020 206 / 125 km2).
VALIDATED = {"burdur"}
LST_SENSOR_BREAK = ("Landsat 5 -> 8 step of about +3 C at 2012/13 (Stage 1): warming_c_per_decade uses Landsat 5 only "
                    "(1985-2012); the pooled slope (warming_pooled_c_per_decade) contains the sensor break and overstates warming.")
REF = (1985, 1990)


@dataclass
class Settings:
    lakes_dir: str = os.path.join(ROOT, "data", "lakes")
    custom_dir: str = os.path.join(ROOT, "data", "custom")
    cache_dir: str = os.path.join(ROOT, "data", "live_cache")
    jobs_db: str = os.path.join(ROOT, "data", "jobs.sqlite")
    index_path: str = os.path.join(ROOT, "data", "index", "lakes.geojson")
    live_ttl_s: int = 3 * 3600
    start_worker: bool = True
    _cache: dict = field(default_factory=dict, repr=False)


def _load(path):
    with open(path) as f:
        return json.load(f)


def lake_dirs(st):
    """{key: (dir, is_custom)} for every readable record; keys are alias and lake_id."""
    out = {}
    for base, custom in ((st.lakes_dir, False), (st.custom_dir, True)):
        if not os.path.isdir(base):
            continue
        for d in sorted(os.listdir(base)):
            p = os.path.join(base, d)
            if not os.path.exists(os.path.join(p, "series.json")):
                continue
            out[d] = (p, custom)
            mp = os.path.join(p, "meta.json")
            if os.path.exists(mp):
                out.setdefault(_load(mp).get("lake_id", d), (p, custom))
    return out


def resolve(st, key):
    return lake_dirs(st).get(key)


def record(st, key):
    r = resolve(st, key)
    if not r:
        return None
    d, custom = r
    rec = dict(dir=d, custom=custom, series=_load(os.path.join(d, "series.json")))
    rec["meta"] = _load(os.path.join(d, "meta.json")) if os.path.exists(os.path.join(d, "meta.json")) else {}
    for n in ("climate", "swot"):
        p = os.path.join(d, n + ".json")
        rec[n] = _load(p) if os.path.exists(p) else None
    return rec


def valid_rows(series, min_valid):
    return [r for r in series if r.get("area_km2") is not None and (r.get("valid_frac") or 0) >= min_valid]


def centre(rec):
    p = os.path.join(rec["dir"], "masks", "lake_polygon.geojson")
    if os.path.exists(p):
        from shapely.geometry import shape
        c = shape(_load(p)["geometry"]).centroid
        return [round(c.x, 4), round(c.y, 4)]
    return rec["meta"].get("seed")


def summary(st, key):
    rec = record(st, key)
    s, meta, stats = rec["series"], rec["meta"], rec["series"].get("stats") or {}
    rows = valid_rows(s["series"], s.get("min_valid", 0.8))
    ref = [r["area_km2"] for r in rows if REF[0] <= r["year"] <= REF[1]]
    ref_mean = float(np.mean(ref)) if ref else None
    last = [r["area_km2"] for r in rows[-3:]]
    area = stats.get("area")
    loss = trend = None
    if ref_mean and last:
        loss = round(100 * (ref_mean - float(np.mean(last))) / ref_mean, 1)
        if area:
            trend = round(100 * area["sen_slope_per_decade"] / ref_mean, 2)
    em = stats.get("area_emergence") or {}
    l5 = stats.get("lst_1985_2012")
    pooled = stats.get("lst_all")
    dec = ((rec["climate"] or {}).get("decomposition")) or {}
    custom = rec["custom"]
    alias = meta.get("alias")
    group = meta.get("group") or ("custom" if custom else ("turkey" if meta.get("country") == "TR" else "reference"))
    return dict(
        id=meta.get("lake_id", key), alias=alias, name=meta.get("name") or s.get("lake"), country=meta.get("country"),
        centre=centre(rec), group=group, validated=bool(alias in VALIDATED and not custom), unverified=bool(custom),
        years=meta.get("years"), ref_mean_km2=None if ref_mean is None else round(ref_mean, 1),
        total_loss_pct=loss, total_loss_basis=f"mean {REF[0]}-{REF[1]} vs mean of last 3 valid years",
        trend_pct_per_decade=trend, trend_p=area and round(area["p"], 6), trend_direction=area and area["trend"],
        emergence_year=em.get("year"), emergence_status=em.get("status"),
        emergence_censored_at_ref_end=bool(em.get("censored_at_ref_end")), emergence_note=em.get("censored_note"),
        warming_c_per_decade=l5 and round(l5["sen_slope_per_decade"], 2),
        warming_basis="Landsat 5 only, 1985-2012" if l5 else None,
        warming_pooled_c_per_decade=pooled and round(pooled["sen_slope_per_decade"], 2),
        warming_sensor_break_caveat=LST_SENSOR_BREAK,
        climate_explained_share=dec.get("explained_share") if dec.get("ok") else None,
        climate_explained_ci90=dec.get("explained_share_ci90") if dec.get("ok") else None,
        climate_interpretable=bool(dec.get("interpretable", False)) if dec.get("ok") else False,
        climate_ci_includes_zero=bool(dec.get("ci_includes_zero", False)),
        climate_flags=dec.get("interpretation_flags", []), climate_wording=dec.get("wording"),
        reliability=(s.get("reliability") or {}).get("reliability", "unknown"),
        reliability_note=(s.get("reliability") or {}).get("note"),
        status=(meta.get("analysis") or {}).get("status") if custom else "precomputed")


def list_lakes(st):
    seen, out = set(), []
    for key, (d, _) in lake_dirs(st).items():
        if d in seen:
            continue
        seen.add(d)
        out.append(summary(st, key))
    return out


def full(st, key):
    rec = record(st, key)
    swot = rec["swot"]
    return dict(summary=summary(st, key), meta=rec["meta"], series=rec["series"]["series"], stats=rec["series"].get("stats"),
                reliability=rec["series"].get("reliability"), min_valid=rec["series"].get("min_valid"),
                lst=dict(note=LST_SENSOR_BREAK), climate=rec["climate"], swot=swot,
                volume=(swot or {}).get("volume") if (swot or {}).get("ok") else None,
                unverified=rec["custom"], analysis=rec["meta"].get("analysis"))


def mask_info(st, key, year):
    """(png_path, info) or None. info.coordinates = [TL, TR, BR, BL] lon/lat for a MapLibre image source."""
    r = resolve(st, key)
    if not r:
        return None
    png = os.path.join(r[0], "masks", f"{int(year)}.png")
    gp = os.path.join(r[0], "masks", "grid.json")
    if not (os.path.exists(png) and os.path.exists(gp)):
        return None
    g = _load(gp)
    from pyproj import Transformer
    a, b, c, d_, e, f = g["affine"][:6]
    h, w = g["shape"]
    tr = Transformer.from_crs(g["crs"], 4326, always_xy=True)
    pts = [tr.transform(x, y) for x, y in
           [(c, f), (a * w + c, d_ * w + f), (a * w + b * h + c, d_ * w + e * h + f), (b * h + c, e * h + f)]]
    coords = [[round(x, 5), round(y, 5)] for x, y in pts]
    lons, lats = [p[0] for p in coords], [p[1] for p in coords]
    return png, dict(year=int(year), coordinates=coords, bounds=[min(lons), min(lats), max(lons), max(lats)],
                     shape=[h, w], resolution_m=g.get("resolution_m"),
                     encoding="PNG uint8: 0 no data, 90 land, 255 water (image is in the UTM grid; use `coordinates` "
                              "for the corners, the image is rotated slightly vs lon/lat)")


def mask_json(st, key, year):
    m = mask_info(st, key, year)
    if not m:
        return None
    png, info = m
    with open(png, "rb") as f:
        info["png_data_uri"] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    return info


def compare(st, ids, metric):
    out, missing = {}, []
    for k in ids:
        rec = record(st, k)
        if not rec:
            missing.append(k)
            continue
        s = rec["series"]
        rows = valid_rows(s["series"], s.get("min_valid", 0.8))
        field_ = "area_km2" if metric == "area_pct" else "lst_c"
        if metric == "lst_anomaly":
            rows = [r for r in rows if r.get("lst_c") is not None]
        ref = [r[field_] for r in rows if REF[0] <= r["year"] <= REF[1]]
        if not ref:
            out[k] = dict(name=rec["meta"].get("name"), years=[], values=[], error="no valid 1985-1990 reference years")
            continue
        m = float(np.mean(ref))
        vals = [100 * r[field_] / m if metric == "area_pct" else r[field_] - m for r in rows]
        out[k] = dict(
            name=rec["meta"].get("name"), id=rec["meta"].get("lake_id", k), reference_mean=round(m, 2),
            years=[r["year"] for r in rows], values=[round(v, 2) for v in vals],
            reliability=(s.get("reliability") or {}).get("reliability", "unknown"))
    return out, missing
