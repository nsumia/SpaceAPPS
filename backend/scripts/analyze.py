"""Stage 3 analyses on an existing lake record (no Landsat access): refresh stats (emergence) in series.json, build
climate.json (NASA POWER, cached under data/power_cache) and swot.json.

    .venv/bin/python -m backend.scripts.analyze burdur van aksehir egirdir
"""
import json
import os
import sys

import pandas as pd

from backend.core import climate, swot
from backend.core.lakes import lake_dir
from backend.core.stats import compute_stats


def refresh_stats(alias):
    p = os.path.join(lake_dir(alias), "series.json")
    with open(p) as f:
        d = json.load(f)
    d["stats"] = compute_stats(pd.DataFrame(d["series"]), d["min_valid"])
    with open(p, "w") as f:
        json.dump(d, f, indent=1)
    return d["stats"]


def main(aliases):
    for a in aliases:
        st = refresh_stats(a)
        ae, le, l5 = st["area_emergence"], st["lst_emergence"], st["lst_emergence_1985_2012"]
        print(a, "area", st["area"]["sen_slope_per_decade"], "emergence", ae and (ae["year"], ae["years_needed"]),
              "| lst", le and le["year"], "| lst L5", l5 and (l5["year"], l5["years_needed"]))
        climate.run(a)
        print(a, "swot ok =", swot.run(a)["ok"])


if __name__ == "__main__":
    main(sys.argv[1:])
