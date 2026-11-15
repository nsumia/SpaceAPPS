"""Forecast: offline, synthetic series only."""
import json

import numpy as np
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.store import Settings
from backend.core.stats import MIN_YEARS, forecast_area

YEARS = [y for y in range(1985, 2026) if y != 2012]


def rows(fn, years=YEARS, seed=1, noise=3.0):
    rng = np.random.default_rng(seed)
    return [dict(year=y, area_km2=max(fn(y) + rng.normal(0, noise), 0.0), valid_frac=1.0) for y in years]


def test_declining_lake_uses_a_trend_model_and_keeps_declining():
    f = forecast_area(rows(lambda y: 205 - 2.15 * (y - 1985)), ref_mean=200.0)
    assert f["ok"] and f["model"] in ("sen_full", "sen_recent") and f["interpretable"]
    assert f["years"][0] == 2026 and f["years"][-1] == 2040 and len(f["median"]) == 15
    assert -24 < f["slope_km2_per_decade"] < -19
    m = {x["year"]: x for x in f["milestones"]}
    assert abs(m[2040]["median_km2"] - (205 - 2.15 * 55)) < 6
    assert m[2040]["lo90_km2"] < m[2040]["median_km2"] < m[2040]["hi90_km2"] < f["last_observed_km2"]
    assert abs(m[2040]["median_pct_of_ref"] - 100 * m[2040]["median_km2"] / 200.0) < 0.1
    assert f["slope_ci90_km2_per_decade"][1] < 0 and not f["flags"]
    assert f["backtest"]["chosen_skill"] > 0.5 and f["backtest"]["mae_km2"]["persistence"] > f["backtest"]["mae_km2"][f["model"]]
    assert all(lo <= a <= b <= c <= hi for lo, a, b, c, hi in zip(f["lo90"], f["lo50"], f["median"], f["hi50"], f["hi90"]))


def test_stable_lake_falls_back_to_persistence_and_says_so():
    f = forecast_area(rows(lambda y: 500.0, noise=10.0, seed=0))
    assert f["ok"] and f["model"] == "persistence" and "no_skill_over_persistence" in f["flags"]
    assert f["slope_km2_per_decade"] is None and f["backtest"]["chosen_skill"] == 0.0
    assert abs(f["median"][-1] - 500) < 25
    for seed in range(1, 8):                 # pure noise never yields an unflagged trend, and the forecast stays flat
        g = forecast_area(rows(lambda y: 500.0, noise=10.0, seed=seed))
        assert g["flags"] and abs(g["median"][-1] - 500) < 25
    assert (f["hi90"][-1] - f["lo90"][-1]) > (f["hi90"][0] - f["lo90"][0])      # the band widens with the horizon


def test_band_holds_about_90_percent_of_held_out_years():
    hit = tot = 0
    for s in range(25):
        r, e, rs = np.random.default_rng(s), 0.0, []
        for y in range(1985, 2036):
            e = 0.5 * e + r.normal(0, 4)
            rs.append(dict(year=y, area_km2=200 - 1.5 * (y - 1985) + e, valid_frac=1.0))
        f = forecast_area(rs[:41], horizon_year=2035, seed=s)
        for k in range(len(f["years"])):
            tot += 1
            hit += f["lo90"][k] <= rs[41 + k]["area_km2"] <= f["hi90"][k]
    assert 0.78 <= hit / tot <= 0.98


def test_no_forecast_when_it_would_be_invented():
    assert forecast_area(rows(lambda y: 100.0), reliability="low")["reason"] == "unreliable_area_series"
    short = forecast_area(rows(lambda y: 100.0, years=YEARS[: MIN_YEARS - 1]))
    assert not short["ok"] and short["reason"] == "too_few_valid_years"
    bad = [dict(r, valid_frac=0.2) for r in rows(lambda y: 100.0)]
    assert not forecast_area(bad)["ok"]
    assert forecast_area(rows(lambda y: 100.0), horizon_year=2025)["reason"] == "horizon_not_after_last_observation"


def test_never_negative_deterministic_and_sparse_cadence_flag():
    r = rows(lambda y: max(60 - 1.6 * (y - 1985), 0.5), noise=1.0)
    a, b = forecast_area(r), forecast_area(r)
    assert a == b and min(a["lo90"]) >= 0 and min(a["median"]) >= 0
    sparse = forecast_area(rows(lambda y: 900 - 6 * (y - 1985), years=list(range(1985, 2026, 2)), noise=8.0))
    assert sparse["ok"] and "sparse_cadence" in sparse["flags"] and sparse["years"][0] == 2026
    json.dumps(a)                                                          # plain Python types only


def test_api_serves_the_forecast(tmp_path):
    d = tmp_path / "lakes" / "demo"
    d.mkdir(parents=True)
    (d / "series.json").write_text(json.dumps(dict(lake="Demo", min_valid=0.8, series=rows(lambda y: 205 - 2.15 * (y - 1985)),
                                                   reliability=dict(reliability="ok"))))
    (d / "meta.json").write_text(json.dumps(dict(lake_id="demo", alias="demo", name="Demo", country="TR", seed=[30.0, 37.7])))
    st = Settings(lakes_dir=str(tmp_path / "lakes"), custom_dir=str(tmp_path / "custom"), jobs_db=str(tmp_path / "jobs.sqlite"),
                  index_path=str(tmp_path / "none.geojson"), start_worker=False, dist_dir=str(tmp_path / "nodist"))
    c = TestClient(create_app(st))
    full = c.get("/api/lakes/demo").json()
    assert full["forecast"]["ok"] and full["forecast"]["horizon_year"] == 2040
    f = c.get("/api/lakes/demo/forecast?horizon=2030").json()
    assert f["years"][-1] == 2030 and [m["year"] for m in f["milestones"]] == [2030]
    assert c.get("/api/lakes/demo/forecast?horizon=2100").status_code == 422
    assert c.get("/api/lakes/nope/forecast").status_code == 404
