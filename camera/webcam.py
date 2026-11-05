"""
Thin wrapper around cv2.VideoCapture with explicit open/close lifecycle.

No threading here — CameraWorker owns the thread. This class is a
testable, side-effect-free abstraction over the raw camera.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class WebcamError(RuntimeError):
    """Raised when the camera cannot be opened or read."""


class Webcam:
    def __init__(
        self,
        index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ):
        self.index = index
        self.requested_width = width
        self.requested_height = height
        self.requested_fps = fps
        self._cap: Optional[cv2.VideoCapture] = None

        # Actual values after opening — may differ from requested
        self.actual_width = 0
        self.actual_height = 0
        self.actual_fps = 0.0

    def open(self) -> None:
        """Open the camera. Raise WebcamError on failure."""
        if self._cap is not None and self._cap.isOpened():
            return

        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)  # DSHOW = fast on Windows
        if not cap.isOpened():
            # Fallback: try without DSHOW (some webcams dislike it)
            cap = cv2.VideoCapture(self.index)

        if not cap.isOpened():
            raise WebcamError(
                f"Cannot open camera index {self.index}. "
                f"Is another app using it? Try index 1 in config."
            )

        # Apply requested settings (webcam may ignore these)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.requested_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.requested_height)
        cap.set(cv2.CAP_PROP_FPS, self.requested_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency

        # Read actual values
        self.actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.actual_fps = cap.get(cv2.CAP_PROP_FPS)

        self._cap = cap
        logger.info(
            "Camera %d opened: %dx%d @ %.1f FPS",
            self.index, self.actual_width, self.actual_height, self.actual_fps,
        )

    def read(self) -> np.ndarray:
        """Read one frame. Raise WebcamError if the frame is empty."""
        if self._cap is None or not self._cap.isOpened():
            raise WebcamError("Camera is not open. Call open() first.")

        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise WebcamError("Camera returned an empty frame.")
        return frame

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera %d released.", self.index)

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def resolution(self) -> Tuple[int, int]:
        return (self.actual_width, self.actual_height)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()