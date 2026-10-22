"""Tests for PoolCalibration perspective mapping and zone determination."""


from aquapulse.schemas import PoolZone
from aquapulse.vision.calibration import PoolCalibration


def test_default_calibration_geometry():
    cal = PoolCalibration()
    poly = cal.water_polygon_px(1280, 720)
    assert poly.shape == (4, 2)

    # In-water test
    center_x, center_y = 640.0, 360.0
    assert cal.in_water(center_x, center_y, 1280, 720) is True

    # Far corner outside pool deck
    assert cal.in_water(10.0, 10.0, 1280, 720) is False


def test_homography_meters_mapping():
    cal = PoolCalibration(deep_end_side="right")
    # Top-left corner should map near (0, 0)
    tl_m = cal.to_pool_m(0.05 * 1000, 0.15 * 500, 1000, 500)
    assert 0.0 <= tl_m[0] <= 1.0
    assert 0.0 <= tl_m[1] <= 1.0

    # Bottom-right corner should map near (25, 12)
    br_m = cal.to_pool_m(0.95 * 1000, 0.85 * 500, 1000, 500)
    assert 24.0 <= br_m[0] <= 25.0
    assert 11.0 <= br_m[1] <= 12.0


def test_zone_determination():
    cal = PoolCalibration(deep_end_side="right")
    # Shallow end
    assert cal.zone_for(5.0, in_water=True) == PoolZone.ZONE_A_SHALLOW
    # Deep end (>= 12.5m)
    assert cal.zone_for(13.0, in_water=True) == PoolZone.ZONE_B_DEEP_END
    # Deck
    assert cal.zone_for(5.0, in_water=False) == PoolZone.POOL_DECK


def test_scale_estimation():
    cal = PoolCalibration()
    scale = cal.metres_per_px_at(640, 360, 1280, 720)
    assert scale > 0.0
