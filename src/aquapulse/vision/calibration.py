"""Pool perspective calibration and pixel-to-meter homography mapping."""

from __future__ import annotations

import math
from typing import Literal

import cv2
import numpy as np
from pydantic import BaseModel, Field

from aquapulse.config import (
    DEEP_END_BOUNDARY_X_M,
    POOL_LENGTH_M,
    POOL_WIDTH_M,
)
from aquapulse.schemas import PoolZone


class PoolCalibration(BaseModel):
    """Calibrates camera perspective to 25m x 12m Malaysian strata condominium pool basin."""

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
        description="Side of the pool that corresponds to the deep end (>=12.5m)",
    )
    deck_margin_norm: float = Field(
        default=0.04,
        ge=0.0,
        le=0.2,
        description="Deck boundary margin buffer around pool water polygon",
    )

    def water_polygon_px(self, width: int, height: int) -> np.ndarray:
        """Return integer pixel coordinates of the 4 water corners (shape: (4, 2))."""
        pts = [
            [int(round(x * width)), int(round(y * height))]
            for x, y in self.pool_corners_norm
        ]
        return np.array(pts, dtype=np.int32)

    def compute_homography(self, width: int, height: int) -> np.ndarray:
        """Compute 3x3 homography matrix mapping image pixels -> physical pool meters (x_m, y_m)."""
        src = self.water_polygon_px(width, height).astype(np.float32)

        # Map to physical pool meter coordinates (0..25m along length, 0..12m along width)
        # Standard: TL=(0,0), TR=(25,0), BR=(25,12), BL=(0,12)
        # If deep_end_side is "left", flip X so deep end is x>=12.5m
        if self.deep_end_side == "left":
            # Left side is deep end -> flip X coordinates so x=25 is deep
            dst = np.array(
                [
                    [POOL_LENGTH_M, 0.0],
                    [0.0, 0.0],
                    [0.0, POOL_WIDTH_M],
                    [POOL_LENGTH_M, POOL_WIDTH_M],
                ],
                dtype=np.float32,
            )
        elif self.deep_end_side == "bottom":
            # Rotated 90 deg: bottom is deep end
            dst = np.array(
                [
                    [0.0, 0.0],
                    [0.0, POOL_WIDTH_M],
                    [POOL_LENGTH_M, POOL_WIDTH_M],
                    [POOL_LENGTH_M, 0.0],
                ],
                dtype=np.float32,
            )
        elif self.deep_end_side == "top":
            dst = np.array(
                [
                    [POOL_LENGTH_M, 0.0],
                    [POOL_LENGTH_M, POOL_WIDTH_M],
                    [0.0, POOL_WIDTH_M],
                    [0.0, 0.0],
                ],
                dtype=np.float32,
            )
        else:
            # Default "right": TL=(0,0) shallow, TR=(25,0) deep, BR=(25,12) deep, BL=(0,12) shallow
            dst = np.array(
                [
                    [0.0, 0.0],
                    [POOL_LENGTH_M, 0.0],
                    [POOL_LENGTH_M, POOL_WIDTH_M],
                    [0.0, POOL_WIDTH_M],
                ],
                dtype=np.float32,
            )

        H, _ = cv2.findHomography(src, dst)
        if H is None:
            # Degenerate fallback: linear scale
            H = np.array(
                [
                    [POOL_LENGTH_M / max(1, width), 0.0, 0.0],
                    [0.0, POOL_WIDTH_M / max(1, height), 0.0],
                    [0.0, 0.0, 1.0],
                ],
                dtype=np.float64,
            )
        return H

    def to_pool_m(self, px: float, py: float, width: int, height: int) -> tuple[float, float]:
        """Convert image pixel coordinate `(px, py)` to pool meter coordinate `(x_m, y_m)`."""
        H = self.compute_homography(width, height)
        pt = np.array([[[px, py]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, H)
        tx = float(np.clip(transformed[0, 0, 0], 0.0, POOL_LENGTH_M))
        ty = float(np.clip(transformed[0, 0, 1], 0.0, POOL_WIDTH_M))
        return (round(tx, 2), round(ty, 2))

    def in_water(self, px: float, py: float, width: int, height: int) -> bool:
        """Return True if pixel `(px, py)` lies inside or on the calibrated water boundary."""
        poly = self.water_polygon_px(width, height)
        dist = cv2.pointPolygonTest(poly, (float(px), float(py)), measureDist=False)
        return dist >= 0

    def zone_for(self, x_m: float, in_water: bool) -> PoolZone:
        """Determine whether track is in ZONE_A_SHALLOW, ZONE_B_DEEP_END, or POOL_DECK."""
        if not in_water:
            return PoolZone.POOL_DECK
        return (
            PoolZone.ZONE_B_DEEP_END
            if x_m >= DEEP_END_BOUNDARY_X_M
            else PoolZone.ZONE_A_SHALLOW
        )

    def metres_per_px_at(self, px: float, py: float, width: int, height: int) -> float:
        """Estimate physical meters per vertical pixel at a given point (for height estimation)."""
        p1 = self.to_pool_m(px, py, width, height)
        p2 = self.to_pool_m(px, min(float(height), py + 20.0), width, height)
        dist_m = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
        return max(0.005, dist_m / 20.0)
