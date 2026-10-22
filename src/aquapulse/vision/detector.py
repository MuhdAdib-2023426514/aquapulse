"""Pre-Trained YOLO26 Pose/Object Tracker & Deterministic 6-Scenario Synthesizer."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from aquapulse.config import (
    CANVAS_HEIGHT_PX,
    CANVAS_WIDTH_PX,
    DEEP_END_BOUNDARY_X_M,
    MODELS_DIR,
    POOL_LENGTH_M,
    POOL_WIDTH_M,
    TODDLER_DEEP_BOUNDARY_BUFFER_M,
    YOLO26_DETECT_MODEL_NAME,
    YOLO26_POSE_MODEL_NAME,
)
from aquapulse.schemas import (
    DetectedObject,
    Keypoint2D,
    PoolZone,
    PostureState,
    ScenarioName,
    SwimmerRole,
    SwimmerTrack,
    ViolationType,
)


def pixel_to_pool_meters(px_x: float, px_y: float) -> tuple[float, float]:
    """Convert `(px_x, px_y)` on the 640x360 canvas to `(x_m, y_m)` in the 25m x 12m pool."""
    x_m = float(np.clip((px_x - 40.0) / 560.0 * POOL_LENGTH_M, 0.0, POOL_LENGTH_M))
    y_m = float(np.clip((px_y - 60.0) / 240.0 * POOL_WIDTH_M, 0.0, POOL_WIDTH_M))
    return (round(x_m, 2), round(y_m, 2))


def pool_meters_to_pixel(x_m: float, y_m: float) -> tuple[int, int]:
    """Convert `(x_m, y_m)` physical pool coordinates to `(px_x, px_y)` on the 640x360 canvas."""
    px_x = int(round(40.0 + (x_m / POOL_LENGTH_M) * 560.0))
    px_y = int(round(60.0 + (y_m / POOL_WIDTH_M) * 240.0))
    return (px_x, px_y)


def build_coco_keypoints(
    cx: int,
    cy: int,
    *,
    posture: PostureState = PostureState.ACTIVE_SWIM,
    role: SwimmerRole = SwimmerRole.ADULT,
    elapsed_sec: float = 0.0,
) -> tuple[list[Keypoint2D], tuple[int, int, int, int]]:
    """Construct 17 COCO keypoints and `(x1, y1, x2, y2)` bbox for a tracked swimmer."""
    scale = 0.65 if role == SwimmerRole.TODDLER else 1.0
    wave_arm = int(round(6.0 * math.sin(elapsed_sec * 4.5)))

    if posture == PostureState.ACTIVE_FLAILING:
        # Instinctive Drowning Response: vertical bobbing with wrists raised above/near shoulders
        flail_dy = int(round(9.0 * math.sin(elapsed_sec * 9.0)))
        pts = [
            (cx, cy - int(22 * scale)),  # 0: nose
            (cx - 3, cy - int(25 * scale)),  # 1: left_eye
            (cx + 3, cy - int(25 * scale)),  # 2: right_eye
            (cx - 6, cy - int(23 * scale)),  # 3: left_ear
            (cx + 6, cy - int(23 * scale)),  # 4: right_ear
            (cx - int(12 * scale), cy - int(10 * scale)),  # 5: left_shoulder
            (cx + int(12 * scale), cy - int(10 * scale)),  # 6: right_shoulder
            (cx - int(18 * scale), cy - int(16 * scale) + flail_dy),  # 7: left_elbow
            (cx + int(18 * scale), cy - int(16 * scale) - flail_dy),  # 8: right_elbow
            (cx - int(20 * scale), cy - int(24 * scale) + flail_dy),  # 9: left_wrist (high!)
            (cx + int(20 * scale), cy - int(24 * scale) - flail_dy),  # 10: right_wrist (high!)
            (cx - int(8 * scale), cy + int(10 * scale)),  # 11: left_hip
            (cx + int(8 * scale), cy + int(10 * scale)),  # 12: right_hip
            (cx - int(9 * scale), cy + int(20 * scale)),  # 13: left_knee
            (cx + int(9 * scale), cy + int(20 * scale)),  # 14: right_knee
            (cx - int(9 * scale), cy + int(28 * scale)),  # 15: left_ankle
            (cx + int(9 * scale), cy + int(28 * scale)),  # 16: right_ankle
        ]
    elif posture in (PostureState.HORIZONTAL_SUBMERGED, PostureState.ACTIVE_SWIM):
        # Horizontal torso orientation along X axis
        arm_reach = 0 if posture == PostureState.HORIZONTAL_SUBMERGED else wave_arm
        pts = [
            (cx + int(22 * scale), cy - 2),  # 0: nose
            (cx + int(24 * scale), cy - 5),  # 1: left_eye
            (cx + int(24 * scale), cy + 1),  # 2: right_eye
            (cx + int(20 * scale), cy - 6),  # 3: left_ear
            (cx + int(20 * scale), cy + 2),  # 4: right_ear
            (cx + int(10 * scale), cy - int(9 * scale)),  # 5: left_shoulder
            (cx + int(10 * scale), cy + int(9 * scale)),  # 6: right_shoulder
            (cx + int(18 * scale), cy - int(13 * scale) + arm_reach),  # 7: left_elbow
            (cx + int(18 * scale), cy + int(13 * scale) - arm_reach),  # 8: right_elbow
            (cx + int(28 * scale), cy - int(12 * scale) + arm_reach),  # 9: left_wrist
            (cx + int(28 * scale), cy + int(12 * scale) - arm_reach),  # 10: right_wrist
            (cx - int(8 * scale), cy - int(7 * scale)),  # 11: left_hip
            (cx - int(8 * scale), cy + int(7 * scale)),  # 12: right_hip
            (cx - int(18 * scale), cy - int(8 * scale)),  # 13: left_knee
            (cx - int(18 * scale), cy + int(8 * scale)),  # 14: right_knee
            (cx - int(27 * scale), cy - int(7 * scale)),  # 15: left_ankle
            (cx - int(27 * scale), cy + int(7 * scale)),  # 16: right_ankle
        ]
    else:
        # Vertical standing / treading posture
        pts = [
            (cx, cy - int(24 * scale)),  # 0: nose
            (cx - 3, cy - int(27 * scale)),  # 1: left_eye
            (cx + 3, cy - int(27 * scale)),  # 2: right_eye
            (cx - 6, cy - int(25 * scale)),  # 3: left_ear
            (cx + 6, cy - int(25 * scale)),  # 4: right_ear
            (cx - int(11 * scale), cy - int(12 * scale)),  # 5: left_shoulder
            (cx + int(11 * scale), cy - int(12 * scale)),  # 6: right_shoulder
            (cx - int(15 * scale), cy - int(2 * scale)),  # 7: left_elbow
            (cx + int(15 * scale), cy - int(2 * scale)),  # 8: right_elbow
            (cx - int(16 * scale), cy + int(6 * scale)),  # 9: left_wrist
            (cx + int(16 * scale), cy + int(6 * scale)),  # 10: right_wrist
            (cx - int(8 * scale), cy + int(10 * scale)),  # 11: left_hip
            (cx + int(8 * scale), cy + int(10 * scale)),  # 12: right_hip
            (cx - int(8 * scale), cy + int(20 * scale)),  # 13: left_knee
            (cx + int(8 * scale), cy + int(20 * scale)),  # 14: right_knee
            (cx - int(8 * scale), cy + int(28 * scale)),  # 15: left_ankle
            (cx + int(8 * scale), cy + int(28 * scale)),  # 16: right_ankle
        ]

    kps = [Keypoint2D(x=float(x), y=float(y), conf=0.96) for x, y in pts]
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    bbox = (
        max(0, min(xs) - 10),
        max(0, min(ys) - 10),
        min(CANVAS_WIDTH_PX, max(xs) + 10),
        min(CANVAS_HEIGHT_PX, max(ys) + 10),
    )
    return kps, bbox


def classify_pose_and_flailing(
    keypoints: list[Keypoint2D],
    *,
    displacement_m: float = 0.5,
    underwater_cue: bool = False,
) -> tuple[PostureState, bool, bool]:
    """Classify skeletal posture (`PostureState`, `is_flailing`, `is_submerged`) from 17 keypoints."""
    if len(keypoints) < 17:
        return (PostureState.ACTIVE_SWIM, False, False)

    l_sh, r_sh = keypoints[5], keypoints[6]
    l_wr, r_wr = keypoints[9], keypoints[10]
    l_hip, r_hip = keypoints[11], keypoints[12]

    sh_y = 0.5 * (l_sh.y + r_sh.y)
    wr_y = 0.5 * (l_wr.y + r_wr.y)
    hip_y = 0.5 * (l_hip.y + r_hip.y)

    sh_x = 0.5 * (l_sh.x + r_sh.x)
    hip_x = 0.5 * (l_hip.x + r_hip.x)

    torso_dx = abs(sh_x - hip_x)
    torso_dy = abs(sh_y - hip_y)

    # Active Flailing: vertical torso + wrists raised above/at shoulder line + near-zero forward travel
    if torso_dy >= torso_dx and wr_y <= (sh_y - 4.0) and displacement_m <= 0.15:
        return (PostureState.ACTIVE_FLAILING, True, False)

    # Horizontal posture
    if torso_dx > torso_dy * 1.15:
        if underwater_cue or displacement_m <= 0.08:
            return (PostureState.HORIZONTAL_SUBMERGED, False, True)
        return (PostureState.ACTIVE_SWIM, False, False)

    return (PostureState.VERTICAL_TREADING, False, False)


def _render_base_pool_canvas(
    *,
    monsoon_mode: bool = False,
) -> np.ndarray:
    """Render a realistic 640x360 BGR swimming pool frame with floor tiles and lane lines."""
    frame = np.zeros((CANVAS_HEIGHT_PX, CANVAS_WIDTH_PX, 3), dtype=np.uint8)

    # Pool deck travertine stone surround
    frame[:, :] = (175, 195, 208)

    if monsoon_mode:
        # Green-algae shifted turbid water after tropical storm
        shallow_bgr = (115, 178, 95)
        deep_bgr = (92, 152, 74)
        tile_line_bgr = (102, 162, 84)
    else:
        # Crystal-clear cyan/azure chlorinated pool water
        shallow_bgr = (238, 195, 65)
        deep_bgr = (212, 150, 28)
        tile_line_bgr = (170, 110, 12)

    cv2.rectangle(frame, (40, 60), (310, 300), shallow_bgr, -1)
    cv2.rectangle(frame, (310, 60), (600, 300), deep_bgr, -1)

    # High-contrast ceramic floor tile grid & racing lane lines (for Laplacian contrast check)
    grid_step = 24 if not monsoon_mode else 48
    for gx in range(40, 600, grid_step):
        cv2.line(frame, (gx, 60), (gx, 300), tile_line_bgr, 1)
    for gy in range(60, 300, grid_step):
        cv2.line(frame, (40, gy), (600, gy), tile_line_bgr, 1)

    if not monsoon_mode:
        for ly in (110, 180, 250):
            cv2.line(frame, (55, ly), (585, ly), (120, 60, 10), 2)

    # 12.5m Shallow/Deep safety rope line
    cv2.line(frame, (310, 60), (310, 300), (60, 220, 255), 2)
    cv2.rectangle(frame, (40, 60), (600, 300), (240, 240, 240), 2)
    return frame


def _draw_synthetic_swimmer_on_frame(
    frame: np.ndarray,
    track: SwimmerTrack,
) -> None:
    """Paint swimmer body & attire onto the raw camera frame so Tier-1/System-2 can inspect ROIs."""
    bx1, by1, bx2, by2 = track.bbox
    cx = (bx1 + bx2) // 2
    cy = (by1 + by2) // 2

    # Draw head (skin tone) at kp[0]
    if track.keypoints:
        hx, hy = int(track.keypoints[0].x), int(track.keypoints[0].y)
    else:
        hx, hy = cx, by1 + 10
    cv2.circle(frame, (hx, hy), 8, (140, 175, 225), -1)

    # Draw torso attire
    if track.suspected_violation == ViolationType.COTTON_ATTIRE:
        # High-saturation bright red/orange opaque cotton street t-shirt
        cv2.rectangle(frame, (cx - 14, cy - 10), (cx + 14, cy + 14), (35, 55, 240), -1)
        cv2.line(frame, (cx - 14, cy - 8), (cx + 14, cy + 12), (245, 245, 245), 2)
    else:
        # Dark Lycra swimwear
        cv2.rectangle(frame, (cx - 10, cy - 8), (cx + 10, cy + 10), (75, 45, 30), -1)

    if track.suspected_violation == ViolationType.SMOKING_VAPING:
        # High-value, low-saturation white/gray vape/smoke aerosol plume near hand/wrist
        cv2.circle(frame, (cx + 14, cy - 4), 7, (238, 238, 242), -1)
        cv2.circle(frame, (cx + 18, cy - 10), 6, (245, 245, 248), -1)


def synthesize_scenario_frame(
    scenario: ScenarioName = ScenarioName.NORMAL_LAP_AND_FAMILY,
    elapsed_sec: float = 0.0,
) -> tuple[np.ndarray, list[SwimmerTrack], list[DetectedObject]]:
    """Deterministically generate a 640x360 BGR frame, `SwimmerTrack`s, and `DetectedObject`s."""
    monsoon_mode = scenario == ScenarioName.MONSOON_DEBRIS_AND_ALGAE
    frame = _render_base_pool_canvas(monsoon_mode=monsoon_mode)
    tracks: list[SwimmerTrack] = []
    objects: list[DetectedObject] = []

    if scenario == ScenarioName.NORMAL_LAP_AND_FAMILY:
        specs = [
            (
                101,
                SwimmerRole.LAP_SWIMMER,
                PoolZone.ZONE_B_DEEP_END,
                PostureState.ACTIVE_SWIM,
                (18.0, 3.2),
            ),
            (
                102,
                SwimmerRole.LAP_SWIMMER,
                PoolZone.ZONE_B_DEEP_END,
                PostureState.ACTIVE_SWIM,
                (20.5, 8.5),
            ),
            (
                103,
                SwimmerRole.ADULT,
                PoolZone.ZONE_A_SHALLOW,
                PostureState.VERTICAL_TREADING,
                (6.5, 5.5),
            ),
            (
                104,
                SwimmerRole.TODDLER,
                PoolZone.ZONE_A_SHALLOW,
                PostureState.VERTICAL_TREADING,
                (7.2, 5.8),
            ),
        ]
        for tid, role, zone, posture, (xm, ym) in specs:
            px, py = pool_meters_to_pixel(xm, ym)
            kps, bbox = build_coco_keypoints(
                px, py, posture=posture, role=role, elapsed_sec=elapsed_sec
            )
            tr = SwimmerTrack(
                track_id=tid,
                role=role,
                zone=zone,
                posture=posture,
                bbox=bbox,
                pool_coords_m=(xm, ym),
                keypoints=kps,
            )
            _draw_synthetic_swimmer_on_frame(frame, tr)
            tracks.append(tr)

    elif scenario == ScenarioName.SILENT_DROWNING_RESCUE:
        # Swimmer #201 in Zone B Deep End:
        # 0s <= elapsed_sec < 10s -> Active Surface Flailing (ACTIVE_FLAILING)
        # elapsed_sec >= 10s -> Exhausted & motionless underwater (HORIZONTAL_SUBMERGED)
        is_flail_phase = elapsed_sec < 10.0
        posture = (
            PostureState.ACTIVE_FLAILING if is_flail_phase else PostureState.HORIZONTAL_SUBMERGED
        )
        xm, ym = (19.2, 6.0)
        px, py = pool_meters_to_pixel(xm, ym)
        kps, bbox = build_coco_keypoints(px, py, posture=posture, elapsed_sec=elapsed_sec)
        victim = SwimmerTrack(
            track_id=201,
            role=SwimmerRole.ADULT,
            zone=PoolZone.ZONE_B_DEEP_END,
            posture=posture,
            bbox=bbox,
            pool_coords_m=(xm, ym),
            keypoints=kps,
            is_flailing=is_flail_phase,
            is_submerged=not is_flail_phase,
        )
        _draw_synthetic_swimmer_on_frame(frame, victim)
        tracks.append(victim)

        # Distant swimmer in Zone A (13.0m away -> outside 1.5m supervision radius)
        px2, py2 = pool_meters_to_pixel(6.0, 3.5)
        kps2, bbox2 = build_coco_keypoints(
            px2, py2, posture=PostureState.ACTIVE_SWIM, elapsed_sec=elapsed_sec
        )
        other = SwimmerTrack(
            track_id=202,
            role=SwimmerRole.LAP_SWIMMER,
            zone=PoolZone.ZONE_A_SHALLOW,
            posture=PostureState.ACTIVE_SWIM,
            bbox=bbox2,
            pool_coords_m=(6.0, 3.5),
            keypoints=kps2,
        )
        _draw_synthetic_swimmer_on_frame(frame, other)
        tracks.append(other)

    elif scenario == ScenarioName.UNACCOMPANIED_TODDLER_DEEP_END:
        # Toddler #301 at x=12.0m (within 0.5m of 12.5m deep-end boundary)
        tx, ty = (12.0, 6.0)
        tpx, tpy = pool_meters_to_pixel(tx, ty)
        tkps, tbbox = build_coco_keypoints(
            tpx,
            tpy,
            posture=PostureState.VERTICAL_TREADING,
            role=SwimmerRole.TODDLER,
            elapsed_sec=elapsed_sec,
        )
        toddler = SwimmerTrack(
            track_id=301,
            role=SwimmerRole.TODDLER,
            zone=PoolZone.ZONE_A_SHALLOW,
            posture=PostureState.VERTICAL_TREADING,
            bbox=tbbox,
            pool_coords_m=(tx, ty),
            keypoints=tkps,
            near_deep_boundary=abs(tx - DEEP_END_BOUNDARY_X_M) <= TODDLER_DEEP_BOUNDARY_BUFFER_M,
        )
        _draw_synthetic_swimmer_on_frame(frame, toddler)
        tracks.append(toddler)

        # Distracted parent #302 on far shallow deck (x=3.5m -> 8.5m away > 1.5m)
        px, py = pool_meters_to_pixel(3.5, 6.0)
        pkps, pbbox = build_coco_keypoints(
            px, py, posture=PostureState.DECK_STANDING, elapsed_sec=elapsed_sec
        )
        parent = SwimmerTrack(
            track_id=302,
            role=SwimmerRole.ADULT,
            zone=PoolZone.POOL_DECK,
            posture=PostureState.DECK_STANDING,
            bbox=pbbox,
            pool_coords_m=(3.5, 6.0),
            keypoints=pkps,
        )
        _draw_synthetic_swimmer_on_frame(frame, parent)
        tracks.append(parent)

    elif scenario == ScenarioName.COTTON_TSHIRT_AND_FOOD_NUDGE:
        # Swimmer #401 wearing opaque cotton street t-shirt in Zone A
        cx_m, cy_m = (7.5, 5.5)
        cpx, cpy = pool_meters_to_pixel(cx_m, cy_m)
        ckps, cbbox = build_coco_keypoints(
            cpx, cpy, posture=PostureState.VERTICAL_TREADING, elapsed_sec=elapsed_sec
        )
        cotton_swimmer = SwimmerTrack(
            track_id=401,
            role=SwimmerRole.ADULT,
            zone=PoolZone.ZONE_A_SHALLOW,
            posture=PostureState.VERTICAL_TREADING,
            bbox=cbbox,
            pool_coords_m=(cx_m, cy_m),
            keypoints=ckps,
            suspected_violation=ViolationType.COTTON_ATTIRE,
        )
        _draw_synthetic_swimmer_on_frame(frame, cotton_swimmer)
        tracks.append(cotton_swimmer)

        # Deck resident #402 eating/drinking at pool edge
        fx_m, fy_m = (10.0, 11.2)
        fpx, fpy = pool_meters_to_pixel(fx_m, fy_m)
        fkps, fbbox = build_coco_keypoints(
            fpx, fpy, posture=PostureState.DECK_LOUNGING, elapsed_sec=elapsed_sec
        )
        food_resident = SwimmerTrack(
            track_id=402,
            role=SwimmerRole.ADULT,
            zone=PoolZone.POOL_DECK,
            posture=PostureState.DECK_LOUNGING,
            bbox=fbbox,
            pool_coords_m=(fx_m, fy_m),
            keypoints=fkps,
            suspected_violation=ViolationType.FOOD_DRINK_POOLSIDE,
        )
        _draw_synthetic_swimmer_on_frame(frame, food_resident)
        tracks.append(food_resident)

        # Draw & register beverage bottle and food bowl on pool deck edge
        cv2.rectangle(frame, (fpx + 12, fpy - 6), (fpx + 22, fpy + 12), (20, 180, 240), -1)
        objects.append(
            DetectedObject(
                label="bottle",
                confidence=0.93,
                bbox=(fpx + 12, fpy - 6, fpx + 22, fpy + 12),
                zone=PoolZone.POOL_DECK,
            )
        )
        objects.append(
            DetectedObject(
                label="cup",
                confidence=0.89,
                bbox=(fpx + 25, fpy - 2, fpx + 35, fpy + 10),
                zone=PoolZone.POOL_DECK,
            )
        )

    elif scenario == ScenarioName.PET_AND_STRAY_ANIMAL_POOL:
        # Resident #501 bringing a pet dog into Zone A Shallow water (Strata By-Law Violation)
        ox_m, oy_m = (8.0, 6.2)
        opx, opy = pool_meters_to_pixel(ox_m, oy_m)
        okps, obbox = build_coco_keypoints(
            opx, opy, posture=PostureState.VERTICAL_TREADING, elapsed_sec=elapsed_sec
        )
        pet_owner = SwimmerTrack(
            track_id=501,
            role=SwimmerRole.ADULT,
            zone=PoolZone.ZONE_A_SHALLOW,
            posture=PostureState.VERTICAL_TREADING,
            bbox=obbox,
            pool_coords_m=(ox_m, oy_m),
            keypoints=okps,
            suspected_violation=ViolationType.PET_OR_STRAY_ANIMAL,
        )
        _draw_synthetic_swimmer_on_frame(frame, pet_owner)
        tracks.append(pet_owner)

        # Draw pet dog (COCO class 16) swimming next to Resident #501 in Zone A Shallow
        dog_x, dog_y = opx + 22, opy + 6
        cv2.ellipse(frame, (dog_x, dog_y), (14, 8), 0, 0, 360, (60, 125, 195), -1)
        cv2.circle(frame, (dog_x + 12, dog_y - 5), 6, (50, 110, 180), -1)
        objects.append(
            DetectedObject(
                label="dog",
                confidence=0.95,
                bbox=(dog_x - 14, dog_y - 11, dog_x + 18, dog_y + 8),
                zone=PoolZone.ZONE_A_SHALLOW,
            )
        )

        # Draw stray cat (COCO class 15) wandering at Zone B pool deck edge
        cat_x, cat_y = 420, 52
        cv2.ellipse(frame, (cat_x, cat_y), (10, 5), 0, 0, 360, (90, 140, 210), -1)
        objects.append(
            DetectedObject(
                label="cat",
                confidence=0.92,
                bbox=(cat_x - 10, cat_y - 6, cat_x + 12, cat_y + 6),
                zone=PoolZone.POOL_DECK,
            )
        )

        # Second normal lap swimmer in Zone B
        lpx, lpy = pool_meters_to_pixel(19.0, 4.0)
        lkps, lbbox = build_coco_keypoints(
            lpx, lpy, posture=PostureState.ACTIVE_SWIM, elapsed_sec=elapsed_sec
        )
        lap_swimmer = SwimmerTrack(
            track_id=502,
            role=SwimmerRole.LAP_SWIMMER,
            zone=PoolZone.ZONE_B_DEEP_END,
            posture=PostureState.ACTIVE_SWIM,
            bbox=lbbox,
            pool_coords_m=(19.0, 4.0),
            keypoints=lkps,
        )
        _draw_synthetic_swimmer_on_frame(frame, lap_swimmer)
        tracks.append(lap_swimmer)

    elif scenario == ScenarioName.MONSOON_DEBRIS_AND_ALGAE:
        # Draw 16 dark olive/brown monsoon storm leaves/twigs across the water basin
        rng = np.random.default_rng(108)
        for _ in range(16):
            lx = int(rng.integers(65, 575))
            ly = int(rng.integers(80, 280))
            cv2.ellipse(frame, (lx, ly), (7, 4), 25, 0, 360, (22, 65, 42), -1)
            zone = PoolZone.ZONE_B_DEEP_END if lx >= 310 else PoolZone.ZONE_A_SHALLOW
            objects.append(
                DetectedObject(
                    label="leaf_debris",
                    confidence=0.91,
                    bbox=(lx - 7, ly - 4, lx + 7, ly + 4),
                    zone=zone,
                )
            )

    elif scenario == ScenarioName.PEAK_CROWD_SURGE_ECO_DRIVE:
        # 14 swimmers across Zone A & Zone B + 2 cotton violations
        rng = np.random.default_rng(77)
        for i in range(14):
            tid = 601 + i
            xm = float(rng.uniform(2.5, 23.0))
            ym = float(rng.uniform(1.8, 10.2))
            zone = (
                PoolZone.ZONE_B_DEEP_END if xm >= DEEP_END_BOUNDARY_X_M else PoolZone.ZONE_A_SHALLOW
            )
            role = SwimmerRole.LAP_SWIMMER if xm >= DEEP_END_BOUNDARY_X_M else SwimmerRole.ADULT
            violation = ViolationType.COTTON_ATTIRE if i in (0, 1) else ViolationType.NONE
            px, py = pool_meters_to_pixel(xm, ym)
            kps, bbox = build_coco_keypoints(px, py, role=role, elapsed_sec=elapsed_sec)
            tr = SwimmerTrack(
                track_id=tid,
                role=role,
                zone=zone,
                posture=PostureState.ACTIVE_SWIM,
                bbox=bbox,
                pool_coords_m=(round(xm, 2), round(ym, 2)),
                keypoints=kps,
                suspected_violation=violation,
            )
            _draw_synthetic_swimmer_on_frame(frame, tr)
            tracks.append(tr)

    return frame, tracks, objects


class AquaPulseVisionDetector:
    """Zero-shot YOLO26 Pose/Object tracker with deterministic scenario synthesizer fallback."""

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.models_dir = models_dir
        self._pose_model: Any | None = None
        self._detect_model: Any | None = None

    @property
    def yolo26_weights_available(self) -> bool:
        """Return True if local YOLO26 weights exist in `assets/models/`."""
        return (self.models_dir / YOLO26_POSE_MODEL_NAME).exists()

    def load_yolo26_if_available(self) -> bool:
        """Lazily load `yolo26n-pose.pt` and `yolo26n.pt` if weights are present on disk."""
        pose_path = self.models_dir / YOLO26_POSE_MODEL_NAME
        detect_path = self.models_dir / YOLO26_DETECT_MODEL_NAME
        if not pose_path.exists():
            return False
        try:
            from ultralytics import YOLO  # type: ignore[import-untyped]

            self._pose_model = YOLO(str(pose_path))
            if detect_path.exists():
                self._detect_model = YOLO(str(detect_path))
            return True
        except Exception:
            return False

    def process_scenario(
        self,
        scenario: ScenarioName = ScenarioName.NORMAL_LAP_AND_FAMILY,
        elapsed_sec: float = 0.0,
    ) -> tuple[np.ndarray, list[SwimmerTrack], list[DetectedObject]]:
        """Run deterministic scenario synthesis (or live YOLO26 tracking when frame stream provided)."""
        return synthesize_scenario_frame(scenario=scenario, elapsed_sec=elapsed_sec)

    def create_video_tracker(
        self,
        calibration: Any,
        role_overrides: dict[int, Any] | None = None,
    ) -> Any:
        """Create a RealFrameTracker instance with loaded YOLO models and calibration."""
        from aquapulse.vision.video_tracker import RealFrameTracker

        self.load_yolo26_if_available()
        return RealFrameTracker(
            calibration=calibration,
            pose_model=self._pose_model,
            detect_model=self._detect_model,
            role_overrides=role_overrides,
        )
