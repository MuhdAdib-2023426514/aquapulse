"""Tests for RealFrameTracker with mocked/fake detection results."""

import numpy as np
import torch

from aquapulse.schemas import PostureState, SwimmerRole
from aquapulse.vision.calibration import PoolCalibration
from aquapulse.vision.video_tracker import RealFrameTracker


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

    # Manually seed a history for track 99 in water
    from collections import deque

    from aquapulse.vision.video_tracker import TrackHistoryItem

    tracker._history[99] = deque([TrackHistoryItem(t=0.0, x_m=15.0, y_m=6.0)])

    # Next frame, detection is lost (e.g. swimmer is fully underwater)
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    tracks, _, _ = tracker.track_frame(frame, timestamp_sec=1.0)

    # Should emit a ghost track with PostureState.HORIZONTAL_SUBMERGED and is_submerged=True
    assert len(tracks) == 1
    assert tracks[0].track_id == 99
    assert tracks[0].is_submerged is True
    assert tracks[0].posture == PostureState.HORIZONTAL_SUBMERGED
