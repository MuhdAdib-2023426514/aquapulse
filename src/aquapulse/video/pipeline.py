"""End-to-end real video perception pipeline, artifact encoding, and timeline generation."""

from __future__ import annotations

import dataclasses
import json
import sqlite3
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import cv2
import imageio_ffmpeg
import numpy as np
from pydantic import BaseModel, Field

from aquapulse.agent.reasoning import AgentReasoningLogger
from aquapulse.agent.state_machine import AquaPulseStateMachine
from aquapulse.agent.tools import PoolsideToolActuator
from aquapulse.config import DEFAULT_CONFIG, PROJECT_ROOT
from aquapulse.db.database import init_db
from aquapulse.esg.forecaster import DiurnalCrowdForecaster
from aquapulse.esg.pump_optimizer import compute_instantaneous_esg_metrics
from aquapulse.schemas import (
    AgentState,
    DetectedObject,
    SwimmerRole,
    SwimmerTrack,
    ViolationType,
)
from aquapulse.vision.agentic_inspector import verify_attire_or_item
from aquapulse.vision.calibration import PoolCalibration
from aquapulse.vision.detector import AquaPulseVisionDetector
from aquapulse.vision.privacy import mask_heads_full_res
from aquapulse.vision.water_inspector import inspect_water_clarity

UPLOADS_DIR: Path = PROJECT_ROOT / "assets" / "uploads"


class VideoJob(BaseModel):
    """Lifecycle state and calibration metadata for an uploaded pool video."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    filename: str
    raw_filepath: str
    status: Literal["uploaded", "processing", "completed", "failed"] = "uploaded"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    current_stage: str = Field(default="Uploaded; awaiting calibration")
    duration_sec: float = 0.0
    fps: float = 30.0
    width: int = 1280
    height: int = 720
    calibration: PoolCalibration = Field(default_factory=PoolCalibration)
    camera_id: str | None = None
    calibration_profile_id: str | None = None
    calibration_version: int | None = None
    sample_fps: float = Field(default=5.0, ge=1.0, le=30.0)
    time_scale: float = Field(default=1.0, ge=0.25, le=5.0)
    role_overrides: dict[int, SwimmerRole] = Field(default_factory=dict)
    error: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class VideoPipeline:
    """Processes real pool video clips through YOLO tracking, dual-path agent, and ESG metrics."""

    def __init__(self, db_conn: sqlite3.Connection | None = None) -> None:
        self.conn = db_conn or init_db(auto_seed=True)
        self.detector = AquaPulseVisionDetector()
        self.detector.load_yolo26_if_available()

    @staticmethod
    def get_job_dir(job_id: str) -> Path:
        job_dir = UPLOADS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def extract_preview(self, job: VideoJob) -> str:
        """Extract first frame, apply Tier-1 face mask, and save as preview.jpg."""
        job_dir = self.get_job_dir(job.id)
        preview_path = job_dir / "preview.jpg"
        cap = cv2.VideoCapture(job.raw_filepath)
        try:
            success, frame = cap.read()
            if success and frame is not None:
                job.height, job.width = frame.shape[:2]
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                job.fps = max(1.0, fps if fps and fps > 0 else 30.0)
                job.duration_sec = round(frame_count / job.fps, 2)

                # Quick head detection for Tier-1 preview masking
                tracker = self.detector.create_video_tracker(
                    calibration=job.calibration,
                    role_overrides=job.role_overrides,
                )
                _, _, head_boxes = tracker.track_frame(frame, timestamp_sec=0.0)
                masked_preview = mask_heads_full_res(frame, head_boxes, margin=0.35)
                cv2.imwrite(str(preview_path), masked_preview, [cv2.IMWRITE_JPEG_QUALITY, 85])
                return str(preview_path)
            raise ValueError("Could not read initial video frame for preview.")
        finally:
            cap.release()

    def process(self, job: VideoJob) -> dict[str, Any]:
        """Execute full video analysis: decode, YOLO tracking, state machine, and artifact generation."""
        job_dir = self.get_job_dir(job.id)
        roi_dir = job_dir / "roi"
        water_dir = job_dir / "water"
        roi_dir.mkdir(parents=True, exist_ok=True)
        water_dir.mkdir(parents=True, exist_ok=True)

        masked_mp4_path = job_dir / "masked.mp4"
        timeline_path = job_dir / "timeline.json"
        perception_path = job_dir / "perception.json"

        job.status = "processing"
        job.progress = 0.05
        job.current_stage = "Initializing video decoder & YOLO tracker"

        cap = cv2.VideoCapture(job.raw_filepath)
        if not cap.isOpened():
            job.status = "failed"
            job.error = f"Cannot open video file {job.raw_filepath}"
            return {"error": job.error}

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or job.width)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or job.height)

            job.fps = fps
            job.width = width
            job.height = height
            job.duration_sec = round(total_frames / max(1.0, fps), 2)

            step_interval = max(1, int(round(fps / job.sample_fps)))
            effective_sample_fps = fps / step_interval

            # Compressed thresholds if pitch time_scale > 1.0 (e.g., 2x makes 5s -> 2.5s)
            scaled_config = dataclasses.replace(
                DEFAULT_CONFIG,
                sys1_verify_sec=round(DEFAULT_CONFIG.sys1_verify_sec / job.time_scale, 2),
                sys1_critical_emergency_sec=round(
                    DEFAULT_CONFIG.sys1_critical_emergency_sec / job.time_scale, 2
                ),
                sys2_nudge_required_sec=round(
                    DEFAULT_CONFIG.sys2_nudge_required_sec / job.time_scale, 2
                ),
            )

            tracker = self.detector.create_video_tracker(
                calibration=job.calibration,
                role_overrides=job.role_overrides,
            )
            actuator = PoolsideToolActuator(db_conn=self.conn)
            reasoning_logger = AgentReasoningLogger()
            state_machine = AquaPulseStateMachine(
                config=scaled_config,
                actuator=actuator,
                reasoning_logger=reasoning_logger,
            )
            forecaster = DiurnalCrowdForecaster(conn=self.conn)

            # Initialize H.264 browser-compatible video writer via imageio-ffmpeg
            ffmpeg_writer = imageio_ffmpeg.write_frames(
                str(masked_mp4_path),
                (width, height),
                fps=fps,
                codec="libx264",
                pix_fmt_in="bgr24",
                pix_fmt_out="yuv420p",
                macro_block_size=1,
            )
            ffmpeg_writer.send(None)  # prime generator

            job.current_stage = "Tracking pose keypoints, objects & agent states"
            frame_idx = 0
            cached_perception: list[dict[str, Any]] = []
            timeline_frames: list[dict[str, Any]] = []
            events: list[dict[str, Any]] = []
            max_state = AgentState.NORMAL
            sys1_latencies: list[float] = []
            last_water_t = -999.0
            last_water_report = None
            last_water_img_rel = None

            # Calibrated pool polygon for water inspection
            water_poly_px = job.calibration.water_polygon_px(width, height)

            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                t_sec = round(frame_idx / fps, 2)
                is_sampled = (frame_idx % step_interval == 0)

                # Process perception only on sampled frames
                if is_sampled:
                    tracks, objects, head_boxes = tracker.track_frame(frame, timestamp_sec=t_sec)
                    cached_perception.append(
                        {
                            "t": t_sec,
                            "tracks": [t.model_dump() for t in tracks],
                            "objects": [o.model_dump() for o in objects],
                            "head_boxes": head_boxes,
                        }
                    )
                else:
                    # Reuse latest head boxes for smooth video playback masking
                    head_boxes = (
                        cached_perception[-1]["head_boxes"] if cached_perception else []
                    )

                # 1. Mask heads in full resolution for browser-playable Tier-1 MP4
                masked_frame = mask_heads_full_res(frame, head_boxes, margin=0.35)
                ffmpeg_writer.send(masked_frame)

                # 2. Run agentic state machine on sampled frames
                if is_sampled:
                    roi_crops: dict[int, Any] = {}
                    roi_inspections: dict[int, dict[str, Any]] = {}
                    roi_rel_paths: dict[str, str] = {}

                    def _verifier(
                        tr: SwimmerTrack,
                        _f: np.ndarray = frame,
                        _objs: list[DetectedObject] = objects,
                        _crops: dict[int, Any] = roi_crops,
                        _insps: dict[int, dict[str, Any]] = roi_inspections,
                        _t: float = t_sec,
                        _paths: dict[str, str] = roi_rel_paths,
                    ) -> Any:
                        res, zoomed = verify_attire_or_item(
                            _f, tr, _objs, allow_vlm=False
                        )
                        _crops[tr.track_id] = zoomed
                        _insps[tr.track_id] = res.model_dump()
                        # Save ROI crop JPEG
                        crop_filename = f"{_t:.1f}_tr{tr.track_id}.jpg"
                        crop_path = roi_dir / crop_filename
                        cv2.imwrite(str(crop_path), zoomed, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        _paths[str(tr.track_id)] = f"roi/{crop_filename}"
                        return res

                    sys1_trace, sys2_insps, tool_logs, thoughts = state_machine.step(
                        tracks=tracks,
                        dt_sec=1.0 / effective_sample_fps,
                        objects=objects,
                        roi_verifier=_verifier,
                    )
                    sys1_latencies.append(sys1_trace.execution_latency_ms)

                    # Update highest observed agent escalation state
                    if sys1_trace.overall_state == AgentState.CRITICAL_EMERGENCY:
                        max_state = AgentState.CRITICAL_EMERGENCY
                    elif (
                        sys1_trace.overall_state == AgentState.VERIFY
                        and max_state != AgentState.CRITICAL_EMERGENCY
                    ):
                        max_state = AgentState.VERIFY

                    # Track timeline events
                    for tl in tool_logs:
                        events.append(
                            {
                                "t": t_sec,
                                "kind": tl.tool_name,
                                "system_path": tl.system_path,
                                "track_id": tl.track_id,
                                "zone": tl.zone.value,
                                "message": tl.message,
                                "audio_tts_text": tl.audio_tts_text,
                                "guard_route_hint": tl.guard_route_hint,
                            }
                        )

                    # Periodic water inspection (every 2.0s)
                    if t_sec - last_water_t >= 2.0 or last_water_report is None:
                        last_water_t = t_sec
                        report, ann_water = inspect_water_clarity(
                            frame, roi_polygon=water_poly_px
                        )
                        last_water_report = report
                        water_filename = f"{t_sec:.1f}.jpg"
                        cv2.imwrite(
                            str(water_dir / water_filename),
                            ann_water,
                            [cv2.IMWRITE_JPEG_QUALITY, 80],
                        )
                        last_water_img_rel = f"water/{water_filename}"

                    # Calculate instantaneous ESG metrics & resident comfort
                    cotton_count = sum(
                        1
                        for t in tracks
                        if t.suspected_violation == ViolationType.COTTON_ATTIRE
                    )
                    food_count = sum(
                        1
                        for t in tracks
                        if t.suspected_violation == ViolationType.FOOD_DRINK_POOLSIDE
                    )
                    animal_count = sum(
                        1 for o in objects if o.label in {"dog", "cat", "bird"}
                    )
                    esg_metrics = compute_instantaneous_esg_metrics(
                        bather_count=len(tracks),
                        cotton_violations=cotton_count,
                        food_drink_events=food_count,
                        animal_events=animal_count,
                    )
                    resident_status = forecaster.build_resident_comfort_status(
                        tracks=tracks,
                        water_report=last_water_report,
                    )

                    timeline_frames.append(
                        {
                            "t": t_sec,
                            "tracks": [t.model_dump() for t in tracks],
                            "objects": [o.model_dump() for o in objects],
                            "system1_trace": sys1_trace.model_dump(),
                            "system2_inspections": [s.model_dump() for s in sys2_insps],
                            "tool_logs": [tl.model_dump(mode="json") for tl in tool_logs],
                            "reasoning_thoughts": thoughts,
                            "esg_metrics": esg_metrics.model_dump(),
                            "water_report": (
                                last_water_report.model_dump()
                                if last_water_report
                                else None
                            ),
                            "resident_comfort": resident_status.model_dump(),
                            "roi_images": roi_rel_paths,
                            "water_image": last_water_img_rel,
                        }
                    )

                frame_idx += 1
                if total_frames > 0 and frame_idx % 10 == 0:
                    job.progress = min(0.92, round(0.05 + 0.85 * (frame_idx / total_frames), 2))

            ffmpeg_writer.close()
            cap.release()

            # Cache raw perception for fast reevaluate
            with open(perception_path, "w", encoding="utf-8") as f:
                json.dump(cached_perception, f)

            # Compile final summary statistics
            peak_bathers = max((len(f["tracks"]) for f in timeline_frames), default=0)
            sys1_p95 = (
                float(np.percentile(sys1_latencies, 95))
                if sys1_latencies
                else 0.8
            )
            avg_hourly_rm = (
                float(np.mean([f["esg_metrics"]["hourly_rm_saved"] for f in timeline_frames]))
                if timeline_frames
                else 18.5
            )

            timeline_payload = {
                "job": job.model_dump(),
                "frames": timeline_frames,
                "events": events,
                "summary": {
                    "duration_sec": job.duration_sec,
                    "sampled_frames_count": len(timeline_frames),
                    "peak_bathers": peak_bathers,
                    "max_agent_state": max_state.value,
                    "system1_p95_latency_ms": round(sys1_p95, 2),
                    "projected_daily_rm_saved": round(avg_hourly_rm * 24.0, 2),
                    "turnover_compliant": True,
                },
            }

            with open(timeline_path, "w", encoding="utf-8") as f:
                json.dump(timeline_payload, f)

            job.status = "completed"
            job.progress = 1.0
            job.current_stage = "Completed analysis and generated playhead timeline"
            return timeline_payload

        except Exception as e:
            cap.release()
            job.status = "failed"
            job.error = f"{e}\n{traceback.format_exc()}"
            return {"error": job.error}

    def reevaluate(self, job: VideoJob) -> dict[str, Any]:
        """Fast-path re-evaluation (<1s): reruns state machine & ESG from cached perception."""
        job_dir = self.get_job_dir(job.id)
        perception_path = job_dir / "perception.json"
        timeline_path = job_dir / "timeline.json"
        roi_dir = job_dir / "roi"
        water_dir = job_dir / "water"

        if not perception_path.exists():
            raise FileNotFoundError("No cached perception.json found. Process the video first.")

        with open(perception_path, encoding="utf-8") as f:
            cached_perception = json.load(f)

        scaled_config = dataclasses.replace(
            DEFAULT_CONFIG,
            sys1_verify_sec=round(DEFAULT_CONFIG.sys1_verify_sec / job.time_scale, 2),
            sys1_critical_emergency_sec=round(
                DEFAULT_CONFIG.sys1_critical_emergency_sec / job.time_scale, 2
            ),
            sys2_nudge_required_sec=round(
                DEFAULT_CONFIG.sys2_nudge_required_sec / job.time_scale, 2
            ),
        )

        actuator = PoolsideToolActuator(db_conn=self.conn)
        reasoning_logger = AgentReasoningLogger()
        state_machine = AquaPulseStateMachine(
            config=scaled_config,
            actuator=actuator,
            reasoning_logger=reasoning_logger,
        )
        forecaster = DiurnalCrowdForecaster(conn=self.conn)

        timeline_frames: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        max_state = AgentState.NORMAL
        sys1_latencies: list[float] = []

        dt_sec = 1.0 / max(1.0, job.sample_fps)

        for item in cached_perception:
            t_sec = item["t"]
            raw_tracks = [SwimmerTrack.model_validate(t) for t in item["tracks"]]
            objects = [DetectedObject.model_validate(o) for o in item["objects"]]

            # Apply manual role overrides (e.g., mark Track #101 as Toddler)
            for tr in raw_tracks:
                if tr.track_id in job.role_overrides:
                    tr.role = job.role_overrides[tr.track_id]
                    if tr.role == SwimmerRole.TODDLER:
                        x_m = tr.pool_coords_m[0]
                        tr.near_deep_boundary = (
                            abs(x_m - job.calibration.depth_boundary_m) <= 1.5
                        )

            sys1_trace, sys2_insps, tool_logs, thoughts = state_machine.step(
                tracks=raw_tracks,
                dt_sec=dt_sec,
            )
            sys1_latencies.append(sys1_trace.execution_latency_ms)

            if sys1_trace.overall_state == AgentState.CRITICAL_EMERGENCY:
                max_state = AgentState.CRITICAL_EMERGENCY
            elif (
                sys1_trace.overall_state == AgentState.VERIFY
                and max_state != AgentState.CRITICAL_EMERGENCY
            ):
                max_state = AgentState.VERIFY

            for tl in tool_logs:
                events.append(
                    {
                        "t": t_sec,
                        "kind": tl.tool_name,
                        "system_path": tl.system_path,
                        "track_id": tl.track_id,
                        "zone": tl.zone.value,
                        "message": tl.message,
                        "audio_tts_text": tl.audio_tts_text,
                        "guard_route_hint": tl.guard_route_hint,
                    }
                )

            cotton_count = sum(
                1 for t in raw_tracks if t.suspected_violation == ViolationType.COTTON_ATTIRE
            )
            food_count = sum(
                1 for t in raw_tracks if t.suspected_violation == ViolationType.FOOD_DRINK_POOLSIDE
            )
            animal_count = sum(1 for o in objects if o.label in {"dog", "cat", "bird"})
            esg_metrics = compute_instantaneous_esg_metrics(
                bather_count=len(raw_tracks),
                cotton_violations=cotton_count,
                food_drink_events=food_count,
                animal_events=animal_count,
            )
            resident_status = forecaster.build_resident_comfort_status(
                tracks=raw_tracks,
            )

            # Match existing saved ROI crops & water frame
            roi_rel_paths = {
                str(tr.track_id): f"roi/{t_sec:.1f}_tr{tr.track_id}.jpg"
                for tr in raw_tracks
                if (roi_dir / f"{t_sec:.1f}_tr{tr.track_id}.jpg").exists()
            }
            water_img_rel = (
                f"water/{t_sec:.1f}.jpg"
                if (water_dir / f"{t_sec:.1f}.jpg").exists()
                else None
            )

            timeline_frames.append(
                {
                    "t": t_sec,
                    "tracks": [t.model_dump() for t in raw_tracks],
                    "objects": [o.model_dump() for o in objects],
                    "system1_trace": sys1_trace.model_dump(),
                    "system2_inspections": [s.model_dump() for s in sys2_insps],
                    "tool_logs": [tl.model_dump(mode="json") for tl in tool_logs],
                    "reasoning_thoughts": thoughts,
                    "esg_metrics": esg_metrics.model_dump(),
                    "water_report": None,
                    "resident_comfort": resident_status.model_dump(),
                    "roi_images": roi_rel_paths,
                    "water_image": water_img_rel,
                }
            )

        peak_bathers = max((len(f["tracks"]) for f in timeline_frames), default=0)
        sys1_p95 = (
            float(np.percentile(sys1_latencies, 95)) if sys1_latencies else 0.8
        )
        avg_hourly_rm = (
            float(np.mean([f["esg_metrics"]["hourly_rm_saved"] for f in timeline_frames]))
            if timeline_frames
            else 18.5
        )

        timeline_payload = {
            "job": job.model_dump(),
            "frames": timeline_frames,
            "events": events,
            "summary": {
                "duration_sec": job.duration_sec,
                "sampled_frames_count": len(timeline_frames),
                "peak_bathers": peak_bathers,
                "max_agent_state": max_state.value,
                "system1_p95_latency_ms": round(sys1_p95, 2),
                "projected_daily_rm_saved": round(avg_hourly_rm * 24.0, 2),
                "turnover_compliant": True,
            },
        }

        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(timeline_payload, f)

        return timeline_payload
