"""Stage 3 analyses on an existing lake record (no Landsat access): refresh stats (emergence) in series.json, build
climate.json (NASA POWER, cached under data/power_cache) and swot.json.

    .venv/bin/python -m backend.scripts.analyze burdur van aksehir egirdir
"""
import json
import os
import sys

import pandas as pd

from backend.core import climate, quality, swot
from backend.core.lakes import lake_dir
from backend.core.stats import compute_stats


def refresh_stats(alias):
    p = os.path.join(lake_dir(alias), "series.json")
    with open(p) as f:
        d = json.load(f)
    d["stats"] = compute_stats(pd.DataFrame(d["series"]), d["min_valid"])
    rel = quality.assess(d["series"], d["min_valid"])
    d["reliability"] = rel
    vol = set(rel["volatile_years"])
    for r in d["series"]:
        r["volatile"] = r["year"] in vol
    with open(p, "w") as f:
        json.dump(d, f, indent=1)
    return d["stats"]


def annotate_climate(alias):
    """Add `interpretable`, `ci_includes_zero`, `wording` to climate.json decomposition(s) (no network)."""
    cp = os.path.join(lake_dir(alias), "climate.json")
    with open(os.path.join(lake_dir(alias), "series.json")) as f:
        rel = json.load(f).get("reliability", {})
    with open(cp) as f:
        c = json.load(f)
    for key in ("decomposition", "decomposition_no_intercept"):
        d = c.get(key)
        if not d or not d.get("ok"):
            continue
        flags = [x for x in d.get("interpretation_flags", []) if not x.startswith("unreliable_area_series")]
        if rel.get("reliability") == "low":
            flags.append("unreliable_area_series: annual area jumps between years (series.json reliability=low); share is not meaningful")
        ci = d.get("explained_share_ci90")
        d["interpretation_flags"] = flags
        d["ci_includes_zero"] = bool(ci and ci[0] <= 0 <= ci[1])
        d["interpretable"] = not flags
        if flags:
            d["wording"] = "not computable / not interpretable: " + "; ".join(x.split(":")[0] for x in flags)
        elif d["ci_includes_zero"]:
            d["wording"] = "climate share not distinguishable from 0 (90 % CI includes 0); do not claim a climate effect"
        else:
            d["wording"] = "climate share with 90 % bootstrap CI; model-based, a sign not proof"
    with open(cp, "w") as f:
        json.dump(c, f, indent=1)
    return c["decomposition"]


def main(aliases):
    if aliases and aliases[0] == "--post":      # offline: stats + reliability + climate annotation only
        for a in aliases[1:]:
            st = refresh_stats(a)
            d = annotate_climate(a)
            print(a, "reliability", json.load(open(os.path.join(lake_dir(a), "series.json")))["reliability"]["reliability"],
                  "| emergence", st["area_emergence"] and (st["area_emergence"]["year"], st["area_emergence"]["censored_at_ref_end"]),
                  "| interpretable", d["interpretable"], "| ci0", d["ci_includes_zero"])
        return
    for a in aliases:
        st = refresh_stats(a)
        ae, le, l5 = st["area_emergence"], st["lst_emergence"], st["lst_emergence_1985_2012"]
        print(a, "area", st["area"] and st["area"]["sen_slope_per_decade"], "emergence", ae and (ae["year"], ae["years_needed"]),
              "| lst", le and le["year"], "| lst L5", l5 and (l5["year"], l5["years_needed"]))
        climate.run(a)
        print(a, "swot ok =", swot.run(a)["ok"])
        annotate_climate(a)


if __name__ == "__main__":
    main(sys.argv[1:])
