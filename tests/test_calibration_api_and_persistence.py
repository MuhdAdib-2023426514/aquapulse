"""Tests for calibration persistence, versioning, multi-camera profiles, and API routes."""

import pytest
from fastapi.testclient import TestClient

from aquapulse.api.main import app
from aquapulse.db.database import (
    activate_calibration_profile,
    create_calibration_profile,
    create_calibration_version,
    create_camera,
    get_active_calibration_for_camera,
    get_calibration_profile,
    get_camera,
    get_connection,
    get_pool,
    init_db,
    list_cameras,
    list_pools,
)
from aquapulse.schemas import (
    CalibrationProfileCreate,
    CalibrationStatus,
    CameraCreate,
)

client = TestClient(app)


# =========================================================================
# Persistence & Database Unit Tests
# =========================================================================


def test_seed_demo_pool_and_camera() -> None:
    """Verify auto-seeding creates AquaPulse Demo Pool, CCTV camera, and active calibration."""
    conn = get_connection(":memory:")
    init_db(conn, auto_seed=True)

    pools = list_pools(conn)
    assert len(pools) >= 1
    demo_pool = get_pool(conn, "demo_pool_1")
    assert demo_pool is not None
    assert demo_pool.name == "AquaPulse Demo Pool"
    assert demo_pool.length_m == 25.0
    assert demo_pool.width_m == 12.0
    assert demo_pool.shallow_depth_m == 0.8
    assert demo_pool.deep_depth_m == 1.8
    assert demo_pool.depth_boundary_m == 12.5

    cams = list_cameras(conn, pool_id="demo_pool_1")
    assert len(cams) >= 1
    cctv = get_camera(conn, "demo_camera_cctv_1")
    assert cctv is not None
    assert cctv.name == "Main Pool CCTV"
    assert cctv.active_calibration_id == "demo_calibration_v1"
    assert cctv.active_calibration_version == 1

    active_cal = get_active_calibration_for_camera(conn, "demo_camera_cctv_1")
    assert active_cal is not None
    assert active_cal.id == "demo_calibration_v1"
    assert active_cal.is_active is True
    assert active_cal.status == CalibrationStatus.ACTIVE
    assert active_cal.deep_end_side == "right"
    assert len(active_cal.pool_corners_norm) == 4


def test_multi_camera_independent_calibrations() -> None:
    """Verify that multiple cameras on the same pool maintain independent calibration profiles."""
    conn = get_connection(":memory:")
    init_db(conn, auto_seed=True)

    # Register Camera B (South Deck CCTV)
    cam_b = create_camera(
        conn,
        CameraCreate(
            id="camera_south_deck",
            pool_id="demo_pool_1",
            name="South Deck CCTV",
            location_description="South pergola overlooking shallow end",
        ),
    )
    assert cam_b.id == "camera_south_deck"

    # Create draft calibration for Camera B
    cal_b1 = create_calibration_profile(
        conn,
        CalibrationProfileCreate(
            pool_id="demo_pool_1",
            camera_id="camera_south_deck",
            pool_corners_norm=[(0.1, 0.2), (0.9, 0.2), (0.9, 0.8), (0.1, 0.8)],
            deep_end_side="left",
            length_m=25.0,
            width_m=12.0,
            shallow_depth_m=0.8,
            deep_depth_m=1.8,
            depth_boundary_m=12.5,
        ),
    )
    assert cal_b1.version == 1
    assert cal_b1.is_active is False
    assert cal_b1.status == CalibrationStatus.DRAFT

    # Activate Camera B calibration
    activated_b = activate_calibration_profile(conn, cal_b1.id)
    assert activated_b is not None
    assert activated_b.is_active is True
    assert activated_b.status == CalibrationStatus.ACTIVE

    # Verify Camera A (Main Pool CCTV) is still active and unchanged
    cal_a = get_active_calibration_for_camera(conn, "demo_camera_cctv_1")
    assert cal_a is not None
    assert cal_a.id == "demo_calibration_v1"
    assert cal_a.is_active is True

    # Verify Camera B active profile
    cal_b = get_active_calibration_for_camera(conn, "camera_south_deck")
    assert cal_b is not None
    assert cal_b.id == cal_b1.id
    assert cal_b.deep_end_side == "left"


def test_calibration_versioning_and_immutability() -> None:
    """Verify revising a calibration creates a new version while preserving the historical version."""
    conn = get_connection(":memory:")
    init_db(conn, auto_seed=True)

    # Create revised version for Main CCTV
    v2_draft = create_calibration_version(
        conn,
        "demo_calibration_v1",
        new_params={
            "depth_boundary_m": 10.0,
            "pool_corners_norm": [(0.06, 0.16), (0.94, 0.16), (0.94, 0.84), (0.06, 0.84)],
        },
    )
    assert v2_draft is not None
    assert v2_draft.version == 2
    assert v2_draft.status == CalibrationStatus.DRAFT
    assert v2_draft.is_active is False
    assert v2_draft.depth_boundary_m == 10.0

    # Historical v1 remains intact and active
    v1 = get_calibration_profile(conn, "demo_calibration_v1")
    assert v1 is not None
    assert v1.version == 1
    assert v1.is_active is True
    assert v1.depth_boundary_m == 12.5

    # Activate v2
    v2_active = activate_calibration_profile(conn, v2_draft.id)
    assert v2_active is not None
    assert v2_active.is_active is True
    assert v2_active.status == CalibrationStatus.ACTIVE

    # Verify v1 is now deactivated
    v1_after = get_calibration_profile(conn, "demo_calibration_v1")
    assert v1_after is not None
    assert v1_after.is_active is False

    # Active profile for camera is now v2
    active_now = get_active_calibration_for_camera(conn, "demo_camera_cctv_1")
    assert active_now is not None
    assert active_now.id == v2_draft.id
    assert active_now.version == 2


def test_prevent_activating_invalid_calibration() -> None:
    """Verify that an invalid or self-intersecting calibration cannot be activated."""
    conn = get_connection(":memory:")
    init_db(conn, auto_seed=True)

    # Draft with self-intersecting bowtie corners
    cal_bad = create_calibration_profile(
        conn,
        CalibrationProfileCreate(
            pool_id="demo_pool_1",
            camera_id="demo_camera_cctv_1",
            pool_corners_norm=[(0.1, 0.2), (0.9, 0.8), (0.9, 0.2), (0.1, 0.8)],
        ),
    )

    with pytest.raises(ValueError, match="self-intersecting"):
        activate_calibration_profile(conn, cal_bad.id)


# =========================================================================
# REST API Endpoints Integration Tests
# =========================================================================


def test_api_pool_registration_and_validation() -> None:
    """Test POST /api/v1/pools and GET /api/v1/pools."""
    # 1. Valid pool creation
    res = client.post(
        "/api/v1/pools",
        json={
            "name": "Clubhouse Olympic Basin",
            "length_m": 50.0,
            "width_m": 25.0,
            "shallow_depth_m": 1.2,
            "deep_depth_m": 2.2,
            "depth_boundary_m": 25.0,
        },
    )
    assert res.status_code == 201
    pool_data = res.json()
    assert pool_data["name"] == "Clubhouse Olympic Basin"
    assert pool_data["length_m"] == 50.0
    pool_id = pool_data["id"]

    # 2. Invalid pool dimensions: deep <= shallow
    res_err = client.post(
        "/api/v1/pools",
        json={
            "name": "Invalid Pool",
            "length_m": 25.0,
            "width_m": 12.0,
            "shallow_depth_m": 2.0,
            "deep_depth_m": 1.5,
            "depth_boundary_m": 12.5,
        },
    )
    assert res_err.status_code == 400

    # 3. GET pool by ID
    res_get = client.get(f"/api/v1/pools/{pool_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == pool_id


def test_api_camera_registration_and_listing() -> None:
    """Test POST /api/v1/cameras and GET /api/v1/cameras/{id}."""
    res = client.post(
        "/api/v1/cameras",
        json={
            "pool_id": "demo_pool_1",
            "name": "Lap Lane 1 Overhead",
            "location_description": "Overhead truss lane 1-2",
        },
    )
    assert res.status_code == 201
    cam = res.json()
    assert cam["name"] == "Lap Lane 1 Overhead"
    cam_id = cam["id"]

    # Fetch camera
    res_get = client.get(f"/api/v1/cameras/{cam_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == cam_id

    # List cameras for pool
    res_list = client.get("/api/v1/pools/demo_pool_1/cameras")
    assert res_list.status_code == 200
    cam_ids = [c["id"] for c in res_list.json()]
    assert cam_id in cam_ids


def test_api_calibration_workflow() -> None:
    """Test full calibration lifecycle: draft -> update -> validate -> activate -> versions."""
    # 1. Create draft calibration
    res_draft = client.post(
        "/api/v1/calibrations",
        json={
            "pool_id": "demo_pool_1",
            "camera_id": "demo_camera_cctv_1",
            "pool_corners_norm": [(0.08, 0.18), (0.92, 0.18), (0.92, 0.82), (0.08, 0.82)],
            "deep_end_side": "right",
            "length_m": 25.0,
            "width_m": 12.0,
            "shallow_depth_m": 0.8,
            "deep_depth_m": 1.8,
            "depth_boundary_m": 12.5,
        },
    )
    assert res_draft.status_code == 201
    draft = res_draft.json()
    cal_id = draft["id"]
    assert draft["status"] == "draft"
    assert draft["is_active"] is False

    # 2. Validate calibration
    res_val = client.post(f"/api/v1/calibrations/{cal_id}/validate")
    assert res_val.status_code == 200
    val_data = res_val.json()
    assert val_data["is_valid"] is True
    assert len(val_data["errors"]) == 0
    assert len(val_data["projected_boundary_norm"]) == 2

    # 3. Activate calibration
    res_act = client.post(f"/api/v1/calibrations/{cal_id}/activate")
    assert res_act.status_code == 200
    act_data = res_act.json()
    assert act_data["is_active"] is True
    assert act_data["status"] == "active"

    # 4. Create new version
    res_ver = client.post(
        f"/api/v1/calibrations/{cal_id}/versions",
        json={"depth_boundary_m": 14.0},
    )
    assert res_ver.status_code == 201
    ver_data = res_ver.json()
    assert ver_data["version"] == draft["version"] + 1
    assert ver_data["depth_boundary_m"] == 14.0
    assert ver_data["is_active"] is False


def test_api_video_upload_with_camera_id() -> None:
    """Verify video upload auto-attaches camera calibration profile."""
    # We test the config endpoint and camera association
    # 1. Fetch active camera
    cam_res = client.get("/api/v1/cameras/demo_camera_cctv_1")
    assert cam_res.status_code == 200

    # 2. Test updating job config with camera_id
    # Create mock job by accessing video routes or verifying config updates
    from aquapulse.api.video_routes import _JOBS, _save_job_state
    from aquapulse.video.pipeline import VideoJob

    test_job = VideoJob(filename="test_cam_pool.mp4", raw_filepath="")
    _JOBS[test_job.id] = test_job
    _save_job_state(test_job)

    cfg_res = client.put(
        f"/api/v1/videos/{test_job.id}/config",
        json={"camera_id": "demo_camera_cctv_1"},
    )
    assert cfg_res.status_code == 200
    updated_job = cfg_res.json()
    assert updated_job["camera_id"] == "demo_camera_cctv_1"
    assert updated_job["calibration_profile_id"] is not None
    assert updated_job["calibration_version"] is not None
    assert updated_job["calibration"]["depth_boundary_m"] == 12.5
