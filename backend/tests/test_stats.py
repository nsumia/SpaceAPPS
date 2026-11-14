import numpy as np
import pytest

from backend.core import stats as bs


def test_sen_slope_uses_actual_years_with_gap():
    years = np.array([y for y in range(1985, 2026) if y != 2012])
    area = 200 - 2.0 * (years - 1985)                      # exactly -2 km2 per year, 2012 missing
    r = bs.trend(area, years)
    assert r["sen_slope_per_year"] == pytest.approx(-2.0)
    assert r["sen_slope_per_decade"] == pytest.approx(-20.0)
    assert r["year_gaps"] == 1 and r["n"] == 40
    assert bs.sen_line(r, [1985, 2025]) == pytest.approx([200.0, 120.0])
    # the old per-observation slope would be biased: index-based slope over the same data is not -2
    idx_slope = np.polyfit(np.arange(len(years)), area, 1)[0]
    assert abs(idx_slope + 2.0) > 0.01


def test_trend_none_if_few():
    assert bs.trend([1, 2, 3], [1, 2, 3]) is None


def _synth(onset, slope, sigma=1.0, seed=0, n0=1985, n1=2025):
    rng = np.random.default_rng(seed)
    yrs = np.arange(n0, n1 + 1)
    v = 100 + rng.normal(0, sigma, len(yrs)) - slope * np.clip(yrs - onset, 0, None)
    return v, yrs


@pytest.mark.parametrize("onset,seed", [(1998, 0), (2002, 1), (1996, 2), (2005, 3)])
def test_emergence_found_within_3_years_of_true_crossing(onset, seed):
    slope, sigma = 2.0, 1.0
    v, yrs = _synth(onset, slope, sigma, seed)
    r = bs.emergence(v, yrs)
    assert r["emerged"] and r["status"] == "emerged"
    # Sen line of a hockey stick is smoothed; the reference is the full-window mean, so compare with the year where the
    # *fitted* line crosses 2 sigma. The true onset + 2 sigma/slope is the lower bound; allow the +-3 y window around the
    # crossing of the Sen line computed independently here.
    s = bs.trend(v, yrs)
    line = bs.sen_line(s, yrs)
    ref = v[yrs <= 1996]
    expect = int(yrs[np.flatnonzero(-(line - ref.mean()) > 2 * r["sigma"])[0]])
    assert abs(r["year"] - expect) <= 3
    assert r["year"] > 1996


def test_emergence_linear_trend_alternating_noise():
    """v = 50 + 0.1 (y-1985) + (+-1 alternating): sigma ~1, reference 1985-1994 (mean offset 0.45), so the true line is
    2 sigma above the reference mean at 1985 + 4.5 + 20 = 2009.5. Found year must be within 3 years."""
    yrs = np.arange(1985, 2026)
    v = 50 + 0.1 * (yrs - 1985) + np.where(yrs % 2 == 0, 1.0, -1.0)
    r = bs.emergence(v, yrs, ref_len=10)
    assert r["emerged"] and abs(r["year"] - 2009.5) <= 3, r


@pytest.mark.parametrize("seed", range(6))
def test_emergence_random_noise_decreasing(seed):
    """Noise N(0,0.5), slope -0.3/yr: true crossing 1985 + 4.5 + 2*0.5/0.3 = 1992.8 is inside/near the reference end, so
    the first eligible year is 1995 +-3."""
    yrs = np.arange(1985, 2026)
    v = 80 - 0.3 * (yrs - 1985) + np.random.default_rng(seed).normal(0, 0.5, len(yrs))
    r = bs.emergence(v, yrs, ref_len=10)
    assert r["emerged"] and r["direction"] == "decreasing" and 1995 <= r["year"] <= 1998, r


def test_emergence_not_yet_with_years_needed():
    yrs = np.arange(1985, 2026)
    v = 10 + np.where(yrs % 2 == 0, 1.0, -1.0) - 0.01 * (yrs - 1985)   # sigma ~1, trend 0.01/yr
    r = bs.emergence(v, yrs)
    assert not r["emerged"] and r["year"] is None and r["label_tr"] == "Henüz ayırt edilemiyor"
    assert r["years_needed"] > 50


def test_emergence_wrong_direction_slope_has_no_estimate():
    yrs = np.arange(1985, 2026)
    v = np.where(yrs < 1997, 10 + (yrs % 2), 10.5)                  # flat after reference: no distinguishable trend
    r = bs.emergence(v.astype(float), yrs)
    assert r is not None and not r["emerged"]
