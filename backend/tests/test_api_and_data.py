import numpy as np
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

from backend.api.main import app
from backend.core import climate, swot
from backend.core.basin import select_basins


def test_health_and_docs():
    c = TestClient(app)
    assert c.get("/api/health").json() == {"status": "ok"}
    assert c.get("/docs").status_code == 200
    spec = c.get("/openapi.json").json()
    assert "/api/health" in spec["paths"]
    assert spec["info"]["title"] == "Metalimnion API"


def power_monthly_fixture():
    d = {}
    for y in (2001, 2002):
        for m in range(1, 13):
            d[f"{y}{m:02d}"] = 1.0           # mm/day
        d[f"{y}13"] = 1.0                    # annual mean key must be ignored
    d["200301"] = -999.0
    return d


def test_power_monthly_to_water_year_mm():
    d = power_monthly_fixture()
    m = climate.monthly_mm(d)
    assert m["2001-02-01"] == 28 and m["2001-03-01"] == 31 and "2001-13" not in m.index.astype(str)
    wy = climate.water_year_totals(d)
    assert list(wy.index) == [2002] and wy[2002] == pytest.approx(365)        # Oct 2001 - Sep 2002, 1 mm/day
    wys = climate.water_year_totals(d, south=True)
    assert list(wys.index) == [2002] and wys[2002] == pytest.approx(365)      # Apr 2001 - Mar 2002


def test_swot_fill_rows_removed():
    csv = ("lake_id,time_str,wse,area_total,wse_units,area_total_units\n"
           "1,2024-01-03T14:52:53Z,35.981,0.0237,m,km^2\n"
           "1,no_data,-999999999999.0,-999999999999.0,m,km^2\n"
           "1,2024-01-04T14:52:53Z,36.0,-999999999999.0,m,km^2\n"
           "1,2023-12-01T00:00:00Z,35.5,0.02,m,km^2\n")
    df = swot.clean_hydrocron_csv(csv)
    assert list(df.wse) == [35.5, 35.981]


def test_select_basins_picks_overlapping_ones():
    lake = box(0, 0, 1, 1)
    polys = [box(-1, -1, 0.5, 2), box(0.5, -1, 3, 2), box(5, 5, 6, 6)]
    assert select_basins(polys, lake) == [0, 1]
    assert select_basins([box(5, 5, 6, 6)], lake) == []
    assert select_basins([box(-1, -1, 0.95, 2), box(0.95, -1, 3, 2)], lake) == [0]   # 5 % sliver ignored


def test_swot_area_level_fit_and_volume_with_extrapolation_flag():
    import numpy as np
    from backend.core import swot
    a = np.linspace(110, 125, 20)
    fit = swot.area_level_fit(a, 850 + 0.05 * (a - 110))
    assert fit["m_per_km2"] == __import__("pytest").approx(0.05) and fit["r2"] > 0.999
    v = swot.volume_change([1986, 2024], [206.0, 118.0], fit)
    assert v[0]["dV_km3"] == 0 and v[0]["extrapolated"] and not v[1]["extrapolated"]
    assert v[1]["dV_km3"] == __import__("pytest").approx(0.05 * (118 ** 2 - 206 ** 2) / 2e3)


def test_swot_run_without_pld_writes_ok_false(tmp_path):
    from backend.core import swot
    out = swot.run("burdur", out_path=str(tmp_path / "swot.json"))
    assert out["ok"] is False and "PLD" in out["reason"]
