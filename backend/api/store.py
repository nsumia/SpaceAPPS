"""Read access to lake records (precomputed data/lakes/<alias>/ and on-demand data/custom/<id>/), summaries, masks,
compare. Pure functions over a Settings object so tests can point them at temp dirs."""
import base64
import json
import math
import os
from dataclasses import dataclass, field

import numpy as np

from backend.core import jsonsafe
from backend.core.lakes import ROOT

# Validation (VALIDATION.md): Turkish lakes are validated (Burdur quantitatively against Sabuncu 2020, the others by the
# Stage 2-3 checks listed there). Reference lakes get the badge only when our trend direction matches the general
# literature direction below. Directions are GENERAL (decline / increase / stable / mixed), see VALIDATION.md for the
# sources actually checked; "mixed" and "stable" lakes never get the badge.
LITERATURE = {
    "urmia": "decline", "aral_south": "decline", "aral_north": "increase", "great_salt_lake": "decline", "mead": "decline",
    "chad": "mixed", "poopo": "decline", "titicaca": "stable", "balkhash": "mixed", "sevan": "mixed",
    "tuz": "decline", "qinghai": "increase", "dead_sea": "decline",
}
LIT_UNVERIFIED = {"titicaca", "balkhash"}      # direction not confirmed by any source seen (VALIDATION.md)
_DIRS = {"decreasing": "decline", "increasing": "increase", "no trend": "stable"}
LST_SENSOR_BREAK = ("Landsat 5 -> 8 step of about +3 C at 2012/13 (Stage 1): warming_c_per_decade uses Landsat 5 only "
                    "(1985-2012); the pooled slope (warming_pooled_c_per_decade) contains the sensor break and overstates warming.")
REF = (1985, 1990)
SAMPLE_PREFIX = "sample-"


@dataclass
class Settings:
    lakes_dir: str = os.path.join(ROOT, "data", "lakes")
    custom_dir: str = os.path.join(ROOT, "data", "custom")
    cache_dir: str = os.path.join(ROOT, "data", "live_cache")
    demo_dir: str = os.path.join(ROOT, "data", "demo_cache")     # committed snapshot: seed when live_cache has no entry
    jobs_db: str = os.path.join(ROOT, "data", "jobs.sqlite")
    index_path: str = os.path.join(ROOT, "data", "index", "lakes.geojson")
    live_ttl_s: int = int(os.environ.get("LLD_LIVE_TTL_S", 3 * 3600))      # e2e sets 1 to force the stale path
    sample_delay_s: float = 0.12                  # pause per replayed year of a pre-computed sample job
    start_worker: bool = True
    dist_dir: str = ""
    _cache: dict = field(default_factory=dict, repr=False)


def _load(path):
    with open(path) as f:
        return jsonsafe.sanitize(json.load(f))          # older files may hold NaN/Infinity literals: read them as null


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


def _finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def valid_rows(series, min_valid):
    return [r for r in series if _finite(r.get("area_km2")) and (r.get("valid_frac") or 0) >= min_valid]


def ref_rows(rows):
    """Baseline rows: 1985-1990 valid years; if there are none (late-starting or sparsely covered lakes) the first 3 valid years."""
    ref = [r for r in rows if REF[0] <= r["year"] <= REF[1]]
    return (ref, [REF[0], REF[1]]) if ref else (rows[:3], [rows[0]["year"], rows[:3][-1]["year"]] if rows else [REF[0], REF[1]])


def centre(rec):
    p = os.path.join(rec["dir"], "masks", "lake_polygon.geojson")
    if os.path.exists(p):
        from shapely.geometry import shape
        c = shape(_load(p)["geometry"]).centroid
        return [round(c.x, 4), round(c.y, 4)]
    return rec["meta"].get("seed")


def latest_area(st, key):
    """(area_km2, year) of the latest valid year, or (None, None). The lake itself, not the buffered index polygon."""
    rec = record(st, key)
    rows = valid_rows(rec["series"]["series"], rec["series"].get("min_valid", 0.8)) if rec else []
    return (round(rows[-1]["area_km2"], 1), rows[-1]["year"]) if rows else (None, None)


def _cadence(meta):
    n = meta.get("cadence_years")
    if not n:
        return meta.get("cadence_note")
    ys = meta.get("years_analysed") or [0, 0]
    ords = {1: "every year", 2: "every 2nd year", 3: "every 3rd year"}
    return f"{ords.get(n, f'every {n}th year')}, {ys[0]}-{ys[-1]} (chosen to fit the time budget; unobserved years are not interpolated)" if n > 1 else \
        f"every year, {ys[0]}-{ys[-1]}" + (" (series starts late: no earlier Landsat 5 scenes in the archive)" if ys[0] > 1985 else "")


def _r(d, k, n):
    """round(d[k], n) or None when the stat block or the value is missing (null after NaN sanitising)."""
    v = (d or {}).get(k)
    return None if v is None else round(v, n)


def alias_of(meta, key):
    return meta.get("alias") or key


def summary(st, key):
    rec = record(st, key)
    s, meta, stats = rec["series"], rec["meta"], rec["series"].get("stats") or {}
    rows = valid_rows(s["series"], s.get("min_valid", 0.8))
    refr, ref_years = ref_rows(rows)
    ref = [r["area_km2"] for r in refr]
    ref_mean = float(np.mean(ref)) if ref else None
    last = [r["area_km2"] for r in rows[-3:]]
    area = stats.get("area")
    loss = trend = None
    if ref_mean and last:
        loss = round(100 * (ref_mean - float(np.mean(last))) / ref_mean, 1)
        if area and area.get("sen_slope_per_decade") is not None:
            trend = round(100 * area["sen_slope_per_decade"] / ref_mean, 2)
    em = stats.get("area_emergence") or {}
    lit = LITERATURE.get(alias_of(meta, key))
    ours = _DIRS.get(area["trend"]) if area else None
    if lit is None or ours is None or lit == "mixed":
        agreement = "not_tested"
    elif ours == "stable" and lit != "stable":
        agreement = "inconclusive"          # our trend is not significant: neither agrees nor conflicts
    elif ours == lit:
        agreement = "agrees"
    else:
        agreement = "unverified_expectation" if alias_of(meta, key) in LIT_UNVERIFIED else "conflict"
    lit_agrees = True if agreement == "agrees" else (False if agreement in ("conflict",) else None)
    l5 = stats.get("lst_1985_2012")
    pooled = stats.get("lst_all")
    dec = ((rec["climate"] or {}).get("decomposition")) or {}
    custom = rec["custom"]
    fc = forecast(st, key)
    fm = (fc.get("milestones") or [None])[-1] if fc.get("ok") and fc.get("interpretable") else None
    alias = meta.get("alias")
    reliability = (s.get("reliability") or {}).get("reliability", "unknown")
    group = meta.get("group") or ("custom" if custom else ("turkey" if meta.get("country") == "TR" else "reference"))
    return dict(
        why_selected=meta.get("why_selected"), mndwi_note=meta.get("mndwi_note"), resolution_m=meta.get("resolution_m"),
        cadence_note=_cadence(meta), cadence_years=meta.get("cadence_years"), years_analysed=meta.get("years_analysed"),
        window=meta.get("window"), literature_direction=lit, our_direction=ours, literature_agrees=lit_agrees, literature_agreement=agreement,
        ref_years=ref_years, recent_years=[r["year"] for r in rows[-3:]],
        recent_mean_km2=round(float(np.mean(last)), 1) if last else None,
        id=meta.get("lake_id", key), alias=alias, name=meta.get("name") or s.get("lake"), country=meta.get("country"),
        centre=centre(rec), group=group, validated=bool(not custom and (group == "turkey" or lit_agrees is True) and reliability != "low"),
        validation_basis=("quantitative vs Sabuncu 2020 + direction" if alias == "burdur" else
                          "direction checked against literature/Stage 2-3 checks" if group == "turkey" else
                          "trend direction matches the general literature direction" if lit_agrees else None), unverified=bool(custom),
        years=meta.get("years"), latest_area_km2=latest_area(st, key)[0], latest_area_year=latest_area(st, key)[1],
        ref_mean_km2=None if ref_mean is None else round(ref_mean, 1),
        total_loss_pct=loss, total_loss_basis=f"mean {ref_years[0]}-{ref_years[1]} vs mean of last 3 valid years",
        trend_pct_per_decade=trend, trend_p=None if not area or area.get("p") is None else round(area["p"], 6), trend_direction=area and area["trend"],
        emergence_year=em.get("year"), emergence_status=em.get("status"),
        emergence_censored_at_ref_end=bool(em.get("censored_at_ref_end")), emergence_note=em.get("censored_note"),
        warming_c_per_decade=_r(l5, "sen_slope_per_decade", 2),
        warming_basis="Landsat 5 only, 1985-2012" if l5 else None,
        warming_pooled_c_per_decade=_r(pooled, "sen_slope_per_decade", 2),
        warming_sensor_break_caveat=LST_SENSOR_BREAK,
        climate_explained_share=dec.get("explained_share") if dec.get("ok") else None,
        climate_explained_ci90=dec.get("explained_share_ci90") if dec.get("ok") else None,
        climate_interpretable=bool(dec.get("interpretable", False)) if dec.get("ok") else False,
        climate_ci_includes_zero=bool(dec.get("ci_includes_zero", False)),
        climate_flags=dec.get("interpretation_flags", []), climate_wording=dec.get("wording"),
        reliability=(s.get("reliability") or {}).get("reliability", "unknown"),
        reliability_note=(s.get("reliability") or {}).get("note"),
        forecast_year=fm and fm["year"], forecast_km2=fm and fm["median_km2"], forecast_pct_of_ref=fm and fm["median_pct_of_ref"],
        status=(meta.get("analysis") or {}).get("status") if custom else "precomputed")


def forecast(st, key, horizon_year=None):
    """Area forecast (backend/core/stats.py), computed on read from the stored series and cached per series file
    version, so existing records need no re-precompute. Deterministic (fixed seed)."""
    from backend.core import stats as fc
    rec = record(st, key)
    horizon = int(horizon_year or fc.HORIZON_YEAR)
    sp = os.path.join(rec["dir"], "series.json")
    ck = ("forecast", sp, os.path.getmtime(sp), horizon)
    if ck not in st._cache:
        s = rec["series"]
        mv = s.get("min_valid", 0.8)
        refr, _ = ref_rows(valid_rows(s["series"], mv))
        out = fc.forecast_area(s["series"], mv, (s.get("reliability") or {}).get("reliability", "unknown"),
                               ref_mean=float(np.mean([r["area_km2"] for r in refr])) if refr else None, horizon_year=horizon)
        if (rec["meta"].get("analysis") or {}).get("status") not in (None, "done"):
            out = dict(out, preliminary=True)          # on-demand job still running: years are still arriving
        st._cache[ck] = out
    return st._cache[ck]


def list_lakes(st):
    seen, out = set(), []
    for key, (d, _) in lake_dirs(st).items():
        if d in seen or os.path.basename(d).startswith(SAMPLE_PREFIX):      # replayed samples are not map lakes
            continue
        seen.add(d)
        out.append(summary(st, key))
    return out


def full(st, key):
    rec = record(st, key)
    swot = rec["swot"]
    return dict(summary=summary(st, key), meta=rec["meta"], series=rec["series"]["series"], stats=rec["series"].get("stats"),
                reliability=rec["series"].get("reliability"), min_valid=rec["series"].get("min_valid"),
                lst=dict(note=LST_SENSOR_BREAK), climate=rec["climate"], swot=swot, forecast=forecast(st, key),
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
        refr, ref_years = ref_rows(rows)
        ref = [r[field_] for r in refr]
        if not ref:
            out[k] = dict(name=rec["meta"].get("name"), years=[], values=[], error="no valid 1985-1990 reference years")
            continue
        m = float(np.mean(ref))
        vals = [100 * r[field_] / m if metric == "area_pct" else r[field_] - m for r in rows]
        out[k] = dict(
            name=rec["meta"].get("name"), id=rec["meta"].get("lake_id", k), reference_mean=round(m, 2), reference_years=ref_years,
            years=[r["year"] for r in rows], values=[round(v, 2) for v in vals],
            reliability=(s.get("reliability") or {}).get("reliability", "unknown"))
    return out, missing
