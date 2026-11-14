"""Trend statistics and emergence year."""
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


def emergence(values, years, ref_len=12, k=2.0):
    """Year in which the Sen trend line permanently leaves the natural variability of the reference period.

    Reference period = first `ref_len` calendar years of the record (years <= first_year + ref_len - 1).
    sigma = std (ddof=2) of the residuals of a linear fit inside the reference period (detrended annual variability);
    ref_mean = mean of the reference values. dev(y) = Sen line(y) - ref_mean. Emerged in year Y when |dev| > k*sigma
    in the direction of the slope for Y and for ALL later integer years up to the last observed year (permanent).
    Years inside the reference period are not eligible (search starts after it).
    Not emerged -> status 'not_yet_distinguishable' ('Henuz ayirt edilemiyor') plus years_needed: extrapolated years
    after the last observation until the Sen line reaches k*sigma (None if the slope points away / is zero)."""
    v = np.asarray(values, float)
    y = np.asarray(years, float)
    ok = np.isfinite(v)
    v, y = v[ok], y[ok]
    s = trend(v, y)
    if s is None:
        return None
    ref = y <= y[0] + ref_len - 1
    if ref.sum() < 6:
        return None
    coef = np.polyfit(y[ref], v[ref], 1)
    resid = v[ref] - np.polyval(coef, y[ref])
    sigma = float(np.sqrt(np.sum(resid ** 2) / (ref.sum() - 2)))
    ref_mean = float(v[ref].mean())
    ref_end = int(y[ref].max())
    sign = 1.0 if s["sen_slope_per_year"] >= 0 else -1.0
    grid = np.arange(ref_end + 1, int(y[-1]) + 1)
    dev = sign * (sen_line(s, grid) - ref_mean)
    exceed = dev > k * sigma
    out = dict(sigma=sigma, ref_mean=ref_mean, ref_years=[int(y[0]), ref_end], k=k, threshold=k * sigma,
               direction="increasing" if sign > 0 else "decreasing")
    if len(grid) and exceed[-1]:
        bad = np.flatnonzero(~exceed)
        first = int(grid[(bad[-1] + 1) if len(bad) else 0])
        cens = first == ref_end + 1
        return dict(out, emerged=True, year=first, status="emerged", years_needed=0.0, censored_at_ref_end=cens,
                    censored_note=("Emergence year is the first post-reference year: the Sen line was already outside the "
                                   "reference variability when the reference period ended, so the true emergence year is "
                                   "EARLIER or equal (left-censored); read it as 'by <year>', not as a detected date.") if cens else None)
    slope = abs(s["sen_slope_per_year"])
    last_dev = float(dev[-1]) if len(grid) else 0.0
    need = (k * sigma - last_dev) / slope if slope > 0 and sigma >= 0 else None
    return dict(out, emerged=False, year=None, status="not_yet_distinguishable", censored_at_ref_end=False, censored_note=None,
                label_tr="Henüz ayırt edilemiyor", years_needed=None if need is None else float(max(need, 0.0)))


def compute_stats(df, min_valid=0.8):
    d = df[(df.valid_frac >= min_valid) & df.area_km2.notna()]
    out = {"area": trend(d.area_km2.values, d.year.values)}
    t = d[d.lst_c.notna()]
    out["lst_all"] = trend(t.lst_c.values, t.year.values)
    # L5 -> L8 break (L8 launched 2013; no L5 data after 2011/12): trend before / after separately
    for name, sub in (("lst_1985_2012", t[t.year <= 2012]), ("lst_2013_2025", t[t.year >= 2013])):
        out[name] = trend(sub.lst_c.values, sub.year.values)
    out["area_emergence"] = emergence(d.area_km2.values, d.year.values)
    out["lst_emergence"] = emergence(t.lst_c.values, t.year.values)
    out["lst_emergence_note"] = ("LST switches Landsat 5 -> 8 at 2012/13 (step of ~3 C); the pooled emergence year is "
                                 "dominated by this sensor break, see lst_emergence_1985_2012 (Landsat 5 only)")
    s5 = t[t.year <= 2012]
    out["lst_emergence_1985_2012"] = emergence(s5.lst_c.values, s5.year.values)
    return out
