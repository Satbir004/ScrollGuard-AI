"""
Loads detection-related settings from config.json.
Single source of truth for all threshold values used by the AI engine.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass
class DetectionConfig:
    # YOLO
    yolo_model: str = "yolov8n.pt"
    confidence_threshold: float = 0.5
    phone_class_id: int = 67           # COCO class for "cell phone"
    yolo_inference_interval: int = 5   # run YOLO every Nth frame

    # Tracker
    tracker_iou_threshold: float = 0.3
    tracker_max_missed_frames: int = 15  # drop track after N frames without YOLO match

    # Inference device
    device: str = "auto"  # "auto" | "cpu" | "cuda"

        # State machine (Phase 6)
    phone_visible_min_seconds: float = 1.0
    desk_still_max_px_per_frame: float = 5.0
    hand_proximity_threshold: float = 0.6
    pickup_proximity_threshold: float = 0.4
    pickup_movement_px_per_frame: float = 15.0
    possible_use_min_seconds: float = 1.5
    confirm_distraction_min_seconds: float = 2.5
    phone_absent_reset_seconds: float = 3.0
    release_proximity_threshold: float = 0.3
    release_min_seconds: float = 1.0

    @classmethod
    def from_file(cls, path: Optional[Path | str] = None) -> "DetectionConfig":
        cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not cfg_path.exists():
            logger.warning(
                "Config file not found at %s; using defaults.", cfg_path
            )
            return cls()

        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            logger.error("Failed to parse config.json: %s. Using defaults.", e)
            return cls()

        d = raw.get("detection", {})
        sm = raw.get("state_machine", {})
        return cls(
            yolo_model=d.get("yolo_model", "yolov8n.pt"),
            confidence_threshold=float(d.get("confidence_threshold", 0.5)),
            phone_class_id=int(d.get("phone_class_id", 67)),
            yolo_inference_interval=int(d.get("yolo_inference_interval", 5)),
            tracker_iou_threshold=float(d.get("tracker_iou_threshold", 0.3)),
            tracker_max_missed_frames=int(d.get("tracker_max_missed_frames", 6)),
            device=str(d.get("device", "auto")),
            phone_visible_min_seconds=float(sm.get("phone_visible_min_seconds", 1.0)),
            desk_still_max_px_per_frame=float(sm.get("desk_still_max_px_per_frame", 5.0)),
            hand_proximity_threshold=float(sm.get("hand_proximity_threshold", 0.6)),
            pickup_proximity_threshold=float(sm.get("pickup_proximity_threshold", 0.4)),
            pickup_movement_px_per_frame=float(sm.get("pickup_movement_px_per_frame", 15.0)),
            possible_use_min_seconds=float(sm.get("possible_use_min_seconds", 1.5)),
            confirm_distraction_min_seconds=float(sm.get("confirm_distraction_min_seconds", 2.5)),
            phone_absent_reset_seconds=float(sm.get("phone_absent_reset_seconds", 3.0)),
            release_proximity_threshold=float(sm.get("release_proximity_threshold", 0.3)),
            release_min_seconds=float(sm.get("release_min_seconds", 1.0)),
        )
            