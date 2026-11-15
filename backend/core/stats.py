"""Statistics on a yearly lake series: trend + emergence year, reliability of the area series, area forecast."""
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


# ---------------------------------------------------------------------------------------------------------------
# Reliability of an annual area series
#
# Reliability of an annual area series (Stage 4 fix for Stage 3 review item 1).
#
# Per year: `volatile` when the area differs from the median of the neighbouring valid years (+-2, excluding itself) by
# more than VOLATILE_FRAC of the 1985-1990 mean area. Lake level: reliability 'low' when >= LOW_SHARE of the valid years
# are volatile. This detects threshold/shallow-water flips (Aksehir: 0 <-> 30-107 km2 with valid_frac 1.0); it does NOT
# tell whether the flip is a real seasonal drying or a classification artefact, only that single-year values cannot be
# trusted individually.

VOLATILE_FRAC = 0.15
LOW_SHARE = 0.2


def assess(series, min_valid=0.8):
    ok = [r for r in series if r.get("area_km2") is not None and (r.get("valid_frac") or 0) >= min_valid]
    if len(ok) < 8:
        return dict(reliability="unknown", n_valid=len(ok), volatile_years=[], note="too few valid years")
    yrs = np.array([r["year"] for r in ok], float)
    a = np.array([r["area_km2"] for r in ok], float)
    ref = a[yrs <= 1990]
    ref_mean = float(ref.mean() if len(ref) else a[:6].mean())
    vol = []
    for i in range(len(a)):
        nb = [a[j] for j in range(max(0, i - 2), min(len(a), i + 3)) if j != i]
        if abs(a[i] - np.median(nb)) > VOLATILE_FRAC * ref_mean:
            vol.append(int(yrs[i]))
    share = len(vol) / len(a)
    rel = "low" if share >= LOW_SHARE else "ok"
    note = None
    if rel == "low":
        note = (f"{len(vol)} of {len(a)} valid years jump by more than {int(VOLATILE_FRAC * 100)} % of the 1985-1990 mean "
                "relative to their neighbours (shallow/ephemeral water or threshold artefact, not independently checked). "
                "Single-year areas, the trend, the emergence year and the climate share are NOT reliable.")
    return dict(reliability=rel, n_valid=len(a), volatile_years=vol, volatile_share=round(share, 2),
                volatile_frac_threshold=VOLATILE_FRAC, ref_mean_km2=round(ref_mean, 1), note=note)


# ---------------------------------------------------------------------------------------------------------------
# Lake-area forecast
#
# A small, backtested statistical model. No neural network and no language model: a record has at
# most ~40 yearly values, so anything bigger would only memorise noise.
#
# Three candidate models are fitted to the valid yearly areas:
#   sen_full     Sen (Theil-Sen) trend of the whole record + AR(1) year-to-year memory of the residuals
#   sen_recent   the same, fitted to the last RECENT_N valid years only (catches a change of regime)
#   persistence  "stays at the mean of the last 3 valid years" (random walk); the no-skill baseline
#
# A trend whose bootstrap 90 % interval includes zero is flagged (trend_not_distinguishable_from_zero).
#
# Model choice is data-driven (rolling-origin backtest): for every origin with at least MIN_TRAIN valid years, each
# model is fitted to the years up to the origin and scored on the up-to-BACKTEST_H years that follow. The model with the
# lowest mean absolute error is used; its skill is reported relative to persistence. A trend model is only chosen when
# it beats persistence by more than MIN_SKILL, otherwise the forecast is flat ("no predictable trend").
#
# Uncertainty: N_DRAWS Monte-Carlo paths. Each path refits the trend on a bootstrap sample of the years (trend
# uncertainty) and adds simulated AR(1) noise that starts at the last observed residual (year-to-year variability).
# Bands are the 5-95 % and 25-75 % quantiles of the paths, clipped at 0 km2. The share of backtest values that fell
# inside the 90 % band is reported (coverage90) so the band can be judged, not just trusted.
#
# This is an extrapolation of the past behaviour. It knows nothing about future rainfall, water policy, dams or
# pumping, and it is NOT a climate projection.

HORIZON_YEAR = 2040
MIN_YEARS = 15          # valid years needed for any forecast
MIN_TRAIN = 12          # valid years needed at a backtest origin
RECENT_N = 15
BACKTEST_H = 10         # years ahead scored in the backtest
MIN_SKILL = 0.05        # a trend model must beat persistence by this much (share of MAE)
N_DRAWS = 2000
N_DRAWS_BACKTEST = 200
LOW_COVERAGE = 0.7      # 90 % band that held fewer than this share of backtest values is flagged
MILESTONES = (2030, 2035, 2040)
MODELS = ("sen_full", "sen_recent", "persistence")
NOTE = ("Extrapolation of the past behaviour of the lake: it knows nothing about future rainfall, water policy, dams "
        "or pumping. It is not a climate projection, and the band is only as good as the backtest says.")


def _sen(y, v):
    """Theil-Sen slope and intercept (scipy convention: median(v) - slope * median(y)); y must be strictly increasing."""
    i, j = np.triu_indices(len(y), 1)
    slope = float(np.median((v[j] - v[i]) / (y[j] - y[i])))
    return slope, float(np.median(v) - slope * np.median(y))


def _fit(y, v, model):
    """Fitted state of one model on the valid years y (ascending) and areas v."""
    gap = float(np.median(np.diff(y))) if len(y) > 1 else 1.0
    if model == "persistence":
        d = np.diff(v) / np.sqrt(np.diff(y))                     # per-year step, robust to 2nd/3rd-year cadence
        return dict(model=model, y=y, v=v, level=float(v[-3:].mean()), step=float(d.std(ddof=1)) if len(d) > 1 else 0.0,
                    last_year=float(y[-1]))
    if model == "sen_recent":
        y, v = y[-RECENT_N:], v[-RECENT_N:]
    slope, icpt = _sen(y, v)
    r = v - (icpt + slope * y)
    phi = 0.0
    if len(r) > 3 and r.std() > 0:
        phi = float(np.clip(np.corrcoef(r[:-1], r[1:])[0, 1], 0.0, 0.95))
    phi_year = phi ** (1.0 / gap)                                # memory per calendar year
    sd = float(r.std(ddof=2)) if len(r) > 2 else 0.0
    return dict(model=model, y=y, v=v, slope=slope, icpt=icpt, phi=phi_year, sd=sd, innov=sd * np.sqrt(1 - phi_year ** 2),
                last_resid=float(r[-1]), last_year=float(y[-1]))


def _point(f, years):
    """Central forecast at `years` (all after the last fitted year)."""
    years = np.asarray(years, float)
    if f["model"] == "persistence":
        return np.full(len(years), f["level"])
    h = years - f["last_year"]
    return np.maximum(f["icpt"] + f["slope"] * years + f["phi"] ** h * f["last_resid"], 0.0)


def _paths(f, years, n, rng, slopes=None):
    """n simulated paths x len(years) (consecutive calendar years starting right after the last fitted year).
    `slopes` (a list) receives the bootstrap slopes of a trend model."""
    years = np.asarray(years, float)
    k = len(years)
    if f["model"] == "persistence":
        return np.maximum(f["level"] + np.cumsum(rng.normal(0.0, f["step"], (n, k)), axis=1), 0.0)
    y, v = f["y"], f["v"]
    idx = rng.integers(0, len(y), (n, len(y)))                   # trend uncertainty: refit on resampled years
    yb, vb = y[idx], v[idx]
    i, j = np.triu_indices(len(y), 1)
    dx = yb[:, j] - yb[:, i]
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = np.nanmedian(np.where(dx != 0, (vb[:, j] - vb[:, i]) / dx, np.nan), axis=1)
    slope = np.where(np.isfinite(slope), slope, f["slope"])
    lines = (np.median(vb, axis=1) - slope * np.median(yb, axis=1))[:, None] + slope[:, None] * years
    if slopes is not None:
        slopes.extend(slope)
    e = np.empty((n, k))
    prev = np.full(n, f["last_resid"])
    for t in range(k):                                           # AR(1) noise continuing from the last residual
        prev = f["phi"] * prev + rng.normal(0.0, f["innov"], n)
        e[:, t] = prev
    return np.maximum(lines + e, 0.0)


def _backtest(y, v, rng):
    """Rolling-origin backtest. Returns (mae per model, n_origins, n_pairs, origins) or None when the record is too short."""
    err = {m: [] for m in MODELS}
    origins = []
    for i in range(MIN_TRAIN, len(y)):
        fut = (y[i:] - y[i - 1]) <= BACKTEST_H
        if not fut.any():
            continue
        origins.append(i)
        for m in MODELS:
            err[m].extend(np.abs(_point(_fit(y[:i], v[:i], m), y[i:][fut]) - v[i:][fut]))
    if not origins:
        return None
    return {m: float(np.mean(e)) for m, e in err.items()}, len(origins), len(err["persistence"]), origins


def _coverage(y, v, model, origins, rng):
    """Share of backtest values inside the simulated 90 % band of the chosen model."""
    hit = tot = 0
    for i in origins:
        f = _fit(y[:i], v[:i], model)
        grid = np.arange(y[i - 1] + 1, y[i - 1] + BACKTEST_H + 1)
        lo, hi = np.percentile(_paths(f, grid, N_DRAWS_BACKTEST, rng), [5, 95], axis=0)
        for yy, vv in zip(y[i:], v[i:]):
            k = int(yy - y[i - 1]) - 1
            if k < BACKTEST_H:
                tot += 1
                hit += lo[k] <= vv <= hi[k]
    return float(hit / tot) if tot else None


def forecast_area(rows, min_valid=0.8, reliability="unknown", ref_mean=None, horizon_year=HORIZON_YEAR, seed=0):
    """Forecast of the yearly lake area up to `horizon_year` from series rows ({year, area_km2, valid_frac}).

    Always returns a dict. ok=False (+ reason) when no forecast is made: too few valid years, a low-reliability series,
    or a horizon that is not after the last observation. When ok, `interpretable` is False if a flag says the numbers
    should not be quoted (the curves may still be drawn)."""
    ok = [r for r in rows if r.get("area_km2") is not None and (r.get("valid_frac") or 0) >= min_valid]
    base = dict(ok=False, horizon_year=int(horizon_year), n_valid=len(ok), note=NOTE)
    if reliability == "low":
        return dict(base, reason="unreliable_area_series")
    if len(ok) < MIN_YEARS:
        return dict(base, reason="too_few_valid_years", min_years=MIN_YEARS)
    y = np.array([r["year"] for r in ok], float)
    v = np.array([r["area_km2"] for r in ok], float)
    last = int(y[-1])
    if horizon_year <= last:
        return dict(base, reason="horizon_not_after_last_observation")
    rng = np.random.default_rng(seed)
    bt = _backtest(y, v, rng)
    if bt is None:
        return dict(base, reason="too_few_valid_years", min_years=MIN_YEARS)
    mae, n_origins, n_pairs, origins = bt
    pers = mae["persistence"]
    skill = {m: (1 - mae[m] / pers if pers > 0 else 0.0) for m in MODELS}
    best = min(("sen_full", "sen_recent"), key=lambda m: mae[m])
    model = best if skill[best] > MIN_SKILL else "persistence"
    cover = _coverage(y, v, model, origins, rng)
    f = _fit(y, v, model)
    grid = np.arange(last + 1, int(horizon_year) + 1)
    slopes = []
    q = np.percentile(_paths(f, grid, N_DRAWS, rng, slopes), [5, 25, 50, 75, 95], axis=0)
    slope_ci = [round(10 * float(x), 2) for x in np.percentile(slopes, [5, 95])] if slopes else None
    flags = []
    if model == "persistence":
        flags.append("no_skill_over_persistence")
    elif slope_ci[0] <= 0 <= slope_ci[1]:
        flags.append("trend_not_distinguishable_from_zero")
    if cover is not None and cover < LOW_COVERAGE:
        flags.append("band_too_narrow_in_backtest")
    if float(np.median(np.diff(y))) > 1:
        flags.append("sparse_cadence")
    rd = lambda a: [round(float(x), 2) for x in a]                  # noqa: E731
    ref = float(ref_mean) if ref_mean else None
    miles = []
    for my in MILESTONES:
        if last < my <= horizon_year:
            k = my - last - 1
            miles.append(dict(year=my, median_km2=round(float(q[2][k]), 1), lo90_km2=round(float(q[0][k]), 1),
                              hi90_km2=round(float(q[4][k]), 1),
                              median_pct_of_ref=None if not ref else round(100 * float(q[2][k]) / ref, 1)))
    return dict(
        ok=True, model=model, horizon_year=int(horizon_year), last_observed_year=last, n_valid=len(ok),
        last_observed_km2=round(float(v[-1]), 1),
        slope_km2_per_decade=None if model == "persistence" else round(10 * f["slope"], 2),
        slope_ci90_km2_per_decade=slope_ci,
        years=[int(g) for g in grid], median=rd(q[2]), lo90=rd(q[0]), hi90=rd(q[4]), lo50=rd(q[1]), hi50=rd(q[3]),
        milestones=miles,
        backtest=dict(n_origins=n_origins, n_pairs=n_pairs, max_horizon_years=BACKTEST_H,
                      mae_km2={m: round(mae[m], 2) for m in MODELS},
                      skill_vs_persistence={m: round(skill[m], 3) for m in MODELS if m != "persistence"},
                      chosen_skill=0.0 if model == "persistence" else round(skill[model], 3),
                      coverage90=None if cover is None else round(cover, 2)),
        flags=flags, interpretable="band_too_narrow_in_backtest" not in flags, n_draws=N_DRAWS, note=NOTE)
