"""Real-video YOLO26 pose/object tracker with homography calibration and ghost submersion."""

from __future__ import annotations

import math
from collections import deque
from typing import Any

import numpy as np

from aquapulse.config import (
    CANVAS_HEIGHT_PX,
    CANVAS_WIDTH_PX,
    DEEP_END_BOUNDARY_X_M,
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
from aquapulse.vision.calibration import PoolCalibration
from aquapulse.vision.detector import classify_pose_and_flailing

# COCO object class IDs
COCO_ANIMAL_CLASSES = {14: "bird", 15: "cat", 16: "dog"}
COCO_FOOD_CLASSES = {39: "bottle", 40: "wine glass", 41: "cup", 45: "bowl"}


class TrackHistoryItem:
    """Historical position record for velocity/displacement calculation."""

    __slots__ = ("t", "x_m", "y_m")

    def __init__(self, t: float, x_m: float, y_m: float) -> None:
        self.t = t
        self.x_m = x_m
        self.y_m = y_m


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
        # Next ID for unassigned tracks
        self._next_fallback_id = 101

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
                    # Bounding box in original frame pixels
                    xyxy = box.xyxy[0].cpu().numpy()
                    orig_x1, orig_y1, orig_x2, orig_y2 = (
                        int(xyxy[0]),
                        int(xyxy[1]),
                        int(xyxy[2]),
                        int(xyxy[3]),
                    )

                    # Extract persistent track ID
                    track_id: int
                    if box.id is not None:
                        track_id = int(box.id[0].item())
                    else:
                        track_id = self._next_fallback_id
                        self._next_fallback_id += 1

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

                    # Ground contact point in original frame for homography
                    # Use ankles (kp 15,16) or hips (kp 11,12) or box bottom
                    ground_px = 0.5 * (orig_x1 + orig_x2)
                    ground_py = float(orig_y2)
                    if len(raw_kps) >= 17 and (raw_kps[15][2] > 0.3 or raw_kps[16][2] > 0.3):
                        ground_py = max(raw_kps[15][1], raw_kps[16][1])

                    # Physical pool coordinates (meters)
                    pool_coords_m = self.calibration.to_pool_m(
                        ground_px, ground_py, frame_w, frame_h
                    )
                    x_m, y_m = pool_coords_m
                    in_water = self.calibration.in_water(
                        ground_px, ground_py, frame_w, frame_h
                    )
                    zone = self.calibration.zone_for(x_m, in_water)

                    # Velocity & Displacement tracking
                    q = self._history.setdefault(track_id, deque(maxlen=25))
                    q.append(TrackHistoryItem(timestamp_sec, x_m, y_m))

                    displacement_m = 0.0
                    velocity_mps = 0.0
                    if len(q) >= 2:
                        old_item = q[0]
                        dt = max(0.1, timestamp_sec - old_item.t)
                        displacement_m = math.hypot(x_m - old_item.x_m, y_m - old_item.y_m)
                        velocity_mps = displacement_m / dt

                    # Posture classification
                    posture, is_flailing, is_submerged = classify_pose_and_flailing(
                        kps_scaled,
                        displacement_m=displacement_m,
                        underwater_cue=in_water and (len(head_orig_pts) == 0),
                    )

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

                    # Near deep boundary: toddler within 1.5m of deep-end line
                    near_deep = False
                    if role == SwimmerRole.TODDLER:
                        dist_to_boundary = abs(x_m - DEEP_END_BOUNDARY_X_M)
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
        # If a swimmer who was in water disappears (e.g. head goes underwater, losing pose detection),
        # keep their track alive as a submerged ghost for up to 30s so the drowning timer fires!
        for prev_id, history_q in list(self._history.items()):
            if prev_id not in detected_ids_this_frame and len(history_q) > 0:
                last_item = history_q[-1]
                # Check if last seen in water within 30s
                in_water_last = self.calibration.in_water(
                    int(round(last_item.x_m)), int(round(last_item.y_m)), frame_w, frame_h
                )
                dt_gone = timestamp_sec - last_item.t
                if (in_water_last or last_item.x_m > 1.0) and dt_gone <= 30.0:
                    ghost_cx = int(round((last_item.x_m / 25.0) * self.canvas_w))
                    ghost_cy = int(round((last_item.y_m / 12.0) * self.canvas_h))
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

                        # Flag violations on nearby tracks
                        if label in COCO_FOOD_CLASSES.values():
                            for tr in tracks:
                                if tr.bbox:
                                    dist_px = math.hypot(
                                        c_obbox[0] - tr.bbox[0], c_obbox[1] - tr.bbox[1]
                                    )
                                    if dist_px <= 75.0:
                                        tr.suspected_violation = ViolationType.FOOD_DRINK_POOLSIDE
                        elif label in ("dog", "cat"):
                            # Animal violation
                            for tr in tracks:
                                tr.suspected_violation = ViolationType.PET_OR_STRAY_ANIMAL
            except Exception:
                pass

        return tracks, objects, head_boxes_full_res
