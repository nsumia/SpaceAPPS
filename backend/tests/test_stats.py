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
