import json

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from backend.core import climate as cl


def _power_json(p_by_year, e_by_year, bad=()):
    """Monthly POWER-like dict. p/e are mm/day constants per calendar year; (year, month) in `bad` -> -999."""
    P, E = {}, {}
    for y in p_by_year:
        for m in range(1, 13):
            k = f"{y}{m:02d}"
            P[k] = -999.0 if (y, m) in bad else p_by_year[y]
            E[k] = e_by_year[y]
        P[f"{y}13"] = 1.0
        E[f"{y}13"] = 1.0
    return dict(PRECTOTCORR=P, EVLAND=E)


def test_water_year_totals_with_fill_rows_dropped():
    d = _power_json({y: 2.0 for y in range(1990, 1994)}, {y: 1.0 for y in range(1990, 1994)}, bad={(1991, 3)})
    t = cl.water_year_totals(d["PRECTOTCORR"])
    assert 1991 not in t.index and 1992 in t.index          # wy 1991 = Oct 1990 - Sep 1991 includes the -999 month
    assert 1990 not in t.index                                # Oct-Dec 1989 missing -> incomplete
    assert t[1992] == pytest.approx(2.0 * 366)               # Oct 1991 - Sep 1992 incl. Feb 1992 (leap)
    assert t[1993] == pytest.approx(2.0 * 365)


def test_pe_water_years_drops_year_with_fill_in_any_point():
    a = _power_json({y: 3.0 for y in range(1990, 1995)}, {y: 1.0 for y in range(1990, 1995)})
    b = _power_json({y: 1.0 for y in range(1990, 1995)}, {y: 1.0 for y in range(1990, 1995)}, bad={(1993, 5)})
    pe = cl.pe_water_years([a, b])
    assert 1993 not in pe.index and 1994 in pe.index and 1992 in pe.index
    assert pe.PE[1992] == pytest.approx(((3.0 - 1.0) + (1.0 - 1.0)) / 2 * 366)


def test_fetch_point_caches_and_reruns_offline(tmp_path):
    calls = []

    def fake(kind, lon, lat, s, e):
        calls.append((lon, lat))
        return {"PRECTOTCORR": {"198101": 1.0}, "EVLAND": {"198101": 1.0}}
    a = cl.fetch_point(30.1, 37.7, 1981, 2025, str(tmp_path), fake)
    b = cl.fetch_point(30.1, 37.7, 1981, 2025, str(tmp_path), lambda *x: 1 / 0)    # must not call the network
    assert a == b and len(calls) == 1


def test_n_points_scales_and_basin_points_inside():
    assert cl.n_points(100) == 4 and cl.n_points(5800) == 6 and cl.n_points(17000) == 9 and cl.n_points(1e6) == 9
    poly = box(30, 37, 31, 38)
    pts = cl.basin_points(poly, 6)
    assert len(pts) == 6 and len(set(pts)) == 6
    assert all(poly.contains(__import__("shapely.geometry", fromlist=["Point"]).Point(p)) for p in pts)


def _synthetic(withdrawal, noise=2.0, seed=0, gap=True):
    rng = np.random.default_rng(seed)
    wys = np.arange(1982, 2026)
    pe = pd.Series(rng.normal(0, 150, len(wys)), index=wys)       # mm per water year
    years = [y for y in range(1985, 2026) if not (gap and y == 2012)]
    area = {1985: 200.0}
    k = 0.05                                                       # km2 per mm of P-E
    for y in range(1986, 2026):
        d = k * pe[y] + rng.normal(0, noise * 0.1) - (withdrawal if y > 1999 else 0.0)
        area[y] = area[y - 1] + d
    return years, [area[y] for y in years], pe


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_decompose_recovers_constant_withdrawal_within_20_percent(seed):
    W = 1.5
    years, area, pe = _synthetic(W, seed=seed)
    r = cl.decompose(years, area, pe)
    assert r["ok"]
    assert r["unexplained_km2_per_year"] == pytest.approx(W, rel=0.20), r["unexplained_km2_per_year"]
    lo, hi = r["unexplained_ci90_km2"]
    assert lo < r["unexplained_loss_km2"] < hi
    assert 0 <= r["n_boot"] and r["last_year"] == 2025


def test_decompose_pure_climate_has_near_zero_unexplained():
    years, area, pe = _synthetic(0.0, seed=3)
    r = cl.decompose(years, area, pe)
    assert abs(r["unexplained_km2_per_year"]) < 0.3


def test_decompose_too_short_returns_not_ok():
    r = cl.decompose([1985, 1986, 1987], [1, 2, 3], pd.Series({1986: 0.0, 1987: 0.0}))
    assert r["ok"] is False


def test_decompose_gap_year_pair_spans_two_water_years():
    years, area, pe = _synthetic(1.0, gap=True)
    pr = cl._pairs(years, pd.Series(area, index=years), pe)
    row = pr[pr.y1 == 2013].iloc[0]
    assert row.y0 == 2011 and row.n == 2 and row.pe == pytest.approx(pe[2012] + pe[2013])
