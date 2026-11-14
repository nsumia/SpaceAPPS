"""Trend statistics. Stage 3 adds emergence year here."""
import numpy as np


def trend(values, years):
    """Hamed-Rao modified Mann-Kendall (p, direction) + Sen slope per YEAR computed on the actual years.
    The MK statistic uses only the ranking, so a missing year does not bias it; the Hamed-Rao autocorrelation
    correction assumes equal spacing (a single gap such as 2012 is a small deviation, not corrected).
    The slope is scipy theilslopes(values, years), so a gap does not turn 'per observation' into 'per year'."""
    import pymannkendall as mk
    from scipy.stats import theilslopes
    v = np.asarray(values, float)
    y = np.asarray(years, float)
    if len(v) < 10:
        return None
    r = mk.hamed_rao_modification_test(v)
    slope, intercept, _, _ = theilslopes(v, y)
    gaps = int(np.sum(np.diff(y) > 1))
    return dict(n=int(len(v)), trend=r.trend, p=float(r.p), sen_slope_per_year=float(slope),
                sen_slope_per_decade=float(slope * 10), intercept=float(intercept + slope * y[0]),
                intercept_year=int(y[0]), year_gaps=gaps,
                first_year=int(y[0]), last_year=int(y[-1]))


def sen_line(s, years):
    """Sen line values at `years` (intercept is anchored at intercept_year, i.e. value = intercept + slope*(year - y0))."""
    y = np.asarray(years, float)
    return s["intercept"] + s["sen_slope_per_year"] * (y - s["intercept_year"])


def compute_stats(df, min_valid=0.8):
    d = df[(df.valid_frac >= min_valid) & df.area_km2.notna()]
    out = {"area": trend(d.area_km2.values, d.year.values)}
    t = d[d.lst_c.notna()]
    out["lst_all"] = trend(t.lst_c.values, t.year.values)
    # L5 -> L8 break (L8 launched 2013; no L5 data after 2011/12): trend before / after separately
    for name, sub in (("lst_1985_2012", t[t.year <= 2012]), ("lst_2013_2025", t[t.year >= 2013])):
        out[name] = trend(sub.lst_c.values, sub.year.values)
    return out
