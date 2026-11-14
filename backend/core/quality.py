"""Reliability of an annual area series (Stage 4 fix for Stage 3 review item 1).

Per year: `volatile` when the area differs from the median of the neighbouring valid years (+-2, excluding itself) by
more than VOLATILE_FRAC of the 1985-1990 mean area. Lake level: reliability 'low' when >= LOW_SHARE of the valid years
are volatile. This detects threshold/shallow-water flips (Aksehir: 0 <-> 30-107 km2 with valid_frac 1.0); it does NOT
tell whether the flip is a real seasonal drying or a classification artefact, only that single-year values cannot be
trusted individually."""
import numpy as np

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
