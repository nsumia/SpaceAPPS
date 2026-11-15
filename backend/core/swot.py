"""SWOT Hydrocron (PriorLake). PLD id must come from the PLD file (no lookup-by-location endpoint). Fill rows:
time_str == 'no_data', wse/area_total == -999999999999.0. Volume/area-level curve is Stage 3."""
import io
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

HYDROCRON = "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries"
TIMEOUT = 60
FILL_LIMIT = -1e6


def clean_hydrocron_csv(text):
    """Parse the CSV and drop fill rows. Returns DataFrame[t (UTC), wse, area_total] sorted by time."""
    df = pd.read_csv(io.StringIO(text))
    df = df[(df.time_str != "no_data") & (df.wse > FILL_LIMIT) & (df.area_total > FILL_LIMIT)].copy()
    df["t"] = pd.to_datetime(df.time_str, utc=True)
    return df.sort_values("t").reset_index(drop=True)


def fetch(pld_id, start, end, timeout=TIMEOUT):
    r = requests.get(HYDROCRON, timeout=timeout, headers={"Accept": "text/csv"}, params=dict(
        feature="PriorLake", feature_id=pld_id, start_time=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end_time=end.strftime("%Y-%m-%dT%H:%M:%SZ"), fields="lake_id,time_str,wse,area_total"))
    r.raise_for_status()
    return clean_hydrocron_csv(r.text)


def recent(pld_id, days=500):
    end = datetime.now(timezone.utc)
    return fetch(pld_id, end - timedelta(days=days), end)


# ---------------------------------------------------------------- Stage 3: volume from area-level curve
import json
import os

import numpy as np

from backend.core import jsonsafe

REASON_NO_PLD = ("No SWOT Prior Lake Database (PLD) id for this lake: Hydrocron has no lookup-by-location endpoint and the PLD "
                 "file (PO.DAAC SWOT_PRIOR_LAKE_DATABASE) needs an Earthdata login that this pipeline does not use. "
                 "Set pld_id in backend/core/lakes.py to enable; nothing is estimated or faked.")


def area_level_fit(area_km2, wse_m, min_n=8):
    """Linear wse = h0 + s*area fit over SWOT observations (area in km2, wse in m). Returns dict or None."""
    a, h = np.asarray(area_km2, float), np.asarray(wse_m, float)
    ok = np.isfinite(a) & np.isfinite(h)
    a, h = a[ok], h[ok]
    if len(a) < min_n or np.ptp(a) <= 0:
        return None
    s, h0 = np.polyfit(a, h, 1)
    r2 = 1 - np.sum((h - (h0 + s * a)) ** 2) / np.sum((h - h.mean()) ** 2)
    return dict(h0=float(h0), m_per_km2=float(s), r2=float(r2), n=int(len(a)), area_range=[float(a.min()), float(a.max())])


def volume_change(years, area_km2, fit):
    """dV = integral A dh with h = h0 + s*A  ->  V(A) - V(A_ref) = s*(A^2 - A_ref^2)/2 (km2*m = 1e-3 km3), relative to the
    first year. Years whose area lies outside the SWOT-observed area range are flagged extrapolated (outer valuation)."""
    a = np.asarray(area_km2, float)
    s = fit["m_per_km2"]
    v = s * (a ** 2 - a[0] ** 2) / 2 * 1e-3
    lo, hi = fit["area_range"]
    return [dict(year=int(y), area_km2=float(x), dV_km3=float(d), extrapolated=bool(x < lo or x > hi))
            for y, x, d in zip(years, a, v)]


def run(alias, out_path=None):
    """Write swot.json for a lake: ok=false with a reason unless a PLD id is configured and data was retrieved."""
    from backend.core.lakes import LAKES, lake_dir
    pld = LAKES[alias].get("pld_id")
    out = dict(alias=alias, ok=False, pld_id=pld, reason=REASON_NO_PLD) if not pld else None
    if out is None:
        try:
            df = recent(pld, days=1200)
            fit = area_level_fit(df.area_total, df.wse)
            if fit is None:
                out = dict(alias=alias, ok=False, pld_id=pld, reason=f"too few valid SWOT observations ({len(df)})")
            else:
                with open(os.path.join(lake_dir(alias), "series.json")) as f:
                    ser = json.load(f)["series"]
                ser = [r for r in ser if r.get("area_km2") is not None]
                out = dict(alias=alias, ok=True, pld_id=pld, fit=fit, n_obs=int(len(df)),
                           volume=volume_change([r["year"] for r in ser], [r["area_km2"] for r in ser], fit))
        except Exception as e:  # noqa: BLE001
            out = dict(alias=alias, ok=False, pld_id=pld, reason=f"{type(e).__name__}: {e}"[:300])
    with open(out_path or os.path.join(lake_dir(alias), "swot.json"), "w") as f:
        jsonsafe.dump(out, f, indent=1)
    return out
