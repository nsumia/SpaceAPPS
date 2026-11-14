from shapely.geometry import box

from backend.core import basin


def test_env_forces_buffer_fallback_without_download(monkeypatch):
    monkeypatch.setenv("LLD_BASIN_FALLBACK", "1")
    monkeypatch.setattr(basin, "extract_level", lambda *a, **k: (_ for _ in ()).throw(AssertionError("downloaded")))
    geom, info = basin.basin_for_lake(box(30, 40, 30.1, 40.1), 100.0)
    assert info["fallback"] is True and "LLD_BASIN_FALLBACK" in info["fallback_reason"]
    assert geom.area > box(30, 40, 30.1, 40.1).area
