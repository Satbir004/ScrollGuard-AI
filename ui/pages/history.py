"""
Distraction History — full table with date filtering.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox,
)

from database.repository import DistractionRepository
from ui.components.section_header import SectionHeader
from ui.styles.theme import (
    ACCENT_PRIMARY, CARD_BG, DANGER, SUCCESS, TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class HistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(16)

        # Header + controls row
        header_row = QHBoxLayout()
        header_row.addWidget(SectionHeader(
            "Distraction History",
            "Every confirmed phone-use event · stored locally",
        ), stretch=1)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All events", "Today", "Last 7 days", "Last 30 days"])
        self.filter_combo.setStyleSheet(
            f"QComboBox {{ background: {CARD_BG}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid #1F2A44; border-radius: 6px; padding: 6px 12px; }}"
        )
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        header_row.addWidget(self.filter_combo)

        self.delete_btn = QPushButton("🗑  Delete Selected")
        self.delete_btn.setObjectName("SecondaryButton")
        self.delete_btn.clicked.connect(self._delete_selected)
        header_row.addWidget(self.delete_btn)

        outer.addLayout(header_row)

        # Table card
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date & Time", "Duration", "Confidence", "Alert Fired",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {CARD_BG};
                color: {TEXT_PRIMARY};
                gridline-color: #1F2A44;
                border: none;
                font-size: 12px;
            }}
            QHeaderView::section {{
                background: #111827;
                color: {TEXT_SECONDARY};
                padding: 8px;
                border: none;
                border-bottom: 1px solid #1F2A44;
                font-weight: 600;
                font-size: 11px;
            }}
            QTableWidget::item:selected {{
                background: {ACCENT_PRIMARY};
                color: white;
            }}
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        card_layout.addWidget(self.table)
        outer.addWidget(card, stretch=1)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px;"
        )
        outer.addWidget(self.summary_label)

    def refresh(self):
        try:
            all_events = DistractionRepository.list_recent(limit=1000)
        except Exception:
            all_events = []

        # Apply filter
        idx = self.filter_combo.currentIndex()
        now = datetime.now(timezone.utc)
        events = all_events
        if idx == 1:  # today
            today = now.strftime("%Y-%m-%d")
            events = [e for e in all_events if e.started_at.startswith(today)]
        elif idx == 2:  # 7d
            cutoff = (now.replace(microsecond=0)).isoformat()[:10]
            from datetime import timedelta
            cutoff = (now - timedelta(days=7)).isoformat()[:10]
            events = [e for e in all_events if e.started_at[:10] >= cutoff]
        elif idx == 3:  # 30d
            from datetime import timedelta
            cutoff = (now - timedelta(days=30)).isoformat()[:10]
            events = [e for e in all_events if e.started_at[:10] >= cutoff]

        self.table.setRowCount(len(events))
        for i, e in enumerate(events):
            self.table.setItem(i, 0, QTableWidgetItem(str(e.id or "")))
            dt_str = e.started_at.replace("T", " ")[:19]
            self.table.setItem(i, 1, QTableWidgetItem(dt_str))
            self.table.setItem(i, 2, QTableWidgetItem(f"{e.duration_seconds}s"))
            conf = QTableWidgetItem(f"{e.confidence * 100:.0f}%")
            conf.setForeground(Qt.GlobalColor.white)
            self.table.setItem(i, 3, conf)
            alert = QTableWidgetItem("Yes" if e.alert_triggered else "No")
            self.table.setItem(i, 4, alert)

        # Summary
        if events:
            total_seconds = sum(e.duration_seconds for e in events)
            avg = total_seconds // len(events)
            self.summary_label.setText(
                f"{len(events)} events · "
                f"{total_seconds}s total · {avg}s average"
            )
        else:
            self.summary_label.setText("No events match the filter")

    def _delete_selected(self):
        rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        if not rows:
            return
        from database.db import get_connection
        conn = get_connection()
        try:
            for row in rows:
                id_item = self.table.item(row, 0)
                if not id_item:
                    continue
                try:
                    eid = int(id_item.text())
                except ValueError:
                    continue
                conn.execute("DELETE FROM distraction_events WHERE id = ?", (eid,))
            conn.commit()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Delete failed")
        self.refresh()