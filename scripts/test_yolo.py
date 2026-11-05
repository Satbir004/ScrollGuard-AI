"""
Standalone YOLO preview. Run:

    python scripts\test_yolo.py

Hold your phone up to the camera. You should see:
  - a cyan bounding box with confidence %
  - the "PHONE" label in the top-right

Watch the FPS in the top-left. It should stay above ~15 even with YOLO
running on CPU because inference runs every 5th frame.
"""

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from camera.camera_worker import CameraWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class YoloPreviewWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScrollGuard AI — YOLO Preview (Phase 4)")
        self.resize(1000, 760)

        self.video_label = QLabel("Starting camera + YOLO...", self)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background: #000; color: #F8FAFC;")

        self.status_label = QLabel("Loading YOLO...", self)
        self.status_label.setStyleSheet(
            "background: #111827; color: #94A3B8; padding: 6px; font: 12pt;"
        )

        layout = QVBoxLayout()
        layout.addWidget(self.video_label, stretch=1)
        layout.addWidget(self.status_label)
        c = QWidget()
        c.setLayout(layout)
        self.setCentralWidget(c)

        self.worker = CameraWorker(index=0, width=1280, height=720, fps=30)
        self.worker.frame_ready.connect(self.on_frame)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.started_ok.connect(self.on_started)
        self.worker.stopped.connect(self.on_stopped)
        self.worker.start()

        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self._update_status)
        self.fps_timer.start(250)

        self._last_fps = 0.0
        self._last_phone = False
        self._last_conf = 0.0

    def on_frame(self, processed) -> None:
        img = processed.image
        meta = processed.metadata

        from camera.frame_processor import FrameProcessor
        hud = FrameProcessor(enable_detection=False).draw_hud(img, meta)

        h, w, ch = hud.shape
        qimg = QImage(hud.data, w, h, ch * w, QImage.Format.Format_BGR888)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))

        self._last_fps = meta.fps
        self._last_phone = meta.phone_visible
        self._last_conf = meta.phone_confidence

    def on_started(self, info: dict) -> None:
        self.status_label.setText(
            f"Camera {info['width']}x{info['height']} "
            f"@ {info['fps']:.0f} FPS  |  YOLO loading..."
        )

    def on_error(self, msg: str) -> None:
        self.video_label.setText(f"Error:\n{msg}")
        self.status_label.setText("Status: error")

    def on_stopped(self) -> None:
        self.status_label.setText("Status: stopped")

    def _update_status(self) -> None:
        if self._last_fps <= 0:
            return
        phone = (
            f"PHONE {self._last_conf * 100:.0f}%"
            if self._last_phone else "NO PHONE"
        )
        self.status_label.setText(
            f"FPS {self._last_fps:.1f}  |  {phone}  |  "
            f"YOLO every 5 frames"
        )

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    w = YoloPreviewWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()