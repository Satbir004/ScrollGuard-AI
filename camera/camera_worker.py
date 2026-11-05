"""
CameraWorker — a QThread that reads frames from the webcam, processes them,
and emits them via Qt signals. The GUI thread never blocks on camera I/O.

Emits:
    frame_ready(ProcessedFrame)  — every successful frame
    error_occurred(str)          — on camera failure
    started_ok(dict)             — when the camera is ready (resolution, fps)
    stopped()                    — when the worker exits cleanly
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QThread, Signal

from .frame_processor import FrameProcessor, ProcessedFrame
from .webcam import Webcam, WebcamError

logger = logging.getLogger(__name__)


class CameraWorker(QThread):
    frame_ready = Signal(object)       # ProcessedFrame
    error_occurred = Signal(str)
    started_ok = Signal(dict)
    stopped = Signal()

    def __init__(
        self,
        index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        target_loop_fps: int = 30,
        parent=None,
    ):
        super().__init__(parent)
        self.camera = Webcam(index=index, width=width, height=height, fps=fps)
        self.processor = FrameProcessor(mirror=True)
        self.target_loop_fps = target_loop_fps
        self._running = False
        self._paused = False

    # ---- Public controls (safe to call from GUI thread) ----

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._running = False

    # ---- QThread entry point ----

    def run(self) -> None:
        try:
            self.camera.open()
        except WebcamError as e:
            logger.error("Camera open failed: %s", e)
            self.error_occurred.emit(str(e))
            return

        self._running = True
        self.started_ok.emit({
            "width": self.camera.actual_width,
            "height": self.camera.actual_height,
            "fps": self.camera.actual_fps,
        })

        frame_interval = 1.0 / self.target_loop_fps if self.target_loop_fps > 0 else 0.0
        next_tick = time.perf_counter()

        try:
            while self._running:
                if self._paused:
                    time.sleep(0.05)
                    continue

                try:
                    raw = self.camera.read()
                except WebcamError as e:
                    logger.warning("Frame read failed: %s", e)
                    time.sleep(0.1)
                    continue

                processed = self.processor.process(raw)
                self.frame_ready.emit(processed)

                # Throttle to target FPS
                if frame_interval > 0:
                    next_tick += frame_interval
                    sleep_for = next_tick - time.perf_counter()
                    if sleep_for > 0:
                        time.sleep(sleep_for)
                    else:
                        # Falling behind — reset baseline
                        next_tick = time.perf_counter()

        finally:
            self.camera.release()
            self.stopped.emit()
            logger.info("CameraWorker stopped.")