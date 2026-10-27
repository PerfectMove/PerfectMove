"""Pose extraction from video using MediaPipe Pose Landmarker.

The analysis code only depends on `PoseSequence`, so it can be tested with
synthetic keypoints and MediaPipe is imported lazily.
"""

from __future__ import annotations

import logging
import urllib.request
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)


class LM(IntEnum):
    """MediaPipe Pose landmark indices used by the analyzers."""

    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


NUM_LANDMARKS = 33


@dataclass
class PoseSequence:
    """Keypoints for a video.

    `landmarks` has shape (frames, 33, 3): x and y in pixels (y grows downward)
    and a visibility score in [0, 1]. Frames where no person was found are NaN.
    """

    times: np.ndarray
    landmarks: np.ndarray
    width: int
    height: int
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.landmarks.ndim != 3 or self.landmarks.shape[1:] != (NUM_LANDMARKS, 3):
            raise ValueError(f"landmarks must be (frames, 33, 3), got {self.landmarks.shape}")
        if len(self.times) != len(self.landmarks):
            raise ValueError("times and landmarks length differ")

    def __len__(self) -> int:
        return len(self.times)

    def point(self, lm: LM) -> np.ndarray:
        """(frames, 2) pixel coordinates of one landmark."""
        return self.landmarks[:, lm, :2]

    def visibility(self, lm: LM) -> np.ndarray:
        return self.landmarks[:, lm, 2]


def ensure_model(model_path: Path) -> Path:
    if model_path.exists():
        return model_path
    model_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading pose model to %s", model_path)
    tmp = model_path.with_suffix(".part")
    urllib.request.urlretrieve(MODEL_URL, tmp)
    tmp.rename(model_path)
    return model_path


def extract_pose(video_path: Path, model_path: Path, sample_fps: float = 15.0) -> PoseSequence:
    """Run MediaPipe Pose on a video, sampling at most `sample_fps` frames per second."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Could not open the video file")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / sample_fps))

    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ensure_model(model_path))),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )

    times: list[float] = []
    frames: list[np.ndarray] = []
    width = height = 0
    index = 0
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                height, width = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                t = index / fps
                result = landmarker.detect_for_video(image, int(t * 1000))
                points = np.full((NUM_LANDMARKS, 3), np.nan)
                if result.pose_landmarks:
                    for i, lm in enumerate(result.pose_landmarks[0]):
                        points[i] = (lm.x * width, lm.y * height, lm.visibility or 0.0)
                times.append(t)
                frames.append(points)
            index += 1
    cap.release()

    if not frames:
        raise ValueError("The video has no readable frames")

    return PoseSequence(
        times=np.array(times),
        landmarks=np.stack(frames),
        width=width,
        height=height,
        meta={"source_fps": fps, "sample_step": step},
    )
