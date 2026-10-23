"""Tests for RealFrameTracker with mocked/fake detection results and custom calibration geometry."""

from collections import deque

import numpy as np
import torch

from aquapulse.schemas import (
    DetectedObject,
    Keypoint2D,
    PoolZone,
    PostureState,
    SwimmerRole,
    SwimmerTrack,
    ViolationType,
)
from aquapulse.vision.agentic_inspector import verify_attire_or_item
from aquapulse.vision.calibration import PoolCalibration
from aquapulse.vision.detector import classify_pose_and_flailing
from aquapulse.vision.video_tracker import RealFrameTracker, TrackHistoryItem


class FakeBox:
    def __init__(self, xyxy, track_id=None):
        self.xyxy = [torch.tensor(xyxy, dtype=torch.float32)]
        self.id = [torch.tensor(track_id, dtype=torch.int32)] if track_id is not None else None


class FakeKeypoints:
    def __init__(self, kps_array):
        self.data = torch.tensor(kps_array, dtype=torch.float32)


class FakeResults:
    def __init__(self, boxes, keypoints=None):
        self.boxes = boxes
        self.keypoints = keypoints


class FakePoseModel:
    def __init__(self, results_fn):
        self.results_fn = results_fn

    def track(self, frame, **kwargs):
        return [self.results_fn(frame)]

    def __call__(self, frame, **kwargs):
        return [self.results_fn(frame)]


def test_tracker_with_simulated_detection():
    cal = PoolCalibration()

    # 17 keypoints for a standing person at (320, 180)
    kps = np.zeros((1, 17, 3), dtype=np.float32)
    for i in range(17):
        kps[0, i] = [320.0, 150.0 + i * 5.0, 0.95]

    def mock_fn(frame):
        boxes = [FakeBox([300, 140, 340, 240], track_id=42)]
        keypoints = FakeKeypoints(kps)
        return FakeResults(boxes=boxes, keypoints=keypoints)

    tracker = RealFrameTracker(
        calibration=cal,
        pose_model=FakePoseModel(mock_fn),
        role_overrides={42: SwimmerRole.TODDLER},
    )

    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    tracks, objects, head_boxes = tracker.track_frame(frame, timestamp_sec=0.0)

    assert len(tracks) == 1
    assert tracks[0].track_id == 42
    assert tracks[0].role == SwimmerRole.TODDLER
    assert len(head_boxes) == 1


def test_ghost_submersion_continuity():
    cal = PoolCalibration()
    tracker = RealFrameTracker(calibration=cal, pose_model=None)

    tracker._history[99] = deque([TrackHistoryItem(t=0.0, x_m=15.0, y_m=6.0)])

    # Next frame, detection is lost (e.g. swimmer is fully underwater)
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    tracks, _, _ = tracker.track_frame(frame, timestamp_sec=1.0)

    # Should emit a ghost track with PostureState.HORIZONTAL_SUBMERGED and is_submerged=True
    assert len(tracks) == 1
    assert tracks[0].track_id == 99
    assert tracks[0].is_submerged is True
    assert tracks[0].posture == PostureState.HORIZONTAL_SUBMERGED


def test_toddler_custom_depth_boundary_proximity():
    """Verify toddler near_deep_boundary triggers at calibrated boundary (e.g. 9.0m) instead of 12.5m."""
    cal = PoolCalibration(
        pool_corners_norm=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        deep_end_side="right",
        length_m=20.0,
        width_m=10.0,
        depth_boundary_m=9.0,  # Custom boundary at 9.0m
    )

    # Place swimmer at normalized x = 0.45 (which maps to 0.45 * 20m = 9.0m in physical pool)
    kps = np.zeros((1, 17, 3), dtype=np.float32)
    # Ankles at x=288px (0.45 * 640), y=180px
    for i in range(17):
        kps[0, i] = [288.0, 120.0 + i * 4.0, 0.90]

    def mock_fn(frame):
        boxes = [FakeBox([270, 100, 306, 184], track_id=7)]
        keypoints = FakeKeypoints(kps)
        return FakeResults(boxes=boxes, keypoints=keypoints)

    tracker = RealFrameTracker(
        calibration=cal,
        pose_model=FakePoseModel(mock_fn),
        role_overrides={7: SwimmerRole.TODDLER},
    )

    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    tracks, _, _ = tracker.track_frame(frame, timestamp_sec=0.0)

    assert len(tracks) == 1
    t = tracks[0]
    assert t.role == SwimmerRole.TODDLER
    # Swimmer is at ~9.0m, exactly on the 9.0m boundary: near_deep_boundary must be True!
    assert t.near_deep_boundary is True
    assert abs(t.pool_coords_m[0] - 9.0) < 0.5


def test_submerged_anchor_fallback():
    """Verify swimmer with submerged ankles uses knees/hips as anchor with confidence weighting."""
    cal = PoolCalibration(
        pool_corners_norm=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        deep_end_side="right",
        length_m=25.0,
        width_m=12.0,
        depth_boundary_m=12.5,
    )

    # Submerged ankles (kp 15,16 confidence = 0.05), but hips (kp 11,12) confidence = 0.85
    kps = np.zeros((1, 17, 3), dtype=np.float32)
    for i in range(11):
        kps[0, i] = [400.0, 100.0 + i * 5.0, 0.85]
    # Hips (11, 12) at y=160
    kps[0, 11] = [390.0, 160.0, 0.85]
    kps[0, 12] = [410.0, 160.0, 0.85]
    # Knees and Ankles submerged
    kps[0, 13] = [390.0, 190.0, 0.10]
    kps[0, 14] = [410.0, 190.0, 0.10]
    kps[0, 15] = [390.0, 220.0, 0.02]
    kps[0, 16] = [410.0, 220.0, 0.02]

    def mock_fn(frame):
        boxes = [FakeBox([380, 90, 420, 220], track_id=55)]
        keypoints = FakeKeypoints(kps)
        return FakeResults(boxes=boxes, keypoints=keypoints)

    tracker = RealFrameTracker(
        calibration=cal,
        pose_model=FakePoseModel(mock_fn),
        role_overrides={55: SwimmerRole.ADULT},
    )

    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    tracks, _, _ = tracker.track_frame(frame, timestamp_sec=0.0)

    assert len(tracks) == 1
    t = tracks[0]
    # Swimmer x=400/640 * 25m = ~15.6m (> 12.5m) -> ZONE_B_DEEP_END
    assert t.zone == PoolZone.ZONE_B_DEEP_END
    assert t.pool_coords_m[0] > 12.5


def test_unconfirmed_transient_noise_not_promoted_to_ghost():
    """Verify that a single-frame unassociated noise glitch is not promoted to a 30s ghost track."""
    cal = PoolCalibration()
    tracker = RealFrameTracker(calibration=cal, pose_model=None)

    # Simulate an unconfirmed fallback track seen only once (detection count = 1)
    tracker._detection_counts[101] = 1
    tracker._history[101] = deque([TrackHistoryItem(t=0.0, x_m=8.0, y_m=4.0, in_water=True)])

    # Next frame, detection is absent
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    tracks, _, _ = tracker.track_frame(frame, timestamp_sec=0.5)

    # Must NOT emit a ghost track for unconfirmed transient noise!
    assert len(tracks) == 0
    assert 101 not in tracker._history


def test_active_freestyle_swimmer_not_marked_submerged():
    """Verify that a horizontal swimmer displacing water with head face-down is classified as ACTIVE_SWIM."""
    # Horizontal torso (torso_dx >> torso_dy)
    # Head keypoints (0..4) are face down / submerged, but swimmer is moving fast (displacement_m = 0.65m)
    kps: list[Keypoint2D] = []
    # Keypoints 0..4 (head) low confidence
    for _ in range(5):
        kps.append(Keypoint2D(x=100.0, y=180.0, conf=0.10))
    # Shoulders (5, 6) at x=130
    kps.append(Keypoint2D(x=130.0, y=175.0, conf=0.85))
    kps.append(Keypoint2D(x=130.0, y=185.0, conf=0.85))
    # Elbows (7, 8)
    kps.append(Keypoint2D(x=150.0, y=170.0, conf=0.80))
    kps.append(Keypoint2D(x=150.0, y=190.0, conf=0.80))
    # Wrists (9, 10)
    kps.append(Keypoint2D(x=170.0, y=170.0, conf=0.80))
    kps.append(Keypoint2D(x=170.0, y=190.0, conf=0.80))
    # Hips (11, 12) at x=200 -> torso_dx = abs(130 - 200) = 70px (horizontal!)
    kps.append(Keypoint2D(x=200.0, y=178.0, conf=0.85))
    kps.append(Keypoint2D(x=200.0, y=182.0, conf=0.85))
    # Knees (13, 14)
    kps.append(Keypoint2D(x=240.0, y=178.0, conf=0.75))
    kps.append(Keypoint2D(x=240.0, y=182.0, conf=0.75))
    # Ankles (15, 16)
    kps.append(Keypoint2D(x=270.0, y=178.0, conf=0.70))
    kps.append(Keypoint2D(x=270.0, y=182.0, conf=0.70))

    # Test with active displacement (swimmer swimming freestyle)
    posture, is_flailing, is_submerged = classify_pose_and_flailing(
        kps,
        displacement_m=0.65,
        underwater_cue=True,  # Head face-down in water
    )
    assert posture == PostureState.ACTIVE_SWIM
    assert is_submerged is False
    assert is_flailing is False

    # Conversely, if displacement is near-zero (motionless floating face-down), it MUST flag HORIZONTAL_SUBMERGED
    posture_still, _, is_submerged_still = classify_pose_and_flailing(
        kps,
        displacement_m=0.04,
        underwater_cue=True,
    )
    assert posture_still == PostureState.HORIZONTAL_SUBMERGED
    assert is_submerged_still is True


def test_overlapping_animal_on_human_suppressed():
    """Verify that a false COCO animal detection overlapping a human swimmer in the pool is suppressed."""
    cal = PoolCalibration()

    # Standing/swimming human at (300, 150) to (360, 250)
    human_kps = np.zeros((1, 17, 3), dtype=np.float32)
    for i in range(17):
        human_kps[0, i] = [330.0, 160.0 + i * 5.0, 0.90]

    def mock_pose(frame):
        boxes = [FakeBox([300, 150, 360, 250], track_id=1)]
        keypoints = FakeKeypoints(human_kps)
        return FakeResults(boxes=boxes, keypoints=keypoints)

    class FakeDetectBox:
        def __init__(self, xyxy, cls_id, conf):
            self.xyxy = [torch.tensor(xyxy, dtype=torch.float32)]
            self.cls = [torch.tensor([cls_id], dtype=torch.int32)]
            self.conf = [torch.tensor([conf], dtype=torch.float32)]

    # Animal detection (COCO class 16 = dog) overlapping human torso
    def mock_detect(frame, **kwargs):
        boxes = [FakeDetectBox([310, 160, 350, 220], cls_id=16, conf=0.55)]
        return FakeResults(boxes=boxes)

    class FakeDetectModel:
        def __call__(self, frame, **kwargs):
            return [mock_detect(frame, **kwargs)]

    tracker = RealFrameTracker(
        calibration=cal,
        pose_model=FakePoseModel(mock_pose),
        detect_model=FakeDetectModel(),
    )

    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    tracks, objects, _ = tracker.track_frame(frame, timestamp_sec=0.0)

    assert len(tracks) == 1
    # The animal detection centered inside the human swimmer's body must be suppressed!
    assert len(objects) == 0


def test_bird_in_pool_not_triggering_pet_violation():
    """Verify that a bird does not trigger PET_OR_STRAY_ANIMAL on a swimmer."""
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    track = SwimmerTrack(
        track_id=10,
        role=SwimmerRole.ADULT,
        zone=PoolZone.ZONE_A_SHALLOW,
        posture=PostureState.ACTIVE_SWIM,
        bbox=(200, 100, 260, 200),
        pool_coords_m=(10.0, 5.0),
        keypoints=[],
        suspected_violation=ViolationType.NONE,
    )
    detected_objects = [
        DetectedObject(
            label="bird",
            confidence=0.88,
            bbox=(220, 110, 240, 130),
            zone=PoolZone.ZONE_A_SHALLOW,
        )
    ]
    res, _ = verify_attire_or_item(frame, track, detected_objects, allow_vlm=False)
    assert ViolationType.PET_OR_STRAY_ANIMAL not in res.detected_violations
