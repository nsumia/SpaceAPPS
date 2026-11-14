"""NASA POWER helpers (units verified in research/api-assumptions-brief.md: all mm/day; YYYY13 = annual MEAN mm/day).
Water-year totals are built from monthly mm/day x days in month. Evaporation parameter: EVLAND (MERRA-2 land ET, a
proxy, not open-water evaporation). Full P-E decomposition is Stage 3."""
import calendar
from datetime import date

import pandas as pd
import requests

POWER = "https://power.larc.nasa.gov/api/temporal"
TIMEOUT = 60
FILL = -999.0
PARAMS = ("PRECTOTCORR", "EVLAND")


def power(kind, lon, lat, start, end, params=PARAMS):
    """Raw `properties.parameter` dict {param: {key: value}} (mm/day). start/end: YYYYMMDD (daily) or YYYY (monthly)."""
    r = requests.get(f"{POWER}/{kind}/point", timeout=TIMEOUT, params=dict(
        parameters=",".join(params), community="AG", longitude=lon, latitude=lat, start=start, end=end, format="JSON"))
    r.raise_for_status()
    return r.json()["properties"]["parameter"]


def monthly_series(d):
    """{YYYYMM: mm/day} -> pandas Series (month start index), dropping the YYYY13 annual-mean key and fill values."""
    s = pd.Series({k: v for k, v in d.items() if not k.endswith("13") and v is not None and v > FILL + 1})
    s.index = pd.to_datetime(s.index, format="%Y%m")
    return s.sort_index()


def monthly_mm(d):
    """Monthly totals in mm (mm/day x days in month)."""
    s = monthly_series(d)
    return s * s.index.days_in_month


def water_year(ts, south=False):
    """Water-year label for each timestamp: Oct-Sep (north, labelled by the ending year) or Apr-Mar (south)."""
    start_month = 4 if south else 10          # label = calendar year in which the water year ends
    return [t.year + (1 if t.month >= start_month else 0) for t in ts]


def water_year_totals(d, south=False):
    """Complete water years only (12 months), mm per water year."""
    m = monthly_mm(d)
    wy = pd.Series(water_year(m.index, south), index=m.index)
    g = m.groupby(wy)
    return g.sum()[g.count() == 12]


def water_year_start(today=None, south=False):
    today = today or date.today()
    m = 4 if south else 10
    return date(today.year if today.month >= m else today.year - 1, m, 1)


# ---------------------------------------------------------------- Stage 3: P-E decomposition
import hashlib
import json
import os

import numpy as np

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "power_cache"))
LABEL_E = "EVLAND (MERRA-2 land evapotranspiration, mm/day) is a land-surface proxy, NOT open-water evaporation"
NOTE = "The unexplained part is a sign, not proof, of human impact (irrigation/withdrawal, model error and land-use change all end up in it)."
REF_YEARS = (1985, 1999)


def n_points(basin_km2):
    """4-9 points, scaled with sqrt(basin area): 5,800 km2 -> 6, 17,000 km2 -> 9."""
    return int(np.clip(round(np.sqrt(basin_km2) / 12.0), 4, 9))


def basin_points(poly_ll, n, grid=40):
    """n spread-out points inside the basin polygon (lon, lat): farthest-point sampling on a regular candidate grid,
    starting from the representative point. Deterministic."""
    from shapely import contains_xy
    x0, y0, x1, y1 = poly_ll.bounds
    gx, gy = np.meshgrid(np.linspace(x0, x1, grid), np.linspace(y0, y1, grid))
    gx, gy = gx.ravel(), gy.ravel()
    m = contains_xy(poly_ll, gx, gy)
    cand = np.c_[gx[m], gy[m]]
    rp = poly_ll.representative_point()
    pts = [(rp.x, rp.y)]
    if len(cand) == 0:
        return pts
    while len(pts) < min(n, len(cand)):
        d = np.min(np.hypot(*(cand[:, None, :] - np.array(pts)[None]).transpose(2, 0, 1)), axis=1)
        pts.append(tuple(cand[int(d.argmax())]))
    return [(round(float(a), 3), round(float(b), 3)) for a, b in pts]



def fetch_point(lon, lat, start=1981, end=None, cache_dir=None, fetcher=None):
    """Monthly POWER JSON for one point, cached on disk (reruns are offline). `fetcher` is injectable for tests."""
    end = end or date.today().year
    base = cache_dir or CACHE_DIR
    path = os.path.join(base, f"monthly_{lon:.3f}_{lat:.3f}_{start}_{end}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    d = (fetcher or power)("monthly", lon, lat, start, end)
    os.makedirs(base, exist_ok=True)
    with open(path, "w") as f:
        json.dump(d, f)
    return d


def pe_water_years(point_dicts, south=False):
    """Mean over points of water-year P - E (mm). Returns DataFrame[P, E, PE] indexed by water year (complete years only;
    a year is dropped if any point lacks a complete water year of both parameters)."""
    P = pd.concat([water_year_totals(d["PRECTOTCORR"], south) for d in point_dicts], axis=1).dropna()
    E = pd.concat([water_year_totals(d["EVLAND"], south) for d in point_dicts], axis=1).dropna()
    idx = P.index.intersection(E.index)
    out = pd.DataFrame({"P": P.loc[idx].mean(axis=1), "E": E.loc[idx].mean(axis=1)})
    out["PE"] = out.P - out.E
    return out


def _pairs(years, area, pe):
    """Consecutive observed years -> (y_prev, y, dA, n_years, sum PE over water years y_prev+1..y). A gap year (2012) gives
    one pair spanning two water years. Pairs with unavailable PE are dropped."""
    rows = []
    ys = list(years)
    for a, b in zip(ys[:-1], ys[1:]):
        wys = range(a + 1, b + 1)
        if all(w in pe.index for w in wys):
            rows.append((a, b, area[b] - area[a], b - a, float(sum(pe[w] for w in wys))))
    return pd.DataFrame(rows, columns=["y0", "y1", "dA", "n", "pe"])


def _fit(ref, intercept=True):
    """dA = a*n + b*PE (the offset accumulates with the number of years spanned); intercept=False forces a = 0."""
    if not intercept:
        b = float(np.sum(ref.pe.values * ref.dA.values) / np.sum(ref.pe.values ** 2))
        return np.array([0.0, b])
    X = np.c_[ref.n.values, ref.pe.values]
    coef, *_ = np.linalg.lstsq(X, ref.dA.values, rcond=None)
    return coef


def decompose(years, area, pe, ref=REF_YEARS, n_boot=2000, seed=0, ci=0.90, intercept=True):
    """Regress annual area change on P-E in the reference period, predict later years, and compare cumulative losses.

    years/area: observed series (valid years only). pe: Series water-year P-E (mm). Pair (y_prev, y) uses the water years
    y_prev+1..y (water year labelled by the year it ends; north: Oct-Sep, area is Aug-Sep of that year).
    Cumulative loss is measured from the last observed year <= ref[1] (the model baseline), positive = loss.
    explained share = predicted cumulative loss / observed cumulative loss (None if observed loss <= 0).
    Bootstrap: case resampling of reference pairs (n_boot), 90 % CI percentiles of share and of unexplained loss."""
    years = [int(y) for y in years]
    area = pd.Series(np.asarray(area, float), index=years)
    pe = pd.Series(pe)
    pr = _pairs(years, area, pe)
    refp = pr[(pr.y0 >= ref[0]) & (pr.y1 <= ref[1])]
    post = pr[pr.y0 >= (refp.y1.max() if len(refp) else ref[1])]
    if len(refp) < 8 or len(post) < 3:
        return dict(ok=False, reason=f"too few pairs (reference {len(refp)}, later {len(post)})")
    coef = _fit(refp, intercept)
    pred = coef[0] * post.n.values + coef[1] * post.pe.values
    cum_pred_loss = -np.cumsum(pred)
    cum_obs_loss = -np.cumsum(post.dA.values)
    unexpl = cum_obs_loss - cum_pred_loss
    resid = refp.dA.values - np.c_[refp.n.values, refp.pe.values] @ coef
    rng = np.random.default_rng(seed)
    shares, unx, rates = [], [], []
    for _ in range(n_boot):
        s = refp.iloc[rng.integers(0, len(refp), len(refp))]
        try:
            c = _fit(s, intercept)
        except np.linalg.LinAlgError:
            continue
        p = -np.sum(c[0] * post.n.values + c[1] * post.pe.values)
        unx.append(cum_obs_loss[-1] - p)
        shares.append(p / cum_obs_loss[-1] if cum_obs_loss[-1] > 0 else np.nan)
    lo, hi = (1 - ci) / 2 * 100, (1 + ci) / 2 * 100
    n_years = int(post.n.sum())
    share = float(cum_pred_loss[-1] / cum_obs_loss[-1]) if cum_obs_loss[-1] > 0 else None
    sh = np.array(shares)
    return dict(
        ok=True, intercept=intercept, ref_corr_dA_PE=float(np.corrcoef(refp.dA, refp.pe)[0, 1]), reference=[int(refp.y0.min()), int(refp.y1.max())], n_ref_pairs=int(len(refp)),
        coef_offset_km2_per_year=float(coef[0]), coef_km2_per_mm_PE=float(coef[1]),
        ref_r2=float(1 - resid.var() / refp.dA.var()) if refp.dA.var() > 0 else None,
        base_year=int(post.y0.iloc[0]), last_year=int(post.y1.iloc[-1]), n_years=n_years,
        years=[int(v) for v in post.y1], cum_observed_loss_km2=[float(v) for v in cum_obs_loss],
        cum_predicted_loss_km2=[float(v) for v in cum_pred_loss], cum_unexplained_km2=[float(v) for v in unexpl],
        observed_loss_km2=float(cum_obs_loss[-1]), predicted_loss_km2=float(cum_pred_loss[-1]),
        unexplained_loss_km2=float(unexpl[-1]), unexplained_km2_per_year=float(unexpl[-1] / n_years),
        explained_share=share,
        explained_share_ci90=None if np.isnan(sh).all() else [float(np.nanpercentile(sh, lo)), float(np.nanpercentile(sh, hi))],
        unexplained_ci90_km2=[float(np.percentile(unx, lo)), float(np.percentile(unx, hi))], n_boot=len(unx))


def run(alias, force_refetch=False, fetcher=None, cache_dir=None, log=print):
    """Build data/lakes/<alias>/climate.json from series.json + basin.geojson (POWER monthly points, cached)."""
    from shapely.geometry import shape
    from backend.core import geo
    from backend.core.lakes import lake_dir
    d = lake_dir(alias)
    with open(os.path.join(d, "series.json")) as f:
        ser = json.load(f)
    with open(os.path.join(d, "basin.geojson")) as f:
        feat = json.load(f)
    with open(os.path.join(d, "meta.json")) as f:
        meta = json.load(f)
    basin = shape(feat["geometry"])
    basin_km2 = geo.to_utm(basin, meta["utm_epsg"]).area / 1e6
    n = n_points(basin_km2)
    pts = basin_points(basin, n)
    south = basin.centroid.y < 0
    pdicts = []
    for lon, lat in pts:
        pdicts.append(fetch_point(lon, lat, 1981, None, cache_dir, fetcher))
    pe = pe_water_years(pdicts, south)
    df = pd.DataFrame(ser["series"])
    okm = (df.valid_frac >= ser["min_valid"]) & df.area_km2.notna()
    dec = decompose(df.year[okm].values, df.area_km2[okm].values, pe.PE)
    dec0 = decompose(df.year[okm].values, df.area_km2[okm].values, pe.PE, intercept=False)
    if dec["ok"]:
        sh = dec["explained_share"]
        dec["interpretation_flags"] = [f for f, c in (
            ("weak_reference_skill: |corr(dA, P-E)| < 0.3 in 1985-1999", abs(dec["ref_corr_dA_PE"]) < 0.3),
            ("share_outside_0_1: predicted loss is larger than observed or has the opposite sign", sh is None or not 0 <= sh <= 1),
            ("small_observed_loss: < 3 % of 1999 area is not separable from classification noise",
             dec["observed_loss_km2"] < 0.03 * float(df.area_km2[okm][df.year[okm] == dec["base_year"]].iloc[0]))) if c]
    out = dict(lake=meta["name"], alias=alias, basin_km2=round(basin_km2, 1), basin_source=feat["properties"].get("source"),
               points=[dict(lon=a, lat=b) for a, b in pts], n_points=len(pts), water_year="Apr-Mar" if south else "Oct-Sep",
               params=dict(P="PRECTOTCORR (mm/day x days in month)", E="EVLAND"), evaporation_label=LABEL_E,
               power_grid_note="MERRA-2 grid ~0.5 x 0.625 deg: several points can share one cell; model data, not stations",
               water_year_series=[dict(wy=int(i), P_mm=float(r.P), E_mm=float(r.E), PE_mm=float(r.PE)) for i, r in pe.iterrows()],
               model="dA(y_prev->y) = a*n_years + b*sum(P-E); fitted on reference pairs 1985-1999; unexplained = observed - predicted cumulative loss after 1999",
               decomposition=dec, decomposition_no_intercept=dec0,
               sensitivity_note="decomposition = regression with intercept (the reference-period drift continues as background, so 'unexplained' = change relative to 1985-1999 behaviour); decomposition_no_intercept = P-E only (reference drift counts as unexplained)",
               note=NOTE, generated=pd.Timestamp.now("UTC").isoformat(timespec="seconds"))
    with open(os.path.join(d, "climate.json"), "w") as f:
        json.dump(out, f, indent=1)
    log(f"{alias}: {n} points, basin {basin_km2:.0f} km2, wy {pe.index.min()}-{pe.index.max()}, "
        + (f"share={dec['explained_share']:.2f} ci={dec['explained_share_ci90']} no-intercept share={dec0.get('explained_share')} corr={dec['ref_corr_dA_PE']:.2f}" if dec["ok"] else f"decomposition failed: {dec['reason']}"))
    return out


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        run(a)
