"""
Phase 6 end-to-end test:

  Hold your phone up like you're scrolling.
  After ~2.5 seconds → 🔊 ALARM.
  Put it down → alarm stops in ~1 second.
  Then check the DB — the event should be recorded.

Run:
    python scripts/test_alarm.py
"""

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from ai_engine.distraction_analyzer import AnalyzerCallbacks
from ai_engine.detection_config import DetectionConfig
from alerts.alert_manager import AlertManager
from camera.camera_worker import CameraWorker
from database.db import init_db
from database.repository import DistractionRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class AlarmTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScrollGuard AI — Phase 6: End-to-End Alarm Test")
        self.resize(1100, 820)

        self.video_label = QLabel("Starting...", self)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background: #000; color: #F8FAFC;")

        self.status_label = QLabel("Loading...", self)
        self.status_label.setStyleSheet(
            "background: #111827; color: #94A3B8; padding: 6px; font: 12pt;"
        )

        layout = QVBoxLayout()
        layout.addWidget(self.video_label, stretch=1)
        layout.addWidget(self.status_label)
        c = QWidget()
        c.setLayout(layout)
        self.setCentralWidget(c)

        # DB
        init_db()

        # Config
        import json
        cfg_raw = json.loads((PROJECT_ROOT / "config.json").read_text())
        alerts_cfg = cfg_raw.get("alerts", {})

        # Alert manager
        self.alerts = AlertManager(
            cooldown_seconds=alerts_cfg.get("cooldown_seconds", 30),
            volume=alerts_cfg.get("volume", 0.8),
            enable_sound=alerts_cfg.get("enable_sound", True),
            enable_voice=alerts_cfg.get("enable_voice", True),
        )
        self.alerts.init()

        # Callbacks — must hop onto Qt thread safely. Signals would be cleaner,
        # but for a test script logging + direct calls is fine.
        callbacks = AnalyzerCallbacks(
            on_distraction_start=lambda: self._on_start(),
            on_distraction_end=self._on_end,
        )

        # Camera worker — pass callbacks through FrameProcessor via config
        self.worker = CameraWorker(index=0, width=1280, height=720, fps=30)
        self.worker.frame_ready.connect(self.on_frame)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.started_ok.connect(self.on_started)
        self.worker.stopped.connect(self.on_stopped)

        # We need to inject callbacks — patch FrameProcessor via a small shim
        from camera.frame_processor import FrameProcessor
        from ai_engine.distraction_analyzer import DistractionAnalyzer
        self.worker.processor = FrameProcessor(
            config=DetectionConfig.from_file(),
            analyzer_callbacks=callbacks,
        )
        self.worker.start()

        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self._update_status)
        self.fps_timer.start(250)

        self._last = None

    def _on_start(self):
        self.alerts.on_distraction_started(confidence=0.8)

    def _on_end(self):
        self.alerts.on_distraction_ended()

    def on_frame(self, processed):
        img = processed.image
        meta = processed.metadata
        from camera.frame_processor import FrameProcessor
        hud = FrameProcessor(enable_detection=False, enable_hands=False).draw_hud(img, meta)
        h, w, ch = hud.shape
        qimg = QImage(hud.data, w, h, ch * w, QImage.Format.Format_BGR888)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))
        self._last = meta

    def on_started(self, info):
        self.status_label.setText(f"Camera {info['width']}x{info['height']} — loading models...")

    def on_error(self, msg):
        self.video_label.setText(f"Error:\n{msg}")
        self.status_label.setText("Status: error")

    def on_stopped(self):
        self.status_label.setText("Status: stopped")

    def _update_status(self):
        m = self._last
        if m is None:
            return
        phone = f"PHONE {m.phone_confidence * 100:.0f}%" if m.phone_visible else "NO PHONE"
        self.status_label.setText(
            f"FPS {m.fps:.1f}  |  {phone}  |  "
            f"Prox {m.proximity:.2f}  |  "
            f"STATE: {m.state}"
        )

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait(2000)
        self.alerts.shutdown()
        # Print event summary
        events = DistractionRepository.list_recent(limit=5)
        print("\n" + "=" * 60)
        print(f"Distraction events in DB: {len(events)}")
        for e in events:
            print(f"  #{e.id}  started={e.started_at}  "
                  f"duration={e.duration_seconds}s  confidence={e.confidence:.2f}")
        print("=" * 60 + "\n")
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    w = AlarmTestWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()