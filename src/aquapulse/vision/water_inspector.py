"""OpenCV Visual Water Clarity, Green-Algae Drift & Monsoon Storm Debris Inspector."""

from __future__ import annotations

from typing import Literal

import cv2
import numpy as np

from aquapulse.schemas import WaterClarityReport


def inspect_water_clarity(
    frame: np.ndarray,
) -> tuple[WaterClarityReport, np.ndarray]:
    """Analyze pool water basin ROI for turbidity, algae green-shift, and storm debris.

    Returns `(WaterClarityReport, annotated_overlay_bgr)`.
    """
    annotated = frame.copy()
    h, w = frame.shape[:2]

    # Pool basin ROI coordinates (matching 640x360 layout or scaled proportionally)
    x1, y1 = int(w * 40 / 640), int(h * 60 / 360)
    x2, y2 = int(w * 600 / 640), int(h * 300 / 360)
    water_roi = frame[y1:y2, x1:x2]

    if water_roi.size == 0:
        report = WaterClarityReport(
            turbidity_score=95.0,
            algae_green_index=18.0,
            floating_debris_count=0,
            status="CRYSTAL_CLEAR",
            cleaner_ticket_opened=False,
        )
        return report, annotated

    # 1. HSV Green-Algae Drift Index
    hsv = cv2.cvtColor(water_roi, cv2.COLOR_BGR2HSV)
    # Measure green-shifted hue pixels (H in [32..86]) vs normal cyan-blue water (H in [88..118])
    green_mask = cv2.inRange(hsv, (32, 35, 30), (86, 255, 255))
    green_ratio = float(np.count_nonzero(green_mask)) / float(
        water_roi.shape[0] * water_roi.shape[1]
    )
    mean_b = float(np.mean(water_roi[:, :, 0])) + 1.0
    mean_g = float(np.mean(water_roi[:, :, 1]))
    gb_ratio = mean_g / mean_b

    algae_green_index = round(
        float(np.clip((gb_ratio - 0.55) * 48.0 + green_ratio * 65.0, 8.0, 98.0)),
        1,
    )

    # 2. Floating Monsoon Storm Debris Contours (dark organic leaf/branch blobs on water)
    # Leaves/twigs rendered or captured on water have low Value or distinct dark olive/brown hue
    debris_mask = cv2.inRange(hsv, (10, 40, 15), (78, 255, 135))
    kernel = np.ones((3, 3), np.uint8)
    debris_mask = cv2.morphologyEx(debris_mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(debris_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    debris_count = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 8.0 <= area <= 1500.0:
            debris_count += 1
            cx, cy, cw, ch = cv2.boundingRect(cnt)
            center = (x1 + cx + cw // 2, y1 + cy + ch // 2)
            radius = max(6, max(cw, ch) // 2 + 3)
            cv2.circle(annotated, center, radius, (0, 140, 255), 2, cv2.LINE_AA)

    # 3. Laplacian Floor-Tile Contrast / Turbidity Score (0..100, higher = clearer)
    gray_water = cv2.cvtColor(water_roi, cv2.COLOR_BGR2GRAY)
    lap_var = float(cv2.Laplacian(gray_water, cv2.CV_64F).var())
    # Combine tile sharpness with green-shift and debris penalties
    raw_clarity = 86.0 + min(12.5, lap_var / 35.0) - max(0.0, (algae_green_index - 24.0) * 0.65)
    raw_clarity -= min(10.0, debris_count * 0.45)
    turbidity_score = round(float(np.clip(raw_clarity, 40.0, 99.0)), 1)

    # 4. Classify Water Status & JMB Cleaner Work Order Decision
    status: Literal[
        "CRYSTAL_CLEAR",
        "SLIGHT_TURBIDITY",
        "ALGAE_WARNING",
        "MONSOON_DEBRIS_ALERT",
    ]
    if debris_count >= 8:
        status = "MONSOON_DEBRIS_ALERT"
        cleaner_ticket = True
        action = (
            f"Auto-dispatched JMB morning skimmer crew: {debris_count} floating monsoon "
            f"leaves/branches detected + algae index {algae_green_index:.1f}."
        )
    elif algae_green_index >= 35.0:
        status = "ALGAE_WARNING"
        cleaner_ticket = True
        action = (
            f"Early green-algae tint drift detected (Green Index={algae_green_index:.1f}). "
            f"Schedule proactive chlorine dosing & filter backwash before bloom requires drainage."
        )
    elif turbidity_score < 82.0:
        status = "SLIGHT_TURBIDITY"
        cleaner_ticket = False
        action = (
            f"Floor-tile contrast slightly reduced ({turbidity_score:.1f}/100); "
            f"increase VFD filtration turnover."
        )
    else:
        status = "CRYSTAL_CLEAR"
        cleaner_ticket = False
        action = "No maintenance required; floor-tile contrast and water clarity optimal."

    # Draw HUD summary bar on annotated water inspection frame
    cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 200, 0), 1)
    cv2.putText(
        annotated,
        f"WATER QA: {status} | Clarity={turbidity_score}/100 | GreenIdx={algae_green_index} | Debris={debris_count}",
        (16, h - 14),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.40,
        (80, 230, 255) if cleaner_ticket else (160, 255, 160),
        1,
        cv2.LINE_AA,
    )

    report = WaterClarityReport(
        turbidity_score=turbidity_score,
        algae_green_index=algae_green_index,
        floating_debris_count=debris_count,
        status=status,
        cleaner_ticket_opened=cleaner_ticket,
        recommended_action=action,
    )
    return report, annotated
