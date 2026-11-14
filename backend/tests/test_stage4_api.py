"""Stage 4 API tests. Offline: real committed lake records, everything else synthetic/mocked (no network, no Landsat)."""
import json
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient
from rasterio.transform import Affine
from shapely.geometry import box, mapping

from backend.api import live_cache, store
from backend.api.jobs import JobManager
from backend.api.main import create_app
from backend.api.store import Settings
from backend.core import quality
from backend.core.stats import emergence
from backend.jobs import runner as jr

SMALL = {"type": "Polygon", "coordinates": [[[30.0, 37.0], [30.2, 37.0], [30.2, 37.2], [30.0, 37.2], [30.0, 37.0]]]}
HUGE = mapping(box(25, 30, 35, 40))


def fake_runner(jid, lake_id, request, progress):
    progress(phase="fake", current_year=2000, progress=50.0)


@pytest.fixture
def st(tmp_path):
    return Settings(custom_dir=str(tmp_path / "custom"), cache_dir=str(tmp_path / "cache"),
                    jobs_db=str(tmp_path / "jobs.sqlite"), start_worker=False)


@pytest.fixture
def client(st):
    app = create_app(st, runner=fake_runner)
    return TestClient(app)


def test_lakes_contract(client):
    r = client.get("/api/lakes")
    assert r.status_code == 200
    lakes = {x["alias"]: x for x in r.json()["lakes"]}
    assert set(lakes) == {"burdur", "van", "aksehir", "egirdir"}
    b = lakes["burdur"]
    for k in ("id", "name", "country", "centre", "total_loss_pct", "trend_pct_per_decade", "trend_p", "emergence_year",
              "emergence_censored_at_ref_end", "warming_c_per_decade", "warming_sensor_break_caveat",
              "climate_explained_share", "climate_interpretable", "group", "validated", "reliability"):
        assert k in b, k
    assert b["group"] == "turkey" and b["validated"] is True and lakes["van"]["validated"] is False
    assert 35 < b["total_loss_pct"] < 50 and b["trend_pct_per_decade"] < 0 and 36 < b["centre"][1] < 39
    assert b["emergence_censored_at_ref_end"] is True            # 1997 = first post-reference year
    assert lakes["egirdir"]["emergence_censored_at_ref_end"] is False
    # not computable flags (Stage 3 review item 3)
    assert lakes["burdur"]["climate_interpretable"] is False and lakes["van"]["climate_interpretable"] is False
    assert lakes["aksehir"]["climate_interpretable"] is False and lakes["aksehir"]["reliability"] == "low"
    assert lakes["egirdir"]["climate_interpretable"] is True and lakes["egirdir"]["climate_ci_includes_zero"] is True
    assert lakes["burdur"]["reliability"] == "ok"


def test_lake_detail_alias_id_and_404(client):
    a = client.get("/api/lakes/burdur").json()
    b = client.get(f"/api/lakes/{a['summary']['id']}").json()
    assert a["summary"]["id"] == b["summary"]["id"] and len(a["series"]) == 41
    for k in ("series", "stats", "climate", "swot", "meta", "reliability", "volume", "unverified"):
        assert k in a
    assert a["unverified"] is False and a["volume"] is None
    r = client.get("/api/lakes/nope")
    assert r.status_code == 404 and "unknown lake" in r.json()["detail"]


def test_masks_png_json_and_404(client):
    r = client.get("/api/lakes/burdur/masks/2020")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    assert len(json.loads(r.headers["x-mask-coordinates"])) == 4
    j = client.get("/api/lakes/burdur/masks/2020?format=json").json()
    w, s, e, n = j["bounds"]
    assert 29.9 < w < e < 30.5 and 37.5 < s < n < 37.95 and j["png_data_uri"].startswith("data:image/png;base64,")
    assert client.get("/api/lakes/burdur/masks/2012").status_code == 404      # no scenes that year
    assert client.get("/api/lakes/burdur/masks/1900").status_code == 404
    assert client.get("/api/lakes/nope/masks/2020").status_code == 404


def _counting(name, calls, ok=True):
    def f(cfg):
        calls.append(name)
        return {"source": name, "ok": True, "fetched_utc": "t", "v": len(calls)} if ok else {"source": name, "ok": False, "error": "down"}
    return f


def test_live_cache_fresh_stale_and_independent(st, monkeypatch):
    meta = store.record(st, "burdur")["meta"]
    calls = []
    monkeypatch.setattr(live_cache, "FETCHERS", {n: _counting(n, calls) for n in ("landsat", "swot", "precip")})
    r1 = live_cache.get_live(st, "L1", meta, now=1000)
    assert calls == ["landsat", "swot", "precip"] and not r1["stale"] and r1["cards"]["landsat"]["cached"] is False
    assert r1["cards"]["gibs"]["image_url"].startswith("https://gibs.earthdata.nasa.gov/wms/")
    r2 = live_cache.get_live(st, "L1", meta, now=1000 + 3600)             # within TTL: no network
    assert len(calls) == 3 and r2["cards"]["landsat"]["cached"] and r2["cards"]["landsat"]["age_s"] == 3600
    # TTL over, landsat down, swot throws, precip fine -> stale only where it failed; precip refreshed
    monkeypatch.setattr(live_cache, "FETCHERS", {"landsat": _counting("landsat", calls, ok=False),
                                                  "swot": lambda c: 1 / 0, "precip": _counting("precip", calls)})
    r3 = live_cache.get_live(st, "L1", meta, now=1000 + 4 * 3600)
    assert r3["stale"] is True
    assert r3["cards"]["landsat"]["stale"] is True and r3["cards"]["landsat"]["ok"] is True       # last good result
    assert r3["cards"]["landsat"]["refresh_error"] == "down" and r3["cards"]["swot"]["stale"] is True
    assert r3["cards"]["precip"]["stale"] is False and r3["cards"]["precip"]["cached"] is False


def test_live_never_good_returns_failure_and_backs_off(st, monkeypatch):
    meta = store.record(st, "burdur")["meta"]
    calls = []
    monkeypatch.setattr(live_cache, "FETCHERS", {"landsat": _counting("landsat", calls, ok=False)})
    r = live_cache.get_live(st, "L2", meta, now=0)
    assert r["cards"]["landsat"]["ok"] is False and r["stale"] is False
    live_cache.get_live(st, "L2", meta, now=60)
    assert calls == ["landsat"]                         # not hammered within RETRY_FAIL_S
    live_cache.get_live(st, "L2", meta, now=1000)
    assert calls == ["landsat", "landsat"]


def test_live_endpoint(client, monkeypatch):
    calls = []
    monkeypatch.setattr(live_cache, "FETCHERS", {n: _counting(n, calls) for n in ("landsat", "swot", "precip")})
    a = client.get("/api/lakes/burdur/live").json()
    b = client.get("/api/lakes/burdur/live").json()
    assert set(a["cards"]) == {"landsat", "swot", "precip", "gibs"} and len(calls) == 3 and b["cards"]["landsat"]["cached"]
    assert client.get("/api/lakes/nope/live").status_code == 404


def test_identify(client):
    r = client.get("/api/identify?lon=42.95&lat=38.65")
    assert r.status_code == 200
    j = r.json()
    assert j["alias"] == "van" and j["precomputed"] and j["computed"] and j["polygon"]["type"] in ("Polygon", "MultiPolygon")
    assert client.get("/api/identify?lon=-30&lat=0").status_code == 404
    assert client.get("/api/identify?lon=999&lat=0").status_code == 422
    sup = client.get("/api/identify?lon=-87.5&lat=47.7").json()                  # Lake Superior, not precomputed
    assert "Superior" in sup["name"] and sup["computed"] is False and sup["id"].startswith("custom-")


def test_analyze_validation_and_direct_result(client):
    r = client.post("/api/analyze", json={"lake_id": "burdur"})
    assert r.status_code == 200 and r.json()["status"] == "done" and r.json()["job_id"] is None
    assert client.post("/api/analyze", json={}).status_code == 422
    assert client.post("/api/analyze", json={"lake_id": "x", "polygon": SMALL}).status_code == 422
    big = client.post("/api/analyze", json={"polygon": HUGE})
    assert big.status_code == 422 and "20,000" in big.json()["detail"] and "smaller" in big.json()["detail"]
    assert client.post("/api/analyze", json={"polygon": {"type": "Point", "coordinates": [0, 0]}}).status_code == 422
    assert client.post("/api/analyze", json={"lake_id": "custom-unknown"}).status_code == 404


def test_job_dedup_and_status(client, st):
    a = client.post("/api/analyze", json={"polygon": SMALL})
    assert a.status_code == 202 and a.json()["status"] == "queued" and a.json()["attached_to_existing"] is False
    b = client.post("/api/analyze", json={"polygon": {"type": "Feature", "properties": {}, "geometry": SMALL}})
    assert b.json()["job_id"] == a.json()["job_id"] and b.json()["attached_to_existing"] is True and a.json()["unverified"]
    jid = a.json()["job_id"]
    assert client.get(f"/api/jobs/{jid}").json()["status"] == "queued"
    client.app.state.jobs.run_pending()
    j = client.get(f"/api/jobs/{jid}").json()
    assert j["status"] == "done" and j["progress"] == 100.0 and j["error"] is None
    assert client.get("/api/jobs/zzz").status_code == 404


def test_jobs_max_two_concurrent_and_failure(tmp_path):
    def boom(jid, lake, req, progress):
        raise RuntimeError("no scenes")
    m = JobManager(str(tmp_path / "j.sqlite"), boom, max_concurrent=2, start=False)
    ids = [m.submit(f"lake{i}", {})[0]["id"] for i in range(3)]
    c1, c2, c3 = m._claim(), m._claim(), m._claim()
    assert c1 and c2 and c3 is None                  # third waits while 2 run
    m._run(c1)
    assert m._claim()["lake_id"] == "lake2"
    assert m.get(ids[0])["status"] == "failed" and "no scenes" in m.get(ids[0])["error"]
    # a restart marks orphaned running jobs failed
    m2 = JobManager(str(tmp_path / "j.sqlite"), boom, start=False)
    assert m2.get(ids[1])["status"] == "failed" and "restarted" in m2.get(ids[1])["error"]


def fake_area(y):
    return 100.0 - (y - 1985) + 0.7 * ((y * 7) % 5 - 2)      # noise: a perfectly linear series divides by zero in pymannkendall


def fake_analysis(st, end_year=2010):
    poly = box(30.0, 37.0, 30.2, 37.2)
    seen = []

    def detect(cat, bbox, seed, max_cloud):
        return poly, dict(polygon_km2=500.0, component_km2=400.0)

    def year(y):
        seen.append(y)
        w = np.zeros((6, 6), bool); w[:3] = True
        return dict(year=y, error=None, area_km2=fake_area(y), valid_frac=1.0, lst_c=20.0 + 0.1 * (y % 3) + 0.03 * (y - 1985), lst_px=9, n_scenes=3,
                    n_items=3, latest_scene=f"{y}-09-01", water=w, valid=np.ones((6, 6), bool),
                    transform=Affine(30, 0, 300000, 0, -30, 4100000))
    jr.run_analysis(st, "custom-testlake", dict(polygon=mapping(poly), name="Test"), lambda **k: None,
                    catalog=object(), analyze_year=year, detect=detect, end_year=end_year)
    return seen


def test_runner_every_fifth_year_first_then_gaps_and_unverified(client, st):
    first, rest = jr.plan_years(1985, 2010)
    assert first == [1985, 1990, 1995, 2000, 2005, 2010] and 1986 in rest and len(first) + len(rest) == 26
    seen = fake_analysis(st)
    assert seen[:6] == first and sorted(seen) == list(range(1985, 2011))
    d = client.get("/api/lakes/custom-testlake").json()
    assert d["unverified"] is True and d["summary"]["group"] == "custom" and d["summary"]["unverified"] is True
    assert d["analysis"]["status"] == "done" and len(d["series"]) == 26 and d["stats"]["area"]["trend"] == "decreasing"
    assert client.get("/api/lakes/custom-testlake/masks/1990").status_code == 200
    assert any(x["id"] == "custom-testlake" for x in client.get("/api/lakes").json()["lakes"])
    # computed custom lake is returned directly by analyze
    assert client.post("/api/analyze", json={"lake_id": "custom-testlake"}).json()["status"] == "done"


def test_compare_normalisation(client, st):
    fake_analysis(st)                                   
    r = client.get("/api/compare?ids=custom-testlake&metric=area_pct").json()
    s = r["series"]["custom-testlake"]
    assert r["base_period"] == [1985, 1990] and s["reference_mean"] == pytest.approx(np.mean([fake_area(y) for y in range(1985, 1991)]), abs=0.01)
    assert s["values"][0] == pytest.approx(100 * fake_area(1985) / s["reference_mean"], abs=0.01) and s["years"][0] == 1985
    ref_vals = [v for y, v in zip(s["years"], s["values"]) if y <= 1990]
    assert np.mean(ref_vals) == pytest.approx(100.0, abs=0.05)                  # 1985-1990 mean == 100 %
    lst = client.get("/api/compare?ids=custom-testlake,burdur&metric=lst_anomaly").json()
    lv = lst["series"]["custom-testlake"]
    assert np.mean([v for y, v in zip(lv["years"], lv["values"]) if y <= 1990]) == pytest.approx(0.0, abs=0.01) and "Landsat 5 -> 8" in " ".join(lst["notes"])
    bur = client.get("/api/compare?ids=burdur").json()["series"]["burdur"]
    assert bur["values"][0] > 99 and bur["values"][-1] < 70 and 2012 not in bur["years"]
    assert client.get("/api/compare?ids=burdur,nope").status_code == 404
    assert client.get("/api/compare?ids=a,b,c,d,e,f,g").status_code == 422
    assert client.get("/api/compare?ids=burdur&metric=bad").status_code == 422


def test_docs_and_openapi_paths(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/lakes", "/api/lakes/{lake_id}", "/api/lakes/{lake_id}/masks/{year}", "/api/lakes/{lake_id}/live",
              "/api/identify", "/api/analyze", "/api/jobs/{job_id}", "/api/compare", "/api/health"):
        assert p in paths, p


def test_quality_flags_volatile_series_only():
    ok = [dict(year=1985 + i, area_km2=200 - i, valid_frac=1.0) for i in range(30)]
    assert quality.assess(ok)["reliability"] == "ok"
    flip = [dict(year=1985 + i, area_km2=(0.0 if i % 2 else 100.0) if i > 8 else 290.0, valid_frac=1.0) for i in range(30)]
    q = quality.assess(flip)
    assert q["reliability"] == "low" and q["volatile_years"] and "NOT reliable" in q["note"]


def test_emergence_censored_at_ref_end_flag():
    y = np.arange(1985, 2026)
    steep = 300.0 - 6.0 * (y - 1985)                       # already far outside the reference band after 1996
    e = emergence(steep + np.where(y % 2, 0.5, -0.5), y)
    assert e["emerged"] and e["year"] == 1997 and e["censored_at_ref_end"] is True and "EARLIER" in e["censored_note"]
    gentle = 300.0 - 0.4 * (y - 1985) + np.where(y % 2, 2.0, -2.0)
    g = emergence(gentle, y)
    assert g["emerged"] and g["year"] > 1997 and g["censored_at_ref_end"] is False


def test_identify_separates_polygon_and_lake_area(client):
    j = client.get("/api/identify?lon=30.17&lat=37.75").json()
    assert "area_km2" not in j and j["polygon_area_km2"] > j["lake_area_km2"] > 0 and j["lake_area_year"] >= 2020
    b = {x["alias"]: x for x in client.get("/api/lakes").json()["lakes"]}["burdur"]
    assert b["latest_area_km2"] == j["lake_area_km2"]


def test_job_error_is_generic_and_runner_marks_failed(client, st, tmp_path):
    def boom(jid, lake, req, progress):
        raise RuntimeError("secret /home/x/path detail")
    app = create_app(st, runner=boom)
    c = TestClient(app)
    jid = c.post("/api/analyze", json={"polygon": SMALL}).json()["job_id"]
    app.state.jobs.run_pending()
    j = c.get(f"/api/jobs/{jid}").json()
    assert j["status"] == "failed" and "secret" not in str(j) and "log" in j["error"]
    assert "secret" in app.state.jobs.get(jid)["error"]            # detail kept server-side
    # real runner: failure after the output dir exists -> meta analysis.status == failed
    def bad(*a, **k):
        raise RuntimeError("no data")
    poly = box(30, 37, 30.1, 37.1)
    with pytest.raises(RuntimeError):
        jr.run_analysis(st, "custom-bad", dict(polygon=mapping(poly)), lambda **k: None, catalog=object(), detect=bad)
    import json as _j
    m = _j.load(open(f"{st.custom_dir}/custom-bad/meta.json"))
    assert m["analysis"]["status"] == "failed"
