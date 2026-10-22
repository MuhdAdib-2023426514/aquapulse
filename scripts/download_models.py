"""Download pre-trained pose and object detection models into assets/models/."""

import shutil
from pathlib import Path

from ultralytics import YOLO

from aquapulse.config import (
    MODELS_DIR,
    YOLO26_DETECT_MODEL_NAME,
    YOLO26_POSE_MODEL_NAME,
)


def download_models() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    pose_target = MODELS_DIR / YOLO26_POSE_MODEL_NAME
    detect_target = MODELS_DIR / YOLO26_DETECT_MODEL_NAME

    print(f"Downloading pose model -> {pose_target}")
    if not pose_target.exists():
        # yolo11n-pose.pt is Ultralytics latest NMS-free edge pose architecture
        model = YOLO("yolo11n-pose.pt")
        weights_src = Path(model.ckpt_path) if hasattr(model, "ckpt_path") and model.ckpt_path else Path("yolo11n-pose.pt")
        if weights_src.exists() and weights_src != pose_target:
            shutil.copy(weights_src, pose_target)
    print(f"Pose model ready: {pose_target.exists()} ({pose_target})")

    print(f"Downloading object detection model -> {detect_target}")
    if not detect_target.exists():
        model = YOLO("yolo11n.pt")
        weights_src = Path(model.ckpt_path) if hasattr(model, "ckpt_path") and model.ckpt_path else Path("yolo11n.pt")
        if weights_src.exists() and weights_src != detect_target:
            shutil.copy(weights_src, detect_target)
    print(f"Detect model ready: {detect_target.exists()} ({detect_target})")


if __name__ == "__main__":
    download_models()
