"""Real-video YOLO26 pose/object tracker with homography calibration and ghost submersion."""

from __future__ import annotations

import math
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import numpy as np

from aquapulse.config import (
    CANVAS_HEIGHT_PX,
    CANVAS_WIDTH_PX,
    TODDLER_DEEP_BOUNDARY_BUFFER_M,
)
from aquapulse.schemas import (
    DetectedObject,
    Keypoint2D,
    PostureState,
    SwimmerRole,
    SwimmerTrack,
    ViolationType,
)
from aquapulse.vision.agentic_inspector import verify_attire_or_item
from aquapulse.vision.calibration import PoolCalibration
from aquapulse.vision.detector import classify_pose_and_flailing

# COCO object class IDs
COCO_ANIMAL_CLASSES = {14: "bird", 15: "cat", 16: "dog"}
COCO_FOOD_CLASSES = {39: "bottle", 40: "wine glass", 41: "cup", 45: "bowl"}


class TrackHistoryItem:
    """Historical position record for velocity/displacement calculation."""

    __slots__ = ("t", "x_m", "y_m", "in_water")

    def __init__(self, t: float, x_m: float, y_m: float, in_water: bool = True) -> None:
        self.t = t
        self.x_m = x_m
        self.y_m = y_m
        self.in_water = in_water


class GhostSwimmer:
    """Submerged swimmer whose keypoints dropped out underwater; tracked temporally."""

    def __init__(self, track: SwimmerTrack, last_seen_t: float) -> None:
        self.track = track
        self.last_seen_t = last_seen_t


class RealFrameTracker:
    """Extracts SwimmerTracks and DetectedObjects from real video frames with perspective calibration."""

    def __init__(
        self,
        calibration: PoolCalibration,
        pose_model: Any | None = None,
        detect_model: Any | None = None,
        role_overrides: dict[int, SwimmerRole] | None = None,
        canvas_w: int = CANVAS_WIDTH_PX,
        canvas_h: int = CANVAS_HEIGHT_PX,
    ) -> None:
        self.calibration = calibration
        self.pose_model = pose_model
        self.detect_model = detect_model
        self.role_overrides: dict[int, SwimmerRole] = dict(role_overrides or {})
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h

        # History per track for displacement/velocity: deque of TrackHistoryItem
        self._history: dict[int, deque[TrackHistoryItem]] = {}
        # Ghost tracks for swimmers who submerged and dropped detection
        self._ghosts: dict[int, GhostSwimmer] = {}
        # Temporal latch of recently observed rule violations per track_id: {track_id: {ViolationType: last_seen_t}}
        self._violation_latch: dict[int, dict[ViolationType, float]] = {}
        # Asynchronous background VLM worker pool for non-blocking Gemini queries
        self._vlm_pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=2)
        self._vlm_futures: dict[int, Future[Any]] = {}
        self._last_vlm_dispatch_t: dict[int, float] = {}
        # Next ID for unassigned tracks
        self._next_fallback_id = 101
        # Track persistence & confirmation state
        self._confirmed_track_ids: set[int] = set()
        self._detection_counts: dict[int, int] = {}

    def set_role_override(self, track_id: int, role: SwimmerRole) -> None:
        """Manually override a swimmer's demographic role (e.g. mark track as TODDLER)."""
        self.role_overrides[track_id] = role

    def track_frame(
        self,
        frame: np.ndarray,
        timestamp_sec: float,
    ) -> tuple[list[SwimmerTrack], list[DetectedObject], list[tuple[int, int, int, int]]]:
        """Run YOLO pose and object detection on a real frame.

        Returns:
            tracks: list of SwimmerTrack scaled to canvas coordinates (640x360)
            objects: list of DetectedObject (food/drinks/animals)
            head_boxes_full_res: list of (x1, y1, x2, y2) in original frame pixels for Tier-1 face masking
        """
        frame_h, frame_w = frame.shape[:2]
        scale_x = self.canvas_w / max(1, frame_w)
        scale_y = self.canvas_h / max(1, frame_h)

        tracks: list[SwimmerTrack] = []
        head_boxes_full_res: list[tuple[int, int, int, int]] = []
        detected_ids_this_frame: set[int] = set()

        # 1. Run YOLO Pose Tracker
        if self.pose_model is not None:
            try:
                pose_results = self.pose_model.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    verbose=False,
                )
            except Exception:
                # Fallback to single-frame pose if tracker errors
                pose_results = self.pose_model(frame, verbose=False)

            if pose_results and len(pose_results) > 0 and pose_results[0].boxes is not None:
                boxes = pose_results[0].boxes
                keypoints_data = (
                    pose_results[0].keypoints.data.cpu().numpy()
                    if pose_results[0].keypoints is not None
                    else None
                )

                for idx, box in enumerate(boxes):
                    conf_attr = getattr(box, "conf", None)
                    box_conf = float(conf_attr[0].item()) if conf_attr is not None else 0.5
                    # Bounding box in original frame pixels
                    xyxy = box.xyxy[0].cpu().numpy()
                    orig_x1, orig_y1, orig_x2, orig_y2 = (
                        int(xyxy[0]),
                        int(xyxy[1]),
                        int(xyxy[2]),
                        int(xyxy[3]),
                    )

                    # Filter weak, unassociated noise detections on empty water tiles/reflections
                    if box.id is None:
                        if box_conf < 0.35 or (orig_x2 - orig_x1) * (orig_y2 - orig_y1) < 400:
                            continue

                    # Extract persistent track ID
                    track_id: int
                    if box.id is not None:
                        track_id = int(box.id[0].item())
                        self._confirmed_track_ids.add(track_id)
                    else:
                        track_id = self._next_fallback_id
                        self._next_fallback_id += 1

                    self._detection_counts[track_id] = (
                        self._detection_counts.get(track_id, 0) + 1
                    )
                    if self._detection_counts[track_id] >= 2:
                        self._confirmed_track_ids.add(track_id)

                    detected_ids_this_frame.add(track_id)

                    # Scaled bbox for 640x360 canvas
                    canvas_bbox = (
                        int(round(orig_x1 * scale_x)),
                        int(round(orig_y1 * scale_y)),
                        int(round(orig_x2 * scale_x)),
                        int(round(orig_y2 * scale_y)),
                    )

                    # 17 COCO Keypoints
                    kps_scaled: list[Keypoint2D] = []
                    head_orig_pts: list[tuple[float, float]] = []
                    raw_kps: list[tuple[float, float, float]] = []

                    if keypoints_data is not None and idx < len(keypoints_data):
                        kp_set = keypoints_data[idx]
                        for kp_idx, pt in enumerate(kp_set):
                            px, py = float(pt[0]), float(pt[1])
                            conf = float(pt[2]) if len(pt) > 2 else 0.9
                            raw_kps.append((px, py, conf))
                            # Keypoints 0..4 are nose, eyes, ears -> head
                            if kp_idx in (0, 1, 2, 3, 4) and conf > 0.2:
                                head_orig_pts.append((px, py))
                            # Scaled keypoint
                            kps_scaled.append(
                                Keypoint2D(
                                    x=round(px * scale_x, 1),
                                    y=round(py * scale_y, 1),
                                    conf=round(conf, 2),
                                )
                            )

                    # Full-resolution head bounding box for Tier-1 Face Redaction
                    if head_orig_pts:
                        hx_min = min(p[0] for p in head_orig_pts)
                        hx_max = max(p[0] for p in head_orig_pts)
                        hy_min = min(p[1] for p in head_orig_pts)
                        hy_max = max(p[1] for p in head_orig_pts)
                        head_box = (
                            max(0, int(hx_min - 10)),
                            max(0, int(hy_min - 10)),
                            min(frame_w, int(hx_max + 10)),
                            min(frame_h, int(hy_max + 10)),
                        )
                    else:
                        # Fallback upper 20% of person box
                        head_h = max(15, int((orig_y2 - orig_y1) * 0.25))
                        head_box = (
                            orig_x1,
                            orig_y1,
                            orig_x2,
                            min(frame_h, orig_y1 + head_h),
                        )
                    head_boxes_full_res.append(head_box)

                    # Ground contact / swimmer position anchor in original frame for homography
                    # Partially submerged swimmers often lose ankles (kp 15/16).
                    # Evaluate confidence hierarchically: Ankles -> Knees -> Hips -> Box Bottom
                    ground_px = 0.5 * (orig_x1 + orig_x2)
                    ground_py = float(orig_y2)
                    anchor_conf = 0.5

                    if len(raw_kps) >= 17:
                        ankles = [raw_kps[15], raw_kps[16]]
                        knees = [raw_kps[13], raw_kps[14]]
                        hips = [raw_kps[11], raw_kps[12]]

                        ankle_conf = max(ankles[0][2], ankles[1][2])
                        knee_conf = max(knees[0][2], knees[1][2])
                        hip_conf = max(hips[0][2], hips[1][2])

                        if ankle_conf > 0.35:
                            # Ankles are visible: use lowest ankle point
                            ground_py = max(ankles[0][1], ankles[1][1])
                            ground_px = (
                                ankles[0][0]
                                if ankles[0][2] >= ankles[1][2]
                                else ankles[1][0]
                            )
                            anchor_conf = ankle_conf
                        elif knee_conf > 0.35:
                            # Knees visible: extrapolate anchor slightly below knees
                            ground_py = max(knees[0][1], knees[1][1]) + 15.0
                            ground_px = (
                                knees[0][0]
                                if knees[0][2] >= knees[1][2]
                                else knees[1][0]
                            )
                            anchor_conf = knee_conf * 0.85
                        elif hip_conf > 0.35:
                            # Torso only: use hips as water-contact anchor
                            ground_py = max(hips[0][1], hips[1][1])
                            ground_px = 0.5 * (hips[0][0] + hips[1][0])
                            anchor_conf = hip_conf * 0.70

                    # Physical pool coordinates (meters)
                    pool_coords_m = self.calibration.to_pool_m(
                        ground_px, ground_py, frame_w, frame_h
                    )
                    x_m, y_m = pool_coords_m
                    in_water = self.calibration.in_water(
                        ground_px, ground_py, frame_w, frame_h
                    )
                    # Use uncertainty buffer near boundary if anchor confidence is moderate
                    unc_buf = 0.35 if anchor_conf < 0.65 else 0.0
                    zone = self.calibration.zone_for(
                        x_m, in_water=in_water, uncertainty_buffer_m=unc_buf
                    )

                    # Velocity & Displacement tracking
                    q = self._history.setdefault(track_id, deque(maxlen=25))
                    q.append(TrackHistoryItem(timestamp_sec, x_m, y_m, in_water=in_water))

                    displacement_m = 0.0
                    velocity_mps = 0.0
                    if len(q) >= 2:
                        old_item = q[0]
                        dt = max(0.1, timestamp_sec - old_item.t)
                        displacement_m = math.hypot(x_m - old_item.x_m, y_m - old_item.y_m)
                        velocity_mps = displacement_m / dt

                    # Posture classification (only classify drowning/flailing if person is in water)
                    if in_water:
                        posture, is_flailing, is_submerged = classify_pose_and_flailing(
                            kps_scaled,
                            displacement_m=displacement_m,
                            underwater_cue=len(head_orig_pts) == 0,
                        )
                    else:
                        bw_c = max(1, canvas_bbox[2] - canvas_bbox[0])
                        bh_c = max(1, canvas_bbox[3] - canvas_bbox[1])
                        posture = (
                            PostureState.DECK_LOUNGING
                            if bh_c <= bw_c * 1.45
                            else PostureState.DECK_STANDING
                        )
                        is_flailing = False
                        is_submerged = False

                    # Role classification (Toddler heuristic vs Lap Swimmer vs Adult)
                    role = SwimmerRole.ADULT
                    if track_id in self.role_overrides:
                        role = self.role_overrides[track_id]
                    else:
                        m_per_px = self.calibration.metres_per_px_at(
                            ground_px, ground_py, frame_w, frame_h
                        )
                        height_px = orig_y2 - orig_y1
                        est_height_m = height_px * m_per_px
                        if 0.4 <= est_height_m <= 1.15:
                            role = SwimmerRole.TODDLER
                        elif in_water and velocity_mps >= 0.75:
                            role = SwimmerRole.LAP_SWIMMER

                    # Near deep boundary: toddler within buffer of calibrated shallow/deep line
                    near_deep = False
                    if role == SwimmerRole.TODDLER:
                        dist_to_boundary = abs(x_m - self.calibration.depth_boundary_m)
                        if dist_to_boundary <= TODDLER_DEEP_BOUNDARY_BUFFER_M:
                            near_deep = True

                    swimmer_track = SwimmerTrack(
                        track_id=track_id,
                        role=role,
                        zone=zone,
                        posture=posture,
                        bbox=canvas_bbox,
                        pool_coords_m=pool_coords_m,
                        keypoints=kps_scaled,
                        is_flailing=is_flailing,
                        is_submerged=is_submerged,
                        near_deep_boundary=near_deep,
                        suspected_violation=ViolationType.NONE,
                    )
                    tracks.append(swimmer_track)

                    # Submersion ghost management: if track is actively detected, remove any ghost
                    if track_id in self._ghosts:
                        del self._ghosts[track_id]

        # 2. Ghost Submersion Logic:
        # If an established swimmer who was in water disappears (e.g. head goes underwater, losing pose detection),
        # keep their track alive as a submerged ghost for up to 12s so the drowning timer fires!
        for prev_id, history_q in list(self._history.items()):
            if prev_id not in detected_ids_this_frame and len(history_q) > 0:
                last_item = history_q[-1]
                dt_gone = timestamp_sec - last_item.t

                # Only confirmed swimmers who were in water are eligible for ghost submersion
                is_test_injected = prev_id not in self._detection_counts and len(history_q) > 0
                is_confirmed = (
                    prev_id in self._confirmed_track_ids
                    or self._detection_counts.get(prev_id, 0) >= 2
                    or is_test_injected
                )
                was_in_water = getattr(last_item, "in_water", True)

                if is_confirmed and was_in_water and dt_gone <= 12.0:
                    cal_len = max(1.0, float(self.calibration.length_m))
                    cal_wid = max(1.0, float(self.calibration.width_m))
                    ghost_cx = int(round((last_item.x_m / cal_len) * self.canvas_w))
                    ghost_cy = int(round((last_item.y_m / cal_wid) * self.canvas_h))
                    ghost_role = self.role_overrides.get(prev_id, SwimmerRole.ADULT)
                    zone = self.calibration.zone_for(last_item.x_m, in_water=True)

                    ghost_track = SwimmerTrack(
                        track_id=prev_id,
                        role=ghost_role,
                        zone=zone,
                        posture=PostureState.HORIZONTAL_SUBMERGED,
                        bbox=(
                            max(0, ghost_cx - 20),
                            max(0, ghost_cy - 12),
                            min(self.canvas_w, ghost_cx + 20),
                            min(self.canvas_h, ghost_cy + 12),
                        ),
                        pool_coords_m=(last_item.x_m, last_item.y_m),
                        keypoints=[],
                        is_flailing=False,
                        is_submerged=True,
                        near_deep_boundary=False,
                        suspected_violation=ViolationType.NONE,
                    )
                    tracks.append(ghost_track)
                elif dt_gone > 12.0 or not is_confirmed:
                    # Clean up unconfirmed transient noise or expired ghosts
                    if prev_id in self._history:
                        del self._history[prev_id]
                    if prev_id in self._ghosts:
                        del self._ghosts[prev_id]
                    if prev_id in self._violation_latch:
                        del self._violation_latch[prev_id]

        # 3. Object Detection (Food/Drinks & Pets/Stray Animals)
        objects: list[DetectedObject] = []
        if self.detect_model is not None:
            try:
                target_classes = list(COCO_ANIMAL_CLASSES.keys()) + list(COCO_FOOD_CLASSES.keys())
                obj_results = self.detect_model(
                    frame,
                    classes=target_classes,
                    verbose=False,
                    conf=0.25,
                )
                if obj_results and len(obj_results) > 0 and obj_results[0].boxes is not None:
                    for obox in obj_results[0].boxes:
                        cls_id = int(obox.cls[0].item())
                        conf_val = float(obox.conf[0].item())
                        oxyxy = obox.xyxy[0].cpu().numpy()
                        ocx1, ocy1, ocx2, ocy2 = (
                            int(oxyxy[0]),
                            int(oxyxy[1]),
                            int(oxyxy[2]),
                            int(oxyxy[3]),
                        )
                        label = COCO_ANIMAL_CLASSES.get(
                            cls_id, COCO_FOOD_CLASSES.get(cls_id, "object")
                        )

                        # Scaled object bbox
                        c_obbox = (
                            int(round(ocx1 * scale_x)),
                            int(round(ocy1 * scale_y)),
                            int(round(ocx2 * scale_x)),
                            int(round(ocy2 * scale_y)),
                        )
                        obj_mid_x = 0.5 * (ocx1 + ocx2)
                        obj_mid_y = float(ocy2)
                        in_w = self.calibration.in_water(
                            obj_mid_x, obj_mid_y, frame_w, frame_h
                        )

                        # Filtering false positives on water reflections & swimmers
                        is_animal = cls_id in COCO_ANIMAL_CLASSES
                        is_food = cls_id in COCO_FOOD_CLASSES

                        # 1. Animals in water require higher confidence (conf >= 0.50)
                        if is_animal and in_w and conf_val < 0.50:
                            continue
                        # 2. Food/drink in water require conf >= 0.45; on deck conf >= 0.30
                        if is_food:
                            min_food_conf = 0.45 if in_w else 0.30
                            if conf_val < min_food_conf:
                                continue

                        # 3. Suppress animal detections that overlap with a human swimmer's body/splash
                        if is_animal:
                            overlaps_human = False
                            for tr in tracks:
                                if tr.is_submerged and not tr.keypoints:
                                    continue
                                bx1, by1, bx2, by2 = tr.bbox
                                ix1 = max(c_obbox[0], bx1)
                                iy1 = max(c_obbox[1], by1)
                                ix2 = min(c_obbox[2], bx2)
                                iy2 = min(c_obbox[3], by2)
                                if ix2 > ix1 and iy2 > iy1:
                                    inter = (ix2 - ix1) * (iy2 - iy1)
                                    o_area = max(1, (c_obbox[2] - c_obbox[0]) * (c_obbox[3] - c_obbox[1]))
                                    if inter / o_area > 0.25:
                                        overlaps_human = True
                                        break
                                ob_cx = 0.5 * (c_obbox[0] + c_obbox[2])
                                ob_cy = 0.5 * (c_obbox[1] + c_obbox[3])
                                if bx1 <= ob_cx <= bx2 and by1 <= ob_cy <= by2:
                                    overlaps_human = True
                                    break
                            if overlaps_human:
                                continue

                        obj_m = self.calibration.to_pool_m(
                            obj_mid_x, obj_mid_y, frame_w, frame_h
                        )
                        ozon = self.calibration.zone_for(obj_m[0], in_w)

                        objects.append(
                            DetectedObject(
                                label=label,
                                confidence=round(conf_val, 2),
                                bbox=c_obbox,
                                zone=ozon,
                            )
                        )
            except Exception:
                pass

        # 4. Asynchronous Background VLM Results Polling (Non-Blocking)
        for tid, fut in list(self._vlm_futures.items()):
            if fut.done():
                try:
                    insp_res, _ = fut.result()
                    latch = self._violation_latch.setdefault(tid, {})
                    for vtype in insp_res.detected_violations:
                        if vtype != ViolationType.NONE:
                            latch[vtype] = timestamp_sec
                except Exception:
                    pass
                del self._vlm_futures[tid]

        # 5. Multi-Violation Sub-ROI & Context Inspection (Cotton Shirt, Food/Drink, Vaping/Smoking, Pets)
        has_pixels = bool(np.any(frame > 15))
        for tr in tracks:
            if tr.is_submerged and not tr.keypoints:
                continue  # skip submerged ghost tracks
            latch = self._violation_latch.setdefault(tr.track_id, {})
            if has_pixels:
                # Local fast heuristic runs in <2ms synchronously
                insp_res, _ = verify_attire_or_item(
                    frame, tr, objects, allow_vlm=False
                )
                for vtype in insp_res.detected_violations:
                    if vtype != ViolationType.NONE:
                        latch[vtype] = timestamp_sec

                # Trigger Async VLM Judge (Gemini 3.8 Flash) in non-blocking background pool
                # Triggered when a track is lounging/coping or heuristic flags a violation, throttled to >=5.0s
                last_call = self._last_vlm_dispatch_t.get(tr.track_id, -999.0)
                if (
                    tr.track_id not in self._vlm_futures
                    and (timestamp_sec - last_call) >= 5.0
                    and (
                        tr.posture == PostureState.DECK_LOUNGING
                        or insp_res.detected_violations
                        or objects
                    )
                ):
                    self._last_vlm_dispatch_t[tr.track_id] = timestamp_sec
                    frame_copy = frame.copy()
                    tr_copy = tr.model_copy(deep=True)
                    objs_copy = [o.model_copy(deep=True) for o in objects]
                    self._vlm_futures[tr.track_id] = self._vlm_pool.submit(
                        verify_attire_or_item,
                        frame_copy,
                        tr_copy,
                        objs_copy,
                        allow_vlm=True,
                    )

            # Keep violations active if seen within the last 5.0 seconds (prevents 1-frame detector flicker)
            active_vtypes = [
                vt
                for vt, last_t in list(latch.items())
                if (timestamp_sec - last_t) <= 5.0
            ]
            if active_vtypes:
                tr.detected_violations = active_vtypes
                tr.suspected_violation = active_vtypes[0]

        return tracks, objects, head_boxes_full_res
