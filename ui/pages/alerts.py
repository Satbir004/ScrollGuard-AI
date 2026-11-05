"""Alerts page — quick test tools + recent alert log."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)

from alerts.sound_manager import SoundManager
from alerts.voice_manager import VoiceManager
from database.repository import AlertRepository
from ui.components.section_header import SectionHeader
from ui.styles.theme import (
    ACCENT_PRIMARY, CARD_BG, DANGER, SUCCESS, TEXT_PRIMARY, TEXT_SECONDARY,
)


class AlertsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._sounds = SoundManager()
        self._voice = VoiceManager()
        self._sounds.init()
        self._voice.init()
        self._build_ui()
        self.refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(16)

        outer.addWidget(SectionHeader(
            "Alerts",
            "Test sounds and view recent alert history",
        ))

        # Test buttons row
        test_card = QFrame()
        test_card.setObjectName("Card")
        tl = QHBoxLayout(test_card)
        tl.setContentsMargins(20, 16, 20, 16)

        play_sound = QPushButton("🔊  Play Alarm Sound")
        play_sound.setObjectName("PrimaryButton")
        play_sound.clicked.connect(self._play_sound)
        tl.addWidget(play_sound)

        play_voice = QPushButton("🎙  Play Random Voice")
        play_voice.setObjectName("PrimaryButton")
        play_voice.clicked.connect(self._play_voice)
        tl.addWidget(play_voice)

        stop = QPushButton("⏸  Stop Audio")
        stop.setObjectName("SecondaryButton")
        stop.clicked.connect(self._stop)
        tl.addWidget(stop)

        tl.addStretch()
        outer.addWidget(test_card)

        # Alert log table
        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Time", "Reason", "Level", "Event ID"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {CARD_BG}; color: {TEXT_PRIMARY};
                gridline-color: #1F2A44; border: none; font-size: 12px;
            }}
            QHeaderView::section {{
                background: #111827; color: {TEXT_SECONDARY};
                padding: 8px; border: none;
                border-bottom: 1px solid #1F2A44;
                font-weight: 600; font-size: 11px;
            }}
        """)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        cl.addWidget(self.table)
        outer.addWidget(card, stretch=1)

    def refresh(self):
        try:
            from database.db import get_connection
            conn = get_connection()
            rows = conn.execute(
                "SELECT * FROM alert_history ORDER BY fired_at DESC LIMIT 100"
            ).fetchall()
        except Exception:
            rows = []
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            dt = r["fired_at"].replace("T", " ")[:19]
            self.table.setItem(i, 0, QTableWidgetItem(dt))
            self.table.setItem(i, 1, QTableWidgetItem(r["reason"]))
            level_map = {0: "Suppressed", 1: "Chime", 2: "Alarm", 3: "Voice"}
            self.table.setItem(
                i, 2,
                QTableWidgetItem(level_map.get(r["level"], str(r["level"]))),
            )
            self.table.setItem(
                i, 3,
                QTableWidgetItem(str(r["event_id"] or "—")),
            )

    def _play_sound(self):
        self._sounds.play_alarm()
        QTimer.singleShot(2000, self._sounds.stop_alarm)

    def _play_voice(self):
        self._voice.play_random()

    def _stop(self):
        self._sounds.stop_alarm()