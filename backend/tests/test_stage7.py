"""Stage 7 (demo reliability): offline serving of cached live data, demo-cache seeding, sample job replay.
No real network: either mocked fetchers or the socket-level offline simulation (backend.core.offline)."""
import json
import os
import socket
import time

import pytest
from fastapi.testclient import TestClient

from backend.api import live_cache, store
from backend.api.main import create_app
from backend.api.store import Settings
from backend.core import offline


@pytest.fixture
def net_off():
    offline.block_network()
    yield
    offline.unblock_network()


def good(name, **kw):
    return dict(source=name, ok=True, fetched_utc="2026-01-01T00:00:00+00:00", **kw)


def seed(path, lake_id):
    os.makedirs(path, exist_ok=True)
    ent = {n: dict(good=good(n, area_km2=1.0), good_ts=1000.0) for n in ("landsat", "swot", "precip")}
    with open(os.path.join(path, f"{lake_id}.json"), "w") as f:
        json.dump(ent, f)


def mk(tmp_path, **kw):
    return Settings(custom_dir=str(tmp_path / "custom"), cache_dir=str(tmp_path / "cache"), demo_dir=str(tmp_path / "demo"),
                    jobs_db=str(tmp_path / "jobs.sqlite"), start_worker=False, sample_delay_s=0, **kw)


def test_offline_blocks_external_but_not_loopback(net_off):
    with pytest.raises(OSError):
        socket.create_connection(("planetarycomputer.microsoft.com", 443), timeout=2)
    with pytest.raises(OSError):
        socket.create_connection(("93.184.216.34", 80), timeout=2)
    with pytest.raises(ConnectionRefusedError):          # loopback is allowed through (nothing listens on port 9)
        socket.create_connection(("127.0.0.1", 9), timeout=2)


def test_all_precomputed_lakes_serve_stale_cache_with_real_fetchers_offline(tmp_path, net_off):
    """Every precomputed lake with an existing (old) cache: real fetchers fail (no network) -> last good result, stale: true."""
    st = mk(tmp_path)
    c = TestClient(create_app(st))
    lakes = c.get("/api/lakes").json()["lakes"]
    assert len(lakes) >= 17
    for lk in lakes:
        seed(st.cache_dir, lk["id"])
    t0 = time.time()
    for lk in lakes:
        r = c.get(f"/api/lakes/{lk['id']}/live")
        assert r.status_code == 200, lk["id"]
        j = r.json()
        assert j["stale"] is True, lk["id"]
        for name in ("landsat", "swot", "precip"):
            card = j["cards"][name]
            assert card["ok"] and card["stale"] and card["cached"] and card["refresh_error"], (lk["id"], name, card)
            assert card["area_km2"] == 1.0
    assert time.time() - t0 < 60


def test_stale_cache_is_not_refetched_for_a_while_after_a_failed_refresh(tmp_path):
    st = mk(tmp_path)
    LID = store.record(st, "burdur")["meta"]["lake_id"]
    seed(st.cache_dir, LID)
    calls = []

    def boom(cfg):
        calls.append(1)
        raise ConnectionError("down")
    live_cache.FETCHERS, orig = {n: boom for n in live_cache.FETCHERS}, live_cache.FETCHERS
    try:
        meta = store.record(st, "burdur")["meta"]
        a = live_cache.get_live(st, LID, meta, now=2_000_000.0)
        n1 = len(calls)
        b = live_cache.get_live(st, LID, meta, now=2_000_010.0)
    finally:
        live_cache.FETCHERS = orig
    assert n1 == 3 and len(calls) == 3                      # second request: no network attempt
    assert a["stale"] and b["stale"] and b["cards"]["landsat"]["stale"]


def test_demo_cache_seeds_empty_live_cache_and_gibs_snapshot(tmp_path, net_off):
    st = mk(tmp_path)
    LID = store.record(st, "burdur")["meta"]["lake_id"]
    seed(st.demo_dir, LID)
    os.makedirs(os.path.join(st.demo_dir, "gibs"))
    open(os.path.join(st.demo_dir, "gibs", LID + ".jpg"), "wb").write(b"\xff\xd8\xff\xd9")
    c = TestClient(create_app(st))
    j = c.get(f"/api/lakes/{LID}/live").json()
    assert j["cards"]["landsat"]["stale"] and j["cards"]["landsat"]["ok"]
    assert os.path.exists(os.path.join(st.cache_dir, LID + ".json"))          # seeded copy becomes the live cache
    assert j["cards"]["gibs"]["snapshot_url"] == f"/api/lakes/{LID}/snapshot.jpg"
    r = c.get(f"/api/lakes/{LID}/snapshot.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert c.get("/api/lakes/van/snapshot.jpg").status_code == 404


def test_sample_job_replays_precomputed_lake_and_is_labelled(tmp_path):
    st = mk(tmp_path)
    app = create_app(st)
    c = TestClient(app)
    r = c.post("/api/analyze", json={"sample": "sevan"})
    assert r.status_code == 202 and r.json()["sample"] is True and r.json()["lake_id"] == "sample-sevan"
    app.state.jobs.run_pending()
    assert c.get(f"/api/jobs/{r.json()['job_id']}").json()["status"] == "done"
    d = c.get("/api/lakes/sample-sevan").json()
    a = d["analysis"]
    assert a["sample"] is True and a["status"] == "done" and a["unverified"] is True and "PRE-COMPUTED SAMPLE" in a["note"]
    assert d["unverified"] and "sample" in d["summary"]["name"]
    assert len(d["series"]) == len(c.get("/api/lakes/sevan").json()["series"]) and d["stats"]
    assert "sample-sevan" not in {x["id"] for x in c.get("/api/lakes").json()["lakes"]}
    assert c.get("/api/lakes/sample-sevan/masks/1990?format=json").status_code == 200
    assert c.post("/api/analyze", json={"sample": "nonexistent"}).status_code == 404


def test_sample_progress_is_progressive(tmp_path):
    from backend.jobs.runner import run_sample
    st = mk(tmp_path)
    src = store.resolve(st, "sevan")[0]
    seen = []
    def prog(**kw):
        p = os.path.join(st.custom_dir, "sample-sevan", "series.json")
        seen.append((kw.get("phase"), len(json.load(open(p))["series"]) if os.path.exists(p) else 0))
    run_sample(st, "sample-sevan", dict(sample_of=src), prog)
    phases = [p for p, _ in seen]
    assert phases[0].startswith("preliminary") and phases[-1] == "filling gaps"
    assert [n for _, n in seen] == sorted(n for _, n in seen) and seen[-1][1] >= 38


def test_offline_basemap_countries(tmp_path):
    c = TestClient(create_app(mk(tmp_path)))
    r = c.get("/api/basemap/countries")
    assert r.status_code == 200
    names = {f["properties"]["name"] for f in r.json()["features"]}
    assert {"Turkey", "Armenia", "Chad", "United States of America"} <= names and len(r.content) < 1_200_000


def test_fail_text_has_no_signed_url_query():
    from backend.core import live
    e = live._fail("Landsat", RuntimeError("Failed to load https://x.blob.core.windows.net/a.TIF?st=1&sig=SECRET%3D:1 due to error"))
    assert "SECRET" not in e["error"] and "sig=" not in e["error"] and "a.TIF" in e["error"]


# Lakes that cannot have a cached demo entry (documented exception list; keep empty unless unavoidable).
DEMO_CACHE_EXCEPTIONS: set[str] = set()


def test_every_lake_has_demo_cache_json_and_snapshot():
    root = os.path.join(store.ROOT, "data")
    missing = []
    for d in sorted(os.listdir(os.path.join(root, "lakes"))):
        mp = os.path.join(root, "lakes", d, "meta.json")
        if not os.path.exists(mp) or d in DEMO_CACHE_EXCEPTIONS:
            continue
        lid = json.load(open(mp)).get("lake_id", d)
        if not os.path.exists(os.path.join(root, "demo_cache", f"{lid}.json")):
            missing.append(f"{d}: no demo_cache/{lid}.json")
        if not os.path.exists(os.path.join(root, "demo_cache", "gibs", f"{lid}.jpg")):
            missing.append(f"{d}: no demo_cache/gibs/{lid}.jpg")
    assert not missing, missing
