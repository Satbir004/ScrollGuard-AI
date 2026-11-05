"""
YOLO detector wrapper. Loads the model once; run() is called per-inference-frame.

Returns a typed list of Detection objects for the phone class only.
Everything else YOLO detects is filtered out — we don't care about chairs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .detection_config import DetectionConfig

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """One detected phone in a single frame."""
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    class_id: int = 67
    class_name: str = "cell phone"

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def area(self) -> int:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)

    @property
    def diagonal(self) -> float:
        w = self.x2 - self.x1
        h = self.y2 - self.y1
        return float((w * w + h * h) ** 0.5)


class PhoneDetector:
    """
    Wraps a YOLOv8 model. Lazy-loads the model on first use so that
    import-time is cheap (important for PyInstaller startup).
    """

    def __init__(self, config: Optional[DetectionConfig] = None):
        self.config = config or DetectionConfig.from_file()
        self._model = None
        self._device = "cpu"

    def _resolve_device(self) -> str:
        if self.config.device == "cpu":
            return "cpu"
        if self.config.device == "cuda":
            return "cuda"
        # auto
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def load(self) -> None:
        """Load the model. Logs device and model name. Raises on failure."""
        if self._model is not None:
            return

        from ultralytics import YOLO

        self._device = self._resolve_device()
        logger.info(
            "Loading YOLO model '%s' on %s...",
            self.config.yolo_model, self._device,
        )
        self._model = YOLO(self.config.yolo_model)
        # Move the underlying torch model once
        try:
            self._model.to(self._device)
        except Exception as e:
            logger.warning("Could not move model to %s (%s); using CPU.",
                           self._device, e)
            self._device = "cpu"
        logger.info("YOLO model ready.")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference on one BGR frame. Returns phone detections only.
        """
        if self._model is None:
            raise RuntimeError("PhoneDetector.load() must be called before detect().")

        results = self._model(
            frame,
            conf=self.config.confidence_threshold,
            verbose=False,
            device=self._device,
        )

        phones: List[Detection] = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0].item())
                if cls_id != self.config.phone_class_id:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0].item())
                phones.append(Detection(
                    x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2),
                    confidence=conf, class_id=cls_id,
                ))

        # Sort by confidence desc — trackers prefer the strongest first
        phones.sort(key=lambda d: d.confidence, reverse=True)
        return phones