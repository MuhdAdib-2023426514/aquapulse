"""Pool perspective calibration and pixel-to-meter homography mapping with reusable profiles."""

from __future__ import annotations

import math
from typing import Any, Literal

import cv2
import numpy as np
from pydantic import BaseModel, Field

from aquapulse.config import (
    DEEP_END_BOUNDARY_X_M,
    POOL_LENGTH_M,
    POOL_WIDTH_M,
)
from aquapulse.schemas import (
    CalibrationStatus,
    CalibrationValidationResult,
    PoolZone,
)


class PoolCalibration(BaseModel):
    """Calibrates camera perspective to swimming pool basin with verified physical dimensions."""

    # 4 clicked corners in normalized coordinates (0.0..1.0): [TL, TR, BR, BL]
    pool_corners_norm: list[tuple[float, float]] = Field(
        default_factory=lambda: [
            (0.05, 0.15),
            (0.95, 0.15),
            (0.95, 0.85),
            (0.05, 0.85),
        ],
        description="4 pool basin water corners normalized to [0..1] in [TL, TR, BR, BL] order",
    )
    deep_end_side: Literal["left", "right", "top", "bottom"] = Field(
        default="right",
        description="Side of the pool camera view that corresponds to the deep end",
    )
    deck_margin_norm: float = Field(
        default=0.04,
        ge=0.0,
        le=0.2,
        description="Deck boundary margin buffer around pool water polygon",
    )

    # Physical dimensions in meters
    length_m: float = Field(
        default=POOL_LENGTH_M,
        gt=0.0,
        description="Physical pool length in meters (longitudinal axis)",
    )
    width_m: float = Field(
        default=POOL_WIDTH_M,
        gt=0.0,
        description="Physical pool width in meters (transverse axis)",
    )

    # Water depths in meters
    shallow_depth_m: float = Field(
        default=0.8,
        gt=0.0,
        description="Verified water depth at shallow end in meters",
    )
    deep_depth_m: float = Field(
        default=1.8,
        gt=0.0,
        description="Verified water depth at deep end in meters",
    )

    # Depth transition boundary
    depth_boundary_m: float = Field(
        default=DEEP_END_BOUNDARY_X_M,
        gt=0.0,
        description="Distance from shallow edge (x=0) to deep-end transition along length in meters",
    )

    # Status
    status: CalibrationStatus = Field(
        default=CalibrationStatus.DRAFT,
        description="Calibration lifecycle status: draft, validated, active, needs_recalibration",
    )

    def water_polygon_px(self, width: int, height: int) -> np.ndarray:
        """Return integer pixel coordinates of the 4 water corners (shape: (4, 2))."""
        pts = [
            [int(round(x * width)), int(round(y * height))]
            for x, y in self.pool_corners_norm
        ]
        return np.array(pts, dtype=np.int32)

    def water_polygon_norm(self) -> list[tuple[float, float]]:
        """Return the 4 normalized water corners [TL, TR, BR, BL]."""
        return list(self.pool_corners_norm)

    def destination_corners_m(self) -> np.ndarray:
        """Compute the physical pool destination coordinates for [TL, TR, BR, BL].

        Physical coordinate convention:
        - x_m in [0.0, length_m]: longitudinal axis (0.0 = shallow end, length_m = deep end)
        - y_m in [0.0, width_m]: transverse axis across pool
        - depth_boundary_m divides shallow (x < depth_boundary_m) and deep (x >= depth_boundary_m)
        """
        length = float(self.length_m)
        width = float(self.width_m)

        if self.deep_end_side == "left":
            # Image left (TL, BL) is deep end (x=length), image right (TR, BR) is shallow (x=0)
            dst = np.array(
                [
                    [length, 0.0],
                    [0.0, 0.0],
                    [0.0, width],
                    [length, width],
                ],
                dtype=np.float32,
            )
        elif self.deep_end_side == "bottom":
            # Image top (TL, TR) is shallow (x=0), image bottom (BL, BR) is deep (x=length)
            dst = np.array(
                [
                    [0.0, 0.0],
                    [0.0, width],
                    [length, width],
                    [length, 0.0],
                ],
                dtype=np.float32,
            )
        elif self.deep_end_side == "top":
            # Image top (TL, TR) is deep (x=length), image bottom (BL, BR) is shallow (x=0)
            dst = np.array(
                [
                    [length, 0.0],
                    [length, width],
                    [0.0, width],
                    [0.0, 0.0],
                ],
                dtype=np.float32,
            )
        else:
            # Default "right": image left (TL, BL) is shallow (x=0), image right (TR, BR) is deep (x=length)
            dst = np.array(
                [
                    [0.0, 0.0],
                    [length, 0.0],
                    [length, width],
                    [0.0, width],
                ],
                dtype=np.float32,
            )
        return dst

    def compute_homography(self, width: int, height: int) -> np.ndarray:
        """Compute 3x3 homography matrix mapping image pixels -> physical pool meters (x_m, y_m)."""
        src = self.water_polygon_px(width, height).astype(np.float32)
        dst = self.destination_corners_m()

        H, _ = cv2.findHomography(src, dst)
        if H is None or not np.isfinite(H).all():
            raise ValueError(
                "Invalid calibration geometry: homography could not be computed from corner points"
            )

        det = float(np.linalg.det(H))
        if abs(det) < 1e-12:
            raise ValueError(
                "Invalid calibration geometry: homography matrix is singular or degenerate"
            )
        return H

    def compute_inverse_homography(self, width: int, height: int) -> np.ndarray:
        """Compute 3x3 inverse homography matrix mapping physical pool meters -> image pixels."""
        H = self.compute_homography(width, height)
        try:
            return np.linalg.inv(H)
        except np.linalg.LinAlgError as err:
            raise ValueError("Cannot invert homography matrix") from err

    def to_pool_m(self, px: float, py: float, width: int, height: int) -> tuple[float, float]:
        """Convert image pixel coordinate `(px, py)` to pool meter coordinate `(x_m, y_m)`."""
        H = self.compute_homography(width, height)
        pt = np.array([[[px, py]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, H)
        tx = float(np.clip(transformed[0, 0, 0], 0.0, self.length_m))
        ty = float(np.clip(transformed[0, 0, 1], 0.0, self.width_m))
        return (round(tx, 2), round(ty, 2))

    def from_pool_m(self, x_m: float, y_m: float, width: int, height: int) -> tuple[float, float]:
        """Convert physical pool meter coordinate `(x_m, y_m)` to image pixel coordinate `(px, py)`."""
        H_inv = self.compute_inverse_homography(width, height)
        pt = np.array([[[x_m, y_m]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, H_inv)
        px = float(transformed[0, 0, 0])
        py = float(transformed[0, 0, 1])
        return (round(px, 1), round(py, 1))

    def from_pool_m_norm(
        self, x_m: float, y_m: float, width: int = 1280, height: int = 720
    ) -> tuple[float, float]:
        """Convert physical pool meter coordinate `(x_m, y_m)` to normalized coordinate `(nx, ny)` in [0..1]."""
        px, py = self.from_pool_m(x_m, y_m, width, height)
        nx = max(0.0, min(1.0, px / max(1, width)))
        ny = max(0.0, min(1.0, py / max(1, height)))
        return (round(nx, 4), round(ny, 4))

    def projected_boundary_px(self, width: int, height: int) -> list[tuple[float, float]]:
        """Return the pixel coordinates of the shallow/deep boundary line endpoints [(x1, y1), (x2, y2)]."""
        pt1 = self.from_pool_m(self.depth_boundary_m, 0.0, width, height)
        pt2 = self.from_pool_m(self.depth_boundary_m, self.width_m, width, height)
        return [pt1, pt2]

    def projected_boundary_norm(
        self, width: int = 1280, height: int = 720
    ) -> list[tuple[float, float]]:
        """Return normalized coordinates of shallow/deep boundary endpoints [(nx1, ny1), (nx2, ny2)]."""
        pt1 = self.from_pool_m_norm(self.depth_boundary_m, 0.0, width, height)
        pt2 = self.from_pool_m_norm(self.depth_boundary_m, self.width_m, width, height)
        return [pt1, pt2]

    def in_water(self, px: float, py: float, width: int, height: int) -> bool:
        """Return True if pixel `(px, py)` lies inside or on the calibrated water boundary."""
        poly = self.water_polygon_px(width, height)
        dist = cv2.pointPolygonTest(poly, (float(px), float(py)), measureDist=False)
        return dist >= 0

    def zone_for(
        self,
        x_m: float,
        in_water: bool,
        y_m: float | None = None,  # noqa: ARG002
        uncertainty_buffer_m: float = 0.0,
    ) -> PoolZone:
        """Determine whether track is in ZONE_A_SHALLOW, ZONE_B_DEEP_END, POOL_DECK, or UNKNOWN.

        Uses the verified calibration boundary `depth_boundary_m` and handles boundary uncertainty.
        """
        if not in_water:
            return PoolZone.POOL_DECK

        if not math.isfinite(x_m) or x_m < 0.0 or x_m > self.length_m:
            return PoolZone.UNKNOWN

        # Optional uncertainty hysteresis near boundary
        if uncertainty_buffer_m > 0.0 and abs(x_m - self.depth_boundary_m) < uncertainty_buffer_m:
            return PoolZone.UNKNOWN

        return (
            PoolZone.ZONE_B_DEEP_END
            if x_m >= self.depth_boundary_m
            else PoolZone.ZONE_A_SHALLOW
        )

    def metres_per_px_at(self, px: float, py: float, width: int, height: int) -> float:
        """Estimate physical meters per vertical pixel at a given point (for height estimation)."""
        p1 = self.to_pool_m(px, py, width, height)
        p2 = self.to_pool_m(px, min(float(height), py + 20.0), width, height)
        dist_m = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
        return max(0.005, dist_m / 20.0)

    def validate_geometry(
        self, width: int = 1280, height: int = 720
    ) -> CalibrationValidationResult:
        """Validate pool geometry, corners, dimensions, depths, and homography.

        Returns CalibrationValidationResult with detailed error/warning messages.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Corner count & coordinate bounds
        if len(self.pool_corners_norm) != 4:
            errors.append(f"Expected exactly 4 corners, but found {len(self.pool_corners_norm)}.")
            return CalibrationValidationResult(is_valid=False, errors=errors, warnings=warnings)

        for idx, (cx, cy) in enumerate(self.pool_corners_norm):
            if not (math.isfinite(cx) and math.isfinite(cy)):
                errors.append(f"Corner #{idx} coordinates must be finite numbers.")
            elif not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
                errors.append(f"Corner #{idx} ({cx:.2f}, {cy:.2f}) is outside normalized frame [0..1].")

        if errors:
            return CalibrationValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # 2. Quadrilateral area check (Shoelace formula)
        pts = self.pool_corners_norm
        shoelace_area = 0.5 * abs(
            pts[0][0] * (pts[1][1] - pts[3][1])
            + pts[1][0] * (pts[2][1] - pts[0][1])
            + pts[2][0] * (pts[3][1] - pts[1][1])
            + pts[3][0] * (pts[0][1] - pts[2][1])
        )
        if shoelace_area < 0.005:
            errors.append(
                f"Calibrated water surface area ({shoelace_area:.4f}) is too small (< 0.5% of frame)."
            )

        # 3. Convexity and corner ordering check (cross products of consecutive edges)
        cross_products = []
        for i in range(4):
            p_curr = pts[i]
            p_next = pts[(i + 1) % 4]
            p_after = pts[(i + 2) % 4]
            v1 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
            v2 = (p_after[0] - p_next[0], p_after[1] - p_next[1])
            cp = v1[0] * v2[1] - v1[1] * v2[0]
            cross_products.append(cp)

        # In screen coordinates (Y down), standard clockwise order [TL, TR, BR, BL] yields positive cross products
        has_pos = any(cp > 1e-6 for cp in cross_products)
        has_neg = any(cp < -1e-6 for cp in cross_products)
        has_zero = any(abs(cp) <= 1e-6 for cp in cross_products)

        if has_zero:
            errors.append("Three or more corners are collinear, forming a degenerate polygon.")
        elif has_pos and has_neg:
            errors.append(
                "Corner polygon is self-intersecting (hourglass/bowtie) or concave. "
                "Ensure corners are ordered [Top-Left, Top-Right, Bottom-Right, Bottom-Left]."
            )
        elif has_neg and not has_pos:
            warnings.append(
                "Corners appear counter-clockwise; standard convention is clockwise [TL, TR, BR, BL]."
            )

        # 4. Physical dimensions and depths
        if self.length_m < 2.0 or self.length_m > 150.0:
            errors.append(f"Pool length ({self.length_m}m) must be between 2.0m and 150.0m.")
        if self.width_m < 1.0 or self.width_m > 50.0:
            errors.append(f"Pool width ({self.width_m}m) must be between 1.0m and 50.0m.")
        if self.shallow_depth_m < 0.1 or self.shallow_depth_m > 5.0:
            errors.append(f"Shallow depth ({self.shallow_depth_m}m) must be between 0.1m and 5.0m.")
        if self.deep_depth_m < 0.1 or self.deep_depth_m > 10.0:
            errors.append(f"Deep depth ({self.deep_depth_m}m) must be between 0.1m and 10.0m.")
        if self.deep_depth_m <= self.shallow_depth_m:
            errors.append(
                f"Deep depth ({self.deep_depth_m}m) must be strictly greater than shallow depth ({self.shallow_depth_m}m)."
            )
        if self.depth_boundary_m <= 0.0 or self.depth_boundary_m >= self.length_m:
            errors.append(
                f"Depth boundary ({self.depth_boundary_m}m) must lie strictly inside pool length (0..{self.length_m}m)."
            )

        if errors:
            return CalibrationValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # 5. Homography computation & invertibility
        sample_mappings: list[dict[str, Any]] = []
        projected_boundary: list[tuple[float, float]] = []
        try:
            self.compute_homography(width, height)
            self.compute_inverse_homography(width, height)

            # Test corner transformations
            dst_expected = self.destination_corners_m()
            src_px = self.water_polygon_px(width, height)
            for idx in range(4):
                px, py = float(src_px[idx][0]), float(src_px[idx][1])
                mapped_m = self.to_pool_m(px, py, width, height)
                exp_x, exp_y = dst_expected[idx][0], dst_expected[idx][1]
                diff = math.hypot(mapped_m[0] - exp_x, mapped_m[1] - exp_y)
                if diff > 0.5:
                    errors.append(
                        f"Corner #{idx} mapping error ({diff:.2f}m) exceeds tolerance (0.5m)."
                    )
                sample_mappings.append(
                    {
                        "corner_index": idx,
                        "pixel": [px, py],
                        "mapped_m": mapped_m,
                        "expected_m": [round(float(exp_x), 2), round(float(exp_y), 2)],
                        "error_m": round(diff, 3),
                    }
                )

            # Test center point
            center_x = float(np.mean(src_px[:, 0]))
            center_y = float(np.mean(src_px[:, 1]))
            center_m = self.to_pool_m(center_x, center_y, width, height)
            sample_mappings.append(
                {
                    "point": "center",
                    "pixel": [center_x, center_y],
                    "mapped_m": center_m,
                }
            )

            # 6. Projected boundary line test
            projected_boundary = self.projected_boundary_norm(width, height)
            b_mid_m = (self.depth_boundary_m, self.width_m / 2.0)
            b_mid_px = self.from_pool_m(b_mid_m[0], b_mid_m[1], width, height)
            if not self.in_water(b_mid_px[0], b_mid_px[1], width, height):
                errors.append(
                    "Projected depth boundary midpoint falls outside the calibrated water polygon."
                )

        except Exception as e:
            errors.append(f"Homography mathematical validation failed: {e}")

        is_valid = len(errors) == 0
        return CalibrationValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            projected_boundary_norm=projected_boundary,
            sample_mappings=sample_mappings,
        )
