"""Two-Tier Malaysia PDPA 2010 & PDPA (Amendment) Act 2024 Privacy Shield.

- Tier 1 (`apply_tier1_face_mask`): Redacts ONLY the head/face bounding box derived from
  COCO keypoints `kp[0..4]` (nose, eyes, ears) with solid `[0, 0, 0]` black before
  passing a cropped ROI to System 2 (`agentic_inspector.py`).
- Tier 2 (`render_tier2_silhouette_frame`): Renders a fresh dark architectural pool blueprint
  canvas with glowing neon 17-keypoint skeletal silhouettes and zero raw camera/skin pixels.
"""

from __future__ import annotations

import cv2
import numpy as np

from aquapulse.config import CANVAS_HEIGHT_PX, CANVAS_WIDTH_PX
from aquapulse.schemas import (
    AgentState,
    DetectedObject,
    PostureState,
    SwimmerRole,
    SwimmerTrack,
    ViolationType,
)

# Standard COCO 17-keypoint body limb pairs (excluding facial keypoints 0..4 so faces stay anonymous)
COCO_BODY_EDGES: tuple[tuple[int, int], ...] = (
    (5, 6),  # shoulders
    (5, 7),  # left upper arm
    (7, 9),  # left forearm
    (6, 8),  # right upper arm
    (8, 10),  # right forearm
    (5, 11),  # left torso
    (6, 12),  # right torso
    (11, 12),  # hips
    (11, 13),  # left thigh
    (13, 15),  # left calf
    (12, 14),  # right thigh
    (14, 16),  # right calf
)


def compute_head_bbox(
    track: SwimmerTrack,
    frame_shape: tuple[int, int, int],
) -> tuple[int, int, int, int]:
    """Compute an expanded `(x1, y1, x2, y2)` head/face bounding box from `kp[0..4]`."""
    h, w = frame_shape[:2]
    bx1, by1, bx2, by2 = track.bbox
    bw = max(12, bx2 - bx1)
    bh = max(16, by2 - by1)

    head_kps = [kp for kp in track.keypoints[:5] if kp.conf > 0.2]
    if head_kps:
        xs = [kp.x for kp in head_kps]
        ys = [kp.y for kp in head_kps]
        pad_x = max(12, int(bw * 0.28))
        pad_y = max(12, int(bh * 0.18))
        hx1 = max(0, int(min(xs)) - pad_x)
        hy1 = max(0, int(min(ys)) - pad_y)
        hx2 = min(w, int(max(xs)) + pad_x)
        hy2 = min(h, int(max(ys)) + pad_y)
        if hx2 > hx1 and hy2 > hy1:
            return (hx1, hy1, hx2, hy2)

    # Fallback: top 30% of person bounding box
    hx1 = max(0, bx1)
    hy1 = max(0, by1)
    hx2 = min(w, bx2)
    hy2 = min(h, by1 + max(12, int(bh * 0.30)))
    return (hx1, hy1, hx2, hy2)


def apply_tier1_face_mask(
    frame: np.ndarray,
    track: SwimmerTrack,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Apply Tier-1 PDPA Face Redaction (`[0, 0, 0]` solid blackout on `kp[0..4]`).

    Preserves torso and hand pixels below the neck so System 2 can verify cotton
    fabric texture, food/drink containers, or smoking without exposing facial biometrics.
    """
    masked = frame.copy()
    hx1, hy1, hx2, hy2 = compute_head_bbox(track, masked.shape)
    masked[hy1:hy2, hx1:hx2] = 0
    return masked, (hx1, hy1, hx2, hy2)


def render_tier2_silhouette_frame(
    tracks: list[SwimmerTrack],
    objects: list[DetectedObject] | None = None,
    overall_state: AgentState = AgentState.NORMAL,
    width: int = CANVAS_WIDTH_PX,
    height: int = CANVAS_HEIGHT_PX,
) -> np.ndarray:
    """Render Tier-2 PDPA Skeletal Silhouette Mode on a dark architectural pool blueprint.

    Contains 0% raw camera/skin pixels—every swimmer is rendered strictly as a
    neon 17-keypoint skeletal silhouette with anonymized head circle and track badge.
    """
    canvas = np.zeros((height, width, 3), dtype=np.uint8)

    # 1. Pool Deck dark blueprint background (#0B1622 -> BGR (34, 22, 11))
    canvas[:, :] = (34, 22, 11)

    # 2. Zone A Shallow Basin (x: 40..310, y: 60..300) & Zone B Deep End (x: 310..600, y: 60..300)
    cv2.rectangle(canvas, (40, 60), (310, 300), (68, 44, 16), thickness=-1)
    cv2.rectangle(canvas, (310, 60), (600, 300), (50, 30, 9), thickness=-1)

    # 3. Blueprint grid & lane lines
    for gx in range(60, 600, 40):
        cv2.line(canvas, (gx, 60), (gx, 300), (78, 52, 22), 1)
    for ly in (110, 160, 200, 250):
        cv2.line(canvas, (40, ly), (600, ly), (95, 65, 28), 1)

    # Pool basin outer border & 12.5m Deep-End Transition Line (x=310)
    cv2.rectangle(canvas, (40, 60), (600, 300), (180, 140, 60), 2)
    cv2.line(canvas, (310, 60), (310, 300), (0, 210, 255), 2)

    # Zone headers & PDPA Compliance watermark
    cv2.putText(
        canvas,
        "PDPA TIER-2 SKELETAL SILHOUETTE SHIELD (0% RAW BIOMETRIC PIXELS)",
        (14, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (212, 245, 0),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        f"STATE: {overall_state.value}",
        (430, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (90, 90, 255)
        if overall_state in (AgentState.CRITICAL_EMERGENCY, AgentState.VERIFY)
        else (180, 240, 120),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "ZONE A: SHALLOW / TODDLER (0.8m)",
        (52, 78),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (200, 180, 120),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "ZONE B: DEEP END (1.8m)",
        (325, 78),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (160, 160, 230),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "POOL DECK PERIMETER",
        (52, 342),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (140, 150, 165),
        1,
        cv2.LINE_AA,
    )

    # 4. Render detected poolside objects / animals / debris as geometric blueprint markers
    if objects:
        for obj in objects:
            ox1, oy1, ox2, oy2 = obj.bbox
            if "debris" in obj.label or "leaf" in obj.label:
                cx, cy = (ox1 + ox2) // 2, (oy1 + oy2) // 2
                cv2.circle(canvas, (cx, cy), 5, (60, 180, 90), -1)
                cv2.circle(canvas, (cx, cy), 7, (90, 220, 120), 1)
            elif obj.label in {"dog", "cat", "bird"}:
                cx, cy = (ox1 + ox2) // 2, (oy1 + oy2) // 2
                cv2.rectangle(canvas, (ox1, oy1), (ox2, oy2), (80, 110, 255), 2)
                cv2.ellipse(canvas, (cx, cy), (8, 4), 0, 0, 360, (80, 110, 255), 2)
                cv2.putText(
                    canvas,
                    f"ANIMAL:{obj.label.upper()}",
                    (ox1 - 4, max(14, oy1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    (80, 130, 255),
                    1,
                    cv2.LINE_AA,
                )
            else:
                cv2.rectangle(canvas, (ox1, oy1), (ox2, oy2), (0, 180, 255), 1)
                cv2.putText(
                    canvas,
                    obj.label.upper(),
                    (ox1, max(12, oy1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.33,
                    (0, 200, 255),
                    1,
                    cv2.LINE_AA,
                )

    # 5. Render each swimmer strictly as a color-coded neon 17-keypoint skeleton
    for track in tracks:
        if (
            track.is_flailing
            or track.is_submerged
            or track.posture
            in (
                PostureState.ACTIVE_FLAILING,
                PostureState.HORIZONTAL_SUBMERGED,
            )
        ):
            color = (110, 45, 255)  # Neon crimson/magenta for System 1 distress
        elif track.near_deep_boundary or track.suspected_violation != ViolationType.NONE:
            color = (60, 210, 255)  # Neon amber for toddler caution or System 2 governance
        elif track.role == SwimmerRole.LAP_SWIMMER:
            color = (255, 220, 60)  # Neon cyan-blue for lap swimmers
        else:
            color = (190, 245, 0)  # Neon aqua-green for normal swimmers

        kps = track.keypoints
        if len(kps) >= 17:
            # Draw anonymized head ring (centered on nose kp[0], no facial features)
            nose = kps[0]
            cv2.circle(
                canvas,
                (int(nose.x), int(nose.y)),
                8 if track.role != SwimmerRole.TODDLER else 6,
                color,
                2,
                cv2.LINE_AA,
            )
            # Draw limb vectors
            for i, j in COCO_BODY_EDGES:
                p1 = (int(kps[i].x), int(kps[i].y))
                p2 = (int(kps[j].x), int(kps[j].y))
                cv2.line(canvas, p1, p2, color, 2, cv2.LINE_AA)
            # Draw joint keypoints (5..16)
            for idx in range(5, 17):
                pt = (int(kps[idx].x), int(kps[idx].y))
                cv2.circle(canvas, pt, 3, (255, 255, 255), -1, cv2.LINE_AA)
        else:
            # Fallback stick silhouette inside bbox if keypoints weren't populated
            bx1, by1, bx2, by2 = track.bbox
            cx, cy = (bx1 + bx2) // 2, (by1 + by2) // 2
            cv2.circle(canvas, (cx, by1 + 8), 7, color, 2, cv2.LINE_AA)
            cv2.line(canvas, (cx, by1 + 15), (cx, cy + 8), color, 2, cv2.LINE_AA)
            cv2.line(canvas, (cx - 10, cy - 2), (cx + 10, cy - 2), color, 2, cv2.LINE_AA)

        bx1, by1, _, _ = track.bbox
        tag = f"#{track.track_id} {track.role.value[:4]}"
        if track.is_flailing:
            tag += " [FLAILING!]"
        elif track.is_submerged:
            tag += " [SUBMERGED!]"
        elif track.near_deep_boundary:
            tag += " [NEAR DEEP]"
        elif track.suspected_violation != ViolationType.NONE:
            tag += f" [{track.suspected_violation.value[:6]}]"

        cv2.putText(
            canvas,
            tag,
            (max(6, bx1 - 4), max(36, by1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            color,
            1,
            cv2.LINE_AA,
        )

    return canvas


def mask_heads_full_res(
    frame: np.ndarray,
    head_boxes: list[tuple[int, int, int, int]],
    margin: float = 0.35,
    blur: bool = False,
) -> np.ndarray:
    """Mask head/face bounding boxes at full frame resolution for Tier-1 PDPA compliance.

    When blur is False (default for Tier-1 security), heads are redacted in solid black.
    When blur is True, heavy pixelation/Gaussian blur is applied.
    """
    output = frame.copy()
    h, w = frame.shape[:2]

    for x1, y1, x2, y2 in head_boxes:
        bw, bh = x2 - x1, y2 - y1
        if bw <= 0 or bh <= 0:
            continue
        pad_x = int(bw * margin)
        pad_y = int(bh * margin)
        rx1 = max(0, x1 - pad_x)
        ry1 = max(0, y1 - pad_y)
        rx2 = min(w, x2 + pad_x)
        ry2 = min(h, y2 + pad_y)

        if blur:
            roi = output[ry1:ry2, rx1:rx2]
            if roi.size > 0:
                ksize = max(15, (min(rx2 - rx1, ry2 - ry1) // 2) * 2 + 1)
                output[ry1:ry2, rx1:rx2] = cv2.GaussianBlur(roi, (ksize, ksize), 30)
        else:
            # Solid black oval for biometric identity redaction
            center = ((rx1 + rx2) // 2, (ry1 + ry2) // 2)
            axes = ((rx2 - rx1) // 2, (ry2 - ry1) // 2)
            cv2.ellipse(output, center, axes, 0, 0, 360, (0, 0, 0), -1)

    return output
