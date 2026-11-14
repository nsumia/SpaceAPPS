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
