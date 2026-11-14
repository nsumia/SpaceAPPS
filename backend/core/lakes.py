"""Lake definitions and record paths.

lake_id = SWOT Prior Lake Database ID if known, else custom-<hash of rounded centre>. The PLD IDs of the four
Turkish lakes are NOT verified (no PLD file lookup yet, Stage 3), so they get custom ids; the readable alias
(burdur, aksehir, egirdir, van) is the directory name under data/lakes/ and is stored with the id in meta.json.
box = (lon_min, lat_min, lon_max, lat_max), generous so that it contains the 1985 lake; seed = (lon, lat) inside it.
"""
import os

from backend.core.geo import custom_lake_id

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LAKES_DIR = os.path.join(ROOT, "data", "lakes")

LAKES = {
    # East edge 30.45: the 1986 lake reaches 30.389E (Stage 1). Yarisli (37.56N 29.96E) lies outside the box.
    "burdur":  dict(name="Burdur",  country="TR", bbox=(29.95, 37.60, 30.45, 37.90), seed=(30.18, 37.72), pld_id=None),
    # Wider than legacy on purpose: includes Eber Lake (~38.6N 31.2E) so that the component logic must exclude it.
    "aksehir": dict(name="Akşehir", country="TR", bbox=(31.05, 38.25, 31.70, 38.80), seed=(31.40, 38.50), pld_id=None),
    "egirdir": dict(name="Eğirdir", country="TR", bbox=(30.60, 37.70, 31.10, 38.40), seed=(30.87, 38.05), pld_id=None),
    # Legacy box (42.25-43.75) clipped Tatvan (42.28E) shore; padded. Includes Erçek Lake (~43.6E 38.65N).
    "van":     dict(name="Van",     country="TR", bbox=(42.15, 38.20, 43.75, 39.10), seed=(42.95, 38.65), pld_id=None),
}


def lake_id(alias):
    d = LAKES[alias]
    return d["pld_id"] or custom_lake_id(*d["seed"])


def lake_dir(alias):
    return os.path.join(LAKES_DIR, alias)
