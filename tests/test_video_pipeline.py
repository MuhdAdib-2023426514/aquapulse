"""Integration tests for VideoPipeline processing and re-evaluation."""

from pathlib import Path

import cv2
import numpy as np

from aquapulse.schemas import SwimmerRole
from aquapulse.video.pipeline import VideoJob, VideoPipeline


def test_video_pipeline_end_to_end(tmp_path: Path):
    # 1. Create a synthetic 1-second video (10 frames at 10 fps)
    video_path = tmp_path / "test_clip.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (640, 360))
    for _ in range(10):
        frame = np.full((360, 640, 3), 120, dtype=np.uint8)
        # Draw pool blue basin
        cv2.rectangle(frame, (40, 60), (600, 300), (200, 150, 50), -1)
        out.write(frame)
    out.release()

    pipeline = VideoPipeline()
    job = VideoJob(
        filename="test_clip.mp4",
        raw_filepath=str(video_path),
        sample_fps=5.0,
        time_scale=2.0,
    )

    # 2. Extract preview
    preview = pipeline.extract_preview(job)
    assert Path(preview).exists()
    assert job.width == 640
    assert job.height == 360

    # 3. Process video
    result = pipeline.process(job)
    assert job.status == "completed"
    assert "frames" in result
    assert "events" in result
    assert "summary" in result
    assert len(result["frames"]) > 0

    # 4. Fast-path reevaluate with role override
    job.role_overrides = {101: SwimmerRole.TODDLER}
    re_result = pipeline.reevaluate(job)
    assert "frames" in re_result
    assert "summary" in re_result
