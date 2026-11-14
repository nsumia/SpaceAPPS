import warnings

import numpy as np
import pytest
from shapely.geometry import Point

from backend.core import geo
from backend.core.lakes import LAKES, lake_id


def test_auto_utm_known_lakes():
    assert geo.utm_epsg(30.18, 37.72) == 32636          # Burdur
    assert geo.utm_epsg(42.95, 38.65) == 32638          # Van
    assert geo.utm_epsg(-69.35, -15.9) == 32719         # Titicaca (south)
    assert geo.utm_epsg(179.99, 10) == 32660 and geo.utm_epsg(180.0, 10) == 32660


def test_all_defined_lakes_have_utm_and_box_contains_seed():
    from shapely.geometry import box
    for k, d in LAKES.items():
        assert box(*d["bbox"]).contains(Point(*d["seed"])), k
        assert 32600 < geo.utm_epsg(*d["seed"]) < 32661
    assert geo.utm_epsg(*LAKES["van"]["seed"], width_deg=1.6) == 32638


def test_wide_lake_warns():
    with pytest.warns(UserWarning, match="wide"):
        geo.utm_epsg(0, 0, width_deg=7.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        geo.utm_epsg(0, 0, width_deg=5.0)


def test_adaptive_resolution_thresholds():
    assert geo.pick_resolution(100) == 30 and geo.pick_resolution(499.9) == 30
    assert geo.pick_resolution(500) == 60 and geo.pick_resolution(4999) == 60
    assert geo.pick_resolution(5000) == 120 and geo.pick_resolution(50000) == 120
    assert geo.pick_resolution(geo.bbox_area_km2(LAKES["van"]["bbox"])) == 120      # 17000+ km2 box
    assert geo.pick_resolution(geo.bbox_area_km2((0, 0, 0.1, 0.1))) == 30


def test_bbox_area_sane():
    assert geo.bbox_area_km2((0, 0, 1, 1)) == pytest.approx(111.32 * 110.57, rel=0.001)


def test_custom_lake_id_stable():
    assert geo.custom_lake_id(30.18, 37.72) == geo.custom_lake_id(30.18, 37.72)
    assert geo.custom_lake_id(30.18, 37.72).startswith("custom-") and lake_id("burdur").startswith("custom-")
    assert len({lake_id(k) for k in LAKES}) == 4


def two_lakes():
    m = np.zeros((120, 200), bool)
    yy, xx = np.mgrid[:120, :200]
    m |= (yy - 60) ** 2 + (xx - 50) ** 2 <= 30 ** 2       # big lake (the user's)
    m |= (yy - 60) ** 2 + (xx - 150) ** 2 <= 20 ** 2      # neighbour lake (bigger than nothing, separate)
    return m


def test_component_selection_excludes_neighbour():
    m = two_lakes()
    c = geo.select_lake_component(m, (60, 50))
    assert c[60, 50] and not c[60, 150]
    c2 = geo.select_lake_component(m, (60, 150))
    assert c2[60, 150] and not c2[60, 50]
    assert c.sum() + c2.sum() == m.sum()


def test_seed_on_land_snaps_to_nearest_lake_and_far_seed_errors():
    m = two_lakes()
    c = geo.select_lake_component(m, (60, 88))              # land, 8 px from the big lake edge
    assert c[60, 50]
    with pytest.raises(ValueError):
        geo.select_lake_component(m, (5, 100), max_snap_px=5)
    with pytest.raises(ValueError):
        geo.select_lake_component(np.zeros((5, 5), bool), (2, 2))


def test_polygon_buffer_excludes_neighbour_and_adds_1km():
    from rasterio.transform import Affine
    m = two_lakes()
    tf = Affine(100.0, 0, 500000.0, 0, -100.0, 4200000.0)   # 100 m pixels: neighbour 5 km away from big lake edge
    c = geo.select_lake_component(m, (60, 50))
    poly = geo.component_to_polygon_utm(c, tf, buffer_m=1000.0)
    nb_pt = Point(500000 + 150 * 100 + 50, 4200000 - 60 * 100 - 50)
    assert not poly.contains(nb_pt)
    area0 = c.sum() * 100 ** 2
    assert poly.area / area0 == pytest.approx((4 / 3) ** 2, rel=0.05)          # 3 km radius + 1 km buffer
