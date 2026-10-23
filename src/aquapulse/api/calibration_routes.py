"""FastAPI REST routes for Pool, Camera, and Calibration Profile management."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from aquapulse.db.database import (
    activate_calibration_profile,
    create_calibration_profile,
    create_calibration_version,
    create_camera,
    create_pool,
    get_calibration_profile,
    get_camera,
    get_connection,
    get_pool,
    list_calibration_profiles,
    list_cameras,
    list_pools,
    update_calibration_profile,
)
from aquapulse.schemas import (
    CalibrationProfile,
    CalibrationProfileCreate,
    CalibrationProfileUpdate,
    CalibrationValidationResult,
    Camera,
    CameraCreate,
    Pool,
    PoolCreate,
)

router = APIRouter(prefix="/api/v1", tags=["calibration_management"])


# =========================================================================
# Pool Endpoints
# =========================================================================


@router.post(
    "/pools",
    response_model=Pool,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new swimming pool basin",
)
def register_pool(pool_in: PoolCreate) -> Pool:
    """Register a swimming pool with physical dimensions and verified water depths."""
    if pool_in.length_m < 2.0 or pool_in.length_m > 150.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pool length ({pool_in.length_m}m) must be between 2.0m and 150.0m.",
        )
    if pool_in.width_m < 1.0 or pool_in.width_m > 50.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pool width ({pool_in.width_m}m) must be between 1.0m and 50.0m.",
        )
    if pool_in.deep_depth_m <= pool_in.shallow_depth_m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deep depth must be strictly greater than shallow depth.",
        )
    if pool_in.depth_boundary_m <= 0.0 or pool_in.depth_boundary_m >= pool_in.length_m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Depth boundary ({pool_in.depth_boundary_m}m) must lie strictly between 0 and pool length ({pool_in.length_m}m).",
        )

    conn = get_connection()
    try:
        return create_pool(conn, pool_in)
    except sqlite3.IntegrityError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pool with ID '{pool_in.id}' already exists.",
        ) from err


@router.get(
    "/pools",
    response_model=list[Pool],
    summary="List all registered swimming pools",
)
def fetch_pools() -> list[Pool]:
    """Retrieve all swimming pool records."""
    conn = get_connection()
    return list_pools(conn)


@router.get(
    "/pools/{pool_id}",
    response_model=Pool,
    summary="Fetch swimming pool by ID",
)
def fetch_pool(pool_id: str) -> Pool:
    """Retrieve details of a specific swimming pool."""
    conn = get_connection()
    pool = get_pool(conn, pool_id)
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pool '{pool_id}' not found.",
        )
    return pool


@router.get(
    "/pools/{pool_id}/cameras",
    response_model=list[Camera],
    summary="List all cameras installed at a pool",
)
def fetch_pool_cameras(pool_id: str) -> list[Camera]:
    """Retrieve all cameras configured for the specified pool."""
    conn = get_connection()
    pool = get_pool(conn, pool_id)
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pool '{pool_id}' not found.",
        )
    return list_cameras(conn, pool_id=pool_id)


# =========================================================================
# Camera Endpoints
# =========================================================================


@router.post(
    "/cameras",
    response_model=Camera,
    status_code=status.HTTP_201_CREATED,
    summary="Register a camera for a swimming pool",
)
def register_camera(camera_in: CameraCreate) -> Camera:
    """Register a camera and associate it with a swimming pool."""
    conn = get_connection()
    pool = get_pool(conn, camera_in.pool_id)
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target pool '{camera_in.pool_id}' does not exist.",
        )

    try:
        return create_camera(conn, camera_in)
    except sqlite3.IntegrityError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera with ID '{camera_in.id}' already exists.",
        ) from err


@router.get(
    "/cameras/{camera_id}",
    response_model=Camera,
    summary="Fetch camera details by ID",
)
def fetch_camera(camera_id: str) -> Camera:
    """Fetch camera record and active calibration version."""
    conn = get_connection()
    camera = get_camera(conn, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found.",
        )
    return camera


# =========================================================================
# Calibration Profile Endpoints
# =========================================================================


@router.post(
    "/calibrations",
    response_model=CalibrationProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new draft calibration profile",
)
def create_calibration(cal_in: CalibrationProfileCreate) -> CalibrationProfile:
    """Create a draft calibration profile for a pool camera."""
    conn = get_connection()
    pool = get_pool(conn, cal_in.pool_id)
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pool '{cal_in.pool_id}' not found.",
        )
    camera = get_camera(conn, cal_in.camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{cal_in.camera_id}' not found.",
        )

    return create_calibration_profile(conn, cal_in)


@router.get(
    "/calibrations",
    response_model=list[CalibrationProfile],
    summary="List calibration profiles",
)
def fetch_calibrations(
    camera_id: str | None = Query(default=None, description="Filter by camera ID"),
    pool_id: str | None = Query(default=None, description="Filter by pool ID"),
) -> list[CalibrationProfile]:
    """List calibration profiles with optional filtering by camera or pool."""
    conn = get_connection()
    return list_calibration_profiles(conn, camera_id=camera_id, pool_id=pool_id)


@router.get(
    "/calibrations/{profile_id}",
    response_model=CalibrationProfile,
    summary="Fetch calibration profile by ID",
)
def fetch_calibration_profile(profile_id: str) -> CalibrationProfile:
    """Retrieve details and geometry of a specific calibration profile."""
    conn = get_connection()
    profile = get_calibration_profile(conn, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calibration profile '{profile_id}' not found.",
        )
    return profile


@router.put(
    "/calibrations/{profile_id}",
    response_model=CalibrationProfile,
    summary="Update draft calibration profile parameters",
)
def edit_calibration_profile(
    profile_id: str,
    updates: CalibrationProfileUpdate,
) -> CalibrationProfile:
    """Update corner coordinates or physical dimensions of a calibration profile."""
    conn = get_connection()
    profile = get_calibration_profile(conn, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calibration profile '{profile_id}' not found.",
        )

    dumped: dict[str, Any] = updates.model_dump(exclude_unset=True)
    updated = update_calibration_profile(conn, profile_id, dumped)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update calibration profile.",
        )
    return updated


@router.post(
    "/calibrations/{profile_id}/validate",
    response_model=CalibrationValidationResult,
    summary="Validate geometry of a calibration profile",
)
def validate_calibration(profile_id: str) -> CalibrationValidationResult:
    """Run geometric, physical, and homography validation checks on the calibration."""
    conn = get_connection()
    profile = get_calibration_profile(conn, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calibration profile '{profile_id}' not found.",
        )

    cal = profile.to_calibration()
    return cal.validate_geometry()


@router.post(
    "/calibrations/{profile_id}/activate",
    response_model=CalibrationProfile,
    summary="Validate and activate calibration profile",
)
def activate_calibration(profile_id: str) -> CalibrationProfile:
    """Validate profile geometry and set it as the active version for its camera."""
    conn = get_connection()
    profile = get_calibration_profile(conn, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calibration profile '{profile_id}' not found.",
        )

    try:
        activated = activate_calibration_profile(conn, profile_id)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        ) from val_err

    if not activated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate calibration profile.",
        )
    return activated


@router.post(
    "/calibrations/{profile_id}/versions",
    response_model=CalibrationProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Create revised version of calibration profile",
)
def create_revised_version(
    profile_id: str,
    updates: CalibrationProfileUpdate | None = None,
) -> CalibrationProfile:
    """Create a new version (version+1) in draft status without altering historical geometry."""
    conn = get_connection()
    profile = get_calibration_profile(conn, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calibration profile '{profile_id}' not found.",
        )

    dumped = updates.model_dump(exclude_unset=True) if updates else None
    new_version = create_calibration_version(conn, profile_id, dumped)
    if not new_version:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create calibration version.",
        )
    return new_version
