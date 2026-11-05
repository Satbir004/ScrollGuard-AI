"""
Standalone Phase 5 preview: phone + hands + proximity.

Run:
    python scripts\test_hands.py

Try these to see the proximity value change:
  1. Empty hands, phone on desk       → Prox 0.0
  2. Hand near desk, phone on desk    → Prox 0.1-0.3
  3. Hand approaching phone           → Prox 0.4-0.6 (yellow)
  4. Hand touching phone              → Prox 0.7-0.95 (orange)
  5. Phone in hand, scrolling         → Prox 0.8+  (red/orange)
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


class HandsPreviewWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScrollGuard AI — Phase 5: Hands + Proximity")
        self.resize(1100, 820)

        self.video_label = QLabel("Starting...", self)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background: #000; color: #F8FAFC;")

        self.status_label = QLabel("Loading models...", self)
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

        self._last = None

    def on_frame(self, processed) -> None:
        img = processed.image
        meta = processed.metadata

        from camera.frame_processor import FrameProcessor
        hud = FrameProcessor(enable_detection=False, enable_hands=False).draw_hud(img, meta)

        h, w, ch = hud.shape
        qimg = QImage(hud.data, w, h, ch * w, QImage.Format.Format_BGR888)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))
        self._last = meta

    def on_started(self, info: dict) -> None:
        self.status_label.setText(
            f"Camera {info['width']}x{info['height']} — warming up..."
        )

    def on_error(self, msg: str) -> None:
        self.video_label.setText(f"Error:\n{msg}")
        self.status_label.setText("Status: error")

    def on_stopped(self) -> None:
        self.status_label.setText("Status: stopped")

    def _update_status(self) -> None:
        m = self._last
        if m is None:
            return
        phone = f"PHONE {m.phone_confidence * 100:.0f}%" if m.phone_visible else "NO PHONE"
        self.status_label.setText(
            f"FPS {m.fps:.1f}  |  {phone}  |  "
            f"Hands {m.hands_visible}  |  Proximity {m.proximity:.2f}"
        )

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    w = HandsPreviewWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()