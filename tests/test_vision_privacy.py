"""Milestone 3 verification tests: Two-Tier PDPA Shield, System 2 Agentic ROI Inspector, OpenCV Water Clarity Inspector, and 6-Scenario Synthesizer."""

from __future__ import annotations

import numpy as np

from aquapulse.schemas import (
    AgentState,
    PostureState,
    ScenarioName,
    SwimmerRole,
    ViolationType,
)
from aquapulse.vision.agentic_inspector import crop_and_zoom_roi, verify_attire_or_item
from aquapulse.vision.detector import (
    AquaPulseVisionDetector,
    build_coco_keypoints,
    classify_pose_and_flailing,
    synthesize_scenario_frame,
)
from aquapulse.vision.privacy import apply_tier1_face_mask, render_tier2_silhouette_frame
from aquapulse.vision.water_inspector import inspect_water_clarity


def test_tier1_pdpa_face_masking_and_roi_zoom() -> None:
    """Verify Tier-1 zeroes out head/face kp[0..4] while preserving torso fabric pixels."""
    frame, tracks, _ = synthesize_scenario_frame(
        ScenarioName.COTTON_TSHIRT_AND_FOOD_NUDGE, elapsed_sec=16.0
    )
    cotton_track = next(t for t in tracks if t.suspected_violation == ViolationType.COTTON_ATTIRE)

    masked_frame, (hx1, hy1, hx2, hy2) = apply_tier1_face_mask(frame, cotton_track)
    head_patch = masked_frame[hy1:hy2, hx1:hx2]
    assert head_patch.size > 0
    assert int(np.max(head_patch)) == 0  # 100% blacked out [0, 0, 0]

    # Torso below head bbox must remain visible (non-zero) for System 2 fabric inspection
    bx1, _, bx2, by2 = cotton_track.bbox
    torso_patch = masked_frame[hy2:by2, bx1:bx2]
    assert torso_patch.size > 0
    assert int(np.max(torso_patch)) > 100

    zoomed_roi, is_redacted, _ = crop_and_zoom_roi(frame, cotton_track, zoom_factor=2.0)
    assert is_redacted is True
    assert zoomed_roi.shape[0] >= 64
    assert zoomed_roi.shape[1] >= 64


def test_tier2_pdpa_skeletal_silhouette_zero_raw_pixels() -> None:
    """Verify Tier-2 Silhouette Mode renders strictly on a fresh blueprint with 0% raw pixels."""
    _, tracks, objects = synthesize_scenario_frame(
        ScenarioName.SILENT_DROWNING_RESCUE, elapsed_sec=12.0
    )
    silhouette = render_tier2_silhouette_frame(
        tracks=tracks,
        objects=objects,
        overall_state=AgentState.VERIFY,
    )
    assert silhouette.shape == (360, 640, 3)
    assert silhouette.dtype == np.uint8
    # Blueprint deck pixel at top-left (5, 5) is strictly the dark blueprint BGR (34, 22, 11)
    assert tuple(int(c) for c in silhouette[5, 5]) == (34, 22, 11)


def test_system2_agentic_inspector_attire_and_food_verification() -> None:
    """Verify System 2 ROI Inspector confirms both cotton streetwear and poolside food/drinks."""
    frame, tracks, objects = synthesize_scenario_frame(
        ScenarioName.COTTON_TSHIRT_AND_FOOD_NUDGE, elapsed_sec=16.0
    )
    cotton_track = next(t for t in tracks if t.suspected_violation == ViolationType.COTTON_ATTIRE)
    food_track = next(
        t for t in tracks if t.suspected_violation == ViolationType.FOOD_DRINK_POOLSIDE
    )

    res_cotton, roi_cotton = verify_attire_or_item(frame, cotton_track, objects)
    assert res_cotton.tier1_face_redacted is True
    assert res_cotton.verified_violation is True
    assert res_cotton.violation_type == ViolationType.COTTON_ATTIRE
    assert roi_cotton.ndim == 3

    res_food, _ = verify_attire_or_item(frame, food_track, objects)
    assert res_food.tier1_face_redacted is True
    assert res_food.verified_violation is True
    assert res_food.violation_type == ViolationType.FOOD_DRINK_POOLSIDE


def test_opencv_water_clarity_and_monsoon_debris_inspector() -> None:
    """Verify OpenCV distinguishes crystal-clear water from post-monsoon debris & algae drift."""
    clean_frame, _, _ = synthesize_scenario_frame(
        ScenarioName.NORMAL_LAP_AND_FAMILY, elapsed_sec=0.0
    )
    clean_report, _ = inspect_water_clarity(clean_frame)
    assert clean_report.status == "CRYSTAL_CLEAR"
    assert clean_report.turbidity_score >= 85.0
    assert clean_report.floating_debris_count <= 2
    assert clean_report.cleaner_ticket_opened is False

    monsoon_frame, _, _ = synthesize_scenario_frame(
        ScenarioName.MONSOON_DEBRIS_AND_ALGAE, elapsed_sec=0.0
    )
    monsoon_report, annotated_monsoon = inspect_water_clarity(monsoon_frame)
    assert monsoon_report.status == "MONSOON_DEBRIS_ALERT"
    assert monsoon_report.floating_debris_count >= 10
    assert monsoon_report.algae_green_index > clean_report.algae_green_index
    assert monsoon_report.cleaner_ticket_opened is True
    assert annotated_monsoon.shape == (360, 640, 3)


def test_all_six_scenarios_and_flailing_pose_classifier() -> None:
    """Verify all 6 pitch scenarios and Active Flailing -> Silent Submersion pose geometry."""
    detector = AquaPulseVisionDetector()
    for scenario in ScenarioName:
        frame, tracks, _ = detector.process_scenario(scenario, elapsed_sec=5.0)
        assert frame.shape == (360, 640, 3)
        if scenario != ScenarioName.MONSOON_DEBRIS_AND_ALGAE:
            assert len(tracks) >= 2
            assert all(len(t.keypoints) == 17 for t in tracks)

    # Verify Active Flailing at t=4.0s vs Silent Submersion at t=14.0s in SILENT_DROWNING_RESCUE
    _, tracks_t4, _ = detector.process_scenario(
        ScenarioName.SILENT_DROWNING_RESCUE, elapsed_sec=4.0
    )
    victim_t4 = next(t for t in tracks_t4 if t.track_id == 201)
    assert victim_t4.posture == PostureState.ACTIVE_FLAILING
    assert victim_t4.is_flailing is True
    assert victim_t4.is_submerged is False

    _, tracks_t14, _ = detector.process_scenario(
        ScenarioName.SILENT_DROWNING_RESCUE, elapsed_sec=14.0
    )
    victim_t14 = next(t for t in tracks_t14 if t.track_id == 201)
    assert victim_t14.posture == PostureState.HORIZONTAL_SUBMERGED
    assert victim_t14.is_submerged is True

    # Verify skeletal keypoint geometry classifier directly
    flail_kps, _ = build_coco_keypoints(
        350, 180, posture=PostureState.ACTIVE_FLAILING, role=SwimmerRole.ADULT, elapsed_sec=1.0
    )
    posture_cls, is_flail_cls, _ = classify_pose_and_flailing(flail_kps, displacement_m=0.02)
    assert posture_cls == PostureState.ACTIVE_FLAILING
    assert is_flail_cls is True
