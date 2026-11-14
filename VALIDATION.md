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
