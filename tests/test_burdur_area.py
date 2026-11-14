import json
import numpy as np
import pandas as pd
import pytest

import burdur_area as ba


def synthetic(n_t=3, size=200, r=60, cloud_frac_scene0=False):
    """Circle lake: water (MNDWI>0, 20 C) in circle radius r px, land (MNDWI<0, 35 C) elsewhere."""
    yy, xx = np.mgrid[:size, :size]
    lake = (yy - size / 2) ** 2 + (xx - size / 2) ** 2 <= r ** 2
    def dn_refl(v): return round((v - ba.OFFSET) / ba.SCALE)
    green = np.where(lake, dn_refl(0.10), dn_refl(0.15))
    swir = np.where(lake, dn_refl(0.02), dn_refl(0.30))
    dn_t = lambda c: round((c + 273.15 - ba.ST_OFFSET) / ba.ST_SCALE)
    st = np.where(lake, dn_t(20.0), dn_t(35.0))
    stack = lambda a: np.stack([a] * n_t).astype("uint16")
    return lake, stack(green), stack(swir), np.zeros((n_t, size, size), "uint16"), stack(st)


def test_known_circle_area_and_lst():
    lake, g, s, qa, st = synthetic()
    res = ba.analyze_arrays(g, s, qa, st)
    expected = lake.sum() * 900 / 1e6
    assert res["area_km2"] == pytest.approx(expected)
    assert res["area_km2"] == pytest.approx(np.pi * 60 ** 2 * 900 / 1e6, rel=0.02)
    assert res["lst_c"] == pytest.approx(20.0, abs=0.05)
    assert res["valid_frac"] == 1.0


def test_scale_offset_constants():
    # DN 20000 -> 0.35 reflectance; DN 45000 -> 20.6 C check of Kelvin scaling
    assert 20000 * ba.SCALE + ba.OFFSET == pytest.approx(0.35)
    assert 45000 * ba.ST_SCALE + ba.ST_OFFSET == pytest.approx(302.8, abs=0.1)


def test_cloud_pixels_masked_in_all_scenes_become_invalid():
    lake, g, s, qa, st = synthetic()
    qa[:, :, :100] = 1 << 3          # cloud flag on left half in every scene
    res = ba.analyze_arrays(g, s, qa, st)
    assert res["valid_frac"] == pytest.approx(0.5, abs=0.01)
    assert res["area_km2"] < lake.sum() * 900 / 1e6 * 0.6


def test_cloud_in_one_scene_is_filled_by_other_scenes():
    lake, g, s, qa, st = synthetic()
    qa[0] = (1 << 3) | (1 << 4)
    res = ba.analyze_arrays(g, s, qa, st)
    assert res["area_km2"] == pytest.approx(lake.sum() * 900 / 1e6)


def test_nodata_zero_ignored():
    lake, g, s, qa, st = synthetic()
    g[:, :50, :] = 0
    res = ba.analyze_arrays(g, s, qa, st)
    assert res["valid_frac"] == pytest.approx(0.75, abs=0.01)


def test_no_lst_if_too_few_pure_water_pixels():
    lake, g, s, qa, st = synthetic(r=8)
    res = ba.analyze_arrays(g, s, qa, st)
    assert np.isnan(res["lst_c"])


def test_platform_config_excludes_l7_l4():
    assert "landsat-7" not in ba.PLATFORMS and "landsat-4" not in ba.PLATFORMS
    assert set(ba.THERMAL_ASSET) == {"landsat-5", "landsat-8", "landsat-9"}
    assert ba.THERMAL_ASSET["landsat-5"] == "lwir" and ba.THERMAL_ASSET["landsat-8"] == "lwir11"


def test_default_bbox_excludes_yarisli():
    from shapely.geometry import Point, box
    assert not box(*ba.DEFAULT_BBOX).contains(Point(29.96, 37.56))


def test_year_with_retries_records_nan_and_error(monkeypatch):
    calls = []
    def boom(*a, **k):
        calls.append(1); raise TimeoutError("net down")
    monkeypatch.setattr(ba, "window_area", boom)
    monkeypatch.setattr(ba.time, "sleep", lambda s: None)
    row = ba.year_with_retries(None, None, None, 1999, 0.0, 40)
    assert len(calls) == ba.RETRIES + 1
    assert np.isnan(row["area_km2"]) and "TimeoutError" in row["error"]


def test_trend_decreasing_and_break_split():
    years = np.arange(1985, 2026)
    rng = np.random.default_rng(0)
    area = 200 - 2.0 * (years - 1985) + rng.normal(0, 1, len(years))
    lst = np.where(years <= 2012, 22.0, 24.0) + rng.normal(0, 0.1, len(years))
    df = pd.DataFrame(dict(year=years, area_km2=area, lst_c=lst, valid_frac=1.0))
    st = ba.compute_stats(df)
    assert st["area"]["trend"] == "decreasing" and st["area"]["p"] < 0.01
    assert st["area"]["sen_slope_per_decade"] == pytest.approx(-20, abs=2)
    assert st["lst_1985_2012"]["last_year"] == 2012 and st["lst_2013_2025"]["first_year"] == 2013


def test_trend_none_when_too_few():
    assert ba.trend([1, 2, 3], [1, 2, 3]) is None
