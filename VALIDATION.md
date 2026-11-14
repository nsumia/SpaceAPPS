# Stage 1 validation: Lake Burdur (real Planetary Computer data)

Run date 2026-11-14. Module: `burdur_area.py` (Stage 1, since moved to `backend/core/landsat.py` + `stats.py`; `legacy/` untouched). Series: `data/lakes/burdur/series.json`, plot: `docs/burdur_series.png`.
Stage 1 reproduce command (script removed in Stage 2): `burdur_area.py --start 1985 --end 2025 ...`; now `.venv/bin/python -m backend.scripts.precompute --lake burdur --plot docs/burdur_series.png` (about 12 min). Stage 1 series kept as `data/lakes/burdur/series_stage1.json`. Offline tests: `tools/run_tests.sh`.

![Burdur series](docs/burdur_series.png)

## 1. Assumptions 1-2 (verified by `tools/verify_assets.py` on real items)
- L5 items (LT05_L2SP_178034_19860924, LT05_L2SP_179034_20100901): thermal asset `lwir`; no `lwir11`.
- L8 (LC08_L2SP_178034_20210924) and L9 (LC09_L2SP_179034_20230929): thermal asset `lwir11`; no `lwir`.
- NIR key is `nir08` (`nir` does not exist). The code does not use NIR (MNDWI = green, swir16).
- `raster:bands`: thermal scale 0.00341802, offset 149, nodata 0, unit kelvin; green/swir16/nir08 scale 2.75e-05, offset -0.2, nodata 0; `qa_pixel` nodata 1. All match the code constants.
- odc-stac returns raw DN (no scaling), so scaling stays in code. Landsat 4 and 7 are excluded (platform filter `in [landsat-5, landsat-8, landsat-9]` works server side, plus a client-side guard).
- Legacy fixes: bbox east edge (below), explicit platform guard, retries (2) + GDAL HTTP timeout, dask workers limited to 4, years run sequentially, failed year kept as NaN with `error` field, pure-numpy `analyze_arrays` for offline testing, JSON output.

## 2. Comparison with literature
Sabuncu 2020 (doi 10.35414/akufemubid.711653): 206 km2 (20 Jun 1986), 125 km2 (8 Jul 2019), June/July single scenes with MLC/SVM/MNDWI. Ours is the Aug-Sep median of all scenes with cloud cover < 40 %, so ours is later in the dry season (lake lower by evaporation) and uses a composite.

| Year | Ours (km2) | Reference | Difference |
|---|---|---|---|
| 1986 | 216.7 | 206 (Sabuncu) | +5.2 % |
| 2019 | 127.8 | 125 (Sabuncu) | +2.2 % |
| 2020 | 125.6 | ~120-125 target | within / +0.5 % of 125 |
| 2021 | 122.6 | ~120-125 | within |
| 2022 | 121.6 | ~120-125 | within |

All inside the 10 % acceptance limit. The 120 km2 for 2022 comes from a repository listing of Kaya et al. 2023, not verified against the full text.

### Cause of the first-run failure (173 km2 in 1986, -16 %)
The first box (lon 29.95-30.30) clipped the lake: `tools/diagnose_component.py` (largest connected water component around 30.18E 37.72N in a wide box, MNDWI > 0) found the 1986 lake spanning lon 30.056-30.389, lat 37.645-37.848, 204.8 km2, while in 2020 it spans lon 30.061-30.270 (124.8 km2). The 2020 result was unaffected (125.0 km2 in the first run), which is why 2020 alone looked fine. Box changed to lon 29.95-30.45, lat 37.60-37.90. Yarisli Lake (37.56N 29.96E) stays outside because lat_min is 37.60.
Threshold sensitivity (same diagnostic, lake component, 1986): MNDWI > 0: 204.8; > -0.1: 205.9; > -0.2: 208.1 km2. In 2020: 124.8 / 127.1 / 150.1 (at -0.2 the lake merges with neighbouring wet ground). So threshold 0 is kept.
Remaining difference: the box total in 1986 (216.7) is about 12 km2 above the connected lake component (204.8). Likely other water or wet pixels inside the box (not verified which); Stage 2's "largest connected component + buffer" polygon should remove this. Older years (1985, 1987-1989: 209-221 km2) are therefore a few percent high.
Caveat: 1989 to 1990 shows a drop of 14 km2 and 2002-2004 a rise (164-169 km2), both inside the noise of 2-8 scenes per year; not investigated.

## 3. Lake surface temperature
Late-summer median of eroded (150 m) water pixels: 20.5-27.5 deg C in all years (min 20.52 in 1991, max 27.45 in 2010), inside the expected 20-28 range (the range itself is not literature-verified; Aslan and Koc-San 2021 absolute values were not checked). Pure-water pixel counts are large; no year dropped for lack of pixels. Minimum pure-water (eroded) pixel count over all years: 121,028 px of 30 m (2025; Stage 2 run, threshold is 50 px).

## 4. Trend tests (Hamed-Rao modified Mann-Kendall + Sen slope, years with valid_frac >= 0.8)
- Area 1985-2025: decreasing, n=40 (1985-2025), Sen -23.33 km2/decade, p=1.91e-08 (Stage 1 numbers; Sen there was per observation, see Stage 2 section 3 for the fixed values).
- LST all years: increasing, n=40 (1985-2025), Sen +1.28 deg C/decade, p=1.01e-07.
- **L5 to L8 break (2012/2013)**: LST before ("1985_2012" window, data end 2011): increasing, n=27 (1985-2011), Sen +1.02 deg C/decade, p=0.00862; after: no trend, n=13 (2013-2025), Sen +0.21 deg C/decade, p=0.669. The step in level is visible (mean 1985-2011 about 23.5, 2013-2025 about 26.3). Part of the 1985-2025 warming may be an L5/L8 calibration offset rather than a lake change, so the pooled trend (+1.28 deg C/decade) must not be presented as a clean warming rate. The within-L5 trend (+1.0 deg C/decade) is significant; the L8/9-only trend is not. No cross-calibration was attempted. L8/9 (100 m TIRS, resampled) versus L5 (120 m) also differ in resolution and shrinking lake shifts which pixels remain pure water.
- 2012 is NaN: Landsat 5 stopped in 2011 and Landsat 8 began in 2013; Landsat 7 is excluded by design. Error field empty (genuinely no scenes: n_scenes = 0).
- No year failed with a network error (all `error` fields null).

## 5. Per-year table (Aug-Sep composite; valid_frac in series.json)
| Year | Area km2 | LST deg C | Scenes |
|---|---|---|---|
| 1985 | 220.8 | 23.36 | 7 |
| 1986 | 216.7 | 24.60 | 4 |
| 1987 | 211.2 | 22.60 | 8 |
| 1988 | 212.2 | 22.64 | 8 |
| 1989 | 209.3 | 22.62 | 6 |
| 1990 | 195.5 | 21.79 | 8 |
| 1991 | 194.3 | 20.52 | 8 |
| 1992 | 187.4 | 21.42 | 6 |
| 1993 | 185.1 | 22.50 | 8 |
| 1994 | 178.2 | 22.89 | 8 |
| 1995 | 177.4 | 23.14 | 7 |
| 1996 | 178.4 | 22.36 | 8 |
| 1997 | 169.4 | 20.54 | 7 |
| 1998 | 172.3 | 24.49 | 6 |
| 1999 | 171.4 | 24.35 | 7 |
| 2000 | 166.2 | 23.21 | 8 |
| 2001 | 157.6 | 24.00 | 7 |
| 2002 | 164.4 | 25.09 | 2 |
| 2003 | 165.8 | 24.78 | 6 |
| 2004 | 169.1 | 24.31 | 6 |
| 2005 | 158.6 | 22.26 | 3 |
| 2006 | 154.8 | 25.30 | 5 |
| 2007 | 152.8 | 24.41 | 4 |
| 2008 | 148.9 | 25.46 | 5 |
| 2009 | 149.0 | 23.16 | 7 |
| 2010 | 147.6 | 27.45 | 4 |
| 2011 | 144.9 | 23.89 | 4 |
| 2012 | NaN | NaN | 0 |
| 2013 | 139.6 | 25.41 | 8 |
| 2014 | 137.2 | 27.37 | 7 |
| 2015 | 142.9 | 26.42 | 7 |
| 2016 | 135.5 | 26.78 | 7 |
| 2017 | 131.9 | 25.83 | 8 |
| 2018 | 130.1 | 26.48 | 7 |
| 2019 | 127.8 | 25.53 | 8 |
| 2020 | 125.6 | 25.93 | 8 |
| 2021 | 122.6 | 25.52 | 6 |
| 2022 | 121.6 | 26.92 | 9 |
| 2023 | 120.8 | 27.44 | 14 |
| 2024 | 118.5 | 26.62 | 13 |
| 2025 | 117.0 | 26.39 | 16 |

## 6. Not verified / open
- Cause of the ~12 km2 excess in the box total versus the connected lake in 1986-89.
- Absolute LST values against literature; absolute accuracy of the thermal data.
- Mixed-sensor consistency of area (L5 vs L8 MNDWI) beyond the 2011/2013 continuity (144.9 to 139.6 km2, consistent).

---

# Stage 2: backend, auto UTM, adaptive resolution, lake polygon, basin (run 2026-11-14)

Code: `backend/core/{landsat,stats,geo,basin,lakes,climate,swot,live}.py`, `backend/scripts/precompute.py`, `backend/api/main.py` (health + /docs only). Decision: the top-level `burdur_area.py` was removed (not wrapped); its tests moved to `backend/tests/test_landsat.py`; the CLI is `python -m backend.scripts.precompute`. Offline tests: `tools/run_tests.sh`.

## 1. Behaviour preserved (code move)
Same masking as Stage 1 (whole box, 30 m) via `precompute --lake burdur --legacy-box-mask --out-dir <scratch>`, single years, real data:

| Year | Stage 1 area | Stage 2 code, box mask | Stage 1 LST | Stage 2 LST |
|---|---|---|---|---|
| 1985 | 220.8 | 220.8 | 23.36 | 23.36 |
| 1996 | 178.4 | 178.4 | 22.36 | 22.36 |
| 2002 | 164.4 | 164.4 | 25.09 | 25.09 |
| 2020 | 125.6 | 125.6 | 25.93 | 25.93 |

So the move, the qa_radsat masking and the metric (EDT) erosion do not change the numbers at this precision.

## 2. Lake polygon (largest connected component, +1 km) versus the whole box, Burdur
Polygon from 1985-1990 (pixel water in >= 50 % of valid years, 60 m detection): component 202.5 km2, polygon (+1 km) 291.4 km2. Analysis at 30 m inside the polygon. Full 1985-2025 run, polygon masking vs Stage 1:
- 1986: **204.8 km2** (Stage 1 216.7; Sabuncu 206: -0.6 %, was +5.2 %). 1985: 205.8 (Stage 1 220.8).
- 2006-2008, 2013-2014, 2016-2025: within 1 % of Stage 1 (-0.3 to -0.8 %); 2009-2012 and 2015: -1.5 to -3.3 %. 1985-2004: -0.6 to -6.8 % (largest 1985 -6.8 %, 1989 -5.8 %, 1988 -5.6 %, 1999 -5.5 %, 1986 -5.5 %, 2002 -5.5 %).
- So the +-1 % criterion holds only where the masking is the same (verified for four years in section 1: identical). The differences are caused by the masking change, not by the code: diagnostic comparing the box mask with the polygon mask (1985, 1996) shows the excess is ONE blob of water at about 29.96E 37.865N (north-west corner of the box): 14.6 km2 in 1985 and 9.0 km2 in 1996, outside the 1 km lake buffer. Identity of that water body NOT VERIFIED. It explains the "about 12 km2 box excess" flagged in Stage 1. The earlier guess that Yarisli was involved was wrong (it is outside the box).
- Series statistics with polygon masking (Hamed-Rao MK p, Sen on actual years): area decreasing, n=40, Sen -21.13 km2/decade, p=3.3e-06; LST all years +1.23 deg C/decade (p=9.5e-08); LST 1985-2011 +1.04 deg C/decade (p=0.0081); LST 2013-2025 no trend, +0.23 deg C/decade (p=0.669). Last value 2025: 116.5 km2 (Stage 1 117.0).
- Files: `data/lakes/burdur/{series.json,series_stage1.json,meta.json,basin.geojson,masks/}`; plot `docs/burdur_series.png`.

## 3. Stage 1 SHOULD_FIX
1. MK/Sen with missing 2012: Sen slope is now `scipy.stats.theilslopes(values, actual_years)` (per year, gap-aware; test `test_sen_slope_uses_actual_years_with_gap`). The MK p value uses ranks only; the Hamed-Rao autocorrelation correction assumes equal spacing and is not adjusted for the single gap (documented in `stats.trend`). `year_gaps` is stored in the stats.
2. VALIDATION section 4 label slips fixed (units, "1985_2012" window with data end 2011).
3. Minimum pure-water pixel count: 121,028 (30 m px; 2025) in the Burdur Stage 2 run, stored as `min_lst_px` in meta.json.
4. qa_radsat: **applied.** Bits read from the STAC item `classification:bitfields` (not from memory): L5 band2 (green) bit 1, band5 (swir16) bit 4, band6 (thermal) bit 5, dropped pixel bit 9; L8/L9 band3 bit 2, band6 bit 5. The L8/L9 bitfield list has NO thermal bit (band10 is not listed), so thermal saturation for L8/9 is not masked: **open**. Result of masking at Burdur: no visible change in section 1.

## 4. Auto UTM, resolution
- `geo.utm_epsg`: Burdur 32636, Van 32638, Titicaca (-69.35, -15.9) 32719 (tests). Warning for boxes wider than 6 deg (test).
- `geo.pick_resolution(area_km2)`: <500 km2 30 m, <5000 km2 60 m, else 120 m. DEVIATION from a literal reading of the spec: the final analysis resolution is chosen by the area of the analysis polygon (lake + 1 km buffer), not the rectangular box, because Burdur's box (1,500 km2) would otherwise drop Burdur to 60 m and break the Stage 1 comparison. The detection pass (before the polygon exists) uses the box area (Burdur 60 m, Van 120 m). Resolution, CRS and erosion are written to meta.json. Thermal erosion is metric: water pixels at Euclidean distance > 150 m from non-water (test with 30 m and 60 m grids).
- Burdur: 30 m, EPSG:32636. Van: 60 m (polygon 4,068 km2), EPSG:32638.

## 5. Van (real data, EPSG:32638)
Run: `precompute --lake van --start 2013 --end 2025` (plus 2019-2021 before). Polygon: component 3,565.7 km2 (detection years 1986-1990; **1985 has no scenes** with cloud < 40 % in Aug-Sep), box water 3,772 km2 (the difference is other water such as Lake Erçek, identity not checked), polygon 4,068.5 km2, resolution 60 m (detection 120 m).
Areas (km2): 2013 3546.8, 2014 3567.1, 2015 3569.8, 2016 3519.8, 2017 3560.3, 2018 3567.1, 2019 3569.3, 2020 3566.8, 2021 3555.1, 2022 3554.3, 2023 3547.7, 2024 3550.4, 2025 3532.2; MK on these 13 years: no trend (p=0.16, Sen -16.3 km2/decade, not significant). LST 22.4-24.3 deg C. Literature area for Van NOT checked. The record covers 2013-2025 only (masks only for 2019-2021: `--no-masks`); the full 1985-2025 Van run was not done.

## 6. Other lakes and basin
- Akşehir (2020 only + detection): component 285.3 km2 vs 312.7 km2 box water, so Eber Lake (~27 km2) is excluded; 2020 area 71.9 km2 with 3 scenes (not a series; box generous: 31.05-31.70E, 38.25-38.80N). Eğirdir (2020 only): polygon 608.2 km2 (lake + 1 km), 2020 area 446.5 km2 (4 scenes), basin level 7 6,787.3 km2; detection log not captured (polygon was cached from a run that hit the timeout), not a series. Scratch outputs, not committed.
- Basin: HydroBASINS v1c, `eu` zip (360 MB, in `data/raw/`, gitignored), level 7 for lakes < 1000 km2 else level 6, union of basins that hold >= 10 % of the lake polygon (plus the best one). Burdur: 1 basin, 5,772.6 km2; Akşehir: 8,102.0 km2; Van (level 6): 17,325.4 km2. No buffer fallback was needed in the committed runs (a first Van run did fall back, flagged in meta.json, because GDAL rejected the level-6 .sbn index; fixed by extracting shp/shx/dbf/prj only). Note: this is the union of the basins containing the lake, NOT the full upstream contributing area. Basin areas were not compared with literature.

## 7. Lake ids
No SWOT PLD id is known/verified (needs the PLD file, Stage 3), so ids are `custom-<sha1 of rounded seed>[:8]`: burdur custom-1fa272fa, aksehir custom-2b08b181, egirdir custom-082105f5, van custom-e9373c68. Directory name = alias, id in meta.json.

## 8. Not verified / open
- Identity of the 29.96E 37.865N water body; absolute LST accuracy; L8/9 thermal saturation (no QA bit).
- `live.py` (POWER, Hydrocron, GIBS, Landsat-now) was ported and unit-tested only for pure helpers; no live network call was run in Stage 2.
- A rasterio `NotGeoreferencedWarning` appears during real runs (from the reprojection inside odc-stac loading); results were unaffected in the checks above but the source asset was not identified.
- Burdur `meta.json` code_version is the commit before the last two small commits (basin extraction fix, legacy flag), which do not affect series values.

# Stage 3 (analyses) - real numbers, run 2026-11-14

Commands: `.venv/bin/python -m backend.scripts.precompute --lake {burdur,van,aksehir,egirdir}` (full 1985-2025, 4 in parallel), then `.venv/bin/python -m backend.scripts.analyze burdur van aksehir egirdir` (stats refresh with emergence, `climate.json`, `swot.json`). POWER responses are cached in `data/power_cache/` (reruns offline). meta.json `code_version` reads `35446b5+dirty` (the working tree had the uncommitted Stage 3 edits while the series ran; precompute code itself unchanged from Stage 2, stats are refreshed by `analyze`).

## Series (valid = valid_frac >= 0.8 and area not NaN)
| Lake | area 1985/86 km2 | area 2023-25 km2 | Sen km2/decade (p) | n valid | not valid years |
|---|---|---|---|---|---|
| Burdur | 205.8 / 204.8 | 120.1, 118.1, 116.5 | -21.1 (3.3e-06) | 40 | 2012 |
| Van | NaN / 3556.1 | 3547.7, 3550.4, 3532.2 | -11.4 (0.0073) | 36 | 1985, 1993, 2002, 2003, 2012 |
| Akşehir | 299.9 / 289.0 | 0.3, 0.0, 0.0 (dry) | -82.0 (p < 1e-4) | 39 | 2005, 2012 |
| Eğirdir | 471.4 / 469.3 | 435.2, 425.0, 412.3 | -5.7 (0.0045) | 40 | 2012 |
Van loss (about 0.7 %/decade) is small compared with classification noise at 60 m; do not read it as a strong signal. Akşehir 2023-25 areas of ~0 km2: the lake bed is dry in the Aug-Sep composites (not independently checked).

## Emergence year (stats.emergence)
Reference = first 12 calendar years of the valid record (1985-1996; Van 1986-1997), sigma = std of the linearly detrended reference (ddof 2), threshold 2 sigma; first year after the reference after which |Sen line - reference mean| > 2 sigma in all later years. Search starts after the reference, so 1997 (Van 1998 would be the analogue) means "already separated at the end of the reference period".
| Lake | sigma km2 | area emergence | LST emergence (pooled) | LST emergence 1985-2012 (Landsat 5 only) |
|---|---|---|---|---|
| Burdur | 1.6 | 1997 | 2006 | 2011 |
| Van | 9.9 | 2017 | 2015 | not yet distinguishable (about 12 more years) |
| Akşehir | 7.9 | 1997 | 2009 | not yet distinguishable (about 11 more years) |
| Eğirdir | 2.1 | 2004 | 2008 | 2009 |
LST caveat: the Landsat 5 -> 8 step at 2012/13 (about +3 C, see Stage 1) is inside the pooled series; the pooled LST emergence years are not clean warming results. The Landsat-5-only column avoids the break but has fewer years. Note also that for LST the pooled emergence years 2006-2015 precede/straddle the break: the Sen line of a pooled series with a step is steeper than the real warming.
Unit tests: synthetic linear trend with alternating noise (true crossing 2009.5, found within 3 years), random-noise series, "not yet" case with years_needed, flat series.

## Climate decomposition (climate.json)
NASA POWER monthly PRECTOTCORR and EVLAND (mm/day x days in month), 1981-2026, basin points: Burdur 6, Akşehir 8, Eğirdir 7, Van 9 (farthest-point sampling in the HydroBASINS union polygon; MERRA-2 cells are ~0.5 x 0.625 deg so points share cells). Water year Oct-Sep. EVLAND is land evapotranspiration, **not open-water evaporation**. Model: area change between consecutive observed years = a*n_years + b*sum(P-E) fitted on 1985-1999 pairs (14), predicted for later years from the 1999 baseline; the 2012 gap pair spans two water years. Bootstrap: 2000 case resamples of the reference pairs, 90 % percentile CI. **The unexplained part is a sign, not proof, of human impact.**
| Lake | observed loss since 1999 km2 | predicted by P-E km2 | explained share (with intercept) [90 % CI] | explained share (no intercept) | corr(dA, P-E) 1985-99 | flags |
|---|---|---|---|---|---|---|
| Burdur | 45.5 | 81.6 | 1.79 [1.45, 2.11] | 1.42 | 0.07 | weak skill, share > 1 |
| Van | 59.5 | -114.4 | -1.92 [-7.12, 1.97] | -1.41 | 0.13 | weak skill, share outside 0-1, loss < 3 % |
| Akşehir | 220.2 | 136.7 | 0.62 [0.34, 0.91] | 0.41 | 0.56 | none |
| Eğirdir | 47.6 | 2.5 | 0.05 [-0.44, 0.49] | -0.09 | 0.66 | none |
Reading: only Akşehir and Eğirdir have a usable reference-period relation (corr 0.56 / 0.66). For Burdur and Van the 1985-1999 correlation is ~0, the fit has no skill, and the shares (>1 or negative) are not interpretable; a "share" there only says that the P-E proxy does not reproduce the lake. The with-intercept variant treats the 1985-1999 drift as background (unexplained = change relative to that), the no-intercept variant counts that drift as unexplained; both are stored. Synthetic test: constant withdrawal recovered within 20 % (3 seeds), pure-climate case near 0.

## SWOT volume (swot.json)
`ok=false` for all four lakes: no PLD id (Hydrocron has no location lookup; the PLD file needs an Earthdata login, not used here; CMR collection search for the PLD returned no public entry). The area-level fit and dV = integral A dh code with an extrapolation flag exists and is unit-tested on synthetic data; it is NOT verified against real SWOT data.

# Stage 4 (API) - Stage 3 review fixes (2026-11-14)

## Akşehir area flips (reliability flag)
Quick look at the committed masks (`data/lakes/aksehir/masks/<year>.png`, water = 255 px at 30 m): 2014 = 83 px (0.07 km2), 2018 = 60 px, 2021 = 33 px versus 2015 = 118,642 px (106.8 km2) and 2020 = 79,889 px (71.9 km2); valid (non-nodata) pixel counts are identical (valid_frac 1.0), so clouds are not the cause. The lake is shallow and ephemeral after about 2005, so either it really dries up or fills between Aug-Sep composites, or the MNDWI > 0 threshold flips on thin/turbid water. **Not independently checked (no second source, no optical inspection of scenes), so no correction was made.**
Instead `series.json` now has a per-year `volatile` flag and a lake-level `reliability` (`backend/core/quality.py`): a year is volatile when it differs from the median of its +-2 neighbouring valid years by more than 15 % of the 1985-1990 mean; a lake is `low` when >= 20 % of valid years are volatile. Result: Akşehir `low` (10 of 39 valid years: 2001, 2003, 2007-09, 2013-15, 2018, 2020); Burdur, Eğirdir, Van `ok`. For a `low` lake the single-year areas, trend, emergence year and climate share are not reliable; the API passes `reliability` and `reliability_note` to the UI.

## Emergence censoring
`emergence()` now returns `censored_at_ref_end` (+ `censored_note`): true when the emergence year is the first post-reference year, i.e. the Sen line was already outside the reference band when the reference period ended, so the real emergence year is earlier or equal. True for Burdur (1997) and Akşehir (1997); false for Eğirdir (2004) and Van (2017). Read 1997 as "by 1997".

## Climate share wording
`climate.json` decomposition now has `interpretable`, `ci_includes_zero`, `interpretation_flags` and `wording`. Not interpretable ("not computable" in the UI): Burdur and Van (no reference skill, share outside 0-1; Van also < 3 % loss) and Akşehir (new flag `unreliable_area_series`; its 0.62 [0.34, 0.91] must not be read as a result). Eğirdir is interpretable but `ci_includes_zero = true` (0.05 [-0.44, 0.49]): the climate share is not distinguishable from 0 and no climate effect should be claimed. Pooled LST warming is exposed next to the Landsat-5-only rate with the sensor-break caveat (`warming_sensor_break_caveat` in `/api/lakes`).

## Lake index (identify)
`data/index/lakes.geojson` (1.7 MB, 1,314 lakes): the 4 precomputed analysis polygons + Natural Earth 10m lakes >= 5 km2 (public domain, 2.3 MB zip) simplified to 0.004 deg. HydroLAKES polygons (>= 50 km2 would be ideal) were NOT used: the polygon zip is ~820 MB and was impractical in this run; `build_lake_index.py --hydrolakes <shp>` reads it if present (untested on the real file). Natural Earth is incomplete for small lakes, so most small lakes (including shallow ones like Akşehir-type lakes) are not identifiable except the precomputed ones.

## On-demand analysis (unverified)
Custom results are written to `data/custom/<id>/` (gitignored), first every 5th year 1985 -> latest complete year, then the gap years, and are always labelled `unverified: true`. No climate decomposition is computed for them (`climate_interpretable: false`). The Landsat path of the runner is NOT exercised by the offline tests (mocked `analyze_year` / `detect`); only the code shared with the precompute is covered by Stage 1-3 runs.

## Stage 6: global reference lakes (Ring 2)
Run 2026-11-14 with `backend.scripts.precompute` + `backend.scripts.analyze` (code: this branch). Per-lake table made by `tools/ref_table.py` from the committed data. Trend = Hamed-Rao modified Mann-Kendall + Sen slope on the valid years (valid_frac >= 0.8), in % of the 1985-1990 mean (or the first 3 valid years where no 1985-90 year exists) per decade. "Ours" = Mann-Kendall direction at p < 0.05, else "stable" (no significant trend).

| Lake | Country | Res (m) | Cadence | Valid yrs | Area first -> last (km2) | Trend %/decade | p | Ours | Literature | Agree |
|---|---|---|---|---|---|---|---|---|---|---|
| Aral Sea (North / Small Aral) | KZ | 60 | every 2nd year, 1985-2025 (chosen to fit the time budget; unobserved years are not interpolated) | 17 | 3094 (1987) -> 3150 (2025) | 1.39 | 0.45 | stable | increase | NO |
| Aral Sea (South / Large Aral) | KZ/UZ | 240 | every 3rd year, 1985-2025 (chosen to fit the time budget; unobserved years are not interpolated) | 12 | 38291 (1988) -> 3726 (2025) | -24.07 | 8e-06 | decline | decline | yes |
| Balkhash | KZ | 120 | every 3rd year, 1985-2025 (chosen to fit the time budget; unobserved years are not interpolated) | 8 | 15901 (1994) -> 16746 (2025) | n/a | n/a | n/a | mixed | n/a |
| Dead Sea | IL/JO | 60 | every year, 1985-2025 | 38 | 687 (1985) -> 593 (2025) | -3.36 | 9e-06 | decline | decline | yes |
| Great Salt Lake | US | 120 | every 2nd year, 1985-2025 (chosen to fit the time budget; unobserved years are not interpolated) | 20 | 6187 (1985) -> 3901 (2025) | -9.93 | <1e-6 | decline | decline | yes |
| Lake Chad | TD/NE/NG/CM | 60 | every year, 2013-2025 (series starts late: no earlier Landsat 5 scenes in the archive) | 13 | 392 (2013) -> 399 (2025) | 0.55 | 0.54 | stable | mixed | n/a |
| Lake Mead | US | 60 | every year, 1985-2025 | 40 | 591 (1985) -> 285 (2025) | -14.21 | <1e-6 | decline | decline | yes |
| Poopo | BO | 60 | every year, 1985-2025 | 35 | 2675 (1985) -> 1674 (2025) | -15.25 | 0.0016 | decline | decline | yes |
| Qinghai | CN | 60 | every 2nd year, 1985-2025 (chosen to fit the time budget; unobserved years are not interpolated) | 18 | 4323 (1987) -> 4528 (2025) | 1.18 | 0.32 | stable | increase | NO |
| Sevan | AM | 60 | every year, 1985-2025 | 37 | 1245 (1985) -> 1262 (2025) | 0.45 | 0.021 | increase | mixed | n/a |
| Titicaca | PE/BO | 120 | every 2nd year, 1985-2025 (chosen to fit the time budget; unobserved years are not interpolated) | 20 | 8260 (1985) -> 7630 (2025) | -2.85 | 3.8e-05 | decline | stable | NO |
| Tuz Golu | TR | 60 | every year, 1985-2025 | 39 | 1768 (1985) -> 1503 (2025) | -4.29 | 0.0027 | decline | decline | yes |
| Urmia | IR | 120 | every 2nd year, 1985-2025 (chosen to fit the time budget; unobserved years are not interpolated) | 20 | 4800 (1985) -> 2707 (2025) | -14.33 | 3e-06 | decline | decline | yes |
| Akşehir | TR | 30 | every year | 39 | 300 (1985) -> 0 (2025) | -28.29 | <1e-6 | decline | - | n/a |
| Burdur | TR | 30 | every year | 40 | 206 (1985) -> 116 (2025) | -10.54 | 3e-06 | decline | - | n/a |
| Eğirdir | TR | 60 | every year | 40 | 471 (1985) -> 412 (2025) | -1.22 | 0.0045 | decline | - | n/a |
| Van | TR | 60 | every year | 36 | 3556 (1986) -> 3532 (2025) | -0.32 | 0.0073 | decline | - | n/a |

Notes on the table
- Cadence: lakes with a coarser cadence were run every 2nd or 3rd year (plus 2025) because the full annual run of 13 lakes did not fit the time budget; unobserved years are not interpolated. Resolution is adaptive by polygon area (30 m under 500 km2, 60 m under 5,000 km2, else 120 m) with an override to 240 m for the South Aral (about 40,000 km2). Time-window: 1 Aug - 30 Sep, except Tuz Golu (15 Mar - 15 May, see below).
- "Valid yrs" are years with >= 80 % valid pixels in the analysis polygon; early Landsat 5 coverage is sparse outside Europe/North America (Poopo, Dead Sea, Balkhash, Aral have missing years).
- The badge "validated" is given to the Turkish lakes and to reference lakes whose direction matches the literature direction (column Agree = yes). Lakes with literature "mixed" or direction "n/a" get no badge and no agreement test. On-demand lakes stay "unverified".

### Agreement and conflicts, with possible reasons (not tested unless stated)
- Agree: Urmia, Aral South, Great Salt Lake, Lake Mead, Poopo, Tuz Golu, Dead Sea (all declines; Tuz Golu uses a spring window).
- Aral North: literature says increase after the 2005 Kokaral dam; we find no significant trend (p = 0.45) from 1987 to 2025. Possible reasons: the 1985-90 baseline is already about 3,100 km2 (before the sea fell apart), so recovery means returning to the baseline rather than exceeding it; dike failure and rebuild; every 2nd year cadence; the area is measured inside the 1985-90 polygon, so any growth beyond it is not counted. Inconclusive (our trend is not significant); no badge.
- Qinghai: literature says increase since about 2002-2004; we find +1.2 %/decade, p = 0.32 (not significant) over 1987-2025 with 18 valid years. Possible reasons: the first half of the record contains the pre-2004 shrinkage so a single monotonic trend test is weak, 2-year cadence, 60 m, change is only about +5 % in area. Direction is positive but not significant; inconclusive, no badge.
- Titicaca (control): the literature direction "stable" is an unverified expectation, not a confirmed conflict. We find a significant decline of about 2.9 %/decade (8,260 km2 in 1985 to 7,630 km2 in 2025), but the literature direction used was "stable". Possible reasons: the 1985-86 start is a high stand of the lake, level drops in the recent drought years, reeds/shallow bays at 120 m, Aug-Sep window; this is a genuine conflict with the control expectation and the lake is flagged so, no badge. Titicaca should not be used as a "stable" control without this caveat.
- Lake Chad: series only 2013-2025 (13 valid years): the Planetary Computer Landsat 5/8/9 collection has no Aug-Sep scenes over the lake before 2013 (STAC searches for 1985, 1987, ..., 2010 returned 0 items), and Landsat 7 is excluded by design. Open-water area about 390-400 km2 inside the 1985-1990 detection polygon, no trend (p = 0.54). Literature "mixed", so no agreement test. Vegetation/flooding (MNDWI limitation) means the number is a lower bound.
- Sevan: significant but small increase (+0.45 %/decade); literature "mixed" (historic drawdown, recovery since the early 2000s), no agreement test.
- Balkhash: only 8 valid years (1994-2025, every 3rd year, 120 m), fewer than the 10 needed for a trend test, so no trend and no agreement test is reported. Coverage before 1994 is too sparse (Landsat 5 downlink).
- Dead Sea: a decline of 687 km2 (1985) to 593 km2 (2025) inside the polygon; southern evaporation ponds are excluded only if not connected to the main body (see note on the lake page).

### Method limitations by lake (also shown on each lake page)
Chad (vegetation, rising-season window), Poopo (shallow, turbid, salt crust), Tuz Golu (salt crust and seasonality; spring window), Great Salt Lake / Urmia / Dead Sea (salt and evaporation ponds may count as water; only the connected component is kept), Titicaca (reeds in shallow bays), Balkhash and Aral (very large: coarse resolution, partial scene coverage, boundary between North and South Aral at 46.1 N is approximate). Transboundary lakes (Aral, Chad, Dead Sea, Titicaca) are described with data only; no statement is made about responsibility.

### Engineering notes
- Dead Sea 2022: one Landsat 9 scene (LC09_L2SP_174038_20220806_02_T1) returns HTTP 403 on its QA_PIXEL asset (checked directly with rasterio; the other assets open), which made the whole year fail with a RasterioIOError. An earlier note blamed expired SAS tokens; that was wrong for this case (the token was still valid). The scene is now excluded (`exclude_items` in `backend/core/lakes.py`, listed in meta.json) and 2022 was recomputed from the remaining scene (599.1 km2, 1 scene). A test now checks that no committed series.json has an error row or a signed-URL fragment.
- The first Balkhash run also failed with "Chunk and warp failed"; I assumed token expiry and made `search_items` drop cached SAS tokens expiring within 20 min. The rerun succeeded, but I did not separately prove that expiry was the cause.
- Climate decomposition needs >= 8 consecutive reference pairs in 1985-1999, so it is not computable for lakes with 2nd/3rd-year cadence or late starts (climate.json has decomposition ok=false with the reason). HydroBASINS was only available for the eu region; for lakes outside it a 25 km buffer basin is used and flagged (`basin.fallback`).

### Literature directions used (general direction only, no numeric comparison)
Searches run 2026-11-14 (WebSearch; page content treated as data). "Checked" = a search result snippet/abstract supported the direction; I did not read every full paper. "Unverified" = no source found in the searches.

| Lake | General direction | Source actually seen | Status |
|---|---|---|---|
| Urmia | decline | Landsat-based studies: area 4,346.7 km2 (2001) -> 2,285.8 km2 (2015) -> 3,705.9 km2 (2019) (magiran.com/paper/2111816); lake shrank by about 202,000 ha 1987-2020 per Naboureh et al. 2021 as quoted in a review (oesr.thanhdo.edu.vn, 2026 PDF) | checked (snippets); partial recovery after 2015 noted |
| Aral Sea (South) | decline | Pekel et al. 2016, Nature 540:418-422 (doi 10.1038/nature20584): Aral Sea is the largest single permanent-water loss, >70 % of global net loss in Middle East and Central Asia | checked (summary pages) |
| Aral Sea (North) | increase / partial recovery | Kokaral dam finished Aug 2005; news/government reports of surface-area growth of about 36 % over 20 years and of a dike failure and rebuild from 2022 (centralasiaclimateportal.org, astanatimes.com, en.wikipedia.org/wiki/Dike_Kokaral) | checked at news level only |
| Great Salt Lake | decline | Record low 5 Jul 2022 (USGS-based news, phys.org 2022-07); lake dropped about 22 ft since 1986 (CNN/KVIA 2022-07-06); GRL 2025 study: tributary streamflow decline about two-thirds of volume loss (sciencedaily 2025-01-21) | checked |
| Lake Mead | decline | Level down about 140-160 ft since 2000 (SNWA drought page; Smithsonian 2022 "lowest since 1930s") | checked (level, not area) |
| Lake Chad | mixed | Open-water area 1,240-2,230 km2 over 2003-2016 with a slight increase (PMC6069056); long-term loss vs 1960s (conference abstracts); numbers depend on whether flooded vegetation is counted | checked, direction "mixed" so no agreement test |
| Poopó | decline (episodic desiccation) | Satge et al. 2017, Remote Sensing: 26-year Landsat record 1990-2015, lake dried out in 2015, droughts 1994/95/2015 | checked |
| Titicaca | stable (strong interannual and multidecadal variability, no long-term trend asserted) | Frontiers Climate 2023 (fclim.2023.1325224) on level variability; no source found stating "no trend" | UNVERIFIED as "stable"; treated as control |
| Balkhash | mixed | NASA Earth Observatory: 70-80 % of inflow from the Ili, inflow reduced since the Kapchagay reservoir (1970); no area time series found | UNVERIFIED (direction) |
| Sevan | mixed (historic drawdown, level recovery since the early 2000s) | Armenian news/government pages report rising level (ecolur.org, armenpress.am, arka.am); no peer-reviewed analysis seen | checked at news level only |
| Tuz Golu | decline | Landsat 5/8 study 2000-2020 (TURJAF 2023, agrifoodscience.com/index.php/TURJAF/article/view/4730) reports decrease of the water surface; Springer s10113-020-01656-z links 32-year shrinkage to NAO/AO | checked (abstracts) |
| Qinghai | increase | Ling et al. 2024, Remote Sensing 16:129: area expanded 1986-2022 (about 2.89 km2/yr), significant increase from about 2002; Frontiers Earth Sci 2022 (feart.2022.1007384) | checked |
| Dead Sea | decline | Level falling about 1.2 m per year, 1.15 m/yr average 1993-2009 (Globes; Yale e360); surface area follows | checked (level; area follows with bathymetry) |
