"""
Dashboard page — connects to real DB data.
Shows: greeting, stats cards, weekly chart, recent distractions, quick-start.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGridLayout, QSizePolicy,
)

from database.repository import (
    DistractionRepository, ProductivityRepository, SessionRepository,
)
from ui.components.section_header import SectionHeader
from ui.components.stat_card import StatCard
from ui.styles.theme import (
    ACCENT_PRIMARY, CARD_BG, BORDER, DANGER, SUCCESS, TEXT_PRIMARY,
    TEXT_SECONDARY, WARNING,
)


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    m = seconds // 60
    if m < 60:
        return f"{m}m"
    h = m // 60
    return f"{h}h {m % 60}m"


class WeeklyChart(QWidget):
    """
    Simple bar chart drawn directly with QPainter — no matplotlib dependency.
    Shows last 7 days of focused vs distracted time.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(220)
        self._data: list[tuple[str, int, int]] = []  # (day_label, focus_s, dist_s)
        self._refresh_data()

    def _refresh_data(self):
        records = {r.day: r for r in ProductivityRepository.list_last_days(7)}
        data = []
        for i in range(6, -1, -1):
            d = datetime.now(timezone.utc) - timedelta(days=i)
            key = d.strftime("%Y-%m-%d")
            label = d.strftime("%a")
            rec = records.get(key)
            focus = rec.focused_seconds if rec else 0
            dist = rec.distracted_seconds if rec else 0
            data.append((label, focus, dist))
        self._data = data
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor, QPen, QFont
        from PySide6.QtCore import QRectF

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin_x, margin_top, margin_bottom = 40, 50, 40
        chart_w = w - margin_x * 2
        chart_h = h - margin_top - margin_bottom

        # Title
        painter.setPen(QColor(TEXT_PRIMARY))
        f = QFont(); f.setPointSize(11); f.setBold(True)
        painter.setFont(f)
        painter.drawText(20, 26, "Weekly Focus vs Distraction")

        # Max for scale
        max_val = max((max(f_, d_) for _, f_, d_ in self._data), default=1)
        if max_val <= 0:
            max_val = 1

        bar_group_w = chart_w / max(len(self._data), 1)
        bar_w = (bar_group_w - 20) / 2
        bar_w = max(bar_w, 6)

        for i, (label, focus, dist) in enumerate(self._data):
            base_x = margin_x + i * bar_group_w + 10
            base_y = margin_top + chart_h

            # Focus bar
            fh = (focus / max_val) * chart_h if max_val > 0 else 0
            if fh > 1:
                painter.fillRect(QRectF(base_x, base_y - fh, bar_w, fh), QColor(SUCCESS))
                painter.setPen(Qt.PenStyle.NoPen)

            # Distraction bar
            dh = (dist / max_val) * chart_h if max_val > 0 else 0
            if dh > 1:
                painter.fillRect(
                    QRectF(base_x + bar_w + 4, base_y - dh, bar_w, dh),
                    QColor(DANGER),
                )

            # Day label
            painter.setPen(QColor(TEXT_SECONDARY))
            f2 = QFont(); f2.setPointSize(9)
            painter.setFont(f2)
            painter.drawText(
                QRectF(base_x - 10, base_y + 8, bar_group_w, 20),
                Qt.AlignmentFlag.AlignHCenter,
                label,
            )

        # Legend
        painter.setPen(QColor(SUCCESS))
        painter.drawText(w - 180, 26, "■ Focus")
        painter.setPen(QColor(DANGER))
        painter.drawText(w - 110, 26, "■ Distraction")

        painter.end()


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._refresh()

        # Auto-refresh every 5 seconds
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(24)

        # Header
        now = datetime.now()
        hour = now.hour
        greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")
        outer.addWidget(SectionHeader(
            f"{greeting}, Student 👋",
            f"Today is {now.strftime('%A, %B %d, %Y')}",
        ))

        # Stat cards row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.focus_card = StatCard("Today's Focus", "0m", "Start a session →")
        self.distract_card = StatCard("Distractions", "0", "None today 🎉", SUCCESS)
        self.avg_card = StatCard("Avg. Distraction", "0s", "")
        self.score_card = StatCard("Productivity Score", "0%", "", ACCENT_PRIMARY)

        cards_layout.addWidget(self.focus_card)
        cards_layout.addWidget(self.distract_card)
        cards_layout.addWidget(self.avg_card)
        cards_layout.addWidget(self.score_card)
        outer.addLayout(cards_layout)

        # Chart
        self.chart = WeeklyChart()
        outer.addWidget(self.chart)

        # Recent distractions + quick start
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(16)

        recent_card = QFrame()
        recent_card.setObjectName("Card")
        recent_card.setMinimumHeight(220)
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(20, 18, 20, 18)
        recent_layout.setSpacing(10)

        recent_title = QLabel("Recent Distractions")
        recent_title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 600; font-size: 14px;")
        recent_layout.addWidget(recent_title)

        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(6)
        recent_layout.addLayout(self.recent_list)
        recent_layout.addStretch()

        bottom_layout.addWidget(recent_card, stretch=2)

        # Quick-start card
        quick_card = QFrame()
        quick_card.setObjectName("Card")
        quick_card.setMinimumHeight(220)
        quick_layout = QVBoxLayout(quick_card)
        quick_layout.setContentsMargins(20, 18, 20, 18)
        quick_layout.setSpacing(12)

        quick_title = QLabel("Ready to focus?")
        quick_title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 600; font-size: 14px;")
        quick_layout.addWidget(quick_title)

        quick_sub = QLabel(
            "Start a session and ScrollGuard will watch\nyour phone while you study."
        )
        quick_sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        quick_layout.addWidget(quick_sub)

        quick_layout.addStretch()

        start_btn = QPushButton("Start 25-minute session")
        start_btn.setObjectName("PrimaryButton")
        start_btn.setMinimumHeight(42)
        quick_layout.addWidget(start_btn)

        bottom_layout.addWidget(quick_card, stretch=1)

        outer.addLayout(bottom_layout)
        outer.addStretch()

    def _refresh(self):
        today = _today_str()

        # Stats from DB
        distractions = DistractionRepository.total_today()
        records = {r.day: r for r in ProductivityRepository.list_last_days(7)}
        today_rec = records.get(today)

        focus_seconds = today_rec.focused_seconds if today_rec else 0
        distracted_seconds = today_rec.distracted_seconds if today_rec else 0
        score = today_rec.productivity_score if today_rec else 0.0

        # Update cards
        self.focus_card.set_value(_format_duration(focus_seconds))
        self.distract_card.set_value(str(distractions))
        if distractions > 0:
            avg = distracted_seconds // max(distractions, 1)
            self.avg_card.set_value(_format_duration(avg))
        else:
            self.avg_card.set_value("0s")
        self.score_card.set_value(f"{int(score)}%")

        # Recent distractions list
        while self.recent_list.count():
            item = self.recent_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        events = DistractionRepository.list_recent(limit=4)
        if not events:
            empty = QLabel("No distractions recorded yet ✨")
            empty.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 8px;")
            self.recent_list.addWidget(empty)
        else:
            for e in events:
                row = QLabel(
                    f"• {e.started_at[11:16]}  —  {e.duration_seconds}s  "
                    f"(conf {e.confidence * 100:.0f}%)"
                )
                row.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
                self.recent_list.addWidget(row)

        # Refresh chart
        self.chart._refresh_data()