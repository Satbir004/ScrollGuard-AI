"""
MediaPipe Hands wrapper.

Runs hand landmark detection on every frame and returns typed HandInfo
objects. Used by proximity.py and the state machine in Phase 6.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HandInfo:
    """One detected hand with 21 landmarks."""
    # Landmarks in normalized coordinates (0.0–1.0) relative to frame size
    landmarks: List[tuple[float, float, float]] = field(default_factory=list)
    # Bounding box of the hand in pixel coordinates
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    # MediaPipe handedness ("Left" or "Right")
    handedness: str = "Unknown"
    # Handedness confidence
    handedness_score: float = 0.0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def pixel_landmarks(self) -> List[tuple[int, int]]:
        """Landmarks in pixel coords — requires frame size to be known."""
        # MediaPipe returns normalized coords; we convert in hand_detector
        return [(int(x), int(y)) for x, y, _ in self.landmarks]  # type: ignore

    def is_open_palm(self, min_visible_landmarks: int = 15) -> bool:
        """
        Rough heuristic: open palm has most landmarks spread out.
        Returns True if at least min_visible_landmarks are non-zero
        AND the bounding box is reasonably large (spread fingers).
        """
        visible = [lm for lm in self.landmarks if lm[0] > 0 or lm[1] > 0]
        if len(visible) < min_visible_landmarks:
            return False
        w = self.x2 - self.x1
        h = self.y2 - self.y1
        return (w * h) > 0


class HandDetector:
    """Wraps MediaPipe Hands. One instance per frame processor."""

    def __init__(
        self,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 0,  # 0 = fastest
    ):
        self.max_num_hands = max_num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity
        self._hands = None

    def load(self) -> None:
        """Initialize MediaPipe Hands. Idempotent."""
        if self._hands is not None:
            return

        import mediapipe as mp

        self._mp_hands = mp.solutions.hands
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=self.max_num_hands,
            model_complexity=self.model_complexity,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
        )
        logger.info(
            "MediaPipe Hands ready (max_hands=%d, complexity=%d)",
            self.max_num_hands, self.model_complexity,
        )

    @property
    def is_loaded(self) -> bool:
        return self._hands is not None

    def detect(self, frame_bgr: np.ndarray) -> List[HandInfo]:
        """
        Run hand detection on a BGR frame. Returns typed HandInfo list.
        Frame must be contiguous (cv2 frames are).
        """
        if self._hands is None:
            raise RuntimeError("HandDetector.load() must be called before detect().")

        # MediaPipe requires RGB
        frame_rgb = frame_bgr[:, :, ::-1]
        frame_rgb = np.ascontiguousarray(frame_rgb)
        h, w = frame_bgr.shape[:2]

        results = self._hands.process(frame_rgb)

        hands: List[HandInfo] = []
        if not results.multi_hand_landmarks:
            return hands

        handedness_list = results.multi_handedness or []

        for i, hand_lm in enumerate(results.multi_hand_landmarks):
            pts_norm: List[tuple[float, float, float]] = []
            xs: List[float] = []
            ys: List[float] = []
            for lm in hand_lm.landmark:
                pts_norm.append((lm.x, lm.y, lm.z))
                xs.append(lm.x * w)
                ys.append(lm.y * h)

            x1 = int(max(0, min(xs)))
            y1 = int(max(0, min(ys)))
            x2 = int(min(w - 1, max(xs)))
            y2 = int(min(h - 1, max(ys)))

            handedness = "Unknown"
            score = 0.0
            if i < len(handedness_list):
                cls = handedness_list[i].classification[0]
                handedness = cls.label
                score = float(cls.score)

            hands.append(HandInfo(
                landmarks=pts_norm,
                x1=x1, y1=y1, x2=x2, y2=y2,
                handedness=handedness,
                handedness_score=score,
            ))

        return hands

    def close(self) -> None:
        if self._hands is not None:
            self._hands.close()
            self._hands = None