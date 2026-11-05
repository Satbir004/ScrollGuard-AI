"""
Settings page — edits config.json and settings table.
Live changes apply to the running monitoring worker on next restart.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QSlider, QSpinBox, QCheckBox, QComboBox, QScrollArea,
)

from ui.components.section_header import SectionHeader
from ui.styles.theme import (
    ACCENT_PRIMARY, CARD_BG, DANGER, SUCCESS, TEXT_PRIMARY,
    TEXT_SECONDARY, BORDER,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def _section_card(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(10)

    t = QLabel(title)
    t.setStyleSheet(
        f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 600;"
    )
    layout.addWidget(t)

    if subtitle:
        s = QLabel(subtitle)
        s.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(s)

    return card, layout


def _row(label: str, widget: QWidget) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 4, 0, 4)
    l = QLabel(label)
    l.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
    l.setMinimumWidth(220)
    h.addWidget(l)
    h.addWidget(widget, stretch=1)
    return w


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = _load_config()
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(16)

        outer.addWidget(SectionHeader(
            "Settings",
            "Changes save to config.json · apply to monitoring after restart",
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 8, 0)
        inner_layout.setSpacing(16)

        det = self.cfg.get("detection", {})
        sm = self.cfg.get("state_machine", {})
        alerts = self.cfg.get("alerts", {})
        prod = self.cfg.get("productivity", {})

        # ---- Detection ----
        card, layout = _section_card(
            "AI Detection",
            "How sensitive the phone detection is. Lower confidence = more detections but more false positives.",
        )
        self.conf_spin = QSpinBox()
        self.conf_spin.setRange(20, 95)
        self.conf_spin.setSuffix(" %")
        self.conf_spin.setValue(int(det.get("confidence_threshold", 0.5) * 100))
        self.conf_spin.setStyleSheet(
            f"QSpinBox {{ background: {CARD_BG}; color: {TEXT_PRIMARY}; "
            f"padding: 6px; border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        layout.addWidget(_row("Phone confidence threshold", self.conf_spin))

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 15)
        self.interval_spin.setSuffix(" frames")
        self.interval_spin.setValue(int(det.get("yolo_inference_interval", 5)))
        self.interval_spin.setStyleSheet(self.conf_spin.styleSheet())
        layout.addWidget(_row("YOLO inference interval", self.interval_spin))
        inner_layout.addWidget(card)

        # ---- State machine ----
        card, layout = _section_card(
            "Detection Timing",
            "How long signals must persist before triggering. Higher = fewer false alarms but slower response.",
        )
        self.confirm_spin = QSpinBox()
        self.confirm_spin.setRange(5, 100)
        self.confirm_spin.setSuffix(" × 0.1s")
        self.confirm_spin.setValue(int(sm.get("confirm_distraction_min_seconds", 2.5) * 10))
        self.confirm_spin.setStyleSheet(self.conf_spin.styleSheet())
        layout.addWidget(_row("Confirm distraction after", self.confirm_spin))

        self.prox_spin = QSpinBox()
        self.prox_spin.setRange(30, 95)
        self.prox_spin.setSuffix(" %")
        self.prox_spin.setValue(int(sm.get("hand_proximity_threshold", 0.6) * 100))
        self.prox_spin.setStyleSheet(self.conf_spin.styleSheet())
        layout.addWidget(_row("Hand proximity threshold", self.prox_spin))
        inner_layout.addWidget(card)

        # ---- Audio ----
        card, layout = _section_card(
            "Alerts & Audio",
            "Sound and voice warning behavior.",
        )
        self.sound_check = QCheckBox("Enable alarm sound")
        self.sound_check.setChecked(bool(alerts.get("enable_sound", True)))
        self.sound_check.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(self.sound_check)

        self.voice_check = QCheckBox("Enable voice warnings")
        self.voice_check.setChecked(bool(alerts.get("enable_voice", True)))
        self.voice_check.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(self.voice_check)

        vol_row = QWidget()
        vol_layout = QHBoxLayout(vol_row)
        vol_layout.setContentsMargins(0, 0, 0, 0)
        vol_layout.addWidget(QLabel("Volume"))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(alerts.get("volume", 0.8) * 100))
        self.vol_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ background: {BORDER}; height: 4px; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ background: {ACCENT_PRIMARY}; "
            f"width: 14px; margin: -6px 0; border-radius: 7px; }}"
        )
        self.vol_value = QLabel(f"{int(alerts.get('volume', 0.8) * 100)}%")
        self.vol_value.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self.vol_slider.valueChanged.connect(
            lambda v: self.vol_value.setText(f"{v}%")
        )
        vol_layout.addWidget(self.vol_slider, stretch=1)
        vol_layout.addWidget(self.vol_value)
        layout.addWidget(_row("Alarm volume", vol_row))

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(5, 300)
        self.cooldown_spin.setSuffix(" s")
        self.cooldown_spin.setValue(int(alerts.get("cooldown_seconds", 30)))
        self.cooldown_spin.setStyleSheet(self.conf_spin.styleSheet())
        layout.addWidget(_row("Alert cooldown", self.cooldown_spin))
        inner_layout.addWidget(card)

        # ---- Productivity ----
        card, layout = _section_card(
            "Productivity",
            "Focus goals and defaults.",
        )
        self.goal_spin = QSpinBox()
        self.goal_spin.setRange(15, 720)
        self.goal_spin.setSuffix(" min")
        self.goal_spin.setValue(int(prod.get("daily_goal_minutes", 120)))
        self.goal_spin.setStyleSheet(self.conf_spin.styleSheet())
        layout.addWidget(_row("Daily focus target", self.goal_spin))

        self.default_session_spin = QSpinBox()
        self.default_session_spin.setRange(5, 180)
        self.default_session_spin.setSuffix(" min")
        self.default_session_spin.setValue(int(prod.get("default_session_minutes", 25)))
        self.default_session_spin.setStyleSheet(self.conf_spin.styleSheet())
        layout.addWidget(_row("Default session length", self.default_session_spin))
        inner_layout.addWidget(card)

        inner_layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)

        # ---- Save / Reset row ----
        bottom = QHBoxLayout()
        bottom.addStretch()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("SecondaryButton")
        reset_btn.clicked.connect(self._reset)
        bottom.addWidget(reset_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setMinimumWidth(160)
        save_btn.clicked.connect(self._save)
        bottom.addWidget(save_btn)

        outer.addLayout(bottom)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {SUCCESS}; font-size: 12px; font-weight: 600;"
        )
        outer.addWidget(self.status_label)

    def _save(self):
        try:
            cfg = _load_config()
            cfg.setdefault("detection", {})
            cfg.setdefault("state_machine", {})
            cfg.setdefault("alerts", {})
            cfg.setdefault("productivity", {})

            cfg["detection"]["confidence_threshold"] = self.conf_spin.value() / 100.0
            cfg["detection"]["yolo_inference_interval"] = self.interval_spin.value()
            cfg["state_machine"]["confirm_distraction_min_seconds"] = self.confirm_spin.value() / 10.0
            cfg["state_machine"]["hand_proximity_threshold"] = self.prox_spin.value() / 100.0
            cfg["alerts"]["enable_sound"] = self.sound_check.isChecked()
            cfg["alerts"]["enable_voice"] = self.voice_check.isChecked()
            cfg["alerts"]["volume"] = self.vol_slider.value() / 100.0
            cfg["alerts"]["cooldown_seconds"] = self.cooldown_spin.value()
            cfg["productivity"]["daily_goal_minutes"] = self.goal_spin.value()
            cfg["productivity"]["default_session_minutes"] = self.default_session_spin.value()

            _save_config(cfg)
            self.status_label.setText(
                "✓  Saved. Restart the app for changes to apply."
            )
        except Exception:
            logger.exception("Save settings failed")
            self.status_label.setStyleSheet(
                f"color: {DANGER}; font-size: 12px; font-weight: 600;"
            )
            self.status_label.setText("✗  Save failed — check terminal")

    def _reset(self):
        default = {
            "detection": {"confidence_threshold": 0.5, "yolo_inference_interval": 5},
            "state_machine": {
                "confirm_distraction_min_seconds": 2.5,
                "hand_proximity_threshold": 0.6,
            },
            "alerts": {
                "enable_sound": True, "enable_voice": True,
                "volume": 0.8, "cooldown_seconds": 30,
            },
            "productivity": {
                "daily_goal_minutes": 120, "default_session_minutes": 25,
            },
        }
        try:
            cfg = _load_config()
            for section, values in default.items():
                cfg.setdefault(section, {}).update(values)
            _save_config(cfg)
            self.status_label.setStyleSheet(
                f"color: {SUCCESS}; font-size: 12px; font-weight: 600;"
            )
            self.status_label.setText("✓  Reset to defaults. Restart to apply.")
        except Exception:
            logger.exception("Reset failed")
            self.status_label.setStyleSheet(
                f"color: {DANGER}; font-size: 12px; font-weight: 600;"
            )
            self.status_label.setText("✗  Reset failed — check terminal")

    def _reset(self):
        default = {
            "detection": {"confidence_threshold": 0.5, "yolo_inference_interval": 5},
            "state_machine": {
                "confirm_distraction_min_seconds": 2.5,
                "hand_proximity_threshold": 0.6,
            },
            "alerts": {
                "enable_sound": True, "enable_voice": True,
                "volume": 0.8, "cooldown_seconds": 30,
            },
            "productivity": {
                "daily_goal_minutes": 120, "default_session_minutes": 25,
            },
        }
        try:
            cfg = _load_config()
            for section, values in default.items():
                cfg.setdefault(section, {}).update(values)
            _save_config(cfg)
            self.status_label.setText("✓  Reset to defaults. Restart to apply.")
        except Exception:
            logger.exception("Reset failed")