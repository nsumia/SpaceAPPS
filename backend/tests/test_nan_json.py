"""Production bug: ValueError 'Out of range float values are not JSON compliant: nan' from starlette's JSONResponse.
Any NaN/Inf that reaches an API response (series rows of failed years, stats on odd series, live cards) must come out
as null, and nothing may be written to disk as NaN."""
import json
import math
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient
from rasterio.transform import Affine
from shapely.geometry import box, mapping

from backend.api import live_cache
from backend.api.main import create_app
from backend.api.store import Settings
from backend.core import jsonsafe
from backend.jobs import runner as jr

LAKE = "custom-83b6bba2"


@pytest.fixture
def st(tmp_path):
    return Settings(custom_dir=str(tmp_path / "custom"), lakes_dir=str(tmp_path / "lakes"), cache_dir=str(tmp_path / "cache"),
                    demo_dir=str(tmp_path / "demo"), jobs_db=str(tmp_path / "jobs.sqlite"), start_worker=False)


def _dirty_lake(st, area=lambda y: 100.0 - (y - 1985) + 0.7 * ((y * 7) % 5 - 2)):
    """A custom lake whose files contain NaN/Infinity literals (what json.dump(allow_nan=True) wrote before the fix)."""
    d = os.path.join(st.custom_dir, LAKE)
    os.makedirs(os.path.join(d, "masks"))
    rows = []
    for y in range(1985, 2026):
        rows.append(dict(year=y, area_km2=area(y), valid_frac=1.0, lst_c=20.0 + 0.03 * (y - 1985), lst_px=9, n_scenes=3,
                         error=None))
    rows[5].update(area_km2=float("nan"), lst_c=float("nan"))          # a cloudy year stored as NaN, not null
    rows[9].update(area_km2=float("inf"))
    rows[-1].update(valid_frac=float("nan"))
    stats = dict(area=dict(n=41, trend="decreasing", p=float("nan"), sen_slope_per_year=float("-inf"),
                           sen_slope_per_decade=float("nan"), intercept=1.0, intercept_year=1985, year_gaps=0,
                           first_year=1985, last_year=2025),
                 lst_all=None, lst_1985_2012=None, area_emergence=None)
    with open(os.path.join(d, "series.json"), "w") as f:
        json.dump(dict(lake="x", bbox=[30, 37, 30.2, 37.2], min_valid=0.8, series=rows, stats=stats,
                       reliability=dict(reliability="unknown", n_valid=40, note=float("nan"))), f)   # allow_nan default
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump(dict(lake_id=LAKE, name="Dirty", group="custom", bbox=[30, 37, 30.2, 37.2], seed=[30.1, 37.1],
                       analysis=dict(status="done", unverified=True, years_done=41, years_total=41)), f)


URLS = [f"/api/lakes", f"/api/lakes/{LAKE}", f"/api/lakes/{LAKE}/forecast", f"/api/lakes/{LAKE}/live",
        f"/api/compare?ids={LAKE}&metric=area_pct", f"/api/compare?ids={LAKE}&metric=lst_anomaly"]


def _no_nan(o):
    if isinstance(o, float):
        assert math.isfinite(o)
    elif isinstance(o, dict):
        [_no_nan(v) for v in o.values()]
    elif isinstance(o, list):
        [_no_nan(v) for v in o]


def test_every_json_endpoint_survives_nan_in_stored_files(st, monkeypatch):
    _dirty_lake(st)
    nan_card = lambda cfg: dict(ok=True, source="t", value=float("nan"), series=[1.0, float("inf")], note=None)
    monkeypatch.setattr(live_cache, "FETCHERS", {"landsat": nan_card, "swot": nan_card, "precip": nan_card})
    c = TestClient(create_app(st, runner=lambda *a, **k: None), raise_server_exceptions=True)
    for u in URLS:
        r = c.get(u)
        assert r.status_code == 200, (u, r.text[:200])
        json.loads(r.text, parse_constant=lambda s: pytest.fail(f"{u} emitted {s}"))
        _no_nan(r.json())
    body = c.get(f"/api/lakes/{LAKE}").json()
    assert body["series"][5]["area_km2"] is None            # NaN year is a gap, not a number


def test_nan_year_is_not_a_valid_year(st):
    from backend.api import store
    _dirty_lake(st)
    rows = store.record(st, LAKE)["series"]["series"]
    assert all(math.isfinite(r["area_km2"]) for r in store.valid_rows(rows, 0.8))


def test_nothing_is_written_to_disk_as_nan(st):
    poly = box(30.0, 37.0, 30.2, 37.2)

    def year(y):
        w = np.zeros((6, 6), bool); w[:3] = True
        bad = y in (1990, 2000)
        return dict(year=y, error=None, area_km2=np.float32("nan") if bad else 100.0 - (y - 1985) + 0.7 * ((y * 7) % 5 - 2),
                    valid_frac=1.0, lst_c=np.float64("nan") if bad else 20.0 + 0.03 * (y - 1985), lst_px=9, n_scenes=3,
                    n_items=3, latest_scene=f"{y}-09-01", water=w, valid=np.ones((6, 6), bool),
                    transform=Affine(30, 0, 300000, 0, -30, 4100000))
    jr.run_analysis(st, LAKE, dict(polygon=mapping(poly), name="T"), lambda **k: None, catalog=object(),
                    analyze_year=year, detect=lambda *a: (poly, dict(polygon_km2=500.0, component_km2=400.0)), end_year=2010)
    for name in ("series.json", "meta.json"):
        raw = open(os.path.join(st.custom_dir, LAKE, name)).read()
        assert not any(t in raw for t in ("NaN", "Infinity", '"nan"')), name
    c = TestClient(create_app(st, runner=lambda *a, **k: None))
    assert c.get(f"/api/lakes/{LAKE}").status_code == 200


def test_jsonsafe_sanitize_and_dump():
    o = dict(a=float("nan"), b=[np.float64("inf"), np.float32("nan"), np.int64(3), 1.5], c=np.array([1.0, np.nan]), d=(1, float("-inf")))
    assert jsonsafe.sanitize(o) == dict(a=None, b=[None, None, 3, 1.5], c=[1.0, None], d=[1, None])
    with pytest.raises(ValueError):
        json.dumps(float("nan"), allow_nan=False)
    assert jsonsafe.dumps(o) == json.dumps(dict(a=None, b=[None, None, 3, 1.5], c=[1.0, None], d=[1, None]))


def test_native_check_reports_missing_library_and_health_exposes_it(st, monkeypatch):
    from backend.core import native_check
    assert native_check.check() == {}                                   # this environment has every wheel working
    bad = native_check.check(("os", "definitely_not_a_module_xyz"))
    assert list(bad) == ["definitely_not_a_module_xyz"] and "ModuleNotFoundError" in bad["definitely_not_a_module_xyz"]
    monkeypatch.setattr(native_check, "check", lambda *a: {"rasterio": "ImportError: libexpat.so.1: cannot open shared object file"})
    c = TestClient(create_app(st, runner=lambda *a, **k: None))
    assert c.get("/api/health").json() == {"status": "ok"}
    h = c.get("/api/health/analysis").json()
    assert h == {"status": "ok", "analysis_ready": False, "analysis_problems": ["rasterio"]}


def test_dockerfile_installs_libexpat_and_smoke_checks_imports():
    df = open(os.path.join(os.path.dirname(__file__), "..", "..", "Dockerfile")).read()
    assert "libexpat1" in df and "--no-install-recommends" in df and "rm -rf /var/lib/apt/lists" in df
    assert "python -m backend.core.native_check" in df.split("COPY backend")[1].split("\n")[1]
