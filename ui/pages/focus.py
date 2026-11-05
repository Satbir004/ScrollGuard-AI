"""
Focus Session page — Pomodoro-style timer wired to the DB.

Behavior:
  - Choose a preset duration (25 / 50 / 60 / 90 min) or custom.
  - Click Start → creates a study_sessions row, starts a QTimer.
  - Every second: update the display; every 30s: write elapsed time to
    productivity_records.
  - Pause / Resume via button.
  - Finish → closes the session row, updates productivity, shows summary.
  - Auto-pauses when the Monitoring page records a distraction,
    auto-resumes when it ends. (Wired via main_window signals.)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSizePolicy,
)

from database.repository import (
    DistractionRepository,
    ProductivityRepository,
    SessionRepository,
)
from database.models import ProductivityRecord
from ui.components.section_header import SectionHeader
from ui.styles.theme import (
    ACCENT_PRIMARY, CARD_BG, DANGER, SUCCESS, TEXT_PRIMARY,
    TEXT_SECONDARY, WARNING, BORDER,
)

logger = logging.getLogger(__name__)


PRESETS = [
    ("Pomodoro", 25),
    ("Focus", 50),
    ("Study", 60),
    ("Deep work", 90),
]


def _fmt_clock(total_seconds: int) -> str:
    if total_seconds < 0:
        total_seconds = 0
    m, s = divmod(total_seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class FocusPage(QWidget):
    # Emitted when a session starts/ends so other pages can react
    session_started = Signal(int)   # session_id
    session_ended = Signal(int)     # session_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_id: int | None = None
        self._session_seconds: int = 0
        self._planned_seconds: int = 25 * 60
        self._state = "idle"  # idle | running | paused
        self._distractions_during_session: int = 0
        self._last_save_at: int = 0

        self._build_ui()

        # 1Hz ticker
        self._ticker = QTimer(self)
        self._ticker.timeout.connect(self._tick)
        self._ticker.setInterval(1000)

    # ---- UI ----

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(20)

        outer.addWidget(SectionHeader(
            "Focus Session",
            "Deep work timer with automatic distraction tracking",
        ))

        # Main row: timer (left) | info (right)
        row = QHBoxLayout()
        row.setSpacing(20)

        # ---- Timer panel ----
        timer_card = QFrame()
        timer_card.setObjectName("Card")
        timer_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        tl = QVBoxLayout(timer_card)
        tl.setContentsMargins(24, 24, 24, 24)
        tl.setSpacing(16)

        self.state_label = QLabel("●  Idle")
        self.state_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 14px; font-weight: 600;"
        )
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.addWidget(self.state_label)

        self.timer_label = QLabel(_fmt_clock(self._planned_seconds))
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 84px; "
            f"font-weight: 700; font-family: 'Segoe UI', monospace;"
        )
        tl.addWidget(self.timer_label)

        self.subtitle_label = QLabel("Ready when you are")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 13px;"
        )
        tl.addWidget(self.subtitle_label)

        tl.addSpacing(12)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        self.start_btn = QPushButton("Start Focus Session")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.setMinimumHeight(48)
        self.start_btn.setMinimumWidth(200)
        self.start_btn.clicked.connect(self._on_start_or_pause)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Finish")
        self.stop_btn.setObjectName("SecondaryButton")
        self.stop_btn.setMinimumHeight(48)
        self.stop_btn.setMinimumWidth(120)
        self.stop_btn.clicked.connect(self._on_finish)
        self.stop_btn.setVisible(False)
        btn_row.addWidget(self.stop_btn)

        btn_row.addStretch()
        tl.addLayout(btn_row)

        tl.addStretch()

        # Presets row
        presets_row = QHBoxLayout()
        presets_row.setSpacing(8)
        self._preset_buttons: dict[int, QPushButton] = {}
        for label, mins in PRESETS:
            b = QPushButton(f"{label}\n{mins} min")
            b.setObjectName("SecondaryButton")
            b.setMinimumHeight(56)
            b.setStyleSheet(
                f"QPushButton {{ background: {CARD_BG}; color: {TEXT_PRIMARY}; "
                f"border: 1px solid {BORDER}; border-radius: 8px; padding: 6px; }}"
                f"QPushButton:hover {{ background: {BORDER}; }}"
            )
            b.clicked.connect(lambda _=False, m=mins: self._select_preset(m))
            self._preset_buttons[mins] = b
            presets_row.addWidget(b)
        tl.addLayout(presets_row)

        row.addWidget(timer_card, stretch=3)

        # ---- Info panel ----
        info_card = QFrame()
        info_card.setObjectName("Card")
        info_card.setFixedWidth(300)
        info_card.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding,
        )
        il = QVBoxLayout(info_card)
        il.setContentsMargins(20, 20, 20, 20)
        il.setSpacing(12)

        info_title = QLabel("Session Details")
        info_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 600;"
        )
        il.addWidget(info_title)

        self.duration_row = self._make_info_row("Planned duration", "25 min")
        self.elapsed_row = self._make_info_row("Elapsed", "0:00")
        self.distractions_row = self._make_info_row("Distractions", "0")
        for r in (self.duration_row, self.elapsed_row, self.distractions_row):
            il.addWidget(r)

        il.addSpacing(12)

        # Today's summary
        today_title = QLabel("Today")
        today_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 600;"
        )
        il.addWidget(today_title)

        self.today_focus_row = self._make_info_row("Total focus", "0m")
        self.today_sessions_row = self._make_info_row("Sessions", "0")
        self.today_distractions_row = self._make_info_row("Distractions", "0")
        for r in (self.today_focus_row, self.today_sessions_row, self.today_distractions_row):
            il.addWidget(r)

        il.addStretch()

        row.addWidget(info_card, stretch=0)
        outer.addLayout(row, stretch=1)

        self._refresh_today_summary()
        self._select_preset(25)

    def _make_info_row(self, label: str, value: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 4, 0, 4)
        h.setSpacing(8)
        l = QLabel(label)
        l.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        v = QLabel(value)
        v.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
        )
        v.setAlignment(Qt.AlignmentFlag.AlignRight)
        h.addWidget(l)
        h.addStretch()
        h.addWidget(v)
        # Store ref on the widget so we can update
        w._value_label = v
        return w

    def _update_info_row(self, widget: QWidget, text: str, color: str | None = None) -> None:
        lbl = widget._value_label
        lbl.setText(text)
        lbl.setStyleSheet(
            f"color: {color or TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
        )

    # ---- Presets ----

    def _select_preset(self, minutes: int) -> None:
        if self._state == "running":
            return
        self._planned_seconds = minutes * 60
        self._session_seconds = 0
        self._update_time_display()
        self._update_info_row(self.duration_row, f"{minutes} min")

        # Highlight selected preset
        for m, b in self._preset_buttons.items():
            if m == minutes:
                b.setStyleSheet(
                    f"QPushButton {{ background: {ACCENT_PRIMARY}; color: white; "
                    f"border: 1px solid {ACCENT_PRIMARY}; border-radius: 8px; padding: 6px; }}"
                )
            else:
                b.setStyleSheet(
                    f"QPushButton {{ background: {CARD_BG}; color: {TEXT_PRIMARY}; "
                    f"border: 1px solid {BORDER}; border-radius: 8px; padding: 6px; }}"
                    f"QPushButton:hover {{ background: {BORDER}; }}"
                )

    # ---- Timer logic ----

    def _update_time_display(self) -> None:
        remaining = max(self._planned_seconds - self._session_seconds, 0)
        self.timer_label.setText(_fmt_clock(remaining))
        self._update_info_row(self.elapsed_row, _fmt_clock(self._session_seconds))

    def _on_start_or_pause(self) -> None:
        if self._state == "idle":
            self._start_session()
        elif self._state == "running":
            self._pause_session()
        elif self._state == "paused":
            self._resume_session()

    def _start_session(self) -> None:
        # Reset counters
        self._session_seconds = 0
        self._distractions_during_session = 0
        self._last_save_at = 0

        try:
            session = SessionRepository.create(
                planned_minutes=self._planned_seconds // 60,
                label="focus",
            )
            self._session_id = session.id
        except Exception:
            logger.exception("Failed to create session in DB")
            self._session_id = None

        self._state = "running"
        self._ticker.start()
        self._update_state_label()
        self._update_buttons()
        self._update_time_display()
        self.start_btn.setText("⏸  Pause")
        self.stop_btn.setVisible(True)
        self._update_info_row(self.distractions_row, "0")
        if self._session_id is not None:
            self.session_started.emit(self._session_id)
        logger.info("Session started: id=%s, planned=%ds",
                    self._session_id, self._planned_seconds)

    def _pause_session(self) -> None:
        self._state = "paused"
        self._ticker.stop()
        self._update_state_label()
        self._update_buttons()
        if self._session_id:
            try:
                SessionRepository.end(self._session_id, status="paused")
            except Exception:
                logger.exception("Failed to mark session paused")

    def _resume_session(self) -> None:
        self._state = "running"
        self._ticker.start()
        self._update_state_label()
        self._update_buttons()
        if self._session_id:
            # Re-open the session
            try:
                from database.db import get_connection
                conn = get_connection()
                conn.execute(
                    "UPDATE study_sessions SET ended_at = NULL, status = 'active' "
                    "WHERE id = ?",
                    (self._session_id,),
                )
                conn.commit()
            except Exception:
                logger.exception("Failed to resume session")

    def _on_finish(self) -> None:
        if self._state == "idle":
            return
        self._finish_session(status="completed")

    def _finish_session(self, status: str) -> None:
        self._ticker.stop()
        elapsed = self._session_seconds

        if self._session_id:
            try:
                SessionRepository.add_seconds(self._session_id, elapsed)
                SessionRepository.end(self._session_id, status=status)
                self.session_ended.emit(self._session_id)
            except Exception:
                logger.exception("Failed to close session")
            self._session_id = None

        self._state = "idle"
        self._update_state_label()
        self._update_buttons()
        self.start_btn.setText("Start Focus Session")
        self.stop_btn.setVisible(False)
        self.subtitle_label.setText(
            f"Session {status} · {_fmt_clock(elapsed)} focused"
        )
        self._refresh_today_summary()
        logger.info("Session ended: status=%s, elapsed=%ds", status, elapsed)

    def _tick(self) -> None:
        self._session_seconds += 1
        self._update_time_display()

        # Save to productivity every 30s
        if self._session_seconds - self._last_save_at >= 30:
            self._last_save_at = self._session_seconds
            self._save_progress()
            self._refresh_today_summary()

        # Auto-complete
        if self._session_seconds >= self._planned_seconds:
            self._finish_session(status="completed")

    def _save_progress(self) -> None:
        """Persist current focus time + distraction count to productivity_records."""
        today = _today()
        try:
            rec = ProductivityRepository.get_for_day(today)
            if rec is None:
                rec = ProductivityRecord(day=today)
            rec.focused_seconds += 30  # 30s delta
            # Recompute score: focus / (focus + distracted), cap 100
            total = rec.focused_seconds + rec.distracted_seconds
            rec.productivity_score = (
                (rec.focused_seconds / total) * 100.0 if total > 0 else 0.0
            )
            ProductivityRepository.upsert_for_day(rec)
        except Exception:
            logger.exception("Failed to save progress")

    # ---- Callbacks from monitoring page ----

    def on_distraction_started(self) -> None:
        """Called by main_window when monitoring confirms a distraction."""
        self._distractions_during_session += 1
        self._update_info_row(
            self.distractions_row,
            str(self._distractions_during_session),
            color=DANGER,
        )

        # Pause the timer during distraction (focus time excludes phone time)
        if self._state == "running":
            self._state = "paused"
            self._ticker.stop()
            self._update_state_label("Phone distraction")
            self._update_buttons()

    def on_distraction_ended(self) -> None:
        """Called when distraction ends — auto-resume the timer."""
        if self._state == "paused" and self._session_id is not None:
            self._state = "running"
            self._ticker.start()
            self._update_state_label()
            self._update_buttons()

    # ---- Display helpers ----

    def _update_state_label(self, override: str | None = None) -> None:
        if override:
            self.state_label.setText(f"●  {override}")
            self.state_label.setStyleSheet(
                f"color: {WARNING}; font-size: 14px; font-weight: 600;"
            )
            return
        if self._state == "idle":
            self.state_label.setText("●  Idle")
            self.state_label.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 14px; font-weight: 600;"
            )
        elif self._state == "running":
            self.state_label.setText("●  Running")
            self.state_label.setStyleSheet(
                f"color: {SUCCESS}; font-size: 14px; font-weight: 600;"
            )
        elif self._state == "paused":
            self.state_label.setText("●  Paused")
            self.state_label.setStyleSheet(
                f"color: {WARNING}; font-size: 14px; font-weight: 600;"
            )

    def _update_buttons(self) -> None:
        if self._state == "running":
            self.start_btn.setText("⏸  Pause")
        elif self._state == "paused":
            self.start_btn.setText("▶  Resume")
        else:
            self.start_btn.setText("Start Focus Session")

    def _refresh_today_summary(self) -> None:
        today = _today()
        try:
            rec = ProductivityRepository.get_for_day(today)
            if rec:
                self._update_info_row(
                    self.today_focus_row, _fmt_clock(rec.focused_seconds)
                )
                self._update_info_row(
                    self.today_distractions_row, str(rec.distraction_count)
                )
            # Count today's sessions
            conn_rows = SessionRepository.list_recent(limit=50)
            today_sessions = sum(
                1 for s in conn_rows if s.started_at.startswith(today)
            )
            self._update_info_row(self.today_sessions_row, str(today_sessions))
        except Exception:
            logger.exception("Failed to refresh today summary")