"""
Full pipeline:
  mirror → YOLO (every Nth frame) → tracker → MediaPipe hands → proximity
       → DistractionAnalyzer → state → annotate
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

import cv2
import numpy as np

from ai_engine.detection_config import DetectionConfig
from ai_engine.detector import PhoneDetector
from ai_engine.distraction_analyzer import (
    AnalyzerCallbacks,
    AnalyzerInput,
    DistractionAnalyzer,
    DistractionState,
)
from ai_engine.frame_annotator import draw_hands, draw_state_badge, draw_tracks
from ai_engine.hand_detector import HandDetector, HandInfo
from ai_engine.phone_tracker import PhoneTracker
from ai_engine.proximity import hand_phone_proximity

logger = logging.getLogger(__name__)


@dataclass
class FrameMetadata:
    fps: float = 0.0
    frame_index: int = 0
    timestamp: float = 0.0
    width: int = 0
    height: int = 0
    phone_visible: bool = False
    phone_confidence: float = 0.0
    yolo_ran_this_frame: bool = False
    hands_visible: int = 0
    proximity: float = 0.0
    hand_open_palm: bool = False
    state: str = "NO_PHONE"


@dataclass
class ProcessedFrame:
    image: np.ndarray
    metadata: FrameMetadata
    tracks: list = field(default_factory=list)
    hands: list = field(default_factory=list)


class FrameProcessor:
    def __init__(
        self,
        config: Optional[DetectionConfig] = None,
        mirror: bool = True,
        enable_detection: bool = True,
        enable_hands: bool = True,
        analyzer_callbacks: Optional[AnalyzerCallbacks] = None,
    ):
        self.config = config or DetectionConfig.from_file()
        self.mirror = mirror
        self.enable_detection = enable_detection
        self.enable_hands = enable_hands

        self.detector = PhoneDetector(self.config)
        self.tracker = PhoneTracker(
            iou_threshold=self.config.tracker_iou_threshold,
            max_missed_frames=self.config.tracker_max_missed_frames,
        )
        self.hand_detector = HandDetector(
            max_num_hands=2,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.5,
            model_complexity=0,
        )
        self.analyzer = DistractionAnalyzer(
            config=self.config, callbacks=analyzer_callbacks,
        )

        self._frame_index = 0
        self._last_tick: Optional[float] = None
        self._fps_ema = 0.0
        self._model_loaded = False
        self._hands_loaded = False

    def _ensure_models(self) -> None:
        if self.enable_detection and not self._model_loaded:
            try:
                self.detector.load()
                self._model_loaded = True
            except Exception as e:
                logger.exception("YOLO failed to load: %s", e)
                self.enable_detection = False
        if self.enable_hands and not self._hands_loaded:
            try:
                self.hand_detector.load()
                self._hands_loaded = True
            except Exception as e:
                logger.exception("Hands failed to load: %s", e)
                self.enable_hands = False

    def process(self, raw_frame: np.ndarray) -> ProcessedFrame:
        now = time.perf_counter()
        if self._last_tick is not None:
            dt = now - self._last_tick
            if dt > 0:
                self._fps_ema = 0.9 * self._fps_ema + 0.1 * (1.0 / dt)
        self._last_tick = now

        frame = cv2.flip(raw_frame, 1) if self.mirror else raw_frame
        self._ensure_models()

        # YOLO
        ran_yolo = False
        if self.enable_detection and self._model_loaded:
            if self._frame_index % max(1, self.config.yolo_inference_interval) == 0:
                try:
                    self.tracker.update(self.detector.detect(frame))
                    ran_yolo = True
                except Exception:
                    logger.exception("YOLO detect failed")
            else:
                self.tracker.tick()

        tracks = self.tracker.active_tracks()
        best = self.tracker.best_track()
        phone_det = best.detection if best else None
        phone_visible = phone_det is not None
        phone_conf = phone_det.confidence if phone_det else 0.0
        phone_center = phone_det.center if phone_det else None

        # Hands
        hands: List[HandInfo] = []
        if self.enable_hands and self._hands_loaded:
            try:
                hands = self.hand_detector.detect(frame)
            except Exception:
                logger.exception("Hand detect failed")

        h, w = frame.shape[:2]
        prox = hand_phone_proximity(hands, phone_det, w, h)
        hand_open = any(hnd.is_open_palm() for hnd in hands)

        # State machine
        analyzer_out = self.analyzer.process(AnalyzerInput(
            timestamp=now,
            phone_visible=phone_visible,
            phone_confidence=phone_conf,
            phone_center=phone_center,
            proximity=prox,
            hands_visible=len(hands),
        ))

        # Annotate
        annotated = frame
        if tracks:
            annotated = draw_tracks(annotated, tracks)
        if hands:
            annotated = draw_hands(
                annotated, hands, w, h,
                phone_detection=phone_det, proximity=prox,
            )

        # State badge bottom-left
        from ai_engine.distraction_analyzer import STATE_COLORS
        badge_color = STATE_COLORS.get(analyzer_out.state, (200, 200, 200))
        draw_state_badge(
            annotated, analyzer_out.state.value, badge_color, 20, h - 20,
        )

        meta = FrameMetadata(
            fps=self._fps_ema, frame_index=self._frame_index,
            timestamp=now, width=w, height=h,
            phone_visible=phone_visible, phone_confidence=phone_conf,
            yolo_ran_this_frame=ran_yolo,
            hands_visible=len(hands), proximity=prox,
            hand_open_palm=hand_open,
            state=analyzer_out.state.value,
        )
        self._frame_index += 1
        return ProcessedFrame(
            image=annotated, metadata=meta, tracks=tracks, hands=hands,
        )

    def draw_hud(self, frame: np.ndarray, meta: FrameMetadata) -> np.ndarray:
        out = frame.copy()
        top = f"FPS {meta.fps:4.1f}  |  {meta.width}x{meta.height}"
        cv2.putText(out, top, (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, top, (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 1, cv2.LINE_AA)

        if meta.phone_visible:
            phone_txt = f"PHONE {meta.phone_confidence * 100:.0f}%"
            phone_color = (0, 220, 255)
        else:
            phone_txt = "NO PHONE"
            phone_color = (150, 150, 150)

        prox_txt = f"Prox {meta.proximity:.2f}"
        if meta.proximity > 0.6:
            prox_color = (0, 100, 255)
        elif meta.proximity > 0.3:
            prox_color = (0, 200, 255)
        else:
            prox_color = (200, 200, 200)

        lines = [
            (phone_txt, phone_color),
            (f"Hands {meta.hands_visible}", (200, 200, 200)),
            (prox_txt, prox_color),
        ]
        y = 28
        for text, color in lines:
            (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
            x = meta.width - tw - 20
            cv2.putText(out, text, (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(out, text, (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 1, cv2.LINE_AA)
            y += 30
        return out