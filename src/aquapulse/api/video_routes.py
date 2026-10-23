"""FastAPI REST routes for video ingestion, calibration, background processing, and media streaming."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from aquapulse.agent.tools import synthesize_alert_wav
from aquapulse.config import MIN_DAILY_TURNOVERS, TNB_TARIFF_RM_PER_KWH
from aquapulse.schemas import SwimmerRole
from aquapulse.video.pipeline import UPLOADS_DIR, VideoJob, VideoPipeline
from aquapulse.vision.calibration import PoolCalibration
from aquapulse.vision.detector import AquaPulseVisionDetector

router = APIRouter(prefix="/api/v1", tags=["video_processing"])

# In-memory registry of uploaded jobs (backed by assets/uploads/)
_JOBS: dict[str, VideoJob] = {}
_PIPELINE = VideoPipeline()
_THREAD_POOL = ThreadPoolExecutor(max_workers=2)


def _load_persisted_jobs() -> None:
    """Reload any previously completed video jobs from disk upon server boot."""
    if not UPLOADS_DIR.exists():
        return
    for job_dir in UPLOADS_DIR.iterdir():
        if job_dir.is_dir():
            job_file = job_dir / "job.json"
            if job_file.exists():
                try:
                    with open(job_file, encoding="utf-8") as f:
                        data = json.load(f)
                    job = VideoJob.model_validate(data)
                    _JOBS[job.id] = job
                except Exception:
                    pass


_load_persisted_jobs()


def _save_job_state(job: VideoJob) -> None:
    job_dir = VideoPipeline.get_job_dir(job.id)
    with open(job_dir / "job.json", "w", encoding="utf-8") as f:
        json.dump(job.model_dump(), f, indent=2)


class JobConfigUpdate(BaseModel):
    """Payload to update calibration, time scale, or role overrides before/after processing."""

    calibration: PoolCalibration | None = None
    sample_fps: float | None = Field(default=None, ge=1.0, le=30.0)
    time_scale: float | None = Field(default=None, ge=0.25, le=5.0)
    role_overrides: dict[int, SwimmerRole] | None = None


@router.post("/videos", response_model=VideoJob)
async def upload_video(file: UploadFile = File(...)) -> VideoJob:  # noqa: B008
    """Upload a raw pool video clip, save securely, and generate a Tier-1 face-masked preview."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Please upload MP4, MOV, AVI, or MKV.",
        )

    job = VideoJob(filename=file.filename, raw_filepath="")
    job_dir = VideoPipeline.get_job_dir(job.id)
    raw_path = job_dir / f"raw{ext}"
    job.raw_filepath = str(raw_path)

    # Stream file to disk
    with open(raw_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    try:
        # Extract initial frame, dimensions, and face-masked preview.jpg
        _PIPELINE.extract_preview(job)
    except Exception as e:
        job.status = "failed"
        job.error = f"Failed to probe video: {e}"

    _JOBS[job.id] = job
    _save_job_state(job)
    return job


@router.get("/videos", response_model=list[VideoJob])
def list_videos() -> list[VideoJob]:
    """List all available uploaded video jobs."""
    return sorted(list(_JOBS.values()), key=lambda j: j.created_at, reverse=True)


@router.get("/videos/{job_id}", response_model=VideoJob)
def get_video_job(job_id: str) -> VideoJob:
    """Get current status and processing progress of a video job."""
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found.")
    return job


@router.put("/videos/{job_id}/config", response_model=VideoJob)
def update_job_config(job_id: str, cfg: JobConfigUpdate) -> VideoJob:
    """Update calibration polygon, pitch time scale, or role overrides for a video."""
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found.")

    if cfg.calibration is not None:
        job.calibration = cfg.calibration
    if cfg.sample_fps is not None:
        job.sample_fps = cfg.sample_fps
    if cfg.time_scale is not None:
        job.time_scale = cfg.time_scale
    if cfg.role_overrides is not None:
        job.role_overrides = cfg.role_overrides

    _save_job_state(job)
    return job


@router.post("/videos/{job_id}/process")
async def start_video_processing(
    job_id: str, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Launch full YOLO tracking, System 1/2 state machine, and artifact generation."""
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found.")

    if job.status == "processing":
        return {"status": "processing", "message": "Job is already running."}

    def _run_worker(target_job: VideoJob) -> None:
        _PIPELINE.process(target_job)
        _save_job_state(target_job)

    # Run in background thread pool so event loop remains responsive
    background_tasks.add_task(asyncio.to_thread, _run_worker, job)
    job.status = "processing"
    job.progress = 0.05
    job.current_stage = "Scheduled for background processing"
    _save_job_state(job)
    return {"status": "processing", "job_id": job.id}


@router.post("/videos/{job_id}/reevaluate")
def reevaluate_video(job_id: str) -> dict[str, Any]:
    """Fast-path re-evaluation (<1s): reruns state machine & ESG over cached perception."""
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found.")

    try:
        timeline = _PIPELINE.reevaluate(job)
        _save_job_state(job)
        return timeline
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/videos/{job_id}/timeline")
def get_video_timeline(job_id: str, response: Response) -> dict[str, Any]:
    """Fetch complete playhead-synced telemetry, events, and metrics."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found.")

    job_dir = VideoPipeline.get_job_dir(job.id)
    timeline_path = job_dir / "timeline.json"
    if not timeline_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Timeline not yet ready. Please run /process on this video first.",
        )

    with open(timeline_path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/videos/{job_id}/media/{file_path:path}")
def get_video_media(job_id: str, file_path: str) -> Response:
    """Safely stream Tier-1 masked MP4, preview, ROI crops, and water frames.

    PDPA Protection: Any attempt to access raw video ('raw.*') is strictly forbidden.
    """
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found.")

    # Prevent path traversal or raw video exposure
    clean_path = Path(file_path).name if "/" not in file_path else file_path
    if ".." in clean_path or clean_path.startswith("raw"):
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: raw unredacted pool footage cannot be served.",
        )

    job_dir = VideoPipeline.get_job_dir(job.id)
    target = (job_dir / clean_path).resolve()

    if not str(target).startswith(str(job_dir.resolve())) or not target.exists():
        raise HTTPException(status_code=404, detail="Media file not found.")

    media_type = "video/mp4" if target.suffix == ".mp4" else "image/jpeg"
    return FileResponse(path=str(target), media_type=media_type)


@router.delete("/videos/{job_id}")
def delete_video_job(job_id: str) -> dict[str, Any]:
    """Delete uploaded video and all associated artifacts."""
    _JOBS.pop(job_id, None)
    job_dir = UPLOADS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    return {"status": "deleted", "job_id": job_id}


@router.get("/audio/{kind}.wav")
def get_alert_audio(kind: str) -> Response:
    """Synthesize and stream alert audio WAV (critical_siren, verify_beacon, polite_nudge)."""
    valid_kinds = {"critical_siren", "verify_beacon", "polite_nudge"}
    if kind not in valid_kinds:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audio kind '{kind}'. Must be one of {valid_kinds}.",
        )

    wav_bytes = synthesize_alert_wav(kind)
    return Response(content=wav_bytes, media_type="audio/wav")


@router.get("/system/capabilities")
def get_system_capabilities() -> dict[str, Any]:
    """Return backend capabilities, weights status, and environmental parameters."""
    detector = AquaPulseVisionDetector()
    return {
        "yolo26_pose_available": detector.yolo26_weights_available,
        "gemini_api_configured": bool(os.getenv("GEMINI_API_KEY")),
        "audio_synthesis_available": True,
        "minimum_daily_turnover_floor": MIN_DAILY_TURNOVERS,
        "tnb_tariff_rm_kwh": TNB_TARIFF_RM_PER_KWH,
        "pdpa_silhouettes_supported": True,
    }
