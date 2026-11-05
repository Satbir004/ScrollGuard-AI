"""Placeholder for pages not yet implemented (Phase 7.5+)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ui.components.section_header import SectionHeader


class PlaceholderPage(QWidget):
    def __init__(self, title: str, subtitle: str = "Coming in a later phase.", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        layout.addWidget(SectionHeader(title, subtitle))

        msg = QLabel("🚧  Under construction")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet("color: #94A3B8; font-size: 16px; padding: 60px;")
        layout.addWidget(msg)
        layout.addStretch()