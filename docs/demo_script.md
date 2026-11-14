# Demo script

All numbers come from the committed data (cited per line). Read the "not computable" and "low reliability" labels aloud:
they are part of the story, not a flaw.

Sources: `data/lakes/<alias>/series.json`, `climate.json`, and `GET /api/lakes` (computed from them).

## 30-second video (about 75 words)
1. (0-6 s) Map, zoom to Burdur, click. "Lake Burdur: 200 square kilometres in the late 1980s, 118 today."
   (ref mean 1985-90 = 200.5 km2, mean 2023-25 = 118.2 km2, -41.1 %; `burdur/series.json`)
2. (6-14 s) Area chart, trend line and emergence note. "Landsat shows a significant decline, p about 3e-6. But is it climate?"
3. (14-22 s) Switch to Urmia, then Aral South. "Same method on Urmia: 4,800 down to 2,707 square kilometres. Aral South: 38,291 in 1988 to 3,726."
   (`urmia/series.json` 1985 and 2025; `aral_south/series.json` 1988 and 2025; Aral at 240 m resolution)
4. (22-28 s) Compare page. "Compared as percentages, Burdur sits between Eğirdir and the big losers."
5. (28-30 s) "Click any lake. Real NASA data, honest limits." End card: Augmented 6th.

## 7-slide presentation
1. **Burdur's loss.** Map zoom, panel. Area 200.5 to 118.2 km2 (-41.1 %), Sen -21.1 km2/decade, p = 3.3e-6
   (`burdur/series.json`, stats.area). Check: our 1986 value 204.8 km2 vs Sabuncu 2020: 206 (VALIDATION.md).
2. **"Climate or human?" chart.** Burdur's split is NOT computable: the 1985-1999 correlation of area change with P-E is
   0.07 (weak skill), the flag says so (`burdur/climate.json`, decomposition.interpretable = false). Say this out loud,
   then show **Eğirdir**: observed loss since the 1999 base 47.6 km2, climate-predicted 2.5 km2, explained share 0.05,
   90 % CI [-0.44, 0.49] includes 0, so "no climate effect claimed" (`egirdir/climate.json`). Do NOT use Akşehir as the
   example: its series is low reliability (10 of 39 years volatile) and its split is not interpretable.
   Message: a residual is a sign, not proof, of human impact.
3. **Other lakes on the map.** Switch to Urmia (-14.3 %/decade) and Aral South (-24.1 %/decade, 240 m, coarse; every 3rd year).
   Neutral language for Aral. Show the "validated" badge basis: direction matches the literature. (`/api/lakes`)
4. **Türkiye in the compare scatter.** Normalised % per decade: Burdur -10.5, Akşehir -28.3 (low reliability), Eğirdir -1.2,
   Van -0.3, Tuz -4.3 (low reliability); Urmia -14.3, Great Salt Lake -9.9, Mead -14.2, Sevan +0.45 (`/api/lakes`
   trend_pct_per_decade). Mention the resolution note (30-240 m).
5. **Live cards.** Latest Landsat scene, POWER precipitation vs normal, VIIRS picture; stale/cached labels. SWOT shows "no data":
   needs Earthdata login. Be explicit about this.
6. **Select a new lake.** Use the button "Demo: replay a pre-computed sample" (Sevan: 1,244.9 to 1,263.0 km2, trend +0.45 %/decade,
   p = 0.021; `sevan/series.json`). Do NOT run a real new lake live: a real job (Lake Hazar in testing) took about 9 minutes.
   If asked about real runs: Hazar finished with 42 years, area ~77-79 km2, no trend, p = 0.77 (PR #7 description).
7. **Method, limits, team.** MNDWI, Hamed-Rao MK + Sen, emergence, P-E decomposition; limits: Landsat 5 to 8 sensor break
   (about 2.9 C step for Burdur), EVLAND is a land proxy, coarse large-lake cadence, SWOT unavailable. Team Augmented 6th.

## Pre-demo checklist
- [ ] Online, once: `.venv/bin/python -m backend.scripts.prefetch --demo` (must exit 0; SWOT warning is expected).
- [ ] `cd frontend && npm run build` (frontend/dist is not committed).
- [ ] Start one server: `.venv/bin/uvicorn backend.api.main:app --port 8000`; open http://127.0.0.1:8000.
- [ ] Offline test: restart the server with `LLD_OFFLINE=1`, check map (Offline basemap option), Burdur panel, Compare, sample job; then restart normally.
- [ ] `tools/run_tests.sh` green on the demo machine.
- [ ] Do not restart the server while a job runs: running jobs fail on restart.
- [ ] Known "no data" cards: Balkhash and Aral South Landsat "now", SWOT everywhere. Do not click those live.
- [ ] Browser zoom 100 %, language EN (TR available), screen recording of a backup run saved.
