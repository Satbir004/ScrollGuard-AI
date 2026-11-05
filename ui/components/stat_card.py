"""Reusable stats card: label, big value, optional delta."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class StatCard(QWidget):
    def __init__(
        self,
        title: str,
        value: str,
        delta: str = "",
        delta_color: str = "#22C55E",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        title_label = QLabel(title.upper())
        title_label.setObjectName("CardTitle")
        layout.addWidget(title_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        layout.addWidget(self.value_label)

        if delta:
            delta_label = QLabel(delta)
            delta_label.setObjectName("CardDelta")
            delta_label.setStyleSheet(f"color: {delta_color}; font-weight: 600;")
            layout.addWidget(delta_label)

        layout.addStretch()

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)