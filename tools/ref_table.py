"""Print the Stage 6 per-lake table (markdown) from data/lakes: python tools/ref_table.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.api import store  # noqa: E402

st = store.Settings()
print("| Lake | Country | Res (m) | Cadence | Valid yrs | Area first -> last (km2) | Trend %/decade | p | Ours | Literature | Agree |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for s in sorted(store.list_lakes(st), key=lambda x: (x["group"], x["name"] or "")):
    rec = store.record(st, s["id"])
    rows = store.valid_rows(rec["series"]["series"], rec["series"].get("min_valid", 0.8))
    fl = f'{rows[0]["area_km2"]:.0f} ({rows[0]["year"]}) -> {rows[-1]["area_km2"]:.0f} ({rows[-1]["year"]})' if rows else "n/a"
    p = s["trend_p"]
    ag = {True: "yes", False: "NO", None: "n/a"}[s.get("literature_agrees")]
    print(f'| {s["name"]} | {s["country"]} | {s.get("resolution_m")} | {s.get("cadence_note") or "every year"} | {len(rows)} | {fl} | '
          f'{s["trend_pct_per_decade"] if s["trend_pct_per_decade"] is not None else "n/a"} | {"n/a" if p is None else ("<1e-6" if p < 1e-6 else f"{p:.2g}")} | '
          f'{s.get("our_direction") or "n/a"} | {s.get("literature_direction") or "-"} | {ag} |')
