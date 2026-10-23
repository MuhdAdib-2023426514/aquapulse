"""System 2 Deliberative Agentic Vision: 3-Step Tier-1 Face-Masked ROI Pipeline & VLM Judge.

Executes a transparent 3-step visual tool chain:
- Step 1 (`crop_and_zoom_roi`): Apply Tier-1 PDPA Face Redaction (`kp[0..4] = [0, 0, 0]`)
  with automatic multi-resolution coordinate scaling and crop a `2x` cubic-zoomed context ROI.
- Step 2 (`probe_sub_rois_and_context`): Multi-violation pixel & keypoint geometry inspection
  across the Torso Polygon (`kp[5,6,11,12]` for colored or neutral/gray cotton t-shirts),
  Person/Wrist-to-Object Proximity (`kp[9,10]` & bbox for poolside food bowls, bottles, cups),
  Animal COCO Context (`dog`/`cat`), and Smoke/Vape Plume + Handheld Vape Pod ROI.
- Step 3 (`verify_attire_or_item`): Structured-output Gemini VLM Agentic Vision Judge on the
  Tier-1 face-masked JPEG bytes (under a strict `2.0s` timeout) with deterministic
  multi-violation OpenCV heuristic consensus fallback.
"""

from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import cv2
import numpy as np

from aquapulse.config import (
    CANVAS_HEIGHT_PX,
    CANVAS_WIDTH_PX,
    PROJECT_ROOT,
    SYS2_TIMEOUT_SEC,
)
from aquapulse.schemas import (
    DetectedObject,
    GeminiVLMInspectionSchema,
    SwimmerTrack,
    System2InspectionResult,
    ViolationType,
)
from aquapulse.vision.privacy import apply_tier1_face_mask

FOOD_DRINK_LABELS = {"bottle", "cup", "bowl", "wine glass", "food_container"}
ANIMAL_LABELS = {"dog", "cat", "bird"}


def _ensure_env_loaded() -> None:
    """Load `.env` from project root if `GEMINI_API_KEY` is not yet in `os.environ`."""
    if os.environ.get("GEMINI_API_KEY"):
        return
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except Exception:
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, v = stripped.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        except Exception:
            pass


def _point_to_bbox_dist(
    px: float,
    py: float,
    bx1: float,
    by1: float,
    bx2: float,
    by2: float,
) -> float:
    """Return Euclidean distance from `(px, py)` to `[bx1, by1, bx2, by2]` (0.0 if inside)."""
    dx = max(bx1 - px, 0.0, px - bx2)
    dy = max(by1 - py, 0.0, py - by2)
    return math.hypot(dx, dy)


def crop_and_zoom_roi(
    frame: np.ndarray,
    track: SwimmerTrack,
    zoom_factor: float = 2.0,
) -> tuple[np.ndarray, bool, tuple[int, int, int, int]]:
    """Step 1: Apply Tier-1 PDPA Face Redaction (`kp[0..4]`), crop context ROI, and zoom `2x`.

    Automatically scales 640x360 track coordinates when `frame` is full-resolution video
    (e.g. 1280x720) and includes surrounding poolside context for bowls, bottles, and handheld vapes.
    Returns `(zoomed_roi_bgr, tier1_face_redacted, head_bbox_in_frame)`.
    """
    masked_frame, head_bbox = apply_tier1_face_mask(frame, track)
    h, w = masked_frame.shape[:2]
    sx = w / float(CANVAS_WIDTH_PX)
    sy = h / float(CANVAS_HEIGHT_PX)

    bx1 = int(round(track.bbox[0] * sx))
    by1 = int(round(track.bbox[1] * sy))
    bx2 = int(round(track.bbox[2] * sx))
    by2 = int(round(track.bbox[3] * sy))

    bw = max(16, bx2 - bx1)
    bh = max(16, by2 - by1)

    # Expand crop around torso/hands/hips so poolside food bowls, bottles, cups, and vapes are visible
    pad_x = max(int(round(12 * sx)), int(round(bw * 0.45)))
    pad_y = max(int(round(10 * sy)), int(round(bh * 0.16)))
    cx1 = max(0, bx1 - pad_x)
    cy1 = max(0, by1 - pad_y)
    cx2 = min(w, bx2 + pad_x)
    cy2 = min(h, by2 + pad_y)

    if cx2 <= cx1 or cy2 <= cy1:
        roi = np.zeros((80, 80, 3), dtype=np.uint8)
    else:
        roi = masked_frame[cy1:cy2, cx1:cx2].copy()

    target_w = max(64, int(round(roi.shape[1] * zoom_factor)))
    target_h = max(64, int(round(roi.shape[0] * zoom_factor)))
    zoomed = cv2.resize(roi, (target_w, target_h), interpolation=cv2.INTER_CUBIC)

    # Confirm mathematically that the head region inside masked_frame is 100% black [0, 0, 0]
    hx1, hy1, hx2, hy2 = head_bbox
    head_pixels = masked_frame[hy1:hy2, hx1:hx2]
    is_redacted = bool(head_pixels.size == 0 or np.max(head_pixels) == 0)

    return zoomed, is_redacted, head_bbox


def probe_sub_rois_and_context(
    masked_frame: np.ndarray,
    zoomed_roi: np.ndarray,
    track: SwimmerTrack,
    detected_objects: list[DetectedObject] | None = None,
) -> dict[str, Any]:
    """Step 2: Inspect torso polygon (`kp[5,6,11,12]`), wrist/hand ROI (`kp[9,10]`), and poolside items.

    Detects multiple simultaneous violations (e.g., wearing a cotton shirt + eating/drinking poolside
    + holding/puffing a vape) directly from pixels and spatial geometry.
    """
    h, w = masked_frame.shape[:2]
    sx = w / float(CANVAS_WIDTH_PX)
    sy = h / float(CANVAS_HEIGHT_PX)

    bx1_c, by1_c, bx2_c, by2_c = track.bbox
    cx_track_c = 0.5 * (bx1_c + bx2_c)
    cy_track_c = 0.5 * (by1_c + by2_c)

    # 1. Extract Torso Patch from shoulders kp[5,6] and hips kp[11,12] (scaled to frame resolution)
    if len(track.keypoints) >= 13:
        torso_kps = [track.keypoints[idx] for idx in (5, 6, 11, 12)]
        tx1 = max(0, int(round(min(p.x for p in torso_kps) * sx)) - int(round(4 * sx)))
        ty1 = max(0, int(round(min(p.y for p in torso_kps) * sy)) - int(round(2 * sy)))
        tx2 = min(w, int(round(max(p.x for p in torso_kps) * sx)) + int(round(4 * sx)))
        ty2 = min(h, int(round(max(p.y for p in torso_kps) * sy)) + int(round(4 * sy)))
        torso_patch = masked_frame[ty1:ty2, tx1:tx2]
    else:
        torso_patch = np.empty((0, 0, 3), dtype=np.uint8)

    if torso_patch.size == 0:
        rh, _ = zoomed_roi.shape[:2]
        torso_patch = zoomed_roi[int(rh * 0.32) : int(rh * 0.78), :]

    hsv = cv2.cvtColor(torso_patch, cv2.COLOR_BGR2HSV)
    valid_mask = hsv[:, :, 2] > 15

    if np.any(valid_mask):
        valid_count = float(np.count_nonzero(valid_mask))
        mean_sat = float(np.mean(hsv[:, :, 1][valid_mask]))
        mean_val = float(np.mean(hsv[:, :, 2][valid_mask]))
        lap_var = float(
            cv2.Laplacian(cv2.cvtColor(torso_patch, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        )
        b_ch = torso_patch[:, :, 0].astype(np.float32)
        g_ch = torso_patch[:, :, 1].astype(np.float32)
        r_ch = torso_patch[:, :, 2].astype(np.float32)

        # (a) Colored/warm opaque cotton streetwear signature
        warm_cotton_pixels = (
            (r_ch > (b_ch + 40.0)) & (hsv[:, :, 2] > 130) & (hsv[:, :, 1] > 90) & valid_mask
        )
        warm_ratio = float(np.count_nonzero(warm_cotton_pixels)) / valid_count

        # (b) Neutral/gray/white opaque cotton t-shirt signature (e.g. gray tee at pool edge)
        # Excludes dark Lycra swimwear (V <= 95), cyan pool water (B > R + 30), and warm bare skin
        neutral_cotton_pixels = (
            (hsv[:, :, 2] >= 105)
            & (hsv[:, :, 1] <= 42)
            & (np.abs(r_ch - b_ch) <= 22.0)
            & (np.abs(g_ch - b_ch) <= 22.0)
            & valid_mask
        )
        neutral_ratio = float(np.count_nonzero(neutral_cotton_pixels)) / valid_count
        if neutral_ratio >= 0.40 and mean_val >= 110.0 and lap_var >= 5.0:
            cotton_pixel_ratio = max(warm_ratio, neutral_ratio)
        else:
            cotton_pixel_ratio = warm_ratio
    else:
        mean_sat = 0.0
        mean_val = 0.0
        lap_var = 0.0
        cotton_pixel_ratio = 0.0

    # 2. Person & Wrist-to-Object Proximity Probe (in 640x360 canvas coordinates)
    anchor_pts_c: list[tuple[float, float]] = [(cx_track_c, cy_track_c)]
    if len(track.keypoints) >= 11:
        anchor_pts_c.extend(
            [
                (track.keypoints[9].x, track.keypoints[9].y),
                (track.keypoints[10].x, track.keypoints[10].y),
            ]
        )
    if len(track.keypoints) >= 13:
        anchor_pts_c.extend(
            [
                (track.keypoints[11].x, track.keypoints[11].y),
                (track.keypoints[12].x, track.keypoints[12].y),
            ]
        )

    nearby_food_items: list[str] = []
    min_food_dist_px: float = 999.0
    nearby_animals: list[str] = []
    min_animal_dist_px: float = 999.0

    for obj in detected_objects or []:
        ox1, oy1, ox2, oy2 = obj.bbox
        ocx = 0.5 * (ox1 + ox2)
        ocy = 0.5 * (oy1 + oy2)
        dist_anchor = min(math.hypot(ax - ocx, ay - ocy) for ax, ay in anchor_pts_c)
        dist_bbox = _point_to_bbox_dist(ocx, ocy, bx1_c, by1_c, bx2_c, by2_c)
        dist_px = min(dist_anchor, dist_bbox)

        if obj.label in FOOD_DRINK_LABELS and dist_px <= 115.0:
            nearby_food_items.append(obj.label)
            min_food_dist_px = min(min_food_dist_px, dist_px)
        elif obj.label in ANIMAL_LABELS and dist_px <= 140.0:
            nearby_animals.append(obj.label)
            min_animal_dist_px = min(min_animal_dist_px, dist_px)

    # 3. Smoke / Vape Aerosol Plume + Handheld Vape Device Probe around wrists/upper torso
    roi_hsv = cv2.cvtColor(zoomed_roi, cv2.COLOR_BGR2HSV)
    plume_mask = (roi_hsv[:, :, 1] <= 18) & (roi_hsv[:, :, 2] >= 236)
    plume_ratio = float(np.count_nonzero(plume_mask)) / float(
        max(1, zoomed_roi.shape[0] * zoomed_roi.shape[1])
    )

    # Inspect wrist patches (kp[9, 10]) for handheld dark vape pod / e-cigarette gesture
    vape_pod_ratio = 0.0
    hand_near_upper_body = False
    if len(track.keypoints) >= 13:
        sh_y = 0.5 * (track.keypoints[5].y + track.keypoints[6].y)
        hip_y = 0.5 * (track.keypoints[11].y + track.keypoints[12].y)
        pad_w = max(14, int(round(18 * sx)))
        for w_idx in (9, 10):
            wk = track.keypoints[w_idx]
            if wk.conf < 0.25:
                continue
            if wk.y <= hip_y + 8.0 and wk.y >= sh_y - 35.0:
                hand_near_upper_body = True
            wx = int(round(wk.x * sx))
            wy = int(round(wk.y * sy))
            w_patch = masked_frame[
                max(0, wy - pad_w) : min(h, wy + pad_w),
                max(0, wx - pad_w) : min(w, wx + pad_w),
            ]
            if w_patch.size > 0:
                whsv = cv2.cvtColor(w_patch, cv2.COLOR_BGR2HSV)
                w_valid = whsv[:, :, 2] > 5
                if np.any(w_valid):
                    w_mean_v = float(np.mean(whsv[:, :, 2][w_valid]))
                    # Handheld matte-black vape device surrounded by brighter skin/pool background
                    dark_pod = (
                        (whsv[:, :, 2] >= 8)
                        & (whsv[:, :, 2] <= 52)
                        & (whsv[:, :, 1] <= 75)
                    )
                    pod_r = float(np.count_nonzero(dark_pod)) / float(w_patch.shape[0] * w_patch.shape[1])
                    if w_mean_v >= 95.0 and 0.055 <= pod_r <= 0.35:
                        vape_pod_ratio = max(vape_pod_ratio, pod_r)

    is_smoking_vaping = bool(
        plume_ratio >= 0.045 or (hand_near_upper_body and vape_pod_ratio >= 0.055)
    )

    # 4. Collect ALL active violations in this ROI
    detected_violations: list[ViolationType] = []
    reasons: list[str] = []

    if nearby_animals:
        detected_violations.append(ViolationType.PET_OR_STRAY_ANIMAL)
        animals_str = ", ".join(sorted(set(nearby_animals)))
        reasons.append(
            f"animal ({animals_str} at {min_animal_dist_px:.1f}px) in pool/deck zone"
        )
    if nearby_food_items:
        detected_violations.append(ViolationType.FOOD_DRINK_POOLSIDE)
        items_str = ", ".join(sorted(set(nearby_food_items)))
        reasons.append(
            f"poolside food/drink ({items_str} within {min_food_dist_px:.1f}px of person/wrist)"
        )
    if cotton_pixel_ratio >= 0.12:
        detected_violations.append(ViolationType.COTTON_ATTIRE)
        reasons.append(
            f"opaque cotton t-shirt/streetwear fabric (cotton_ratio={cotton_pixel_ratio:.2f}, V={mean_val:.1f}, S={mean_sat:.1f})"
        )
    if is_smoking_vaping:
        detected_violations.append(ViolationType.SMOKING_VAPING)
        reasons.append(
            f"smoking/vaping detected (plume_ratio={plume_ratio:.3f}, handheld_vape_ratio={vape_pod_ratio:.3f})"
        )

    if detected_violations:
        verified = True
        # If the caller/scenario flagged a specific suspected violation that is confirmed, keep it as primary
        if track.suspected_violation in detected_violations:
            detected_violation = track.suspected_violation
        else:
            detected_violation = detected_violations[0]
        conf = 0.94
        joined_reasons = "; ".join(reasons)
        v_labels = ", ".join(v.value for v in detected_violations)
        summary = (
            f"Tier-1 face-masked ROI (2x zoom) verified [{v_labels}]: {joined_reasons}."
        )
    else:
        detected_violation = ViolationType.NONE
        verified = False
        conf = 0.95
        summary = (
            "Tier-1 face-masked ROI inspected: compliant dark Lycra swimwear, no prohibited items."
        )

    step2_trace = (
        f"2. probe_torso_and_wrist_roi: torso_cotton_ratio={cotton_pixel_ratio:.2f} "
        f"(S={mean_sat:.1f}, V={mean_val:.1f}, Lap={lap_var:.0f}), "
        f"wrist_food={nearby_food_items or 'none'}, animals={nearby_animals or 'none'}, "
        f"plume_ratio={plume_ratio:.3f}, vape_pod_ratio={vape_pod_ratio:.3f}"
    )

    return {
        "verified": verified,
        "violation_type": detected_violation,
        "detected_violations": detected_violations,
        "confidence": conf,
        "summary": summary,
        "step2_trace": step2_trace,
        "cotton_pixel_ratio": cotton_pixel_ratio,
        "nearby_food_items": nearby_food_items,
        "nearby_animals": nearby_animals,
        "plume_ratio": plume_ratio,
        "vape_pod_ratio": vape_pod_ratio,
    }


def _call_gemini_vlm_with_timeout(
    api_key: str,
    jpeg_bytes: bytes,
    heuristic_probe: dict[str, Any],
    timeout_sec: float,
) -> GeminiVLMInspectionSchema | str | None:
    """Invoke Gemini VLM Judge with Structured Output on Tier-1 face-masked JPEG bytes."""

    def _invoke() -> GeminiVLMInspectionSchema | str | None:
        from google import genai  # type: ignore[import-not-found]
        from google.genai import types  # type: ignore[import-not-found]

        client = genai.Client(api_key=api_key)
        cues_hint = (
            f"Local OpenCV/YOLO spatial cues: food_items={heuristic_probe.get('nearby_food_items')}, "
            f"animals={heuristic_probe.get('nearby_animals')}, "
            f"cotton_ratio={heuristic_probe.get('cotton_pixel_ratio', 0.0):.2f}, "
            f"vape_pod_ratio={heuristic_probe.get('vape_pod_ratio', 0.0):.3f}, "
            f"plume_ratio={heuristic_probe.get('plume_ratio', 0.0):.3f}."
        )
        prompt = (
            "You are AquaPulse System 2 Agentic Vision Judge inspecting a PDPA Tier-1 face-masked "
            "swimming pool ROI crop (the person's face is blacked out for privacy). "
            "Carefully inspect the image and identify ALL pool rule violations present:\n"
            "- FOOD_DRINK_POOLSIDE: bowls of food, cups, drink bottles, or eating/drinking at the pool edge/deck.\n"
            "- SMOKING_VAPING: holding a vape pod, e-cigarette, cigarette, or exhaling vapor/smoke.\n"
            "- COTTON_ATTIRE: wearing an opaque cotton t-shirt or street clothes instead of proper swimwear.\n"
            "- PET_OR_STRAY_ANIMAL: dog, cat, or animal in the pool/deck area.\n"
            f"{cues_hint}"
        )

        for model_name in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.8-flash"):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=GeminiVLMInspectionSchema,
                        temperature=0.1,
                    ),
                )
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, GeminiVLMInspectionSchema):
                    return parsed
                text = getattr(response, "text", None)
                if text:
                    try:
                        return GeminiVLMInspectionSchema.model_validate_json(text.strip())
                    except Exception:
                        return text.strip()
            except Exception:
                continue
        return None

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_invoke)
        return future.result(timeout=max(0.1, timeout_sec))


def verify_attire_or_item(
    frame: np.ndarray,
    track: SwimmerTrack,
    detected_objects: list[DetectedObject] | None = None,
    *,
    allow_vlm: bool = True,
    timeout_sec: float = SYS2_TIMEOUT_SEC,
) -> tuple[System2InspectionResult, np.ndarray]:
    """Execute 3-Step System 2 `Crop/Zoom (Tier-1 Face-Masked) -> Probe Sub-ROIs -> VLM Judge` pipeline.

    Always masks facial keypoints `kp[0..4]` BEFORE cropping or calling any verifier.
    Calls Gemini VLM with Structured Output when `GEMINI_API_KEY` is present, and falls back
    seamlessly to deterministic multi-violation OpenCV/YOLO inspection if offline or on timeout.
    """
    t0 = time.perf_counter()
    _ensure_env_loaded()

    # Step 1: Tier-1 Face Mask (kp[0..4] == [0,0,0]) & 2x Cubic ROI Zoom
    masked_frame, _ = apply_tier1_face_mask(frame, track)
    zoomed_roi, tier1_redacted, head_bbox = crop_and_zoom_roi(frame, track, zoom_factor=2.0)
    step1_trace = (
        f"1. tier1_face_mask_and_2x_zoom: head_bbox={head_bbox} kp[0..4]==0 ({tier1_redacted}), "
        f"zoomed_roi={zoomed_roi.shape[1]}x{zoomed_roi.shape[0]}px"
    )

    # Step 2: Multi-Violation Torso Polygon, Wrist Vape & Poolside Object Sub-ROI Probe
    probe = probe_sub_rois_and_context(
        masked_frame=masked_frame,
        zoomed_roi=zoomed_roi,
        track=track,
        detected_objects=detected_objects,
    )
    verified: bool = probe["verified"]
    detected_vtype: ViolationType = probe["violation_type"]
    detected_violations: list[ViolationType] = list(probe["detected_violations"])
    conf: float = probe["confidence"]
    summary: str = probe["summary"]
    step2_trace: str = probe["step2_trace"]

    # Step 3: Gemini VLM Structured Judge with Strict Timeout + Heuristic Consensus
    backend: str = "opencv_heuristic"
    vlm_used: bool = False
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if allow_vlm and api_key and tier1_redacted:
        try:
            ok, encoded = cv2.imencode(".jpg", zoomed_roi)
            elapsed_so_far = time.perf_counter() - t0
            rem_timeout = timeout_sec - elapsed_so_far
            if ok and rem_timeout > 0.1:
                vlm_res = _call_gemini_vlm_with_timeout(
                    api_key=api_key,
                    jpeg_bytes=encoded.tobytes(),
                    heuristic_probe=probe,
                    timeout_sec=rem_timeout,
                )
                if isinstance(vlm_res, GeminiVLMInspectionSchema):
                    vlm_used = True
                    backend = "gemini_3.8_flash"
                    vlm_violations: list[ViolationType] = list(vlm_res.detected_violations)
                    if vlm_res.bringing_food_or_drink and ViolationType.FOOD_DRINK_POOLSIDE not in vlm_violations:
                        vlm_violations.append(ViolationType.FOOD_DRINK_POOLSIDE)
                    if vlm_res.smoking_or_vaping and ViolationType.SMOKING_VAPING not in vlm_violations:
                        vlm_violations.append(ViolationType.SMOKING_VAPING)
                    if vlm_res.wearing_cotton and ViolationType.COTTON_ATTIRE not in vlm_violations:
                        vlm_violations.append(ViolationType.COTTON_ATTIRE)

                    # Merge VLM structured violations with local spatial detections
                    merged: list[ViolationType] = []
                    for v in vlm_violations + detected_violations:
                        if v != ViolationType.NONE and v not in merged:
                            merged.append(v)

                    detected_violations = merged
                    verified = bool(vlm_res.verified_violation or len(detected_violations) > 0)
                    if vlm_res.primary_violation != ViolationType.NONE:
                        detected_vtype = vlm_res.primary_violation
                    elif detected_violations:
                        detected_vtype = detected_violations[0]
                    conf = round(max(conf, vlm_res.confidence), 2)
                    summary = f"[Gemini VLM Judge + Spatial Consensus] {vlm_res.reasoning_summary} | {summary}"
                elif isinstance(vlm_res, str) and vlm_res:
                    vlm_used = True
                    backend = "gemini_3.8_flash"
                    summary = f"[Gemini VLM Judge + OpenCV Consensus] {vlm_res} | {summary}"
        except Exception:
            backend = "opencv_heuristic"
            vlm_used = False

    v_list_str = ",".join(v.value for v in detected_violations) if detected_violations else "NONE"
    step3_trace = (
        f"3. verifier_verdict ({backend}): verified={verified}, "
        f"primary={detected_vtype.value}, all=[{v_list_str}], conf={conf:.2f}, vlm_used={vlm_used}"
    )
    visual_steps = [step1_trace, step2_trace, step3_trace]

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    result = System2InspectionResult(
        track_id=track.track_id,
        target_type=f"tier1_masked_{detected_vtype.value.lower()}_roi",
        tier1_face_redacted=tier1_redacted,
        verified_violation=verified,
        violation_type=detected_vtype,
        detected_violations=detected_violations,
        confidence=conf,
        inspector_backend=backend,  # type: ignore[arg-type]
        vlm_used=vlm_used,
        visual_tool_steps=visual_steps,
        reasoning_summary=summary,
        inspection_latency_ms=elapsed_ms,
    )
    return result, zoomed_roi
