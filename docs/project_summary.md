# Metalimnion - project summary

**Team:** Augmented 6th. **Challenge:** Become An Earth Trend Detective!

## Problem
Lakes in semi-arid regions are shrinking, but public discussion mixes two questions: how much water is gone, and why.
Turkey's Lake Burdur lost about 41 % of its water surface between the 1985-1990 mean and the 2023-2025 mean in our
data (200.5 to 118.2 km2, `data/lakes/burdur/series.json`). Citizens and journalists need a quick, honest way to see
such trends for any lake and to see whether rainfall and evaporation could explain them.

## Solution
A web app with an interactive map. Click a lake (or draw one) and get a 1985-2025 water-area and temperature record
from Landsat, a trend test (Hamed-Rao Mann-Kendall + Sen slope), the year the loss becomes distinguishable from
natural variability, and a climate check that compares the observed loss with what NASA POWER (MERRA-2)
precipitation minus evaporation predicts. A compare page puts four Turkish lakes next to 13 global reference lakes
using normalised percentages. Everything is shown with p-values and confidence intervals, and unavailable results
say "no data" or "not computable" instead of a guess.

## NASA data used
- Landsat 5/8/9 Collection 2 Level-2 (USGS/NASA), water area and surface temperature.
- NASA POWER (MERRA-2): precipitation and evapotranspiration for the catchment.
- NASA GIBS: VIIRS daily and Blue Marble imagery.
- SWOT (Hydrocron): code for lake volume change is written and unit-tested, but real SWOT results are NOT shown
  because looking up lake ids needs an Earthdata login that the project did not use.
Other: HydroBASINS catchments, Natural Earth lakes and borders.

## Impact
The tool turns open satellite data into a plain-language, reproducible lake report. It tells apart lakes where climate
explains the loss from lakes where a large part is unexplained. It states clearly that an unexplained part is a sign,
not proof, of human impact. Known limits (sensor change in 2012, a land-evaporation proxy, low reliability for some
shallow lakes) are displayed in the app and in the README.

## Use of AI (disclosure)
The code and documentation of this project were written with AI assistance (Claude Code) under the team's direction.
The summaries shown in the app are generated from fixed templates filled with computed numbers; no AI model runs
inside the app at runtime. Data processing, statistics and validation were run on real data, and tests are in the repository.
