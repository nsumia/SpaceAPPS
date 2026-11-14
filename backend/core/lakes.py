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


# ---- Stage 6: global reference lakes (group "reference"). Keys beyond Stage 1-5: group, why, note (MNDWI limits),
# step (cadence in years, 1 = every year), res_m (optional override, else adaptive), window (MM-DD start, end).
# Seeds/boxes come from the Natural Earth lake index (data/index/lakes.geojson) plus a margin for the 1985 extent.
REF = dict(group="reference")
LAKES.update({
    "urmia": dict(name="Urmia", country="IR", bbox=(44.8, 36.9, 46.1, 38.4), seed=(45.512, 37.698), pld_id=None, step=2, **REF,
                  why="Neighbour of Turkiye; fast-shrinking hypersaline lake; irrigation pressure and drought.",
                  note="Salt flats, causeway and evaporation/salt ponds can be classified as water; only the connected main water body is kept."),
    "aral_south": dict(name="Aral Sea (South / Large Aral)", country="KZ/UZ", bbox=(57.8, 43.2, 62.0, 46.1), seed=(58.527, 45.22), pld_id=None,
                       step=3, res_m=240, **REF,
                       why="Classic irrigation-driven collapse (Amu Darya / Syr Darya diversion). Data-only description; shared by Kazakhstan and Uzbekistan.",
                       note="Very large lake: 240 m resolution and every 3rd year. Southern/eastern basins dried up; the 1985-90 extent defines the analysis polygon, so later shrinkage is measured inside it. Boundary with the North Aral at 46.1 N is approximate."),
    "aral_north": dict(name="Aral Sea (North / Small Aral)", country="KZ", bbox=(59.8, 46.1, 61.9, 47.5), seed=(60.9, 46.75), pld_id=None,
                       step=2, **REF,
                       why="Part of the Aral Sea separated by a dam (Kokaral, 2005); partial recovery afterwards. Data-only description.",
                       note="Boundary with the South Aral at 46.1 N is approximate (the sea was one water body until about 1987); every 2nd year."),
    "great_salt_lake": dict(name="Great Salt Lake", country="US", bbox=(-113.4, 40.5, -111.7, 41.9), seed=(-112.575, 41.183), pld_id=None, step=2, **REF,
                            why="Arid region; water use and drought. Record high in 1986-87, record low in 2022.",
                            note="Salt evaporation ponds and wetlands along the shore may count as water; disconnected ponds are excluded by the largest-component rule, connected ones are not. Level changes at the shallow flats change area strongly."),
    "mead": dict(name="Lake Mead", country="US", bbox=(-114.85, 36.0, -113.7, 36.6), seed=(-114.014, 36.208), pld_id=None, step=1, **REF,
                 why="Reservoir; drought and water allocation (Colorado River).",
                 note="Reservoir: area follows operations as well as climate; narrow canyon arms are partly mixed pixels at 30 m."),
    "chad": dict(name="Lake Chad", country="TD/NE/NG/CM", bbox=(13.0, 12.0, 15.3, 14.6), seed=(14.536, 13.061), pld_id=None, step=1, start=2013, **REF,
                 why="Sahel climate variability; shared by Chad, Niger, Nigeria and Cameroon. Data-only description.",
                 note="Series starts in 2013: the Planetary Computer Landsat 5/8/9 collection has no Aug-Sep scenes over the lake before 2013 (checked with STAC searches for 1985-2010), and Landsat 7 is excluded by design, so there is no 1985-1990 baseline (the first 3 valid years are used instead). MNDWI limitation: shallow lake with extensive floating/emergent vegetation and seasonal flooding; open water is under- or mis-estimated and the Aug-Sep window is the rising season (the lake peaks in Dec-Feb), so annual values depend on rainfall timing. Treat the trend as indicative only."),
    "poopo": dict(name="Poopo", country="BO", bbox=(-67.8, -19.6, -66.5, -17.6), seed=(-67.181, -18.614), pld_id=None, step=1, **REF,
                  why="Shallow lake with complete desiccation events (2015-16).",
                  note="MNDWI limitation: very shallow, turbid, saline water with vegetation and salt crust; mud/wet flats can be mixed with water and zero-area years are real drying or classification limits. Southern hemisphere: water year Apr-Mar for climate."),
    "titicaca": dict(name="Titicaca", country="PE/BO", bbox=(-70.2, -17.0, -68.4, -15.1), seed=(-69.354, -15.921), pld_id=None, step=2, **REF,
                     why="Large, relatively stable lake; control example. Shared by Peru and Bolivia. Data-only description.",
                     note="Control lake: level varies by about 1-2 m, which changes area only a little in the deep basin; shallow bays with reeds are uncertain. Southern hemisphere: water year Apr-Mar for climate."),
    "balkhash": dict(name="Balkhash", country="KZ", bbox=(72.8, 44.6, 79.6, 47.2), seed=(73.953, 45.903), pld_id=None, step=3, **REF,
                     why="Closed basin; irrigation and inflow (Ili) pressure.",
                     note="Very large lake: 120 m resolution and every 3rd year; the box is wider than one UTM zone so edges are slightly distorted; shallow eastern part has reeds and variable shore."),
    "sevan": dict(name="Sevan", country="AM", bbox=(44.8, 40.0, 45.8, 40.75), seed=(45.364, 40.379), pld_id=None, step=1, **REF,
                  why="Regional lake with historic water withdrawal (Soviet era) and later level recovery.",
                  note="High-altitude lake; Aug-Sep composites are mostly cloud-free."),
    "tuz": dict(name="Tuz Golu", country="TR", bbox=(33.0, 38.3, 34.0, 39.3), seed=(33.312, 38.825), pld_id=None, step=1,
                window=("03-15", "05-15"), **REF,
                why="Turkiye's second largest lake; very shallow, seasonal. Only included in this stage, with a seasonality caveat.",
                note="Seasonality caveat: the lake is a thin sheet of water in winter-spring and a salt crust in late summer, so Aug-Sep would show almost no water. This record uses a 15 Mar - 15 May window. MNDWI limitation: salt crust and wet salt flats are ambiguous; area is very sensitive to the year's rainfall."),
    "qinghai": dict(name="Qinghai", country="CN", bbox=(99.4, 36.4, 100.9, 37.3), seed=(100.114, 36.879), pld_id=None, step=2, **REF,
                    why="Increasing-lake example (Tibetan Plateau); rising since about 2004.",
                    note="Saline lake; seasonal ice does not affect the Aug-Sep window."),
    "dead_sea": dict(name="Dead Sea", country="IL/JO", bbox=(35.2, 31.0, 35.8, 31.95), seed=(35.478, 31.526), pld_id=None, step=1, **REF,
                     why="Fast level fall (about 1 m per year). Shared by Israel, Jordan (and the West Bank coast). Data-only description.",
                     note="Southern evaporation ponds are industrial and may count as water; only the connected main water body around the seed is kept. Hypersaline water gives a different MNDWI signal near the shore."),
})


def years_for(cfg, start=1985, end=2025):
    """Analysis years for the lake's cadence: every `step` years from start, plus the last year."""
    step = int(cfg.get("step", 1))
    start = max(start, int(cfg.get("start", start)))
    return sorted(set(range(start, end + 1, step)) | {end})


def lake_id(alias):
    d = LAKES[alias]
    return d["pld_id"] or custom_lake_id(*d["seed"])


def lake_dir(alias):
    return os.path.join(LAKES_DIR, alias)
