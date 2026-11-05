"""
Analytics page — all charts read live from the SQLite DB.
Four charts: weekly focus/distraction, 30-day focus trend,
distraction count by hour, productivity score trend.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QSizePolicy,
)

from database.repository import (
    DistractionRepository, ProductivityRepository, SessionRepository,
)
from ui.components.section_header import SectionHeader
from ui.components.stat_card import StatCard
from ui.styles.theme import (
    ACCENT_PRIMARY, ACCENT_SECONDARY, BORDER, CARD_BG, DANGER,
    SUCCESS, TEXT_PRIMARY, TEXT_SECONDARY, WARNING,
)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class BaseChart(QFrame):
    """Base class for painter-drawn charts with a title."""
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(260)
        self._title = title
        self._subtitle = subtitle

    def draw_title(self, painter: QPainter, w: int) -> int:
        """Draw title + subtitle, return the top of the chart area."""
        painter.setPen(QColor(TEXT_PRIMARY))
        f = QFont(); f.setPointSize(11); f.setBold(True)
        painter.setFont(f)
        painter.drawText(20, 26, self._title)
        if self._subtitle:
            painter.setPen(QColor(TEXT_SECONDARY))
            f2 = QFont(); f2.setPointSize(9)
            painter.setFont(f2)
            painter.drawText(20, 44, self._subtitle)
            return 60
        return 46


class WeeklyChart(BaseChart):
    """Last 7 days: focused (green) vs distracted (red) bars."""
    def __init__(self, parent=None):
        super().__init__("Weekly Focus vs Distraction", "Last 7 days")
        self._data: list[tuple[str, int, int]] = []

    def refresh(self):
        recs = {r.day: r for r in ProductivityRepository.list_last_days(7)}
        out = []
        for i in range(6, -1, -1):
            d = datetime.now(timezone.utc) - timedelta(days=i)
            key = d.strftime("%Y-%m-%d")
            r = recs.get(key)
            out.append((
                d.strftime("%a"),
                r.focused_seconds if r else 0,
                r.distracted_seconds if r else 0,
            ))
        self._data = out
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        top = self.draw_title(p, w)

        mx, mb = 40, 40
        cw = w - mx * 2
        ch = h - top - mb
        if ch <= 0 or cw <= 0:
            p.end(); return

        max_val = max((max(f_, d_) for _, f_, d_ in self._data), default=1)
        if max_val <= 0:
            max_val = 1

        gw = cw / max(len(self._data), 1)
        bw = max((gw - 24) / 2, 5)

        for i, (label, focus, dist) in enumerate(self._data):
            bx = mx + i * gw + 12
            by = top + ch

            fh = (focus / max_val) * ch if max_val > 0 else 0
            if fh > 1:
                p.fillRect(QRectF(bx, by - fh, bw, fh), QColor(SUCCESS))

            dh = (dist / max_val) * ch if max_val > 0 else 0
            if dh > 1:
                p.fillRect(QRectF(bx + bw + 4, by - dh, bw, dh), QColor(DANGER))

            p.setPen(QColor(TEXT_SECONDARY))
            f = QFont(); f.setPointSize(8)
            p.setFont(f)
            p.drawText(
                QRectF(bx - 8, by + 8, gw, 18),
                Qt.AlignmentFlag.AlignHCenter, label,
            )

        # Legend
        p.setPen(QColor(SUCCESS))
        p.drawText(w - 180, 26, "■ Focus")
        p.setPen(QColor(DANGER))
        p.drawText(w - 105, 26, "■ Distraction")
        p.end()


class ThirtyDayFocusChart(BaseChart):
    """30-day focus-minutes line chart."""
    def __init__(self, parent=None):
        super().__init__("Focus Trend", "Last 30 days · minutes")
        self._data: list[int] = []

    def refresh(self):
        recs = {r.day: r for r in ProductivityRepository.list_last_days(30)}
        out = []
        for i in range(29, -1, -1):
            d = datetime.now(timezone.utc) - timedelta(days=i)
            key = d.strftime("%Y-%m-%d")
            r = recs.get(key)
            out.append(int((r.focused_seconds if r else 0) / 60))
        self._data = out
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        top = self.draw_title(p, w)

        mx, mb = 40, 30
        cw = w - mx * 2
        ch = h - top - mb
        if ch <= 0 or cw <= 0 or not self._data:
            p.end(); return

        max_v = max(max(self._data), 1)
        # Draw zero line
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawLine(mx, top + ch, mx + cw, top + ch)

        # Line
        pen = QPen(QColor(ACCENT_PRIMARY), 2)
        p.setPen(pen)
        step = cw / max(len(self._data) - 1, 1)
        prev_pt = None
        for i, v in enumerate(self._data):
            x = mx + i * step
            y = top + ch - (v / max_v) * ch
            if prev_pt is not None:
                p.drawLine(prev_pt, x, y) if False else p.drawLine(
                    int(prev_pt[0]), int(prev_pt[1]), int(x), int(y),
                )
            # Marker
            p.setBrush(QColor(ACCENT_PRIMARY))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)
            p.setPen(pen)
            prev_pt = (x, y)

        # Axis label
        p.setPen(QColor(TEXT_SECONDARY))
        f = QFont(); f.setPointSize(8)
        p.setFont(f)
        p.drawText(mx, top + ch + 18, "30 days ago")
        p.drawText(mx + cw - 40, top + ch + 18, "Today")
        p.end()


class HourDistributionChart(BaseChart):
    """Distractions grouped by hour of day (0-23)."""
    def __init__(self, parent=None):
        super().__init__("Distraction Hours", "Today · by hour")
        self._data: list[int] = [0] * 24

    def refresh(self):
        today = _today()
        data = [0] * 24
        try:
            events = DistractionRepository.list_recent(limit=200)
            for e in events:
                if not e.started_at.startswith(today):
                    continue
                # ISO: "YYYY-MM-DDTHH:MM:SS+00:00"
                try:
                    hour = int(e.started_at[11:13])
                    data[hour] += 1
                except Exception:
                    pass
        except Exception:
            pass
        self._data = data
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        top = self.draw_title(p, w)

        mx, mb = 40, 30
        cw = w - mx * 2
        ch = h - top - mb
        if ch <= 0 or cw <= 0:
            p.end(); return

        max_v = max(max(self._data), 1)
        bw = cw / 24
        for i, v in enumerate(self._data):
            if v <= 0:
                continue
            bh = (v / max_v) * ch
            x = mx + i * bw + 1
            p.fillRect(
                QRectF(x, top + ch - bh, bw - 2, bh),
                QColor(WARNING),
            )

        # X axis labels (every 6h)
        p.setPen(QColor(TEXT_SECONDARY))
        f = QFont(); f.setPointSize(8)
        p.setFont(f)
        for hh in (0, 6, 12, 18, 23):
            x = mx + hh * bw
            p.drawText(int(x), top + ch + 18, f"{hh:02d}")
        p.end()


class ProductivityTrendChart(BaseChart):
    """30-day productivity score (0-100) line chart."""
    def __init__(self, parent=None):
        super().__init__("Productivity Score", "Last 30 days")
        self._data: list[float] = []

    def refresh(self):
        recs = {r.day: r for r in ProductivityRepository.list_last_days(30)}
        out = []
        for i in range(29, -1, -1):
            d = datetime.now(timezone.utc) - timedelta(days=i)
            key = d.strftime("%Y-%m-%d")
            r = recs.get(key)
            out.append(r.productivity_score if r else 0.0)
        self._data = out
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        top = self.draw_title(p, w)

        mx, mb = 40, 30
        cw = w - mx * 2
        ch = h - top - mb
        if ch <= 0 or cw <= 0 or not self._data:
            p.end(); return

        # 0-100 range always
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawLine(mx, top + ch, mx + cw, top + ch)

        pen = QPen(QColor(ACCENT_SECONDARY), 2)
        p.setPen(pen)
        step = cw / max(len(self._data) - 1, 1)
        prev = None
        for i, v in enumerate(self._data):
            x = mx + i * step
            y = top + ch - (v / 100.0) * ch
            if prev is not None:
                p.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
            p.setBrush(QColor(ACCENT_SECONDARY))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)
            p.setPen(pen)
            prev = (x, y)

        p.setPen(QColor(TEXT_SECONDARY))
        f = QFont(); f.setPointSize(8)
        p.setFont(f)
        p.drawText(mx - 22, top + 10, "100")
        p.drawText(mx - 15, top + ch + 4, "0")
        p.end()


class AnalyticsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(10000)  # every 10s

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(20)

        outer.addWidget(SectionHeader(
            "Analytics",
            "Your focus history and trends · read live from local database",
        ))

        # Top stat row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        self.stat_total_focus = StatCard("Total Focus", "0h")
        self.stat_total_dist = StatCard("Total Distractions", "0")
        self.stat_avg_session = StatCard("Avg Session", "0m")
        self.stat_best_day = StatCard("Best Day", "—")
        for s in (self.stat_total_focus, self.stat_total_dist,
                  self.stat_avg_session, self.stat_best_day):
            stats_row.addWidget(s)
        outer.addLayout(stats_row)

        # 2x2 chart grid
        grid = QGridLayout()
        grid.setSpacing(16)

        self.weekly = WeeklyChart()
        self.thirtyday = ThirtyDayFocusChart()
        self.hourdist = HourDistributionChart()
        self.prodtrend = ProductivityTrendChart()

        grid.addWidget(self.weekly, 0, 0)
        grid.addWidget(self.thirtyday, 0, 1)
        grid.addWidget(self.hourdist, 1, 0)
        grid.addWidget(self.prodtrend, 1, 1)
        outer.addLayout(grid)

        outer.addStretch()

    def refresh(self):
        try:
            # Top cards
            all_recs = ProductivityRepository.list_last_days(365)
            total_focus_s = sum(r.focused_seconds for r in all_recs)
            total_dist = sum(r.distraction_count for r in all_recs)
            sessions = SessionRepository.list_recent(limit=500)
            done = [s for s in sessions if s.status == "completed"]
            avg_s = (
                sum(s.actual_seconds for s in done) / len(done) if done else 0
            )
            best = max(all_recs, key=lambda r: r.focused_seconds, default=None)

            self.stat_total_focus.set_value(f"{total_focus_s / 3600:.1f}h")
            self.stat_total_dist.set_value(str(total_dist))
            self.stat_avg_session.set_value(f"{int(avg_s / 60)}m")
            self.stat_best_day.set_value(
                f"{int(best.focused_seconds / 60)}m" if best else "—"
            )

            self.weekly.refresh()
            self.thirtyday.refresh()
            self.hourdist.refresh()
            self.prodtrend.refresh()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Analytics refresh failed")