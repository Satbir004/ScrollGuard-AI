"""
Live Monitoring page — embeds camera + AI pipeline + alarm into the dashboard.

Owns its own CameraWorker and AlertManager. Starts monitoring on page first-show,
stops on hide. Can be paused/resumed via controls or Ctrl+Shift+P.

Distraction events are written to the database via AlertManager; the page
shows a live counter for the current session.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSizePolicy, QSpacerItem,
)

from ai_engine.detection_config import DetectionConfig
from ai_engine.distraction_analyzer import AnalyzerCallbacks, DistractionState
from alerts.alert_manager import AlertManager
from camera.camera_worker import CameraWorker
from camera.frame_processor import FrameProcessor
from ui.components.section_header import SectionHeader
from ui.styles.theme import (
    ACCENT_PRIMARY, CARD_BG, DANGER, SUCCESS, TEXT_PRIMARY,
    TEXT_SECONDARY, WARNING,
)

logger = logging.getLogger(__name__)


# Map analyzer states to display colors
STATE_COLOR_MAP = {
    "NO_PHONE":              "#94A3B8",
    "PHONE_DETECTED":        "#06B6D4",
    "PHONE_ON_DESK":         "#22C55E",
    "HAND_APPROACHING":      "#F59E0B",
    "PHONE_PICKED_UP":       "#F97316",
    "POSSIBLE_PHONE_USE":    "#EF4444",
    "DISTRACTION_CONFIRMED": "#DC2626",
}


class StatusRow(QWidget):
    """One line: label on left, value on right."""
    def __init__(self, label: str, value: str = "—", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        self.label = QLabel(label)
        self.label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        self.value = QLabel(value)
        self.value.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
        )
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.value)

    def set(self, text: str, color: str | None = None) -> None:
        self.value.setText(text)
        if color:
            self.value.setStyleSheet(
                f"color: {color}; font-size: 12px; font-weight: 600;"
            )
        else:
            self.value.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
            )

class MonitoringPage(QWidget):
    # Emits when a distraction is confirmed (used by dashboard to refresh)
    distraction_recorded = Signal()
    # Emits when distraction starts / ends (used by FocusPage to auto-pause)
    distraction_started = Signal()
    distraction_ended = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: CameraWorker | None = None
        self._alerts: AlertManager | None = None
        self._paused = False
        self._session_distractions = 0
        self._current_event_active = False
        self._last_meta = None

        self._build_ui()

        # UI refresh timer (status labels, not frames — frames arrive via signal)
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_status)
        self._ui_timer.start(250)

    # ---- UI construction ----

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(20)

        # Header row
        header_row = QHBoxLayout()
        header_row.addWidget(SectionHeader(
            "Live Monitoring",
            "Real-time phone-use detection with on-device AI",
        ), stretch=1)

        self.active_indicator = QLabel("●  STARTING")
        self.active_indicator.setStyleSheet(
            f"color: {WARNING}; font-size: 13px; font-weight: 600; "
            f"padding: 6px 14px; background: {CARD_BG}; "
            f"border-radius: 12px;"
        )
        header_row.addWidget(self.active_indicator)
        outer.addLayout(header_row)

        # Main content: video (left) | controls (right)
        content_row = QHBoxLayout()
        content_row.setSpacing(20)

        # ---- Video panel ----
        video_panel = QFrame()
        video_panel.setObjectName("Card")
        video_layout = QVBoxLayout(video_panel)
        video_layout.setContentsMargins(12, 12, 12, 12)
        video_layout.setSpacing(8)

        self.video_label = QLabel("Initializing camera + AI models...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet(
            "background: #000; color: #F8FAFC; "
            "border-radius: 8px; font-size: 14px;"
        )
        self.video_label.setMinimumSize(640, 400)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        video_layout.addWidget(self.video_label, stretch=1)

        self.footer_label = QLabel("Initializing...")
        self.footer_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 11px; padding: 4px;"
        )
        video_layout.addWidget(self.footer_label)

        content_row.addWidget(video_panel, stretch=3)

        # ---- Control panel ----
        control_panel = QFrame()
        control_panel.setObjectName("Card")
        control_panel.setFixedWidth(300)
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(20, 20, 20, 20)
        control_layout.setSpacing(10)

        # Live status
        status_title = QLabel("Live Status")
        status_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 600;"
        )
        control_layout.addWidget(status_title)

        self.state_row = StatusRow("Current state", "NO_PHONE")
        self.phone_row = StatusRow("Phone", "—")
        self.hands_row = StatusRow("Hands detected", "0")
        self.proximity_row = StatusRow("Proximity", "0.00")
        self.fps_row = StatusRow("Preview FPS", "0.0")

        for row in (
            self.state_row, self.phone_row, self.hands_row,
            self.proximity_row, self.fps_row,
        ):
            control_layout.addWidget(row)

        control_layout.addSpacing(10)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {CARD_BG};")
        control_layout.addWidget(divider)
        control_layout.addSpacing(10)

        # Session stats
        session_title = QLabel("This Session")
        session_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 600;"
        )
        control_layout.addWidget(session_title)

        self.session_count_row = StatusRow("Distractions", "0")
        control_layout.addWidget(self.session_count_row)

        control_layout.addStretch()

        # Buttons
        self.pause_btn = QPushButton("⏸  Pause Monitoring")
        self.pause_btn.setObjectName("SecondaryButton")
        self.pause_btn.setMinimumHeight(38)
        self.pause_btn.clicked.connect(self._toggle_pause)
        control_layout.addWidget(self.pause_btn)

        self.test_alarm_btn = QPushButton("🔊  Test Alarm")
        self.test_alarm_btn.setObjectName("SecondaryButton")
        self.test_alarm_btn.setMinimumHeight(38)
        self.test_alarm_btn.clicked.connect(self._test_alarm)
        control_layout.addWidget(self.test_alarm_btn)

        content_row.addWidget(control_panel, stretch=0)
        outer.addLayout(content_row, stretch=1)

    # ---- Lifecycle ----

    def showEvent(self, event):
        super().showEvent(event)
        if self._worker is None:
            self._start_worker()

    def hideEvent(self, event):
        super().hideEvent(event)
        # Keep worker running when hidden — the whole point is background monitoring.
        # Stop only on explicit "stop" or app exit.

    def shutdown(self) -> None:
        """Called by main_window on app exit."""
        self._stop_worker()

    # ---- Worker control ----

    def _start_worker(self) -> None:
        logger.info("Starting monitoring worker")

        # Build alert manager
        import json
        from pathlib import Path
        PROJECT_ROOT = Path(__file__).parent.parent.parent
        try:
            cfg = json.loads((PROJECT_ROOT / "config.json").read_text())
        except Exception:
            cfg = {}
        alerts_cfg = cfg.get("alerts", {})

        self._alerts = AlertManager(
            cooldown_seconds=alerts_cfg.get("cooldown_seconds", 30),
            volume=alerts_cfg.get("volume", 0.8),
            enable_sound=alerts_cfg.get("enable_sound", True),
            enable_voice=alerts_cfg.get("enable_voice", True),
        )
        self._alerts.init()

        # Callbacks
        callbacks = AnalyzerCallbacks(
            on_distraction_start=self._on_distraction_start,
            on_distraction_end=self._on_distraction_end,
        )

        # Worker
        self._worker = CameraWorker(index=0, width=1280, height=720, fps=30)
        self._worker.processor = FrameProcessor(
            config=DetectionConfig.from_file(),
            analyzer_callbacks=callbacks,
        )
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.started_ok.connect(self._on_started)
        self._worker.stopped.connect(self._on_stopped)
        self._worker.start()

    def _stop_worker(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(2000)
            self._worker = None
        if self._alerts is not None:
            self._alerts.shutdown()
            self._alerts = None

    # ---- Callbacks ----

    def _on_started(self, info: dict) -> None:
        self.active_indicator.setText("●  ACTIVE")
        self.active_indicator.setStyleSheet(
            f"color: {SUCCESS}; font-size: 13px; font-weight: 600; "
            f"padding: 6px 14px; background: {CARD_BG}; "
            f"border-radius: 12px;"
        )
        self.footer_label.setText(
            f"Camera {info['width']}x{info['height']} @ "
            f"{info['fps']:.0f} FPS  ·  YOLO every 5 frames  ·  "
            f"MediaPipe hands every frame"
        )

    def _on_error(self, msg: str) -> None:
        self.video_label.setText(f"Camera error:\n{msg}")
        self.active_indicator.setText("●  ERROR")
        self.active_indicator.setStyleSheet(
            f"color: {DANGER}; font-size: 13px; font-weight: 600; "
            f"padding: 6px 14px; background: {CARD_BG}; "
            f"border-radius: 12px;"
        )

    def _on_stopped(self) -> None:
        self.active_indicator.setText("●  STOPPED")

    def _on_frame(self, processed) -> None:
        img = processed.image
        meta = processed.metadata

        # Draw HUD on a copy
        from camera.frame_processor import FrameProcessor
        hud_frame = FrameProcessor(enable_detection=False, enable_hands=False).draw_hud(img, meta)

        # Scale to video label size, preserving aspect ratio
        h, w, ch = hud_frame.shape
        qimg = QImage(hud_frame.data, w, h, ch * w, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(qimg)

        label_w = self.video_label.width()
        label_h = self.video_label.height()
        scaled = pixmap.scaled(
            label_w, label_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)

        self._last_meta = meta

    def _on_distraction_start(self) -> None:
        """Called by state machine when DISTRACTION_CONFIRMED is entered."""
        self._session_distractions += 1
        self._current_event_active = True
        self.distraction_recorded.emit()
        self.distraction_started.emit()
        if self._alerts is not None:
            self._alerts.on_distraction_started(confidence=0.8)

    def _on_distraction_end(self) -> None:
        self._current_event_active = False
        self.distraction_ended.emit()
        if self._alerts is not None:
            self._alerts.on_distraction_ended()

    # ---- UI updates ----

    def _refresh_status(self) -> None:
        m = self._last_meta
        if m is None:
            return

        state = m.state
        state_color = STATE_COLOR_MAP.get(state, TEXT_SECONDARY)
        self.state_row.set(state.replace("_", " "), state_color)

        if m.phone_visible:
            self.phone_row.set(f"Detected · {m.phone_confidence * 100:.0f}%", "#06B6D4")
        else:
            self.phone_row.set("None", TEXT_SECONDARY)

        self.hands_row.set(str(m.hands_visible))

        prox = m.proximity
        if prox > 0.6:
            prox_color = "#EF4444"
        elif prox > 0.3:
            prox_color = "#F59E0B"
        else:
            prox_color = TEXT_SECONDARY
        self.proximity_row.set(f"{prox:.2f}", prox_color)

        self.fps_row.set(f"{m.fps:.1f}")

        self.session_count_row.set(
            str(self._session_distractions),
            DANGER if self._session_distractions > 0 else TEXT_PRIMARY,
        )

    # ---- Button handlers ----

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._worker is not None:
            if self._paused:
                self._worker.pause()
                self.pause_btn.setText("▶  Resume Monitoring")
                self.active_indicator.setText("●  PAUSED")
                self.active_indicator.setStyleSheet(
                    f"color: {WARNING}; font-size: 13px; font-weight: 600; "
                    f"padding: 6px 14px; background: {CARD_BG}; "
                    f"border-radius: 12px;"
                )
            else:
                self._worker.resume()
                self.pause_btn.setText("⏸  Pause Monitoring")
                self.active_indicator.setText("●  ACTIVE")
                self.active_indicator.setStyleSheet(
                    f"color: {SUCCESS}; font-size: 13px; font-weight: 600; "
                    f"padding: 6px 14px; background: {CARD_BG}; "
                    f"border-radius: 12px;"
                )

    def _test_alarm(self) -> None:
        """Play the alarm + voice without needing actual detection."""
        if self._alerts is None:
            logger.warning("Alert manager not ready")
            return
        self._alerts.sounds.play_alarm()
        self._alerts.voice.play_random()
        # Auto-stop after 3 seconds
        QTimer.singleShot(3000, self._alerts.sounds.stop_alarm)