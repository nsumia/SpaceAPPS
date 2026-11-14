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
