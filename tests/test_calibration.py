"""Comprehensive tests for PoolCalibration perspective mapping, homography, and geometry validation."""

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
    cal = PoolCalibration(deep_end_side="right", depth_boundary_m=12.5)
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


def test_four_orientations_geometry():
    """Verify shallow -> deep coordinate alignment across all 4 camera orientations."""
    w, h = 1000, 500

    # 1. Right: TL is shallow (0,0), TR is deep (25,0)
    cal_right = PoolCalibration(deep_end_side="right", length_m=25.0, width_m=12.0)
    p_tl = cal_right.to_pool_m(50, 75, w, h)
    p_tr = cal_right.to_pool_m(950, 75, w, h)
    assert p_tl[0] < 1.0
    assert p_tr[0] > 24.0

    # 2. Left: TL is deep (25,0), TR is shallow (0,0)
    cal_left = PoolCalibration(deep_end_side="left", length_m=25.0, width_m=12.0)
    p_tl_l = cal_left.to_pool_m(50, 75, w, h)
    p_tr_l = cal_left.to_pool_m(950, 75, w, h)
    assert p_tl_l[0] > 24.0
    assert p_tr_l[0] < 1.0

    # 3. Bottom: TL is shallow (0,0), BL is deep (25,0)
    cal_bottom = PoolCalibration(deep_end_side="bottom", length_m=25.0, width_m=12.0)
    p_tl_b = cal_bottom.to_pool_m(50, 75, w, h)
    p_bl_b = cal_bottom.to_pool_m(50, 425, w, h)
    assert p_tl_b[0] < 1.0
    assert p_bl_b[0] > 24.0

    # 4. Top: TL is deep (25,0), BL is shallow (0,0)
    cal_top = PoolCalibration(deep_end_side="top", length_m=25.0, width_m=12.0)
    p_tl_t = cal_top.to_pool_m(50, 75, w, h)
    p_bl_t = cal_top.to_pool_m(50, 425, w, h)
    assert p_tl_t[0] > 24.0
    assert p_bl_t[0] < 1.0


def test_non_midpoint_boundary():
    """Verify non-midpoint boundary position configurable in physical pool coordinates."""
    # Boundary at 8.0 meters in a 20m pool
    cal = PoolCalibration(length_m=20.0, width_m=10.0, depth_boundary_m=8.0)
    assert cal.zone_for(7.5, in_water=True) == PoolZone.ZONE_A_SHALLOW
    assert cal.zone_for(8.1, in_water=True) == PoolZone.ZONE_B_DEEP_END

    # Boundary at 18.0 meters in a 25m pool
    cal2 = PoolCalibration(length_m=25.0, width_m=12.0, depth_boundary_m=18.0)
    assert cal2.zone_for(17.9, in_water=True) == PoolZone.ZONE_A_SHALLOW
    assert cal2.zone_for(18.0, in_water=True) == PoolZone.ZONE_B_DEEP_END


def test_roundtrip_pixel_to_pool_and_back():
    """Verify that transforming pixels -> pool meters -> pixels preserves coordinates."""
    cal = PoolCalibration(length_m=30.0, width_m=15.0, depth_boundary_m=15.0)
    w, h = 1920, 1080

    # Center of pool
    center_px = (0.5 * w, 0.5 * h)
    x_m, y_m = cal.to_pool_m(center_px[0], center_px[1], w, h)
    back_px, back_py = cal.from_pool_m(x_m, y_m, w, h)

    assert abs(back_px - center_px[0]) < 2.0
    assert abs(back_py - center_px[1]) < 2.0


def test_projected_boundary_endpoints():
    """Verify shallow/deep boundary projection into pixel and normalized space."""
    cal = PoolCalibration(
        pool_corners_norm=[(0.1, 0.2), (0.9, 0.2), (0.9, 0.8), (0.1, 0.8)],
        deep_end_side="right",
        length_m=20.0,
        width_m=10.0,
        depth_boundary_m=10.0,  # Exactly at midpoint
    )
    w, h = 1000, 500
    norm_boundary = cal.projected_boundary_norm(w, h)
    assert len(norm_boundary) == 2

    p1, p2 = norm_boundary
    # Midpoint of 0.1 and 0.9 is 0.5 along X
    assert abs(p1[0] - 0.5) < 0.05
    assert abs(p2[0] - 0.5) < 0.05
    # Y coordinates match top and bottom edges
    assert abs(p1[1] - 0.2) < 0.05
    assert abs(p2[1] - 0.8) < 0.05


def test_resolution_invariance():
    """Normalized coordinates should map identically across different video resolutions."""
    cal = PoolCalibration()
    norm_x, norm_y = 0.5, 0.5

    # 720p
    m_720 = cal.to_pool_m(norm_x * 1280, norm_y * 720, 1280, 720)
    # 1080p
    m_1080 = cal.to_pool_m(norm_x * 1920, norm_y * 1080, 1920, 1080)
    # 4K
    m_4k = cal.to_pool_m(norm_x * 3840, norm_y * 2160, 3840, 2160)

    assert abs(m_720[0] - m_1080[0]) < 0.05
    assert abs(m_720[1] - m_1080[1]) < 0.05
    assert abs(m_1080[0] - m_4k[0]) < 0.05
    assert abs(m_1080[1] - m_4k[1]) < 0.05


def test_geometry_validation_success():
    """Verify validation passes for standard valid demo configuration."""
    cal = PoolCalibration()
    res = cal.validate_geometry()
    assert res.is_valid is True
    assert len(res.errors) == 0
    assert len(res.projected_boundary_norm) == 2
    assert len(res.sample_mappings) > 0


def test_geometry_validation_failures():
    """Verify validation catches self-intersecting, collinear, or out-of-range geometry."""
    # 1. Self-intersecting corners (bowtie/hourglass)
    cal_bowtie = PoolCalibration(
        pool_corners_norm=[(0.1, 0.2), (0.9, 0.8), (0.9, 0.2), (0.1, 0.8)]
    )
    res_bt = cal_bowtie.validate_geometry()
    assert res_bt.is_valid is False
    assert any("self-intersecting" in e.lower() for e in res_bt.errors)

    # 2. Collinear corners (zero area or degenerate line)
    cal_collinear = PoolCalibration(
        pool_corners_norm=[(0.1, 0.2), (0.3, 0.2), (0.6, 0.2), (0.9, 0.2)]
    )
    res_col = cal_collinear.validate_geometry()
    assert res_col.is_valid is False
    assert any("collinear" in e.lower() or "too small" in e.lower() for e in res_col.errors)

    # 3. Invalid physical dimensions
    cal_dim = PoolCalibration(length_m=1.0)  # Too short (< 2.0m)
    res_dim = cal_dim.validate_geometry()
    assert res_dim.is_valid is False
    assert any("length" in e.lower() for e in res_dim.errors)

    # 4. Deep depth <= shallow depth
    cal_depth = PoolCalibration(shallow_depth_m=2.0, deep_depth_m=1.2)
    res_depth = cal_depth.validate_geometry()
    assert res_depth.is_valid is False
    assert any("greater than shallow depth" in e.lower() for e in res_depth.errors)

    # 5. Boundary position outside pool length
    cal_bound = PoolCalibration(length_m=25.0, depth_boundary_m=26.0)
    res_bound = cal_bound.validate_geometry()
    assert res_bound.is_valid is False
    assert any("boundary" in e.lower() for e in res_bound.errors)


def test_zone_uncertainty_buffer():
    """Verify uncertainty buffer returns UNKNOWN near the depth boundary."""
    cal = PoolCalibration(length_m=25.0, depth_boundary_m=12.5)

    # At 12.4m with 0.5m buffer: within [12.0, 13.0] -> UNKNOWN
    assert cal.zone_for(12.4, in_water=True, uncertainty_buffer_m=0.5) == PoolZone.UNKNOWN
    # At 11.8m with 0.5m buffer: strictly shallow
    assert cal.zone_for(11.8, in_water=True, uncertainty_buffer_m=0.5) == PoolZone.ZONE_A_SHALLOW
    # At 13.2m with 0.5m buffer: strictly deep
    assert cal.zone_for(13.2, in_water=True, uncertainty_buffer_m=0.5) == PoolZone.ZONE_B_DEEP_END
